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

Stitched OOS (2023-10-27 to 2026-04-26): 1256 trades, net -56.3 USD, max drawdown 54.95%, per pair {'frxEURUSD': -24.53, 'frxGBPUSD': -22.24, 'frxUSDJPY': -9.53}, kill events 1, luck check (p95 of 200 random runs = -59.582500000000046): True. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'no_kill_switch', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f1_london_breakout_oos/`, `research/phase4/f1_london_breakout/`.

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

Stitched OOS (2023-10-27 to 2026-04-26): 266 trades, net -40.83 USD, max drawdown 45.48%, per pair {'frxEURUSD': -22.25, 'frxGBPUSD': -16.2, 'frxUSDJPY': -2.38}, kill events 0, luck check (p95 of 200 random runs = 18.917499999999972): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f2_trend_breakout_oos/`, `research/phase4/f2_trend_breakout/`.

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

Stitched OOS (2023-10-27 to 2026-04-26): 130 trades, net -26.97 USD, max drawdown 32.04%, per pair {'frxEURUSD': -10.75, 'frxGBPUSD': -5.45, 'frxUSDJPY': -10.77}, kill events 0, luck check (p95 of 200 random runs = 28.161499999999993): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'oos_trades_200_plus', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f2_trend_breakout_1d_oos/`, `research/phase4/f2_trend_breakout_1d/`.

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

Stitched OOS (2023-10-27 to 2026-04-26): 309 trades, net 0.7 USD, max drawdown 33.25%, per pair {'frxEURUSD': 19.31, 'frxGBPUSD': 10.98, 'frxUSDJPY': -29.59}, kill events 0, luck check (p95 of 200 random runs = 34.59249999999997): False. Failed checks: ['luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f3_trend_pullback_oos/`, `research/phase4/f3_trend_pullback/`.

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

Stitched OOS (2023-10-27 to 2026-04-26): 1251 trades, net -123.27 USD, max drawdown 53.15%, per pair {'frxEURUSD': -47.17, 'frxGBPUSD': -38.11, 'frxUSDJPY': -37.99}, kill events 2, luck check (p95 of 200 random runs = -59.937000000000005): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'no_kill_switch', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f3_trend_pullback_1h_oos/`, `research/phase4/f3_trend_pullback_1h/`.

<!-- phase4:f3_trend_pullback_1h end -->

<!-- phase4:f4_mean_reversion start -->

### f4_mean_reversion (1h): 16 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f4_mean_reversion v00 | length=20, stretch=2.0, er_max=0.2, sl_atr=1.5 | 2904 | -240.12 | 4 | - |
| 2026-10-30 | f4_mean_reversion v01 | length=20, stretch=2.0, er_max=0.2, sl_atr=3.0 | 2167 | -203.04 | 4 | - |
| 2026-10-30 | f4_mean_reversion v02 | length=20, stretch=2.0, er_max=0.35, sl_atr=1.5 | 3818 | -294.41 | 5 | - |
| 2026-10-30 | f4_mean_reversion v03 | length=20, stretch=2.0, er_max=0.35, sl_atr=3.0 | 2710 | -242.24 | 4 | - |
| 2026-10-30 | f4_mean_reversion v04 | length=20, stretch=3.0, er_max=0.2, sl_atr=1.5 | 1113 | -104.69 | 2 | 2 |
| 2026-10-30 | f4_mean_reversion v05 | length=20, stretch=3.0, er_max=0.2, sl_atr=3.0 | 891 | -92.25 | 1 | 1, 3, 4 |
| 2026-10-30 | f4_mean_reversion v06 | length=20, stretch=3.0, er_max=0.35, sl_atr=1.5 | 1671 | -139.11 | 2 | - |
| 2026-10-30 | f4_mean_reversion v07 | length=20, stretch=3.0, er_max=0.35, sl_atr=3.0 | 1285 | -129.2 | 2 | 5 |
| 2026-10-30 | f4_mean_reversion v08 | length=50, stretch=2.0, er_max=0.2, sl_atr=1.5 | 4325 | -286.4 | 5 | - |
| 2026-10-30 | f4_mean_reversion v09 | length=50, stretch=2.0, er_max=0.2, sl_atr=3.0 | 3034 | -214.25 | 4 | - |
| 2026-10-30 | f4_mean_reversion v10 | length=50, stretch=2.0, er_max=0.35, sl_atr=1.5 | 4646 | -307.74 | 6 | - |
| 2026-10-30 | f4_mean_reversion v11 | length=50, stretch=2.0, er_max=0.35, sl_atr=3.0 | 3214 | -219.94 | 4 | - |
| 2026-10-30 | f4_mean_reversion v12 | length=50, stretch=3.0, er_max=0.2, sl_atr=1.5 | 3069 | -190.29 | 3 | - |
| 2026-10-30 | f4_mean_reversion v13 | length=50, stretch=3.0, er_max=0.2, sl_atr=3.0 | 2149 | -184.74 | 3 | - |
| 2026-10-30 | f4_mean_reversion v14 | length=50, stretch=3.0, er_max=0.35, sl_atr=1.5 | 3397 | -219.76 | 4 | - |
| 2026-10-30 | f4_mean_reversion v15 | length=50, stretch=3.0, er_max=0.35, sl_atr=3.0 | 2338 | -192.94 | 4 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 551 trades, net -61.63 USD, max drawdown 50.05%, per pair {'frxEURUSD': -25.77, 'frxGBPUSD': -15.94, 'frxUSDJPY': -19.92}, kill events 1, luck check (p95 of 200 random runs = -21.37900000000004): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'no_kill_switch', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f4_mean_reversion_oos/`, `research/phase4/f4_mean_reversion/`.

<!-- phase4:f4_mean_reversion end -->

<!-- phase4:f4_mean_reversion_4h start -->

