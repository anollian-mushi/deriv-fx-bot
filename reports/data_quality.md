# Data quality report: historical candles

Phase 1, written 2026-10-28. Numbers come from `scripts/data_quality.py`,
which reads the `_manifest.json` file in every data folder. Re-run it after
new data arrives.

## The short version

- We have **two sources**, kept in separate folders and labelled in every
  file (`source` column):
  - **Deriv**: the price feed the bot will actually trade on. Deriv only
    keeps about **one year** of history, so that is all there is:
    2025-10-29 to 2026-10-27, at 1m, 15m and 1h.
  - **Dukascopy**: a free outside source, used **only for training and
    validation**. **Five years** of 1m mid prices plus the spread:
    2021-10-27 to 2026-10-27.
- Both are **clean**. No candle failed the price checks, and there are no
  duplicates. Every gap we found has an ordinary explanation: holidays, or
  the quiet hour around 22:00 UTC.
- **Deriv's prices match Dukascopy's mid price very closely**: typically
  0.05 to 0.1 pip apart. That is good news. It means five years of
  Dukascopy history is a fair stand-in for Deriv's feed when developing
  strategies.
- The final holdout test must still use the most recent Deriv data (see the
  research rules in CLAUDE.md).

## What was checked

For every saved day:

| Check | What it means |
|---|---|
| UTC timestamps | each candle's time is its start, in UTC, on an exact minute / 15-minute / hour boundary |
| Prices make sense | high ≥ open and close ≥ low, and no zero or negative prices |
| No duplicates | each candle time appears once |
| Gaps | missing candles inside trading hours (Mon–Fri 00:00–24:00 GMT, Friday until 20:55) |
| Outside hours | candles when Deriv is closed (weekend, Friday after 20:55) |

Rules for what counts as a gap:
- **Not gaps:** weekends, the Friday 20:55 early close, and whole closed
  days (holidays). Holidays are listed as "closed days".
- **Normal:** in 1m data, runs of 1 to 4 missing minutes. A quiet minute
  with no price change is normal, so these are only counted.
- **Gaps:** in 1m data, 5 or more missing minutes in a row. In 15m and 1h
  data, any missing candle.

## Deriv (`data/<symbol>/<1m|15m|1h>/`)

| Symbol | Granularity | First day | Last day | Days | Closed days | Gaps | Short 1m blips | Bad candles |
|---|---|---|---|---|---|---|---|---|
| frxEURUSD | 1m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | 4 | 0 |
| frxEURUSD | 15m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |
| frxEURUSD | 1h | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |
| frxGBPUSD | 1m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | 4 | 0 |
| frxGBPUSD | 15m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |
| frxGBPUSD | 1h | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |
| frxUSDJPY | 1m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | 4 | 0 |
| frxUSDJPY | 15m | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |
| frxUSDJPY | 1h | 2025-10-29 | 2026-10-27 | 258 | 25 Dec, 1 Jan | 2 | - | 0 |

What this means:
- **How far back:** history starts on 2025-10-29 for every pair and
  granularity. At 15m and 1h, only half of 2025-10-28 was available, so that
  day was left out. Deriv
  keeps a rolling year: each day the oldest day disappears. That is why the
  collector runs every weekday and keeps what it has already saved.
- **The only gaps** are Christmas Eve (2025-12-24) and New Year's Eve
  (2025-12-31). On both days the market closed early, at 22:00 GMT.
  These are holiday hours, not missing data.
- **Almost no missing minutes:** apart from those two evenings, every
  trading minute of the year is present except 4 single minutes per pair.
  Deriv's feed is very complete.
- **Fridays** have 1,255 one-minute candles (00:00 to 20:54), exactly as
  the 20:55 close predicts.
- **Nothing was thrown away.** Because the collector only asks for whole
  candle periods, Deriv never sent the partial candles found in Phase 0.

### 15m and 1h built from 1m vs Deriv's own

We built 15m and 1h candles from Deriv's 1m candles and compared them with
the 15m and 1h candles Deriv supplies:

| Symbol | Built | Candles compared | Exactly equal | Largest difference |
|---|---|---|---|---|
| frxEURUSD | 15m | 24,130 | 100% | none |
| frxEURUSD | 1h | 6,034 | 99.57% | 0.8 pip (close) |
| frxGBPUSD | 15m | 24,130 | 100% | none |
| frxGBPUSD | 1h | 6,034 | 99.57% | 0.9 pip (close) |
| frxUSDJPY | 15m | 24,130 | 100% | none |
| frxUSDJPY | 1h | 6,034 | 99.55% | 0.7 pip (close) |

