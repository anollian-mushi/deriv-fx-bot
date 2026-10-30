# Backtest: phase4_f9_eur_gbp_convergence_oos

Generated 2026-10-30T11:53Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:EurGbpConvergence (walk-forward schedule)` (1d) Phase 4 family f9, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 122 | 6.17% | 7.63% | 51.6% | 1.756 | -1.77 | 1.059 | 19.32% / 27.87% / 32.3% |
| Multipliers, 1.5x cost (stress) | 122 | 2.44% | 9.51% | 50.0% | 1.746 | -1.706 | 1.023 | 20.22% / 28.99% / 33.23% |
| MT5 micro (comparison only) | 122 | 7.61% | 8.26% | 52.5% | 1.74 | -1.789 | 1.073 | 18.94% / 27.34% / 31.65% |

In plain language:
- **122 trades**, net result **6.17 USD** on a start of 100.0 (6.17%). The worst fall from a high point was 7.63%.
- Average commission per trade: 0.0687 USD. Minimum target (average win at least 3x that): **met**.
- **122 trades filled late** (the signal had to wait), on average 360.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 122}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 74}.
- How trades ended: {'strategy_exit': 24, 'forced_deadline': 71, 'stop_out': 10, 'stop_loss': 17}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
