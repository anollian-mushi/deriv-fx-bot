# Backtest: phase4_f12_lone_mover_reverts_oos

Generated 2026-10-30T16:25Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:LoneMoverReverts (walk-forward schedule)` (1h) Phase 4 family f12, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 92 | -7.72% | 9.26% | 40.2% | 0.944 | -0.775 | 0.819 | 13.58% / 18.44% / 20.09% |
| Multipliers, 1.5x cost (stress) | 92 | -10.88% | 11.86% | 39.1% | 0.918 | -0.784 | 0.752 | 15.51% / 20.32% / 21.83% |
| MT5 micro (comparison only) | 92 | -2.59% | 7.0% | 44.6% | 0.903 | -0.776 | 0.935 | 10.78% / 15.49% / 17.26% |

In plain language:
- **92 trades**, net result **-7.72 USD** on a start of 100.0 (-7.72%). The worst fall from a high point was 9.26%.
- Average commission per trade: 0.0736 USD. Minimum target (average win at least 3x that): **met**.
- **0 trades filled late** (the signal had to wait), on average 0.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {}.
- How trades ended: {'stop_loss': 21, 'strategy_exit': 70, 'stop_out': 1}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
