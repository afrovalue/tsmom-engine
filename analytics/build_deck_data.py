"""Regenerate deck_data.json from the live engine.

The deck's numbers were originally computed ad hoc, which meant a correction to the engine
could not be pushed into the slides without redoing that work by hand. This script derives
every figure the deck uses from the same code path the engine runs, so the two cannot drift.

    python3 build_deck_data.py --engine ~/Downloads/TS_MOM/tsmom_engine
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

TBILL = 0.04
BENCH = "ES=F"          # S&P 500 futures: excess returns by construction


def stats(ret: pd.Series) -> dict:
    n = len(ret)
    mean, sd = ret.mean(), ret.std()
    ann, vol = mean * 12, sd * np.sqrt(12)
    eq = (1 + ret).cumprod()
    dd = eq / eq.cummax() - 1
    neg = ret[ret < 0]
    dsd = np.sqrt((neg ** 2).sum() / n) * np.sqrt(12) if len(neg) else 0.0
    # `ann` is the arithmetic annualisation, which is what the Sharpe ratio is built from.
    # `cagr` is what a growth-of-$1 chart actually shows; at 14% vol the two differ by about
    # a point, so a slide that puts a compounded curve under an arithmetic number invites
    # exactly the question of why they disagree. Both are shipped and each is used where it
    # belongs.
    cagr = float(eq.iloc[-1]) ** (12 / n) - 1 if n else 0.0
    return {"sharpe": round(ann / vol, 4) if vol > 0 else 0.0,
            "sortino": round(ann / dsd, 4) if dsd > 0 else 0.0,
            "ann": round(ann, 4), "cagr": round(cagr, 4), "vol": round(vol, 4),
            "maxdd": round(dd.min(), 4), "hit": round((ret > 0).mean(), 3),
            "dd_months": int((dd < -1e-9).astype(int)
                             .groupby((dd >= -1e-9).cumsum()).sum().max() or 0),
            "months": int(n)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=os.path.expanduser("~/Downloads/TS_MOM/tsmom_engine"))
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                  "deck_data.json"))
    # MOP Eq. 5 is uncapped. The live engine caps at 5x because uncapped sizing demands 30x+
    # on 2-year notes, but the deck shows the paper's specification unless told otherwise.
    ap.add_argument("--cap", type=float, default=None,
                    help="leverage cap per instrument; omit for the paper's uncapped Eq. 5")
    args = ap.parse_args()

    sys.path.insert(0, args.engine)
    import tsmom

    ins = tsmom.load_instruments(os.path.join(args.engine, "instruments.csv"))
    px = tsmom.load_csv_cache(os.path.join(args.engine, "data_cache"))
    px = px[[c for c in px.columns if c in set(ins["ticker"])]]
    r = tsmom.excess_returns(px, ins, TBILL)
    bt = tsmom.backtest(r, cap=args.cap)

    D = {"asof": str(px.index[-1].date()), "n_inst": int(len(ins)), "cap": args.cap,
         "universe": {k: int(v) for k, v in
                      ins["asset_class"].value_counts().to_dict().items()}}
    for k in (12, 6, 3):
        D[f"stats{k}"] = stats(bt[k]["monthly_returns"])

    ret12 = bt[12]["monthly_returns"]
    eq = (1 + ret12).cumprod()
    dd = eq / eq.cummax() - 1

    # benchmark on exactly the strategy's months, rebased to the same start
    m_idx = tsmom.monthly_index(r)
    bench_m = m_idx[BENCH].pct_change(fill_method=None).reindex(ret12.index).fillna(0.0)
    spx = (1 + bench_m).cumprod()

    # quarterly sample keeps the curve readable at slide size
    q = [i for i, d in enumerate(ret12.index) if d.month % 3 == 0]
    # the true first and last month of the return series — eq_dates starts at the first
    # QUARTER end, which is up to two months later and misstates the window on three slides
    D["month_first"] = ret12.index[0].strftime("%Y-%m")
    D["month_last"] = ret12.index[-1].strftime("%Y-%m")
    D["eq_dates"] = [ret12.index[i].strftime("%Y-%m") for i in q]
    D["eq_vals"] = [round(float(eq.iloc[i]), 4) for i in q]
    D["spx_vals"] = [round(float(spx.iloc[i]), 4) for i in q]
    D["dd_vals"] = [round(float(dd.iloc[i]), 4) for i in q]

    yr = ret12.groupby(ret12.index.year).apply(lambda s: (1 + s).prod() - 1)
    D["years"] = [int(y) for y in yr.index]
    D["yr_vals"] = [round(float(v), 4) for v in yr.values]

    # crisis alpha: the benchmark's ten worst months and what the strategy did in them
    worst = bench_m.nsmallest(10)
    D["crisis"] = [[d.strftime("%Y-%m"), round(float(bench_m[d]), 4),
                    round(float(ret12[d]), 4)] for d in worst.index]
    D["crisis_avg"] = [round(float(worst.mean()), 4),
                       round(float(ret12[worst.index].mean()), 4)]
    D["crisis_hit"] = int((ret12[worst.index] > 0).sum())

    # Per-sleeve books. Each instrument's monthly P&L is sign x leverage x return and does
    # not depend on how many others are live, so a sleeve is just the equal-weight average
    # of its own columns. Re-running tsmom.backtest per sleeve would instead apply its
    # "at least 5 live instruments" guard and silently return nothing for crypto, which has
    # two — the sleeve would vanish from the deck rather than show a small sample.
    instr = bt[12]["instrument_returns"]
    D["sleeve"] = {}
    for ac, grp in ins.groupby("asset_class"):
        cols = [c for c in grp["ticker"] if c in instr.columns]
        if not cols:
            continue
        sub = instr[cols].mean(axis=1).dropna()
        if len(sub) > 12:
            D["sleeve"][ac] = {**stats(sub), "n": int(len(cols))}

    snap = tsmom.current_snapshot(px, ins, TBILL)
    live = snap.dropna(subset=["portfolio_weight"])
    D["sl_now"] = {ac: {"long": int((g["sig_12m"] > 0).sum()),
                        "short": int((g["sig_12m"] < 0).sum()),
                        "net": round(float(g["portfolio_weight"].sum()), 4)}
                   for ac, g in live.groupby("asset_class")}

    # realised beta to the benchmark, split by the sign of the benchmark's month
    def beta(mask=None):
        x = bench_m if mask is None else bench_m[mask]
        y = ret12 if mask is None else ret12[mask]
        if len(x) < 12 or x.var() == 0:
            return 0.0
        return round(float(np.cov(x, y)[0, 1] / x.var()), 4)
    D["beta_all"] = beta()
    D["beta_down"] = beta(bench_m < 0)
    D["beta_up"] = beta(bench_m > 0)
    D["corr"] = round(float(np.corrcoef(bench_m, ret12)[0, 1]), 4)

    # Split the sample in half. The labels are emitted with the data rather than hard-coded
    # in the deck, so the slide always describes the halves it is actually showing.
    y0, y1 = ret12.index[0].year, ret12.index[-1].year
    mid = y0 + (y1 - y0) // 2
    # Two splits, one year apart. The "trend has decayed" claim turns out to depend entirely
    # on where the sample is cut — 2006-15 vs 2016-26 shows decay, 2006-16 vs 2017-26 shows
    # the opposite — so both are carried and the deck reports the instability rather than
    # picking the cut that suits it.
    D["regime"], D["regime_keys"] = {}, []
    for c in (mid - 1, mid):
        ka, kb = f"{y0}-{c}", f"{c+1}-{y1}"
        D["regime"][ka] = stats(ret12[ret12.index.year <= c])
        D["regime"][kb] = stats(ret12[ret12.index.year > c])
        D["regime_keys"].append([ka, kb])

    with open(args.out, "w") as f:
        json.dump(D, f, indent=1)
    print(f"wrote {args.out}")
    print(f"  cap: {'uncapped (paper Eq. 5)' if args.cap is None else f'{args.cap:g}x'}")
    print(f"  {D['n_inst']} instruments · {D['stats12']['months']} months · "
          f"12m Sharpe {D['stats12']['sharpe']:.2f} · vol {D['stats12']['vol']:.1%} · "
          f"maxDD {D['stats12']['maxdd']:.1%}")
    print(f"  sleeves: " + ", ".join(f"{k} {v['sharpe']:.2f}" for k, v in D["sleeve"].items()))
    eras = " vs ".join(f"{k} {v['sharpe']:.2f}" for k, v in D["regime"].items())
    print(f"  beta {D['beta_all']:.2f} · crisis hit {D['crisis_hit']}/10 · eras {eras}")


if __name__ == "__main__":
    main()
