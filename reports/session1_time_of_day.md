# Session 1: does the time of day give an edge after Deriv's cost?

Run on 10 Nov 2026 on branch `session1-timeofday`. Measurement only: no trades of any kind,
nothing registered. The definition was fixed and committed before the run
(`research/session1/definition.md`). The script is `scripts/session1_time_of_day.py`, and the
raw numbers are in `research/session1/results.json` and `results_attempt2.json`.

## The honest conclusion

**No hour and no session is positive after Deriv's real cost. 0 of the 93 patterns tested
pass.**

- **Each hour does move a lot**, but in no reliable direction. A typical 1-hour candle spans
  6-35 pips from high to low, while the *average* direction of any hour is under 1.4 pips.
- **The cost is bigger than every average move.** The cheapest hours cost 2.6 pips on EUR/USD
  and GBP/USD and about 4 pips on USD/JPY; each hour's real cost was subtracted.
- **The best pattern** is "sell EUR/USD in the 15:00 UTC hour". Before cost it fell about 1.1
  pips on average, in both halves of the five years. After cost it still loses about 1.8 pips a
  trade in its weaker half.
- **Luck:** about half the hour-by-pair patterns (37 of 72) kept the same direction in both
  halves, which is what coin flips would give. Shuffled data finds patterns as strong as the
  best real one before cost 19% of the time.
- **Ranaldo's idea:** 5 of the 6 predicted directions show up (euro and pound weaker during
  London hours and stronger in New York hours; yen weaker in Asian hours). But the moves are
  small (0.4 to 1.1 pips a session), mostly not statistically clear, and all lose money after
  cost.

Nothing passes, so nothing is proposed. For the record, no registered incubator candidate trades
one of these hourly patterns.

## What was measured

- **Data:** Dukascopy 1-minute prices for EUR/USD, GBP/USD and USD/JPY, 27 Oct 2021 to 27 Oct
  2026. That is 1,299 trading days, about 30,400 one-hour candles per pair. Nothing dated
  31 Oct 2026 or later was read.
- **Minutes kept:** only the minutes when Deriv's market is open (weekdays, Friday until
  20:55 UTC).
- **1-hour candles on UTC hours.**
  - "Return" is close minus open in pips: positive means the pair rose during that hour.
  - "Range" is high minus low in pips.
- **Real cost:** the measured Deriv commission for the hour the trade opens
  (`research/phase2/cost_by_hour.json`), turned into pips at that candle's price. No spread or
  slippage was added. It is about 2.6 pips in the cheap hours (08:00-17:59 UTC) for EUR/USD and
  GBP/USD, 4 pips for USD/JPY, and 12 times that at 21:00 UTC.
- **The pass rule (fixed before the run):** a pattern counts only if it moves the same way in
  the older half (Oct 2021 to Apr 2024) and the newer half (Apr 2024 to Oct 2026), *and* is
  positive after cost in both halves.

## 1. Hour by hour

Average return and t-value, average range and cost, all in pips.

- **Bold** marks |t| ≥ 2, the usual line for "probably not chance" if you only looked once.
- \* marks hours outside the project's entry window (06:00-17:59 UTC). Those could not be traded
  under the CLAUDE.md rules anyway.

