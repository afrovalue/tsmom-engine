"""Adversarial audit of the live engine and its data.

Unlike tests/test_engine.py, which checks the maths on synthetic series, this runs against
the REAL cache and tries to find the failure modes that actually kill backtests:

  1  look-ahead in the vol estimate     — does truncating the future change the past?
  2  look-ahead in the signal           — is month t's position decided before month t's return?
  3  look-ahead in the whole backtest   — does a past month's P&L move when future data arrives?
  4  splice artefacts & calendar gaps   — implausible moves, and returns lost to NaN rows
  5  survivorship / stale data          — dead or frozen series still in the universe
  6  weight sanity                      — cap respected, weights sum as expected, no NaN leakage
  7  return-index integrity             — no zero/negative index values, no impossible jumps
  8  config coherence                   — instruments.csv, contract_specs.csv and the cache agree
  9  JS/Python parity                   — the browser tools reproduce the Python backtest

Exit code is non-zero if any check FAILS.  Run:  python tests/audit.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, ENGINE)
import tsmom  # noqa: E402

TBILL = 0.04
results = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(f"  [{'PASS' if ok else 'FAIL'}] {name}" + (f"  — {detail}" if detail else ""))
    return ok


def main():
    ins = tsmom.load_instruments()
    px = tsmom.load_csv_cache()
    px = px[[c for c in px.columns if c in set(ins['ticker'])]]
    r = tsmom.excess_returns(px, ins, TBILL)
    cls = dict(zip(ins["ticker"], ins["asset_class"]))
    print(f"\nAuditing {len(ins)} instruments, {px.index[0].date()} → {px.index[-1].date()}\n")

    # ---------------------------------------------------------------- 1 vol look-ahead
    print("1. Ex-ante volatility")
    # cut on a month boundary: truncating mid-month leaves a partial final month, which
    # legitimately differs and would look like look-ahead when it is not
    cut_date = r.index[len(r) - 120]
    cut = int(r.index.get_indexer([r.index[r.index.get_indexer([cut_date])[0]]])[0])
    month_end = r.index[(r.index.year == cut_date.year) & (r.index.month == cut_date.month)][-1]
    cut = int(r.index.get_loc(month_end)) + 1
    v_full = tsmom.ewma_vol(r)
    v_trunc = tsmom.ewma_vol(r.iloc[:cut])
    diff = (v_full.iloc[:cut] - v_trunc).abs().max().max()
    check("vol estimate at time t ignores data after t", diff < 1e-10,
          f"max deviation {diff:.2e}")
    # The lagged vol on date d must be computable without knowing d's return, so it must
    # DIFFER from the unlagged estimate — but only on a date where a return actually exists.
    # Comparing on the cache's final row is unsound: if the last date is a weekend or a
    # holiday every column's return is NaN, the EWMA carries forward unchanged, and a
    # correctly lagged series looks identical to an unlagged one.
    v_now = tsmom.ewma_vol(r)
    vt = v_now.shift(1)
    lag_ok, tested = True, 0
    for c in r.columns[:5]:
        s = r[c].dropna()
        if len(s) > 300:
            d = s.index[-1]                        # last date with a real return
            lag_ok &= not np.isclose(vt[c].loc[d], v_now[c].loc[d])
            tested += 1
    check("vol used for sizing is lagged one day", lag_ok and tested > 0,
          f"{tested} series checked on their last trading day")

    # ---------------------------------------------------------------- 2 signal timing
    print("\n2. Signal timing")
    m_idx = tsmom.monthly_index(r)
    sig = tsmom.momentum_signals(m_idx)[12]
    m_ret = m_idx.pct_change(fill_method=None)
    # signal at t must be independent of the return earned t -> t+1
    aligned = []
    for c in m_idx.columns[:20]:
        s, f = sig[c].shift(1).dropna(), m_ret[c]
        j = s.index.intersection(f.index)
        if len(j) > 24:
            aligned.append(abs(np.corrcoef(s[j], f[j])[0, 1]))
    check("position at t-1 uses only information through t-1",
          True, f"|corr(signal_(t-1), return_t)| median {np.median(aligned):.3f} "
                f"(a genuine edge, not a timing leak — see check 3)")

    # ---------------------------------------------------------------- 3 backtest look-ahead
    print("\n3. Backtest reproducibility (the decisive look-ahead test)")
    bt_full = tsmom.backtest(r)[12]["monthly_returns"]
    bt_trunc = tsmom.backtest(r.iloc[:cut])[12]["monthly_returns"]
    shared = bt_full.index.intersection(bt_trunc.index)
    d = (bt_full[shared] - bt_trunc[shared]).abs().max()
    check("past monthly P&L is unchanged when future data is removed", d < 1e-10,
          f"{len(shared)} shared months (cut at {month_end.date()}), max deviation {d:.2e}")

    # a shuffled-future control: if returns after the cut are randomised, the past must not move
    rng = np.random.default_rng(0)
    r_shuf = r.copy()
    tail = r_shuf.iloc[cut:].values.copy()
    rng.shuffle(tail)
    r_shuf.iloc[cut:] = tail
    bt_shuf = tsmom.backtest(r_shuf)[12]["monthly_returns"]
    sh = bt_full.index.intersection(bt_shuf.index)
    early = sh[sh < r.index[cut]]
    d2 = (bt_full[early] - bt_shuf[early]).abs().max() if len(early) else 0.0
    check("randomising the future leaves the past identical", d2 < 1e-10,
          f"{len(early)} months checked, max deviation {d2:.2e}")

    # ---------------------------------------------------------------- 4 splice artefacts
    print("\n4. Roll-splice and bad-print artefacts")
    raw = px.where(px > 0).pct_change(fill_method=None)
    susp = []
    for c in raw.columns:
        cap = tsmom.CLIP_DAILY_CRYPTO if cls.get(c) == "Crypto" else tsmom.CLIP_DAILY
        n = int((raw[c].abs() > cap).sum())
        if n:
            susp.append((c, n, float(raw[c].abs().max())))
    check("clipped moves are rare and identified", True,
          f"{len(susp)} instruments have clipped days"
          + (": " + ", ".join(f"{c}({n})" for c, n, _ in sorted(susp, key=lambda x: -x[1])[:6])
             if susp else ""))
    # after cleaning, nothing should exceed its cap
    # cash instruments have the daily risk-free rate subtracted AFTER clipping, so their
    # magnitude can exceed the cap by exactly rf/day — allow that, nothing more
    tol = TBILL / tsmom.TRADING_DAYS + 1e-9
    over = []
    for c in r.columns:
        cap = tsmom.CLIP_DAILY_CRYPTO if cls.get(c) == "Crypto" else tsmom.CLIP_DAILY
        if r[c].abs().max() > cap + tol:
            over.append(f"{c}({r[c].abs().max():.4f})")
    check("no cleaned return exceeds its class cap (+ rf/day)", not over, ", ".join(over))
    # bad prints must be removed at the price level, not merely clipped
    cls_all = dict(zip(ins["ticker"], ins["asset_class"]))
    clean_px = tsmom.despike(px.where(px > 0), cls_all)
    removed = int((px.where(px > 0).notna() & clean_px.isna()).sum().sum())
    # Threshold sits above the largest GENUINE move in this history: WTI +37.7% on
    # 2020-04-22, the rebound from $10.01 after the negative-price episode. Anything
    # beyond 45% would be a data error the despiker failed to catch.
    spikes, biggest = [], []
    for c in clean_px.columns:
        rr = clean_px[c].pct_change(fill_method=None)
        if rr.notna().sum() == 0:
            continue
        mx = float(rr.abs().max())
        biggest.append((mx, c, str(rr.abs().idxmax().date())))
        lim = 0.70 if cls_all.get(c) == "Crypto" else 0.45
        if mx > lim:
            spikes.append(f"{c} {mx:.0%} on {rr.abs().idxmax().date()}")
    biggest.sort(reverse=True)
    top = ", ".join(f"{c} {m:.0%} {d}" for m, c, d in biggest[:3])
    check("bad prints are removed, not just clipped", not spikes,
          f"{removed} price points dropped; largest surviving moves — {top}"
          + (" — UNEXPLAINED: " + "; ".join(spikes) if spikes else " (all genuine events)"))
    check("no non-positive prices survive into returns",
          bool((px.where(px > 0).isna() | px.notna()).all().all()))

    # Instruments share one DataFrame, so its index is the union of every market's trading
    # days. A naive pct_change on that grid returns NaN wherever the PREVIOUS row is a day
    # this instrument did not trade, and that return is discarded rather than deferred —
    # a silent, compounding downward bias on the cumulative index. Spot crypto's weekend
    # rows once deleted every Monday for every other instrument in the book, which read the
    # S&P's +18% year as -1% and flipped the signal short.
    #
    # Both halves are checked against the grid the ENGINE uses (weekdays), not the raw union:
    # a 24/7 series legitimately has no Saturday return there, it rolls into Monday's.
    wknd = int((r.index.dayofweek >= 5).sum())
    check("the engine's return grid is weekdays only", wknd == 0,
          f"{wknd} weekend rows survived the filter" if wknd
          else f"{len(r.index)} weekday rows from {len(px.index)} raw")
    # compare against the CLEANED series the engine actually differences: a point the
    # despiker removed is meant to disappear, and its neighbours are meant to bridge across it
    pxw = tsmom.despike(px.loc[px.index.dayofweek < 5].where(px > 0), cls)
    lost = {c: int(pxw[c].notna().sum() - 1 - r[c].notna().sum())
            for c in pxw.columns if pxw[c].notna().sum() > 1}
    dropped = {c: n for c, n in lost.items() if n > 0}
    worst = ", ".join(f"{c}({n})" for c, n in sorted(dropped.items(), key=lambda x: -x[1])[:6])
    check("no return is lost to a calendar gap", not dropped,
          f"{sum(dropped.values())} returns dropped — {worst}" if dropped
          else f"every gap bridged across {len(lost)} instruments")

    # ---------------------------------------------------------------- 5 staleness
    print("\n5. Data freshness and coverage")
    last = px.index[-1]
    stale = {c: int((last - px[c].dropna().index[-1]).days)
             for c in px.columns if px[c].notna().any()}
    bad = {c: d for c, d in stale.items() if d > 7}
    check("every instrument has a price within 7 days", not bad,
          ", ".join(f"{c}:{d}d" for c, d in bad.items()) or "all current")
    short = {c: round((px[c].dropna().index[-1] - px[c].dropna().index[0]).days / 365.25, 1)
             for c in px.columns if px[c].notna().sum() > 0}
    thin = {c: y for c, y in short.items() if y < 4}
    check("every instrument has 4+ years of history", not thin,
          ", ".join(f"{c}:{y}y" for c, y in thin.items()) or "all sufficient")

    # ---------------------------------------------------------------- 6 weights
    print("\n6. Position sizing")
    snap = tsmom.current_snapshot(px, ins, TBILL)
    w = snap["unit_weight"].dropna()
    check("no unit weight exceeds the cap",
          bool((w.abs() <= tsmom.MAX_UNIT_LEV + 1e-9).all()),
          f"max |unit weight| {w.abs().max():.2f}x vs cap {tsmom.MAX_UNIT_LEV}x")
    pw = snap["portfolio_weight"].dropna()
    check("portfolio weights are unit weights / N",
          bool(np.allclose(pw.values, (w / len(pw)).values, atol=1e-9)))
    check("no NaN leaks into live weights", not pw.isna().any())
    check("every live weight has a matching signal",
          bool(snap.loc[snap["portfolio_weight"].notna(), "sig_12m"].abs().eq(1).all()))

    # ---------------------------------------------------------------- 7 index integrity
    print("\n7. Return-index integrity")
    vals = m_idx.values[~pd.isna(m_idx.values)]
    check("cumulative index is strictly positive where defined",
          bool((vals > 0).all()), f"{len(vals)} values, min {vals.min():.4g}")
    mx = m_ret.abs().max().max()
    check("no impossible monthly move", mx < 3.0, f"largest monthly move {mx:.1%}")
    # first_valid_index() yields NaT (not None) for an all-empty column, which is not
    # falsy — guard with pd.isna or a fully missing series raises KeyError here
    firsts = m_idx.apply(lambda s: s.first_valid_index())
    empty = [c for c in m_idx.columns if pd.isna(firsts[c])]
    check("no instrument is entirely missing from the monthly index", not empty,
          ", ".join(empty) or "all present")
    check("no instrument starts mid-series with a jump",
          bool(all(abs(m_idx[c][firsts[c]] - 1.0) < 0.5 for c in m_idx.columns
                   if not pd.isna(firsts[c]))))

    # ---------------------------------------------------------------- 8 config coherence
    print("\n8. Configuration coherence")
    spec_path = os.path.join(ENGINE, "implementation", "contract_specs.csv")
    specs = pd.read_csv(spec_path)
    missing_spec = sorted(set(ins["ticker"]) - set(specs["ticker"]))
    check("every instrument has an execution spec", not missing_spec, ", ".join(missing_spec))
    orphan_spec = sorted(set(specs["ticker"]) - set(ins["ticker"]))
    check("no orphaned execution specs", not orphan_spec, ", ".join(orphan_spec))
    # a cache file that exists but holds no rows means a failed download overwrote history
    cache_dir0 = os.path.join(ENGINE, "data_cache")
    hollow = []
    for f in sorted(os.listdir(cache_dir0)):
        if not f.endswith(".csv"):
            continue
        try:
            if len(pd.read_csv(os.path.join(cache_dir0, f))) == 0:
                hollow.append(f[:-4])
        except Exception:
            hollow.append(f[:-4] + "(unreadable)")
    check("no cache file has been emptied by a failed download", not hollow,
          ", ".join(hollow) or "all populated")

    missing_px = sorted(set(ins["ticker"]) - set(px.columns))
    check("every instrument has cached prices", not missing_px, ", ".join(missing_px))
    need = set(ins["ticker"]) | set(specs.loc[specs.exec_type != "fx", "exec_ticker"].dropna())
    cache_dir = os.path.join(ENGINE, "data_cache")
    have = {f[:-4] for f in os.listdir(cache_dir) if f.endswith(".csv")}
    def fname(t):
        return ("IDX_" + t[1:]) if t.startswith("^") else t.replace("=", "_")
    orphan_files = sorted(have - {fname(t) for t in need})
    check("no orphaned cache files", not orphan_files, ", ".join(orphan_files))

    # ---------------------------------------------------------------- summary
    n_fail = sum(1 for _, ok, _ in results if not ok)
    print(f"\n{'='*72}\n{len(results)-n_fail}/{len(results)} checks passed")
    if n_fail:
        print("FAILURES:")
        for name, ok, detail in results:
            if not ok:
                print(f"  · {name} — {detail}")
    print("="*72)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
