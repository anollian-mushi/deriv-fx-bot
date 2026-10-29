# Product choice: Multipliers or MT5 forex CFDs?

Written 2026-10-28, after Phase 2. Research only: no trades, and the real
account was used for price quotes only. Numbers come from:
- our own measurements: `config/contract_specs.yaml`, `research/phase2/`
- Deriv's official pages, listed under Sources at the end
- our candle data: `research/typical_moves.json`, `research/product_costs.json`

Rebuild the tables with `python scripts/typical_moves.py` and
`python scripts/product_costs.py`.

## Update (2026-10-29, 19:30 UTC): final version, read this first

This report was first written on 28 Oct and then corrected twice:
1. **Real and demo charge the same commission at the same moment.** An
   earlier "real costs 3× demo" claim came from comparing samples taken 90
   minutes apart.
2. **The rate changes with the time of day and around news.** A full day of
   hourly samples (`reports/costs.md`, section 3) shows:
   - **06:00–17:59 UTC:** the base rate (EUR/USD 0.0239%), except around big
     news.
   - **00:00–05:59:** a little above base.
   - **18:00–23:59:** 2× to 12× the base. The highest reading came just
     after the daily 20:55–21:30 pause, when new trades are refused.

Sections 3, 4 and 5 below are rewritten with the full day of data. The MT5
facts and integration findings (sections 1, 2, 6) did not change.

## The short version

- **At the base rate, a Multiplier trade costs about 3 pips** (EUR/USD,
  GBP/USD) or 4 pips (USD/JPY), paid once when it opens:
  - no spread;
  - no overnight fee (checked over one weekday night).

  **In the evening and around big news it costs 2–12 times more.**
- **MT5 CFDs are still cheaper:** about 1.0–1.4 pips of spread, plus a
  nightly swap. That is about 2–3 times cheaper than Multipliers at the base
  rate, and far cheaper than Multipliers in the evening.
- **MT5 is still the riskier product for this project:**
  - losses are **not capped** at a stake;
  - Deriv's API **cannot trade MT5**;
  - it needs the Windows-only MT5 terminal running unattended.
- **Recommendation:** stay on **Multipliers, x100 (x200 at most)**. Research
  **1h and 4h** candles, with daily as a secondary check, and open new trades
  only in **06:00–17:59 UTC**. Drop 15m: even at the base rate it costs about
  half of a typical 15-minute candle. Every backtest still shows MT5 costs
  side by side.

## 1. Costs side by side (EUR/USD, GBP/USD, USD/JPY)

| | **Deriv Multipliers (real account)** | **Deriv MT5 forex CFD** |
|---|---|---|
| Spread | **None.** Entry and exit fill at the mid price (measured on 10 demo trades: entry 0.0–0.5 pip from the quote, sells exactly at the shown price) | Min spread EUR/USD 1.1 pips, GBP/USD 1.0, USD/JPY 1.4. Micro symbols: 0.7 / 0.7 / 0.9. Typical spreads are not published |
| Commission | One fee at the start, as a share of stake × multiplier, minimum 0.02 USD. **It changes during the day** and is the same on real and demo. Base rate (06:00–17:59 UTC, outside big news): **0.0239%** EUR/USD, **0.0203%** GBP/USD, **0.0275%** USD/JPY. Evening and news: 2–12× that (`reports/costs.md`). The KID says it "can be up to 0.5%" | Standard account: "0% commission". Zero Spread account: about 3–4 USD per 100,000 traded, per side (this figure is from a partner help page; see section 6) |
| Overnight / swap fees | **None.** No official page mentions any. A demo trade held 12.3 h over Wednesday night (CFD triple-swap night) was charged nothing beyond the opening commission | Yes, every night at rollover, **triple on Wednesday**. Per lot per night (1 lot = 100,000): EUR/USD long −11.42 / short +2.66 points; GBP/USD −5.43 / −4.13; USD/JPY +9.95 / −21.98 (10 points = 1 pip) |
| Weekend | Unknown: what a weekend gap does to an open contract (see Open questions) | Swap for the weekend is charged on Wednesday. Weekend gaps can jump past a stop |
| Smallest trade | Stake 1 USD (max 2,000). At x100 that is a 100 USD position: 1 pip ≈ 0.009 USD | 0.01 lot = 1,000 units: 1 pip ≈ 0.10 USD. Micro symbols: 0.1 lot of 1,000 = 100 units: 1 pip ≈ 0.01 USD |
| Multipliers / leverage | x100, x200, x300, x500, x800 (real and demo, measured) | Up to 1:1000, fixed per asset; margin 0.10% |
| **How losses are limited** | **Hard cap: you can never lose more than the stake.** Automatic stop out when the loss reaches the stake. Stop loss and take profit are optional. A stop loss is not guaranteed: we saw one close 0.6 pip past its level | **No cap per trade.** Margin call at 100% margin level; stop out at 50%, closing the biggest loser first. A stop loss "is not a guarantee". No guaranteed stop. Negative balance protection is only "at our sole discretion" |
| Trading hours (GMT) | Mon–Fri 00:00–23:59:59, Friday to 20:55; **no new trades 20:55–21:30 daily** (measured, not in the published hours) | Sun 21:10 – Fri 20:55, daily break 20:59–21:10 |
| Minimum deposit | 5 USD balance, 1 USD stake | "minimum deposit of 5 USD" |

