"""
TSMOM engine — Moskowitz, Ooi, Pedersen (2012), "Time Series Momentum", JFE 104.

Implements:
  * Daily excess-return indexes per instrument (futures ~ excess by construction;
    ETF/index proxies get the T-bill rate subtracted).
  * Ex-ante EWMA volatility, Eq. (1):
        sigma_t^2 = 261 * sum_i (1-delta) * delta^i * (r_{t-1-i} - rbar_t)^2
    with center of mass delta/(1-delta) = 60 days  =>  delta = 60/61.
    Implemented with pandas ewm(com=60): running EWMA mean, then EWMA of squared
    deviations. Lagged one day everywhere it is used (no look-ahead).
  * Signals: sign of trailing k-month excess return, k in {3, 6, 12};
    12m is the headline (paper's TSMOM, k=12, h=1).
  * Sizing, Eq. (5): position = sign(r_{t-12,t}) * (vol_target / sigma_t),
    equal risk allocation 1/N_t across live instruments.
"""

from __future__ import annotations

import os
import numpy as np
import pandas as pd

# ----------------------------------------------------------------------------- params
TRADING_DAYS = 261          # annualization used in the paper
EWMA_COM = 60               # center of mass (days) => delta = 60/61
VOL_TARGET = 0.40           # per-instrument ex-ante vol target (paper: 40%)
LOOKBACKS = (3, 6, 12)      # months; 12m is the headline signal
MIN_MONTHS = 13             # history needed for a 12m signal
MIN_VOL_DAYS = 60           # min daily obs before we trust the vol estimate
STALE_DAYS = 7              # flag instrument if last price older than this (calendar days)
WEAK_Z = 0.5                # |trend strength| below this is close to a coin flip
CLIP_DAILY = 0.15           # cap |daily return|: roll-gap / bad-print guard
CLIP_DAILY_CRYPTO = 0.50    # crypto really does move this much; only clip true bad prints
MAX_UNIT_LEV = 5.0          # cap on 40%/sigma per instrument (paper is uncapped:
                            # 2Y notes at ~1% vol would demand 30x+ leverage)

HERE = os.path.dirname(os.path.abspath(__file__))

try:  # pandas >= 2.2 uses "ME" for month-end; older versions use "M"
    pd.tseries.frequencies.to_offset("ME")
    MONTH_END = "ME"
except ValueError:
    MONTH_END = "M"


# ----------------------------------------------------------------------------- universe
def load_instruments(path: str | None = None) -> pd.DataFrame:
    """Load the signal universe. Supports the current schema
    (name, asset_class, ticker, source_type, exec_ticker, notes) and the original one
    (name, asset_class, yahoo_futures, etf_proxy, preferred_source, notes)."""
    df = pd.read_csv(path or os.path.join(HERE, "instruments.csv"))
    if "source_type" not in df.columns:                      # legacy schema
        df["ticker"] = np.where(
            (df["preferred_source"] == "etf") | df["yahoo_futures"].isna(),
            df["etf_proxy"], df["yahoo_futures"])
        df["source_type"] = np.where(df["preferred_source"] == "futures",
                                     "futures", "etf")
    if "exec_ticker" not in df.columns:
        df["exec_ticker"] = df["ticker"]
    # Futures and rolled FX forwards are self-financing, so their price return already IS
    # an excess return. Cash instruments (ETFs) must have the risk-free rate subtracted.
    df["is_excess"] = df["source_type"].isin(["futures", "fx_spot"])
    return df.dropna(subset=["ticker"]).reset_index(drop=True)


# ----------------------------------------------------------------------------- data layer
def fetch_yahoo(tickers: list[str], start: str = "2005-01-01") -> pd.DataFrame:
    """Live mode: daily adjusted closes from Yahoo. Requires network access."""
    import yfinance as yf
    px = yf.download(tickers, start=start, progress=False, auto_adjust=True)["Close"]
    if isinstance(px, pd.Series):
        px = px.to_frame(tickers[0])
    return px.sort_index()


