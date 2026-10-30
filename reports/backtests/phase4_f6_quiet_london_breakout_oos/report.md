# Backtest: phase4_f6_quiet_london_breakout_oos

Generated 2026-10-30T10:10Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:QuietLondonBreakout (walk-forward schedule)` (1h) Phase 4 family f6, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 872 | -39.94% | 44.82% | 30.0% | 0.661 | -0.349 | 0.813 | 43.84% / 49.38% / 52.02% |
| Multipliers, 1.5x cost (stress) | 871 | -61.4% | 50.81% | 29.5% | 0.593 | -0.348 | 0.713 | 57.44% / 60.76% / 62.16% |
| MT5 micro (comparison only) | 872 | -5.35% | 20.17% | 30.6% | 0.686 | -0.312 | 0.972 | 18.84% / 26.3% / 29.25% |

In plain language:
- **872 trades**, net result **-39.94 USD** on a start of 100.0 (-39.94%). The worst fall from a high point was 44.82%.
- Average commission per trade: 0.052 USD. Minimum target (average win at least 3x that): **met**.
- **13 trades filled late** (the signal had to wait), on average 32.3 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 86}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 73}.
- How trades ended: {'stop_loss': 556, 'strategy_exit': 280, 'take_profit': 36}.
- Kill switch hit: False (stress run: True). Research restarts after a kill: 0 (stress run: 1); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
