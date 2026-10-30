# Backtest: phase4_f7_weekly_momentum_tue_oos

Generated 2026-10-30T10:44Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:WeeklyMomentum (walk-forward schedule)` (1d) Phase 4 family f7, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 260 | -32.45% | 49.9% | 43.5% | 2.242 | -1.944 | 0.886 | 48.21% / 59.65% / 63.81% |
| Multipliers, 1.5x cost (stress) | 260 | -37.49% | 51.82% | 43.1% | 2.156 | -1.885 | 0.866 | 50.7% / 61.59% / 65.76% |
| MT5 micro (comparison only) | 260 | -29.53% | 47.47% | 44.6% | 2.192 | -1.971 | 0.896 | 46.59% / 58.52% / 62.72% |

In plain language:
- **260 trades**, net result **-32.45 USD** on a start of 100.0 (-32.45%). The worst fall from a high point was 49.9%.
- Average commission per trade: 0.0678 USD. Minimum target (average win at least 3x that): **met**.
- **260 trades filled late** (the signal had to wait), on average 363.1 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 384}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 124}.
- How trades ended: {'stop_out': 42, 'stop_loss': 61, 'forced_deadline': 157}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