| Hour (UTC) | EUR/USD return | EUR/USD range | EUR/USD cost | GBP/USD return | GBP/USD range | GBP/USD cost | USD/JPY return | USD/JPY range | USD/JPY cost |
|---|---|---|---|---|---|---|---|---|---|
| 00 * | +0.01 (t +0.0) | 12 | 3.0 | -0.48 (t -1.2) | 14 | 3.3 | -0.32 (t -0.5) | 30 | 4.2 |
| 01 * | -0.28 (t -1.3) | 12 | 3.1 | +0.06 (t +0.2) | 14 | 3.4 | -0.49 (t -1.0) | 27 | 4.3 |
| 02 * | +0.34 (t +1.8) | 10 | 3.0 | +0.13 (t +0.6) | 12 | 3.2 | **+1.08** (t +2.5) | 21 | 4.1 |
| 03 * | -0.24 (t -1.4) | 8 | 3.0 | -0.31 (t -1.6) | 10 | 3.1 | -0.54 (t -1.1) | 19 | 4.0 |
| 04 * | -0.23 (t -1.5) | 8 | 3.0 | -0.09 (t -0.5) | 10 | 3.1 | -0.04 (t -0.1) | 19 | 4.0 |
| 05 * | +0.15 (t +0.8) | 10 | 3.2 | -0.06 (t -0.2) | 12 | 3.1 | +0.48 (t +1.3) | 20 | 4.3 |
| 06 | -0.33 (t -1.2) | 14 | 3.0 | -0.11 (t -0.3) | 19 | 3.0 | +0.20 (t +0.4) | 25 | 4.1 |
| 07 | +0.30 (t +0.8) | 19 | 2.8 | -0.27 (t -0.6) | 24 | 2.8 | +0.51 (t +0.9) | 28 | 4.1 |
| 08 | +0.56 (t +1.6) | 19 | 2.6 | +0.18 (t +0.4) | 24 | 2.6 | -0.26 (t -0.4) | 27 | 4.0 |
| 09 | -0.47 (t -1.5) | 16 | 2.6 | +0.23 (t +0.6) | 22 | 2.6 | +0.66 (t +1.5) | 23 | 4.0 |
| 10 | -0.15 (t -0.6) | 15 | 2.6 | -0.59 (t -1.6) | 20 | 2.6 | -0.04 (t -0.1) | 20 | 4.0 |
| 11 | **-1.31** (t -4.5) | 16 | 2.6 | -0.62 (t -1.5) | 22 | 2.6 | +0.28 (t +0.7) | 21 | 4.0 |
| 12 | +0.21 (t +0.4) | 22 | 2.6 | +0.17 (t +0.3) | 28 | 2.6 | +0.29 (t +0.4) | 33 | 4.3 |
| 13 | +0.57 (t +1.2) | 24 | 2.6 | +0.47 (t +0.8) | 30 | 2.6 | -0.84 (t -1.1) | 35 | 4.3 |
| 14 | +0.65 (t +1.4) | 24 | 2.6 | +0.25 (t +0.4) | 30 | 2.6 | -0.20 (t -0.3) | 34 | 4.2 |
| 15 | **-1.07** (t -2.6) | 22 | 2.6 | -0.19 (t -0.4) | 27 | 2.6 | +0.88 (t +1.4) | 29 | 4.2 |
| 16 | -0.25 (t -0.8) | 16 | 2.6 | -0.09 (t -0.2) | 21 | 2.6 | **+0.94** (t +2.4) | 21 | 4.3 |
| 17 | +0.17 (t +0.7) | 14 | 2.6 | +0.27 (t +0.8) | 17 | 2.6 | +0.24 (t +0.6) | 19 | 4.5 |
| 18 * | +0.17 (t +0.6) | 14 | 5.9 | +0.12 (t +0.3) | 17 | 5.7 | +0.02 (t +0.1) | 19 | 10.1 |
| 19 * | +0.07 (t +0.3) | 12 | 3.1 | +0.32 (t +1.0) | 14 | 2.9 | **+0.98** (t +2.7) | 16 | 5.2 |
| 20 * | +0.19 (t +1.2) | 9 | 9.8 | +0.27 (t +1.4) | 11 | 9.5 | +0.36 (t +1.0) | 13 | 15.9 |
| 21 * | **+0.51** (t +3.8) | 6 | 31.6 | **+0.45** (t +3.2) | 9 | 31.3 | **-0.88** (t -3.8) | 11 | 47.8 |
| 22 * | **+0.51** (t +3.5) | 6 | 15.6 | +0.19 (t +1.0) | 8 | 15.3 | **-0.94** (t -2.8) | 14 | 23.5 |
| 23 * | +0.18 (t +0.9) | 7 | 11.3 | +0.04 (t +0.2) | 9 | 12.0 | -0.65 (t -1.5) | 19 | 16.9 |

How to read it:

