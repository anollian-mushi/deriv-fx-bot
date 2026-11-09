# What a Multiplier trade really costs (Phase 2)

Measured 2026-10-28 16:22 UTC to 2026-10-29 19:18 UTC on frxEURUSD,
frxGBPUSD and frxUSDJPY. Sources:
- 29 price-quote samples, about 6,000 quotes. Most came from the demo
  account's own connection; 3 from the real account (quotes only, no orders);
  7 from the public connection.
- 11 demo trades at the 1 USD minimum stake (demo money only).

All numbers are rebuilt from the raw files by the scripts listed at the end.
Candle-based figures (typical moves) use only data before 2026-04-28, as the
holdout rule in CLAUDE.md requires.

## The short version

- **One cost, paid when the trade opens: Deriv's commission.** There is no
  spread: trades open and close at the mid price. There is no overnight fee:
  a trade held 12 hours through Wednesday night was charged nothing extra.
- **The commission rate changes during the day, a lot.**

  | When (UTC) | Rate, EUR/USD example | Price must move this far your way just to break even |
  |---|---|---|
  | 06:00–17:59 (normal) | 0.024% | **about 3 pips** (USD/JPY: 4) |
  | 00:00–05:59 | a little higher | about 3–3.5 pips |
  | Around big news, 18:00–20:55 | 2–4× | 6–10 pips |
  | Just after the daily pause | up to 12× | up to 33 pips |

- **New trades are refused every weekday from 20:55 to 21:30 UTC.** Open
  trades carry on normally through the pause.
- **The multiplier does not change the cost in pips.** It changes two things:
  - **how close the automatic stop out is:** at 1 USD and x100 it is about
    115–150 pips away; at x800 about 12–15 pips;
  - **how much of your stake the commission eats:** 2–3% at x100, 16–22% at
    x800, in normal hours.
- **Realistic for 15m–1h trading: x100, and x200 at most, opening only in
  normal hours (06:00–17:59 UTC, away from big news).** Even then, a 15m
  trade starts about half a typical candle behind, and a 1h trade about a
  fifth to a quarter.
- **Real and demo charge exactly the same rate at the same moment.** This was
  checked side by side three times. Demo results are therefore priced
  correctly, as long as they use the rate of the hour the trade opened.

## 1. Which multipliers really work

| Connection | Offered | Refused |
|---|---|---|
| **Real account** (quotes only) | **100, 200, 300, 500, 800** | 50, 150, 250 |
| **Demo account** | **100, 200, 300, 500, 800** (even a direct buy at 50/150/250 was refused) | 50, 150, 250 |
| Public connection, no login | 50, 100, 150, 250, 500 | 200, 300, 800 |

- The real and demo lists match `contracts_for`. The public list does not,
  and it is not what we trade.
- **x500 and x800 can disappear when commission is high.** Just after the
  daily pause (21:36 UTC), Deriv refused them as "Invalid stake/payout":
  commission × multiplier would have been more than 100% of the stake.
- The project only allows x100 and x200 (CLAUDE.md). Both were offered in
  every sample.

## 2. Limits (the same on all three pairs, demo and real)

| Item | Limit | Notes |
|---|---|---|
| Stake | 1 to 2,000 USD | 500 USD max on the public connection |
| Take profit | 0.10 USD to 50 × stake | |
| Stop loss | commission + 0.01 USD to the stake | **Use commission + 0.02.** Deriv's own check rejects the exact minimum when its decimal maths rounds a hair above (0.2 + 0.01 = 0.21000000000000002) |
| Minimum commission | 0.02 USD | Matters only at x50 and 1 USD, which we don't use |
| Stop out | always on | The trade closes when the loss, including commission, reaches the whole stake |

None of these limits changed with the time of day or with stake size, apart
from the multiplier refusals above.

## 3. Commission by hour

Full table: `research/phase2/cost_by_hour.md`. Every reading for each hour
is listed, and the highest reading per hour is the one backtests use. Here
is the summary at the 1 USD minimum stake, x100. The cost is the move needed
to break even, in pips.