def load_csv_cache(cache_dir: str | None = None) -> pd.DataFrame:
    """CSV mode: one file per ticker in data_cache/, columns Date,Close (extra cols ok).

    File name = ticker with '=' -> '_' and '^' -> '' (e.g. CL=F -> CL_F.csv).
    Stooq exports (Date,Open,High,Low,Close,Volume) work as-is.
    """
    cache_dir = cache_dir or os.path.join(HERE, "data_cache")
    out = {}
    for fn in sorted(os.listdir(cache_dir)):
        if not fn.lower().endswith(".csv"):
            continue
        t = fn[:-4]
        if t.startswith("IDX_"):
            t = "^" + t[4:]
        t = t.replace("_F", "=F").replace("_X", "=X")
        s = pd.read_csv(os.path.join(cache_dir, fn))
        s.columns = [c.strip().title() for c in s.columns]
        s["Date"] = pd.to_datetime(s["Date"])
        out[t] = s.set_index("Date")["Close"].astype(float)
    if not out:
        raise FileNotFoundError(f"no CSV files in {cache_dir}")
    return pd.DataFrame(out).sort_index()


def despike(px: pd.DataFrame, cls: dict | None = None) -> pd.DataFrame:
    """Drop single-day bad prints before any return is computed.

    Yahoo's FX series carry occasional corrupt values — USD/CLP printed 5.00 between two
    663.7 quotes, USD/TWD printed 1.80 between two 30.1s. Clipping the resulting return
    caps the damage but still injects a fake round trip into the cumulative index and
    inflates the EWMA vol for months afterwards, so the price point itself is removed.

    A point is bad only if it is far from the CENTRED rolling median: a genuine jump that
    holds drags the median with it and survives; a spike that reverts does not.
    """
    out = px.copy()
    for c in out.columns:
        s = out[c]
        if s.notna().sum() < 20:
            continue
        med = s.rolling(5, center=True, min_periods=3).median()
        ratio = s / med
        crypto = (cls or {}).get(c) == "Crypto"
        hi, lo = (3.0, 1 / 3.0) if crypto else (1.6, 1 / 1.6)
        bad = (ratio > hi) | (ratio < lo)
        if bad.any():
            out.loc[bad.fillna(False), c] = np.nan
    return out


def excess_returns(px: pd.DataFrame, instruments: pd.DataFrame,
                   tbill_annual: pd.Series | float = 0.0) -> pd.DataFrame:
    """Daily excess returns. Futures: raw pct change. ETF/index: subtract daily T-bill.

    Cleaning: non-positive prices -> NaN (WTI Apr-2020 makes pct_change meaningless),
    and daily returns clipped — Yahoo's continuous futures splice front months without
    back-adjustment, so roll gaps show up as fake jumps (NG worst). The cap is
    class-aware: 15% is above any real daily move in traditional markets (2008 crude
    ~ -13%), but crypto genuinely trades +/-20-30% in a day, so clipping it there would
    delete real returns rather than artefacts.

    Calendar. Instruments are loaded into one DataFrame, so its index is the UNION of every
    market's trading days, and each instrument is NaN on days it did not trade. Naive
    `px.pct_change()` on that grid computes price[t] / price[t-1], and when t-1 is a NaN row
    the return is NaN — DISCARDED, not deferred. Every day some other market trades and this
    one does not, this one's next return vanishes from the cumulative index: 3.1% of all
    daily returns here, which read gold's twelve-month return as +20.4% when it was +23.9%.
    Returns are therefore computed between CONSECUTIVE VALID prices per instrument and
    mapped back to the grid. The grid is also restricted to weekdays, so that a 24/7 series
    (spot crypto) cannot introduce weekend rows that would delete every Monday for everyone
    else and hand the 24/7 series ~365 observations a year against everyone else's ~252.
    """
    cls = dict(zip(instruments["ticker"], instruments["asset_class"]))
    px = px.loc[px.index.dayofweek < 5]
    px = despike(px.where(px > 0), cls)
    r = pd.DataFrame(index=px.index, columns=px.columns, dtype=float)
    for c in px.columns:
        s = px[c].dropna()
        r[c] = s.pct_change().reindex(px.index)
    for c in r.columns:
        cap = CLIP_DAILY_CRYPTO if cls.get(c) == "Crypto" else CLIP_DAILY
        r[c] = r[c].clip(-cap, cap)
    is_excess = dict(zip(instruments["ticker"], instruments["is_excess"]))
    if np.isscalar(tbill_annual):
        rf_daily = float(tbill_annual) / TRADING_DAYS
        for c in r.columns:
            if not is_excess.get(c, True):
                r[c] = r[c] - rf_daily
    else:
        rf_daily = (tbill_annual.reindex(r.index).ffill() / TRADING_DAYS).fillna(0.0)
        for c in r.columns:
            if not is_excess.get(c, True):
                r[c] = r[c] - rf_daily
    return r


