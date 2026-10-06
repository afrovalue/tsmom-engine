"""Orchestrator: fetch data (yahoo | csv), compute signals, write report.

Usage:
    python run.py --mode yahoo          # live download (needs network)
    python run.py --mode csv            # read data_cache/*.csv
"""

from __future__ import annotations

import argparse
import glob
import os
import sys

import pandas as pd

import tsmom
import report as report_mod

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["yahoo", "csv"], default="yahoo")
    ap.add_argument("--start", default="2005-01-01")
    ap.add_argument("--vol-target", type=float, default=tsmom.VOL_TARGET)
    ap.add_argument("--tbill", type=float, default=0.04,
                    help="annual T-bill rate used for ETF/index excess returns")
    ap.add_argument("--out", default=os.path.join(HERE, "reports"))
    args = ap.parse_args()

    ins = tsmom.load_instruments()
    if args.mode == "yahoo":
        # signal universe + any execution-only proxies named in contract_specs.csv
        tickers = list(ins["ticker"])
        spec_path = os.path.join(HERE, "implementation", "contract_specs.csv")
        if os.path.exists(spec_path):
            specs = pd.read_csv(spec_path)
            specs = specs[specs["exec_type"] != "fx"]     # FX forwards have no Yahoo ticker
            extra = sorted(set(specs["exec_ticker"].dropna()) - set(tickers))
            if extra:
                print(f"also fetching execution proxies: {', '.join(extra)}")
                tickers += extra
        px = tsmom.fetch_yahoo(tickers, start=args.start)
        # persist for offline reuse
        cache = os.path.join(HERE, "data_cache")
        os.makedirs(cache, exist_ok=True)
        # A transient Yahoo failure returns an empty or truncated series. Writing that over
        # a good cache destroys history that cannot be recovered, so the cache is only
        # replaced when the download is at least as complete as what we already hold.
        for c in px.columns:
            safe = ("IDX_" + c[1:]) if c.startswith("^") else c.replace("=", "_")
            path = os.path.join(cache, f"{safe}.csv")
            new = px[c].dropna()
            n_old = 0
            if os.path.exists(path):
                try:
                    n_old = len(pd.read_csv(path))
                except Exception:
                    n_old = 0
            if len(new) == 0:
                print(f"WARNING: {c} downloaded empty — keeping {n_old} cached rows",
                      file=sys.stderr)
                continue
            if n_old and len(new) < n_old * 0.9:
                print(f"WARNING: {c} downloaded {len(new)} rows vs {n_old} cached — "
                      f"keeping the cache", file=sys.stderr)
                continue
            new.rename("Close").to_csv(path)
        # exec proxies are cached for pricing only — keep signals on the universe
        px = px[[c for c in px.columns if c in set(ins["ticker"])]]
    else:
        px = tsmom.load_csv_cache()
        keep = [c for c in px.columns if c in set(ins["ticker"])]
        missing = sorted(set(ins["ticker"]) - set(keep))
        if missing:
            print(f"note: no data for {len(missing)} instruments: {', '.join(missing)}",
                  file=sys.stderr)
        px = px[keep]

    r = tsmom.excess_returns(px, ins, args.tbill)
    snap = tsmom.current_snapshot(px, ins, args.tbill, args.vol_target)
    bt = tsmom.backtest(r, vol_target=args.vol_target)
    bt_stats = {k: {kk: vv for kk, vv in v.items()
                    if kk not in ("monthly_returns", "instrument_returns")}
                for k, v in bt.items()}

    asof = str(px.index[-1].date())
    prev = None
    prior = sorted(glob.glob(os.path.join(args.out, "signals_*.csv")))
    prior = [p for p in prior if asof not in p]
    if prior:
        prev = pd.read_csv(prior[-1])

    md, csv = report_mod.render(snap, bt_stats, prev, args.out, asof)
    print(f"report: {md}\nsignals: {csv}")

    # rebuild the interactive tools — one data file drives both hosted pages, which
    # recompute signals, weights, risk and orders live for any parameter setting
    try:
        sys.path.insert(0, os.path.join(HERE, "analytics"))
        import build_console
        build_console.main()
    except Exception as e:
        print(f"console build skipped: {e}", file=sys.stderr)

    for k in sorted(bt_stats):
        st = bt_stats[k]
        print(f"  {k:>2}m backtest: Sharpe {st['sharpe']:.2f}, ann vol {st['ann_vol']:.1%}, "
              f"{st['n_months']} months")


if __name__ == "__main__":
    main()