| UTC hours | EUR/USD | GBP/USD | USD/JPY | What we saw |
|---|---|---|---|---|
| 00–05 | 3.1–3.3 | 3.2–3.6 | 4.3–4.7 | about 1.1–1.3× base, falling towards morning |
| 06–11 | 2.8 | 2.7 | 4.3 | base rate, every sample |
| 12 | 8.4 | 8.2 | 12.9 | 3× base, all pairs (12:32 Thu; likely US data release) |
| 13 | 8.4 | 2.7 | 4.3 | EUR/USD still 3×, others back to base |
| 14–17 | 2.8 | 2.7 | 4.3 | base rate, both days where sampled |
| 18 | 8.4 | 8.2 | 12.9 | 3× Wed (US rate decision day), 2× Thu |
| 19 | 6.5 | 6.2 | 10.6 | 2.3–2.5× |
| 20:00–20:55 | 10.4 | 10.0 | 17.2 | 3.7–4×; **new trades refused 20:55–21:30** |
| 21:30–22 | 33.5 | 32.7 | 51.7 | **12× just after the pause** |
| 22 | 16.6 | 16.0 | 25.4 | 6× |
| 23 | 12.0 | 12.6 | 18.3 | 4.3–4.6× |

Base rates (the lowest ever seen, and the most common):
- EUR/USD **0.0239%**
- GBP/USD **0.0203%**
- USD/JPY **0.0275%**

These are shares of stake × multiplier.

How to read it:
- **The base rate always came back to exactly the same value.** That looks
  like Deriv's normal price, multiplied up at certain times.
- **The rises look like two things on top of each other:**
  1. **A daily pattern:** raised in the evening, highest just after the
     20:55–21:30 pause, back to base by about 06:00.
  2. **News:** about 3× around big releases. The rise was per currency: at
     13:16 only EUR/USD was still raised.
- **We have only one or two readings per hour.** On a heavy-news day other
  hours could be raised too, and quiet evenings could be cheaper. The rule
  "use the highest reading per hour, plus a 1.5× stress test" covers this
  cautiously.

## 4. What one trade costs at the 1 USD minimum stake

**Normal hours (base rate):**

| Multiplier | Position size | EUR/USD commission (% of stake) | GBP/USD | USD/JPY | Stop out distance (EUR / GBP / JPY) |
|---|---|---|---|---|---|
| x100 | 100 USD | 0.024 USD (2%) | 0.020 (2%) | 0.028 (3%) | 114 / 131 / 152 pips |
| x200 | 200 USD | 0.048 (5%) | 0.041 (4%) | 0.055 (6%) | 56 / 64 / 74 pips |
| x300 | 300 USD | 0.072 (7%) | 0.061 (6%) | 0.083 (8%) | 36 / 42 / 48 pips |
| x500 | 500 USD | 0.120 (12%) | 0.101 (10%) | 0.138 (14%) | 21 / 24 / 27 pips |
| x800 | 800 USD | 0.191 (19%) | 0.162 (16%) | 0.220 (22%) | 12 / 14 / 15 pips |

**Raised hours (3× base, e.g. news or 18:00 UTC):**

| Multiplier | EUR/USD commission (% of stake) | GBP/USD | USD/JPY | Stop out distance (EUR / GBP / JPY) |
|---|---|---|---|---|
| x100 | 0.072 (7%) | 0.061 (6%) | 0.083 (8%) | 108 / 126 / 144 pips |
| x200 | 0.143 (14%) | 0.122 (12%) | 0.165 (16%) | 50 / 59 / 65 pips |
| x300 | 0.215 (22%) | 0.183 (18%) | 0.247 (25%) | 31 / 37 / 39 pips |
| x500 | 0.358 (36%) | 0.304 (30%) | 0.412 (41%) | 15 / 19 / 18 pips |
| x800 | 0.574 (57%) | 0.487 (49%) | 0.660 (66%) | 6 / 9 / 7 pips |

In plain terms:
- **Break-even is the same at every multiplier:** 2.7–2.8 pips (4.3 on
  USD/JPY) in normal hours. A higher multiplier makes each pip worth more,
  but the commission grows in step with it.
