# Strategy research (Phase 4)

Written 2026-10-30, updated after each round. Pre-holdout data only (Dukascopy 1m, 2021-10-27 to
2026-04-27). **The holdout (Deriv data from 2026-04-28) was not touched.**

## Program status (updated at the end of each round)

| Round | Families | Variants | Running total | Luck check | Result |
|---|---|---|---|---|---|
| 1 | 1–5 (approved 30 Oct) | 132 | 132 | beat p95 of 200 random runs | **nothing passed** |
| 2 | 6–8 (designed from round 1) | 38 (incl. 9 void) | 170 | beat p99 of 500 random runs | **nothing passed** |
| 3 | to come | | | p99 of 500 | |

The holdout has not been touched, and won't be until the whole program
ends.

## The short version (after round 2)

- **No strategy passed in either round.** 170 variants tried, every one
  logged in `research/log.md`.
- The closest result is still round 1's **buy-the-dip in a daily trend, 4h**
  (family 3). It broke even, but:
  - random entries did as well 1 time in 5;
  - its profit came from the first three half-years only;
  - nearby settings did not work.
- **Most strategies did no better than random entries before costs.**
  Their losses are roughly the commission they paid. Several were close to
  break-even at MT5 costs (−3 to −5 USD) and lost 23–40 USD at Multiplier
  costs.
- The one entry that beat random in round 1 (London breakout) lost that
  edge when filtered and given wider targets in round 2.
- **Recommendation so far:** do not trade any of these, on demo or real.

## 1. How the testing worked

These rules were agreed on 30 October, before any testing.

**Data**
- **Period:** pre-holdout only. Walk-forward with 5 rounds: each round
  chooses settings on 24 months, then tests the next 6 months. The 5 test
  periods join into one 30-month out-of-sample run, 2023-10-27 to
  2026-04-26.
- **Choosing settings:** in each round, the variant with the best net
  profit divided by max drawdown on its training window (measured costs, 3
  pairs combined) was used for the next 6 months.

**Costs and trading rules**
- **Commission:** the measured rate for the UTC hour each trade opens
  (`research/phase2/cost_by_hour.json`).
- **Slippage:** 0.5 pip on entry, 1 pip on stop-loss exits.
- **Every run is also priced** at 1.5× commission and at MT5 costs (MT5
  for comparison only).
- **Risk and calendar:**
  - all CLAUDE.md hard limits on: x100, 3% stake, at most 2 trades;
  - entry window 06:00–17:59 UTC; 12:00–12:59 blocked on all pairs and
    13:00–13:59 on EUR/USD (cost table);
  - everything closed by Friday 20:30;
  - fixed signal wait: 1h, 4h or 12h by timeframe.

**Kill switch and luck check**
- **Kill switch:** research "observe" mode. When the account fell to 50%,
  the event was recorded and the account restarted at 100 USD, so every
  result covers the whole period. **Any firing = fail.**
- **Luck check:** 200 runs per strategy with **random entries** (random
  direction), using:
  - the same exits;
  - the same candle hours;
  - the same number of signals per pair and hour;
  - the same costs and limits.

  To pass, a strategy must beat the best 5% of those random runs.

**To pass, a strategy must have:**
- a profit after costs on at least 2 of 3 pairs, and overall;
- 200 or more out-of-sample trades;
- at most 5 settings;
- an average win at least 3× the average commission;
- no kill switch;
- a pass on the luck check.

## 2. Results (out of sample, 2023-10-27 to 2026-04-26, 100 USD start)

USD figures are the net result over 30 months.

