# TJR method test: does it have an edge at Deriv's costs?

Run 6 Nov 2026 on branch `tjr-smc`. Rules: `docs/tjr_rules.md` (approved 2 Nov 2026). Plan,
variants and checks: `docs/tjr_test_plan.md` (approved 2 Nov 2026, fixed before any run).
Raw results: `research/tjr/`.

## The short answer

**No variant passes. Nothing is proposed for the incubator.**

- **Model 1** (sweep + break of structure, enter on the break) is the only model that trades
  often enough to judge.
  - It has a small real edge before costs: about **2.8 pips a trade** on 5m execution and
    0.8 on 15m.
  - Deriv's cost is about **4.2 pips a trade**, larger than that edge. So it **loses 26-46% of
    the account** over three years out of sample.
- **Models 2, 3 and 4** (wait for price to come back to the order block or FVG and confirm on
  1m/5m, as the notes say) almost never complete: **0 to 3 trades in three years across nine
  pairs**. There is nothing to judge.
- **At MT5-level costs** the model 1 trades on the three majors would roughly break even
  (+14 to +18 USD over three years). Almost all of that comes from EUR/USD. I would not call
  that a pass either (details in section 5).

One result needs a plain word: **model 1 on 5m formally clears the owner's eight pre-screen
checks**. It averages 0.53 trades a day, above the 0.3 waiver line. It is profitable before
costs, and it beats the middle of the coin-toss runs. But it **fails the CLAUDE.md pass rule**:
after costs it is profitable on only 1 of the 3 majors (EUR/USD) and loses money overall. The
incubator would also end it. Its graduation rule needs a profit after costs, at the measured
commission and at 1.5x. Here three years of history show a 31% loss and a 48% loss. So I am
not proposing it. If you see it differently, it is your call.

## 1. What was tested

- **Pairs (9):** EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, USD/CHF, EUR/GBP, EUR/JPY and
  GBP/JPY. All six new pairs, GBP/JPY included, passed Monday's cost check, so **no pair was
  dropped for cost**.
- **Data:** before 2026-10-31 only. The walk-forward used six rounds, each training on 24
  months and testing the next 6. The out-of-sample period, stitched from the six test
  windows, is **2023-10-27 to 2026-10-26** (776 trading days).
- **Costs:**
  - Deriv's commission at the rate for each trade's opening hour. The majors' rates come from
    the table re-checked after the 1 Nov clock change; the new pairs' from Monday's table.
  - Slippage of 0.5 pip on entry and 1 pip on stop exits.
  - Every trade also re-run at 1.5x the commission.
- **Rules:**
  - Every CLAUDE.md hard limit, starting from 100 USD.
  - The owner's 4x-cost stop rule: skip a trade whose stop is closer than 4x its cost.
  - London and New York session windows, the news windows, US bank holidays, and everything
    closed by 17:55 UTC.
- **30 variants:**
  - 4 entry models x 5m/15m execution, with the walk-forward choosing n (6 or 12 candles):
    16 variants.
  - A break-even version of each model and timeframe: 8.
  - The "touch-and-close" alternative for models 2-4: 6.
- **Luck check:** 200 coin-toss runs per variant. Each takes the variant's own signals (same
  minutes, stops and targets) and tosses a coin for the direction. It was not run where the
  result before costs was not positive, as in the pre-screen.

## 2. Results, out of sample (2023-10-27 to 2026-10-26, from 100 USD)

"Before-cost pips" is the price move each trade captured, before commission and slippage: the
real edge of the signals. "Cost/risk" is the cost per trade divided by the stop distance (the
4x rule caps it at 25%). "Coin toss" is the share of the 200 coin-toss runs this variant beat
after costs; the 95th-percentile coin-toss result is in brackets.

