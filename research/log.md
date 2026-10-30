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

<!-- phase4:f1_london_breakout start -->

### f1_london_breakout (1h): 24 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f1_london_breakout v00 | box_start=0, cutoff=10, sl_frac=0.5, tp_mult=1.0 | 2387 | -166.04 | 3 | - |
| 2026-10-30 | f1_london_breakout v01 | box_start=0, cutoff=10, sl_frac=0.5, tp_mult=1.5 | 2348 | -148.33 | 2 | - |
| 2026-10-30 | f1_london_breakout v02 | box_start=0, cutoff=10, sl_frac=0.5, tp_mult=2.5 | 2326 | -110.05 | 2 | - |
| 2026-10-30 | f1_london_breakout v03 | box_start=0, cutoff=10, sl_frac=1.0, tp_mult=1.0 | 2275 | -152.68 | 3 | - |
| 2026-10-30 | f1_london_breakout v04 | box_start=0, cutoff=10, sl_frac=1.0, tp_mult=1.5 | 2220 | -129.18 | 2 | - |
| 2026-10-30 | f1_london_breakout v05 | box_start=0, cutoff=10, sl_frac=1.0, tp_mult=2.5 | 2184 | -81.82 | 1 | 1, 2, 3, 5 |
| 2026-10-30 | f1_london_breakout v06 | box_start=0, cutoff=15, sl_frac=0.5, tp_mult=1.0 | 3005 | -222.58 | 4 | - |
| 2026-10-30 | f1_london_breakout v07 | box_start=0, cutoff=15, sl_frac=0.5, tp_mult=1.5 | 2957 | -197.77 | 3 | - |
| 2026-10-30 | f1_london_breakout v08 | box_start=0, cutoff=15, sl_frac=0.5, tp_mult=2.5 | 2922 | -164.22 | 3 | - |
| 2026-10-30 | f1_london_breakout v09 | box_start=0, cutoff=15, sl_frac=1.0, tp_mult=1.0 | 2843 | -197.33 | 3 | - |
| 2026-10-30 | f1_london_breakout v10 | box_start=0, cutoff=15, sl_frac=1.0, tp_mult=1.5 | 2756 | -177.06 | 3 | - |
| 2026-10-30 | f1_london_breakout v11 | box_start=0, cutoff=15, sl_frac=1.0, tp_mult=2.5 | 2689 | -131.84 | 2 | - |
| 2026-10-30 | f1_london_breakout v12 | box_start=3, cutoff=10, sl_frac=0.5, tp_mult=1.0 | 2484 | -175.97 | 3 | - |
| 2026-10-30 | f1_london_breakout v13 | box_start=3, cutoff=10, sl_frac=0.5, tp_mult=1.5 | 2456 | -169.88 | 3 | - |
| 2026-10-30 | f1_london_breakout v14 | box_start=3, cutoff=10, sl_frac=0.5, tp_mult=2.5 | 2430 | -166.17 | 3 | - |
| 2026-10-30 | f1_london_breakout v15 | box_start=3, cutoff=10, sl_frac=1.0, tp_mult=1.0 | 2399 | -144.87 | 2 | - |
| 2026-10-30 | f1_london_breakout v16 | box_start=3, cutoff=10, sl_frac=1.0, tp_mult=1.5 | 2347 | -128.84 | 2 | - |
| 2026-10-30 | f1_london_breakout v17 | box_start=3, cutoff=10, sl_frac=1.0, tp_mult=2.5 | 2297 | -106.81 | 2 | - |
| 2026-10-30 | f1_london_breakout v18 | box_start=3, cutoff=15, sl_frac=0.5, tp_mult=1.0 | 2783 | -204.18 | 4 | - |
| 2026-10-30 | f1_london_breakout v19 | box_start=3, cutoff=15, sl_frac=0.5, tp_mult=1.5 | 2756 | -198.95 | 3 | - |
| 2026-10-30 | f1_london_breakout v20 | box_start=3, cutoff=15, sl_frac=0.5, tp_mult=2.5 | 2720 | -191.14 | 3 | - |
| 2026-10-30 | f1_london_breakout v21 | box_start=3, cutoff=15, sl_frac=1.0, tp_mult=1.0 | 2692 | -180.23 | 3 | - |
| 2026-10-30 | f1_london_breakout v22 | box_start=3, cutoff=15, sl_frac=1.0, tp_mult=1.5 | 2634 | -153.56 | 3 | - |
| 2026-10-30 | f1_london_breakout v23 | box_start=3, cutoff=15, sl_frac=1.0, tp_mult=2.5 | 2563 | -132.2 | 2 | 4 |

Stitched OOS (2023-10-27 to 2026-04-26): 1256 trades, net -56.3 USD, max drawdown 54.95%, per pair {'frxEURUSD': -24.53, 'frxGBPUSD': -22.24, 'frxUSDJPY': -9.53}, kill events 1, luck check beats p95: True (p95 -59.582500000000046). **Candidate: False**. Report: `reports/backtests/phase4_f1_london_breakout_oos/`, `research/phase4/f1_london_breakout/`.

<!-- phase4:f1_london_breakout end -->