| Strategy | Variants | Trades | Net (measured) | Worst fall | Win rate | Avg win / loss (USD) | Profit factor | Monte Carlo p95 fall | Kill switch | Net at 1.5× (kill) | Net at MT5 | Beat random runs | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. London breakout, 1h | 24 | 1,256 | **−56.30** | 55% | 37% | 0.71 / −0.50 | 0.86 | 63% | 1× | −88.05 (1) | −2.98 | **95.5%** | Fail |
| 2. Trend breakout, 4h | 18 | 266 | **−40.83** | 45% | 36% | 1.23 / −0.92 | 0.74 | 54% | 0 | −46.11 (1) | −33.84 | 23% | Fail |
| 2. Trend breakout, daily | 12 | 130 | **−26.97** | 32% | 45% | 1.30 / −1.42 | 0.74 | 42% | 0 | −30.04 (0) | −22.87 | 32% | Fail |
| 3. Trend pullback, 4h | 16 | 309 | **+0.70** | 33% | 47% | 2.04 / −1.83 | 1.00 | 43% | 0 | −9.69 (0) | +11.39 | 78% | Fail (luck check) |
| 3. Trend pullback, 1h | 8 | 1,251 | **−123.27** | 53% | 39% | 0.66 / −0.58 | 0.72 | 83% | 2× | −147.59 (3) | −76.57 | 15% | Fail |
| 4. Mean reversion, 1h | 16 | 551 | **−61.63** | 50% | 40% | 0.65 / −0.61 | 0.70 | 61% | 1× | −76.35 (1) | −42.78 | 9% | Fail |
| 4. Mean reversion, 4h | 8 | 167 | **−10.14** | 26% | 47% | 1.46 / −1.43 | 0.92 | 34% | 0 | −15.37 (0) | −5.74 | 64% | Fail |
| 5. Session drift, 1h | 30 | 1,290 | **−107.92** | 50% | 45% | 0.46 / −0.53 | 0.71 | 80% | 2× | −141.97 (2) | −65.66 | 12% | Fail |

Profit by pair (measured cost):

| Strategy | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| 1. London breakout | −24.53 | −22.24 | −9.53 |
| 2. Trend breakout 4h | −22.25 | −16.20 | −2.38 |
| 2. Trend breakout daily | −10.75 | −5.45 | −10.77 |
| 3. Trend pullback 4h | **+19.31** | **+10.98** | −29.59 |
| 3. Trend pullback 1h | −47.17 | −38.11 | −37.99 |
| 4. Mean reversion 1h | −25.77 | −15.94 | −19.92 |
| 4. Mean reversion 4h | −3.13 | **+1.87** | −8.88 |
| 5. Session drift | −55.26 | −52.66 | 0 (no USD/JPY trades by design) |

How to read it:
- **Profit factor** is total won ÷ total lost. Above 1 means profit.
  Only the trend pullback on 4h reached 1.00.
- **The Monte Carlo p95 fall** is the drawdown that only 5% of reshuffled
  trade orders beat. Every strategy shows 34–83%, so even the "flat" ones
  came close to the 50% kill switch in bad orderings.
- **"Beat random runs"** is the share of 200 random-entry runs the
  strategy beat. 95% is needed.
- **Net losses above 100 USD** (trend pullback 1h, session drift) are
  possible because of the research restarts. After each kill the account
  restarted at 100 USD.
- **The minimum target** (average win ≥ 3× average commission) was met by
  every strategy. That rule was never the problem. The problem is the
  losing trades.

Full reports per strategy are in `reports/backtests/phase4_<name>_oos/`:
the report, trades, an equity chart and gate skips. Walk-forward picks,
grid results and luck runs are in `research/phase4/<name>/`.

## 3. What failed and why, in plain language

**1. London open breakout.**
- **The idea:** trade the break of the quiet Asian-hours range when London
  opens.
- **Result:** every one of the 24 variants lost money in every training
  period. It lost out of sample too.
- **What's still interesting:** it beat 95.5% of random-entry runs, so the
  breakout direction does carry a small amount of real information.
- **Why it fails:** that information is worth less than the commission. At
  MT5's lower costs the same trades roughly broke even (−3 USD).
- **In short:** the signal is real but too weak for our costs.

**2. Multi-day trend breakout (4h and daily).**
- **The idea:** buy new multi-day highs, sell new lows, and ride the trend.
- **Result:** it lost on every pair. It did worse than random entries, and
  even at MT5 costs.
- **Why:** in 2023–2026 these pairs made few clean multi-week trends. Most
  breakouts reversed.
- **Note:** the Friday close (required until the Phase 6 weekend test)
  also cuts off the long trends this idea depends on.
- **In short:** the signal does not work here, whatever the cost.

