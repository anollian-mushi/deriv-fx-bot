# Backtest: phase4_f4_mean_reversion_4h_oos

Generated 2026-10-30T09:25Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:MeanReversion4h (walk-forward schedule)` (4h) Phase 4 family f4, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 167 | -10.14% | 26.28% | 47.3% | 1.463 | -1.428 | 0.919 | 24.66% / 34.05% / 38.39% |
| Multipliers, 1.5x cost (stress) | 167 | -15.37% | 29.84% | 45.5% | 1.446 | -1.377 | 0.877 | 27.03% / 36.31% / 40.26% |
| MT5 micro (comparison only) | 167 | -5.74% | 21.85% | 47.3% | 1.489 | -1.402 | 0.953 | 22.65% / 31.81% / 36.08% |

In plain language:
- **167 trades**, net result **-10.14 USD** on a start of 100.0 (-10.14%). The worst fall from a high point was 26.28%.
- Average commission per trade: 0.0725 USD. Minimum target (average win at least 3x that): **met**.
- **72 trades filled late** (the signal had to wait), on average 106.9 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 11, 'outside_entry_window': 100, 'cost_gate': 25}. The live cost gate blocked **25** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 74}.
- How trades ended: {'forced_deadline': 43, 'strategy_exit': 50, 'stop_loss': 52, 'take_profit': 19, 'stop_out': 3}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
