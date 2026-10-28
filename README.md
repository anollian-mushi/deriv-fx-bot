# deriv-fx-bot

An automated forex trading bot for Deriv, built around Multiplier (up/down)
contracts on EUR/USD, GBP/USD and USD/JPY. Strategies are researched and
backtested first, then run on a demo account, and only moved to real money
once the go-live checklist is complete.

**Status:** Phase 0 (project setup and API check). There is no trading code
yet.

- Project rules, risk limits and research standards: [CLAUDE.md](CLAUDE.md)
- Before trading real money: [docs/go_live_checklist.md](docs/go_live_checklist.md)
- How the Deriv API and Multiplier contracts work: [docs/deriv_api_notes.md](docs/deriv_api_notes.md)

## Settings

Settings are read from environment variables first, then from a `.env` file
in the repo folder if one exists. Secrets are never committed, printed or
logged. See [.env.example](.env.example) for the full list.

| Variable | Needed for | Notes |
|---|---|---|
| `DERIV_APP_ID` | account access | your Deriv app ID |
| `DERIV_PAT` | account access | Personal Access Token with the `trade` scope |
| `DERIV_ACCOUNT_ID` | optional | if empty, the demo account is picked automatically |
| `DERIV_MODE` | | `demo` (default) or `real` |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | alerts (later) | |
| `TRADING_ENABLED` | | `false` (default). The bot only places orders when `true` |

## Setup: cloud sessions (claude.ai/code)

1. In the cloud environment settings, add the variables above as environment
   variables. Do not create a `.env` file in the cloud.
2. Make sure the environment's network access allows `api.derivws.com`
   (API) and `developers.deriv.com` (docs).
3. In the session:
   ```bash
   python3.12 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m pytest
   .venv/bin/python scripts/check_public.py
   .venv/bin/python scripts/check_demo_balance.py
   ```

## Setup: Ubuntu VPS

1. Install Python 3.12 and git:
   ```bash
   sudo apt update
   sudo apt install -y python3.12 python3.12-venv git
   ```
   If your Ubuntu version has no `python3.12` package, use the deadsnakes
   PPA (`sudo add-apt-repository ppa:deadsnakes/ppa`) first.
2. Get the code and install the packages:
   ```bash
   git clone https://github.com/anollian-mushi/deriv-fx-bot.git
   cd deriv-fx-bot
   python3.12 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   ```
3. Create the settings file and lock it down so only your user can read it:
   ```bash
   cp .env.example .env
   chmod 600 .env
   nano .env        # fill in the values
   ```
4. Check everything works:
   ```bash
   .venv/bin/python -m pytest
   .venv/bin/python scripts/check_public.py
   .venv/bin/python scripts/check_demo_balance.py
   ```

Running the bot as a systemd service is added in a later phase (`deploy/`).

## Phase 0 check scripts

- `scripts/check_public.py`: no login. Lists active forex symbols and
  confirms the symbols, trading hours, allowed multipliers and a sample
  commission/stop-out quote for EUR/USD, GBP/USD and USD/JPY.
- `scripts/check_demo_balance.py`: logs in to the **demo** account only and
  prints the balance. Refuses real accounts. Never prints the token or the
  one-time connection URL. Places no orders.

## Folders

- `src/fxbot/` the bot's code (see the Repo layout section of CLAUDE.md)
- `scripts/` runnable scripts
- `tests/` automated tests (`pytest`)
- `docs/` API notes and checklists
- `data/` compressed daily candle files
- `research/` research notes and the log of every strategy variant tried
- `reports/` backtest and performance reports
- `reviews/` trade exports for reviews