**3. Buy the dip in a daily trend (4h and 1h).**
- **4h version:** the same settings won every round, and in training
  profit was about 7 times the worst fall. Out of sample, that faded to
  break-even.
  - EUR/USD and GBP/USD made money; USD/JPY lost most of it back.
  - Random entries with the same stops and targets did this well 22% of
    the time.
  - Strong training numbers followed by a flat test is the classic sign of
    a pattern that fitted the past rather than one that predicts the
    future.
- **1h version:** small dips on hourly candles were mostly noise, and the
  commission ate the account twice.
- **In short:** the closest call, but no evidence of an edge.

**4. Mean reversion in calm markets (1h and 4h).**
- **The idea:** fade big stretches away from the average when the market
  is calm.
- **Result (1h):** it did worse than 91% of random entries. Stretched
  prices tended to keep going.
- **Result (4h):** about break-even before costs, losing after, with too
  few trades.
- **In short:** no edge.

**5. Time-of-day drift.**
- **The idea:** published research (Ranaldo 2009; Breedon and Ranaldo
  2013, using 1997–2007 data) found that a currency tends to weaken during
  its own country's working hours. The directions were fixed from those
  papers before testing.
- **Result:** short EUR/USD and GBP/USD in the European morning lost
  steadily. It did worse than 88% of random-direction runs at the same
  hours.
- **Why:** the effect seems to have faded, or even reversed, since the
  papers' data period.
- **I did not try the opposite direction.** Flipping a rule because our
  data says so is exactly the data-mining the owner ruled out.

## 3b. Round 2: new families designed from round 1's failures

Round 2 used the stricter luck bar: the running total passed 150 variants,
so a strategy had to beat the **99th percentile of 500** random runs. Before
calling anything a candidate, four more checks were added (owner, 30 Oct):
- **Not one pair:** without its best pair, the rest still makes money.
- **Not one period:** it makes money in at least 3 of the 5 half-year test
  windows, and still does without the best one.
- **Not a few big trades:** it is still profitable without its largest 2%
  of trades.
- **Nearby settings work:** settings one step away also made money on
  average in the test windows.

Round 1 was re-checked against them for information. Every round 1
strategy fails all four, including the near-miss trend pullback 4h. That
one made money in its first three half-years (+7, +5, +22 USD) and lost in
the last two (−10, −24).

What round 1 taught, and how round 2 used it:
1. **Many short trades lose to the commission; the near misses held
   longer.** So round 2 aimed for fewer trades and wider targets.
2. **The London breakout was the only entry better than random, but its
   moves were too small.** Family 6 traded it only after a quiet Asian
   night, with a target sized on the daily range.
3. **Fading stretched moves did worse than random,** which suggests short
   moves tend to continue. Family 8 follows a strong morning move instead.
4. **Multi-day breakouts failed, and the Friday close cuts trends.**
   Family 7 makes one trade per week in the direction of the past months
   (time-series momentum, a documented effect at longer horizons).

| Strategy (round 2) | Variants | Trades | Net (measured) | Worst fall | Win rate | Avg win / loss | Profit factor | Monte Carlo p95 fall | Kill switch | Net at 1.5× (kill) | Net at MT5 | Beat random runs | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 6. Quiet-night London breakout, 1h | 8 | 872 | **−39.94** | 45% | 30% | 0.66 / −0.35 | 0.81 | 49% | 0 | −61.40 (1) | −5.35 | 41% | Fail |
| 7. Weekly momentum, daily (Monday close) | 9 + 9 void | 260 | **−32.45** | 50% | 44% | 2.24 / −1.94 | 0.89 | 60% | 0 | −37.49 (0) | −29.53 | 34% | Fail |
| 8. Morning momentum, 1h | 12 | 419 | **−23.46** | 30% | 43% | 0.70 / −0.64 | 0.85 | 38% | 0 | −34.26 (0) | −4.26 | 50% | Fail |

| Strategy (round 2) | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| 6. Quiet-night London breakout | −32.53 | −9.43 | +2.02 |
| 7. Weekly momentum | +25.95 | −22.29 | −36.11 |
| 8. Morning momentum | −8.07 | −12.41 | −2.98 |

