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

<!-- phase4:f2_trend_breakout start -->

### f2_trend_breakout (4h): 18 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f2_trend_breakout v00 | n=20, sl_atr=1.5, m=10 | 764 | -129.02 | 2 | - |
| 2026-10-30 | f2_trend_breakout v01 | n=20, sl_atr=1.5, m=20 | 748 | -109.93 | 2 | - |
| 2026-10-30 | f2_trend_breakout v02 | n=20, sl_atr=2.5, m=10 | 681 | -132.1 | 2 | 5 |
| 2026-10-30 | f2_trend_breakout v03 | n=20, sl_atr=2.5, m=20 | 658 | -133.82 | 2 | - |
| 2026-10-30 | f2_trend_breakout v04 | n=20, sl_atr=3.5, m=10 | 661 | -134.48 | 2 | - |
| 2026-10-30 | f2_trend_breakout v05 | n=20, sl_atr=3.5, m=20 | 627 | -133.06 | 2 | - |
| 2026-10-30 | f2_trend_breakout v06 | n=55, sl_atr=1.5, m=10 | 474 | -46.74 | 0 | - |
| 2026-10-30 | f2_trend_breakout v07 | n=55, sl_atr=1.5, m=20 | 471 | -44.91 | 0 | 2, 3 |
| 2026-10-30 | f2_trend_breakout v08 | n=55, sl_atr=2.5, m=10 | 442 | -69.48 | 1 | - |
| 2026-10-30 | f2_trend_breakout v09 | n=55, sl_atr=2.5, m=20 | 439 | -74.3 | 1 | - |
| 2026-10-30 | f2_trend_breakout v10 | n=55, sl_atr=3.5, m=10 | 434 | -60.63 | 1 | 1 |
| 2026-10-30 | f2_trend_breakout v11 | n=55, sl_atr=3.5, m=20 | 423 | -53.31 | 1 | - |
| 2026-10-30 | f2_trend_breakout v12 | n=100, sl_atr=1.5, m=10 | 366 | -47.76 | 0 | - |
| 2026-10-30 | f2_trend_breakout v13 | n=100, sl_atr=1.5, m=20 | 364 | -47.84 | 0 | 4 |
| 2026-10-30 | f2_trend_breakout v14 | n=100, sl_atr=2.5, m=10 | 344 | -71.02 | 1 | - |
| 2026-10-30 | f2_trend_breakout v15 | n=100, sl_atr=2.5, m=20 | 340 | -74.67 | 1 | - |
| 2026-10-30 | f2_trend_breakout v16 | n=100, sl_atr=3.5, m=10 | 342 | -71.09 | 1 | - |
| 2026-10-30 | f2_trend_breakout v17 | n=100, sl_atr=3.5, m=20 | 334 | -74.51 | 1 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 266 trades, net -40.83 USD, max drawdown 45.48%, per pair {'frxEURUSD': -22.25, 'frxGBPUSD': -16.2, 'frxUSDJPY': -2.38}, kill events 0, luck check beats p95: False (p95 18.917499999999972). **Candidate: False**. Report: `reports/backtests/phase4_f2_trend_breakout_oos/`, `research/phase4/f2_trend_breakout/`.

<!-- phase4:f2_trend_breakout end -->

<!-- phase4:f2_trend_breakout_1d start -->

### f2_trend_breakout_1d (1d): 12 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f2_trend_breakout_1d v00 | n=10, sl_atr=0.75, m=5 | 327 | -35.1 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v01 | n=10, sl_atr=0.75, m=10 | 327 | -35.1 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v02 | n=10, sl_atr=1.25, m=5 | 318 | -35.45 | 0 | 2, 5 |
| 2026-10-30 | f2_trend_breakout_1d v03 | n=10, sl_atr=1.25, m=10 | 318 | -35.45 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v04 | n=20, sl_atr=0.75, m=5 | 248 | -36.63 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v05 | n=20, sl_atr=0.75, m=10 | 248 | -36.63 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v06 | n=20, sl_atr=1.25, m=5 | 244 | -42.09 | 0 | 4 |
| 2026-10-30 | f2_trend_breakout_1d v07 | n=20, sl_atr=1.25, m=10 | 244 | -42.09 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v08 | n=55, sl_atr=0.75, m=5 | 145 | -31.57 | 0 | 3 |
| 2026-10-30 | f2_trend_breakout_1d v09 | n=55, sl_atr=0.75, m=10 | 145 | -31.57 | 0 | - |
| 2026-10-30 | f2_trend_breakout_1d v10 | n=55, sl_atr=1.25, m=5 | 142 | -29.59 | 0 | 1 |
| 2026-10-30 | f2_trend_breakout_1d v11 | n=55, sl_atr=1.25, m=10 | 142 | -29.59 | 0 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 130 trades, net -26.97 USD, max drawdown 32.04%, per pair {'frxEURUSD': -10.75, 'frxGBPUSD': -5.45, 'frxUSDJPY': -10.77}, kill events 0, luck check beats p95: False (p95 28.161499999999993). **Candidate: False**. Report: `reports/backtests/phase4_f2_trend_breakout_1d_oos/`, `research/phase4/f2_trend_breakout_1d/`.

<!-- phase4:f2_trend_breakout_1d end -->

<!-- phase4:f3_trend_pullback start -->

