"""Synthetic-data validation of the TSMOM math. Run: python tests/test_engine.py"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tsmom  # noqa: E402

rng = np.random.default_rng(7)
DAYS = pd.bdate_range("2015-01-01", "2025-12-31")


def make_series(mu_ann, vol_ann):
    return pd.Series(rng.normal(mu_ann / 261, vol_ann / np.sqrt(261), len(DAYS)),
                     index=DAYS)


def test_ewma_vol_recovers_true_vol():
    r = pd.DataFrame({"A": make_series(0.0, 0.20), "B": make_series(0.0, 0.50)})
    v = tsmom.ewma_vol(r)
    tailA, tailB = v["A"].iloc[-500:].mean(), v["B"].iloc[-500:].mean()
    assert abs(tailA - 0.20) < 0.03, tailA
    assert abs(tailB - 0.50) < 0.06, tailB
    print(f"  ewma vol: A={tailA:.3f} (true .20)  B={tailB:.3f} (true .50)  OK")


def test_ewma_delta_and_com():
    # weights (1-d)d^i with com=60 -> d = 60/61; center of mass must be 60
    d = 60 / 61
    i = np.arange(20000)
    w = (1 - d) * d ** i
    assert abs(w.sum() - 1) < 1e-9
    assert abs((i * w).sum() - 60) < 1e-6
    print(f"  delta={d:.5f}, weight COM={(i*w).sum():.2f} days  OK")


def test_signal_signs():
    up = make_series(0.30, 0.10)   # strong uptrend
    dn = make_series(-0.30, 0.10)  # strong downtrend
    r = pd.DataFrame({"UP": up, "DN": dn})
    m = tsmom.monthly_index(r)
    sigs = tsmom.momentum_signals(m)
    for k in (3, 6, 12):
        assert sigs[k]["UP"].iloc[-1] == 1.0, (k, "UP")
        assert sigs[k]["DN"].iloc[-1] == -1.0, (k, "DN")
    print("  trending series produce correct 3/6/12m signs  OK")


def test_no_lookahead():
    r = pd.DataFrame({"A": make_series(0.05, 0.25)})
    v_full = tsmom.ewma_vol(r).shift(1)
    v_trunc = tsmom.ewma_vol(r.iloc[:-100]).shift(1)
    # estimates on the shared dates must be identical: future data can't change the past
    shared = v_trunc.index
    pd.testing.assert_frame_equal(v_full.loc[shared], v_trunc)
    print("  vol estimate unchanged by future data (no look-ahead)  OK")


def test_weights_scale_inversely_with_vol():
    r = pd.DataFrame({"LOWV": make_series(0.20, 0.10), "HIV": make_series(0.20, 0.40)})
    ins = pd.DataFrame({"name": ["LOWV", "HIV"], "asset_class": ["X", "X"],
                        "ticker": ["LOWV", "HIV"], "is_excess": [True, True]})
    px = (1 + r).cumprod() * 100
    snap = tsmom.current_snapshot(px, ins).set_index("ticker")
    ratio = abs(snap.loc["LOWV", "unit_weight"] / snap.loc["HIV", "unit_weight"])
    assert 2.5 < ratio < 6.0, ratio  # ~4x for 4x vol difference
    both_live = snap["portfolio_weight"].notna().sum()
    assert both_live == 2
    assert abs(snap["unit_weight"] / 2 - snap["portfolio_weight"]).max() < 1e-12
    print(f"  low-vol weight / high-vol weight = {ratio:.1f} (expect ~4)  OK")


def test_backtest_captures_trend():
    # a persistent trender should earn positive TSMOM returns with Sharpe >> 0
    cols = {f"T{j}": make_series(0.15 * (1 if j % 2 == 0 else -1), 0.20)
            for j in range(10)}
    r = pd.DataFrame(cols)
    bt = tsmom.backtest(r)
    s = bt[12]
    # ~0.4 per-instrument Sharpe expected; portfolio benefits from averaging but
    # 132 monthly obs => Sharpe SE ~0.3, so require clearly-positive rather than large
    assert s["sharpe"] > 0.4, s["sharpe"]
    assert 0.05 < s["ann_vol"] < 0.60
    print(f"  backtest on trending universe: Sharpe {s['sharpe']:.2f}, "
          f"vol {s['ann_vol']:.1%}  OK")


if __name__ == "__main__":
    for fn in [test_ewma_delta_and_com, test_ewma_vol_recovers_true_vol,
               test_signal_signs, test_no_lookahead,
               test_weights_scale_inversely_with_vol, test_backtest_captures_trend]:
        print(fn.__name__)
        fn()
    print("\nall tests passed")
