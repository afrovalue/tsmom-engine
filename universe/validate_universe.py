"""Screen the candidate universe for a $10M fund and regenerate the engine's config.

Downloads every candidate in candidates.csv, applies history / staleness / liquidity
screens, then writes:
    ../instruments.csv                      the signal universe (passing names)
    ../implementation/contract_specs.csv    execution specs for the same names
    universe_report.md                      what passed, what failed and why

Run on a machine with internet (the cloud sandbox cannot reach Yahoo):
    python universe/validate_universe.py
    python universe/validate_universe.py --nav 10000000 --min-years 4
Then re-run the engine:
    python run.py --mode yahoo
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)

# A position can reach MAX_UNIT_LEV/N of NAV; we want it to be a modest slice of daily volume.
# 10% of one day's volume is workable for a MONTHLY-rebalanced book (entries can be worked
# over a day or two with limits); it would be far too aggressive for a daily trader.
MAX_ADV_SHARE = 0.10
START = "2005-01-01"

# Yahoo's Volume field for continuous futures (`XX=F`) reports the front-month quote only and
# is frequently partial or absent — measured values like Cotton $1.0M/day or Silver $20M/day
# are demonstrably wrong by orders of magnitude, and Platinum/Palladium return nothing at all.
# Screening futures on that field measures noise, not liquidity, so futures use a curated tier
# from `candidates.csv` instead. ETF volume on Yahoo IS reliable and is screened as measured.
TIER_FLOOR_USD = {          # approximate daily notional traded, order of magnitude
    "deep": 1_000_000_000,
    "moderate": 100_000_000,
    "thin": 20_000_000,
    "unrated": 20_000_000,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nav", type=float, default=10_000_000)
    ap.add_argument("--min-years", type=float, default=4.0,
                    help="minimum price history required (needs 12m lookback + backtest)")
    ap.add_argument("--stale-days", type=int, default=7)
    ap.add_argument("--keep-failed", action="store_true",
                    help="write every candidate through, screens become warnings only")
    args = ap.parse_args()

    import yfinance as yf

    cand = pd.read_csv(os.path.join(HERE, "candidates.csv"))
    cand = cand[cand["source_type"] != "skip"].drop_duplicates(subset=["ticker"])
    tickers = sorted(set(cand["ticker"]))
    print(f"downloading {len(tickers)} candidates …")
    raw = yf.download(tickers, start=START, progress=False, auto_adjust=True,
                      group_by="column")
    px = raw["Close"] if "Close" in raw else raw
    vol = raw["Volume"] if "Volume" in raw else pd.DataFrame(index=px.index)

    # Yahoo fails intermittently on individual tickers. Treating that as "this market does
    # not exist" would silently delete a deep market (it dropped Gold once) — so anything the
    # download missed falls back to the cached history before it is judged.
    cache_dir = os.path.join(ENGINE, "data_cache")
    recovered = []
    if os.path.isdir(cache_dir):
        for t in tickers:
            if t in px.columns and px[t].notna().sum() > 0:
                continue
            safe = ("IDX_" + t[1:]) if t.startswith("^") else t.replace("=", "_")
            f = os.path.join(cache_dir, safe + ".csv")
            if os.path.exists(f):
                try:
                    c = pd.read_csv(f)
                    c["Date"] = pd.to_datetime(c["Date"])
                    s = c.set_index("Date")["Close"].astype(float)
                    if len(s) > 0:
                        px[t] = s.reindex(px.index) if len(px.index) else s
                        recovered.append(t)
                except Exception:
                    pass
    if recovered:
        print(f"note: download failed for {len(recovered)} ticker(s), using cached history "
              f"instead of dropping them: {', '.join(recovered)}")

    # per-instrument budget: the largest single position this engine can ask for
    n_expected = max(len(cand), 1)
    max_pos_usd = args.nav * 5.0 / n_expected      # MAX_UNIT_LEV = 5x, equal-weighted
    min_adv = max_pos_usd / MAX_ADV_SHARE

    today = px.index[-1]
    rows = []
    for _, c in cand.iterrows():
        t = c["ticker"]
        s = px[t].dropna() if t in px.columns else pd.Series(dtype=float)
        rec = {"name": c["name"], "asset_class": c["asset_class"], "ticker": t,
               "source_type": c["source_type"], "n_obs": len(s)}
        if s.empty:
            rec.update({"verdict": "FAIL", "reason": "no data on Yahoo and none cached",
                        "years": 0, "last": None, "adv_usd": None})
            rows.append(rec); continue

        years = (s.index[-1] - s.index[0]).days / 365.25
        stale = (today - s.index[-1]).days
        last = float(s.iloc[-1])

        src = c["source_type"]
        tier = str(c.get("liquidity_tier") or "").strip()
        adv, adv_basis = None, "—"

        if src == "etf":                                   # Yahoo share volume is reliable here
            if t in vol.columns:
                v = vol[t].reindex(s.index).tail(60)
                if v.notna().sum() >= 20 and v.median() > 0:
                    adv, adv_basis = float(v.median()) * last, "measured"
        elif src == "futures":                             # curated tier, see note above
            adv, adv_basis = TIER_FLOOR_USD.get(tier or "unrated"), f"tier: {tier or 'unrated'}"

        reasons = []
        if years < args.min_years:
            reasons.append(f"only {years:.1f}y history")
        if stale > args.stale_days:
            reasons.append(f"stale {stale}d")
        if src == "fx_spot":
            pass                                           # OTC; no venue volume to measure
        elif adv is None:
            reasons.append("volume unavailable — review manually")
        elif adv < min_adv:
            reasons.append(f"ADV ${adv/1e6:.1f}M < ${min_adv/1e6:.1f}M needed")

        verdict = "PASS" if not reasons else "FAIL"
        override = str(c.get("override") or "").strip().lower()
        if override == "keep" and verdict == "FAIL":
            verdict, reasons = "PASS", [f"OVERRIDE keep (was: {'; '.join(reasons)})"]
        elif override == "drop":
            verdict, reasons = "FAIL", ["OVERRIDE drop"]

        # passes, but a full position is a big share of a day's trading
        thin = (verdict == "PASS" and adv is not None
                and max_pos_usd > 0.5 * MAX_ADV_SHARE * adv)

        rec.update({"verdict": verdict, "reason": "; ".join(reasons),
                    "years": round(years, 1), "last": round(last, 4),
                    "adv_usd": None if adv is None else round(adv, 0),
                    "adv_basis": adv_basis, "thin": thin})
        rows.append(rec)

    res = pd.DataFrame(rows)
    passed = res if args.keep_failed else res[res["verdict"] == "PASS"]
    keep = cand[cand["ticker"].isin(set(passed["ticker"]))].copy()

    # ---- write instruments.csv (signal universe) ----
    inst = keep[["name", "asset_class", "ticker", "source_type", "exec_ticker", "notes"]]
    inst.to_csv(os.path.join(ENGINE, "instruments.csv"), index=False)

    # ---- write contract_specs.csv (execution) ----
    spec = keep.copy()
    spec["exec_type"] = spec["source_type"].map(
        {"futures": "futures", "etf": "etf", "fx_spot": "fx"})
    spec = spec[["ticker", "exec_type", "exec_ticker", "multiplier", "price_factor",
                 "unit", "micro_symbol", "micro_multiplier", "notes"]]
    spec.to_csv(os.path.join(ENGINE, "implementation", "contract_specs.csv"), index=False)

    # ---- report ----
    L = [f"# Universe validation — {str(today.date())}", ""]
    L.append(f"Screened **{len(res)}** candidates for a **${args.nav:,.0f}** fund. "
             f"Largest single position ≈ ${max_pos_usd:,.0f} (5× cap ÷ {n_expected} names), "
             f"so a market needs ≥ **${min_adv/1e6:.0f}M** median daily dollar volume "
             f"to keep that position under {MAX_ADV_SHARE:.0%} of ADV.")
    L.append("")
    L.append(f"**{(res['verdict']=='PASS').sum()} passed · "
             f"{(res['verdict']=='FAIL').sum()} rejected · "
             f"{int(res['thin'].sum())} flagged thin (expect slippage).**")
    L.append("")
    L.append("> **How liquidity is judged.** ETFs are screened on measured median 60-day dollar "
             "volume. Futures are *not*: Yahoo's volume field for continuous contracts reports "
             "only the front-month quote and is often partial or missing, which produces "
             "nonsense (Cotton at $1M/day, Silver at $20M/day, Platinum blank). Futures instead "
             "use the curated `liquidity_tier` in `candidates.csv` — deep / moderate / thin — "
             "with order-of-magnitude floors. FX spot is OTC and screened on history only. "
             "Set `override` to `keep` or `drop` in `candidates.csv` to force any decision.")
    L.append("")
    for ac in ["Commodity", "Equity", "Bond", "FX"]:
        grp = res[res["asset_class"] == ac]
        if grp.empty:
            continue
        L.append(f"### {ac} — {(grp['verdict']=='PASS').sum()}/{len(grp)} passed")
        L.append("")
        L.append("| Instrument | Ticker | Type | History | Liquidity | Basis | Verdict |")
        L.append("|---|---|---|---|---|---|---|")
        for _, r in grp.iterrows():
            adv = "—" if r["adv_usd"] is None else f"${r['adv_usd']/1e6:,.0f}M"
            v = ("✓ thin" if r["thin"] else "✓") if r["verdict"] == "PASS" else f"✗ {r['reason']}"
            L.append(f"| {r['name']} | `{r['ticker']}` | {r['source_type']} | "
                     f"{r['years']}y | {adv} | {r['adv_basis']} | {v} |")
        L.append("")
    L.append("_FX spot pairs carry no exchange volume on Yahoo; OTC depth is assumed and they "
             "are screened on history only. Their returns exclude the interest differential, "
             "which is material for high-carry pairs (TRY, BRL, ZAR)._")

    rep = os.path.join(HERE, "universe_report.md")
    with open(rep, "w") as f:
        f.write("\n".join(L))
    res.to_csv(os.path.join(HERE, "validation_detail.csv"), index=False)

    print(f"\n{(res['verdict']=='PASS').sum()} passed, {(res['verdict']=='FAIL').sum()} rejected")
    for _, r in res[res["verdict"] == "FAIL"].iterrows():
        print(f"  ✗ {r['name']:24s} {r['ticker']:12s} {r['reason']}")
    print(f"\nwrote instruments.csv ({len(inst)} names), contract_specs.csv, {rep}")
    print("next:  python run.py --mode yahoo")


if __name__ == "__main__":
    main()
