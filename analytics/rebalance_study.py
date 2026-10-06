"""Does the rebalance interval matter, and is monthly the right one?

The engine rebalances monthly because MOP's TSMOM(k, h) uses h = 1 month. That is a
specification, not a finding, so this tests it directly: re-form the book every N trading
days, hold until the next rebalance, and measure what happens to return, risk and turnover.

Two things are separated, because they pull in opposite directions:

  * GROSS Sharpe. Slower rebalancing means the vol estimate driving position size is older,
    so the book is less well risk-targeted. This should cost a little.
  * NET Sharpe. Slower rebalancing means less turnover, so less is paid in spread. This
    should gain a little. Where the two cross is the answer.

Turnover is measured as the sum of |w_new - w_old| across instruments at each rebalance,
annualised — the standard "one-way turnover" convention, so 1.0 means the book's gross
notional is replaced once a year.

    python3 rebalance_study.py --engine ~/Downloads/TS_MOM/tsmom_engine
"""

from __future__ import annotations

import argparse
import os
import sys

import numpy as np
import pandas as pd

TBILL = 0.04
TRADING_DAYS = 261


def run(r: pd.DataFrame, vol: pd.DataFrame, midx: pd.DataFrame, step: int,
        k: int = 12, vt: float = 0.40, cap: float | None = None,
        spread_bps: float = 0.0):
    """Rebalance every `step` trading days; hold the weights in between.

    Weights are formed from information available on the rebalance date only: the trailing
    k-month return through that date and the vol estimate lagged one day. Between
    rebalances the position is held fixed in WEIGHT terms, which is what a monthly-order
    workflow actually does — it does not drift with price.
    """
    dates = r.index
    reb = list(range(0, len(dates), step))
    w = pd.Series(0.0, index=r.columns)
    prev = w.copy()

    daily, turn_events = [], []
    lookback_days = int(round(k * TRADING_DAYS / 12))

    reb = set(reb)
    for i, d in enumerate(dates):
        # Earn FIRST, with the weights already in force, then rebalance. Doing it the other
        # way round lets the weight set on day i earn day i's own return, using a trailing
        # index that already contains it — a one-day look-ahead on every rebalance date, and
        # therefore five times as much of it at weekly as at monthly. It shows up as a clean
        # monotone "faster is better", which is exactly the answer one wants to be careful of.
        daily.append(float((w * r.iloc[i].fillna(0.0)).sum()))
        if i in reb and i >= lookback_days:
            # trailing k-month return from the cumulative index, on the rebalance date
            idx_now, idx_then = midx.iloc[i], midx.iloc[i - lookback_days]
            tr = idx_now / idx_then - 1.0
            v = vol.iloc[i]                      # already lagged one day
            live = tr.notna() & v.notna() & (v > 0)
            if live.sum() >= 5:
                lev = vt / v[live]
                if cap is not None:
                    lev = lev.clip(upper=cap)
                new = np.sign(tr[live]) * lev / live.sum()
                new = new.reindex(r.columns).fillna(0.0)
                turn_events.append(float((new - prev).abs().sum()))
                prev, w = new, new

    pnl = pd.Series(daily, index=dates)
    if not len(turn_events):
        return None

    # one-way turnover per year, and the spread it costs at `spread_bps` round trip
    years = (dates[-1] - dates[0]).days / 365.25
    turnover = sum(turn_events) / years
    cost_yr = turnover * spread_bps / 1e4

    ann = pnl.mean() * TRADING_DAYS
    vol_ann = pnl.std() * np.sqrt(TRADING_DAYS)
    eq = (1 + pnl).cumprod()
    dd = (eq / eq.cummax() - 1).min()
    return {"step": step, "ann": ann, "vol": vol_ann,
            "sharpe": ann / vol_ann if vol_ann > 0 else 0.0,
            "net_sharpe": (ann - cost_yr) / vol_ann if vol_ann > 0 else 0.0,
            "turnover": turnover, "cost_yr": cost_yr, "maxdd": dd,
            "n_reb": len(turn_events)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", default=os.path.expanduser("~/Downloads/TS_MOM/tsmom_engine"))
    ap.add_argument("--spread-bps", type=float, default=8.0,
                    help="round-trip transaction cost on turnover, in bps of notional")
    ap.add_argument("--cap", type=float, default=None, help="leverage cap (default uncapped)")
    args = ap.parse_args()

    sys.path.insert(0, args.engine)
    import tsmom

    ins = tsmom.load_instruments(os.path.join(args.engine, "instruments.csv"))
    px = tsmom.load_csv_cache(os.path.join(args.engine, "data_cache"))
    px = px[[c for c in px.columns if c in set(ins["ticker"])]]
    r = tsmom.excess_returns(px, ins, TBILL)
    vol = tsmom.ewma_vol(r).shift(1)
    midx = (1 + r.fillna(0.0)).cumprod().where(r.notna().cummax())

    print(f"{len(ins)} instruments · {r.index[0].date()} → {r.index[-1].date()} · "
          f"{len(r)} trading days")
    print(f"cost assumption: {args.spread_bps:.0f} bps round trip on turnover · "
          f"cap: {'uncapped' if args.cap is None else f'{args.cap:g}x'}\n")

    GRID = [(5, "weekly"), (10, "2 weeks"), (15, "3 weeks"), (21, "monthly"),
            (30, "6 weeks"), (42, "2 months"), (63, "quarterly"),
            (84, "4 months"), (126, "half-yearly")]

    print(f"{'interval':<14}{'days':>5}{'ann':>8}{'vol':>8}{'Sharpe':>9}"
          f"{'turnover':>10}{'cost':>8}{'net SR':>9}{'maxDD':>9}")
    print("-" * 80)
    rows = []
    for step, label in GRID:
        res = run(r, vol, midx, step, cap=args.cap, spread_bps=args.spread_bps)
        if not res:
            continue
        rows.append((label, res))
        print(f"{label:<14}{step:>5}{res['ann']:>8.1%}{res['vol']:>8.1%}"
              f"{res['sharpe']:>9.2f}{res['turnover']:>9.1f}x{res['cost_yr']:>8.2%}"
              f"{res['net_sharpe']:>9.2f}{res['maxdd']:>9.1%}")

    # Cross-check: the step=21 row is approximately the engine's own monthly backtest, which
    # is independently audited for look-ahead. If they disagree materially, this script is
    # wrong, not the engine.
    eng = tsmom.backtest(r, vol_target=0.40, cap=args.cap)[12]
    mine = next((x[1]["sharpe"] for x in rows if x[0] == "monthly"), None)
    print(f"\ncross-check — engine's calendar-monthly 12m Sharpe {eng['sharpe']:.2f} "
          f"vs this study's 21-day row {mine:.2f}"
          + ("  ✓" if mine is not None and abs(mine - eng['sharpe']) < 0.10
             else "  ⚠ these should be close; investigate before trusting the table"))

    best_g = max(rows, key=lambda x: x[1]["sharpe"])
    best_n = max(rows, key=lambda x: x[1]["net_sharpe"])
    print(f"\nbest gross: {best_g[0]} ({best_g[1]['sharpe']:.2f})   "
          f"best net: {best_n[0]} ({best_n[1]['net_sharpe']:.2f})")

    # How much of the spread in these numbers is signal and how much is noise? The standard
    # error of a Sharpe over T years is about sqrt((1 + SR^2/2)/T); anything inside that is
    # not a finding.
    yrs = (r.index[-1] - r.index[0]).days / 365.25
    sr = best_g[1]["sharpe"]
    se = np.sqrt((1 + sr * sr / 2) / yrs)
    print(f"Sharpe standard error over {yrs:.0f} years ≈ {se:.2f} — differences smaller "
          f"than that are noise, not evidence.")


if __name__ == "__main__":
    main()
