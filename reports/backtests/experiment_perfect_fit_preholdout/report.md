# Backtest: experiment_perfect_fit_preholdout

Generated 2026-10-31T09:56Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.perfect_fit:PerfectFit` (1h) EXPERIMENT ONLY: fitted to the pre-holdout period on purpose
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2021-10-27 to 2026-04-27 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 5533 | 3870034.7% | 1.29% | 97.8% | 728.701 | -576.698 | 55.118 | 1.61% / 1.74% / 2.16% |
| Multipliers, 1.5x cost (stress) | 5533 | 3604116.2% | 1.44% | 97.7% | 681.071 | -602.137 | 47.762 | 1.68% / 1.89% / 2.31% |
| MT5 micro (comparison only) | 5533 | 4236086.48% | 1.41% | 98.0% | 793.126 | -566.505 | 67.764 | 1.41% / 1.5% / 1.87% |

In plain language:
- **5533 trades**, net result **3870034.7 USD** on a start of 100.0 (3870034.7%). The worst fall from a high point was 1.29%.
- Average commission per trade: 88.4945 USD. Minimum target (average win at least 3x that): **met**.
- **361 trades filled late** (the signal had to wait), on average 23.9 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 364}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 3}.
- How trades ended: {'take_profit': 4280, 'strategy_exit': 1205, 'stop_loss': 48}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
