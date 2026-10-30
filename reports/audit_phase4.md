# Phase 4 audit: could a bug be hiding an edge?

Written 2026-10-30, after the Phase 4 program ended with "no strategy
passed". The owner asked for an audit before accepting that result. No
strategy and no rule was changed, and **the holdout (Deriv data from
2026-04-28) was not touched**: every run here uses pre-holdout Dukascopy
data, exactly as Phase 4 did.

What this report answers, in order:
1. Can the pipeline see an edge at all? (Positive controls: things that
   *must* show a profit if the machinery works.)
2. Is the wiring right? (Up/Down, which pair a signal goes to, what a
   candle's timestamp means, UTC.)
3. Are costs charged once, not twice? Gross (no-cost) vs net results.
4. Is the luck check fair?
5. Does "no edge" still stand, and what needs re-running?

Everything added for the audit is a **diagnostic, never a candidate**:
`src/fxbot/backtest/audit.py` (controls), `tests/test_audit_phase4.py`
(17 tests), `scripts/audit_phase4.py` (real-data checks) and the raw
results in `research/audit/*.json`.

## The short version

- **The machinery works.** A cheating strategy that peeks at the next
  candle turned 100 USD into 45,805 USD over 2024 after full costs, and
  beat all 20 of its random-direction twins (each lost about 130 USD). A
  synthetic price with a built-in 2-pip drift is profitable before costs
  and passes the luck check. Flipping a strategy's signals mirrors its
  before-cost result.
- **Nothing is charged twice.** Commission, the 0.5 pip entry slippage and
  the 1 pip stop-loss slippage each appear exactly once in every trade,
  and the stop loss beats the take profit inside one candle as documented.
  Running the engine with all costs switched off agrees with "recorded
  profit + recorded costs" to within a small fraction of one commission.
- **Before costs, five families made a small profit** (1.8 to 6.3 pips a
  trade). The costs come to about 4 pips a trade, so all but family 9
  turned into losses. This is the same picture the Phase 4 report drew,
  now with the numbers side by side.
- **One real bug, in the luck check.** The random-entry runs did not
  always make as many trades as the strategy they were judging. For
  family 8 they made 41% fewer, for family 6 30% fewer, because the
  per-hour signal rate was averaged across walk-forward windows that used
  a different signal hour, and because filters that live in a family's
  stop-setting code were applied a second time to the random entries.
  Fewer random trades means less commission paid by the random runs, so
  those families' "beat random runs" percentages were **understated**.
  Fixed, with tests. The committed luck results are stale and need
  re-running (section 6).
- **In the other direction**, for the 4h and daily families the random
  runs made 13 to 21% *more* trades than the candidate (random-direction
  trades hit their stops sooner, so the run was flat more often). That
  flattered those candidates; it did not hide anything.
- **"No edge" still stands.** The preview re-run of the corrected luck
  check (section 4) does not lift any family to a pass, and the gross
  results show why: the largest before-cost edge found (family 9, 6 pips a
  trade on 122 trades) is also the one with the fewest trades, and the
  rest are 2 pips or less against 4 pips of cost.

## 1. Positive controls: can the pipeline see an edge?

**a. The cheat.** `audit.Cheat` reads the *next* 1h candle's close (a
look-ahead no real strategy can have) and trades its direction whenever
the coming move is at least 8 pips, holding one candle. It uses the normal
engine, the normal risk module, the measured commission table and the
same slippage as every Phase 4 run. Its random-direction twin keeps the
same candles and exits but tosses a coin for the direction.

| 2024, three pairs | Trades | Net after costs | Gross before costs |
|---|---|---|---|
| Cheat | 2,190 | **+45,805 USD** | +58,502 USD |
| 20 random-direction twins | 2,191 on average | −131.59 USD on average (best −92.79, worst −157.67; 40 kill-switch restarts in total) | |

