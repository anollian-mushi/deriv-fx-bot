# Cost what-if: would any Phase 4 family pass if trading were cheaper?

> **WHAT-IF ONLY. Nothing here is a candidate.** No new strategy, no new
> settings, no rule or data change, and **the holdout was not touched**. Each
> family keeps the settings its walk-forward already chose, and its recorded
> out-of-sample trades (2023-10-27 to 2026-04-26) are re-priced at other costs.
> A pass here would only mean "worth a separate, approved look", never "trade
> it".

Written 2026-10-30. Code: `src/fxbot/backtest/whatif.py`,
`scripts/cost_whatif.py`; tests `tests/test_cost_whatif.py`; raw results
`research/cost_whatif/`.

## The short version

- **No family passes at any cost, not even at zero.** That covers:
  - the low-cost broker model (about 1.0 pip a trade);
  - 2.0 pips a trade;
  - "slippage only, no commission";
  - "no cost at all", which no broker offers.
- **So none of the 10 families (13 versions) has a break-even cost to
  report.** And because none reaches a cost where everything else passes,
  the luck check has no level to be run at (section 4).
- **Cost is not what is stopping them.** Six versions do make money before
  costs, but each fails a rule that has nothing to do with cost:
  - **the profit comes from one pair:** London breakout (USD/JPY) and
    morning momentum (USD/JPY);
  - **too few trades:** EUR vs GBP convergence (122) and mean reversion 4h
    (167);
  - **the profit comes from a few big trades or one period:** trend
    pullback 4h and quiet-night London breakout.
- **The other seven versions lose money even before costs.**
- **What this means:** a cheaper broker or product would not rescue any of
  these strategies. It also confirms that the MT5 decision note in
  CLAUDE.md is not triggered.

| Bucket | Families |
|---|---|
| Would pass at about **1.0 pip** (low-cost broker model) | **none** |
| Would pass at **2.0 pips** total per trade | **none** |
| Would pass at **no realistic cost** | **all 13 versions**, and none passes even at zero cost |

## 1. How the what-if works

**Starting point.** For each family, I took its stitched out-of-sample
trades as recorded, with the walk-forward settings it actually picked.

**Step 1: strip out the costs.**
- Each trade's **before-cost move** is its recorded profit with every
  modelled cost added back: commission, 0.5 pip entry slippage, and 1 pip
  slippage on stop-loss exits.
- This is the same calculation the Phase 4 audit used
  (`audit.gross_of`).

**Step 2: charge a new cost.** Three cost models:
- **"Total C pips" (question 1):**
  - every trade costs C pips, slippage included, with no overnight fee;
  - the loss stays capped at the stake, as on Multipliers;
  - a trade can never cost less than its own slippage (0.5 pip, or 1.5 pips
    on a stop-loss exit), so C = 0.5 means "slippage only, no commission";
  - scanned from 0.5 to 5.0 pips in 0.1-pip steps.
- **"Low-cost broker" (question 2):**
  - a fee of 1.0 pip on EUR/USD and GBP/USD and 1.3 pips on USD/JPY;
  - the same slippage rules on top;
  - plus the overnight swap from the MT5 comparison (`mt5.py`: per night,
    triple on Wednesdays, long or short rate by direction);
  - no stake cap, because a CFD has none.
  - With slippage, this averages roughly 1.5–2.4 pips per trade before
    swap, depending on how often a family exits at its stop.
- **"No cost at all":** shown for reference, to tell "costs too high" apart
  from "no edge".

**Step 3: rebuild the account.**
- Trades are replayed in time order from 100 USD.
- Stake = 3% of the closed balance at entry, x100.
- The kill switch runs in research "observe" mode: at 50 USD the event is
  recorded and the balance restarts at 100 USD.

**Step 4: run every check at each cost.**
- **The CLAUDE.md rules:**
  - profitable on 2 of 3 pairs, and profitable overall;
  - 200+ out-of-sample trades;
  - at most 5 settings;
  - average win at least 3× the average cost actually paid (here the full
    cost including slippage, which is stricter than commission alone);
  - no kill switch.
- **The four "not fake" checks:**
  - not one pair;
  - not one half-year;
  - not a few big trades;
  - nearby settings work. For this one, the neighbouring grid runs are
    re-priced the same way. The settings themselves are never re-chosen.

