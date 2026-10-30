# Backtest: phase4_f11_dollar_catch_up_oos

Generated 2026-10-30T16:24Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:DollarWideCatchUp (walk-forward schedule)` (1h) Phase 4 family f11, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 234 | -27.28% | 30.65% | 49.6% | 0.655 | -0.875 | 0.736 | 31.14% / 36.55% / 39.57% |
| Multipliers, 1.5x cost (stress) | 234 | -32.84% | 35.56% | 47.9% | 0.624 | -0.842 | 0.68 | 35.58% / 40.34% / 43.19% |
| MT5 micro (comparison only) | 234 | -16.32% | 23.41% | 51.7% | 0.674 | -0.866 | 0.833 | 22.73% / 29.09% / 32.3% |

In plain language:
- **234 trades**, net result **-27.28 USD** on a start of 100.0 (-27.28%). The worst fall from a high point was 30.65%.
- Average commission per trade: 0.0626 USD. Minimum target (average win at least 3x that): **met**.
- **0 trades filled late** (the signal had to wait), on average 0.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {}.
- How trades ended: {'strategy_exit': 198, 'stop_out': 6, 'stop_loss': 30}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