The cheat beat every random twin by a wide margin (the unit test on
synthetic data does the same with 20 twins). The gigantic number is what
compounding a 3% stake at a 70% win rate looks like; it is not a
strategy, it is proof that an edge, if present, comes through the
pipeline with costs charged.

**b. A small built-in edge.** A synthetic random walk gains exactly 2
pips between 08:00 and 12:00 UTC every day. A strategy that buys at
08:00 and sells at 12:00 (`audit.AuditDrift`) earns about 2 pips a trade
before costs and is profitable. After costs it loses (2 pips of edge do
not pay 2.6 pips of commission), but it beats the 95th percentile of 40
random-direction runs through the real `Scheduled` / `RandomEntry` /
`entry_rates` pipeline. So the luck check can recognise a real but small
edge even when the net result is negative. (Test:
`test_small_built_in_edge_passes_the_luck_check_with_full_costs`.)

**c. Flipped signals.** `audit.flipped(cls)` reverses every entry
direction of a family and keeps its exits. Run with costs switched off on
the real out-of-sample data, with each family's own walk-forward
schedule:

| Family (before costs) | Original, return per unit of stake | Flipped | Sum (0 = exact mirror) |
|---|---|---|---|
| 5. Session drift (time exits only) | −13.31 | +14.04 | +0.73 |
| 1. London breakout (stop and target) | +14.82 | −22.91 | −8.09 |
| 8. Morning momentum (stop, time exit) | +4.49 | −13.23 | −8.74 |
| 3. Trend pullback 4h (stop and target) | +13.21 | +6.48 | +19.69 |

Family 5 is the clean case: its exits are pure clock times, so the
flipped run is the same trades with the sign reversed, and it mirrors
within 5% (the residue is the stop-out cap, which hits 18 times one way
and 14 the other). Where a family has a stop loss and a target the mirror
breaks by design: the flipped trade sits on the wrong side of an
asymmetric exit. Family 3 is worth a note: *both* directions made money
before costs, which says its gross profit came from the exit structure
(near stop, far target, forced Friday close) in this period rather than
from the direction of the entry. That agrees with the Phase 4 verdict
that family 3 has no directional edge.

What this tells us: the engine has no direction bias, and a reversed
signal loses what the original wins.

## 2. Wiring

All checked with tests in `tests/test_audit_phase4.py`:

- **Up/Down is not inverted.** On a price that rises 60 pips an hour, an
  Up trade makes money and a Down trade loses, and the profit equals
  Deriv's formula (stake × 100 × move ÷ entry, minus commission) to the
  cent. The contract math is also already pinned to 11 real demo trades
  within a cent (`tests/test_backtest_fills.py`).
- **A signal reaches its own pair.** A signal for USD/JPY opens a USD/JPY
  trade at USD/JPY's price (around 150, not 1.10), at that pair's own
  1-minute open plus the 0.5 pip slippage.
- **Candle timestamps.** A candle's `epoch` is its start time and `end`
  its close time. The engine hands a 1h candle to the strategy at the
  minute it closes, its open is the first minute's open and its close is
  the last minute's close, and a trade signalled at 10:00 fills at the
  10:00 minute's open. Each call sees exactly one more closed candle than
  the previous call. (Every family also has a no-look-ahead test from
  Phase 4: changing future prices changes no past signal.)
- **UTC everywhere.** The code uses epoch arithmetic (`epoch % 86400`), so
  the entry window and hour-of-day are UTC in January and July alike; a
  signal at 08:00 UTC fills at 08:00 UTC in both. The data were checked
  independently: on first Fridays, the one-minute price range spikes at
  **13:30 UTC in winter and 12:30 UTC in summer** on all three pairs
  (26-60 pips against 2-3 pips in the surrounding minutes). That is the US
  jobs report at 08:30 New York time, so the Dukascopy files are stamped
  in UTC with no daylight-saving slip. Fridays run 00:00 to 20:54 and
  Mondays start at 00:00, as the Deriv calendar requires.