# ----------------------------------------------------------------------------- vol (Eq. 1)
def ewma_vol(daily_ret: pd.DataFrame, com: int = EWMA_COM,
             ann: int = TRADING_DAYS) -> pd.DataFrame:
    """Annualized ex-ante EWMA vol per Eq. (1). NOT lagged here — lag at point of use."""
    mu = daily_ret.ewm(com=com, adjust=False, min_periods=MIN_VOL_DAYS).mean()
    var = ((daily_ret - mu) ** 2).ewm(com=com, adjust=False,
                                      min_periods=MIN_VOL_DAYS).mean()
    return np.sqrt(ann * var)


# ----------------------------------------------------------------------------- signals & weights
def monthly_index(daily_ret: pd.DataFrame) -> pd.DataFrame:
    """Month-end cumulative excess-return index (log-safe compounding)."""
    idx = (1.0 + daily_ret.fillna(0.0).where(daily_ret.notna(), 0.0)).cumprod()
    idx = idx.where(daily_ret.notna().cummax())          # NaN before first obs
    return idx.resample(MONTH_END).last()


def momentum_signals(m_idx: pd.DataFrame,
                     lookbacks=LOOKBACKS) -> dict[int, pd.DataFrame]:
    """sign(trailing k-month excess return) at each month-end."""
    out = {}
    for k in lookbacks:
        ret_k = m_idx / m_idx.shift(k) - 1.0
        out[k] = np.sign(ret_k)
    return out


def tsmom_weights(sig12: pd.Series, sigma: pd.Series,
                  vol_target: float = VOL_TARGET) -> pd.DataFrame:
    """Eq. (5) sizing at one date: w_s = sign * vol_target / sigma_s, and /N portfolio."""
    live = sig12.dropna().index.intersection(sigma.dropna().index)
    w = sig12[live] * vol_target / sigma[live]
    port = w / len(live) if len(live) else w
    return pd.DataFrame({"unit_weight": w, "portfolio_weight": port})


