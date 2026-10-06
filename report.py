"""Render the TSMOM signal report (markdown + CSV) from a snapshot DataFrame."""

from __future__ import annotations  # py3.9-safe type hints

import os
import pandas as pd

ARROW = {1.0: "LONG", -1.0: "SHORT", 0.0: "FLAT"}


def _fmt_sig(x):
    return ARROW.get(x, "–")


def render(snap: pd.DataFrame, backtest_stats: dict | None = None,
           prev_snap: pd.DataFrame | None = None, out_dir: str = "reports",
           asof: str = "") -> tuple[str, str]:
    os.makedirs(out_dir, exist_ok=True)
    csv_path = os.path.join(out_dir, f"signals_{asof}.csv")
    md_path = os.path.join(out_dir, f"tsmom_report_{asof}.md")
    snap.to_csv(csv_path, index=False)

    flips = []
    if prev_snap is not None:
        prev = prev_snap.set_index("ticker")["sig_12m"]
        for _, row in snap.iterrows():
            p = prev.get(row["ticker"])
            if p is not None and not pd.isna(p) and not pd.isna(row["sig_12m"]) and p != row["sig_12m"]:
                flips.append(f"{row['name']}: {_fmt_sig(p)} -> {_fmt_sig(row['sig_12m'])}")

    lines = [f"# TSMOM Signal Report — {asof}", ""]
    lines.append(f"Headline signal: **12-month** time series momentum (MOP Eq. 5), "
                 f"vol-scaled to 40% ex-ante per instrument, equal risk across live instruments.")
    lines.append("")

    if flips:
        lines += ["## Signal flips since last run", ""] + [f"- {f}" for f in flips] + [""]
    elif prev_snap is not None:
        lines += ["_No 12-month signal flips since last run._", ""]

    # Portfolio tilt summary
    live = snap.dropna(subset=["portfolio_weight"])
    lines += ["## Portfolio summary", ""]
    lines.append(f"- Live instruments: {len(live)} of {len(snap)}")
    net = live["portfolio_weight"].sum()
    gross = live["portfolio_weight"].abs().sum()
    lines.append(f"- Net exposure: {net:+.2f}x | Gross exposure: {gross:.2f}x (of NAV, paper scaling)")
    for ac, grp in live.groupby("asset_class"):
        longs = (grp["sig_12m"] > 0).sum()
        shorts = (grp["sig_12m"] < 0).sum()
        lines.append(f"- {ac}: {longs} long / {shorts} short, net weight {grp['portfolio_weight'].sum():+.2f}x")
    lines.append("")

    lines += ["## Signals by instrument", ""]
    lines.append("| Instrument | Class | 3m | 6m | **12m** | Agree | 12m ret | Strength | Ex-ante vol | Unit wt | Port wt |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for _, r in snap.sort_values(["asset_class", "name"]).iterrows():
        stale = " ⚠stale" if r.get("stale") else ""
        lines.append(
            f"| {r['name']}{stale} | {r['asset_class']} | {_fmt_sig(r['sig_3m'])} | "
            f"{_fmt_sig(r['sig_6m'])} | **{_fmt_sig(r['sig_12m'])}** | {int(r['agreement'])}/2 | "
            f"{r['ret_12m']:+.1%} | {r.get('strength_z', float('nan')):+.2f}σ"f"{' ⚠' if r.get('weak') else ''} | {r['exante_vol']:.1%} | "
            f"{'' if pd.isna(r['unit_weight']) else f'{r.unit_weight:+.2f}x'} | "
            f"{'' if pd.isna(r['portfolio_weight']) else f'{r.portfolio_weight:+.3f}x'} |"
            if not pd.isna(r["ret_12m"]) else
            f"| {r['name']}{stale} | {r['asset_class']} | – | – | – | – | insufficient history | – | – | – | – |"
        )
    lines.append("")

    if backtest_stats:
        lines += ["## Backtest fingerprint (validation)", ""]
        lines.append("| Lookback | Ann. return | Ann. vol | Sharpe | Hit rate | Months |")
        lines.append("|---|---|---|---|---|---|")
        for k in sorted(backtest_stats):
            s = backtest_stats[k]
            lines.append(f"| {k}m | {s['ann_return']:+.1%} | {s['ann_vol']:.1%} | "
                         f"{s['sharpe']:.2f} | {s['hit_rate']:.0%} | {s['n_months']} |")
        lines.append("")

    lines.append("_Strength is the trailing return in standard deviations of that same 12-month "
                 "move, r / (sigma * sqrt(k/12)); |z| < 0.5 is marked as a coin-flip signal. "
                 "Signals, not advice._")

    with open(md_path, "w") as f:
        f.write("\n".join(lines))
    return md_path, csv_path
