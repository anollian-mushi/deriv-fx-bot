# Deriv FX Multiplier Bot

## Goal
Research, build and run an automated forex trading bot on Deriv using
Multiplier contracts. The owner is new to trading: explain decisions in
plain language in every report.

## Fixed decisions
- API: the current Deriv API at https://developers.deriv.com. Public
  WebSocket for market data; PAT + Deriv-App-ID header for REST; trading
  WebSocket reached via an OTP URL; separate demo and real endpoints.
  Read the current docs before writing API code. Do not copy old
  ws.derivws.com/websockets/v3 tutorials.
- Market: forex majors EUR/USD, GBP/USD, USD/JPY (exact symbols from
  active_symbols).
- Contract: Multipliers (up/down). Model commission, stop out, take profit
  and stop loss exactly as Deriv documents them.
- Contract rules come from config/contract_specs.yaml (measured).
  Backtests take commission ONLY from research/phase2/cost_by_hour.json,
  at the rate for the UTC hour each trade opens. The commission medians
  in config/contract_specs.yaml mix different hours and must never be
  used for pricing. Real and demo charge the same rate at the same
  moment; the rate changes during the day and around news.
- Timeframe: research 1h and 4h candles, with daily as a secondary check
  (built from 1m data on UTC boundaries). 15m is out: even at the base
  commission it costs about half a typical 15m candle (reports/costs.md).
  No tick scalping.
- Entry window: new trades open only 06:00-17:59 UTC, where Deriv charges
  its base commission outside big news. Never 20:55-21:30 UTC (Deriv
  refuses new trades). Fixed, not a tunable parameter. PROVISIONAL: it was
  measured between the European (25 Oct) and US (1 Nov) clock changes and
  is re-checked after 1 Nov (see Research rules).
- Stack: Python 3.12, pytest, Ubuntu VPS with systemd, Telegram for
  alerts and control.
- Data: candles as compressed daily files in data/. No raw ticks in git.
  No file over 50 MB. Report total repo size after data changes.

## Hard risk limits (set by the owner)
Never change, loosen or work around these without explicit approval.
- Starting capital: 50 to 100 USD.
- Kill switch: equity at or below 50% of starting balance -> close all
  positions, stop trading, alert Telegram, require a manual restart.
- Max risk per trade: 3% of current balance (stake = max loss). Pick the
  real value from testing, within this cap and Deriv's minimum stake.
- Daily loss limit: 10% of the start-of-day balance -> no new trades until
  the next UTC day.
- Max open positions: 2, and at most 1 per pair.
- Multiplier: x100 or x200 only (x100 for trades held overnight), chosen
  by testing. Never raise size after losses: no martingale, no averaging
  down, no grids.
- Live cost gate: before every buy, the risk module reads the commission
  rate in the quote and skips the trade if it is above 1.5x that pair's
  base rate (EUR/USD 0.0239%, GBP/USD 0.0203%, USD/JPY 0.0275%). Every
  skip is logged with the rate seen.
- No weekend holding until the Phase 6 weekend test: every open trade is
  closed by Friday 20:30 UTC. The backtester enforces the same rule.
- Orders only when TRADING_ENABLED=true. Real money only when the owner
  sets DERIV_MODE=real.
- All limits live in a separate risk module. Every order passes through
  it; strategy code cannot bypass it.

## Research rules
- Every backtest includes Deriv commission, spread and a slippage
  assumption.
- Every backtest also runs at 1.5x the measured commission (Deriv says
  the rate varies with volatility) and shows MT5 costs side by side for
  comparison only. A pass is judged at the measured Multiplier rate.
- Minimum target vs cost: a strategy's average winning trade must be at
  least 3x the average commission its trades actually paid (from the
  cost-by-hour table). At the base rate that is about 9 pips EUR/USD,
  8 pips GBP/USD, 13 pips USD/JPY.
- Clock-change re-check: in the week after 1 Nov, re-sample 05:00-07:00
  and 12:00-19:00 UTC on two weekdays (quotes only). Report whether the
  cheap window moved and whether 12:00-13:59 is raised every day or only
  on news days, and update cost_by_hour.json. Runs alongside Phase 3 and
  does not block it.
- Split data into train, validation and a final holdout.
- Holdout: all Deriv data from 2026-04-28 onward. This start date is fixed
  and never moves; data collected later is added to the holdout. It is
  used once, at the end, and reported as-is. Because it is still small,
  report its result as "consistent / inconsistent with validation", not
  as proof.
- No overlap: no data of any source dated 2026-04-28 or later may be used
  for training, validation, parameter choices or strategy selection. That
  includes Dukascopy. The holdout period is never seen in any form until
  the single final test.
- Walk-forward validation is required.
- A strategy passes only if it is profitable after costs on at least 2 of
  the 3 pairs, with 200+ out-of-sample trades in total.
- At most 5 tunable parameters per strategy.
- Log every variant tried in research/log.md.
- Report: net return, max drawdown, win rate, average win and loss,
  profit factor, trade count, Monte Carlo drawdowns.
- "No strategy passes" is a valid result. Never tune to pass the holdout.
- Dukascopy history is for training and validation. The final holdout must
  be the most recent Deriv data, because that's the price feed the bot
  actually trades on.

## Engineering rules
- Secrets never go into the repo. Read settings from environment variables
  first, then from a .env file if one exists, so the same code works in
  cloud sessions and on the VPS. Never print, log or commit secrets.
- The owner works from a phone in cloud sessions. Keep each command under
  about 10 minutes; split long backtests and downloads into chunks that
  save progress to files and can resume.
- The backtester and the live bot use the same strategy code.
- Tests for contract math and every risk limit.
- The bot survives disconnects: reconnect, fetch a fresh OTP URL, and
  reconcile open positions with Deriv on startup.
- Every signal, order and close goes into a SQLite journal (on the VPS,
  never committed). Trade exports for reviews go in reviews/.
- Commit after each working step with a clear message. Keep README current.
- Show a plan and wait for approval before large changes.

## Repo layout
Folders marked (later) are created in the phase that needs them.
- src/fxbot/config.py: settings loader (env vars first, then .env)
- src/fxbot/deriv/: Deriv API clients (public WS, REST + OTP, trading WS)
- src/fxbot/data/: candle collectors (Deriv, Dukascopy), validation, calendar
- src/fxbot/contracts/ (later): Multiplier contract math
- src/fxbot/backtest/ (later): backtester, costs, walk-forward, Monte Carlo
- src/fxbot/strategies/ (later): strategy code shared by backtest and live
- src/fxbot/risk/ (later): all hard risk limits; every order passes here
- src/fxbot/live/ (later): live bot, reconnect, reconciliation, journal
- src/fxbot/telegram/ (later): alerts and commands
- scripts/: runnable entry points and checks
- deploy/ (later): systemd unit and VPS setup
- tests/: pytest
- docs/: API notes, checklists
- data/<symbol>/<1m|15m|1h>/YYYY-MM-DD.csv.gz: Deriv candles (source=deriv)
- data_external/dukascopy/<symbol>/1m/: Dukascopy mid + spread, research only
- .github/workflows/: daily Deriv collection, manual Dukascopy backfill
- reports/: backtest and data quality reports
- research/: research notes and log.md; reviews/: trade exports
