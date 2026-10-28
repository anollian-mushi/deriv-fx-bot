# Product choice: Multipliers or MT5 forex CFDs?

Written 2026-10-28, after Phase 2. Research only: no trades, and the real
account was used for price quotes only. Numbers come from:
- our own measurements: `config/contract_specs.yaml`, `research/phase2/`
- Deriv's official pages, listed under Sources at the end
- our candle data: `research/typical_moves.json`, `research/product_costs.json`

Rebuild the tables with `python scripts/typical_moves.py` and
`python scripts/product_costs.py`.

## Correction (2026-10-28, 20:10 UTC): read this first

An earlier version said the real account charges 3 times the demo
commission. **That was wrong.** Checked side by side, three rounds on all
three pairs, real and demo quote **exactly the same rate at the same moment**
(`research/phase2/real_vs_demo.md`). The "3x" came from comparing a demo
sample at 16:35 with a real sample at 18:07: **the rate changes strongly
during the day.**

| UTC time (Wed 28 Oct) | EUR/USD | GBP/USD | USD/JPY | Account |
|---|---|---|---|---|
| 16:35 | 0.0239% | 0.0203% | 0.0275% | demo |
| 18:07 | 0.0717% | 0.0609% | 0.0825% | real |
| 20:01-20:09 | 0.0893% | 0.0743% | 0.1101% | real and demo, identical |

What this changes:
- The cost figures below use the 18:07 rate: about 8 pips (EUR/USD,
  GBP/USD) and 13 pips (USD/JPY). They are **one point in a daily range**:
  - At 16:35, the same trade cost about 2.7 / 2.7 / 4.4 pips.
  - At 20:00, about 10 / 10 / 17 pips.
- **When a strategy trades may matter as much as which timeframe it uses.**
  Trades in the cheap hours could cost a third of the expensive ones.
- The public (no login) connection quotes a different, lower rate. That is
  not what we trade, so the off-hours GitHub samples cannot answer this
  question. Demo-connection samples through the night and tomorrow morning
  will.
- **Section 4 (recommendation) and section 5 (CLAUDE.md changes) are on hold**
  until the cost-by-hour table is in `reports/costs.md` (Thursday morning).
  The MT5 comparison and the integration findings (sections 2 and 6) are
  not affected.

## The short version (written before the correction above)

- **Real Multipliers are expensive** at the 18:07 rate: a trade must move
  about **8 pips** (EUR/USD, GBP/USD) or **13 pips** (USD/JPY) in your favour
  just to break even. That is about one whole typical 1-hour candle. The
  correction above shows this cost depends on the time of day.
- **MT5 CFDs are about 5 to 10 times cheaper per trade.** The cost is the
  spread, from 1.0–1.4 pips (0.7–0.9 on "micro" symbols), plus a small
  overnight swap.
- **But MT5 is a different, riskier product for this project:**
  - Losses are **not capped** at a stake.
  - Deriv's API **cannot trade MT5**.
  - A Python bot on Linux needs the Windows-only MT5 terminal, running under
    Wine or on a Windows server.
- **Recommendation:** stay on **Multipliers**, but research **4h and daily**
  candles only. Use **x100** (x200 at most), with real-account costs.
  - Drop 15m and 1h: real costs eat 65–90% of a typical 1h candle.
  - Every backtest will also report MT5 costs side by side. Then we will know
    if a strategy only works at MT5 prices, and can decide on MT5 with real
    evidence instead of guessing now.

## 1. Costs side by side (EUR/USD, GBP/USD, USD/JPY)