- **What a higher multiplier really does is shorten the leash.** At x800, a
  normal 15-minute wobble of 12–15 pips can stop the trade out, losing the
  whole stake. In raised hours it can be as little as 6–9 pips.
- **The stake scales everything.** At 3 USD (the 3% cap on a 100 USD
  account), multiply every USD figure by 3. The pips and percentages stay the
  same.

## 5. Cost compared with a typical move

"Typical move" is the median high-to-low range of one candle on Deriv's
prices from 2025-10-29 to 2026-04-27. Dukascopy's longer history comes after
the slash. Cost is per trade, open and close together.

| Pair | Candle | Typical range | Normal hours | 3× hours |
|---|---|---|---|---|
| EUR/USD | 15m | 5.0 / 5.6 pips | 2.8 pips = **56%** | 167% |
| EUR/USD | 1h | 10.4 / 11.6 | 2.8 = **27%** | 80% |
| EUR/USD | 4h | 21.2 / 23.9 | 2.8 = **13%** | 39% |
| EUR/USD | 1d | 58.6 / 71.2 | 2.8 = **5%** | 14% |
| GBP/USD | 15m | 6.7 / 7.3 | 2.7 = **41%** | 122% |
| GBP/USD | 1h | 14.2 / 14.8 | 2.7 = **19%** | 58% |
| GBP/USD | 4h | 29.8 / 30.6 | 2.7 = **9%** | 27% |
| GBP/USD | 1d | 81.1 / 87.7 | 2.7 = **3%** | 10% |
| USD/JPY | 15m | 8.4 / 9.1 | 4.3 = **51%** | 154% |
| USD/JPY | 1h | 17.5 / 18.9 | 4.3 = **25%** | 74% |
| USD/JPY | 4h | 36.7 / 39.5 | 4.3 = **12%** | 35% |
| USD/JPY | 1d | 92.3 / 113.3 | 4.3 = **5%** | 14% |

The MT5 comparison is in `reports/product_choice.md`.

## 6. Which multipliers look realistic for 15m–1h trading

- **x100: yes, in normal hours.**
  - Stop out is 114–152 pips away, about 11 typical hourly candles. Normal
    noise will not stop it out; your own stop loss decides the exit.
  - Commission is 2–3% of the stake.
- **x200: possible, with care.**
  - Stop out is 56–74 pips away, about 5 typical hourly candles. That is fine
    for 15m–1h, but tight for a trade held a day.
  - Commission is 4–6% of the stake in normal hours, 12–16% in raised hours.
- **x300 to x800: not realistic.**
  - The stop out sits within 1–4 typical hourly candles, and as close as 6
    pips in raised hours.
  - Commission eats 6–66% of the stake.
  - Deriv may refuse x500 and x800 outright at expensive times.
  - The project rules already exclude them.

**Timing matters more than the multiplier.**
- Opening only in **06:00–17:59 UTC** (outside big news) keeps costs at the
  base rate.
- Opening at **18:00–05:59** costs 1.1× to 12× more per trade.

**15m is still very hard.** Even at the base rate, costs are 41–56% of a
typical 15-minute candle. A 15m strategy would need targets of many candles.

**1h is workable only with targets several candles wide.** Costs are 19–27%
of one typical hourly candle.

## 7. How trades actually fill (11 demo trades)

| Check | Result |
|---|---|
| Entry price vs the quote | Entry fills at the **mid price**, 0.0–0.5 pip from the quoted spot (average about 0.05 pip, worst 0.5 pip against us) |
| Manual close (`sell`, price 0) | Filled **exactly** at the last price shown on all 7 manual closes |
| Take profit | Closed exactly at the level and paid exactly the amount set (2 of 2) |
| Stop loss | Closed at the **first tick at or past the level**, at that tick's mid. A price jump past the level costs the size of the jump: 0.6 pip (0.03 USD extra at x500 on EUR/USD) and 0.01 USD on USD/JPY |
| Changing TP/SL (`contract_update`) | Set, changed and removed fine on all 6 test cycles; Deriv's prices matched our formula within 1 pipette |
| Profit rounding | Deriv's profit is our formula rounded to the nearest cent (all differences within ±0.009 USD) |
| How Deriv reports its own closes | Contracts closed by TP, SL or stop out come back with `status: null` and `is_sold: 1`. The bot must read `is_sold`, not `status` |

