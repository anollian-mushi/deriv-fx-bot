# Research log

Every strategy variant tried is logged here (CLAUDE.md research rules), with
its parameters, data period and result, including the ones that fail.

| Date | Strategy / variant | Params | Pairs, timeframe | Data | Result | Report |
|---|---|---|---|---|---|---|
| 2026-10-30 | ma_cross_example (**engine test only, not a research variant, never to be traded**) | fast 20, slow 50, x100, 3% stake, no SL/TP | EUR/USD 1h | Dukascopy 2021-10-27 to 2026-04-27 (pre-holdout) | Loses: -50% after 368 trades, kill switch hit Sept 2024. Shows the engine and every risk rule work; says nothing about strategies | `reports/backtests/ma_cross_example_eurusd_1h/` |