### f3_trend_pullback (4h): 16 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f3_trend_pullback v00 | trend_len=20, pullback=15, sl_atr=1.5, tp_r=1.5 | 717 | 4.62 | 0 | - |
| 2026-10-30 | f3_trend_pullback v01 | trend_len=20, pullback=15, sl_atr=1.5, tp_r=2.5 | 677 | 86.42 | 0 | - |
| 2026-10-30 | f3_trend_pullback v02 | trend_len=20, pullback=15, sl_atr=2.5, tp_r=1.5 | 575 | 76.24 | 0 | - |
| 2026-10-30 | f3_trend_pullback v03 | trend_len=20, pullback=15, sl_atr=2.5, tp_r=2.5 | 537 | 139.29 | 0 | 1, 2, 3, 4, 5 |
| 2026-10-30 | f3_trend_pullback v04 | trend_len=20, pullback=30, sl_atr=1.5, tp_r=1.5 | 1273 | -83.66 | 1 | - |
| 2026-10-30 | f3_trend_pullback v05 | trend_len=20, pullback=30, sl_atr=1.5, tp_r=2.5 | 1100 | -27.94 | 0 | - |
| 2026-10-30 | f3_trend_pullback v06 | trend_len=20, pullback=30, sl_atr=2.5, tp_r=1.5 | 846 | -4.61 | 0 | - |
| 2026-10-30 | f3_trend_pullback v07 | trend_len=20, pullback=30, sl_atr=2.5, tp_r=2.5 | 751 | 15.05 | 0 | - |
| 2026-10-30 | f3_trend_pullback v08 | trend_len=50, pullback=15, sl_atr=1.5, tp_r=1.5 | 762 | -1.92 | 0 | - |
| 2026-10-30 | f3_trend_pullback v09 | trend_len=50, pullback=15, sl_atr=1.5, tp_r=2.5 | 721 | 44.87 | 0 | - |
| 2026-10-30 | f3_trend_pullback v10 | trend_len=50, pullback=15, sl_atr=2.5, tp_r=1.5 | 600 | 30.65 | 0 | - |
| 2026-10-30 | f3_trend_pullback v11 | trend_len=50, pullback=15, sl_atr=2.5, tp_r=2.5 | 564 | 51.96 | 0 | - |
| 2026-10-30 | f3_trend_pullback v12 | trend_len=50, pullback=30, sl_atr=1.5, tp_r=1.5 | 1315 | -138.65 | 2 | - |
| 2026-10-30 | f3_trend_pullback v13 | trend_len=50, pullback=30, sl_atr=1.5, tp_r=2.5 | 1138 | -89.71 | 1 | - |
| 2026-10-30 | f3_trend_pullback v14 | trend_len=50, pullback=30, sl_atr=2.5, tp_r=1.5 | 866 | -76.26 | 1 | - |
| 2026-10-30 | f3_trend_pullback v15 | trend_len=50, pullback=30, sl_atr=2.5, tp_r=2.5 | 776 | -47.21 | 1 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 309 trades, net 0.7 USD, max drawdown 33.25%, per pair {'frxEURUSD': 19.31, 'frxGBPUSD': 10.98, 'frxUSDJPY': -29.59}, kill events 0, luck check beats p95: False (p95 34.59249999999997). **Candidate: False**. Report: `reports/backtests/phase4_f3_trend_pullback_oos/`, `research/phase4/f3_trend_pullback/`.

<!-- phase4:f3_trend_pullback end -->

<!-- phase4:f3_trend_pullback_1h start -->

### f3_trend_pullback_1h (1h): 8 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f3_trend_pullback_1h v00 | trend_len=20, pullback=15, sl_atr=2.0, tp_r=1.5 | 2307 | -125.12 | 2 | 1, 2, 3, 4 |
| 2026-10-30 | f3_trend_pullback_1h v01 | trend_len=20, pullback=15, sl_atr=2.0, tp_r=2.5 | 2187 | -145.58 | 2 | 5 |
| 2026-10-30 | f3_trend_pullback_1h v02 | trend_len=20, pullback=30, sl_atr=2.0, tp_r=1.5 | 3531 | -270.52 | 5 | - |
| 2026-10-30 | f3_trend_pullback_1h v03 | trend_len=20, pullback=30, sl_atr=2.0, tp_r=2.5 | 3175 | -268.5 | 5 | - |
| 2026-10-30 | f3_trend_pullback_1h v04 | trend_len=50, pullback=15, sl_atr=2.0, tp_r=1.5 | 2271 | -158.46 | 3 | - |
| 2026-10-30 | f3_trend_pullback_1h v05 | trend_len=50, pullback=15, sl_atr=2.0, tp_r=2.5 | 2152 | -178.92 | 3 | - |
| 2026-10-30 | f3_trend_pullback_1h v06 | trend_len=50, pullback=30, sl_atr=2.0, tp_r=1.5 | 3479 | -277.55 | 5 | - |
| 2026-10-30 | f3_trend_pullback_1h v07 | trend_len=50, pullback=30, sl_atr=2.0, tp_r=2.5 | 3134 | -297.83 | 6 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 1251 trades, net -123.27 USD, max drawdown 53.15%, per pair {'frxEURUSD': -47.17, 'frxGBPUSD': -38.11, 'frxUSDJPY': -37.99}, kill events 2, luck check beats p95: False (p95 -59.937000000000005). **Candidate: False**. Report: `reports/backtests/phase4_f3_trend_pullback_1h_oos/`, `research/phase4/f3_trend_pullback_1h/`.

<!-- phase4:f3_trend_pullback_1h end -->