### f4_mean_reversion_4h (4h): 8 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f4_mean_reversion_4h v00 | length=20, stretch=2.0, er_max=0.2, sl_atr=2.0 | 721 | -23.9 | 0 | - |
| 2026-10-30 | f4_mean_reversion_4h v01 | length=20, stretch=2.0, er_max=0.35, sl_atr=2.0 | 976 | -76.33 | 1 | - |
| 2026-10-30 | f4_mean_reversion_4h v02 | length=20, stretch=3.0, er_max=0.2, sl_atr=2.0 | 247 | 18.1 | 0 | 1, 2, 3 |
| 2026-10-30 | f4_mean_reversion_4h v03 | length=20, stretch=3.0, er_max=0.35, sl_atr=2.0 | 390 | -14.99 | 0 | 4, 5 |
| 2026-10-30 | f4_mean_reversion_4h v04 | length=50, stretch=2.0, er_max=0.2, sl_atr=2.0 | 1257 | -82.54 | 1 | - |
| 2026-10-30 | f4_mean_reversion_4h v05 | length=50, stretch=2.0, er_max=0.35, sl_atr=2.0 | 1312 | -49.05 | 1 | - |
| 2026-10-30 | f4_mean_reversion_4h v06 | length=50, stretch=3.0, er_max=0.2, sl_atr=2.0 | 827 | -82.4 | 1 | - |
| 2026-10-30 | f4_mean_reversion_4h v07 | length=50, stretch=3.0, er_max=0.35, sl_atr=2.0 | 888 | -51.68 | 1 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 167 trades, net -10.14 USD, max drawdown 26.28%, per pair {'frxEURUSD': -3.13, 'frxGBPUSD': 1.87, 'frxUSDJPY': -8.88}, kill events 0, luck check (p95 of 200 random runs = 7.8689999999999864): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'oos_trades_200_plus', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f4_mean_reversion_4h_oos/`, `research/phase4/f4_mean_reversion_4h/`.

<!-- phase4:f4_mean_reversion_4h end -->

<!-- phase4:f5_session_drift start -->

### f5_session_drift (1h): 30 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f5_session_drift v00 | entry_hour=6, exit_hour=12, stop_pips=0 | 2336 | -92.36 | 1 | 5 |
| 2026-10-30 | f5_session_drift v01 | entry_hour=6, exit_hour=12, stop_pips=20 | 2336 | -140.82 | 2 | - |
| 2026-10-30 | f5_session_drift v02 | entry_hour=6, exit_hour=14, stop_pips=0 | 2336 | -126.04 | 2 | - |
| 2026-10-30 | f5_session_drift v03 | entry_hour=6, exit_hour=14, stop_pips=20 | 2336 | -137.33 | 2 | - |
| 2026-10-30 | f5_session_drift v04 | entry_hour=6, exit_hour=16, stop_pips=0 | 2336 | -126.82 | 2 | 3, 4 |
| 2026-10-30 | f5_session_drift v05 | entry_hour=6, exit_hour=16, stop_pips=20 | 2336 | -119.22 | 2 | - |
| 2026-10-30 | f5_session_drift v06 | entry_hour=8, exit_hour=12, stop_pips=0 | 2336 | -99.86 | 1 | - |
| 2026-10-30 | f5_session_drift v07 | entry_hour=8, exit_hour=12, stop_pips=20 | 2336 | -151.88 | 3 | - |
| 2026-10-30 | f5_session_drift v08 | entry_hour=8, exit_hour=14, stop_pips=0 | 2336 | -126.49 | 2 | 2 |
| 2026-10-30 | f5_session_drift v09 | entry_hour=8, exit_hour=14, stop_pips=20 | 2335 | -145.95 | 2 | - |
| 2026-10-30 | f5_session_drift v10 | entry_hour=8, exit_hour=16, stop_pips=0 | 2336 | -129.54 | 2 | 1 |
| 2026-10-30 | f5_session_drift v11 | entry_hour=8, exit_hour=16, stop_pips=20 | 2336 | -162.8 | 3 | - |
| 2026-10-30 | f5_session_drift v12 | entry_hour=10, exit_hour=12, stop_pips=0 | 2336 | -86.06 | 1 | - |
| 2026-10-30 | f5_session_drift v13 | entry_hour=10, exit_hour=12, stop_pips=20 | 2336 | -96.12 | 1 | - |
| 2026-10-30 | f5_session_drift v14 | entry_hour=10, exit_hour=14, stop_pips=0 | 2336 | -111.14 | 2 | - |
| 2026-10-30 | f5_session_drift v15 | entry_hour=10, exit_hour=14, stop_pips=20 | 2336 | -127.55 | 2 | - |
| 2026-10-30 | f5_session_drift v16 | entry_hour=10, exit_hour=16, stop_pips=0 | 2336 | -114.61 | 2 | - |
| 2026-10-30 | f5_session_drift v17 | entry_hour=10, exit_hour=16, stop_pips=20 | 2336 | -127.48 | 2 | - |
| 2026-10-30 | f5_session_drift v18 | entry_hour=16, exit_hour=19, stop_pips=0 | 2336 | -146.9 | 2 | - |
| 2026-10-30 | f5_session_drift v19 | entry_hour=16, exit_hour=19, stop_pips=20 | 2514 | -179.0 | 3 | - |
| 2026-10-30 | f5_session_drift v20 | entry_hour=16, exit_hour=20, stop_pips=0 | 2336 | -142.87 | 2 | - |
| 2026-10-30 | f5_session_drift v21 | entry_hour=16, exit_hour=20, stop_pips=20 | 2513 | -191.18 | 3 | - |
| 2026-10-30 | f5_session_drift v22 | entry_hour=16, exit_hour=21, stop_pips=0 | 2336 | -140.77 | 2 | - |
| 2026-10-30 | f5_session_drift v23 | entry_hour=16, exit_hour=21, stop_pips=20 | 2513 | -192.22 | 3 | - |
| 2026-10-30 | f5_session_drift v24 | entry_hour=17, exit_hour=19, stop_pips=0 | 2337 | -138.59 | 2 | - |
| 2026-10-30 | f5_session_drift v25 | entry_hour=17, exit_hour=19, stop_pips=20 | 2448 | -158.34 | 3 | - |
| 2026-10-30 | f5_session_drift v26 | entry_hour=17, exit_hour=20, stop_pips=0 | 2336 | -141.03 | 2 | - |
| 2026-10-30 | f5_session_drift v27 | entry_hour=17, exit_hour=20, stop_pips=20 | 2450 | -177.86 | 3 | - |
| 2026-10-30 | f5_session_drift v28 | entry_hour=17, exit_hour=21, stop_pips=0 | 2337 | -137.14 | 2 | - |
| 2026-10-30 | f5_session_drift v29 | entry_hour=17, exit_hour=21, stop_pips=20 | 2448 | -174.3 | 3 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 1290 trades, net -107.92 USD, max drawdown 50.4%, per pair {'frxEURUSD': -55.26, 'frxGBPUSD': -52.66, 'frxUSDJPY': 0}, kill events 2, luck check (p95 of 200 random runs = -39.63000000000003): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'no_kill_switch', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f5_session_drift_oos/`, `research/phase4/f5_session_drift/`.

<!-- phase4:f5_session_drift end -->

<!-- phase4:f6_quiet_london_breakout start -->

### f6_quiet_london_breakout (1h): 8 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f6_quiet_london_breakout v00 | box_max=0.3, tp_atr=0.6, sl_frac=0.5 | 1284 | -81.57 | 1 | - |
| 2026-10-30 | f6_quiet_london_breakout v01 | box_max=0.3, tp_atr=0.6, sl_frac=1.0 | 1251 | -76.96 | 1 | - |
| 2026-10-30 | f6_quiet_london_breakout v02 | box_max=0.3, tp_atr=1.0, sl_frac=0.5 | 1283 | -66.48 | 1 | 1, 2 |
| 2026-10-30 | f6_quiet_london_breakout v03 | box_max=0.3, tp_atr=1.0, sl_frac=1.0 | 1249 | -68.31 | 1 | 3 |
| 2026-10-30 | f6_quiet_london_breakout v04 | box_max=0.5, tp_atr=0.6, sl_frac=0.5 | 2084 | -136.13 | 2 | - |
| 2026-10-30 | f6_quiet_london_breakout v05 | box_max=0.5, tp_atr=0.6, sl_frac=1.0 | 1979 | -105.53 | 2 | - |
| 2026-10-30 | f6_quiet_london_breakout v06 | box_max=0.5, tp_atr=1.0, sl_frac=0.5 | 2079 | -109.27 | 2 | - |
| 2026-10-30 | f6_quiet_london_breakout v07 | box_max=0.5, tp_atr=1.0, sl_frac=1.0 | 1971 | -76.97 | 1 | 4, 5 |

Stitched OOS (2023-10-27 to 2026-04-26): 872 trades, net -39.94 USD, max drawdown 44.82%, per pair {'frxEURUSD': -32.53, 'frxGBPUSD': -9.43, 'frxUSDJPY': 2.02}, kill events 0, luck check (p99 of 500 random runs = -5.40750000000003): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f6_quiet_london_breakout_oos/`, `research/phase4/f6_quiet_london_breakout/`.

<!-- phase4:f6_quiet_london_breakout end -->

<!-- phase4:f7_weekly_momentum_tue start -->

### f7_weekly_momentum_tue (1d): 9 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f7_weekly_momentum_tue v00 | lookback=20, sl_atr=0 | 460 | -56.88 | 1 | - |
| 2026-10-30 | f7_weekly_momentum_tue v01 | lookback=20, sl_atr=1.0 | 462 | -47.17 | 1 | - |
| 2026-10-30 | f7_weekly_momentum_tue v02 | lookback=20, sl_atr=1.5 | 460 | -56.08 | 1 | 3 |
| 2026-10-30 | f7_weekly_momentum_tue v03 | lookback=60, sl_atr=0 | 444 | -57.34 | 1 | 2 |
| 2026-10-30 | f7_weekly_momentum_tue v04 | lookback=60, sl_atr=1.0 | 448 | -47.75 | 1 | 4, 5 |
| 2026-10-30 | f7_weekly_momentum_tue v05 | lookback=60, sl_atr=1.5 | 444 | -58.69 | 1 | 1 |
| 2026-10-30 | f7_weekly_momentum_tue v06 | lookback=120, sl_atr=0 | 421 | -107.46 | 2 | - |
| 2026-10-30 | f7_weekly_momentum_tue v07 | lookback=120, sl_atr=1.0 | 424 | -96.72 | 1 | - |
| 2026-10-30 | f7_weekly_momentum_tue v08 | lookback=120, sl_atr=1.5 | 421 | -100.91 | 2 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 260 trades, net -32.45 USD, max drawdown 49.9%, per pair {'frxEURUSD': 25.95, 'frxGBPUSD': -22.29, 'frxUSDJPY': -36.11}, kill events 0, luck check (p99 of 500 random runs = 81.83969999999998): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f7_weekly_momentum_tue_oos/`, `research/phase4/f7_weekly_momentum_tue/`.

<!-- phase4:f7_weekly_momentum_tue end -->

<!-- phase4:f8_morning_momentum start -->

