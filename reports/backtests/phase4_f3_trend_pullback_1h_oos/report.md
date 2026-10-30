# Backtest: phase4_f3_trend_pullback_1h_oos

Generated 2026-10-30T08:47Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:TrendPullback1h (walk-forward schedule)` (1h) Phase 4 family f3, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 1251 | -123.27% | 53.15% | 38.5% | 0.662 | -0.575 | 0.721 | 81.53% / 82.94% / 83.58% |
| Multipliers, 1.5x cost (stress) | 1250 | -147.59% | 50.51% | 38.1% | 0.591 | -0.554 | 0.656 | 87.57% / 88.44% / 88.95% |
| MT5 micro (comparison only) | 1251 | -76.57% | 78.67% | 39.4% | 0.683 | -0.546 | 0.815 | 78.82% / 82.18% / 83.49% |

In plain language:
- **1251 trades**, net result **-123.27 USD** on a start of 100.0 (-123.27%). The worst fall from a high point was 53.15%.
- Average commission per trade: 0.0563 USD. Minimum target (average win at least 3x that): **met**.
- **213 trades filled late** (the signal had to wait), on average 53.7 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 842, 'cost_gate': 127, 'daily_pause': 51, 'max_positions': 222}. The live cost gate blocked **127** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 1043}.
- How trades ended: {'stop_loss': 661, 'forced_deadline': 112, 'take_profit': 291, 'strategy_exit': 183, 'stop_out': 1, 'kill_switch': 3}.
- Kill switch hit: True (stress run: True). Research restarts after a kill: 2 (stress run: 3); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
