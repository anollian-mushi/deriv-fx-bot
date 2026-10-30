# Backtest: phase4_f2_trend_breakout_1d_oos

Generated 2026-10-30T08:15Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:TrendBreakout1d (walk-forward schedule)` (1d) Phase 4 family f2, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 130 | -26.97% | 32.04% | 44.6% | 1.297 | -1.419 | 0.736 | 33.68% / 41.66% / 45.36% |
| Multipliers, 1.5x cost (stress) | 130 | -30.04% | 32.91% | 42.3% | 1.309 | -1.361 | 0.706 | 35.71% / 43.43% / 46.73% |
| MT5 micro (comparison only) | 130 | -22.87% | 29.8% | 45.4% | 1.309 | -1.41 | 0.772 | 30.79% / 39.05% / 42.79% |

In plain language:
- **130 trades**, net result **-26.97 USD** on a start of 100.0 (-26.97%). The worst fall from a high point was 32.04%.
- Average commission per trade: 0.0611 USD. Minimum target (average win at least 3x that): **met**.
- **130 trades filled late** (the signal had to wait), on average 360.8 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 150}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 70}.
- How trades ended: {'forced_deadline': 91, 'stop_loss': 29, 'stop_out': 10}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