| | **Deriv Multipliers (real account)** | **Deriv MT5 forex CFD** |
|---|---|---|
| Spread | **None.** Entry and exit fill at the mid price (measured on 10 demo trades: entry 0.0–0.5 pip from the quote, sells exactly at the shown price) | Min spread EUR/USD 1.1 pips, GBP/USD 1.0, USD/JPY 1.4. Micro symbols: 0.7 / 0.7 / 0.9. Typical spreads are not published |
| Commission | One fee at the start, as a share of stake × multiplier, minimum 0.02 USD. **It changes during the day** and is the same on real and demo. EUR/USD: 0.0239% at 16:35, 0.0717% at 18:07, 0.0893% at 20:00 UTC. The KID says it "can be up to 0.5%" | Standard account: "0% commission". Zero Spread account: about 3–4 USD per 100,000 traded, per side (this figure is from a partner help page; see section 6) |
| Overnight / swap fees | **None mentioned** in the KID or the Multipliers page; our own API replies show none. **Not yet confirmed for forex**: tonight's demo trade held overnight tests it | Yes, every night at rollover, **triple on Wednesday**. Per lot per night (1 lot = 100,000): EUR/USD long −11.42 / short +2.66 points; GBP/USD −5.43 / −4.13; USD/JPY +9.95 / −21.98 (10 points = 1 pip) |
| Weekend | Unknown: what a weekend gap does to an open contract (see Open questions) | Swap for the weekend is charged on Wednesday. Weekend gaps can jump past a stop |
| Smallest trade | Stake 1 USD (max 2,000). At x100 that is a 100 USD position: 1 pip ≈ 0.009 USD | 0.01 lot = 1,000 units: 1 pip ≈ 0.10 USD. Micro symbols: 0.1 lot of 1,000 = 100 units: 1 pip ≈ 0.01 USD |
| Multipliers / leverage | x100, x200, x300, x500, x800 (real and demo, measured) | Up to 1:1000, fixed per asset; margin 0.10% |
| **How losses are limited** | **Hard cap: you can never lose more than the stake.** Automatic stop out when the loss reaches the stake. Stop loss and take profit are optional. A stop loss is not guaranteed: we saw one close 0.6 pip past its level | **No cap per trade.** Margin call at 100% margin level; stop out at 50%, closing the biggest loser first. A stop loss "is not a guarantee". No guaranteed stop. Negative balance protection is only "at our sole discretion" |
| Trading hours (GMT) | Mon–Fri 00:00–23:59:59, Friday to 20:55 | Sun 21:10 – Fri 20:55, daily break 20:59–21:10 |
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
| **Multipliers via the Deriv API** (what we have) | Pure Python. REST for a one-time login link, then a WebSocket. Runs under systemd on Ubuntu. Already built and tested on demo in Phases 0–2 | **Easy** (done) | The commission rate, which rises sharply at some hours |
| MT5 + Wine on the Ubuntu VPS | Install MT5 and *Windows* Python under Wine with a virtual screen (Xvfb). The official `MetaTrader5` Python package talks to the terminal | **Hard** | The terminal updates itself and can break under Wine. It needs a watchdog for crashes. The MT5 password sits on disk |
| MT5 Docker image + `mt5linux` bridge | A community image bundles Wine + MT5 + a remote-call bridge. Our Linux Python calls it over a local network port | **Medium** | Community projects, one maintainer each. The image is about 4 GB. The first login needs a web screen (VNC). The ports must be firewalled |
| Windows VPS | Run the official package and terminal natively | **Easy–medium** | Costs more. No systemd, and Windows is harder to look after from a phone. A second deploy path |
| MQL5 Expert Advisor inside MT5 | Trading logic written in MT5's own language, with signals from Python | **Hard** | Splits strategy and risk code across two languages. That breaks our rules: one shared strategy code base, one risk module |
| Deriv API for MT5 trades | **Does not exist.** The API can only move money to and from MT5 accounts | n/a | n/a |

Sources for this section: Deriv API index, MetaTrader5 package pages, MT5
Linux install guide, mt5linux and Docker image pages (see Sources).

## 3. Cost per trade vs a typical move

"Typical move" means the median high-to-low range of one candle on Deriv's
prices over the last year. Dukascopy's five-year figure is shown after the
slash; the last year was about 20% quieter than the five-year average. Cost
is per trade, open and close together, in pips, and shown as a share of that
range.

Assumptions:
- **Multipliers:** commission at the real rate, no spread, no swap (still to
  be confirmed).
