# deriv-fx-bot

An automated forex trading bot for Deriv, built around Multiplier (up/down)
contracts on EUR/USD, GBP/USD and USD/JPY. Strategies are researched and
backtested first, then run on a demo account, and only moved to real money
once the go-live checklist is complete.

**Status:** Phase 2 done (real trading costs and contract rules, see
[reports/costs.md](reports/costs.md)). No strategy or live bot yet.

- Project rules, risk limits and research standards: [CLAUDE.md](CLAUDE.md)
- Before trading real money: [docs/go_live_checklist.md](docs/go_live_checklist.md)
- How the Deriv API and Multiplier contracts work: [docs/deriv_api_notes.md](docs/deriv_api_notes.md)
- What the historical data looks like: [reports/data_quality.md](reports/data_quality.md)
- What a trade really costs: [reports/costs.md](reports/costs.md)
- Multipliers vs MT5, and the research plan: [reports/product_choice.md](reports/product_choice.md)

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

## Historical data

Two sources, kept apart. Every file has a `source` column, and the loaders
refuse to mix sources.

| Folder | Source | What | Use |
|---|---|---|---|
| `data/<symbol>/<1m\|15m\|1h>/YYYY-MM-DD.csv.gz` | Deriv | the bot's own price feed, ~1 year (Deriv keeps a rolling year) | everything, incl. the final holdout |
| `data_external/dukascopy/<symbol>/1m/YYYY-MM-DD.csv.gz` | Dukascopy | mid price + spread, up to 5 years | training and validation only |

One file per UTC day: `epoch,open,high,low,close[,spread],source`, where
`epoch` is the candle start time in UTC seconds. Each folder has a
`_manifest.json` with closed days (holidays), gaps and other per-day checks.

Collecting (both are resumable: if a run stops, run it again):
```bash
.venv/bin/python scripts/collect_candles.py --max-minutes 9      # Deriv
.venv/bin/python scripts/collect_dukascopy.py --max-minutes 9    # Dukascopy
.venv/bin/python scripts/data_quality.py                         # summary tables
```

GitHub Actions:
- **Collect Deriv candles** runs automatically at 00:15 UTC Tuesday to
  Saturday and commits the new day's files. It needs no secrets. If it
  fails, GitHub emails you.
- **Backfill Dukascopy history** is started by hand (Actions tab, "Run
  workflow"). Dukascopy throttles cloud-session downloads heavily, so bulk
  downloads run on GitHub's machines.

## Phase 2 cost scripts

All of these send price quotes only, except `demo_cost_trades.py`.
- `scripts/sample_proposals.py [--demo]`: one quote sample on all pairs,
  multipliers and stakes, written to `research/phase2/`. Without `--demo`
  it uses the public connection, whose rate is not ours.
- `scripts/check_real_quotes.py`: the same quote sample through the real
  account. Quotes only: a guard blocks every other request type. It refuses
  to run with `DERIV_MODE=real`.
- `scripts/demo_cost_trades.py`: small trades on the **demo** account only.
  Needs `TRADING_ENABLED=true`, uses the 1 USD minimum stake and stops at 20
  trades.
- `scripts/build_contract_specs.py`, `scripts/cost_by_hour.py`,
  `scripts/check_stopout.py`: rebuild `config/contract_specs.yaml` and the
  tables in `research/phase2/`.
- `scripts/typical_moves.py`, `scripts/product_costs.py`: typical candle
  moves and cost vs move. They use data before 2026-04-28 only, unless given
  `--include-holdout`.

## Folders

- `src/fxbot/` the bot's code (see the Repo layout section of CLAUDE.md)
- `scripts/` runnable scripts
- `tests/` automated tests (`pytest`)
- `docs/` API notes and checklists
- `data/` Deriv candle files; `data_external/` other sources (research only)
- `config/` measured contract specs (`contract_specs.yaml`)
- `research/` research notes, Phase 2 raw samples and the log of every
  strategy variant tried
- `reports/` backtest and performance reports
- `reviews/` trade exports for reviews