### f8_morning_momentum (1h): 12 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f8_morning_momentum v00 | entry_hour=9, k=0.25, sl_frac=0.5 | 1286 | -84.55 | 1 | - |
| 2026-10-30 | f8_morning_momentum v01 | entry_hour=9, k=0.25, sl_frac=1.0 | 1264 | -49.29 | 1 | - |
| 2026-10-30 | f8_morning_momentum v02 | entry_hour=9, k=0.4, sl_frac=0.5 | 694 | -40.84 | 0 | - |
| 2026-10-30 | f8_morning_momentum v03 | entry_hour=9, k=0.4, sl_frac=1.0 | 690 | -25.96 | 0 | 3, 4, 5 |
| 2026-10-30 | f8_morning_momentum v04 | entry_hour=10, k=0.25, sl_frac=0.5 | 1406 | -79.19 | 1 | - |
| 2026-10-30 | f8_morning_momentum v05 | entry_hour=10, k=0.25, sl_frac=1.0 | 1375 | -66.79 | 1 | - |
| 2026-10-30 | f8_morning_momentum v06 | entry_hour=10, k=0.4, sl_frac=0.5 | 782 | -49.83 | 0 | 1, 2 |
| 2026-10-30 | f8_morning_momentum v07 | entry_hour=10, k=0.4, sl_frac=1.0 | 775 | -43.04 | 0 | - |
| 2026-10-30 | f8_morning_momentum v08 | entry_hour=11, k=0.25, sl_frac=0.5 | 1492 | -83.15 | 1 | - |
| 2026-10-30 | f8_morning_momentum v09 | entry_hour=11, k=0.25, sl_frac=1.0 | 1460 | -69.51 | 1 | - |
| 2026-10-30 | f8_morning_momentum v10 | entry_hour=11, k=0.4, sl_frac=0.5 | 855 | -45.55 | 0 | - |
| 2026-10-30 | f8_morning_momentum v11 | entry_hour=11, k=0.4, sl_frac=1.0 | 848 | -48.65 | 0 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 419 trades, net -23.46 USD, max drawdown 30.46%, per pair {'frxEURUSD': -8.07, 'frxGBPUSD': -12.41, 'frxUSDJPY': -2.98}, kill events 0, luck check (p99 of 500 random runs = 3.0614999999999895): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f8_morning_momentum_oos/`, `research/phase4/f8_morning_momentum/`.

<!-- phase4:f8_morning_momentum end -->

<!-- phase4:f9_eur_gbp_convergence start -->

### f9_eur_gbp_convergence (1d): 8 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f9_eur_gbp_convergence v00 | length=20, z_in=1.5, hold_days=3 | 279 | -4.71 | 0 | - |
| 2026-10-30 | f9_eur_gbp_convergence v01 | length=20, z_in=1.5, hold_days=8 | 279 | -0.11 | 0 | - |
| 2026-10-30 | f9_eur_gbp_convergence v02 | length=20, z_in=2.0, hold_days=3 | 119 | -16.72 | 0 | - |
| 2026-10-30 | f9_eur_gbp_convergence v03 | length=20, z_in=2.0, hold_days=8 | 119 | -15.2 | 0 | - |
| 2026-10-30 | f9_eur_gbp_convergence v04 | length=60, z_in=1.5, hold_days=3 | 231 | 33.29 | 0 | 1, 3 |
| 2026-10-30 | f9_eur_gbp_convergence v05 | length=60, z_in=1.5, hold_days=8 | 230 | 30.31 | 0 | 2, 4, 5 |
| 2026-10-30 | f9_eur_gbp_convergence v06 | length=60, z_in=2.0, hold_days=3 | 102 | 9.9 | 0 | - |
| 2026-10-30 | f9_eur_gbp_convergence v07 | length=60, z_in=2.0, hold_days=8 | 101 | 13.52 | 0 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 122 trades, net 6.17 USD, max drawdown 7.63%, per pair {'frxEURUSD': -11.83, 'frxGBPUSD': 18.0, 'frxUSDJPY': 0}, kill events 0, luck check (p99 of 500 random runs = 12.958799999999991): False. Failed checks: ['profitable_pairs_2_of_3', 'oos_trades_200_plus', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades']. **Candidate: False**. Report: `reports/backtests/phase4_f9_eur_gbp_convergence_oos/`, `research/phase4/f9_eur_gbp_convergence/`.

<!-- phase4:f9_eur_gbp_convergence end -->

<!-- phase4:f10_shock_day start -->

### f10_shock_day (1d): 8 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f10_shock_day v00 | k=1.25, hold_days=1, sl_atr=0.75 | 428 | -43.27 | 0 | - |
| 2026-10-30 | f10_shock_day v01 | k=1.25, hold_days=1, sl_atr=1.25 | 404 | -39.08 | 0 | - |
| 2026-10-30 | f10_shock_day v02 | k=1.25, hold_days=3, sl_atr=0.75 | 391 | -76.68 | 1 | - |
| 2026-10-30 | f10_shock_day v03 | k=1.25, hold_days=3, sl_atr=1.25 | 358 | -69.06 | 1 | - |
| 2026-10-30 | f10_shock_day v04 | k=1.6, hold_days=1, sl_atr=0.75 | 188 | -16.44 | 0 | 5 |
| 2026-10-30 | f10_shock_day v05 | k=1.6, hold_days=1, sl_atr=1.25 | 183 | -12.4 | 0 | 1, 2 |
| 2026-10-30 | f10_shock_day v06 | k=1.6, hold_days=3, sl_atr=0.75 | 181 | -29.12 | 0 | 3, 4 |
| 2026-10-30 | f10_shock_day v07 | k=1.6, hold_days=3, sl_atr=1.25 | 171 | -39.33 | 0 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 103 trades, net -26.09 USD, max drawdown 26.93%, per pair {'frxEURUSD': 0.04, 'frxGBPUSD': -8.59, 'frxUSDJPY': -17.54}, kill events 0, luck check (p99 of 500 random runs = 32.104999999999976): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'oos_trades_200_plus', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f10_shock_day_oos/`, `research/phase4/f10_shock_day/`.

<!-- phase4:f10_shock_day end -->

### Phase 4 running total (program finished 2026-10-30)

| Round | Families | Variants | Running total | Luck bar |
|---|---|---|---|---|
| 1 | f1-f5 | 132 | 132 | p95 of 200 random runs |
| 2 | f6-f8 (f7: 9 void variants from the Friday-close version, counted) | 38 | 170 | p99 of 500 |
| 3 | f9-f10 | 16 | 186 | p99 of 500 |
| 4 (final) | a1_ml_day (track A, 24 model settings), f11-f12 (track B, 24) | 48 | 234 | p99 of 500 coin-toss runs on the candidate's own signal days |

Result: no strategy passed in any round; the holdout was not used. See reports/strategy_research.md.

## Audit of the Phase 4 pipeline (2026-10-30)

Not variants. Diagnostics only, to check that the research machinery could
have seen an edge (`reports/audit_phase4.md`). Nothing was tested on the
holdout; no strategy or rule was changed.

