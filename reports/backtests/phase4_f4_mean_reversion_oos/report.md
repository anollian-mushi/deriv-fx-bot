# Backtest: phase4_f4_mean_reversion_oos

Generated 2026-10-30T09:24Z by `scripts/run_backtest.py`.

- Strategy: `fxbot.strategies.families:MeanReversion (walk-forward schedule)` (1h) Phase 4 family f4, stitched out-of-sample
- Pairs: frxEURUSD, frxGBPUSD, frxUSDJPY
- Period: 2023-10-27 to 2026-04-26 (pre-holdout data only)
- Starting balance: 100.0 USD; all CLAUDE.md risk limits on.

| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) | Profit factor | Monte Carlo drawdown p50 / p95 / p99 |
|---|---|---|---|---|---|---|---|---|
| Multipliers, measured cost | 551 | -61.63% | 50.05% | 39.6% | 0.653 | -0.613 | 0.698 | 57.69% / 60.84% / 62.34% |
| Multipliers, 1.5x cost (stress) | 551 | -76.35% | 50.01% | 38.5% | 0.643 | -0.627 | 0.641 | 64.36% / 66.64% / 68.17% |
| MT5 micro (comparison only) | 551 | -42.78% | 51.48% | 40.7% | 0.667 | -0.588 | 0.777 | 47.07% / 52.73% / 55.21% |

In plain language:
- **551 trades**, net result **-61.63 USD** on a start of 100.0 (-61.63%). The worst fall from a high point was 50.05%.
- Average commission per trade: 0.0544 USD. Minimum target (average win at least 3x that): **met**.
- **74 trades filled late** (the signal had to wait), on average 57.8 minutes after the signal.
- Signals that could not fill at once, by first reason: {'cost_gate': 59, 'outside_entry_window': 233, 'max_positions': 39, 'daily_pause': 15}. The live cost gate blocked **59** signals (`gate_skips.csv`).
- Signals dropped: {'expired': 277, 'kill_switch': 1}.
- How trades ended: {'forced_deadline': 55, 'stop_loss': 253, 'strategy_exit': 129, 'take_profit': 111, 'stop_out': 1, 'kill_switch': 2}.
- Kill switch hit: True (stress run: True). Research restarts after a kill: 1 (stress run: 1); any restart counts as a FAIL.
- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only 5% of orderings beat; it is a better guide to risk than the single historical drawdown.
- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for comparison only; a pass is judged on Multiplier costs.

Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.