**Self-check.** Re-pricing each family at the cost it actually paid
reproduces its recorded result:
- exactly to the cent for 8 of 13 versions;
- within 1.3 USD for the others (−57.55 vs −56.30, −60.31 vs −61.63,
  −39.24 vs −39.94, −123.04 vs −123.27).

The small gaps come from the approximations below.

**Approximations (all small next to the results):**
- **Same trades at every cost.** In a real run at another cost, a
  different balance path could change a daily-loss pause or which signal
  gets one of the 2 position slots. The re-priced runs keep every trade.
- **The kill switch checks closed balance, not live equity.** That is
  slightly lenient, but no family here is near the line except the ones
  that lose anyway.
- **Exits at Deriv's stop-out level are kept as they were,** in the broker
  model too. At x100 this is rare.

## 2. Results

Net result in USD over the 30 months from a 100 USD start. "Before-cost
edge" is the average move per trade in the trade's favour, before any cost.

| Family | Trades | Before-cost edge (pips/trade) | As recorded (Deriv) | No cost at all | Slippage only (0.5) | 1.0 total | 2.0 total | Low-cost broker (1.0 / 1.3 + swap) |
|---|---|---|---|---|---|---|---|---|
| 1. London breakout 1h | 1,256 | **+1.8** | −56.30 | +52.71 | +12.66 | +5.31 | −14.98 | −17.89 |
| 2. Trend breakout 4h | 266 | −2.9 | −40.83 | −24.38 | −28.37 | −29.83 | −33.21 | −36.43 |
| 2. Trend breakout daily | 130 | −5.8 | −26.97 | −18.05 | −19.88 | −20.83 | −22.96 | −24.12 |
| 3. Trend pullback 4h | 309 | **+4.5** | +0.70 | +33.48 | +25.76 | +22.88 | +15.48 | +7.32 |
| 3. Trend pullback 1h | 1,251 | −1.4 | −123.27 | −36.70 | −56.74 | −62.54 | −79.11 | −86.56 |
| 4. Mean reversion 1h | 551 | −2.0 | −61.63 | −25.81 | −34.46 | −36.69 | −42.65 | −40.93 |
| 4. Mean reversion 4h | 167 | **+1.6** | −10.14 | +4.54 | +1.42 | +0.05 | −3.12 | −7.42 |
| 5. Session drift 1h | 1,290 | −1.0 | −107.92 | −36.60 | −45.98 | −57.71 | −82.82 | −71.47 |
| 6. Quiet-night London breakout 1h | 872 | **+2.0** | −39.94 | +39.10 | +9.62 | +5.64 | −8.26 | −11.84 |
| 7. Weekly momentum daily | 260 | −2.4 | −32.45 | −14.87 | −18.61 | −20.40 | −24.58 | −32.00 |
| 8. Morning momentum 1h | 419 | **+1.8** | −23.46 | +12.40 | +3.67 | +0.42 | −7.20 | −6.98 |
| 9. EUR vs GBP convergence daily | 122 | **+6.3** | +6.17 | +17.40 | +15.12 | +13.57 | +10.39 | +6.72 |
| 10. Shock day daily | 103 | −9.5 | −26.09 | −18.84 | −20.41 | −21.00 | −22.66 | −23.58 |

**Highest total cost at which each would pass every rule and check:
none for all 13.** Every row fails at least one check at every cost from
0.5 to 5.0 pips, and at zero.

What blocks each family that makes money before costs. Pair results are in
USD; "half-years" are the 5 test windows.

**1. London breakout**
- **With no cost:** passes everything except "not a few big trades".
  Without its largest 26 trades (2%) it loses 35.56 USD.
- **From slippage only upwards:** EUR/USD and GBP/USD lose. All the
  profit is USD/JPY (+24 at slippage only), so it fails "2 of 3 pairs".

**3. Trend pullback 4h**
- **At every cost:** USD/JPY loses (−24 to −27), so the profit rests on
  EUR/USD and GBP/USD. It fails "not one pair".
- **It also fails "not a few big trades":** without its largest 7 trades
  it loses 23 to 42 USD.
- **From slippage only upwards, it also fails:**
  - "not one half-year": +12, +12, +29, then −4 and −23 (slippage only);
  - "nearby settings work".

**4. Mean reversion 4h**
- Only 167 trades. The 200-trade rule fails whatever the cost.
- Its before-cost edge (+4.54 USD over 30 months) is almost nothing
  anyway.

**6. Quiet-night London breakout**
- **With no cost:** fails only "not a few big trades" (−12.31 USD without
  its largest 18).
