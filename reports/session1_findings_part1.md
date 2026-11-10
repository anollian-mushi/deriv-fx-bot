# Session 1 findings, part 1: products, real costs and data

Written 10 Nov 2026 from files already in the repository. Nothing new was
collected or downloaded, no Deriv call was made and nothing was traded.
Candle figures use only data dated before 31 Oct 2026, the start of the
untouched period. New numbers (the candle moves for all nine pairs) were
computed from the local files by `scripts/session1_findings.py` and saved in
`research/session1_findings.json`.

Pairs covered: the three majors (EUR/USD, GBP/USD, USD/JPY) and the six newer
pairs (AUD/USD, USD/CAD, USD/CHF, EUR/GBP, EUR/JPY, GBP/JPY).

## 1. What Deriv offers through the API

**Ordinary forex trading with a stop loss and a take profit IS available, as
Multipliers.** You pick a direction (up or down), a stake and a multiplier.
The trade then gains or loses like a normal forex position worth
stake x multiplier, until you close it or a stop loss, take profit or stop
out closes it. **There is no fixed payout**: a quote's `payout` field is 0,
and the result is simply the price move times the position size minus the
commission. So no "payout break-even" calculation applies, as it would to a
fixed-payout option. What matters is how far the price must move to cover the
commission (section 2).

| Item | All nine pairs (measured) | Source |
|---|---|---|
| Product | Multipliers, Up (`MULTUP`) and Down (`MULTDOWN`) | `docs/deriv_api_notes.md` section 5 |
| Multipliers on the demo and real accounts | 100, 200, 300, 500, 800. 50, 150 and 250 are refused | `reports/costs.md` section 1; the six newer pairs in the 2 Nov samples, `research/phase2/pairs2/` |
| Multipliers this project allows | x100 and x200 only (x100 for trades held overnight) | `CLAUDE.md` |
| Stake | 1 to 2,000 USD | `reports/costs.md` section 2; the same on the newer pairs |
| Take profit | 0.10 USD up to 50 x stake | `reports/costs.md` section 2 |
| Stop loss | from commission + 0.01 USD up to the stake. Use commission + 0.02, because Deriv rejects the exact minimum after rounding | `config/contract_specs.yaml` |
| Stop out | always on: the trade closes when the loss reaches the whole stake. You can never lose more than the stake | `reports/costs.md` section 2 |
| Duration | **no expiry.** A trade stays open until it is closed. Trades from 26 seconds to a full weekend were held without any limit appearing | `research/demo_cost_trades.csv`, `reports/weekend_test.md` |
| Trading hours | Monday to Friday 00:00-23:59 GMT, Friday until 20:55. **New trades are refused every weekday from 20:55 to 21:30 UTC**; open trades carry on | `docs/deriv_api_notes.md`, `reports/costs.md` section 9 |
| Deal cancellation | not available on forex Multipliers | `docs/deriv_api_notes.md` section 5 |
| Fees | one commission, paid when the trade opens (section 2). Minimum 0.02 USD. No spread, no fee to close, no overnight fee, no weekend fee | `reports/costs.md` sections 3 and 9, `reports/weekend_test.md` |

**Options-style contracts (fixed-payout Rise/Fall and similar):** our files
do not record them. Every quote and trade the project made was a Multiplier,
and the `contracts_for` checks only kept the Multiplier entries. Whether
Deriv offers fixed-payout options on these pairs through this API is
**not checked**. One read-only `contracts_for` request per pair would answer
it. The project chose Multipliers deliberately (`reports/product_choice.md`):
losses are capped at the stake and the API trades them directly.

## 2. Real costs

**How Multipliers charge.** There is **no spread**: trades open and close at
the mid price (entry measured 0.0-0.5 pip from the quote, `reports/costs.md`
section 7). The **only cost is one commission**, a share of
stake x multiplier, **paid once when the trade opens**. Closing is free. The
rate **changes by the hour** and rises around big news, so backtests must use
the rate for the hour each trade opens. That rate comes from
`research/phase2/cost_by_hour.json` (majors) and
`research/phase2/cost_by_hour_pairs2.json` (newer pairs), never from the
medians in `config/contract_specs.yaml` (`CLAUDE.md`).

Because there is no closing fee, **the round-trip cost is the opening
commission**. In pips it does not depend on the stake or the multiplier.

**Round-trip cost in the cheap window, 06:00-17:59 UTC.** "Base" is the
pair's lowest measured rate, which is what most hours in the window charge.
"Highest hour" is the dearest hour seen inside the window. The last column
adds the 0.5 pip entry slippage the backtester assumes on every trade.

