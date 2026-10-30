# Backtest: phase4_f5_session_drift_oos

Generated 2026-10-30T09:51Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:SessionDrift (walk-forward schedule)` (1h) Phase 4 family f5, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 1290 | -107.92% | 50.4% | 44.8% | 0.461 | -0.526 | 0.712 | 78.23% / 80.42% / 81.58% |
| Multipliers, 1.5x cost (stress) | 1290 | -141.97% | 52.38% | 43.2% | 0.528 | -0.595 | 0.674 | 86.09% / 87.23% / 87.8% |
| MT5 micro (comparison only) | 1290 | -65.66% | 65.66% | 46.9% | 0.473 | -0.513 | 0.813 | 69.15% / 74.0% / 76.23% |

In plain language:
- **1290 trades**, net result **-107.92 USD** on a start of 100.0 (-107.92%). The worst fall from a high point was 50.4%.
- Average commission per trade: 0.0447 USD. Minimum target (average win at least 3x that): **met**.
- **0 trades filled late** (the signal had to wait), on average 0.0 minutes after the signal.
- Signals that could not fill at once, by first reason: {}. The live cost gate blocked **0** signals (`gate_skips.csv`).
- Signals dropped: {}.
- How trades ended: {'strategy_exit': 1266, 'stop_out': 20, 'kill_switch': 4}.
- Kill switch hit: True (stress run: True). Research restarts after a kill: 2 (stress run: 2); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
