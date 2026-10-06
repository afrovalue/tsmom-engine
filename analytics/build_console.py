"""One data file that lets every dashboard recompute itself live.

Rather than pre-computing results for a fixed vol target and leverage cap, this ships the
raw monthly series so the browser can rebuild signals, weights, the backtest and the risk
decomposition for ANY parameter setting:

    midx[i][t]   monthly cumulative excess-return index for instrument i
    mvol[i][t]   annualized EWMA vol (MOP Eq. 1) known at month-end t (already lagged a day)
    corr         shrunk correlation matrix over the recent window, for the risk model

Everything downstream follows from those:
    trailing k-month return   = midx[t] / midx[t-k] - 1
    signal                    = sign(trailing return), 0 inside the deadband
    leverage                  = min(vol_target / vol, cap)
    weight                    = signal * leverage / N

Writes ../reports/console_data.json plus the two rendered pages.
Called by run.py; standalone:  python analytics/build_console.py
"""

from __future__ import annotations

import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.dirname(HERE)
sys.path.insert(0, ENGINE)
import tsmom  # noqa: E402

TBILL = 0.04
CORR_WINDOW = 750        # ~3y of daily observations for the correlation estimate
CORR_MIN_OBS = 250       # an instrument needs this many to enter the risk model
SHRINK = 0.20            # toward the average pairwise correlation (Ledoit-Wolf in spirit)


def shrunk_correlation(rets: pd.DataFrame) -> pd.DataFrame:
    """Sample correlation, shrunk toward constant-correlation, then made PSD."""
    c = rets.corr(min_periods=CORR_MIN_OBS)
    keep = c.notna().sum() > len(c) * 0.5
    c = c.loc[keep, keep].fillna(0.0)
    np.fill_diagonal(c.values, 1.0)

    off = c.values[~np.eye(len(c), dtype=bool)]
    target = np.full(c.shape, float(np.mean(off)))
    np.fill_diagonal(target, 1.0)
    m = (1 - SHRINK) * c.values + SHRINK * target

    vals, vecs = np.linalg.eigh(m)          # clip negative eigenvalues -> valid covariance basis
    if vals.min() < 1e-8:
        vals = np.clip(vals, 1e-8, None)
        m = vecs @ np.diag(vals) @ vecs.T
        d = np.sqrt(np.diag(m))
        m = m / np.outer(d, d)
    return pd.DataFrame(m, index=c.index, columns=c.columns)