What "losses not capped" means in practice: on MT5 the bot's risk module
alone would have to keep each loss within 3% of the balance. Normally the
stop loss does that. But a weekend gap or a news spike can jump past the stop
and lose more than planned. On a 50–100 USD account at high leverage, one bad
gap could hit the 50% kill switch. With Multipliers, the most a trade can lose
is its stake, and that limit holds even through gaps.

## 2. How a Python bot on an Ubuntu VPS could trade each

| | How it works | Difficulty | Main problems |
|---|---|---|---|
| **Multipliers via the Deriv API** (what we have) | Pure Python. REST for a one-time login link, then a WebSocket. Runs under systemd on Ubuntu. Already built and tested on demo in Phases 0–2 | **Easy** (done) | The commission rate, which rises sharply in the evening and around news |
| MT5 + Wine on the Ubuntu VPS | Install MT5 and *Windows* Python under Wine with a virtual screen (Xvfb). The official `MetaTrader5` Python package talks to the terminal | **Hard** | The terminal updates itself and can break under Wine. It needs a watchdog for crashes. The MT5 password sits on disk |
| MT5 Docker image + `mt5linux` bridge | A community image bundles Wine + MT5 + a remote-call bridge. Our Linux Python calls it over a local network port | **Medium** | Community projects, one maintainer each. The image is about 4 GB. The first login needs a web screen (VNC). The ports must be firewalled |
| Windows VPS | Run the official package and terminal natively | **Easy–medium** | Costs more. No systemd, and Windows is harder to look after from a phone. A second deploy path |
| MQL5 Expert Advisor inside MT5 | Trading logic written in MT5's own language, with signals from Python | **Hard** | Splits strategy and risk code across two languages. That breaks our rules: one shared strategy code base, one risk module |
| Deriv API for MT5 trades | **Does not exist.** The API can only move money to and from MT5 accounts | n/a | n/a |

Sources for this section: Deriv API index, MetaTrader5 package pages, MT5
Linux install guide, mt5linux and Docker image pages (see Sources).

## 3. Cost per trade vs a typical move

**Only data dated before 2026-04-28 is used** (Deriv 2025-10-29 to
2026-04-27, Dukascopy 2021-10-27 to 2026-04-27), as the holdout rule
requires.

"Typical move" means the median high-to-low range of one candle on Deriv's
prices (first figure); Dukascopy's longer history comes after the slash.
Cost is per trade, open and close together, in pips, and shown as a share of
the Deriv range.

Assumptions:
- **Multipliers:** commission at the **base rate** (06:00–17:59 UTC, outside
  big news) and at **3× base** (seen around news and at 18:00 UTC). From
  `research/phase2/cost_by_hour.json`. Fills at the mid price: no spread,
  and no swap (confirmed for one weekday night).