| Variant | Trades (a day) | Before-cost pips a trade | Net / at 1.5x, USD | Max drawdown | Win rate | Avg win / loss, USD | Profit factor | Monte Carlo drawdown p95 | Cost/risk | Coin toss |
|---|---|---|---|---|---|---|---|---|---|---|
| **m1_5m** (model 1, 5m) | 413 (0.53) | **+2.77** | **-30.66 / -47.82** | 33.6% | 42.1% | 1.08 / -0.91 | 0.86 | 49.3% | 17% | 90% (-21.2) |
| m1_5m_be (break-even stop) | 416 (0.54) | +2.93 | -26.12 / -45.21 | 31.4% | 39.2% | 1.17 / -0.86 | 0.88 | 46.2% | 17% | 92% (-20.0) |
| **m1_15m** (model 1, 15m) | 358 (0.46) | +0.84 | **-46.35 / -69.75** | 49.6% | 40.5% | 0.99 / -0.89 | 0.76 | 55.7% | 16% | 72% (-32.6) |
| m1_15m_be | 359 (0.46) | +1.03 | -43.41 / -62.32 | 47.5% | 37.3% | 1.05 / -0.82 | 0.77 | 53.4% | 16% | 79% (-34.5) |
| m2_5m (order block, 1m confirmation) | 3 (0.00) | +22.9 | +1.86 / +1.62 | 1.3% | 33% | 4.30 / -1.22 | 1.76 | 2.4% | 16% | 46% (3.1) |
| m2_5m_be | 3 (0.00) | +22.9 | +1.86 / +1.62 | 1.3% | 33% | 4.30 / -1.22 | 1.76 | 2.4% | 16% | 46% (3.9) |
| m2_5m_touch | 15 (0.02) | +23.7 | +11.63 / +10.47 | 5.0% | 47% | 2.87 / -1.06 | 2.38 | 5.5% | 19% | 84% (15.6) |
| m2_15m (order block, 5m confirmation) | 1 (0.00) | +29.2 | +1.88 / +1.81 | 0% | 100% | 1.88 / - | - | 0% | 22% | 52% (1.9) |
| m2_15m_be | 1 (0.00) | +29.2 | +1.88 / +1.81 | 0% | 100% | 1.88 / - | - | 0% | 22% | 52% (1.9) |
| m2_15m_touch | 11 (0.01) | +9.5 | +0.02 / -0.73 | 4.5% | 27% | 1.94 / -0.73 | 1.00 | 5.2% | 22% | 84% (3.4) |
| m3_5m (FVG, 1m confirmation) | 1 (0.00) | -26.4 | -1.29 / -1.37 | 1.3% | 0% | - / -1.29 | 0 | 1.3% | 18% | not run |
| m3_5m_be | 1 (0.00) | -26.4 | -1.29 / -1.37 | 1.3% | 0% | - / -1.29 | 0 | 1.3% | 18% | not run |
| m3_5m_touch | 5 (0.01) | -2.0 | -1.48 / -1.86 | 2.2% | 40% | 0.82 / -1.04 | 0.53 | 3.1% | 21% | not run |
| m3_15m (FVG, 5m confirmation) | 0 | - | 0 / 0 | - | - | - | - | - | - | not run |
| m3_15m_be | 0 | - | 0 / 0 | - | - | - | - | - | - | not run |
| m3_15m_touch | 4 (0.01) | -5.6 | -1.51 / -1.79 | 3.0% | 25% | 1.58 / -1.03 | 0.51 | 3.0% | 19% | not run |
| m4_5m (sniper, 1m confirmation) | 2 (0.00) | -27.3 | -2.52 / -2.68 | 2.5% | 0% | - / -1.26 | 0 | 2.5% | 17% | not run |
| m4_5m_be | 2 (0.00) | -27.3 | -2.52 / -2.68 | 2.5% | 0% | - / -1.26 | 0 | 2.5% | 17% | not run |
| m4_5m_touch | 9 (0.01) | +20.5 | +4.07 / +3.33 | 5.6% | 44% | 2.83 / -1.45 | 1.56 | 5.7% | 19% | 64% (14.4) |
| m4_15m (sniper, 5m confirmation) | 1 (0.00) | +29.2 | +1.88 / +1.81 | 0% | 100% | 1.88 / - | - | 0% | 22% | 52% (1.9) |
| m4_15m_be | 1 (0.00) | +29.2 | +1.88 / +1.81 | 0% | 100% | 1.88 / - | - | 0% | 22% | 52% (1.9) |
| m4_15m_touch | 12 (0.02) | +6.8 | -1.85 / -2.67 | 6.3% | 25% | 1.94 / -0.85 | 0.76 | 6.6% | 22% | 52% (4.7) |