def r6(x):
    """Round to significant figures, not decimal places — a cumulative index that has fallen
    to 0.04 needs the same relative precision as one that has risen to 40."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return None
    return float(f"{float(x):.9g}")


def main():
    ins = tsmom.load_instruments()
    px = tsmom.load_csv_cache()
    keep = [c for c in px.columns if c in set(ins["ticker"])]
    px_u = px[keep]
    r = tsmom.excess_returns(px_u, ins, TBILL)

    midx = tsmom.monthly_index(r)
    mvol = tsmom.ewma_vol(r).shift(1).resample(tsmom.MONTH_END).last()
    mvol = mvol.reindex(midx.index)
    corr = shrunk_correlation(r.tail(CORR_WINDOW))

    # execution specs
    spec_path = os.path.join(ENGINE, "implementation", "contract_specs.csv")
    specs = pd.read_csv(spec_path).set_index("ticker") if os.path.exists(spec_path) else None
    last = {c: float(px[c].dropna().iloc[-1]) for c in px.columns if px[c].notna().any()}

    order = [t for t in ins["ticker"] if t in midx.columns]
    name_map = dict(zip(ins["ticker"], ins["name"]))
    cls_map = dict(zip(ins["ticker"], ins["asset_class"]))

    inst, MIDX, MVOL = [], [], []
    for t in order:
        sp = specs.loc[t] if (specs is not None and t in specs.index) else None
        exec_t = str(sp["exec_ticker"]) if sp is not None and isinstance(sp.get("exec_ticker"), str) else t
        price = last.get(exec_t, last.get(t))
        kind, unit, micro, micro_unit, note = "unpriced", None, None, None, ""
        if sp is not None and price is not None:
            et = str(sp["exec_type"])
            if et == "fx":
                kind, unit, note = "fx", 1.0, "forward notional"
            elif et == "etf":
                kind, unit, note = "etf", round(price, 4), "shares"
            else:
                kind = "futures"
                unit = round(price * float(sp["price_factor"]) * float(sp["multiplier"]), 2)
                note = str(sp["unit"])
                if isinstance(sp["micro_symbol"], str) and sp["micro_symbol"]:
                    micro = sp["micro_symbol"]
                    micro_unit = round(price * float(sp["price_factor"])
                                       * float(sp["micro_multiplier"]), 2)
        inst.append({"n": name_map[t], "ac": cls_map[t], "t": t, "x": exec_t, "k": kind,
                     "u": unit, "m": micro, "mu": micro_unit, "note": note,
                     "v": r6(mvol[t].iloc[-1]) if t in mvol else None})
        MIDX.append([r6(v) if pd.notna(v) else None for v in midx[t]])
        MVOL.append([r6(v) if pd.notna(v) else None for v in mvol[t]])

    # S&P 500 futures excess returns, for realised beta in the Lab
    BENCH_TICKER = "ES=F"
    bench = None
    if BENCH_TICKER in midx.columns:
        br = midx[BENCH_TICKER].pct_change(fill_method=None)
        bench = [r6(v) if pd.notna(v) else None for v in br]

    risk_idx = [order.index(t) for t in corr.index if t in order]
    risk_tk = [order[i] for i in risk_idx]
    C = corr.loc[risk_tk, risk_tk].round(4).values.tolist()

    data = {
        "asof": str(px.index[-1].date()),
        "month_end": str(midx.index[-1].date()),
        # two reference points: what the paper actually specifies (Eq. 5 is UNCAPPED), and
        # what this engine runs by default (a 5x cap, since 30x on 2Y notes is unfundable)
        "paper": {"vol_target": tsmom.VOL_TARGET, "cap": None, "deadband": 0.0},
        "defaults": {"vol_target": tsmom.VOL_TARGET, "cap": tsmom.MAX_UNIT_LEV,
                     "deadband": 0.0, "nav": 10_000_000},
        "corr_window": CORR_WINDOW, "shrink": SHRINK,
        "dates": [str(d.date()) for d in midx.index],
        "inst": inst, "midx": MIDX, "mvol": MVOL,
        "bench": bench, "bench_name": "S&P 500",
        "risk_idx": risk_idx, "corr": C,
    }

    reports = os.path.join(ENGINE, "reports")
    os.makedirs(reports, exist_ok=True)
    jpath = os.path.join(reports, "console_data.json")
    blob = json.dumps(data, separators=(",", ":"))
    with open(jpath, "w") as f:
        f.write(blob)

    core_path = os.path.join(HERE, "console_core.js")
    core = open(core_path).read() if os.path.exists(core_path) else ""

    made = []
    for tpl_name, out_name in [("backtest_template.html", "backtest.html"),
                               ("console_template.html", "console.html")]:
        tpl = os.path.join(HERE, tpl_name)
        if os.path.exists(tpl):
            with open(tpl) as f:
                t = f.read()
            t = t.replace("/*__CORE__*/", core)          # shared compute, injected once
            out = os.path.join(reports, out_name)
            with open(out, "w") as f:
                f.write(t.replace("/*__DATA__*/null", blob))
            made.append(out)

    print(f"console data: {jpath}  ({len(blob)/1024:.0f} KB, "
          f"{len(inst)} instruments x {len(data['dates'])} months)")
    for m in made:
        print(f"  rendered: {m}")


if __name__ == "__main__":
    main()