- **At slippage only and at 1.0:**
  - EUR/USD loses (−20 to −21), so it fails "not one pair";
  - its first and last half-years lose;
  - it still depends on its biggest trades.
- **At 2.0 and at the broker model:** a net loss.

**8. Morning momentum**
- **At every cost:** USD/JPY carries it, so it fails "not one pair". It
  also depends on a few big trades.
- **From slippage only upwards:** it is profitable on only one pair, so it
  also fails "2 of 3 pairs".

**9. EUR vs GBP convergence**
- Only 122 trades. The 200-trade rule fails at every cost.
- The EUR leg loses at every cost, so it also fails "2 of 3 pairs". (The
  rule question about two-leg trades raised in
  `reports/strategy_research.md` still stands; it would not change this,
  because of the trade count.)

**The other seven versions** (2 ×2, 3-1h, 4-1h, 5, 7, 10) **lose money
even before costs.** No price could make them pass.

## 3. The three buckets, in plain language

**Would pass at about 1.0 pip (low-cost broker): none.**
- At the broker model only two versions make money at all: trend
  pullback 4h (+7.32 USD) and EUR vs GBP convergence (+6.72 USD).
- Both fail on rules that cost doesn't touch: the trend
  pullback relies on two pairs and a few big trades, and EUR vs GBP has
  too few trades.
- The broker's overnight swap also hurts the strategies that hold for
  days. Trend pullback 4h makes +15.48 at "2.0 total, no swap" but only
  +7.32 at the broker, even though the broker's fee is lower.

**Would pass at 2.0 pips: none.**
- At 2.0 pips total, only two versions are still in profit: trend
  pullback 4h (+15.48) and EUR vs GBP (+10.39). Both fail the same
  cost-independent checks listed above.
- London breakout, quiet-night London breakout, morning momentum and mean
  reversion 4h are in profit only below about 1–1.5 pips total. Even there,
  each fails a check that has nothing to do with cost.

**Would pass at no realistic cost: all 13.**
- Even the impossible "no cost at all" case produces no pass.
- The closest calls with no cost are London breakout (1h) and quiet-night
  London breakout. They pass every rule except "not a few big trades": a
  small number of large winners carry the whole result.

## 4. Why the luck check was not run

The request was to run the luck check (99th percentile of 500 random runs)
at each family's break-even cost. **No family has a break-even cost**:
none passes the other rules at any cost, so there is no level to test.

Running it anyway would cost about 30 minutes of compute per family and
could not change any outcome. A luck pass cannot make up for a failed rule.

If this is ever revisited (for example with a longer history), the luck
check must use the corrected random-entry rates from the Phase 4 audit. The
script does that: `python scripts/cost_whatif.py random`, then `luck`. It
rebuilds the rates in memory from each family's own out-of-sample run and
saves the random trades, so they can be re-priced at any cost.

## 5. What this means for the project

- **Cheaper trading would not rescue any of these strategies.** Every
  failure that survives at zero cost is a failure of the idea, not the
  price:
  - one pair carrying the result;
  - a handful of big winners;
  - one good period;
  - too few trades.
- **The CLAUDE.md MT5 decision note stays untriggered.** It applies only
  if a strategy passes at MT5 costs and fails at Multiplier costs. Nothing
  passes at any cost.
- **The Phase 4 conclusion stands, now from the cost side as well:** on
  2023–2026 data, none of the ten families has a robust edge on these
  pairs.
- **The two ideas with the most before-cost edge** are EUR vs GBP
  convergence (6.3 pips a trade) and trend pullback 4h (4.5 pips).
  - Their problems are too few trades and concentration in one period.
  - More history (option 1 in `reports/strategy_research.md`) is the only
    thing that could tell whether that is bad luck or no edge.
  - That needs the owner's approval, and any re-test counts as new
    variants judged at the 99th percentile.

## Files

| What | Where |
|---|---|
| Re-pricing model | `src/fxbot/backtest/whatif.py` |
| Scan, random runs, luck | `scripts/cost_whatif.py` |
| Tests (self-check on real trades, slippage floor, swap, stake cap, kill switch) | `tests/test_cost_whatif.py` |
| Every cost level × every check, per family | `research/cost_whatif/scan.json` |
| The "no cost at all" run (`python scripts/cost_whatif.py zero`) | `research/cost_whatif/zero_cost.json` |
