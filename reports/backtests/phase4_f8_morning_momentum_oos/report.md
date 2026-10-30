# Backtest: phase4_f8_morning_momentum_oos

Generated 2026-10-30T11:22Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:MorningMomentum (walk-forward schedule)` (1h) Phase 4 family f8, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 419 | -23.46% | 30.46% | 43.4% | 0.702 | -0.638 | 0.845 | 30.83% / 38.0% / 40.95% |
| Multipliers, 1.5x cost (stress) | 419 | -34.26% | 39.94% | 41.8% | 0.649 | -0.606 | 0.768 | 38.83% / 44.57% / 46.59% |
| MT5 micro (comparison only) | 419 | -4.26% | 20.7% | 45.1% | 0.72 | -0.61 | 0.97 | 19.37% / 27.03% / 30.72% |

In plain language:
- **419 trades**, net result **-23.46 USD** on a start of 100.0 (-23.46%). The worst fall from a high point was 30.46%.
- Average commission per trade: 0.0599 USD. Minimum target (average win at least 3x that): **met**.
- **1 trades filled late** (the signal had to wait), on average 39.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 34}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 33}.
- How trades ended: {'strategy_exit': 275, 'stop_loss': 142, 'stop_out': 2}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