## 8. Stop-out formula

```
commission = max(0.02, rate × stake × multiplier)   (unrounded)
stop out   = entry × (1 − (stake − commission) / (stake × multiplier))   for Up
stop out   = entry × (1 + (stake − commission) / (stake × multiplier))   for Down
rounded to the pip size, away from the entry price
```

Checked against every quote collected (`research/phase2/stopout_check.md`):

| Connection | Quotes | Exact | Largest error |
|---|---|---|---|
| Demo | 4,404 | 4,404 | **0** |
| Real | 540 | 540 | **0** |
| Public | 1,080 | 1,067 | 1 pipette (0.1 pip) |
| All demo trades | 10 stop-out prices | 10 | 0 |

**Largest error overall: 1 pipette (0.1 pip), on the public connection
only.** If the bot uses the commission *shown* in a quote (rounded to cents)
instead of the rate, the error grows to 6 pipettes (0.6 pip). So the code
uses the unrounded rate (`src/fxbot/contracts/multiplier.py`).

## 9. Overnight, weekend and the daily pause

- **Overnight: no charge.**
  - Demo trade #11 (EUR/USD Up, x100, 1 USD) was held 12.3 hours, from 20:01
    Wednesday to 08:21 Thursday. That covered the daily pause, the rollover
    and Wednesday night, when CFD brokers charge a triple swap.
  - The statement shows only the buy (−1.00) and the sell (+0.70).
  - The 0.30 loss is the 23-pip price move plus the commission paid at the
    start; our formula gave −0.296.
- **Daily pause:** new trades are refused 20:55–21:30 UTC on weekdays. Deriv
  says "Trading is not available from 20:55:00 to 21:30:00", although its
  trading hours list nothing. Open trades are not affected.
- **Weekend: no charge (measured 6-9 Nov 2026, `reports/weekend_test.md`).**
  - A demo EUR/USD Up contract, x100, 1 USD, stop loss 0.20 USD, was held from
    Friday 18:01 to Monday 06:30 UTC.
  - The statement shows only the buy (-1.00) and the sell (+1.12). The +0.12
    profit is the price move minus the 0.02 commission paid at the start,
    so nothing at all was charged for the weekend.
  - The Monday gap was 9.3 pips in the trade's favour, so the stop loss was
    not reached. **Still open:** what a large gap against a trade does to the
    stop loss (fill at the gapped price, or worse) and to the stop out.
    Deriv's terms say a Multiplier never loses more than its stake.
  - Recommendation: keep the "no weekend holding" rule until a gap against a
    trade has been seen; repeat with one Up and one Down contract.

## 10. What the backtester must use (from these results)

1. **Commission:** the highest rate measured for the UTC hour the trade
   opens (`research/phase2/cost_by_hour.json`). Also run every backtest at
   1.5× that rate.
2. **No new trades 20:55–21:30 UTC** on weekdays, and none outside Deriv's
   trading hours.
3. **No spread on Multipliers.** Fill at the mid price, plus a slippage
   allowance:
   - **entry:** 0.5 pip against us, the worst seen;
   - **stop-loss exits:** 1 pip past the level, to cover gaps.
4. **Take profit:** pays exactly the amount set.
5. **Stop out:** the formula in section 8, with the loss capped at the stake.
6. **Profit** rounded to the nearest cent.
7. **Stop loss** at least commission + 0.02 USD.

## 11. Decisions taken after this report (owner, 30 Oct; in CLAUDE.md)

- **Product:** Multipliers, x100 or x200 only (x100 for trades held
  overnight).
- **Timeframes:** 1h and 4h, with daily as a secondary check. 15m is out.
- **Entry window:** new trades only 06:00–17:59 UTC, never 20:55–21:30.
  **The window is provisional:** it was measured between the European (25
  Oct) and US (1 Nov) clock changes. In the week after 1 Nov, 05:00–07:00
  and 12:00–19:00 UTC are re-sampled on two weekdays (quotes only) to check
  whether the cheap window moved, and whether 12:00–13:59 is raised every
  day or only on news days.
  **Result (5 Nov): the window did not move; see section 13.**
