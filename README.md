# deriv-fx-bot

An automated forex trading bot for Deriv, built around Multiplier (up/down)
contracts on EUR/USD, GBP/USD and USD/JPY. Strategies are researched and
backtested first, then run on a demo account, and only moved to real money
once the go-live checklist is complete.

**Status:** Phase 4 strategy research finished after a fourth and final
round: **no strategy passed** (234 variants: 10 rule families in rounds 1-3,
then a machine-learning strategy and 2 original families in round 4; see
[reports/strategy_research.md](reports/strategy_research.md)). An audit of
the pipeline ([reports/audit_phase4.md](reports/audit_phase4.md)) confirmed
it can see an edge and charges costs once. The holdout is still untouched.
No live bot.

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

## Backtesting (Phase 3)

```bash
.venv/bin/python scripts/build_candle_cache.py        # once: cache 1m data (about 40 s)
.venv/bin/python scripts/run_backtest.py \
    --strategy fxbot.strategies.ma_cross_example:MaCrossExample \
    --symbols frxEURUSD --name ma_cross_example_eurusd_1h
```

- Each run makes two passes, one at the measured commission and one at 1.5x
  commission. It also re-prices the same trades at MT5 micro costs, for
  comparison only.
- Output goes to `reports/backtests/<name>/`: `report.md`, `trades.csv`,
  `equity.png`, `metrics.json` and `gate_skips.csv`.
- **Resumable:** progress is saved monthly in `state/backtest/`. If a run
  stops at its time limit (9 minutes by default, exit code 2), run the same
  command again. Use `--restart` to start over.
- **Holdout:** only data before 2026-04-28 is used. `--include-holdout` is
  for the single final test only.

How the engine works:
- **Data:** 1m Dukascopy mid prices before 2026-04-28 and Deriv 1m candles
  from then on. 1h, 4h and daily candles are built on UTC boundaries, and a
  strategy only ever sees closed candles.
- **Costs:** commission comes only from
  `research/phase2/cost_by_hour.json`, for the hour each trade opens. Entry
  slippage is 0.5 pip; stop-loss exits fill 1 pip past the level.
  Take-profit, stop-out and SL-before-TP rules are as in
  `reports/costs.md` section 10.
- **Risk:** every order passes `fxbot.risk` (all CLAUDE.md hard limits plus
  the live cost gate). The calendar is `fxbot.sessions`: entry window,
  daily pause, closed days, closes by 20:30 before a weekend or closed day,
  and x200 closed by 20:50.
- **Delayed signals:** a signal that can't fill at once waits for the first
  allowed minute. It expires after a fixed wait set by the timeframe (1h: 1
  hour, 4h: 4 hours, daily: 12 hours), unless the strategy cancels it first.
  Strategies cannot change the wait.
- **Pair order:** the order in which pairs are checked rotates from minute
  to minute (`fxbot.sessions.pair_order`), so no pair always gets first
  claim on the 2-position limit.
- **Research kill-switch mode:** `--kill-switch observe` records each time
  the kill switch would fire, closes the trades, restarts at the starting
  balance and keeps going, so results cover the whole period. Any firing
  still counts as a fail. The default (`enforce`) stops the run, as live.
- **Walk-forward:** `fxbot.backtest.walkforward.rolling_windows()` splits
  pre-holdout data into train/validation windows.
- **Strategies:** live in `src/fxbot/strategies/`.
  `ma_cross_example.py` is an engine test only, not for trading.

## Strategy research (Phase 4)

```bash
python scripts/research_family.py grid    --family f1   # every variant, full pre-holdout period
python scripts/research_family.py oos     --family f1   # walk-forward picks, stitched out-of-sample run
python scripts/research_family.py luck    --family f1   # 200 random-entry runs (luck check)
python scripts/research_family.py summary --family f1   # pass/fail checks, updates research/log.md
```

- Families f1-f12 (4 rounds) and their declared grids are in `src/fxbot/backtest/research.py`;
  strategy code in `src/fxbot/strategies/families.py`.
- Each stage saves progress and stops before about 9 minutes (exit code 2);
  run it again to continue.
- Results: `research/phase4/<name>/` and `reports/backtests/phase4_<name>_oos/`.
- Luck check: rounds 1-3 match the signal *rate* per (window, pair, hour)
  (`oos_rates.json`; if it predates the 30 Oct audit fix, run `oos` again first).
  Round 4 families use the candidate's own signal days and pairs with a
  coin-toss direction (`oos_signals.json`), 500 runs, 99th percentile.

### Round 4 track A: the machine-learning day strategy

```bash
python scripts/research_ml.py table     # feature rows at every 08:00 UTC close (research/phase4/a1_ml_day/table.npz)
python scripts/research_ml.py fit       # per round: inner 18+6 month selection runs, full refit, test runs
python scripts/research_ml.py oos       # picks (inner score only) and the stitched out-of-sample run
python scripts/research_ml.py luck      # 500 coin-toss runs on the candidate's own signal days
python scripts/research_ml.py summary   # checks, what the picked models learned, log rows
```

- Strategy and features: `src/fxbot/strategies/ml_day.py` (decision 08:00 UTC, exit 20:00).
  Models are saved as `FrozenModel`s: they predict, and any attempt to refit
  raises. The five picked models are in `research/phase4/a1_ml_day/models/`.
- Run the fit and luck stages with `OMP_NUM_THREADS=1` (4 worker processes;
  with more threads each, the gradient-boosting fits crawl).
- Needs `scikit-learn` (pinned in `requirements.txt`).

## Pipeline audit

```bash
python scripts/audit_phase4.py trades      # consistency of every committed OOS trades.csv
python scripts/audit_phase4.py utc         # data is UTC (US jobs-report spike at 13:30 / 12:30)
python scripts/audit_phase4.py cheat       # next-candle cheat control vs random-direction twins
python scripts/audit_phase4.py grossnet    # gross (no cost) vs net, plus an engine no-cost check
python scripts/audit_phase4.py flip        # reversed signals before and after costs
python scripts/audit_phase4.py luck-preview --family f8 --runs 100   # corrected luck check, resumable
```

Diagnostics only (`src/fxbot/backtest/audit.py`, `tests/test_audit_phase4.py`);
nothing in them is a strategy. Results go to `research/audit/`; the report is
`reports/audit_phase4.md`.

## Folders

- `src/fxbot/` the bot's code (see the Repo layout section of CLAUDE.md)
- `scripts/` runnable scripts
- `tests/` automated tests (`pytest`)
- `docs/` API notes and checklists
- `data/` Deriv candle files; `data_external/` other sources (research only)
- `config/` measured contract specs (`contract_specs.yaml`)
- `cache/` built candle arrays for the backtester (not committed)
- `research/` research notes, Phase 2 raw samples and the log of every
  strategy variant tried
- `reports/` backtest and performance reports
- `reviews/` trade exports for reviews
