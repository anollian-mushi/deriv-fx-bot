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
- Timeframe: research 15m to 1h candles. No tick scalping unless tests
  prove it beats costs.
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
- Multiplier: chosen by testing within an allowed range. Never raise size
  after losses: no martingale, no averaging down, no grids.
- Orders only when TRADING_ENABLED=true. Real money only when the owner
  sets DERIV_MODE=real.
- All limits live in a separate risk module. Every order passes through
  it; strategy code cannot bypass it.

## Research rules
- Every backtest includes Deriv commission, spread and a slippage
  assumption.
- Split data into train, validation and a final holdout (the most recent
  ~20%). The holdout is used once, at the end, and reported as-is.
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
- src/fxbot/data/ (later): candle downloader, daily compressed files
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
- data/: candle files; reports/: backtest reports
- research/: research notes and log.md; reviews/: trade exports
