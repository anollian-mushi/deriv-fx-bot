# Backtest: phase4_f10_shock_day_oos

Generated 2026-10-30T12:23Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:ShockDay (walk-forward schedule)` (1d) Phase 4 family f10, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 103 | -26.09% | 26.93% | 38.8% | 1.258 | -1.213 | 0.659 | 30.69% / 36.45% / 39.62% |
| Multipliers, 1.5x cost (stress) | 103 | -28.74% | 29.49% | 37.9% | 1.239 | -1.204 | 0.627 | 32.74% / 38.13% / 41.31% |
| MT5 micro (comparison only) | 103 | -22.44% | 22.44% | 38.8% | 1.286 | -1.172 | 0.696 | 27.71% / 33.67% / 36.96% |

In plain language:
- **103 trades**, net result **-26.09 USD** on a start of 100.0 (-26.09%). The worst fall from a high point was 26.93%.
- Average commission per trade: 0.0621 USD. Minimum target (average win at least 3x that): **met**.
- **103 trades filled late** (the signal had to wait), on average 360.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 118}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 56}.
- How trades ended: {'strategy_exit': 40, 'stop_loss': 34, 'forced_deadline': 27, 'stop_out': 2}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