- **MT5:** the published minimum spread, plus swap for the average number of
  nights held: 0.015 for a 15m hold, 0.06 for a 1h hold, 0.23 for a 4h hold,
  1.4 for a 1-day hold (counting Wednesday's triple swap). The swap is
  averaged over long and short. The "2× spread" column is a stress case,
  because typical spreads are not published.
- Slippage is left out for both. Backtests add it separately.

| Pair | Candle | Typical range | Multipliers, base rate | Multipliers, 3× base | MT5 Standard | MT5 Standard, 2× spread | MT5 micro |
|---|---|---|---|---|---|---|---|
| EUR/USD | 15m | 5.0 / 5.6 pips | 2.8 pips = **56%** | 8.4 = 167% | 1.1 = 22% | 2.2 = 44% | 0.7 = 14% |
| EUR/USD | 1h | 10.4 / 11.6 | 2.8 = **27%** | 8.4 = 80% | 1.1 = 11% | 2.2 = 21% | 0.7 = 7% |
| EUR/USD | 4h | 21.2 / 23.9 | 2.8 = **13%** | 8.4 = 39% | 1.2 = 6% | 2.3 = 11% | 0.8 = 4% |
| EUR/USD | 1d | 58.6 / 71.2 | 2.8 = **5%** | 8.4 = 14% | 1.7 = 3% | 2.8 = 5% | 1.3 = 2% |
| GBP/USD | 15m | 6.7 / 7.3 | 2.7 = **41%** | 8.2 = 122% | 1.0 = 15% | 2.0 = 30% | 0.7 = 11% |
| GBP/USD | 1h | 14.2 / 14.8 | 2.7 = **19%** | 8.2 = 58% | 1.0 = 7% | 2.0 = 14% | 0.7 = 5% |
| GBP/USD | 4h | 29.8 / 30.6 | 2.7 = **9%** | 8.2 = 27% | 1.1 = 4% | 2.1 = 7% | 0.8 = 3% |
| GBP/USD | 1d | 81.1 / 87.7 | 2.7 = **3%** | 8.2 = 10% | 1.7 = 2% | 2.7 = 3% | 1.4 = 2% |
| USD/JPY | 15m | 8.4 / 9.1 | 4.3 = **51%** | 12.9 = 154% | 1.4 = 17% | 2.8 = 33% | 0.9 = 11% |
| USD/JPY | 1h | 17.5 / 18.9 | 4.3 = **25%** | 12.9 = 74% | 1.4 = 8% | 2.8 = 16% | 0.9 = 5% |
| USD/JPY | 4h | 36.7 / 39.5 | 4.3 = **12%** | 12.9 = 35% | 1.5 = 4% | 2.9 = 8% | 1.0 = 3% |
| USD/JPY | 1d | 92.3 / 113.3 | 4.3 = **5%** | 12.9 = 14% | 2.2 = 2% | 3.6 = 4% | 1.7 = 2% |

How to read this:
- **15m is out on Multipliers.** Even at the base rate, a trade starts about
  half a typical 15-minute candle behind. At 3× it starts more than a whole
  candle behind.
- **1h is workable at the base rate**, with targets several candles wide.
  Costs are 19–27% of one typical hourly candle. In raised hours it is
  hopeless (58–80%).
- **4h and daily are comfortable at the base rate:** 3–13%.
- **So *when* a trade opens matters as much as the timeframe.** Opening only
  in 06:00–17:59 UTC keeps costs at the base rate most of the time.
- **MT5 is still 2–3 times cheaper** than Multipliers at the base rate.
- **The multiplier does not change the cost in pips.** It changes how close
  the stop out is: x100 about 115–150 pips, x200 about 55–75. It also
  changes how much of the stake the commission takes: 2–3% at x100, 4–6% at
  x200 at the base rate.

Rebuild: `python scripts/typical_moves.py`, `python scripts/cost_by_hour.py`,
then `python scripts/product_costs.py`. All three refuse holdout data unless
given `--include-holdout`.

## 4. Recommendation

**Product:** Deriv Multipliers, x100 (x200 at most).

**Timeframes for Phase 4:** 1h and 4h, with daily as a secondary check.
15m is dropped.

**When to open trades:** only 06:00–17:59 UTC.

Why still Multipliers and not MT5, even though MT5 is 2–3× cheaper:
1. **Loss limits.** Multipliers cap each loss at the stake, gaps included.
   That fits the owner's hard limits (3% per trade, 50% kill switch) on a
   50–100 USD account. MT5 has no such cap. Deriv's own documents say stops
   are not guaranteed and negative balance protection is discretionary.
2. **Running it.** Our bot is pure Python on Ubuntu under systemd and already
   works on demo. MT5 needs a Windows program running unattended, plus a
   stored password and a watchdog. That is a lot for an owner who works from
   a phone.
3. **The gap is smaller than first thought.** In normal hours, Multipliers
   cost about 3 pips (4 on USD/JPY), which is workable on 1h and comfortable
   on 4h. The early "8–13 pips" figure came from the expensive hours.
4. **Evidence first.** Paying for MT5 infrastructure only makes sense if a
   strategy passes at MT5 costs and fails at Multiplier costs.

Plan for Phase 3 and Phase 4:
- **Phase 3:** build the backtester with **two cost models** and show both in
  every report:
  - **Main:** Multipliers. Commission at the highest rate measured for the
    UTC hour each trade opens (`research/phase2/cost_by_hour.json`), plus the
    1.5× stress run. Also: no new trades 20:55–21:30 UTC, and the slippage
    and rounding rules in `reports/costs.md` section 10.
  - **For comparison:** MT5 micro, with spread and swap as in section 3.
- **Phase 4:** research **1h and 4h** candles, with daily as a secondary
  check, built from 1m data on UTC boundaries, on all three pairs. New trades
  open only 06:00–17:59 UTC. A strategy passes only on the Multiplier cost
  model, as the rules require.
- **When to come back to MT5:** if a strategy passes on MT5 costs but fails on
  Multiplier costs, write a separate MT5 decision note. It would cover the
  setup, the extra risk module work and a demo period, and needs the owner's
  approval.

Things to know before agreeing:
- **Fewer chances per day.** The entry window is 12 of the 24 hours. On 4h
  and daily candles, reaching 200+ out-of-sample trades across 3 pairs is
  harder; 1h helps here. "No strategy passes" stays a valid result, and the
  rule stays as it is.
- **Holdout size.** The holdout is all Deriv data from 2026-04-28, about 6
  months today and growing. On 1h and 4h that gives a reasonable number of
  trades. On daily candles only a handful per pair, which is why its result
  is reported as "consistent / inconsistent with validation".
- **The cost-by-hour table is from one weekday.** News days can raise other
  hours too. The table is used cautiously (the highest reading per hour,
  plus the 1.5× stress run), and should be re-sampled for a few days during
  the Phase 6 demo run.
- **Weekend holding is still untested.** A daily strategy that holds over
  the weekend is the riskiest case: costs and gap behaviour are unknown
  until Phase 6.

## 5. Proposed CLAUDE.md changes (waiting for approval; not applied)

Already in CLAUDE.md (approved 28 Oct), unchanged:
- the per-hour commission rule
- x100/x200 only (x100 overnight)
- the 1.5× stress test with MT5 costs side by side
- the fixed holdout from 2026-04-28 and the no-overlap rule

The two items marked ON HOLD can now be settled.

**Timeframe** (replaces the current line and its ON HOLD note):
```diff
- - Timeframe: research 15m to 1h candles. No tick scalping unless tests
-   prove it beats costs.
-   ON HOLD until reports/costs.md is done: switch to 4h and daily candles
-   only (built from 1m data on UTC boundaries), dropping 15m and 1h
-   (reports/product_choice.md).
+ - Timeframe: research 1h and 4h candles, with daily as a secondary check
+   (built from 1m data on UTC boundaries). 15m is out: even at the base
+   commission it costs about half a typical 15m candle (reports/costs.md).
+   No tick scalping.
+ - Entry window: new trades open only 06:00-17:59 UTC, where Deriv charges
+   its base commission outside big news. Never 20:55-21:30 UTC (Deriv
+   refuses new trades). Fixed, not a tunable parameter.
```

**Minimum target vs cost** (replaces the ON HOLD item):
```diff
- - ON HOLD until reports/costs.md is done: minimum target vs cost (a
-   strategy's average winning trade at least 3x the round-trip cost:
-   EUR/USD and GBP/USD >= 25 pips, USD/JPY >= 40 pips). The pip figures
-   came from one hour's rate and will be recomputed from the cost-by-hour
-   table.
+ - Minimum target vs cost: a strategy's average winning trade must be at
+   least 3x the average commission its trades actually paid (from the
+   cost-by-hour table). At the base rate that is about 9 pips EUR/USD,
+   8 pips GBP/USD, 13 pips USD/JPY.
```

The rule now compares a strategy's wins with the cost its own trades
actually paid, instead of fixed pip numbers taken from one hour.

## 6. Open questions and caveats

1. **Weekend holding on forex Multipliers.** One weekday night cost nothing
   (demo trade #11). Weekend costs and gap behaviour are still unknown until
   the Phase 6 demo run.
2. **MT5 typical spreads are not published**, only minimums. The figures
   are for an unnamed account type, probably Standard, and come with a note
   that they "may not represent today's trading conditions". If MT5 is ever
   chosen, measure the spread on an MT5 demo account first.
3. **Zero Spread commission** (3–4 USD per 100,000 per side) comes from a
   Deriv *partner* help page. It may describe what partners are paid, not
   what clients are charged.
4. **The Multipliers KID** is published by Deriv's EU entity and contains
   template errors. Its "up to 0.5%" commission ceiling shows the rate can
   rise. We saw up to 0.287% on EUR/USD (12× base) just after the daily
   pause. The cost-by-hour table comes from one weekday and should be
   re-sampled in Phase 6.
5. **MT5 automation details come from community projects**: the Docker image
   and the mt5linux bridge. Their maintenance and reliability are not
   guaranteed. That MT5's saved password is stored unencrypted is an
   assumption, not documented.

## Sources

Deriv (official):
- Trading specifications: spreads, swaps, sizes, leverage and hours, read 2026-10-28. https://deriv.com/en/trading-specifications
- Deriv MT5 account types and the Standard account ("From 0.1 pips", no commission). https://deriv.com/trading-platforms/deriv-mt5
- MT5 account types. https://deriv.com/help-centre-question/what-types-of-mt5-trading-accounts-does-deriv-offer
- Forex market page ("0% commission", minimum deposit 5 USD). https://deriv.com/markets/forex
- Swap calculator (formula, Wednesday triple swap). https://deriv.com/trading-calculators/swap-calculator
- Margin calculator (margin call at 100%). https://deriv.com/trading-calculators/margin-calculator
- Trading Terms (stop out at 50%, overnight rule). https://deriv.com/terms-and-conditions/trading-terms
- Risk Disclosure (stops not guaranteed; Multiplier losses capped at stake). https://deriv.com/terms-and-conditions/risk-disclosure
- General Terms of Use (negative balance protection at Deriv's discretion). https://deriv.com/terms-and-conditions/general-terms-of-use
- Leverage is fixed per asset. https://deriv.com/help-centre-question/change-leverage-on-deriv-mt5-account
- Zero Spread commission rates (partner help centre). https://deriv.com/partners-help-centre-questions/what-are-the-commission-rates-for-trades-on-the-deriv-mt5-zero-spread-account
- Swap-free admin fees (blog, 25 May 2026). https://blog.deriv.com/blog/admin-fees-for-deriv-mt5-swap-free-accounts
- Multipliers page ("A fixed commission is charged when you open a Multipliers trade"). https://deriv.com/options-types/multipliers
- Forex Multipliers Key Information Document (updated 27 July 2026). https://docs.deriv.com/regulatory/kid/kid_deriv_multipliers_forex.pdf
- Gold and silver Multipliers, "without swap fees" (blog, 4 April 2025). https://blog.deriv.com/blog/posts/gold-and-silver-trading-with-multipliers
- Deriv API index (no MT5 trading endpoints). https://developers.deriv.com/llms.txt
- Deriv API wallet transfer to platforms (the only MT5 mention). https://developers.deriv.com/llms/wallet-transfer-platforms.md

MT5 and tooling:
- MetaTrader5 Python package (Windows wheels only). https://pypi.org/project/MetaTrader5/
- MetaTrader5 Python documentation. https://www.mql5.com/en/docs/python_metatrader5
- MT5 on Linux via Wine. https://www.metatrader5.com/en/terminal/help/start_advanced/install_linux
- MT5 command-line and config-file start. https://www.metatrader5.com/en/terminal/help/start_advanced/start
- mt5linux bridge (community). https://pypi.org/project/mt5linux/ and https://github.com/lucas-campagna/mt5linux
- MetaTrader5 Docker image (community). https://github.com/gmag11/MetaTrader5-Docker
- MQL5 SocketCreate (for the Expert Advisor bridge). https://www.mql5.com/en/docs/network/socketcreate