- **Live cost gate (risk module):** before every buy, the bot skips the trade
  if the quoted commission rate is above 1.5× the pair's base rate:

  | Pair | Base rate | Skip above |
  |---|---|---|
  | EUR/USD | 0.0239% | 0.0359% |
  | GBP/USD | 0.0203% | 0.0305% |
  | USD/JPY | 0.0275% | 0.0413% |

  Every skip is logged with the rate seen.
- **No weekend holding** until the Phase 6 weekend test. Every open trade is
  closed by Friday 20:30 UTC, in the backtester too.
- **Pricing source:** backtests take commission only from
  `research/phase2/cost_by_hour.json`. The commission figures in
  `config/contract_specs.yaml` mix different hours and must never be used
  for pricing.
- **Minimum target:** a strategy's average winning trade must be at least 3×
  the average commission its trades actually paid. At the base rate that is
  about 9 pips on EUR/USD, 8 on GBP/USD and 13 on USD/JPY.

## 12. Limits of this data

- **Only one weekday (Wednesday to Thursday), with one or two samples per
  hour.** Rates at the same hour on other days, especially heavy-news days,
  may differ. Re-sampling for a few more days during the Phase 6 demo run
  would tighten the table.
- **The link to news is our reading of the timing,** not something Deriv
  states.
- **Only 11 demo trades.** The fill results are consistent but small in
  number. The Phase 6 demo run will add many more.

## 13. Clock-change re-check (after 1 Nov 2026)

**Short answer: the cheap window did not move.** From 06:00 to 17:59 UTC
the commission stayed at, or within 1.15x of, the base rate on all three
days sampled after the US clock change, well under the 1.5x cost gate. The
12:00-13:59 rise seen on Thursday 29 Oct did not come back on any day, so it
looks like a news-day effect, not a daily pattern. The evening is cheaper
than before at 19:00, but 18:00 is still raised on some days.

**What was sampled.** Quotes only, on the demo connection, no trades:
05:00-07:00 and 12:00-19:00 UTC on Tuesday 3 and Thursday 5 November, plus
Monday 2 November hourly from 06:00 to 18:00 (taken for the new-pairs test,
which also quoted the three majors). Two hours are missing: Tuesday 13:00
(the sample started 52 minutes late and fell into 14:00) and Monday 14:00 and
19:00 (not sampled or late). Each other re-checked hour has two or three days.

**The readings**, as a multiple of each pair's base rate, for EUR/USD /
GBP/USD / USD/JPY:

| UTC hour | Wed 28 Oct | Thu 29 Oct | Mon 2 Nov | Tue 3 Nov | Thu 5 Nov |
|---|---|---|---|---|---|
| 05 | | 1.1 / 1.2 / 1.0 | | 1.2 / 1.2 / 1.1 | 1.2 / 1.2 / 1.1 |
| 06 | | 1.0 / 1.0 / 1.0 | 1.1 / 1.2 / 1.0 | 1.1 / 1.2 / 1.0 | 1.1 / 1.2 / 1.0 |
| 07 | | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 | 1.0 / 1.1 / 1.0 | 1.0 / 1.1 / 1.0 |
| 12 | | **3.0 / 3.0 / 3.0** | 1.0 / 1.0 / 1.1 | 1.0 / 1.0 / 1.1 | 1.0 / 1.0 / 1.1 |
| 13 | | **3.0** / 1.0 / 1.0 | 1.0 / 1.0 / 1.1 | missing | 1.0 / 1.0 / 1.0 |
| 14-17 | 1.0 (16:00) | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0-1.1 | 1.0 / 1.0 / 1.0-1.1 | 1.0 / 1.0 / 1.0-1.1 |
| 18 | **3.0 / 3.0 / 3.0** | **2.0 / 2.0 / 2.1** | **2.3 / 2.2 / 2.5** (18:21) | 1.0 / 1.0 / 1.2 (18:11) | 1.0 / 1.0 / 1.2 (18:11) |
| 19 | | **2.3 / 2.3 / 2.5** | missing | 1.2 / 1.1 / 1.3 | 1.2 / 1.1 / 1.3 |

