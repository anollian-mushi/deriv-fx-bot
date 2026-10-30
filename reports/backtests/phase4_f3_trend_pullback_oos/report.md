# Backtest: phase4_f3_trend_pullback_oos

Generated 2026-10-30T08:46Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:TrendPullback (walk-forward schedule)` (4h) Phase 4 family f3, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 309 | 0.7% | 33.25% | 47.2% | 2.043 | -1.826 | 1.002 | 31.39% / 43.23% / 48.64% |
| Multipliers, 1.5x cost (stress) | 309 | -9.69% | 36.17% | 46.6% | 1.931 | -1.744 | 0.966 | 34.42% / 46.55% / 51.41% |
| MT5 micro (comparison only) | 309 | 11.39% | 27.13% | 47.6% | 2.058 | -1.797 | 1.039 | 27.89% / 38.97% / 45.11% |

In plain language:
- **309 trades**, net result **0.7 USD** on a start of 100.0 (0.7%). The worst fall from a high point was 33.25%.
- Average commission per trade: 0.0839 USD. Minimum target (average win at least 3x that): **met**.
- **122 trades filled late** (the signal had to wait), on average 102.1 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 160, 'cost_gate': 76, 'max_positions': 52}. The live cost gate blocked **76** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 178}.
- How trades ended: {'stop_loss': 99, 'forced_deadline': 187, 'stop_out': 5, 'take_profit': 18}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