| Date | What | Data | Result |
|---|---|---|---|
| 2026-10-30 | Cheat control: next-candle look-ahead, 1h, 3 pairs, vs 20 random-direction twins (`audit.Cheat`, never a candidate) | Dukascopy 2024-01-01 to 2024-12-31 (pre-holdout) | +45,805 USD net, beats every twin (twins −93 to −158 USD). Pipeline sees an edge |
| 2026-10-30 | Gross (no-cost) vs net re-pricing of all 13 OOS runs; engine no-cost cross-check on f1, f5, f9 | OOS 2023-10-27 to 2026-04-26 | Costs charged once; gross edge +1.8 to +6.3 pips/trade on f1, f3-4h, f6, f8, f9, below ~4 pips of cost |
| 2026-10-30 | Flipped signals before costs: f5, f1, f8, f3-4h (`audit.flipped`) | OOS span | f5 mirrors within 5%; families with asymmetric stops do not, as expected |
| 2026-10-30 | **Luck-check bug found and fixed**: random runs made 41% (f8) / 30% (f6) fewer trades than the candidate (rate diluted across windows; stops() filters applied twice). Rates now keyed by (window, pair, hour) over tradeable candles | - | Committed luck.json files are stale; f8 and f6 need re-running (f1, f5 for a clean record). Re-runs count as new variants (owner's rule) |
| 2026-10-30 | Preview of the corrected luck check, 100 random runs (not official; `research/audit/luck_preview_*.json`) | OOS span | f8: random trades 246 → 446, share beaten 50% → 89%, still fails (net −23.46, p99 bar −8.27). f6: random trades 614 → 887, share beaten 41% → 68%, still fails (net −39.94, p99 bar −19.92) |

### Cost what-if (2026-10-30, research only, not variants)

Every Phase 4 family's recorded out-of-sample trades, with its walk-forward
settings unchanged, were re-priced at other costs per trade: 0.5 to 5.0 pips
total, a low-cost broker model (1.0 / 1.3 pips plus swap) and no cost at all.
No strategy, setting, rule or data changed, and the holdout was not read.
This adds no variants to the running total (still 186). Result: no family
passes at any cost, including zero. See reports/cost_whatif.md.

## Round 4 (final, 2026-10-30): a learned strategy and two original families

Rules (owner, 30 Oct 2026): horizon 08:00 -> 20:00 UTC; at most 30 variants
per track, each model setting counts; luck check = 500 random runs on the
candidate's own signal days and pairs with a coin-toss direction, beat the
99th percentile; all CLAUDE.md rules and the four "not fake" checks; the
model's scaling is fitted on the training window only, every model is
seeded, saved models are frozen (never retrained). Pre-holdout data only;
the holdout was not touched. Track A: `scripts/research_ml.py`; track B:
`scripts/research_family.py --family f11 / f12`.

<!-- phase4:a1_ml_day start -->

### a1_ml_day (1h, track A, round 4): 24 variants

Each round: the variant is fitted on the first 18 months of the training window and scored on the last 6 (inner validation, real engine, measured costs); the best inner score is picked, refitted on all 24 months and traded on the test window. Test-window columns are shown for every variant for the record (used only for the nearby-settings check, never to pick).

| Date | Variant | Params | Inner-validation net % by round | Test-window net USD by round | Test trades | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | a1_ml_day v00 | model=lr, feats=own, pool=all, margin=0.05 | 35.48 / -20.76 / -18.3 / 4.67 / -11.11 | -5.14 / -10.77 / 4.91 / -9.01 / -5.78 | 832 | - |
| 2026-10-30 | a1_ml_day v01 | model=lr, feats=own, pool=all, margin=0.08 | 19.0 / -2.5 / -19.57 / 4.99 / -9.16 | -0.35 / -17.81 / 33.96 / -4.28 / 2.01 | 480 | 2 |
| 2026-10-30 | a1_ml_day v02 | model=lr, feats=own, pool=all, margin=0.12 | -3.63 / -8.46 / -19.51 / 2.31 / -4.4 | 1.86 / -10.62 / 15.44 / -4.51 / 2.7 | 170 | - |
| 2026-10-30 | a1_ml_day v03 | model=lr, feats=own, pool=pair, margin=0.05 | 25.78 / -14.62 / -23.06 / -16.81 / -21.82 | -8.98 / -27.88 / 6.5 / -21.3 / 5.91 | 958 | - |
| 2026-10-30 | a1_ml_day v04 | model=lr, feats=own, pool=pair, margin=0.08 | 6.93 / -14.19 / -26.96 / -14.07 / -19.25 | -8.58 / -30.81 / 15.18 / -23.7 / -12.09 | 667 | - |
| 2026-10-30 | a1_ml_day v05 | model=lr, feats=own, pool=pair, margin=0.12 | -1.48 / -8.17 / -18.4 / -3.06 / -7.69 | 11.0 / -23.15 / 11.74 / -17.99 / 0.16 | 371 | - |
| 2026-10-30 | a1_ml_day v06 | model=lr, feats=peers, pool=all, margin=0.05 | -7.89 / -24.77 / -25.88 / -11.97 / -7.68 | -15.65 / -16.95 / -0.46 / -12.29 / -9.47 | 921 | - |
| 2026-10-30 | a1_ml_day v07 | model=lr, feats=peers, pool=all, margin=0.08 | 9.47 / -8.49 / -30.56 / 6.51 / -22.86 | -9.71 / -25.75 / 20.3 / -9.48 / 2.29 | 595 | - |
| 2026-10-30 | a1_ml_day v08 | model=lr, feats=peers, pool=all, margin=0.12 | 4.44 / -2.26 / -26.05 / 17.03 / -13.68 | 10.75 / -16.87 / 7.02 / -10.33 / -1.17 | 267 | 4 |
| 2026-10-30 | a1_ml_day v09 | model=lr, feats=peers, pool=pair, margin=0.05 | -5.36 / -12.26 / -34.4 / -15.21 / -12.87 | -24.53 / -31.31 / 9.57 / -2.62 / -5.63 | 1040 | - |
| 2026-10-30 | a1_ml_day v10 | model=lr, feats=peers, pool=pair, margin=0.08 | 9.37 / -14.23 / -38.14 / -6.41 / -10.41 | -7.78 / -22.16 / 18.86 / -13.45 / -6.01 | 804 | - |
| 2026-10-30 | a1_ml_day v11 | model=lr, feats=peers, pool=pair, margin=0.12 | 26.12 / -10.63 / -35.52 / -1.95 / -3.82 | 0.78 / -20.01 / 3.92 / -14.18 / -2.34 | 473 | 1 |
| 2026-10-30 | a1_ml_day v12 | model=gb, feats=own, pool=all, margin=0.05 | 9.02 / -10.93 / -14.99 / -23.85 / -7.93 | -22.6 / -22.09 / -1.98 / -8.95 / -9.33 | 1071 | - |
| 2026-10-30 | a1_ml_day v13 | model=gb, feats=own, pool=all, margin=0.08 | -2.32 / -20.89 / -7.2 / -14.09 / 2.7 | -25.3 / -11.7 / -11.32 / 0.01 / 2.88 | 814 | 3, 5 |
| 2026-10-30 | a1_ml_day v14 | model=gb, feats=own, pool=all, margin=0.12 | -7.28 / -10.78 / -14.34 / -7.6 / -10.43 | -12.93 / -8.75 / 6.24 / 4.85 / -3.93 | 465 | - |
| 2026-10-30 | a1_ml_day v15 | model=gb, feats=own, pool=pair, margin=0.05 | 20.2 / -9.66 / -26.52 / -20.51 / -16.27 | -3.2 / -17.76 / -22.48 / -15.4 / -5.86 | 1173 | - |
| 2026-10-30 | a1_ml_day v16 | model=gb, feats=own, pool=pair, margin=0.08 | 1.81 / -7.62 / -24.61 / -24.36 / -14.2 | -4.73 / -19.02 / -23.15 / -12.62 / -11.29 | 1032 | - |
| 2026-10-30 | a1_ml_day v17 | model=gb, feats=own, pool=pair, margin=0.12 | -3.68 / -3.08 / -30.77 / -25.61 / -16.6 | -11.64 / -23.61 / -14.68 / -13.61 / -4.68 | 796 | - |
| 2026-10-30 | a1_ml_day v18 | model=gb, feats=peers, pool=all, margin=0.05 | 19.31 / -30.63 / -28.22 / -30.2 / -25.98 | -24.9 / -24.56 / 27.12 / -5.19 / 11.24 | 1037 | - |
| 2026-10-30 | a1_ml_day v19 | model=gb, feats=peers, pool=all, margin=0.08 | 8.72 / -28.81 / -9.6 / -25.04 / -18.22 | -22.89 / -23.61 / 21.51 / -13.33 / 8.95 | 768 | - |
| 2026-10-30 | a1_ml_day v20 | model=gb, feats=peers, pool=all, margin=0.12 | -15.76 / -26.11 / -14.83 / -24.34 / -9.22 | -21.62 / -15.14 / 19.98 / -4.01 / -0.58 | 457 | - |
| 2026-10-30 | a1_ml_day v21 | model=gb, feats=peers, pool=pair, margin=0.05 | 16.05 / -28.86 / -30.56 / -7.92 / -42.24 | -26.07 / -24.17 / -12.82 / -28.17 / 8.68 | 1197 | - |
| 2026-10-30 | a1_ml_day v22 | model=gb, feats=peers, pool=pair, margin=0.08 | 6.35 / -22.18 / -32.43 / -7.68 / -42.0 | -23.76 / -24.97 / 0.92 / -24.85 / 7.15 | 1047 | - |
| 2026-10-30 | a1_ml_day v23 | model=gb, feats=peers, pool=pair, margin=0.12 | 7.15 / -14.54 / -30.11 / -3.77 / -32.57 | -14.3 / -27.97 / -0.93 / -25.44 / 5.72 | 808 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 612 trades, net -32.16 USD, max drawdown 46.23%, per pair {'frxEURUSD': -11.59, 'frxGBPUSD': -15.6, 'frxUSDJPY': -4.97}, kill events 0, luck check (p99 of 500 random runs on the candidate's own signal days = 3.5028999999999972): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_a1_ml_day_oos/`, `research/phase4/a1_ml_day/`.

<!-- phase4:a1_ml_day end -->

<!-- phase4:f11_dollar_catch_up start -->

### f11_dollar_catch_up (1h): 12 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f11_dollar_catch_up v00 | decision_hour=8, k=0.2, stop=0.0 | 724 | -25.78 | 0 | - |
| 2026-10-30 | f11_dollar_catch_up v01 | decision_hour=8, k=0.2, stop=0.5 | 724 | -22.9 | 0 | - |
| 2026-10-30 | f11_dollar_catch_up v02 | decision_hour=8, k=0.3, stop=0.0 | 394 | -9.35 | 0 | 1, 5 |
| 2026-10-30 | f11_dollar_catch_up v03 | decision_hour=8, k=0.3, stop=0.5 | 394 | -7.6 | 0 | 2 |
| 2026-10-30 | f11_dollar_catch_up v04 | decision_hour=8, k=0.45, stop=0.0 | 156 | -23.91 | 0 | - |
| 2026-10-30 | f11_dollar_catch_up v05 | decision_hour=8, k=0.45, stop=0.5 | 156 | -23.15 | 0 | - |
| 2026-10-30 | f11_dollar_catch_up v06 | decision_hour=10, k=0.2, stop=0.0 | 876 | -31.99 | 1 | - |
| 2026-10-30 | f11_dollar_catch_up v07 | decision_hour=10, k=0.2, stop=0.5 | 876 | -41.53 | 1 | - |
| 2026-10-30 | f11_dollar_catch_up v08 | decision_hour=10, k=0.3, stop=0.0 | 588 | -38.31 | 0 | - |
| 2026-10-30 | f11_dollar_catch_up v09 | decision_hour=10, k=0.3, stop=0.5 | 588 | -42.55 | 0 | 3 |
| 2026-10-30 | f11_dollar_catch_up v10 | decision_hour=10, k=0.45, stop=0.0 | 272 | -26.91 | 0 | 4 |
| 2026-10-30 | f11_dollar_catch_up v11 | decision_hour=10, k=0.45, stop=0.5 | 272 | -35.46 | 0 | - |

Stitched OOS (2023-10-27 to 2026-04-26): 234 trades, net -27.28 USD, max drawdown 30.65%, per pair {'frxEURUSD': -9.09, 'frxGBPUSD': -3.21, 'frxUSDJPY': -14.98}, kill events 0, luck check (p99 of 500 random runs = 0.9092999999999825): False. Failed checks: ['profitable_pairs_2_of_3', 'net_profit_positive', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f11_dollar_catch_up_oos/`, `research/phase4/f11_dollar_catch_up/`.

<!-- phase4:f11_dollar_catch_up end -->

<!-- phase4:f12_lone_mover_reverts start -->

### f12_lone_mover_reverts (1h): 12 variants

Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-30 | f12_lone_mover_reverts v00 | decision_hour=8, k=0.2, stop=0.0 | 247 | -46.54 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v01 | decision_hour=8, k=0.2, stop=0.5 | 247 | -35.65 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v02 | decision_hour=8, k=0.3, stop=0.0 | 198 | -31.67 | 0 | 4 |
| 2026-10-30 | f12_lone_mover_reverts v03 | decision_hour=8, k=0.3, stop=0.5 | 198 | -23.65 | 0 | 5 |
| 2026-10-30 | f12_lone_mover_reverts v04 | decision_hour=8, k=0.45, stop=0.0 | 127 | -7.82 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v05 | decision_hour=8, k=0.45, stop=0.5 | 127 | -0.68 | 0 | 1 |
| 2026-10-30 | f12_lone_mover_reverts v06 | decision_hour=10, k=0.2, stop=0.0 | 285 | -30.84 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v07 | decision_hour=10, k=0.2, stop=0.5 | 285 | -25.2 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v08 | decision_hour=10, k=0.3, stop=0.0 | 234 | -25.77 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v09 | decision_hour=10, k=0.3, stop=0.5 | 234 | -23.96 | 0 | - |
| 2026-10-30 | f12_lone_mover_reverts v10 | decision_hour=10, k=0.45, stop=0.0 | 164 | -8.47 | 0 | 2 |
| 2026-10-30 | f12_lone_mover_reverts v11 | decision_hour=10, k=0.45, stop=0.5 | 164 | -10.92 | 0 | 3 |

Stitched OOS (2023-10-27 to 2026-04-26): 92 trades, net -7.72 USD, max drawdown 9.26%, per pair {'frxEURUSD': 2.62, 'frxGBPUSD': 0.67, 'frxUSDJPY': -11.01}, kill events 0, luck check (p99 of 500 random runs = 15.434799999999996): False. Failed checks: ['net_profit_positive', 'oos_trades_200_plus', 'luck_check_beats_p95', 'not_one_pair', 'not_one_period', 'not_few_big_trades', 'nearby_settings_work']. **Candidate: False**. Report: `reports/backtests/phase4_f12_lone_mover_reverts_oos/`, `research/phase4/f12_lone_mover_reverts/`.

<!-- phase4:f12_lone_mover_reverts end -->

## Strategy incubator (2026-10-31)

The 2026-04-28 holdout is used up. Deriv data from 2026-10-31 onward is the
untouched period, read only by the incubator (`incubator/README.md`).
Registered on 2026-10-31, frozen at their walk-forward round 5 picks, scored
from 2026-11-01 under the fixed graduation rule in CLAUDE.md. These are not
new research variants; no parameter was chosen for the incubator.

| Date | Candidate | Settings |
|---|---|---|
| 2026-10-31 | f1_london_breakout_r5 | box_start=0, cutoff=10, sl_frac=1.0, tp_mult=2.5 |
| 2026-10-31 | f3_trend_pullback_4h_r5 | trend_len=20, pullback=15, sl_atr=2.5, tp_r=2.5 |
| 2026-10-31 | f9_eur_gbp_convergence_r5 | length=60, z_in=1.5, hold_days=8 |
| 2026-10-31 | a1_ml_day_r5 | gb, own features, pooled, margin=0.08, models/round5_full.pkl |
## Incubator ideas (31 Oct 2026): new candidates for the strategy incubator

Owner's rules for a new candidate (31 Oct 2026): a written reason for the edge
and how it differs from everything Phase 4 and Round 4 tested; expected move per
trade at least 3x the cost (about 4 pips with slippage); at least 1.5 expected
trades per trading day across the three pairs; executable by the bot under
every CLAUDE.md rule; at most 5 settings chosen before testing; a pre-screen on
data before 2026-10-31 only (walk-forward as in Phase 4, extended by one round:
Dukascopy to 2026-04-27, then the used-up Deriv holdout to 2026-10-30; six
rounds, out of sample 2023-10-27 to 2026-10-26) that is profitable before costs
and beats the median of 200 coin-toss runs on the idea's own signals; the
engine's look-ahead test; and no two candidates that are minor variants.
Harness: `src/fxbot/backtest/prescreen.py`, `scripts/prescreen.py`,
`scripts/prescreen_ml.py`. The untouched period is never read (the data layer
raises). Every idea pre-screened has its rows below; ideas rejected on reasoning
alone (never run) are listed first.

### Rejected without a run (fail a check by construction)

| Date | Idea | Why it was not run |
|---|---|---|
| 2026-10-31 | Month-end fix flows (rebalancing into the last fix of the month) | about 1 signal day a month: fails the 1.5 trades/day check |
| 2026-10-31 | Weekend gap fill on Monday morning | at most 3 signals a week, most gaps under 10 pips: fails trades/day |
| 2026-10-31 | Friday afternoon squaring of the week's move | 3 signals a week at most: fails trades/day |
| 2026-10-31 | Carry drift (always long USD/JPY, no overnight fee on Multipliers) | the expected drift over a day or two is 1-3 pips, below 3x cost; a spot position earns no interest, only the swap would, and Deriv pays none; re-entry each Monday after the Friday close |
| 2026-10-31 | Tokyo fix (00:55 UTC) reversal on Japanese settlement days | the reversal is over before the 06:00 entry window opens |
| 2026-10-31 | US jobs report (NFP) continuation | one signal a month, in the 12:00-13:59 cost-gate hours |
| 2026-10-31 | Last-half-hour intraday momentum (Elaut et al. 2018) | the predicted interval is 21:30-22:00 UTC, inside Deriv's pause and 12x commission |
| 2026-10-31 | Beta-residual reversion (a pair's move minus what the other two imply) | a smoother statistic for family 12 (lone mover reverts), which was at the coin-toss median; a minor variant |
| 2026-10-31 | A 3-day reversal rule | the rule the Round 4 models learned; writing it as a rule is tuning to past data, which the owner ruled out |
| 2026-10-31 | Asian-range sweep (Judas swing) | the same mechanism as idea 2 (turtle soup) with a different level: a minor variant |
| 2026-10-31 | EUR/GBP traded directly as a new pair (family 9 with one commission) | family 9 made 0.1 trades a day; one leg instead of two halves the cost but not the frequency |
| 2026-10-31 | High-volatility crosses (GBP/JPY, EUR/JPY) as new pairs | the cost is a percentage of the position, so the move-to-cost ratio improves only by the volatility ratio (about 1.5x), and the commission on crosses is unmeasured; no idea here is specific to a cross, so no new pair was prepared and no Monday cost sampling scheduled |
| 2026-10-31 | Flipped versions of any idea that loses (fade instead of follow) | choosing the direction from our own data is the data-mining the owner ruled out with family 5 |

<!-- prescreen:fix_reversal start -->

### fix_reversal (i1_fix_reversal, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | fix_reversal v00 | k=0.1, hold_hours=2, stop=0.0 | 1843 | -142.7 | 2 | - |
| 2026-10-31 | fix_reversal v01 | k=0.1, hold_hours=2, stop=0.5 | 1852 | -141.38 | 2 | - |
| 2026-10-31 | fix_reversal v02 | k=0.1, hold_hours=4, stop=0.0 | 1843 | -129.56 | 2 | 4 |
| 2026-10-31 | fix_reversal v03 | k=0.1, hold_hours=4, stop=0.5 | 1852 | -133.57 | 2 | - |
| 2026-10-31 | fix_reversal v04 | k=0.2, hold_hours=2, stop=0.0 | 988 | -89.84 | 1 | - |
| 2026-10-31 | fix_reversal v05 | k=0.2, hold_hours=2, stop=0.5 | 989 | -84.34 | 1 | - |
| 2026-10-31 | fix_reversal v06 | k=0.2, hold_hours=4, stop=0.0 | 988 | -90.33 | 1 | 3, 6 |
| 2026-10-31 | fix_reversal v07 | k=0.2, hold_hours=4, stop=0.5 | 989 | -86.17 | 1 | 1, 2, 5 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 670 trades (0.86/day), net -57.17 USD (1.5x: -77.91), gross before costs -11.18 USD (-1.4 pips/trade), avg |move| 18.24 pips vs cost 3.59 pips (ratio 5.09), win rate 40.3%, PF 0.606, kill events 1, per pair net {EURUSD: -17.93 (247), GBPUSD: -15.92 (257), USDJPY: -23.32 (166)}, per window gross [-3.12, -4.53, 2.07, -15.19, 12.18, -2.58]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median', 'no_kill_switch']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/fix_reversal/`.

<!-- prescreen:fix_reversal end -->

<!-- prescreen:turtle_soup start -->

### turtle_soup (i2_turtle_soup, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | turtle_soup v00 | sl_frac=0.25, tp_frac=0.5, cutoff=12 | 561 | -39.05 | 0 | 1, 4 |
| 2026-10-31 | turtle_soup v01 | sl_frac=0.25, tp_frac=0.5, cutoff=17 | 955 | -69.99 | 1 | - |
| 2026-10-31 | turtle_soup v02 | sl_frac=0.25, tp_frac=0.75, cutoff=12 | 561 | -43.37 | 0 | 3, 5 |
| 2026-10-31 | turtle_soup v03 | sl_frac=0.25, tp_frac=0.75, cutoff=17 | 952 | -77.37 | 1 | - |
| 2026-10-31 | turtle_soup v04 | sl_frac=0.5, tp_frac=0.5, cutoff=12 | 558 | -46.67 | 0 | 2, 6 |
| 2026-10-31 | turtle_soup v05 | sl_frac=0.5, tp_frac=0.5, cutoff=17 | 947 | -83.97 | 1 | - |
| 2026-10-31 | turtle_soup v06 | sl_frac=0.5, tp_frac=0.75, cutoff=12 | 557 | -57.09 | 1 | - |
| 2026-10-31 | turtle_soup v07 | sl_frac=0.5, tp_frac=0.75, cutoff=17 | 943 | -94.58 | 1 | - |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 327 trades (0.42/day), net -27.89 USD (1.5x: -35.03), gross before costs 0.23 USD (-0.1 pips/trade), avg |move| 25.67 pips vs cost 4.1 pips (ratio 6.26), win rate 35.8%, PF 0.734, kill events 0, per pair net {EURUSD: -11.98 (112), GBPUSD: -10.19 (137), USDJPY: -5.72 (78)}, per window gross [6.43, 5.06, -0.79, -6.12, 1.19, -5.56]. Luck (200 coin-toss runs on the candidate's own signals): median net -28.29, share beaten 52%. Checks failed: ['c3_trades_per_day_1_5']. **Pre-screen (check 6): PASS**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/turtle_soup/`.

<!-- prescreen:turtle_soup end -->

<!-- prescreen:round_bounce start -->

### round_bounce (i3_round_bounce, 1h): 4 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | round_bounce v00 | sl_frac=0.15, tp_frac=0.3 | 3536 | -298.73 | 5 | - |
| 2026-10-31 | round_bounce v01 | sl_frac=0.15, tp_frac=0.6 | 3367 | -271.18 | 5 | 2 |
| 2026-10-31 | round_bounce v02 | sl_frac=0.3, tp_frac=0.3 | 2894 | -240.65 | 4 | 5, 6 |
| 2026-10-31 | round_bounce v03 | sl_frac=0.3, tp_frac=0.6 | 2663 | -233.31 | 4 | 1, 3, 4 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 1593 trades (2.05/day), net -141.9 USD (1.5x: -184.72), gross before costs -35.96 USD (-0.97 pips/trade), avg |move| 26.93 pips vs cost 4.31 pips (ratio 6.26), win rate 37.5%, PF 0.655, kill events 2, per pair net {EURUSD: -44.11 (373), GBPUSD: -38.41 (525), USDJPY: -59.38 (695)}, per window gross [-1.94, 2.46, -16.92, -5.29, -8.83, -5.45]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c6_gross_positive', 'c6_beats_random_median', 'no_kill_switch']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/round_bounce/`.

<!-- prescreen:round_bounce end -->

<!-- prescreen:round_break start -->

### round_break (i4_round_break, 1h): 4 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | round_break v00 | thru=0.05, sl_frac=0.15 | 2905 | -240.37 | 4 | - |
| 2026-10-31 | round_break v01 | thru=0.05, sl_frac=0.3 | 2370 | -214.5 | 4 | 3 |
| 2026-10-31 | round_break v02 | thru=0.1, sl_frac=0.15 | 1894 | -141.97 | 2 | 1, 2, 4, 5 |
| 2026-10-31 | round_break v03 | thru=0.1, sl_frac=0.3 | 1752 | -160.32 | 3 | 6 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 1088 trades (1.4/day), net -107.6 USD (1.5x: -139.53), gross before costs -28.84 USD (-1.23 pips/trade), avg |move| 24.67 pips vs cost 4.38 pips (ratio 5.64), win rate 28.1%, PF 0.624, kill events 2, per pair net {EURUSD: -43.02 (293), GBPUSD: -28.63 (361), USDJPY: -35.95 (434)}, per window gross [0.33, -8.51, -25.69, 4.88, -0.31, 0.45]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median', 'no_kill_switch']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/round_break/`.

<!-- prescreen:round_break end -->

<!-- prescreen:asia_fade start -->

### asia_fade (i5_asia_fade, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | asia_fade v00 | decision_hour=7, k=0.25, exit_hour=12 | 999 | -77.86 | 1 | - |
| 2026-10-31 | asia_fade v01 | decision_hour=7, k=0.25, exit_hour=20 | 999 | -92.38 | 1 | - |
| 2026-10-31 | asia_fade v02 | decision_hour=7, k=0.4, exit_hour=12 | 438 | -37.28 | 0 | 5 |
| 2026-10-31 | asia_fade v03 | decision_hour=7, k=0.4, exit_hour=20 | 438 | -27.23 | 0 | 1, 2, 3, 4, 6 |
| 2026-10-31 | asia_fade v04 | decision_hour=8, k=0.25, exit_hour=12 | 1201 | -98.76 | 1 | - |
| 2026-10-31 | asia_fade v05 | decision_hour=8, k=0.25, exit_hour=20 | 1201 | -145.04 | 2 | - |
| 2026-10-31 | asia_fade v06 | decision_hour=8, k=0.4, exit_hour=12 | 578 | -48.34 | 0 | - |
| 2026-10-31 | asia_fade v07 | decision_hour=8, k=0.4, exit_hour=20 | 578 | -81.08 | 1 | - |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 277 trades (0.36/day), net -37.15 USD (1.5x: -44.14), gross before costs -18.65 USD (-3.03 pips/trade), avg |move| 46.71 pips vs cost 4.03 pips (ratio 11.58), win rate 44.0%, PF 0.708, kill events 0, per pair net {EURUSD: -7.07 (59), GBPUSD: -15.97 (61), USDJPY: -14.11 (157)}, per window gross [-11.85, 3.19, 0.79, -7.97, -4.76, 1.95]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/asia_fade/`.

<!-- prescreen:asia_fade end -->

<!-- prescreen:us_data_drift start -->

### us_data_drift (i6_us_data_drift, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | us_data_drift v00 | k=0.2, exit_hour=17, stop=0.0 | 1268 | -89.91 | 1 | - |
| 2026-10-31 | us_data_drift v01 | k=0.2, exit_hour=17, stop=0.5 | 1279 | -90.37 | 1 | - |
| 2026-10-31 | us_data_drift v02 | k=0.2, exit_hour=20, stop=0.0 | 1268 | -92.57 | 1 | - |
| 2026-10-31 | us_data_drift v03 | k=0.2, exit_hour=20, stop=0.5 | 1279 | -95.36 | 1 | - |
| 2026-10-31 | us_data_drift v04 | k=0.3, exit_hour=17, stop=0.0 | 740 | -62.07 | 1 | - |
| 2026-10-31 | us_data_drift v05 | k=0.3, exit_hour=17, stop=0.5 | 749 | -59.23 | 1 | 4, 5 |
| 2026-10-31 | us_data_drift v06 | k=0.3, exit_hour=20, stop=0.0 | 740 | -60.93 | 1 | 1, 2, 3 |
| 2026-10-31 | us_data_drift v07 | k=0.3, exit_hour=20, stop=0.5 | 749 | -63.85 | 1 | 6 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 425 trades (0.55/day), net -48.36 USD (1.5x: -60.85), gross before costs -21.91 USD (-3.06 pips/trade), avg |move| 24.95 pips vs cost 3.65 pips (ratio 6.83), win rate 40.2%, PF 0.584, kill events 0, per pair net {EURUSD: -15.52 (159), GBPUSD: -19.68 (150), USDJPY: -13.16 (116)}, per window gross [-5.43, -11.74, 4.45, 1.77, -3.82, -7.15]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/us_data_drift/`.

<!-- prescreen:us_data_drift end -->

<!-- prescreen:ny_into_asia start -->

### ny_into_asia (i7_ny_into_asia, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | ny_into_asia v00 | k=0.25, exit_hour=0, stop=0.0 | 1175 | -98.65 | 1 | - |
| 2026-10-31 | ny_into_asia v01 | k=0.25, exit_hour=0, stop=0.5 | 1177 | -92.55 | 1 | 1, 4 |
| 2026-10-31 | ny_into_asia v02 | k=0.25, exit_hour=6, stop=0.0 | 1176 | -136.68 | 2 | - |
| 2026-10-31 | ny_into_asia v03 | k=0.25, exit_hour=6, stop=0.5 | 1178 | -115.73 | 2 | - |
| 2026-10-31 | ny_into_asia v04 | k=0.4, exit_hour=0, stop=0.0 | 628 | -51.03 | 1 | 5, 6 |
| 2026-10-31 | ny_into_asia v05 | k=0.4, exit_hour=0, stop=0.5 | 630 | -49.29 | 0 | 3 |
| 2026-10-31 | ny_into_asia v06 | k=0.4, exit_hour=6, stop=0.0 | 628 | -72.69 | 1 | - |
| 2026-10-31 | ny_into_asia v07 | k=0.4, exit_hour=6, stop=0.5 | 630 | -63.42 | 1 | 2 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 471 trades (0.61/day), net -37.3 USD (1.5x: -46.89), gross before costs -4.71 USD (-0.33 pips/trade), avg |move| 18.29 pips vs cost 3.59 pips (ratio 5.1), win rate 35.7%, PF 0.643, kill events 0, per pair net {EURUSD: -22.42 (164), GBPUSD: -13.58 (186), USDJPY: -1.3 (121)}, per window gross [-3.66, 9.19, -0.87, -2.06, -2.19, -5.12]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/ny_into_asia/`.

<!-- prescreen:ny_into_asia end -->

<!-- prescreen:london_reversal start -->

### london_reversal (i8_london_reversal, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | london_reversal v00 | k=0.4, exit_hour=17, stop=0.0 | 1164 | -78.1 | 1 | - |
| 2026-10-31 | london_reversal v01 | k=0.4, exit_hour=17, stop=0.5 | 1177 | -73.98 | 1 | 3 |
| 2026-10-31 | london_reversal v02 | k=0.4, exit_hour=20, stop=0.0 | 1164 | -73.89 | 1 | - |
| 2026-10-31 | london_reversal v03 | k=0.4, exit_hour=20, stop=0.5 | 1177 | -67.75 | 1 | 2 |
| 2026-10-31 | london_reversal v04 | k=0.6, exit_hour=17, stop=0.0 | 598 | -34.66 | 0 | 4, 5, 6 |
| 2026-10-31 | london_reversal v05 | k=0.6, exit_hour=17, stop=0.5 | 605 | -34.89 | 0 | - |
| 2026-10-31 | london_reversal v06 | k=0.6, exit_hour=20, stop=0.0 | 598 | -41.26 | 0 | - |
| 2026-10-31 | london_reversal v07 | k=0.6, exit_hour=20, stop=0.5 | 605 | -37.28 | 0 | 1 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 457 trades (0.59/day), net -28.53 USD (1.5x: -39.08), gross before costs 2.88 USD (0.52 pips/trade), avg |move| 23.61 pips vs cost 3.69 pips (ratio 6.4), win rate 45.3%, PF 0.748, kill events 0, per pair net {EURUSD: -8.44 (163), GBPUSD: -4.56 (159), USDJPY: -15.53 (135)}, per window gross [-6.85, 1.37, 0.6, 3.76, 1.74, 2.25]. Luck (200 coin-toss runs on the candidate's own signals): median net -33.17, share beaten 70%. Checks failed: ['c3_trades_per_day_1_5']. **Pre-screen (check 6): PASS**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/london_reversal/`.

<!-- prescreen:london_reversal end -->

<!-- prescreen:range_exhaustion start -->

### range_exhaustion (i9_range_exhaustion, 1h): 4 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | range_exhaustion v00 | r=1.0, sl_frac=0.25 | 731 | -64.8 | 1 | - |
| 2026-10-31 | range_exhaustion v01 | r=1.0, sl_frac=0.5 | 716 | -46.98 | 1 | 4, 5 |
| 2026-10-31 | range_exhaustion v02 | r=1.3, sl_frac=0.25 | 359 | -40.39 | 0 | - |
| 2026-10-31 | range_exhaustion v03 | r=1.3, sl_frac=0.5 | 350 | -34.69 | 0 | 1, 2, 3, 6 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 271 trades (0.35/day), net -28.32 USD (1.5x: -34.91), gross before costs -8.83 USD (-1.46 pips/trade), avg |move| 24.96 pips vs cost 3.89 pips (ratio 6.42), win rate 43.2%, PF 0.63, kill events 0, per pair net {EURUSD: -8.12 (82), GBPUSD: -8.97 (99), USDJPY: -11.23 (90)}, per window gross [-7.32, 0.26, -1.46, -1.0, 0.25, 0.45]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/range_exhaustion/`.

<!-- prescreen:range_exhaustion end -->

<!-- prescreen:trend_intraday start -->

### trend_intraday (i10_trend_intraday, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | trend_intraday v00 | lookback=5, k=0.5, stop=0.0 | 2229 | -208.11 | 4 | - |
| 2026-10-31 | trend_intraday v01 | lookback=5, k=0.5, stop=0.5 | 2235 | -200.09 | 4 | - |
| 2026-10-31 | trend_intraday v02 | lookback=5, k=1.0, stop=0.0 | 1570 | -133.88 | 2 | 1 |
| 2026-10-31 | trend_intraday v03 | lookback=5, k=1.0, stop=0.5 | 1573 | -117.27 | 2 | 6 |
| 2026-10-31 | trend_intraday v04 | lookback=10, k=0.5, stop=0.0 | 2391 | -150.97 | 3 | 4 |
| 2026-10-31 | trend_intraday v05 | lookback=10, k=0.5, stop=0.5 | 2397 | -156.97 | 3 | 3, 5 |
| 2026-10-31 | trend_intraday v06 | lookback=10, k=1.0, stop=0.0 | 2008 | -147.61 | 2 | 2 |
| 2026-10-31 | trend_intraday v07 | lookback=10, k=1.0, stop=0.5 | 2012 | -147.92 | 2 | - |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 1227 trades (1.58/day), net -134.4 USD (1.5x: -164.36), gross before costs -53.55 USD (-2.3 pips/trade), avg |move| 40.76 pips vs cost 3.87 pips (ratio 10.52), win rate 42.8%, PF 0.733, kill events 2, per pair net {EURUSD: -42.31 (410), GBPUSD: -38.55 (409), USDJPY: -53.54 (408)}, per window gross [-10.96, -4.89, -0.99, -15.97, -20.21, -0.52]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c6_gross_positive', 'c6_beats_random_median', 'no_kill_switch']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/trend_intraday/`.

<!-- prescreen:trend_intraday end -->

<!-- prescreen:ny_cut_breakout start -->

### ny_cut_breakout (i11_ny_cut_breakout, 1h): 4 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | ny_cut_breakout v00 | range_hours=2, sl_frac=0.5 | 1992 | -115.56 | 2 | - |
| 2026-10-31 | ny_cut_breakout v01 | range_hours=2, sl_frac=1.0 | 1891 | -93.07 | 1 | 2, 4, 5, 6 |
| 2026-10-31 | ny_cut_breakout v02 | range_hours=3, sl_frac=0.5 | 1787 | -116.83 | 2 | 1 |
| 2026-10-31 | ny_cut_breakout v03 | range_hours=3, sl_frac=1.0 | 1718 | -94.31 | 1 | 3 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 1109 trades (1.43/day), net -54.09 USD (1.5x: -85.1), gross before costs 14.87 USD (1.02 pips/trade), avg |move| 16.65 pips vs cost 3.85 pips (ratio 4.32), win rate 39.3%, PF 0.699, kill events 1, per pair net {EURUSD: -21.05 (356), GBPUSD: -13.28 (389), USDJPY: -19.76 (364)}, per window gross [-1.41, 3.62, 1.67, 14.24, -7.76, 4.51]. Luck (200 coin-toss runs on the candidate's own signals): median net -75.7, share beaten 94%. Checks failed: ['c3_trades_per_day_1_5', 'no_kill_switch']. **Pre-screen (check 6): PASS**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/ny_cut_breakout/`.

<!-- prescreen:ny_cut_breakout end -->

<!-- prescreen:twap_pullback start -->

### twap_pullback (i12_twap_pullback, 1h): 4 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | twap_pullback v00 | k=0.3, sl_frac=0.2 | 1385 | -95.76 | 1 | - |
| 2026-10-31 | twap_pullback v01 | k=0.3, sl_frac=0.4 | 1230 | -81.5 | 1 | 6 |
| 2026-10-31 | twap_pullback v02 | k=0.5, sl_frac=0.2 | 462 | -24.9 | 0 | 3, 5 |
| 2026-10-31 | twap_pullback v03 | k=0.5, sl_frac=0.4 | 431 | -24.7 | 0 | 1, 2, 4 |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 357 trades (0.46/day), net -40.3 USD (1.5x: -47.48), gross before costs -12.82 USD (-2.15 pips/trade), avg |move| 25.73 pips vs cost 4.25 pips (ratio 6.05), win rate 35.6%, PF 0.625, kill events 0, per pair net {EURUSD: -12.67 (100), GBPUSD: -6.87 (106), USDJPY: -20.76 (151)}, per window gross [12.35, -5.31, -10.8, -4.59, 1.35, -5.82]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_gross_positive', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/twap_pullback/`.

<!-- prescreen:twap_pullback end -->

<!-- prescreen:morning_overnight start -->

### morning_overnight (i13_morning_overnight, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | morning_overnight v00 | decision_hour=8, k=0.25, stop=0.0 | 958 | -23.81 | 1 | - |
| 2026-10-31 | morning_overnight v01 | decision_hour=8, k=0.25, stop=0.5 | 960 | -54.65 | 1 | - |
| 2026-10-31 | morning_overnight v02 | decision_hour=8, k=0.4, stop=0.0 | 457 | 5.99 | 0 | 1, 4, 5, 6 |
| 2026-10-31 | morning_overnight v03 | decision_hour=8, k=0.4, stop=0.5 | 458 | -5.25 | 0 | 2, 3 |
| 2026-10-31 | morning_overnight v04 | decision_hour=10, k=0.25, stop=0.0 | 1227 | -31.01 | 1 | - |
| 2026-10-31 | morning_overnight v05 | decision_hour=10, k=0.25, stop=0.5 | 1229 | -69.45 | 1 | - |
| 2026-10-31 | morning_overnight v06 | decision_hour=10, k=0.4, stop=0.0 | 688 | -54.58 | 1 | - |
| 2026-10-31 | morning_overnight v07 | decision_hour=10, k=0.4, stop=0.5 | 690 | -68.87 | 1 | - |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 297 trades (0.38/day), net 17.47 USD (1.5x: 3.9), gross before costs 44.62 USD (7.15 pips/trade), avg |move| 47.79 pips vs cost 4.03 pips (ratio 11.86), win rate 50.2%, PF 1.117, kill events 0, per pair net {EURUSD: 11.95 (76), GBPUSD: -7.51 (83), USDJPY: 13.03 (138)}, per window gross [6.77, 3.41, -1.45, 18.05, 8.25, 9.6]. Luck (200 coin-toss runs on the candidate's own signals): median net -31.65, share beaten 100%. Checks failed: ['c3_trades_per_day_1_5']. **Pre-screen (check 6): PASS**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/morning_overnight/`.

<!-- prescreen:morning_overnight end -->

<!-- prescreen:knn_path start -->

### knn_path (a2_knn_path, 1h): 8 variants

Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; selection used only each round's training window.

| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |
|---|---|---|---|---|---|---|
| 2026-10-31 | knn_path v00 | model=knn50, feats=path, pool=pair, margin=0.05 | 1146 | -80.18 | 0 | - |
| 2026-10-31 | knn_path v01 | model=knn50, feats=path, pool=pair, margin=0.1 | 636 | -25.56 | 0 | 1 |
| 2026-10-31 | knn_path v02 | model=knn50, feats=pathpeers, pool=pair, margin=0.05 | 1072 | -111.77 | 0 | - |
| 2026-10-31 | knn_path v03 | model=knn50, feats=pathpeers, pool=pair, margin=0.1 | 520 | -15.89 | 0 | 2, 3, 5 |
| 2026-10-31 | knn_path v04 | model=knn200, feats=path, pool=pair, margin=0.05 | 803 | -57.17 | 0 | - |
| 2026-10-31 | knn_path v05 | model=knn200, feats=path, pool=pair, margin=0.1 | 237 | -21.41 | 0 | 4 |
| 2026-10-31 | knn_path v06 | model=knn200, feats=pathpeers, pool=pair, margin=0.05 | 759 | -78.18 | 0 | 6 |
| 2026-10-31 | knn_path v07 | model=knn200, feats=pathpeers, pool=pair, margin=0.1 | 140 | -0.28 | 0 | - |

Stitched OOS (2023-10-27 to 2026-10-26, 776 trading days): 443 trades (0.57/day), net -32.9 USD (1.5x: -42.63), gross before costs 1.41 USD (0.25 pips/trade), avg |move| 42.69 pips vs cost 3.94 pips (ratio 10.84), win rate 47.0%, PF 0.837, kill events 0, per pair net {EURUSD: -17.44 (115), GBPUSD: 3.81 (91), USDJPY: -19.27 (237)}, per window gross [15.5, 4.67, -7.83, -9.24, -0.12, -1.57]. Luck (0 coin-toss runs on the candidate's own signals): median net 0, share beaten 0%. Checks failed: ['c3_trades_per_day_1_5', 'c6_beats_random_median']. **Pre-screen (check 6): FAIL**; all 2/3/5/6 checks: False. Files: `research/incubator_prescreen/knn_path/`.

<!-- prescreen:knn_path end -->