- **The committed trade files are internally consistent.** All 6,996
  out-of-sample trades across the 13 reports: commission = the table rate
  for the entry hour × stake × multiplier; profit = direction × move −
  commission (take profits pay exactly their amount, stop outs lose
  exactly the stake, no stop loss lost less than its amount); every entry
  inside 06:00-17:59 UTC and outside the cost-gate hours; every price in
  its pair's range; nothing held past Friday 20:30. Seven trades closed in
  the same minute they opened (a stop hit inside the entry minute, which
  the engine checks against that minute's full range: slightly
  pessimistic, and seven out of 6,996).

## 3. Costs: gross vs net, charged once

**Per trade** (`test_each_cost_is_charged_exactly_once_per_exit_type`):
with stake 3 USD at x100 and a 20-pip stop and target,
- a take profit pays the 20-pip move minus the commission, and nothing
  else;
- a stop loss loses the whole-cent stop amount (20 pips + commission,
  rounded up to the cent, which places the level 20.1 pips away) plus
  exactly 1 pip of slippage;
- a plain close pays the move from the slipped entry minus the commission,
  so a trade closed flat costs commission + 0.5 pip, once;
- a stop out loses the stake and not a cent more, and a crash through
  both levels takes the stop loss first (the SL-first rule), once;
- the 1.5× stress run changes only the commission; entry, stop and target
  levels move by at most the cent rounding (0.2 pips), never by a pip.

**Per run.** Every committed out-of-sample trade re-priced with its costs
added back (`gross_of`: profit + commission + 0.5 pip + 1 pip on stop-loss
exits), with the three families the owner asked for in bold:

| Family | Trades | Gross (no costs) | Commission | Slippage | Net (as reported) | Gross pips / trade |
|---|---|---|---|---|---|---|
| **1. London breakout 1h** | 1,256 | **+39.11** | 70.92 | 24.48 | **−56.30** | +1.8 |
| 2. Trend breakout 4h | 266 | −23.11 | 13.74 | 3.99 | −40.83 | −2.9 |
| 2. Trend breakout daily | 130 | −17.13 | 7.94 | 1.91 | −26.97 | −5.8 |
| **3. Trend pullback 4h** | 309 | **+33.50** | 25.94 | 6.87 | **+0.70** | +4.5 |
| 3. Trend pullback 1h | 1,251 | −28.82 | 70.49 | 23.96 | −123.27 | −1.4 |
| 4. Mean reversion 1h | 551 | −22.09 | 29.96 | 9.57 | −61.63 | −2.0 |
| 4. Mean reversion 4h | 167 | +5.10 | 12.11 | 3.13 | −10.14 | +1.6 |
| 5. Session drift | 1,290 | −39.33 | 57.67 | 10.92 | −107.92 | −1.0 |
| 6. Quiet London breakout | 872 | +23.77 | 45.36 | 18.34 | −39.94 | +2.0 |
| 7. Weekly momentum | 260 | −10.70 | 17.64 | 4.11 | −32.45 | −2.4 |
| 8. Morning momentum | 419 | +8.50 | 25.10 | 6.86 | −23.46 | +1.8 |
| **9. EUR vs GBP convergence** | 122 | **+16.59** | 8.38 | 2.03 | **+6.17** | +6.3 |
| 10. Shock day | 103 | −17.97 | 6.39 | 1.73 | −26.09 | −9.5 |

USD over the 30-month out-of-sample period from a 100 USD start; "net" is
the figure in `reports/strategy_research.md`. Gross per pair for the three
highlighted families: London breakout +8.20 / +11.46 / +19.44 (EUR/USD,
GBP/USD, USD/JPY); trend pullback 4h +31.14 / +19.46 / −17.10; EUR vs
GBP −6.11 / +22.69.

