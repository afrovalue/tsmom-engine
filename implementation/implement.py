"""Portfolio implementation: convert the report's weights into dollar targets and orders.

Takes the latest signals_*.csv from ../reports/ (portfolio weights as share of NAV),
the latest prices from ../data_cache/, and the contract specs beside this file, and
produces per-instrument dollar notionals, futures contract counts, and ETF share
counts for an adjustable portfolio size.

Usage:
    python implementation/implement.py --nav 1000000
    python implementation/implement.py --nav 250000 --micros     # micro contracts where listed
    python implementation/implement.py --nav 2e6 --scale 0.5     # halve all weights (20% unit vol)

Outputs (into this folder): positions_<date>.csv and implementation_<date>.md
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, ENGINE)
import tsmom  # noqa: E402


def latest_signals(reports_dir):
    files = sorted(glob.glob(os.path.join(reports_dir, "signals_*.csv")))
    if not files:
        raise FileNotFoundError("no signals_*.csv in reports/ — run run.py first")
    return files[-1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--nav", type=float, default=1_000_000,
                    help="portfolio size in dollars (default 1,000,000)")
    ap.add_argument("--scale", type=float, default=1.0,
                    help="multiply all weights (e.g. 0.5 = half the paper's 40%% unit vol)")
    ap.add_argument("--micros", action="store_true",
                    help="use micro contracts where a micro spec exists")
    ap.add_argument("--signals", default=None, help="path to a signals_*.csv (default: latest)")
    args = ap.parse_args()

    sig_path = args.signals or latest_signals(os.path.join(ENGINE, "reports"))
    asof = os.path.basename(sig_path).replace("signals_", "").replace(".csv", "")
    sig = pd.read_csv(sig_path)
    specs = pd.read_csv(os.path.join(HERE, "contract_specs.csv")).set_index("ticker")
    px = tsmom.load_csv_cache()
    last_px = {c: float(px[c].dropna().iloc[-1]) for c in px.columns if px[c].notna().any()}

    rows, skipped = [], []
    for _, r in sig.iterrows():
        t, w = r["ticker"], r.get("portfolio_weight", np.nan)
        if pd.isna(w) or bool(r.get("stale", False)):
            skipped.append(f"{r['name']} ({'stale price' if bool(r.get('stale', False)) else 'no weight'})")
            continue
        w *= args.scale
        target = w * args.nav
        sp = specs.loc[t] if t in specs.index else None
        exec_t = str(sp["exec_ticker"]) if sp is not None and isinstance(sp.get("exec_ticker"), str) else t
        price = last_px.get(exec_t, last_px.get(t, np.nan))
        row = {"name": r["name"], "asset_class": r["asset_class"], "ticker": t,
               "exec_ticker": exec_t,
               "signal": "LONG" if r["sig_12m"] > 0 else "SHORT",
               "weight": round(w, 4), "target_usd": round(target, 0)}
        if sp is None or sp["exec_type"] == "index" or pd.isna(price):
            row.update({"instrument": f"no price for {exec_t}",
                        "unit_usd": np.nan, "qty_exact": np.nan, "qty": np.nan,
                        "filled_usd": np.nan, "gap_usd": np.nan})
        elif sp["exec_type"] == "fx":
            # FX forwards trade in arbitrary notional — no contract rounding
            row.update({"instrument": f"{exec_t} forward notional",
                        "unit_usd": 1.0, "qty_exact": round(target, 0), "qty": round(target, 0),
                        "filled_usd": round(target, 0), "gap_usd": 0.0})
        elif sp["exec_type"] == "etf":
            shares = int(round(target / price))
            filled = shares * price
            row.update({"instrument": f"{exec_t} shares @ {price:,.2f}",
                        "unit_usd": round(price, 2),
                        "qty_exact": round(target / price, 1), "qty": shares,
                        "filled_usd": round(filled, 0), "gap_usd": round(filled - target, 0)})
        else:
            mult = float(sp["multiplier"]); label = exec_t
            if args.micros and isinstance(sp["micro_symbol"], str) and sp["micro_symbol"]:
                mult = float(sp["micro_multiplier"]); label = sp["micro_symbol"]
            unit = price * float(sp["price_factor"]) * mult
            n_exact = target / unit
            n = int(round(n_exact))
            filled = n * unit
            row.update({"instrument": f"{label} x {n:+d} (1 = ${unit:,.0f})",
                        "unit_usd": round(unit, 0),
                        "qty_exact": round(n_exact, 2), "qty": n,
                        "filled_usd": round(filled, 0), "gap_usd": round(filled - target, 0)})
        rows.append(row)

    out = pd.DataFrame(rows).sort_values(["asset_class", "name"])
    csv_path = os.path.join(HERE, f"positions_{asof}.csv")
    out.to_csv(csv_path, index=False)

    # ---- summary ----
    filled = out.dropna(subset=["filled_usd"])
    tgt_gross = out["target_usd"].abs().sum()
    tgt_net = out["target_usd"].sum()
    fil_gross = filled["filled_usd"].abs().sum()
    fil_net = filled["filled_usd"].sum()
    zeroed = filled[(filled["qty"] == 0) & (filled["target_usd"].abs() > 0)]
    overshoot = filled[filled["gap_usd"].abs() > 0.5 * filled["target_usd"].abs().clip(lower=1)]
    notional_only = out[out["filled_usd"].isna()]

    L = [f"# Implementation — {asof}", ""]
    L.append(f"NAV **${args.nav:,.0f}**"
             + (f" · weights scaled ×{args.scale}" if args.scale != 1 else "")
             + (" · micro contracts" if args.micros else ""))
    L.append("")
    L.append(f"- Target: net ${tgt_net:+,.0f} ({tgt_net/args.nav:+.2f}x) · "
             f"gross ${tgt_gross:,.0f} ({tgt_gross/args.nav:.2f}x)")
    L.append(f"- Filled after rounding: net ${fil_net:+,.0f} ({fil_net/args.nav:+.2f}x) · "
             f"gross ${fil_gross:,.0f} ({fil_gross/args.nav:.2f}x)")
    L.append(f"- Rounding gap: ${(filled['gap_usd'].abs().sum()):,.0f} across {len(filled)} instruments")
    if len(zeroed):
        L.append(f"- **{len(zeroed)} positions round to zero contracts** (target smaller than "
                 f"half a contract): {', '.join(zeroed['name'])}. "
                 "Consider --micros, a larger NAV, or accept the omission.")
    if len(overshoot):
        L.append(f"- {len(overshoot)} positions where one contract is lumpy vs target "
                 f"(fill misses by >50%): {', '.join(overshoot['name'])}")
    if len(notional_only):
        L.append(f"- Notional-only (no cached execution price — trade via listed ETF proxy): "
                 f"{', '.join(notional_only['name'])}")
    L.append("")
    L.append("| Instrument | Class | Signal | Weight | Target $ | Order | Filled $ | Gap $ |")
    L.append("|---|---|---|---|---|---|---|---|")
    for _, r in out.iterrows():
        if pd.isna(r.get("qty")):
            order = r["instrument"]                        # no execution price available
        elif "forward notional" in str(r["instrument"]):
            order = f"{r['exec_ticker']} {r['qty']:+,.0f} USD"
        elif " shares @" in str(r["instrument"]):
            order = f"{int(r['qty']):+,d} {r['exec_ticker']} sh"
        else:
            order = r["instrument"].split(" (")[0]         # e.g. "ES=F x -1" / "MES x +2"
        L.append(f"| {r['name']} | {r['asset_class']} | {r['signal']} | {r['weight']:+.3f}x | "
                 f"{r['target_usd']:+,.0f} | {order} | "
                 f"{'' if pd.isna(r['filled_usd']) else format(r['filled_usd'], '+,.0f')} | "
                 f"{'' if pd.isna(r['gap_usd']) else format(r['gap_usd'], '+,.0f')} |")
    if skipped:
        L += ["", f"_Skipped (stale/no weight): {', '.join(skipped)}_"]
    L += ["", "_Futures margin typically runs ~5–20% of gross notional (paper, footnote 8) — "
          "check your broker's requirements. Orders are month-end targets, not advice._"]

    md_path = os.path.join(HERE, f"implementation_{asof}.md")
    with open(md_path, "w") as f:
        f.write("\n".join(L))
    print(f"positions: {csv_path}\nsummary:   {md_path}")
    print(f"NAV ${args.nav:,.0f} → target gross {tgt_gross/args.nav:.2f}x, "
          f"filled gross {fil_gross/args.nav:.2f}x, "
          f"{len(zeroed)} zero-fills{' (try --micros)' if len(zeroed) and not args.micros else ''}")


if __name__ == "__main__":
    main()
