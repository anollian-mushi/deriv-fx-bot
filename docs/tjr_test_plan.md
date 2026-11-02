# TJR test, Step 2: the plan, fixed before any run

Status (2 Nov 2026): **approved by the owner in full; written and coded; nothing has been run on
market data.** On the owner's instruction, the runs start only after **both** of these have
updated the cost tables:

- Monday 2 Nov: the new-pairs cost decision (`research/incubator_prescreen/pairs2_cost_rule.json`
  and the new pairs' commission table);
- Thursday 5 Nov: the clock-change re-check of `research/phase2/cost_by_hour.json`. The New York
  session (11:00-16:00 UTC) overlaps the hours that file currently marks as raised.

The start is scheduled for **Friday 6 Nov 2026**. Before starting, `python scripts/tjr_test.py
preflight` checks that both are in place. The research log is also read to confirm both are
final. If either is missing, nothing starts. The rules are in `docs/tjr_rules.md` (approved 2 Nov
2026). The results will go in `reports/tjr_test.md`.

Everything below is decided now, before any result is seen. Nothing in it may be changed
because of a result.

## 1. Data, costs and limits

- **Data:** before 2026-10-31 only. Dukascopy 1m to 2026-04-27, Deriv 1m from 2026-04-28 to
  2026-10-30. `fxbot.backtest.prescreen` cannot read the untouched period; it raises an
  error first.
- **Pairs:** EUR/USD, GBP/USD, USD/JPY, plus every new pair kept by Monday's cost check
  (`research/incubator_prescreen/pairs2_cost_rule.json`). Owner's decision, made before any
  result: if GBP/JPY fails that check, the test still runs on all pairs that passed. The
  report then says GBP/JPY was dropped for cost; the same applies to any other new pair that
  failed. Results are reported per pair.
- **Commission:** the rate for the UTC hour each trade opens. The majors' rates come from
  `research/phase2/cost_by_hour.json` and the new pairs' from
  `research/phase2/cost_by_hour_pairs2.json`. `setup` records both files' SHA-256, and every
  later stage stops if either file changes, so no result mixes two tables.
- **Slippage:** 0.5 pip on entry, 1 pip on stop exits (project standard).
- **Every CLAUDE.md hard limit** goes through the risk module. That includes the live cost
  gate (skip if the hour's rate is above 1.5x the pair's base rate). Start at 100 USD. The
  kill switch is recorded (observe mode): if it fires even once, the variant fails.
- **Owner's cost rule:** skip a trade whose stop is closer than 4x its cost per trade
  (commission at the hour's measured rate + 0.5 pip). It is judged at the measured rate, so
  the 1.5x run keeps exactly the same trades.
- **1.5x run:** every variant also runs at 1.5x the measured commission.
- **MT5 comparison (information only):** the same trades re-priced at Deriv MT5 micro spreads,
  majors only (the project has MT5 specs for the majors only). No swap applies, because every
  trade closes the same day.

## 2. Walk-forward (the incubator pre-screen method)

Same rounds as the pre-screen. 24 months of training, 6 months of testing, stepped by 6
months, six rounds. The out-of-sample period is 2023-10-27 to 2026-10-26 (776 trading days).

1. Each grid variant runs once over 2021-10-27 to 2026-10-30.
2. In each round, the variant with the best net / max drawdown on that round's *training*
   window is picked. The test window is never looked at.
3. The picks are stitched into one out-of-sample run: measured commission, then 1.5x.

## 3. The 30 variants

**8 ideas = 4 entry models x 2 execution timeframes.** In each idea the walk-forward chooses
only **n** (6 or 12 execution candles). That is the time allowed for the break after the
sweep, and for the retracement after the break.

| # | Variant | Strategy (fed / execution / confirmation) | Model | n | Break-even | Confirmation |
|---|---|---|---|---|---|---|
| 1-2 | m1_5m v0, v1 | TJR5m (1m / 5m / -) | 1 Foundation | 6, 12 | off | - |
| 3-4 | m2_5m v0, v1 | TJR5m (1m / 5m / 1m) | 2 Order block | 6, 12 | off | 1m sweep + break |
| 5-6 | m3_5m v0, v1 | TJR5m (1m / 5m / 1m) | 3 FVG | 6, 12 | off | 1m sweep + break |
| 7-8 | m4_5m v0, v1 | TJR5m (1m / 5m / 1m) | 4 Sniper | 6, 12 | off | 1m sweep + break |
| 9-10 | m1_15m v0, v1 | TJR15m (5m / 15m / -) | 1 | 6, 12 | off | - |
| 11-12 | m2_15m v0, v1 | TJR15m (5m / 15m / 5m) | 2 | 6, 12 | off | 5m sweep + break |
| 13-14 | m3_15m v0, v1 | TJR15m (5m / 15m / 5m) | 3 | 6, 12 | off | 5m sweep + break |
| 15-16 | m4_15m v0, v1 | TJR15m (5m / 15m / 5m) | 4 | 6, 12 | off | 5m sweep + break |
| 17-24 | m{1-4}_{5m,15m}_be | the idea's walk-forward schedule | same | as picked | **on** (owner's C23 variant) | same |
| 25-30 | m{2-4}_{5m,15m}_touch | the idea's walk-forward schedule | same | as picked | off | **touch-and-close** (labelled C18 alternative) |

Settings per variant: model, n, breakeven, confirm. That is 4, within the limit of 5. The
execution timeframe is the strategy class. Everything else is fixed by `docs/tjr_rules.md`:
session windows, news windows, the 1-pip stop buffer, target rules, x200/x100, and the 17:55
UTC flat time.

## 4. Luck check

As in the pre-screen: **200 coin-toss runs** on the candidate's own out-of-sample signals.
They use the same pairs, minutes, stops, targets, multiplier and stop rule, with a random
direction. The candidate must beat the **median** of those runs. As in the pre-screen, it is
not run for a variant whose before-cost result is not above zero, because the answer could
not change the verdict.

To save time, a coin-toss run only replays 05:00-18:00 UTC on days that had a signal. Every
trade is closed by 17:55 UTC on its opening day, so the other hours cannot change the result.
This was checked on synthetic data: replaying a candidate's own signals with their own
directions reproduces its trades exactly.

The 95th percentile is reported next to the median. Thirty variants are being tried, so
beating the median alone is weak evidence. The incubator's graduation rule (1 - 0.05/N
percentile on forward data) remains the real test for anything registered.

