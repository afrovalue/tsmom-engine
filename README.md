# TSMOM Engine

Time series momentum signal engine per Moskowitz, Ooi & Pedersen (2012), *Time Series Momentum*, JFE 104 ("MOP" — the paper is Moskowitz, Ooi & Pedersen (2012), Time Series Momentum, Journal of Financial Economics.`).

## Universe

`universe/candidates.csv` is the full candidate list — every sleeve in AQR's *Trends Everywhere*
table that a fund of this size can actually reach, via listed futures, US-listed ETFs, or FX
forwards. `universe/validate_universe.py` screens them and regenerates `instruments.csv` and
`implementation/contract_specs.csv`:

```bash
python universe/validate_universe.py --nav 10000000   # then: python run.py --mode yahoo
```

The screen rejects anything with too little history, a stale price, or too little daily volume
to hold the engine's largest position in under 10% of ADV (a monthly-rebalanced book can work
an entry over a day or two; a daily trader would want a tighter bar). `universe/universe_report.md`
lists every pass and rejection with its reason, and flags names that pass but are still thin
enough to cost slippage.

**Liquidity is judged two different ways, on purpose.** ETFs use measured median 60-day dollar
volume from Yahoo, which is reliable. Futures do **not**: Yahoo's volume field for continuous
contracts (`XX=F`) reports only the front-month quote and is often partial or missing, which
yields nonsense — Cotton at $1M/day, Silver at $20M/day, Platinum blank. Futures instead use the
curated `liquidity_tier` column in `candidates.csv` (deep / moderate / thin) with
order-of-magnitude floors. FX spot is OTC and screened on history alone. The `override` column
takes `keep` or `drop` to force any decision, so a judgment call is recorded in the file rather
than made by quietly retuning a threshold.

Re-run the screen **quarterly, and whenever NAV changes materially** — the liquidity bar scales
with fund size, so a bigger book legitimately drops the thinner names.

**Deliberately excluded** (in AQR's table, not reachable here): OTC interest-rate swaps across
17 countries, CDX/iTraxx credit indices, EU emissions allowances, physical-delivery exotics
(South African maize, palm oil, iron ore, UK natural gas), and the long/short equity factors
(SMB, HML, UMD, BAB…). These need ISDA documentation, institutional prime brokerage, or
local-exchange membership. Where a listed proxy exists it is used instead — carbon via KRBN,
EM credit via EMB, US HY/IG via HYG/LQD, country equities via their MSCI ETFs.

**Data cleaning.** Prices are despiked before any return is computed: a point far from its
centred 5-day rolling median is dropped outright, because Yahoo's FX series carry corrupt
single-day values (USD/CLP printed 5.00 between two 663.7 quotes; USD/TWD printed 1.80 between
two 30.1s). Clipping such a return would still inject a fake round trip into the cumulative index
and inflate the EWMA vol for months. A genuine jump that *holds* drags the median with it and
survives — WTI's +37.7% rebound on 2020-04-22 is kept. Remaining daily returns are then capped at
±15%, or ±50% for crypto, which really does move that much.

**Known compromises**, all flagged in the specs:
- Country equity ETFs are unhedged USD, so they carry currency exposure the local index doesn't.
- FX spot pairs price the trend but exclude the interest differential — returns understate carry,
  materially for TRY, BRL and ZAR.
- Crypto is CME futures (BTC=F from Dec-2017, ETH=F from Feb-2021), so both are self-financing and
  weekday-aligned with the rest of the book. ETH has the shortest history in the universe.
- European equity is Euro Stoxx 50 (`FEZ`) plus UK (`EWU`), Switzerland (`EWL`) and Sweden
  (`EWD`). `VGK` and the remaining single-country ETFs stay out to keep the equity sleeve from
  dominating portfolio risk. Sweden sits below the ADV screen and is held by an explicit
  `override=keep`, which is recorded in `candidates.csv` rather than hidden in a threshold.

## What it does

1. Builds daily **excess-return indexes** for every instrument in the universe (commodities,
   equity indices, bonds and credit, FX). Futures and rolled FX forwards are self-financing so
   their price return is already an excess return; ETFs get the T-bill rate subtracted.
2. **Ex-ante EWMA volatility** (paper Eq. 1): annualized, δ = 60/61 (60-day center of mass), ×261, computed daily and **lagged one day** at every point of use — no look-ahead.
3. **Signals**: sign of trailing 3, 6, 12-month excess return at month-end. **12-month is the headline** (the paper's canonical TSMOM, k=12, h=1). 3m/6m are shown as agreement/confirmation.
4. **Weights** (Eq. 5): `w = sign(r_12m) × vol_target / σ` per instrument (default 40%, the paper's number), split equally across live instruments. Gross/net exposure and sleeve tilts are summarized in the report.
5. **Backtest fingerprint**: TSMOM(3/6/12, h=1) Sharpe, vol, hit-rate — sanity-checks each run against the paper's known behavior.

## Files

- `instruments.csv` — the universe: name, class, Yahoo futures ticker, ETF proxy. Edit freely; the engine picks up changes on the next run.
- `tsmom.py` — core math (data prep, EWMA vol, signals, sizing, backtest).
- `report.py` — renders the markdown report + signals CSV into `reports/`.
- `run.py` — orchestrator.
- `tests/audit.py` — **adversarial audit against the real cache** (26 checks): look-ahead in the
  vol estimate, in the signal, and in the whole backtest (including a randomised-future control);
  bad-print removal; roll-splice artefacts; staleness and history coverage; weight/cap integrity;
  return-index sanity; and coherence between `instruments.csv`, `contract_specs.csv` and the cache.
  Run it after any data or config change — it exits non-zero on failure.
- `tests/test_engine.py` — synthetic-data validation (vol estimator recovers true vol, δ/center-of-mass check, sign correctness, no-look-ahead proof, inverse-vol sizing, trend capture).

## Running

```bash
pip install pandas numpy yfinance
python run.py --mode yahoo             # live: downloads from Yahoo, caches to data_cache/
python run.py --mode csv               # offline: reads data_cache/*.csv
python run.py --mode yahoo --vol-target 0.20   # gentler sizing
python tests/test_engine.py            # validate the math on synthetic series
python tests/audit.py                  # audit the real cache (look-ahead, splices, config)
```

CSV mode expects one file per ticker in `data_cache/`, columns `Date,Close` (extra columns fine; Stooq exports work as-is). Naming: `=` → `_`, leading `^` → `IDX_` (e.g. `CL=F` → `CL_F.csv`, `^GDAXI` → `IDX_GDAXI.csv`). A `--mode yahoo` run refreshes this cache automatically, so the engine keeps working offline afterwards.

## The two interactive tools

Both are published pages that **recompute themselves live**. Rather than baking in one vol
target and leverage cap, `analytics/build_console.py` ships the raw monthly series — the
cumulative excess-return index and the EWMA vol for every instrument, plus the correlation
matrix — and the pages rebuild signals, weights, the backtest and the risk decomposition in the
browser for whatever parameters you choose. The shared maths lives once in
`analytics/console_core.js` and is injected into both pages at build time, so they cannot drift
apart.

### TSMOM Engine — signals, risk and orders on one row
**https://claude.ai/code/artifact/95623fc9-2425-44ca-ac03-dfb5e0bf0852**
(`TSMOM Engine.webloc`; offline copy `reports/console.html`)

Signal horizon, vol target, leverage cap, deadband and NAV drive everything at once: change any
of them and the positions, the ex-ante risk and the executable orders all move together. Shows
`σₚ = √(w'Σw)` against its perfect-correlation ceiling `Σ|wᵢ|σᵢ`, the diversification ratio, risk
share by sleeve, a largest-risk-contributors panel, and the order for each market (futures contracts, ETF shares
or FX forward notional). Trailing returns within ±3% of zero are flagged ⚠ — in the signal
columns *and* in the order rows, so you can see when you are about to trade on a coin flip.

### Backtest Lab — the same parameters, run through history
**https://claude.ai/code/artifact/de34c7ab-986a-4d1d-866f-c6a97d5a527a**
(`TSMOM Backtest Lab.webloc`; offline copy `reports/backtest.html`)

The full backtest rebuilt on every control change (~60ms), with each statistic shown against the
paper's own defaults so a change reads as a delta rather than a bare number. Includes a sweep of
Sharpe across leverage caps at the current vol target, which is the quickest way to see whether a
constraint helps or hurts.

**Two reference points, not one.** MOP Eq. 5 is **uncapped** — the "Paper (uncapped)" preset is
the paper as written, and every "vs paper" delta measures against it. The "Engine default (5×)"
preset is what `run.py` and the reports use, because uncapped sizing demands 30×+ on 2Y notes.
Which is better is an empirical question the Lab answers directly.

**The deadband is not in the paper.** MOP is pure sign — any positive trailing return is a full
long. The deadband control makes weak trends go flat instead, which is a real strategy change;
it defaults to off so the base case stays faithful to Eq. 5.

**A note on what the vol target actually does.** Because
`w = vol_target × min(1/σ, cap/vol_target) / N`, the vol target is a linear scaler on every
position. On its own it moves portfolio volatility, not Sharpe — it changes risk-adjusted
performance only through how often the cap binds. The cap and the target therefore have to be
read together, which is why both are on screen at once.

## Implementation (weights → dollars & contracts)

`implementation/implement.py` converts the latest report's portfolio weights into dollar
targets and executable orders for an adjustable portfolio size:

```bash
python implementation/implement.py --nav 1000000          # $1M portfolio
python implementation/implement.py --nav 250000 --micros  # micro contracts where listed
python implementation/implement.py --nav 2000000 --scale 0.5  # halve all weights
```

It reads `implementation/contract_specs.csv` (multipliers and quote conventions per
contract — edit if you trade different instruments), prices from `data_cache/`, and writes
`positions_<date>.csv` plus a readable `implementation_<date>.md` showing target vs filled
dollars per instrument, futures contract counts, ETF share counts, and the rounding gaps.
It flags positions that round to zero contracts (small NAVs can't fill the paper's granular
weights — use `--micros`, more NAV, or accept omissions) and reports achieved net/gross vs
target so you can see what contract lumpiness does to the book before you trade it.

## Reading the report

Per instrument: 3m / 6m / **12m** direction, whether the short lookbacks agree with the 12m headline (2/2 = full agreement, 0/2 = the trend may be turning), trailing 12m return (small magnitudes = weak/borderline signals), ex-ante vol, and the vol-scaled weight. Instruments flagged `⚠stale` (price > 7 days old) are excluded from weights.

## Caveats

- Yahoo continuous futures use crude roll adjustment — long-lookback returns are slightly distorted for markets in steep contango/backwardation (natural gas especially). Fine for signal direction; upgrade to a proper back-adjusted feed (Norgate/CSI/Bloomberg) if precision starts to matter.
- The 40% per-instrument vol target is the paper's convention and implies real leverage (the paper notes ~5–20% margin capital). Scale `--vol-target` to your actual risk budget.
- Per-instrument weights are capped at 5x (`MAX_UNIT_LEV`) — uncapped Eq. 5 demands 30x+ on low-vol instruments like 2Y notes.
- Backtest fingerprint, 85 instruments, Feb 2006 → Aug 2026 (gross of costs):

  | Universe | 3m | 6m | 12m |
  |---|---|---|---|
  | All 85 | 0.34 | 0.41 | **0.26** |
  | Excluding the 12 EM FX spot pairs | 0.30 | 0.36 | **0.19** |
  | The original 43-name book | 0.25 | 0.23 | **0.15** |

  Read the middle row as the conservative number: EM FX spot returns exclude the interest
  differential, so the +0.07 of 12m Sharpe those 12 pairs add is partly an artefact of missing
  carry, not skill. The genuine diversification gain from expanding the universe is
  0.15 → 0.19. The paper's 1985–2009 Sharpe (~1 gross) reflects both cleaner data and a far
  friendlier era for trend — do not expect to reproduce it here.
- Rebalancing at $10M fills cleanly (5 zero-fills, 2.71× gross vs 2.78× target). At $1M the
  same universe leaves 28 zero-fills and tracks far worse — check the blotter before assuming
  a smaller book can run all 85 names.
- Signals, not investment advice.

## Returns are computed between consecutive valid prices

Instruments share one DataFrame, so its index is the union of every market's trading days and
each instrument is NaN on days it did not trade. A naive `pct_change()` on that grid returns
NaN wherever the previous row is a day this instrument was closed — and that return is
**discarded, not deferred**. It was silently deleting 3.1% of all daily returns here, which
read gold's twelve-month return as +20.4% when it was +23.9%, and it would have deleted every
Monday for every instrument the moment a 24/7 series (spot crypto) entered the universe.

`excess_returns` therefore differences each instrument on its own valid observations and maps
the result back to the grid, and restricts the grid to weekdays so no 24/7 series can reopen
the hole. Two audit checks fail loudly if either guarantee is ever lost.

## Rebuilding the deck

`analytics/build_deck_data.py` derives every figure in `TSMOM_Strategy.pptx` from this engine,
and `analytics/build_deck.js` renders the slides from it (needs `pptxgenjs`), so the deck and
the engine cannot drift:

```bash
python3 analytics/build_deck_data.py --engine . --out reports/deck_data.json
node analytics/build_deck.js          # run it beside a copy of deck_data.json
```