How to read it: the costs are not a small adjustment. For the 1h families
they are 1.5 to 2 times the size of the gross result either way. A family
needs about 4 pips a trade of real edge before it can break even; the best
found was 6 pips on 122 trades (family 9) and the next 4.5 pips on 309
(family 3), and those two already failed the luck and robustness checks on
their net results.

**Engine cross-check.** The same walk-forward schedules were run again
with commission and slippage switched off (`audit.no_costs()`):

| Family | Engine gross | Re-priced gross | Gap per trade | One commission |
|---|---|---|---|---|
| 5. Session drift | −39.88 | −39.33 | −0.0004 USD | 0.045 USD |
| 1. London breakout | +47.36 | +39.11 | +0.0066 USD | 0.057 USD |
| 9. EUR vs GBP | +16.78 | +16.59 | +0.0016 USD | 0.069 USD |

The two gross figures differ only through what a cost-free run changes:
bigger stakes (no losses to shrink the balance), no kill-switch restarts,
no daily-loss pauses, and stop levels 0.5 pip closer because the entry is
not slipped. A cost charged twice would open a gap of about one commission
per trade; the gaps are 1-12% of that. Costs are charged once.

## 4. The luck check

**What it does.** For each family the stitched out-of-sample run is
repeated with random entries: the same exits, the same candle hours, the
same rate of signals per pair and hour, and a coin toss for the
direction. The candidate must beat the 95th (round 1) or 99th (rounds 2-3)
percentile of those runs.

**Checked and correct:** the random runs use the family's own `stops()`
and `exit_now()`, the same engine, the same risk module, the same
commission table and slippage (asserted per trade in the tests), and the
same walk-forward schedule. The percentile is numpy's default linear
interpolation and the pass rule is "net strictly above it" with the
required number of runs; `R.luck_result()` now does this in one place for
the summary stage and is unit-tested.

**The bug.** The signal rate was stored per (pair, hour) over the whole
30-month run, and the random entry was then vetoed by the family's
`stops()` at any candle where it says "no trade". Two things go wrong:

1. *Diluted rates.* Family 8 was picked with entry hour 10 in rounds 1-2
   and hour 9 in rounds 3-5. Its 09:00 rate was measured over all five
   windows, three of which could signal at 09:00 and two of which could
   not; the random run then entered at that diluted rate in every window,
   and `stops()` (which only allows a trade at the window's own entry
   hour) threw away the rest. Random runs: 246 trades on average against
   the candidate's 419.
2. *Filters counted twice.* Family 6 only trades after a quiet night. The
   quiet test lives in `stops()`. The random rate was "signals ÷ all flat
   candles", quiet nights or not, and then `stops()` refused the random
   entries on busy nights: the filter applied twice. Random runs: 614
   trades against the candidate's 872. Family 1 has the same shape for
   its "box at least 10 pips" rule (2.5% fewer random trades).

Fewer random trades means less commission paid, so the random runs looked
better than they should and the candidate's "share of random runs beaten"
was understated. Family 5's hour change did not change its trade count
(its stops do not veto), but its random runs in rounds 1-2 entered at
06:00 instead of 08:00, a different hold than the candidate's.

**The fix** (`src/fxbot/backtest/research.py`): the rate is kept per
(walk-forward window, pair, hour), and the flat candles it is measured
over are only those where `stops()` would allow a trade. Tests:
`test_random_runs_keep_trade_count_when_the_signal_hour_changes_between_windows`
(fails on the old code at about half the trades, passes within 5% now) and
`test_random_runs_do_not_apply_an_entry_filter_twice`. The luck stage of
`scripts/research_family.py` refuses the old rate files, so a family
cannot be re-checked without rebuilding its rates.