**Did the cheap window move?**
- **Morning:** no. 05:00 is slightly raised (1.1-1.2x) and 06:00 only just
  above base on EUR/USD and GBP/USD (1.1-1.2x). From 07:00 it is at base,
  as before. The window can keep starting at 06:00: those readings are far
  under the 1.5x gate, which would still block a trade on a bad day.
- **Afternoon:** 12:00-17:59 is at base on every post-change day. USD/JPY
  sits a little above its lowest-ever rate (1.05-1.14x) most afternoons.
- **Evening:** it seems to have shifted about an hour later. Before the US
  change, 18:00 was 2-3x and 19:00 about 2.3x. After it, 19:10 is only
  1.1-1.3x and 18:11 is near base, but Monday's 18:21 reading was still
  2.2-2.5x. The rise probably starts within the 18:00 hour now. Nothing
  changes for the bot, because new trades already stop at 17:59.

**Was 12:00-13:59 raised every day or only on news days?** Only on Thursday
29 Oct. It was at base on Monday 2, Tuesday 3 and Thursday 5 November.
Scheduled news, for context only (**not verified**: taken from public
economic calendars, not from Deriv):
- Thu 29 Oct: ECB rate decision, listed for 13:15 UTC (14:15 CET), with the
  press conference after it. That fits the 3x seen at 12:32 on all pairs and
  at 13:16 on EUR/USD only.
- Wed 28 Oct: US Federal Reserve decision, listed for 18:00 UTC. That fits
  the 3x at 18:07.
- Tue 3 Nov: US election day; no big release found for 12:00-14:00 UTC.
- Thu 5 Nov: Bank of England decision, listed for 12:00 UTC. The 12:12
  sample was at base, so the rise, if any, did not last past the release or
  did not happen.
So the pattern fits "raised around big central-bank news, otherwise base",
but three quiet days are not proof.

**What changed in the cost table.** `research/phase2/cost_by_hour.json` now
uses only the post-1-Nov samples for 05:00-07:00 and 12:00-19:00 UTC, the
highest reading per hour, and records the dates each hour comes from. The
other hours keep their 28-29 Oct readings. Base rates are unchanged.
Main changes for backtests and the incubator: 12:00 and 13:00 drop from 3x
to base, 18:00 from 3x to about 2.3x, 19:00 from 2.3x to about 1.2x, and
05:00-07:00 rise slightly (1.05-1.2x). The incubator replays every
candidate with the current table, so its forward results will be repriced
with these rates from the next daily run; the engine fingerprint changes
for that reason. The 28-29 Oct table is kept unchanged as
`research/phase2/cost_by_hour_2026-10-29.json` (archive, never used for
pricing).

**Proposed CLAUDE.md wording (needs the owner's approval; not changed).**
Replace the last two sentences of the "Entry window" bullet with:

> Fixed, not a tunable parameter. Re-checked after the US clock change
> (2, 3 and 5 Nov 2026; reports/costs.md section 13): the window did not
> move. 12:00-13:59 UTC is raised only around big news, which the live cost
> gate handles.

## Files

| What | Where |
|---|---|
| All measured specs (rebuilt by `scripts/build_contract_specs.py`) | `config/contract_specs.yaml` |
| Commission by hour (`scripts/cost_by_hour.py`) | `research/phase2/cost_by_hour.md` / `.json` |
| The 28-29 Oct table before the re-check (archive, not for pricing) | `research/phase2/cost_by_hour_2026-10-29.json` |
| Stop-out check (`scripts/check_stopout.py`) | `research/phase2/stopout_check.md` |
| Real vs demo, same-time pairs | `research/phase2/real_vs_demo.md` |
| Every demo trade | `research/demo_cost_trades.csv`; raw replies in `research/phase2/demo_raw/` |
| Raw quote samples | `research/phase2/proposals_*.jsonl.gz` |
| Typical moves and cost vs move (`scripts/typical_moves.py`, `scripts/product_costs.py`) | `research/typical_moves.json`, `research/product_costs.json` |