- **MT5:** the published minimum spread, plus swap for the average number of
  nights held: 0.06 for a 1h hold, 0.23 for a 4h hold, 1.4 for a 1-day hold
  (counting Wednesday's triple swap). The swap is averaged over long and
  short. The "2× spread" column is a stress case, because typical spreads are
  not published.
- Slippage is left out for both. Backtests add it separately.

| Pair | Candle | Typical range | Multipliers (real) | MT5 Standard | MT5 Standard, 2× spread | MT5 micro |
|---|---|---|---|---|---|---|
| EUR/USD | 1h | 9.2 / 11.1 pips | 8.0 pips = **87%** | 1.1 pips = 12% | 2.2 pips = 24% | 0.7 pips = 8% |
| EUR/USD | 4h | 19.1 / 23.0 pips | 8.0 pips = **42%** | 1.2 pips = 6% | 2.3 pips = 12% | 0.8 pips = 4% |
| EUR/USD | 1d | 54.6 / 67.8 pips | 8.0 pips = **15%** | 1.7 pips = 3% | 2.8 pips = 5% | 1.3 pips = 2% |
| GBP/USD | 1h | 12.3 / 14.4 pips | 8.1 pips = **66%** | 1.0 pips = 8% | 2.0 pips = 16% | 0.7 pips = 6% |
| GBP/USD | 4h | 25.3 / 29.5 pips | 8.1 pips = **32%** | 1.1 pips = 4% | 2.1 pips = 8% | 0.8 pips = 3% |
| GBP/USD | 1d | 70.6 / 84.5 pips | 8.1 pips = **11%** | 1.7 pips = 2% | 2.7 pips = 4% | 1.4 pips = 2% |
| USD/JPY | 1h | 14.9 / 18.2 pips | 13.1 pips = **88%** | 1.4 pips = 10% | 2.8 pips = 19% | 0.9 pips = 6% |
| USD/JPY | 4h | 31.7 / 37.9 pips | 13.1 pips = **41%** | 1.5 pips = 5% | 2.9 pips = 9% | 1.0 pips = 3% |
| USD/JPY | 1d | 84.5 / 108.7 pips | 13.1 pips = **15%** | 2.2 pips = 3% | 3.6 pips = 4% | 1.7 pips = 2% |

How to read this:
- **On 1h candles, a real Multiplier trade starts about 70–90% of a typical
  hour's move in the red.** Even a good signal has almost nothing left after
  costs, so 1h (and 15m) are not worth researching on Multipliers.
- **On 4h, costs are about a third to two fifths of a typical candle.** That
  is hard, but a trade that rides 2–3 candles has room.
- **On daily candles, costs are 11–15% of a typical day.** That is the first
  timeframe where Multipliers look workable.
- **MT5 is cheap on every timeframe**, even at double the minimum spread.
  Its costs on 1h are about what Multipliers cost on daily candles.
- **The multiplier does not change the cost in pips.** It changes two other
  things:
  - **How close the stop out is.** x100: about 100–145 pips on the real
    account. x200: 48–66. x500: 14–19, which is less than a typical 4h range.
  - **How big a share of the stake the commission takes.** x100: 6–8%.
    x200: 12–17%. x500: 30–41%.
- **For 4h and daily trades only x100, and maybe x200, make sense.** Higher
  multipliers would be stopped out by normal daily movement.

## 4. Recommendation (ON HOLD, see the correction at the top)

**Product: Deriv Multipliers, real-account costs, x100 (x200 at most).**

Why not switch to MT5 now, even though it is much cheaper:
1. **Loss limits.** Multipliers cap each loss at the stake, gaps included.
   That fits the owner's hard limits (3% per trade, 50% kill switch) on a
   50–100 USD account. MT5 has no such cap. Deriv's own documents say stops
   are not guaranteed and negative balance protection is discretionary.
2. **Running it.** Our bot is pure Python on Ubuntu under systemd and already
   works on demo. MT5 needs a Windows program running unattended, plus a
   stored password and a watchdog. That is a lot for an owner who works from
   a phone.
3. **Evidence first.** We don't know yet whether any strategy has an edge.
   Paying for MT5 infrastructure only makes sense if a strategy passes at
   MT5 costs and fails at Multiplier costs.

Plan for Phase 3 and Phase 4:
- **Phase 3:** build the backtester with **two cost models** and show both in
  every report:
  - **Main:** Multipliers, commission from `config/contract_specs.yaml` at the
    rate for the hour of each trade.
  - **For comparison:** MT5 micro, with spread and swap as in section 3.
- **Phase 4:** research **4h and daily** candles (built from 1m data, on UTC
  boundaries) on all three pairs. A strategy passes only on the Multiplier
  cost model, as the rules already require.
- **When to come back to MT5:** if a strategy passes on MT5 costs but fails on
  Multiplier costs, write a separate MT5 decision note. It would cover the
  setup, the extra risk module work and a demo period, and needs the owner's
  approval.

Things to know before agreeing:
- **Fewer trades.** On 4h and daily candles, reaching 200+ out-of-sample
  trades across 3 pairs is harder. A daily strategy trading about once a week
  per pair makes about 50 trades per pair-year. "No strategy passes" becomes
  more likely. That is a valid result, and the rule should stay as it is.
- **Small final holdout.** The holdout must be the most recent Deriv data:
  the last ~20% of one year, about 50 trading days. On daily candles that is
  only a handful of trades per pair. It should still be used once and
  reported as it is.
- **A daily strategy assumes no overnight fee.** Tonight's demo trade checks
  that. If Multipliers do charge overnight, section 3 must be redone before
  Phase 4.

## 5. Proposed CLAUDE.md changes (ON HOLD; not applied)

**Fixed decisions:** replace the Timeframe line.
```diff
- - Timeframe: research 15m to 1h candles. No tick scalping unless tests
-   prove it beats costs.
+ - Timeframe: research 4h and daily candles (built from 1m data on UTC
+   boundaries). 15m and 1h are out: real-account costs are 65-90% of a
+   typical 1h candle (reports/product_choice.md). No tick scalping.
```

**Fixed decisions:** add to the Contract line.
```diff
  - Contract: Multipliers (up/down). Model commission, stop out, take profit
    and stop loss exactly as Deriv documents them.
+ - Contract costs and rules come from config/contract_specs.yaml (measured).
+   Backtests use the commission rate for the hour each trade opens (it
+   changes during the day; real and demo are the same at the same moment).
```

**Hard risk limits:** narrow the multiplier line. This tightens the limit,
it does not loosen it.
```diff
- - Multiplier: chosen by testing within an allowed range. Never raise size
-   after losses: no martingale, no averaging down, no grids.
+ - Multiplier: x100 or x200 only (x100 for trades held overnight), chosen
+   by testing. Never raise size after losses: no martingale, no averaging
+   down, no grids.
```

**Research rules:** add a minimum target and a cost stress test.
```diff
+ - Minimum target vs cost: a strategy's average winning trade must be at
+   least 3x the round-trip cost (EUR/USD and GBP/USD >= 25 pips, USD/JPY
+   >= 40 pips at today's real rate). Take-profit distances below that are
+   not allowed.
+ - Every backtest also runs at 1.5x the measured commission (Deriv says
+   the rate varies with volatility) and reports MT5 costs side by side for
+   comparison only. A pass is judged on Multiplier costs.
```

The 200+ out-of-sample trades rule, the 2-of-3 pairs rule and the holdout
rule stay unchanged.

## 6. Open questions and caveats

1. **Overnight cost on forex Multipliers.** No official page answers it. The
   1 USD demo trade held overnight tonight (Phase 2) checks the statement.
   Weekend gap behaviour stays open until the Phase 6 demo run.
2. **MT5 typical spreads are not published**, only minimums. The figures
   are for an unnamed account type, probably Standard, and come with a note
   that they "may not represent today's trading conditions". If MT5 is ever
   chosen, measure the spread on an MT5 demo account first.
3. **Zero Spread commission** (3–4 USD per 100,000 per side) comes from a
   Deriv *partner* help page. It may describe what partners are paid, not
   what clients are charged.
4. **The Multipliers KID** is published by Deriv's EU entity and contains
   template errors. Its "up to 0.5%" commission ceiling shows the rate can
   rise. On 2026-10-28 the rate went from 0.024% to 0.089% (EUR/USD) in
   under four hours. The demo samples tonight and tomorrow measure it
   across the day.
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
