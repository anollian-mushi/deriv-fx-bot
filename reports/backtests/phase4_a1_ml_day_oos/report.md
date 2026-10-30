# Backtest: phase4_a1_ml_day_oos

Generated 2026-10-30T15:59Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.ml_day:MLDay (walk-forward schedule, model retrained per round)` (1h) Round 4 track A, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 612 | -32.16% | 46.23% | 46.2% | 0.715 | -0.713 | 0.863 | 41.12% / 49.31% / 52.76% |
| Multipliers, 1.5x cost (stress) | 612 | -46.56% | 54.08% | 44.3% | 0.643 | -0.647 | 0.789 | 51.35% / 57.48% / 59.6% |
| MT5 micro (comparison only) | 612 | -4.88% | 29.71% | 48.4% | 0.727 | -0.696 | 0.978 | 24.7% / 34.37% / 38.7% |

In plain language:
- **612 trades**, net result **-32.16 USD** on a start of 100.0 (-32.16%). The worst fall from a high point was 46.23%.
- Average commission per trade: 0.0606 USD. Minimum target (average win at least 3x that): **met**.
- **0 trades filled late** (the signal had to wait), on average 0.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {'max_positions': 48}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 48}.
- How trades ended: {'strategy_exit': 596, 'stop_out': 16}.
- Kill switch hit: False (stress run: False). Research restarts after a kill: 0 (stress run: 0); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