The kill switch never fired out of sample. In the full five-year runs (used only for
choosing n), the model 1 variants fired it once or twice. A Monte Carlo drawdown of 46-56%
(95th percentile) also says it would come close in the incubator.

The walk-forward chose n = 12 in every round for m1_5m. For m1_15m it chose n = 6 in five
rounds and 12 in one.

## 3. Model 1 per pair (before-cost pips a trade; net after costs, USD; trades)

| Pair | m1_5m before costs | m1_5m net | m1_15m before costs | m1_15m net |
|---|---|---|---|---|
| EUR/USD | **+10.0** | **+16.99** (72) | **+8.7** | **+10.85** (58) |
| GBP/USD | +1.1 | -6.95 (77) | +1.2 | -4.54 (60) |
| USD/JPY | -2.2 | -14.60 (58) | +0.4 | -2.12 (48) |
| AUD/USD | +2.6 | -4.50 (27) | -1.9 | -12.18 (25) |
| USD/CAD | -3.6 | -8.92 (33) | -7.1 | -11.61 (32) |
| USD/CHF | +0.9 | -4.18 (21) | -5.1 | -10.79 (23) |
| EUR/GBP | +2.5 | -1.73 (35) | -0.0 | -9.33 (49) |
| EUR/JPY | +0.7 | -6.93 (40) | +1.6 | -1.27 (22) |
| GBP/JPY | **+7.7** | +0.16 (50) | +1.6 | -5.36 (41) |

Only EUR/USD makes money after costs on its own, with GBP/JPY about level on 5m. That is 1 of
the 3 majors, so the CLAUDE.md rule (profitable after costs on at least 2 of the 3) fails. Before
costs, m1_5m was positive in 5 of the 6 test windows. After costs it was negative in 5 of 6.

## 4. Why the trades are rare: where the setups were lost

**Model 1 on 5m, nine pairs, three years out of sample:**

