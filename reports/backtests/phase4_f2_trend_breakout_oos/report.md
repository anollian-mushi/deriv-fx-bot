# Backtest: phase4_f2_trend_breakout_oos

Generated 2026-10-30T08:15Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:TrendBreakout (walk-forward schedule)` (4h) Phase 4 family f2, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 266 | -40.83% | 45.48% | 35.7% | 1.226 | -0.92 | 0.74 | 46.65% / 54.19% / 56.94% |
| Multipliers, 1.5x cost (stress) | 266 | -46.11% | 50.17% | 33.5% | 1.386 | -0.958 | 0.728 | 52.26% / 58.99% / 61.39% |
| MT5 micro (comparison only) | 266 | -33.84% | 39.18% | 36.1% | 1.235 | -0.897 | 0.778 | 41.05% / 49.3% / 52.3% |

In plain language:
- **266 trades**, net result **-40.83 USD** on a start of 100.0 (-40.83%). The worst fall from a high point was 45.48%.
- Average commission per trade: 0.0517 USD. Minimum target (average win at least 3x that): **met**.
- **118 trades filled late** (the signal had to wait), on average 104.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {'cost_gate': 68, 'outside_entry_window': 142, 'max_positions': 28}. The live cost gate blocked **68** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 132}.
- How trades ended: {'stop_out': 3, 'forced_deadline': 133, 'strategy_exit': 30, 'stop_loss': 100}.
- Kill switch hit: False (stress run: True). Research restarts after a kill: 0 (stress run: 1); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
