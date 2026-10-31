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
