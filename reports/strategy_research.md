# Strategy research (Phase 4)

Written 2026-10-30, updated after each round. Pre-holdout data only (Dukascopy 1m, 2021-10-27 to
2026-04-27). **The holdout (Deriv data from 2026-04-28) was not touched.**

> **Round 4 (30 Oct 2026, the final round) is in section 3d.** It added a
> machine-learning strategy and two original rule families, 48 variants in
> all, judged with a stricter luck check. Nothing passed. The totals below
> and in section 4 include it.

> **Audit note (30 Oct 2026, after this report):** `reports/audit_phase4.md`
> checked the pipeline with positive controls and found one bug in the luck
> check. The random-entry runs for families 6 and 8 made 30-41% fewer trades
> than the candidate, so the "beat random runs" figures quoted below for
> those two (41% and 50%) are understated and their luck checks need
> re-running; the other families' luck figures are flattered, if anything.
> No net result, pair result or pass/fail verdict in this report changes.

## Program status (updated at the end of each round)

| Round | Families | Variants | Running total | Luck check | Result |
|---|---|---|---|---|---|
| 1 | 1–5 (approved 30 Oct) | 132 | 132 | beat p95 of 200 random runs | **nothing passed** |
| 2 | 6–8 (designed from round 1) | 38 (incl. 9 void) | 170 | beat p99 of 500 random runs | **nothing passed** |
| 3 | 9–10 (designed from rounds 1–2) | 16 | 186 | beat p99 of 500 random runs | **nothing passed** |
| 4 (final) | track A: ML day strategy (24 model settings); track B: families 11–12 (24) | 48 | **234** | beat p99 of 500 coin-toss runs on the candidate's own signal days | **nothing passed** |

**The program is finished. No strategy passed.** With no final candidates,
the holdout was not used. It is still untouched and valid for any future
research.

## The short version (final, after round 4)

- **No strategy passed in any round.** 234 variants were tried: 10 rule
  families (13 strategy versions) in rounds 1–3, then in round 4 a
  machine-learning strategy (24 model settings) and 2 original families
  (24 variants), every one logged in `research/log.md`.
- **Round 4 in one line:** the model found a real but tiny signal (about 1
  pip a trade before costs, beating 80% of coin-toss runs where 99% was
  needed) and lost 32 USD after costs; the dollar-wide catch-up family lost
  before costs; the lone-mover family made too few trades and lost. Section
  3d has the details and what the models learned.
- **Nothing was tested on the holdout.** That step is only for final
  candidates, and there are none.
- **The common pattern: almost every idea had about zero edge before
  costs.**
  - Most did no better than random entries with the same exits.
  - The commission, about 3 pips per trade, then turned them into steady
    losses.
  - Several were within a few USD of break-even at MT5's lower costs, and
    lost 23–60 USD at Multiplier costs.
- **The two nearest misses**, neither a candidate:
  - **Buy the dip in a daily trend, 4h (family 3):** broke even. Its profit
    faded after 2024, and random entries did as well 1 time in 5.
  - **EUR vs GBP convergence (family 9):** +6 USD with a small 8%
    drawdown, and nearby settings also worked. But it had only 122 trades,
    its gain came mostly from one half-year, and it loses without its 5
    best trades.
- **Recommendation: do not trade any of these, on demo or real money.**
  Section 5 lists what could change the picture. Every option there needs
  your approval, because it changes data, pairs or CLAUDE.md.

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

## 3c. Round 3 (last): ideas of a different kind

Rounds 1–2 showed that single-pair price patterns had about zero edge
before costs. Round 3 tried two kinds of idea not yet tested. Both needed
only the existing data and rules.
- **Family 9, EUR vs GBP convergence (daily).**
  - When EUR and GBP drift unusually far apart against the dollar, buy the
    cheap one and sell the dear one, hold 3–8 days.
  - The dollar's moves largely cancel between the two legs.
  - It needed one small engine addition: a strategy can now see the other
    pairs' closed candles. That is tested for no look-ahead.
- **Family 10, after a shock day (daily).**
  - After an unusually large daily move that closes near its extreme
    (often a news day), trade its continuation for 1–3 days.