## 5. The 8 checks

A variant passes only if all eight hold:

1. **A written reason** for the edge, and how it differs from ideas tested before (the report
   gives it per model).
2. **Average move at least 3x the average cost** per trade (`move_vs_cost`).
3. **At least 1.5 trades per trading day** across all pairs. Owner: this may be waived only if
   the variant averages at least **0.3** trades a day.
4. **Executable under every CLAUDE.md rule.** Every trade goes through the risk module. The
   5m/15m timeframes are the owner's research exception. Before any live use, the live bot
   would also need the stop-loss update.
5. **At most 5 settings**, chosen before testing (here 4).
6. **Pre-screen:** gross (before costs) above zero **and** net above the median of the 200
   coin-toss runs.
7. **No look-ahead.** The engine and strategy tests include a "change the future, the past
   signals stay the same" test (`tests/test_tjr.py`).
8. **Not a minor variant** of a registered candidate. None of the five registered
   candidates trades sweeps on 5m/15m; the nearest earlier idea, `turtle_soup`, was not
   registered.

Also reported, as CLAUDE.md asks, but not part of the 8 checks: profit after costs on at least
2 of the 3 majors, and 200+ out-of-sample trades.

## 6. What the report will show

For every variant:

- trades and trades a day;
- net return at measured and 1.5x commission;
- max drawdown, win rate, average win and loss, profit factor, and Monte Carlo drawdowns
  (p50/p95/p99);
- **before-cost edge in pips per trade** (all pairs and per pair);
- **cost as a share of risk** (cost per trade / stop distance; the 4x rule caps it at 25%);
- per-pair results;
- how many setups each rule removed (sweeps outside the session, against the bias, no
  break in time, cost floor, news, and so on);
- how often the break-even stop moved;
- coin-toss result;
- the MT5 comparison for the majors.

The report will say plainly if nothing passes, and whether the result would pass at MT5-level
costs. If something passes every check, the report proposes registering it in the incubator,
and nothing is registered until the owner approves.

## 7. How to run it (after the cost re-check)

Each command stops before about 9 minutes and saves its progress. Run it again until it
prints "0 left".

```bash
python scripts/tjr_test.py preflight        # both cost inputs final? (exit 2 if not)
python scripts/tjr_test.py setup --costs-rechecked
python scripts/tjr_test.py grid
python scripts/tjr_test.py oos
python scripts/tjr_test.py luck
python scripts/tjr_test.py summary
```

Rough cost, from synthetic-data timing: one 5-year run on 9 pairs takes about 7-10 minutes
fed 1m candles (5m execution) and about 3 minutes fed 5m candles (15m execution).

| Stage | Estimate |
|---|---|
| Grid | about 1 hour (6-8 commands) |
| Out of sample | about 1.5 hours (10-12 commands) |
| Luck | about 25 minutes per variant with a positive before-cost result |

Runs fed 1m candles use about 3 GB of memory each, so the runner uses 2 workers.
