# Research log

Every strategy variant tried is logged here (CLAUDE.md research rules), with
its parameters, data period and result, including the ones that fail.

| Date | Strategy / variant | Params | Pairs, timeframe | Data | Result | Report |
|---|---|---|---|---|---|---|
| 2026-10-30 | ma_cross_example (**engine test only, not a research variant, never to be traded**) | fast 20, slow 50, x100, 3% stake, no SL/TP | EUR/USD 1h | Dukascopy 2021-10-27 to 2026-04-27 (pre-holdout) | Loses: -50% after 368 trades, kill switch hit Sept 2024. Shows the engine and every risk rule work; says nothing about strategies | `reports/backtests/ma_cross_example_eurusd_1h/` |

## Phase 4: strategy research (started 2026-10-30)

Rules (CLAUDE.md, plus the owner's 30 Oct decisions):
- Pre-holdout data only: Dukascopy 1m, 2021-10-27 to 2026-04-27.
- Walk-forward: choose on 24 months, test the next 6, step 6 months. Five
  rounds; the out-of-sample (OOS) period is 2023-10-27 to 2026-04-26.
- In each round the variant with the best **net profit / max drawdown** on
  its training window (measured costs, 3 pairs combined) is picked.
- Every grid point below is one variant. The budget is at most 30 per
  family. The timeframe is fixed per sub-grid, not tuned.
- Fixed for all families: x100, 3% stake, kill switch in research
  "observe" mode (any firing = fail).
- Luck check: 200 random-entry runs with the same exits, candle hours and
  signal rate. The strategy must beat their 95th percentile.

### Family 5 directions: set from published research before testing

A currency tends to weaken during its own country's working hours and to
strengthen during foreign working hours:
- Ranaldo, A., "Segmentation and time-of-day patterns in foreign exchange
  markets", Swiss National Bank Working Paper 2007-03
  (https://www.snb.ch/en/publications/research/working-papers/2007/working_paper_2007_03).
  The journal version is listed as Journal of Banking & Finance 33 (2009);
  that reference was not verified online.
- Breedon, F. and Ranaldo, A., "Intraday patterns in FX returns and order
  flow", SNB Working Paper 2011-04
  (https://www.snb.ch/en/publications/research/working-papers/2011/working_paper_2011_04)
  and Queen Mary WP 694 (2012). EBS data 1997-2007. They note that on
  EUR/USD it forms a simple profitable strategy (before our costs). The
  journal version is listed as Journal of Money, Credit and Banking (2013);
  not verified online.

Direction rules (fixed, not from our data):
- Europe-only hours, entry 06:00-11:59 UTC: EUR/USD Down, GBP/USD Down,
  USD/JPY no trade (neither currency is local).
- US-only hours, entry 16:00-17:59 UTC: EUR/USD Up, GBP/USD Up, USD/JPY
  Down.
- 12:00-15:59: Europe and US both open, no direction, no trade.