| Step | Count |
|---|---|
| 30m candles that swept a prominent high or low and closed back inside | 32,843 |
| ... outside the London and New York windows | -20,276 |
| ... against the daily and 4h bias (or daily and 4h disagreed) | -8,614 |
| ... both sides swept, pair already traded that session, or a setup already waiting | -484 |
| **Setups** | **3,469** |
| ... price went back through the sweep wick (the stop level) before a break | -1,738 |
| ... no break of structure within n candles | -473 |
| **Breaks of structure** | **1,258** |
| ... break came after the session window, in a news window, or on a US holiday | -273 |
| ... stop too wide for x100, bias changed, or the pair already had a trade | -19 |
| **Orders sent** | **966** |
| ... stop closer than 4x the cost per trade (owner's cost rule) | -406 |
| ... could not fill within 2 minutes (no commission rate for that hour, or 2 trades already open) | -147 |
| **Trades** | **413** |

The 4x-cost rule removed 42% of the orders. Without it the remaining trades would have had
even tighter stops, where Deriv's cost is a bigger share of the risk.

**Models 2-4: the confirmation inside the zone almost never completes.** For example, the
order block model on 5m:

- 1,137 breaks of structure;
- price came back into the order block 434 times;
- a fresh 1m sweep inside it happened 423 times;
- a 1m break of structure followed 105 times;
- 85 of those were not in premium/discount;
- that left 17 orders, and 11 had a stop under the cost floor;
- **3 trades.**

The FVG and sniper models end the same way. The touch-and-close alternative trades a bit more
(4-15 trades), but 0.02 a day is far below the 0.3 waiver line, so those results can't be
judged either. The small positive numbers on a few of them come from 1-15 trades and say
nothing about an edge.

**Break-even stop:** it moved the stop in 164 of 416 trades (m1_5m_be). It improved the
result a little (-26 instead of -31 USD), but not enough to change the verdict.

## 5. The checks

| Check | m1_5m | m1_5m_be | m1_15m | All other variants |
|---|---|---|---|---|
| 1 Written reason for the edge | yes (below) | yes | yes | yes |
| 2 Average move at least 3x the cost | yes (27.1 vs 4.2 pips, 6.4x) | yes (5.9x) | yes (6.3x) | yes where any trades |
| 3 At least 1.5 trades a day (waivable only at 0.3 or more) | 0.53: **fails, waivable** | 0.54: fails, waivable | 0.46: fails, waivable | 0.00-0.02: **fails, not waivable** |
| 4 Executable under CLAUDE.md | yes, in the backtest; the live bot does not yet run 1m/5m candles | also needs the stop update in the live bot | as m1_5m | - |
| 5 At most 5 settings | yes (4) | yes | yes | yes |
| 6 Profitable before costs and beats the coin-toss median | yes (+35.87 USD; beats 90%) | yes (beats 92%) | yes (+9.08; beats 72%) | fails or too few trades |
| 7 No look-ahead | yes (tests) | yes | yes | yes |
| 8 Not a minor variant of a candidate | yes | yes | yes | yes |
| CLAUDE.md: profitable after costs on 2 of 3 majors, 200+ trades | **fails** (1 of 3) | **fails** | **fails** | fails |
| Net profit after costs | **-30.66 USD** | -26.12 | -46.35 | - |

The coin-toss check is weak here. Thirty variants were tried, so some would beat the median by
chance. None of the model 1 variants beats the 95th percentile (m1_5m: -30.66 against
-21.21).

**Check 1, the reason (and why it is not enough).** Model 1 trades the sweep only in the
direction of the daily and 4h trend, and only after a candle closes past the last swing.
That is a continuation idea, and earlier rounds found mild continuation in these pairs. The
before-cost result agrees: about +2.8 pips a trade on 5m. But a TJR stop sits beyond the 30m
sweep wick, about 27 pips on average. The edge per trade is about a tenth of the risk, and
Deriv takes about 4.2 pips, so the cost is larger than the edge.

**At MT5-level costs (comparison only, majors only):** the same model 1 trades, re-priced at
Deriv MT5 micro spreads. No swap applies, because every trade closes the same day.

| | m1_5m | m1_15m |
|---|---|---|
| EUR/USD | +23.35 | +15.59 |
| GBP/USD | -1.23 | -0.49 |
| USD/JPY | -8.41 | +2.62 |
| **Total, 3 majors** | **+13.71** (Deriv: -4.56) | **+17.72** (Deriv: +4.19) |

So at MT5 costs the majors roughly break even to slightly positive over three years. But:

- the 5m version is still profitable on only 1 of 3 majors;
- the 15m version reaches 2 of 3 only through +2.62 USD on USD/JPY, and its signals beat
  only 72% of coin tosses.

The project has no MT5 cost figures for the six new pairs. **My answer: not a convincing pass
at MT5 costs either.**

## 6. Things to know about this run

- **A runner fault, found and fixed before these results.** My synthetic-data test of the
  runner on 2 Nov left resumable engine files under `state/backtest/`. Today, 4 grid runs and
  10 out-of-sample runs (the m1_15m and m3_15m ones) resumed those files instead of running.
  The tell was that m1_15m showed 1,188 sweeps where every other variant showed about 33,000.
  The affected results were deleted and rerun. The runner now keeps its engine files under
  `state/tjr/engine/`, named for this setup, so this cannot repeat. All numbers above come
  from the reruns.
- **The coin-toss runs replay only the hours that matter:** 05:00-18:00 UTC on days with a
  signal, and a wake list of minutes. Both were checked to give identical trades to a full
  replay.
- **No commission rate for the new pairs at 14:00-14:59 UTC.** Monday's sample for that hour
  arrived late, so the backtest could not open new-pair trades in that hour; 134 model 1 5m
  orders were dropped. That is too few to change the result: the average model 1 trade loses
  money.
- **5m and 15m execution** was an owner-approved exception for this research only. Nothing
  here changes CLAUDE.md.

## 7. What I would do next

Nothing for the incubator from this test. Two lessons:

1. The useful part of TJR's method on our data is the **trend filter plus break
   confirmation**, not the order block, FVG or premium/discount entries. Those almost never
   trigger once the notes' full chain is applied.
2. The edge is real but about **3 pips a trade**, below Deriv's cost of about 4. The same
   pattern turned up earlier with `ny_cut_breakout`: a small real edge and a larger cost. A
   TJR-style idea could only work on Deriv with much wider targets per trade, which would
   mean a different, slower method. I have not tested that.