| Strategy (round 3) | Variants | Trades | Net (measured) | Worst fall | Win rate | Avg win / loss | Profit factor | Monte Carlo p95 fall | Kill switch | Net at 1.5× (kill) | Net at MT5 | Beat random runs | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 9. EUR vs GBP convergence, daily | 8 | 122 | **+6.17** | 8% | 52% | 1.76 / −1.77 | 1.06 | 28% | 0 | +2.44 (0) | +7.61 | 94% | Fail |
| 10. Shock-day continuation, daily | 8 | 103 | **−26.09** | 27% | 39% | 1.26 / −1.21 | 0.66 | 36% | 0 | −28.74 (0) | −22.44 | 10% | Fail |

| Strategy (round 3) | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| 9. EUR vs GBP convergence | −11.83 | +18.00 | not traded |
| 10. Shock-day continuation | +0.04 | −8.59 | −17.54 |

**Family 9** is the most interesting result of the program, and still not
a candidate.
- **For it:**
  - every training round was positive;
  - out of sample it made money at all three cost levels;
  - its worst fall was only 8%;
  - settings one step away also made money on average (the only family to
    pass that check).
- **Against it:**
  - only 122 trades, short of the 200 required;
  - it beat 94% of random hedged runs, below the 99% needed;
  - most of the gain came in its first half-year (+7 USD), then roughly
    flat (−0.9, −2.0, +1.0, +1.1);
  - without its 5 biggest trades it loses 19 USD.
- **A rule question for the owner (no change made).** In a hedged pair
  trade only the two legs together matter, so "profitable on 2 of 3 pairs"
  fits it poorly: here the EUR leg lost and the GBP leg won. It made no
  difference this time, because the strategy fails on trade count, luck
  and robustness anyway.

**Family 10:** after a big day, the next day was as likely to reverse as
to continue. It lost in all five half-year test windows and did worse than
90% of random entries.

## 3d. Round 4 (final): a learned strategy and two original families

Rounds 1–3 copied known ideas and found about zero edge before costs. Round 4
(plan approved by the owner, 30 Oct 2026) tried two things of a different
kind, with the same data and rules:
- **Track A:** let a model find the direction from data instead of guessing
  it. A machine-learning strategy makes one decision per pair per day.
- **Track B:** two families of my own design that read all three pairs at
  once, to tell a move of the dollar itself from a move on one pair alone.
  No Phase 4 family had done that.

**Fixed before any testing (both tracks)**
- **Horizon 08:00 → 20:00 UTC** for everything. Chosen for cost: a 12-hour
  move on EUR/USD is about 34 pips on average (45 pips standard deviation),
  so the direction only has to be right about 56% of the time to pay the
  4 pips of cost. A 1-hour move is about 8 pips and would need 80%.
- **Luck check (stricter than rounds 1–3):** 500 random runs that enter on
  **the candidate's own signal days and pairs** and only toss a coin for the
  direction. Trade count, timing and commission then match the candidate
  exactly; only the direction skill is tested. The candidate must beat the
  99th percentile.
- **Variants:** at most 30 per track, each model setting counts as one.
  Running total 186 → 234.
- **Everything else as before:** measured commission by hour, 0.5 / 1 pip
  slippage, 1.5× and MT5 runs, all CLAUDE.md limits, the four "not fake"
  checks, pre-holdout data only.