| Pair | Base rate | Cost at base | Highest hour in the window | Including 0.5 pip slippage |
|---|---|---|---|---|
| EUR/USD | 0.0239% | 2.8 pips | 3.1 pips (06:00) | 3.3-3.6 pips |
| GBP/USD | 0.0203% | 2.7 pips | 3.1 pips (06:00) | 3.2-3.6 pips |
| USD/JPY | 0.0275% | 4.3 pips | 4.9 pips (17:00) | 4.8-5.4 pips |
| AUD/USD | 0.0400% | 2.8 pips | 2.8 pips | 3.3 pips |
| USD/CAD | 0.0212% | 3.0 pips | 3.2 pips | 3.5-3.7 pips |
| USD/CHF | 0.0360% | 3.0 pips | 3.5 pips | 3.5-4.0 pips |
| EUR/GBP | 0.0243% | 2.0 pips | 2.4 pips | 2.5-2.9 pips |
| EUR/JPY | 0.0250% | 4.4 pips | 4.5 pips | 4.9-5.0 pips |
| GBP/JPY | 0.0238% | 5.0 pips | 5.5 pips | 5.5-6.0 pips |

Pips are converted at each table's own reference price (`price_used` in the
table). Outside the window the commission is 2-12 times higher: 6-10 pips in
the evening and up to about 33 pips on EUR/USD just after the daily pause
(`reports/costs.md` section 3). The majors' table was re-checked after the US
clock change; the newer pairs' table comes from one day, Monday 2 Nov.

**Cost as a share of a typical candle.** Below, the cost at base is divided by
the average move of one candle, its high minus its low. Candles are built from
1m data on UTC boundaries, inside Deriv's trading hours, from data before
31 Oct 2026. Where the highest hour in the window costs noticeably more, its
share is shown in brackets.

Five years of Dukascopy 1m data (Nov 2021 to Oct 2026), the longer and
steadier measure:

| Pair | 15m candle: average move, cost share | 1h candle | 4h candle |
|---|---|---|---|
| EUR/USD | 6.8 pips, **41%** (46%) | 14.1 pips, **20%** (22%) | 28.4 pips, **10%** (11%) |
| GBP/USD | 8.7 pips, **31%** (36%) | 17.9 pips, **15%** (18%) | 36.1 pips, **8%** (9%) |
| USD/JPY | 11.0 pips, **39%** (44%) | 22.8 pips, **19%** (21%) | 46.7 pips, **9%** (10%) |
| AUD/USD | 6.0 pips, **47%** | 12.3 pips, **23%** | 24.8 pips, **11%** |
| USD/CAD | 7.1 pips, **42%** (45%) | 14.4 pips, **21%** (22%) | 28.8 pips, **10%** (11%) |
| USD/CHF | 6.0 pips, **49%** (58%) | 12.3 pips, **24%** (28%) | 24.8 pips, **12%** (14%) |
| EUR/GBP | 4.1 pips, **50%** (59%) | 8.2 pips, **25%** (29%) | 16.1 pips, **13%** (15%) |
| EUR/JPY | 11.9 pips, **37%** | 24.4 pips, **18%** | 49.2 pips, **9%** |
| GBP/JPY | 15.1 pips, **33%** (37%) | 30.6 pips, **16%** (18%) | 61.5 pips, **8%** (9%) |

Deriv's own 1m data, the feed the bot trades on. Majors: Oct 2025 to Oct 2026.
Newer pairs: Apr to Oct 2026, a calmer half year.

| Pair | 15m candle: average move, cost share | 1h candle | 4h candle |
|---|---|---|---|
| EUR/USD | 5.5 pips, **51%** (57%) | 11.3 pips, **25%** (28%) | 22.9 pips, **12%** (14%) |
| GBP/USD | 7.2 pips, **38%** (44%) | 14.9 pips, **18%** (21%) | 30.0 pips, **9%** (10%) |
| USD/JPY | 8.9 pips, **48%** (55%) | 18.6 pips, **23%** (26%) | 38.2 pips, **11%** (13%) |
| AUD/USD | 4.3 pips, **65%** | 8.9 pips, **32%** | 17.7 pips, **16%** |
| USD/CAD | 4.8 pips, **62%** (67%) | 10.0 pips, **30%** (32%) | 20.5 pips, **14%** (16%) |
| USD/CHF | 4.5 pips, **66%** (78%) | 9.5 pips, **31%** (37%) | 19.3 pips, **15%** (18%) |
| EUR/GBP | 2.4 pips, **85%** (100%) | 4.8 pips, **42%** (50%) | 9.8 pips, **21%** (25%) |
| EUR/JPY | 8.8 pips, **50%** | 18.8 pips, **24%** | 39.0 pips, **11%** |
| GBP/JPY | 11.2 pips, **45%** (49%) | 23.5 pips, **21%** (23%) | 48.1 pips, **10%** (11%) |

