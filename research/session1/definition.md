# Session 1: time-of-day test. The definition, fixed before the run

Written and committed on 10 Nov 2026, **before** any number was computed. The script
`scripts/session1_time_of_day.py` implements exactly this. The owner asked for one pre-set
definition and one run. Any change after the run counts as a second attempt and is reported as
such.

## Data

- **Pairs:** EUR/USD, GBP/USD, USD/JPY.
- **Source:** Dukascopy 1m mid prices (`data_external/dukascopy/<pair>/1m/`), files dated
  2021-10-27 to 2026-10-27, the last Dukascopy day before the cutoff. **Nothing dated
  2026-10-31 or later is read.** The script refuses any file dated on or after the cutoff.
- **Minutes kept:** only minutes when Deriv's market is open (`fxbot.sessions.market_open`).
  That means weekdays only, Friday until 20:55 UTC, and no Christmas or New Year's Day. A bot
  on Deriv could not trade the other minutes.
- **1-hour candles, on UTC hour boundaries.**
  - open = the first 1m open in the hour;
  - close = the last 1m close in the hour;
  - high and low = the extremes of the hour's 1m candles.
  - A candle counts only if it has **at least 30** 1m candles.

## Measures (step 1)

For every pair and every UTC hour (0-23), over all days:

- **return** = close − open of the 1h candle, in pips (0.0001; 0.01 for USD/JPY). Positive means
  the pair rose. Reported: the mean, the standard deviation, the count, and the t-value (mean
  divided by its standard error).
- **range** = high − low, in pips. Reported: the mean.

## Sessions and the Ranaldo test (step 2)

Fixed UTC hours, no summer-time shifts:

| Session | UTC hours |
|---|---|
| Asian | 00:00-06:59 |
| London | 07:00-11:59 |
| Overlap (London + New York) | 12:00-15:59 |
| New York | 16:00-20:59 |
| Late (rollover; not a named session, reported for completeness) | 21:00-23:59 |

- **Session return** for one day = the sum of that day's 1h returns in the session's hours.
  It counts only if the session has at least half its hours on that day. Reported: mean,
  t-value and count per pair and session.
- **Ranaldo (2009):** a currency tends to weaken during its own working hours and strengthen
  outside them. The predictions are fixed here before the run:

  | Pair | Block | Whose home hours | Predicted sign of the pair's move |
  |---|---|---|---|
  | EUR/USD | London 07-11 | EUR | negative (EUR weakens) |
  | EUR/USD | New York 16-20 | USD | positive (USD weakens) |
  | GBP/USD | London 07-11 | GBP | negative |
  | GBP/USD | New York 16-20 | USD | positive |
  | USD/JPY | Asian 00-06 | JPY | positive (JPY weakens) |
  | USD/JPY | New York 16-20 | USD | negative (USD weakens) |

  The overlap (both home markets open) carries no prediction. For each of the 6, the report
  shows: whether the sign matches, the t-value, both halves, and the result after cost.

## Real cost (step 3)

- The **measured commission for the opening hour**, from `research/phase2/cost_by_hour.json`
  (`max_rate_pct` for that UTC hour and pair).
- In pips, per candle: **rate × the candle's open price / pip**. One trade means one commission.
  An hourly trade pays the rate of its own hour. A session trade pays the rate of the session's
  first hour on that day.
- That is the owner's cost rule for this test. No spread or slippage is added; the commission
  is Deriv's cost.
- **After-cost edge** of a pattern = (mean return in the pattern's direction) − (mean cost).
- **Hours outside the CLAUDE.md entry window (06:00-17:59 UTC)** are still measured, but are
  marked "not tradable under the project rules".

## Two halves and the pass rule (step 4)

- **Older half:** 2021-10-27 to 2024-04-26. **Newer half:** 2024-04-27 to 2026-10-27. The split
  is at the calendar midpoint.
- For each hour × pair combination (72 in all), the direction s is the sign of its
  full-period mean. Its score is

  **S = min(s × mean(older half) − cost(older half), s × mean(newer half) − cost(newer half))**

- A pattern **passes** only if S > 0. That means the same sign in both halves and positive
  after cost in both halves.
- The same rule is applied to the 15 session × pair combinations and to the 6 Ranaldo
  predictions. The Ranaldo predictions use their predicted direction instead of s.
- **Tests counted:** 72 hours + 15 sessions + 6 Ranaldo predictions = **93**.

## Luck (step 4)

- **200 shuffled versions of the same data.** For every pair and every day, the day's 1h
  returns and their costs are shuffled among that day's hours (seed 20261110 + shuffle number).
- Each day keeps its total move, its candles and the long-run trend. Only *which hour* a move
  happened in is randomised, and the cost stays with the hour, as in real trading.
- In each shuffle, the best S over the 72 hour × pair combinations is recorded, together with
  how many combinations pass. The report compares the real best S, and the real number of
  passes, with those 200 values: their median and 95th percentile, and the share of shuffles
  that do at least as well.
- Also reported, for information only: the same comparison **before cost**
  (S_gross = min over the halves of s × mean). This shows whether there is time-of-day
  structure at all, apart from cost.

## No trades

This is a measurement only. No engine run, no orders, no demo, no registration.
