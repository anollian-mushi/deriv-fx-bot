# Backtest: ma_cross_example_eurusd_1h

Generated 2026-10-30T07:26Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.ma_cross_example:MaCrossExample` (1h) ENGINE TEST ONLY, NOT FOR TRADING
- Pairs: frxEURUSD
- Period: 2021-10-27 to 2026-04-27 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 368 | -50.0% | 54.8% | 37.0% | 0.977 | -0.788 | 0.727 | 54.06% / 60.52% / 63.35% |
| Multipliers, 1.5x cost (stress) | 347 | -50.01% | 54.02% | 36.0% | 0.97 | -0.771 | 0.708 | 54.16% / 60.23% / 62.34% |
| MT5 micro (comparison only) | 368 | -41.98% | 46.97% | 38.0% | 0.963 | -0.775 | 0.762 | 47.27% / 54.66% / 57.67% |

In plain language:
- **368 trades**, ending at **50.0 USD** from 100.0 (-50.0%). The worst fall from a high point was 54.8%.
- Average commission per trade: 0.0517 USD. Minimum target (average win at least 3x that): **met**.
- **213 trades filled late** (the signal had to wait), on average 353.5 minutes after the signal.
- Signals that could not fill at once, by first reason: {'outside_entry_window': 189, 'cost_gate': 28, 'daily_pause': 16}. The live cost gate blocked **28** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 17}.
- How trades ended: {'strategy_exit': 215, 'forced_deadline': 133, 'stop_out': 19, 'kill_switch': 1}.
- Kill switch hit: True (stress run: True).
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