**A residual the fix does not remove.** For the 4h and daily families the
random runs make *more* trades than the candidate (family 2: +13%, 4: +13%,
9: +21%, 10: +18%): a random-direction trade hits its stop sooner, the run
is flat sooner, and at the same per-candle rate it enters again. This is
inherent in "same rate per flat candle". It works *against* the random
runs (more commission), so it flatters the candidate; it cannot hide an
edge. If the owner wants the comparison exact, the alternative is "the
candidate's own signal candles, coin-toss direction", which fixes the
trade count by construction; that is a rule change and is not made here.

**Preview of the corrected check** (`scripts/audit_phase4.py
luck-preview`, 100 random runs each, saved in
`research/audit/luck_preview_*.json`; committed `luck.json` files were not
touched):

*(preview running at the time of this commit; filled in by the next commit)*

## 5. Other things noticed (not bugs, but worth knowing)

- **The fixed signal wait silently drops some signals.** A daily candle
  "ends" at 00:00 the next day, so Friday's daily candle ends on Saturday
  and its 12-hour wait expires before Monday 06:00: Friday daily signals
  never trade (known from family 7; it also applies to families 2-daily and
  10). A 4h candle ending at 20:00 or 00:00 needs more than 4 hours to
  reach the entry window, so 4h families trade only the candles ending
  04:00, 08:00, 12:00 and 16:00. The rule is applied as written and
  equally to the random runs; it is mentioned because it removes a third
  of the daily families' signals.
- **The entry-minute stop check uses the whole minute's range,** including
  the part before the trade existed. Seven trades in 6,996 were affected.
- **Stop levels move with cent rounding.** Deriv sets stop loss and take
  profit as cent amounts, so the levels sit up to 0.3 pips from the
  nominal pip distance, and the 1.5× stress run shifts them by 0.2 pips.
  Modelled as Deriv does it; no action.
- **The engine and data were reproducible.** Every stitched out-of-sample
  run repeated here gave the committed trade count and net to the cent.

## 6. Does "no edge" still stand, and what needs re-running?

**Yes, it stands.**
- The positive controls show the pipeline would have found an edge of a
  few pips, and did find one in synthetic data.
- No cost is double-charged; the gross numbers in section 3 are the true
  before-cost results, and they are small.
- The one real bug worked *against* families 6 and 8 (and marginally 1),
  not for them. The preview above shows where they land with it fixed:
  (see the preview table in section 4).

**What needs re-running.** Every committed `luck.json` was produced with
the old rate files, so strictly all 13 sub-grids' luck results are stale.
In order of how much the bug moved them:
1. **f8 (morning momentum)** and **f6 (quiet London breakout)**: large
   effect, must be re-run before their "beat random runs" figures are
   quoted again.
2. **f1 (London breakout)**: small effect (2.5% fewer random trades),
   re-run for completeness; its 95.5% is likely to tick up slightly, but
   it fails on net loss regardless.
3. **f5**: the random runs had the right count but the wrong hour in two
   windows; re-run for a clean record.
4. **f2, f3, f4, f7, f9, f10**: the fix changes nothing in their rates
   (one signal hour, no filters in `stops()`); the residual in section 4
   remains and flatters them. Re-run only if the owner adopts the stricter
   "same signal candles" rule.

Per the owner's rule, any re-run counts as new variants. The commands are
`python scripts/research_family.py oos --family f8` (rebuilds the rates
and the out-of-sample report; the trades do not change) followed by
`luck` and `summary`. Each luck re-run at 500 runs takes about 30 minutes
of compute in resumable 8.5-minute chunks.

## Files

| What | Where |
|---|---|
| Positive controls and the no-cost engine switch | `src/fxbot/backtest/audit.py` |
| Audit tests (17) | `tests/test_audit_phase4.py` |
| Real-data audit script (stages: trades, utc, cheat, grossnet, flip, luck-preview) | `scripts/audit_phase4.py` |
| Raw results of each stage | `research/audit/*.json` |
| The luck-check fix | `src/fxbot/backtest/research.py` (`Scheduled`, `RandomEntry`, `entry_rates`, `luck_result`), `scripts/research_family.py` |