In plain language:
- **Family 6:** the filter left fewer, weaker breakouts and lost the
  original's slight edge over random entries (41%). It nearly broke even
  at MT5 costs (−5 USD), so the commission is again most of the loss.
- **Family 7:** holding a whole week makes results swing widely. The
  99th-percentile random run made +82 USD, so only a big real edge would
  show. There was none: it lost on 2 of 3 pairs, and its EUR/USD gain came
  from one half-year.
- **Family 8:** a strong morning did not predict the afternoon. It landed
  exactly at the middle of the random runs, and its loss is close to the
  commission it paid.

**A rule side effect worth knowing.** Family 7's first version signalled
on Friday's daily close and **made no trades at all**. The fixed 12-hour
wait for daily signals expires a Friday-close signal before Monday's open.
- The same rule silently dropped Friday signals in round 1's daily trend
  test.
- This is the rule working as written, not a bug.
- Family 7 was moved to Monday's close. The 9 empty variants still count in
  the running total.

## 4. How likely is a pass to be luck?

- 132 variants across 8 sub-grids. Each sub-grid gave one walk-forward
  result, so there were **8 chances to pass.**
- With 8 independent tries at a 5% luck threshold, the chance that at
  least one passes by pure luck is about **1 in 3** (1 − 0.95⁸ ≈ 34%).
- So even a single pass would have needed the holdout to back it up.
- With no passes, the honest conclusion is: **in this period, none of
  these ideas beat Deriv's Multiplier costs on these pairs.**

## 5. Shortlist, holdout and next steps

- **Shortlist: empty.** No holdout test was run. The holdout is still
  untouched, so it stays valid for any future candidate.
- **Re-check after 5 Nov** (`cost_by_hour.json`): nothing to re-run. If
  the cheap window moves, past results would shift only slightly, not
  enough to turn any of these losses into a pass. Family 1, the most
  cost-sensitive, would need the commission to roughly halve.
- **MT5 decision note:** not needed. CLAUDE.md asks for one only if a
  strategy passes at MT5 costs. None did: the London breakout came closest
  at −3 USD, and the trend pullback made +11 USD at MT5 cost but would
  still fail the luck check.

**Recommendation:** do not run any of these strategies on demo or real
money, and do not move to Phase 5/6 with them.

Ideas worth trying next, in order of how promising they look. Each would be
a new family with its own approved plan and budget, logged in the same way:

1. **Fewer, bigger trades from the one real signal.** The London breakout
   is the only entry that beat random. A version that trades only on wide
   Asian ranges, or only on Tuesday–Thursday, with targets held into the
   afternoon, would pay the same 3 pips for a larger move. The risk is
   that this slices the same data again; the budget should be small (about
   10 variants).
2. **Wait for the Phase 6 weekend test.** If holding over the weekend
   turns out to be safe and cheap, the trend families lose their worst
   handicap, the Friday close. They could be re-tested once, on daily
   candles only.
3. **Add a news filter.** Skipping known big releases (US jobs, CPI, rate
   decisions) removes the hours where Deriv's commission jumps and prices
   gap past stops. This needs an economic calendar source first.
4. **Accept the result.** These five are the standard ideas for 1h–daily
   forex. If the next small round also fails, the honest answer is that
   Multipliers at about 3 pips per trade are too expensive for these
   approaches on these pairs.

Do not try more variants of families 2–5 on this same data. Each extra
batch makes a lucky pass more likely, not a real one.

## Files

| What | Where |
|---|---|
| Every variant tried | `research/log.md` (Phase 4 section) |
| Walk-forward picks, grid, luck runs, pass checks per strategy | `research/phase4/<name>/` |
| Out-of-sample reports (measured, 1.5×, MT5, Monte Carlo) | `reports/backtests/phase4_<name>_oos/` |
| Strategy code (shared with the live bot) | `src/fxbot/strategies/families.py` |
| Harness | `src/fxbot/backtest/research.py`, `scripts/research_family.py` |

Rebuild any family:
```
python scripts/research_family.py grid --family f1
python scripts/research_family.py oos --family f1
python scripts/research_family.py luck --family f1
python scripts/research_family.py summary --family f1
```
Each stage resumes if stopped.