- **Ranges are large; average moves are tiny.** In the busy hours (12:00-15:00 UTC) a candle
  covers 22-35 pips, but its *average* direction is under 1 pip. Each hour's direction is close
  to a coin flip.
- **10 of the 72 cells have |t| ≥ 2**, against about 3-4 expected by chance. Half of them are
  the 21:00-22:00 rollover hours. There the dollar weakens a little against the euro and pound
  and strengthens against the yen. Those hours cost 12-15 pips or more on Deriv (it is the
  daily pause and the widest-cost period), and they are outside the entry window. So it is
  interesting, and untradable.
- **EUR/USD at 11:00 UTC** (-1.3 pips, t -4.5) was strong in the older half (-2.2 pips) and
  mostly faded in the newer half (-0.45). That is the kind of pattern that disappears.
- **EUR/USD at 15:00 UTC** (-1.1 pips) is the hour before the 16:00 London fix. It is the most
  consistent hour (-0.75 older, -1.4 newer), but smaller than its 2.6-pip cost.

## 2. Sessions and the Ranaldo idea

Each session's move per day is the sum of its hours. A session trade pays one commission, at
its first hour's rate. All figures are in pips.

| Pair | Session (UTC) | Average move a day (t) | Older half | Newer half | Cost | After cost, weaker half |
|---|---|---|---|---|---|---|
| EUR/USD | Asian 00-06 | -0.57 (t -1.1) | -1.23 | +0.10 | 3.0 | -3.1 |
| EUR/USD | London 07-11 | -1.08 (t -1.5) | -1.37 | -0.78 | 2.8 | -2.0 |
| EUR/USD | Overlap 12-15 | +0.36 (t +0.4) | -0.21 | +0.93 | 2.6 | -2.8 |
| EUR/USD | New York 16-20 | +0.35 (t +0.6) | +0.97 | -0.27 | 2.6 | -3.0 |
| EUR/USD | Late 21-23 | +1.21 (t +4.4) | +1.23 | +1.19 | 31.5 | -31.1 |
| GBP/USD | Asian 00-06 | -0.86 (t -1.3) | -1.56 | -0.15 | 3.3 | -3.2 |
| GBP/USD | London 07-11 | -1.07 (t -1.1) | -1.86 | -0.27 | 2.8 | -2.6 |
| GBP/USD | Overlap 12-15 | +0.71 (t +0.6) | -0.05 | +1.46 | 2.6 | -2.6 |
| GBP/USD | New York 16-20 | +0.89 (t +1.2) | +1.45 | +0.33 | 2.6 | -2.4 |
| GBP/USD | Late 21-23 | +0.68 (t +2.2) | +0.74 | +0.62 | 31.3 | -31.5 |
| USD/JPY | Asian 00-06 | +0.38 (t +0.3) | +3.24 | -2.49 | 4.2 | -6.9 |
| USD/JPY | London 07-11 | +1.14 (t +1.0) | +0.39 | +1.89 | 4.1 | -3.5 |
| USD/JPY | Overlap 12-15 | +0.14 (t +0.1) | +1.51 | -1.24 | 4.3 | -5.8 |
| USD/JPY | New York 16-20 | **+2.54 (t +3.0)** | +3.06 | +2.02 | 4.3 | -2.5 |
| USD/JPY | Late 21-23 | -2.46 (t -4.2) | -3.40 | -1.52 | 47.7 | -49.1 |

**Ranaldo (2009): a currency weakens during its own working hours and strengthens at night.**
The predictions were fixed before the run:

| Prediction | Result | t | Older / newer half | After cost |
|---|---|---|---|---|
| EUR weakens in London hours (EUR/USD falls 07-11) | yes, -1.08 | -1.5 | -1.37 / -0.78 | loses 2.0 |
| USD weakens in New York hours (EUR/USD rises 16-20) | yes, +0.35 | +0.6 | +0.97 / **-0.27** | loses 3.0 |
| GBP weakens in London hours (GBP/USD falls 07-11) | yes, -1.07 | -1.1 | -1.86 / -0.27 | loses 2.6 |
| USD weakens in New York hours (GBP/USD rises 16-20) | yes, +0.89 | +1.2 | +1.45 / +0.33 | loses 2.4 |
| JPY weakens in Asian hours (USD/JPY rises 00-06) | yes, +0.38 | +0.3 | +3.24 / **-2.49** | loses 6.9 |
| USD weakens in New York hours (USD/JPY falls 16-20) | **no, +2.54** (USD got stronger) | +3.0 | +3.06 / +2.02 | loses 7.1 |

