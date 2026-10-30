# Backtest: phase4_f1_london_breakout_oos

Generated 2026-10-30T07:56Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:LondonBreakout (walk-forward schedule)` (1h) Phase 4 family f1, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 1256 | -56.3% | 54.95% | 37.3% | 0.714 | -0.496 | 0.856 | 56.92% / 62.86% / 65.06% |
| Multipliers, 1.5x cost (stress) | 1255 | -88.05% | 53.41% | 36.8% | 0.652 | -0.491 | 0.774 | 70.84% / 73.98% / 75.51% |
| MT5 micro (comparison only) | 1256 | -2.98% | 27.18% | 38.3% | 0.737 | -0.462 | 0.992 | 23.94% / 33.27% / 37.23% |

In plain language:
- **1256 trades**, net result **-56.3 USD** on a start of 100.0 (-56.3%). The worst fall from a high point was 54.95%.
- Average commission per trade: 0.0565 USD. Minimum target (average win at least 3x that): **met**.
- **56 trades filled late** (the signal had to wait), on average 38.8 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 229, 'cost_gate': 11}. The live cost gate blocked **11** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 184}.
- How trades ended: {'stop_loss': 664, 'strategy_exit': 376, 'take_profit': 213, 'stop_out': 2, 'kill_switch': 1}.
- Kill switch hit: True (stress run: True). Research restarts after a kill: 1 (stress run: 1); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
