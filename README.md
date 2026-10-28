# deriv-fx-bot

An automated forex trading bot for Deriv, built around Multiplier (up/down)
contracts on EUR/USD, GBP/USD and USD/JPY. The project is in its setup phase:
no trading code exists yet. Strategies are researched and backtested first,
then run on a demo account, and only moved to real money once the go-live
checklist is complete.

- Project rules, risk limits and research standards: [CLAUDE.md](CLAUDE.md)
- Before trading real money: [docs/go_live_checklist.md](docs/go_live_checklist.md)

## Settings

Secrets are never committed. Copy `.env.example` to `.env` on the VPS and fill
in the values, or set them as environment variables in cloud sessions.

## Folders

- `data/` compressed daily candle files
- `research/` research notes and the log of every strategy variant tried
- `reports/` backtest and performance reports
- `reviews/` trade exports for reviews
- `docs/` checklists and documentation