# ----------------------------------------------------------------------------- backtest
def backtest(daily_ret: pd.DataFrame, lookbacks=LOOKBACKS,
             vol_target: float = VOL_TARGET, cap: float | None = MAX_UNIT_LEV) -> dict:
    """Monthly TSMOM(k, h=1) for each k. Signal at month t uses index through t;
    vol is the daily EWMA estimate at the LAST DAY BEFORE month t's end (lagged);
    return earned over t -> t+1. Matches the paper's timing.

    `cap` limits vol_target/sigma per instrument. Pass None for Eq. 5 exactly as written —
    the paper is UNCAPPED — or a number for the engine's default, which exists only because
    uncapped sizing demands 30x+ on 2-year notes.
    """
    m_idx = monthly_index(daily_ret)
    m_ret = m_idx.pct_change(fill_method=None)
    sigs = momentum_signals(m_idx, lookbacks)
    sig_d = ewma_vol(daily_ret).shift(1)                # sigma_{t-1}: yesterday's estimate
    sig_m = sig_d.resample(MONTH_END).last()            # available at month-end t

    results = {}
    for k, sg in sigs.items():
        lev = vol_target / sig_m
        if cap is not None:
            lev = lev.clip(upper=cap)
        instr_ret = sg.shift(1) * lev.shift(1) * m_ret  # decided at t, earned t->t+1
        live = instr_ret.notna().sum(axis=1)
        port = instr_ret.mean(axis=1).where(live >= 5)  # need a few live instruments
        port = port.dropna()
        ann_mean = port.mean() * 12
        ann_vol = port.std() * np.sqrt(12)
        results[k] = {
            "monthly_returns": port,
            "instrument_returns": instr_ret,
            "ann_return": ann_mean,
            "ann_vol": ann_vol,
            "sharpe": ann_mean / ann_vol if ann_vol > 0 else np.nan,
            "hit_rate": (port > 0).mean(),
            "n_months": len(port),
        }
    return results


# ----------------------------------------------------------------------------- current snapshot
def current_snapshot(px: pd.DataFrame, instruments: pd.DataFrame,
                     tbill_annual=0.0, vol_target: float = VOL_TARGET) -> pd.DataFrame:
    """Today's signal table: 3/6/12m signs, agreement, ex-ante vol, weights."""
    r = excess_returns(px, instruments, tbill_annual)
    m_idx = monthly_index(r)
    sigs = momentum_signals(m_idx)
    sig_d = ewma_vol(r).shift(1)

    last_m = m_idx.index[-1]
    sigma_now = sig_d.iloc[-1]

    rows = []
    for _, ins in instruments.iterrows():
        t = ins["ticker"]
        if t not in m_idx.columns:
            continue
        s3, s6, s12 = (sigs[k].loc[last_m, t] if t in sigs[k].columns else np.nan
                       for k in (3, 6, 12))
        vol = sigma_now.get(t, np.nan)
        last_px_date = px[t].dropna().index[-1] if t in px and px[t].notna().any() else None
        stale = (last_px_date is None or
                 (px.index[-1] - last_px_date).days > STALE_DAYS)
        r12 = (m_idx[t].iloc[-1] / m_idx[t].shift(12).iloc[-1] - 1.0
               if m_idx[t].notna().sum() > 12 else np.nan)
        w = (s12 * min(vol_target / vol, MAX_UNIT_LEV)
             if (not np.isnan(vol) and not np.isnan(s12) and vol > 0 and not stale)
             else np.nan)
        # Trend strength in standard deviations of the 12-month move itself. A raw return
        # threshold is dimensionally wrong: -1% on a 1.2%-vol note is most of a sigma, while
        # -1% on 42%-vol natural gas is nothing. Judging both by "3%" flags only low-vol markets.
        z12 = (r12 / (vol * np.sqrt(12 / 12))
               if (not np.isnan(vol) and vol > 0 and not np.isnan(r12)) else np.nan)
        rows.append({
            "name": ins["name"], "asset_class": ins["asset_class"], "ticker": t,
            "sig_3m": s3, "sig_6m": s6, "sig_12m": s12,
            "agreement": int(pd.Series([s3, s6]).eq(s12).sum()) if not np.isnan(s12) else 0,
            "ret_12m": r12, "strength_z": z12, "exante_vol": vol,
            "weak": bool(abs(z12) < WEAK_Z) if not np.isnan(z12) else False,
            "unit_weight": w, "stale": stale,
        })
    snap = pd.DataFrame(rows)
    n_live = snap["unit_weight"].notna().sum()
    snap["portfolio_weight"] = snap["unit_weight"] / n_live if n_live else np.nan
    return snap