What this means in plain words:
- **15m is too expensive.** A 15-minute trade starts a third to two thirds of
  a typical candle behind, and on EUR/GBP almost a whole candle. This is why
  the project dropped 15m (`CLAUDE.md`).
- **1h is possible but tight.** The cost is a fifth to a quarter of a typical
  candle on most pairs over five years. In the recent half year it is about
  30% on most newer pairs, and 42-50% on EUR/GBP.
- **4h is the most forgiving.** The cost is about a tenth of a typical candle.
- **The cheapest pairs in practice** are GBP/USD and the yen crosses
  (GBP/JPY, EUR/JPY): they move most for what they cost. **EUR/GBP** has the
  lowest cost in pips but moves so little that it is the dearest relative to
  its moves.
- These averages cover all trading hours. Candles inside the 06:00-17:59
  window usually move more than night candles, so in the window the shares
  are somewhat lower than shown.
- Recent Deriv candles moved less than the five-year Dukascopy average: about
  17-20% less on the majors and 23-41% less on the newer pairs. Partly the markets were
  calmer, and partly the two periods differ. The same cost therefore weighs
  more today than the long average suggests.

## 3. Data available

All files are compressed daily CSV files, one per pair per day, with a
`_manifest.json` per folder that records the quality checks.

| Source | Pairs | Timeframes stored | Period (before 31 Oct 2026) | Where |
|---|---|---|---|---|
| Deriv (the bot's own feed) | EUR/USD, GBP/USD, USD/JPY | 1m, 15m, 1h | 29 Oct 2025 to 30 Oct 2026: 261 trading days, about one year | `data/<symbol>/<1m, 15m or 1h>/` |
| Deriv | the six newer pairs | 1m | 28 Apr to 30 Oct 2026: 134 trading days, half a year | `data/<symbol>/1m/` |
| Dukascopy (research only) | all nine pairs | 1m mid prices plus spread | about five years: majors 27 Oct 2021 to 27 Oct 2026, newer pairs 1 Nov 2021 to 30 Oct 2026, 1,295-1,305 trading days each | `data_external/dukascopy/<symbol>/1m/` |

- **Longer timeframes are built, not stored.** 4h and daily candles (and
  15m/1h where Deriv has none) are built from 1m data on UTC boundaries, as
  `CLAUDE.md` requires. Building 15m and 1h from Deriv's 1m matches Deriv's
  own candles 100% at 15m and 99.6% at 1h. The only differences are the
  Friday 20:00 hourly candle, by up to 0.9 pip (`reports/data_quality.md`).
- **Deriv keeps only about one rolling year.** The daily GitHub job saves
  every new day, so our copy keeps growing. Data from 31 Oct 2026 onward is
  the untouched period: only the incubator may read it.
- **Dukascopy is for training and validation only.** Final tests must use
  Deriv data (`CLAUDE.md`).
- **Size:** `data/` about 30 MB, `data_external/` about 204 MB. No file is
  near the 50 MB limit.

**Data quality** (`reports/data_quality.md` for the majors; the same checks
from the folder manifests for the newer pairs):

| Source | Bad candles | Duplicates | Gaps of 5+ minutes | Short gaps (1-4 minutes) |
|---|---|---|---|---|
| Deriv, majors (1m, 15m, 1h) | 0 | 0 | 2 per pair: the early closes on 24 and 31 Dec | 4 single minutes per pair in a year |
| Deriv, newer pairs (1m) | 0 | 0 | 0 | 1 minute per pair in half a year |
| Dukascopy, majors | 0 | 0 | 101-133 per pair in 5 years | 5,600-7,100 minutes per pair |
| Dukascopy, newer pairs | 0 | 0 | 141-367 per pair in 5 years | 3,900-11,700 minutes per pair |

- **Deriv's data is very complete.** Christmas and New Year's Day are
  recorded as closed days. Fridays have exactly the 1,255 minutes up to the
  20:55 close.
- **Dukascopy gaps are ordinary.** Holidays, plus short quiet spells around
  the 21:00-23:00 UTC rollover and early Asian hours. A normal day has about
  1,435 of 1,440 minutes. The yen crosses and USD/CHF have more long gaps,
  still at quiet times.
- **Dukascopy also quotes after Deriv's Friday 20:55 close.** Those minutes
  are kept in the files but dropped by the backtester and by this report.
- **Deriv and Dukascopy agree closely:** typically 0.05-0.1 pip apart on the
  same minute (majors, `reports/data_quality.md`). So five years of Dukascopy
  are a fair stand-in for Deriv when developing strategies. This comparison
  was not repeated for the newer pairs.

**Rebuild the numbers:** `python scripts/session1_findings.py` (about one
minute; local files only).
