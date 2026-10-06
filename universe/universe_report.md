# Universe validation — 2026-09-16

Screened **83** candidates for a **$10,000,000** fund. Largest single position ≈ $602,410 (5× cap ÷ 83 names), so a market needs ≥ **$6M** median daily dollar volume to keep that position under 10% of ADV.

**81 passed · 2 rejected · 3 flagged thin (expect slippage).**

> **How liquidity is judged.** ETFs are screened on measured median 60-day dollar volume. Futures are *not*: Yahoo's volume field for continuous contracts reports only the front-month quote and is often partial or missing, which produces nonsense (Cotton at $1M/day, Silver at $20M/day, Platinum blank). Futures instead use the curated `liquidity_tier` in `candidates.csv` — deep / moderate / thin — with order-of-magnitude floors. FX spot is OTC and screened on history only. Set `override` to `keep` or `drop` in `candidates.csv` to force any decision.

### Commodity — 27/28 passed

| Instrument | Ticker | Type | History | Liquidity | Basis | Verdict |
|---|---|---|---|---|---|---|
| WTI Crude | `CL=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Brent Crude | `BZ=F` | futures | 19.1y | $1,000M | tier: deep | ✓ |
| RBOB Gasoline | `RB=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Heating Oil | `HO=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Natural Gas | `UNG` | etf | 19.4y | $93M | measured | ✓ |
| Gold | `GC=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Silver | `SI=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Copper | `HG=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Platinum | `PL=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Palladium | `PA=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Corn | `ZC=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Wheat CBOT | `ZW=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Wheat KC | `KE=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Soybeans | `ZS=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Soybean Meal | `ZM=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Soybean Oil | `ZL=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Oats | `ZO=F` | futures | 21.7y | $20M | tier: thin | ✓ |
| Rough Rice | `ZR=F` | futures | 21.7y | $20M | tier: thin | ✓ |
| Coffee | `KC=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Cotton | `CT=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Sugar | `SB=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Cocoa | `CC=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Orange Juice | `OJ=F` | futures | 21.7y | $20M | tier: thin | ✓ |
| Live Cattle | `LE=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Feeder Cattle | `GF=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Lean Hogs | `HE=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Carbon Allowances | `KRBN` | etf | 6.1y | $0M | measured | ✗ ADV $0.4M < $6.0M needed |
| Uranium | `URA` | etf | 15.9y | $120M | measured | ✓ |

### Equity — 22/22 passed

| Instrument | Ticker | Type | History | Liquidity | Basis | Verdict |
|---|---|---|---|---|---|---|
| S&P 500 | `ES=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Nasdaq 100 | `NQ=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Dow | `YM=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Russell 2000 | `RTY=F` | futures | 9.2y | $1,000M | tier: deep | ✓ |
| Nikkei 225 | `NKD=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Euro Stoxx 50 | `FEZ` | etf | 21.7y | $49M | measured | ✓ |
| Australia | `EWA` | etf | 21.7y | $59M | measured | ✓ |
| Canada | `EWC` | etf | 21.7y | $81M | measured | ✓ |
| Hong Kong | `EWH` | etf | 21.7y | $56M | measured | ✓ |
| Singapore | `EWS` | etf | 21.7y | $29M | measured | ✓ |
| Korea | `EWY` | etf | 21.7y | $3,237M | measured | ✓ |
| Taiwan | `EWT` | etf | 21.7y | $496M | measured | ✓ |
| India | `INDA` | etf | 14.6y | $236M | measured | ✓ |
| China A-Shares | `ASHR` | etf | 12.9y | $122M | measured | ✓ |
| China Large Cap | `FXI` | etf | 21.7y | $682M | measured | ✓ |
| Brazil | `EWZ` | etf | 21.7y | $733M | measured | ✓ |
| Mexico | `EWW` | etf | 21.7y | $76M | measured | ✓ |
| South Africa | `EZA` | etf | 21.7y | $8M | measured | ✓ thin |
| Emerging Broad | `EEM` | etf | 21.7y | $1,365M | measured | ✓ |
| UK | `EWU` | etf | 21.7y | $37M | measured | ✓ |
| Switzerland | `EWL` | etf | 21.7y | $19M | measured | ✓ |
| Sweden | `EWD` | etf | 21.7y | $4M | measured | ✓ thin |

### Bond — 10/11 passed

| Instrument | Ticker | Type | History | Liquidity | Basis | Verdict |
|---|---|---|---|---|---|---|
| US 2Y Note | `ZT=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| US 5Y Note | `ZF=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| US 10Y Note | `ZN=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| US 30Y Bond | `ZB=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| Intl Treasuries | `IGOV` | etf | 17.6y | $5M | measured | ✗ ADV $5.3M < $6.0M needed |
| Intl Treasuries Broad | `BWX` | etf | 18.9y | $8M | measured | ✓ thin |
| US TIPS | `TIP` | etf | 21.7y | $179M | measured | ✓ |
| EM Sovereign USD | `EMB` | etf | 18.7y | $521M | measured | ✓ |
| EM Local Currency | `EMLC` | etf | 16.1y | $42M | measured | ✓ |
| US HY Credit | `HYG` | etf | 19.4y | $2,320M | measured | ✓ |
| US IG Credit | `LQD` | etf | 21.7y | $2,915M | measured | ✓ |

### FX — 20/20 passed

| Instrument | Ticker | Type | History | Liquidity | Basis | Verdict |
|---|---|---|---|---|---|---|
| EUR/USD | `6E=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| JPY/USD | `6J=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| GBP/USD | `6B=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| AUD/USD | `6A=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| CAD/USD | `6C=F` | futures | 21.7y | $1,000M | tier: deep | ✓ |
| CHF/USD | `6S=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| NZD/USD | `6N=F` | futures | 21.7y | $100M | tier: moderate | ✓ |
| Dollar Index | `UUP` | etf | 19.5y | $46M | measured | ✓ |
| USD/MXN | `USDMXN=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/BRL | `USDBRL=X` | fx_spot | 20.5y | $nanM | — | ✓ |
| USD/ZAR | `USDZAR=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/TRY | `USDTRY=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/INR | `USDINR=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/KRW | `USDKRW=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/TWD | `USDTWD=X` | fx_spot | 20.3y | $nanM | — | ✓ |
| USD/PLN | `USDPLN=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/CNY | `USDCNY=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/SGD | `USDSGD=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/ILS | `USDILS=X` | fx_spot | 21.7y | $nanM | — | ✓ |
| USD/CLP | `USDCLP=X` | fx_spot | 21.7y | $nanM | — | ✓ |

_FX spot pairs carry no exchange volume on Yahoo; OTC depth is assumed and they are screened on history only. Their returns exclude the interest differential, which is material for high-carry pairs (TRY, BRL, ZAR)._