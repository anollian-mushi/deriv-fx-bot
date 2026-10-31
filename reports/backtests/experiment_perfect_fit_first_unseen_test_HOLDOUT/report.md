# Backtest: experiment_perfect_fit_first_unseen_test

Generated 2026-10-31T09:58Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.perfect_fit:PerfectFit` (1h) EXPERIMENT ONLY: fitted to the pre-holdout period on purpose
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2026-04-28 to 2026-10-30 (INCLUDES THE HOLDOUT)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 386 | -50.02% | 50.41% | 33.9% | 0.29 | -0.345 | 0.432 | 50.47% / 51.75% / 52.35% |
| Multipliers, 1.5x cost (stress) | 277 | -50.02% | 50.29% | 29.2% | 0.269 | -0.366 | 0.303 | 50.19% / 51.09% / 51.72% |
| MT5 micro (comparison only) | 386 | -19.57% | 20.93% | 42.0% | 0.304 | -0.307 | 0.716 | 21.47% / 24.71% / 25.87% |

In plain language:
- **386 trades**, net result **-50.02 USD** on a start of 100.0 (-50.02%). The worst fall from a high point was 50.41%.
- Average commission per trade: 0.1032 USD. Minimum target (average win at least 3x that): **NOT met**.
- **5 trades filled late** (the signal had to wait), on average 8.8 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 6}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 1}.
- How trades ended: {'strategy_exit': 342, 'take_profit': 23, 'stop_loss': 19, 'kill_switch': 2}.
- Kill switch hit: True (stress run: True). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