**Three owner safeguards, each with a test** (`tests/test_round4.py`):
1. Any scaling inside the model is fitted on the training window only
   (the scaler and the model sit in one pipeline that sees training rows
   only; the test checks the scaler's means equal the training rows' means
   and not the whole table's).
2. Every model has a fixed seed; fitting twice gives identical
   probabilities (tested for both model types and both training setups).
3. A saved model is **frozen**: it can predict, and any attempt to refit it
   raises an error. The single holdout test, had there been one, would have
   loaded the five pre-holdout models exactly as saved.

Plus the look-ahead tests: scrambling every candle after a cut date changes
no feature row and no prediction before it; features at 08:00 use only
candles closed by 08:00; a row's label is the same day's 20:00 close, so no
training label reaches past its training window.

### Track A: the machine-learning day strategy

**What it does.** At 08:00 UTC it computes 14 features from closed candles
(moves since midnight, in the last hour and over 1, 3, 5 and 20 trading
days; yesterday's range and the week's ranges relative to the month; where
price sits in the month's range; where yesterday closed; the weekday), all
divided by the pair's 20-day average daily range. A second feature set adds
the three pairs' moves in the dollar's direction (since midnight, 1 day,
5 days). The model gives the probability that the pair is higher at 20:00.
It trades Up above 0.5 + margin, Down below 0.5 − margin. Exit at 20:00; no
stop (as family 5).

**24 settings, all logged:** 2 models (logistic regression; gradient
boosting with 150 shallow trees) × 2 feature sets (own pair; with the other
pairs) × 2 training setups (one model for all three pairs; one per pair) ×
3 margins (55%, 58%, 62% sure).

**Retraining and honest selection.** In each of the 5 walk-forward rounds,
every setting was trained on the first 18 months of the 24-month training
window and judged on the last 6 through the real engine (net profit ÷ worst
fall, as in Phase 4). The best was retrained on all 24 months and traded on
the next 6 test months. The picks were: round 1 per-pair logistic with
peers (62%), round 2 pooled logistic, own features (58%), rounds 3 and 5
pooled gradient boosting, own features (58%), round 4 pooled logistic with
peers (62%). So the "strategy" changed model, features and margin from
round to round; no single setting won twice in a row except boosting in
rounds 3 and 5.

| Track A | Variants | Trades | Net (measured) | Worst fall | Win rate | Avg win / loss (USD) | Profit factor | Monte Carlo p95 fall | Kill switch | Net at 1.5× (kill) | Net at MT5 | Beat coin-toss runs (p99 bar) | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ML day strategy, 1h | 24 | 612 | **−32.16** | 46% | 46% | 0.72 / −0.71 | 0.86 | 49% | 0 | −46.56 (0) | −4.88 | 80% (bar +3.50) | Fail |

| Track A | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| ML day strategy | −11.59 (193 trades) | −15.60 (156) | −4.97 (263) |

Before costs it made **+10.71 USD, about 1 pip a trade**; the commission
was 37 USD. By half-year: +0.8, −17.9, −9.4, −7.6, +1.9. Without its 13
biggest trades it loses 69 USD. Neighbouring settings lost on average.
48 signals expired because both position slots were taken (three pairs,
two slots).

**The luck check is the interesting part.** The 500 coin-toss runs made
exactly 612 trades each and lost 47.6 USD on average (median −45). The
model's −32 USD beats 80% of them, and the 99th-percentile run made
+3.5 USD. So the models do carry a little real direction skill, worth about
1 pip a trade; a pass needed about 4.

**What the chosen models learned, in plain language** (from
`research/phase4/a1_ml_day/explain.json`: logistic weights, or for boosting
the permutation importance and the sign of the link to the prediction):
- **The one rule that showed up in more than one round: a 3-day reversal.**
  After the pair rose over the last three trading days, the model leaned
  Down, and the other way round. It was the strongest feature in rounds 1
  and 2 (for all three pairs in round 1).
- **A month-scale pull toward the top of the range.** "Where price sits in
  the last month's range" pushed the prediction Up in rounds 1 (GBP/USD,
  USD/JPY), 2, 3, 4 and 5: near the monthly high, the model expected more
  upside. In round 4 it was the top feature, but paired with "move over the
  last month" pushing Down, which is nearly the same information with the
  opposite sign: the model was splitting hairs between two correlated
  features, a sign of fitting noise.
- **The dollar carries across pairs.** In round 1, a dollar rise on GBP/USD
  since midnight pushed the USD/JPY prediction Up, and a dollar rise on
  USD/JPY over the last day pushed EUR/USD Down. That is exactly the
  family 11 idea, found independently by the model, and family 11 then lost
  out of sample.
- **The boosting models (rounds 3 and 5) learned trend-following at several
  scales** (last day, last week, last month all pushing the same way as the
  move) and fitted their training rows far better (73% right) than the
  logistic models (56–61%). Out of sample both won 46% of trades. A model
  that is 73% right on data it has seen and 46% on data it has not is the
  classic sign of memorising noise.
- **Pair and weekday biases.** The pooled round 2 model leaned Up on
  USD/JPY and Down on EUR/USD whatever the features (the dollar rose during
  its training years); round 1 leaned Down on Tuesdays for EUR/USD and
  Thursdays for USD/JPY. Those are the kind of patterns that exist in any
  two-year sample and mean nothing.

Does it make sense? A short reversal and a longer trend are the two most
common shapes in price data, and a dollar move carrying across pairs is
real economics. But the model could only turn them into about 1 pip a
trade, and the rules it found shifted from round to round, which is what a
weak, unstable signal looks like. The margin filter did not help: the
62%-sure settings traded less but not better.

### Track B: two original families

Both start from one measurement at the decision hour: each pair's move
since 00:00 UTC in the dollar's direction, as a fraction of its own 20-day
average daily range. Three pairs give a reading of whether the dollar itself
moved. Settings per family (12 variants): decision hour 08:00 or 10:00, size
k = 0.2, 0.3 or 0.45 daily ranges, stop none or half a daily range. Exit
20:00.

- **Family 11, dollar-wide move, catch-up.** If all three pairs point the
  same way for the dollar and the average move is at least k, buy the dollar
  on the two pairs that moved least. Reason: a move on all three pairs at
  once is a dollar flow, not pair noise; flows take hours to work through,
  and the laggards have the most left.
- **Family 12, lone mover reverts.** If one pair moved at least k while the
  other two together show the dollar roughly flat (within k/3), trade that
  pair back toward where it started. Reason: a move on one pair with no
  dollar move behind it is most often a single-currency order or thin-market
  push that gets absorbed and partly undone.

| Track B | Variants | Trades | Net (measured) | Worst fall | Win rate | Avg win / loss (USD) | Profit factor | Monte Carlo p95 fall | Kill switch | Net at 1.5× (kill) | Net at MT5 | Beat coin-toss runs (p99 bar) | Result |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 11. Dollar-wide catch-up, 1h | 12 | 234 | **−27.28** | 31% | 50% | 0.66 / −0.88 | 0.74 | 37% | 0 | −32.84 (0) | −16.32 | 57% (bar +0.91) | Fail |
| 12. Lone mover reverts, 1h | 12 | 92 | **−7.72** | 9% | 40% | 0.94 / −0.78 | 0.82 | 18% | 0 | −10.88 (0) | −2.59 | {{F12_LUCK}} | Fail |

| Track B | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| 11. Dollar-wide catch-up | −9.09 | −3.21 | −14.98 |
| 12. Lone mover reverts | +2.62 | +0.67 | −11.01 |

In plain language:
- **Family 11 lost before costs** (−9.5 USD gross, −2.6 pips a trade). Every
  one of its 12 variants lost over the full period, and it lost in 4 of the
  5 half-years. When all three pairs had already moved for the dollar by
  08:00 or 10:00, the laggards did not catch up; on average they drifted
  back a little. The 500 coin-toss runs on its own signal days lost
  28.9 USD on average; family 11 landed right in the middle of them (beat
  57%), so its direction rule carried no information at all.
- **Family 12 barely traded.** The "others flat" condition is rare: 92
  trades in 30 months, 60 of them on USD/JPY, which lost 11 USD; the EUR
  and GBP legs made a few USD on 32 trades. Before costs it broke even
  (+0.4 USD). It fails on trade count whatever else happens, and its stop
  was hit on 21 of 92 trades. {{F12_LUCK_TEXT}}
- Both families reached the test with every walk-forward training score
  negative in the early rounds: the harness picked the least bad setting
  each time, as the rules require, and the test confirmed there was nothing
  to pick.

### What round 4 adds to the conclusion

- A flexible model with 14–23 features, retrained every six months, found
  about 1 pip a trade of real direction skill on these pairs at this
  horizon. That is the clearest measurement of the available edge the
  program has produced: it is not zero, and it is a quarter of the cost.
- Reading the three pairs together did not help. The dollar-wide
  continuation idea lost before costs; the lone-mover reversal was too rare
  to judge and lost on the pair it mostly traded.
- With 234 variants and 16 walk-forward results (section 4), one chance pass
  would have been likely by now at the old p95 bar; the p99 bar and the
  "not fake" checks were there to catch it, and nothing came close.

## 4. How likely is a pass to be luck?

- Over the program: 234 variants, giving **16 walk-forward results** (one
  per sub-grid; the ML track counts as one, with its 24 settings competing
  inside each round).
- At the p95 bar used in round 1 (8 results), the chance that at least
  one passes by luck alone is about 1 in 3.
- From round 2 on, the bar was p99 of 500 random runs, plus the four "not
  fake" checks, which cut that chance a lot. Round 4 tightened the random
  runs further (the candidate's own signal days, coin-toss direction).
- None passed even the basic CLAUDE.md rules together with the luck check.
  The closest on the luck check alone were the London breakout (round 1,
  95.5% at the old p95 bar, a net loss) and the round 4 model (80% at the
  p99 bar, a net loss).
- So the honest conclusion is: **in 2023–2026, none of these ideas beat
  Deriv's Multiplier costs on EUR/USD, GBP/USD and USD/JPY.**

## 5. Final result, holdout and what could change it

- **Final candidates: none, after four rounds. The holdout was not used.**
  It stays untouched and valid. The five round-4 models are saved frozen in
  `research/phase4/a1_ml_day/models/` for the record; none is a candidate.
- **Re-check after 5 Nov** (`cost_by_hour.json`): nothing to re-run. Even
  if the cheap window moves, no result is near a pass. The losses are
  about the size of the commission, so it would have to fall a lot, not
  shift by an hour.
- **MT5 decision note:** not needed. CLAUDE.md asks for one only if a
  strategy passes at MT5 costs. None passed the full rules there either.
  The nearest were trend pullback 4h (+11 USD) and EUR vs GBP (+8 USD),
  and both fail the luck and robustness checks at any cost.

**Recommendation:**
- Do not trade any of these strategies, on demo or real money.
- Do not move to Phase 5/6 with them.
- Running the bot now would mostly pay commission to Deriv.

What could change the picture. Every option needs your approval: it changes
data, pairs, the network list or CLAUDE.md. I have not done any of them.

1. **More history (Dukascopy before 2021-10-27).**
   - **Gain:** longer walk-forward and more out-of-sample trades. This is
     the only way to judge low-frequency ideas like family 9 fairly: 122
     trades is too few to tell an edge from luck.
   - **Cost:** about 5 MB of compressed data per pair-year (the current
     4.5 years are 22–24 MB per pair). The repo is about 75 MB on GitHub
     now, so 3 more years for all three pairs (about 45 MB) stays under
     150 MB.
   - **Caveat:** re-testing family 9 on longer data counts as new
     variants, and would be judged at p99.
2. **More pairs, especially crosses such as EUR/GBP traded directly.**
   - A direct cross would turn family 9's two legs into one trade with one
     commission, which roughly halves its cost.
   - Each new pair first needs quotes-only cost sampling, and its own
     commission rate may be higher.
3. **A news filter.**
   - Skipping big releases removes the hours where the commission jumps
     and prices gap past stops.
   - Needs an economic-calendar source (a network change).
4. **The Phase 6 weekend test.**
   - If weekend holding is safe and cheap, trend ideas lose the forced
     Friday close, which also kills Friday daily signals under the 12-hour
     wait.
   - That needs the test, and a CLAUDE.md change, first.
5. **Accept the result.**
   - Ten families covering the standard 1h–daily ideas found no edge large
     enough to pay about 3 pips a trade.
   - Stopping here is a legitimate outcome. It saves the starting capital,
     which a bot running these strategies would most likely lose.

**My view:**
- **Options 1 and 2, aimed narrowly at the EUR vs GBP idea,** are the only
  ones with a specific reason to hope. Even so, the odds are modest.
- **If you'd rather not spend more time on this, option 5 is a sound
  answer.**

## Files

| What | Where |
|---|---|
| Every variant tried | `research/log.md` (Phase 4 section) |
| Walk-forward picks, grid, luck runs, pass checks per strategy | `research/phase4/<name>/` |
| Out-of-sample reports (measured, 1.5×, MT5, Monte Carlo) | `reports/backtests/phase4_<name>_oos/` |
| Strategy code (shared with the live bot) | `src/fxbot/strategies/families.py` (families 1–12), `src/fxbot/strategies/ml_day.py` (round 4 model strategy) |
| Harness | `src/fxbot/backtest/research.py`, `scripts/research_family.py`, `scripts/research_ml.py` (round 4 track A) |
| Round 4 tests (look-ahead, train-only scaling, seeds, frozen models, families 11–12, signal-days luck check) | `tests/test_round4.py` |

Rebuild any family:
```
python scripts/research_family.py grid --family f1
python scripts/research_family.py oos --family f1
python scripts/research_family.py luck --family f1
python scripts/research_family.py summary --family f1
```
Each stage resumes if stopped. The round 4 model strategy:
```
OMP_NUM_THREADS=1 python scripts/research_ml.py table    # then fit, oos, luck, summary
```