**Every difference is the Friday 20:00 hourly candle**. Mostly its closing
price differs, and occasionally its high or low. Deriv's hourly candle
includes one last price at the 20:55 close that is not inside any 1-minute
candle. It is harmless: up to 0.9 pip, once a week, at a time the bot will
not be trading anyway. **Conclusion:** 15m and 1h can be built from 1m
safely, so later phases can test other timeframes too (e.g. 30m) from the
same 1m data.

## Dukascopy (`data_external/dukascopy/<symbol>/1m/`)

Research only: training and validation, never the final holdout.

| Symbol | First day | Last day | Days | Gaps (5+ min) | Short blips (minutes) | Candles after Friday 20:55 | Bad candles |
|---|---|---|---|---|---|---|---|
| frxEURUSD | 2021-10-27 | 2026-10-27 | 1,305 | 132 | 6,934 | 6,685 | 0 |
| frxGBPUSD | 2021-10-27 | 2026-10-27 | 1,305 | 133 | 7,113 | 6,689 | 0 |
| frxUSDJPY | 2021-10-27 | 2026-10-27 | 1,305 | 101 | 5,576 | 6,677 | 0 |

What is in each file:
- **Mid price.** Open, high, low and close are the average of Dukascopy's
  bid and ask prices.
- **`spread`:** the ask minus the bid, averaged over the start and end of
  the minute.
- **Missing minutes.** A minute where nobody traded is left out. Dukascopy
  repeats the last price for such minutes, and keeping those would make
  quiet times look busier than they were.

What this means:
- **Long gaps are only holidays.** These are Christmas Day and New Year's
  Day each year, plus the last two hours of New Year's Eve. Dukascopy shows
  a few stray prices on those days, so they appear as long gaps rather than
  closed days.
- **Other gaps are short and at quiet times.** They are mostly 5 to 30
  minutes (median 6) around 21:00 to 23:00 UTC, the daily "rollover" when banks settle
  and trading is thin. Others fall in the early Asian hours (02:00 to
  03:00).
- **About 1,435 of 1,440 minutes are present on a normal day.**
  Dukascopy is a little less complete than Deriv, as expected for a real
  interbank feed.
- **Fridays after 20:55:** Dukascopy keeps quoting until about 21:00 to
  22:00 UTC, but Deriv is closed then. The files keep these minutes (we
  store the source as it is). The backtester must drop them using Deriv's
  hours.
- **Weekends** are not stored. That includes Sunday evening, when Dukascopy
  reopens but Deriv does not.

### Dukascopy vs Deriv on the same minutes

On the year both sources cover (258 days per pair):

| Symbol | Minutes compared | Typical close difference | 95% of minutes within | Typical Dukascopy spread |
|---|---|---|---|---|
| frxEURUSD | 360,394 | 0.05 pip | 0.35 pip | 0.3 pip |
| frxGBPUSD | 360,131 | 0.10 pip | 0.50 pip | 0.65 pip |
| frxUSDJPY | 360,585 | 0.10 pip | 0.55 pip | 0.4 pip |

In plain terms:
- **Deriv's forex price is essentially a mid price.** It sits within a
  fraction of a pip of Dukascopy's mid most of the time.
- **Dukascopy's spread is the banks' raw spread**, not a Deriv cost. On
  Deriv Multipliers the main cost is the commission (0.02% to 0.028% of the
  position size, see `docs/deriv_api_notes.md`). Backtests will still add a
  spread and slippage allowance as the research rules require.

## Anything suspicious?

Nothing that blocks research. Points to keep in mind:
1. **Deriv history is short and rolling.** If the daily workflow stops for
   longer than a year, the oldest data cannot be fetched again. GitHub
   emails on failure.
2. **Hourly Friday candle:** use 1h candles built from 1m data, or
   Deriv's 1h candles, but don't mix the two in one test (see above).
3. **Dukascopy quotes outside Deriv's hours** (Friday evening): the
   backtester must apply Deriv's trading hours.
4. **Download notes.** Dukascopy throttles downloads from the cloud session
   heavily, so its bulk download runs on GitHub Actions. Deriv has a
   separate, undocumented rate limit for history requests (~30 per minute).
   The collectors handle both.

## Size

| What | Size |
|---|---|
| `data/` (Deriv, 1 year, 3 pairs × 1m/15m/1h) | 10.5 MB (1m 9.3, 15m 0.9, 1h 0.3) |
| `data_external/dukascopy/` (5 years, 3 pairs, 1m) | 61 MB |
| **Repo size on GitHub** (git history, compressed) | **71 MB** |
| Full clone on disk (files + git history) | 143 MB (158 MB counting disk block overhead) |
| Largest single file | about 20 KB (limit: 50 MB) |

Growth: the daily Deriv workflow adds about 11 MB per year. Dukascopy only
grows if the backfill is run again.