In plain words:

- The euro and pound pattern matches Ranaldo in direction. The London-hours weakening of EUR and
  GBP shows up in both halves, but it shrank in the newer half and is about 1 pip a day, under
  the 2.8-pip cost.
- Five of six right directions would happen by pure chance about 1 time in 9, so this is a
  hint, not proof.
- The one clearly significant session result goes *against* the theory. USD/JPY rose in New
  York hours (+2.5 pips a day, both halves), which means the dollar strengthened in its own
  hours. After the 4.3-pip cost it still loses.

## 3. Luck: is the best result better than shuffled data?

- **Tests counted:** 93 (72 hour × pair, 15 session × pair, 6 Ranaldo predictions). Nothing was
  tuned. The definition was fixed and committed before the run.
- **Shuffled versions:** 200. For each pair and each day, that day's hourly moves were shuffled
  among its hours. Each day keeps its total move and the long-run trend; only *which hour* a
  move fell in is random. The same pass rule and score were then applied.

| | Real data | Shuffled: middle | Shuffled: top 5% | Shuffles at least as good |
|---|---|---|---|---|
| Patterns passing (after cost, both halves) | **0** | 0 | 0 | 100% |
| Best pattern after cost, weaker half (attempt 2) | **-1.82 pips** (EUR/USD 15:00, sell) | -2.11 | -1.83 | 4.5% |
| Best pattern before cost, weaker half | **+1.06 pips** (USD/JPY 02:00, buy) | +0.93 | +1.33 | 19% |

What this says:

- **Before cost** the best real pattern is ordinary: 1 shuffle in 5 does as well. Real
  time-of-day patterns, if any, are no stronger than what luck produces in 72 tries. The rate
  of hours keeping their direction in both halves (37 of 72) is also the coin-flip rate.
- **After cost** the best real pattern (sell EUR/USD in the 15:00 hour) is a bit better than
  most shuffles: only 4.5% match it. That fits the one consistent hour above, the hour before
  the London 16:00 fix. But "better than luck" here still means **losing 1.8 pips a trade** in
  its weaker half, so it is not usable.
- **The fix-hour idea was already tested** in the incubator pre-screen as `fix_reversal` (i1,
  31 Oct 2026). That idea faded the hour before the fix rather than following it, and it lost
  before costs.

**Second attempt, disclosed:** the luck section of my definition contradicted itself.
- One sentence said each hour's cost moves with its shuffled return. Another said the cost stays
  with the hour, as in real trading.
- Attempt 1 followed the first sentence. That spreads the 12x late-evening costs over every
  shuffled hour, so the shuffled after-cost scores came out too low. The real pattern then
  looked better than every shuffle (median -4.26, 0% as good), which was misleading.
- I recorded the problem, changed only that one thing (costs stay with their hour) and ran
  again. Those are the attempt-2 numbers above.
- Every real (unshuffled) number, the before-cost luck check and the verdict are the same in
  both attempts. Both files are kept: `results.json` (attempt 1) and `results_attempt2.json`.

## 4. What it means for the bot

- Time of day on its own is not an edge on Deriv. The average hourly or session drift in these
  three pairs is 0-2.5 pips, and Deriv charges 2.6-4.3 pips per trade in the cheap hours.
- The strongest time-of-day effects are around the 21:00-22:00 UTC rollover. That is exactly
  when Deriv pauses new trades and charges up to 12 times the base rate.
- Time of day still matters as a filter for costs, and the project already uses it that way:
  new trades only 06:00-17:59 UTC.
- Nothing is proposed for the incubator. No registered candidate is affected.
