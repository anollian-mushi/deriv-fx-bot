# Perfect-fit experiment log

Owner-approved experiment on branch `experiment/perfect-fit` (31 Oct 2026), an explicit
exception to the CLAUDE.md research rules: no walk-forward, no luck check, no
parameter limit, no 2-of-3-pairs rule. Kept: real costs (commission by UTC hour from
`research/phase2/cost_by_hour.json`, slippage rules), every hard risk limit, the entry
window, daily pause, Friday close, and closed candles only.

Goal: the highest **net profit / max drawdown** on the whole pre-holdout period
(Dukascopy 1m, 2021-10-27 to 2026-04-27). Scores here are net return % / max drawdown %
(drawdown floored at 0.5% so a handful of lucky trades with no loss cannot divide by zero).

**Variants tried: 299,152.** Every one is a row of
[`research/experiment/variants.csv.gz`](experiment/variants.csv.gz) (id, family, rule,
exit setup, screen trades / net / drawdown / score). They were scored with the fast
screen (`src/fxbot/backtest/fastsim.py`); the finalists were then re-run in the real
engine (table at the end), and the engine result decided the winner.

Exit setups (528, each combined with every rule): x100 with stop loss
{none,10,15,20,30,50} pips, take profit {none,10,15,20,30,50,80}, time exit after
{1,2,3,4,6,8,12,24 h, none}; x200 with stop loss {none,10,15,20,30}, take profit
{none,10,15,20,30,50}, time exit {1,2,4,8 h, none}.

## By family

| Family | Variants | Killed (equity hit 50%) | Best screen score | Best variant | Exit setup | Trades | Net % | Max DD % |
|---|---|---|---|---|---|---|---|---|
| ML knn_1 | 96 | 0 | 14,763,671.3 | knn_1, predicted profit/stake > 0.05 | x200 SL- TP- hold1 | 17933 | 7,381,835.7 | 0.00 |
| ML knn_25 | 96 | 0 | 192,875.1 | knn_25, predicted profit/stake > 0.1 | x200 SL- TP- hold4 | 3655 | 1,452,989.4 | 7.53 |
| ML knn_5 | 96 | 0 | 1,419,412.3 | knn_5, predicted profit/stake > 0.5 | x100 SL50 TP80 holdmax | 885 | 709,706.1 | 0.03 |
| ML lgbm_l | 96 | 0 | 14,720,078.2 | lgbm_l, predicted profit/stake > 0.05 | x200 SL- TP- hold1 | 17563 | 7,360,039.1 | 0.00 |
| ML lgbm_m | 96 | 0 | 11,817,383.5 | lgbm_m, predicted profit/stake > 0.0 | x200 SL30 TP50 hold1 | 13011 | 5,908,691.7 | 0.45 |
| ML lgbm_s | 96 | 0 | 343,121.4 | lgbm_s, predicted profit/stake > 0.0 | x100 SL30 TP50 hold8 | 3589 | 736,187.3 | 2.15 |
| R1 time-of-day cells | 528 | 0 | 0.4 | best direction per pair x hour cell (in-sample) | x100 SL- TP- holdmax | 372 | 17.5 | 39.98 |
| R2 one indicator | 247,104 | 242,461 | 1.8 | upper_wick > q70 -> Up | x100 SL- TP- holdmax | 653 | 81.0 | 44.58 |
| R3 two indicators | 50,844 | 14,719 | 32.1 | ret_48 < q10 -> Up AND prevday_range_pos > q80 | x100 SL- TP80 holdmax | 9 | 16.1 | 0.00 |
| R4 cell filter | 100 | 0 | 45.5 | peer2_ret_4 > q90 -> Up AND peer2_ret_24 < q20 | only profitable pair x hour cells (15) | x100 SL- TP- holdmax | 39 | 73.7 | 1.62 |

## Best 25 variants overall (screen)

| Id | Family | Variant | Exit setup | Trades | Net % | Max DD % | Score |
|---|---|---|---|---|---|---|---|
| ml-482 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL- TP- hold1 | 17933 | 7,381,835.7 | 0.00 | 14,763,671.3 |
| ml-194 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL- TP- hold1 | 17563 | 7,360,039.1 | 0.00 | 14,720,078.2 |
| ml-488 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL- TP50 hold1 | 17970 | 7,355,279.5 | 0.00 | 14,710,559.0 |
| ml-200 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL- TP50 hold1 | 17597 | 7,335,249.2 | 0.00 | 14,670,498.4 |
| ml-494 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL30 TP- hold1 | 17830 | 7,303,674.2 | 0.00 | 14,607,348.4 |
| ml-500 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL30 TP50 hold1 | 17872 | 7,295,032.4 | 0.00 | 14,590,064.8 |
| ml-206 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL30 TP- hold1 | 17439 | 7,280,475.1 | 0.00 | 14,560,950.2 |
| ml-212 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL30 TP50 hold1 | 17511 | 7,272,998.9 | 0.00 | 14,545,997.7 |
| ml-512 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL- TP30 hold1 | 18114 | 7,247,063.8 | 0.00 | 14,494,127.6 |
| ml-506 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL30 TP30 hold1 | 18107 | 7,243,839.2 | 0.00 | 14,487,678.5 |
| ml-224 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL- TP30 hold1 | 17786 | 7,226,601.1 | 0.00 | 14,453,202.2 |
| ml-218 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL30 TP30 hold1 | 17750 | 7,219,360.5 | 0.00 | 14,438,721.0 |
| ml-193 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.0 | x200 SL- TP- hold1 | 22305 | 7,210,943.8 | 0.01 | 14,421,887.6 |
| ml-481 | ML knn_1 | knn_1, predicted profit/stake > 0.0 | x200 SL- TP- hold1 | 22511 | 7,189,095.7 | 0.00 | 14,378,191.4 |
| ml-199 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.0 | x200 SL- TP50 hold1 | 22332 | 7,169,511.7 | 0.02 | 14,339,023.4 |
| ml-518 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL20 TP- hold1 | 17529 | 7,153,983.1 | 0.00 | 14,307,966.1 |
| ml-205 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.0 | x200 SL30 TP- hold1 | 22225 | 7,149,757.8 | 0.02 | 14,299,515.6 |
| ml-487 | ML knn_1 | knn_1, predicted profit/stake > 0.0 | x200 SL- TP50 hold1 | 22532 | 7,146,887.3 | 0.00 | 14,293,774.6 |
| ml-524 | ML knn_1 | knn_1, predicted profit/stake > 0.05 | x200 SL20 TP50 hold1 | 17569 | 7,145,614.8 | 0.00 | 14,291,229.6 |
| ml-230 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL20 TP- hold1 | 17169 | 7,129,773.0 | 0.00 | 14,259,546.1 |
| ml-236 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.05 | x200 SL20 TP50 hold1 | 17215 | 7,128,203.2 | 0.00 | 14,256,406.5 |
| ml-493 | ML knn_1 | knn_1, predicted profit/stake > 0.0 | x200 SL30 TP- hold1 | 22410 | 7,126,771.1 | 0.00 | 14,253,542.2 |
| ml-211 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.0 | x200 SL30 TP50 hold1 | 22233 | 7,125,482.6 | 0.00 | 14,250,965.2 |
| ml-499 | ML knn_1 | knn_1, predicted profit/stake > 0.0 | x200 SL30 TP50 hold1 | 22437 | 7,100,439.5 | 0.00 | 14,200,879.0 |
| ml-217 | ML lgbm_l | lgbm_l, predicted profit/stake > 0.0 | x200 SL30 TP30 hold1 | 22436 | 7,072,587.4 | 0.01 | 14,145,174.9 |

## Ceiling: perfect hindsight (not a strategy)

Taking, at every candidate hour, whichever direction actually made money (knowing the
future) gives these screen scores. No real strategy can beat them; they show how far
in-sample fitting can be pushed.

- x200 SL- TP- hold1: score 14,378,191.4
- x200 SL- TP50 hold1: score 14,293,774.6
- x200 SL30 TP- hold1: score 14,253,542.2

## Finalists re-run in the real engine (kill switch enforced)

| Rank | Source | Variant | Exit setup | Engine trades | Net % | Max DD % | Win % | Score | Killed |
|---|---|---|---|---|---|---|---|---|---|
| 1 | ml | knn_1 | x200 SL30 TP30 hold1 | 5533 | 3,870,034.7 | 1.29 | 97.8 | 2,995,147.0 | False |
| 2 | ml | knn_1 | x200 SL15 TP30 holdmax | 8747 | 6,121,281.4 | 2.06 | 94.2 | 2,972,275.7 | False |
| 3 | ml | lgbm_l | x200 SL15 TP30 holdmax | 8722 | 6,115,014.9 | 2.06 | 94.2 | 2,969,233.0 | False |
| 4 | ml | lgbm_l | x200 SL30 TP30 hold1 | 5425 | 3,815,838.5 | 1.29 | 97.8 | 2,953,176.9 | False |
| 5 | ml | lgbm_l | x200 SL15 TP30 holdmax | 8421 | 6,064,564.4 | 2.06 | 94.4 | 2,944,936.7 | False |
| 6 | ml | knn_1 | x200 SL15 TP30 holdmax | 8431 | 6,063,861.9 | 2.06 | 94.3 | 2,944,595.6 | False |
| 7 | ml | knn_1 | x200 SL20 TP- hold1 | 6149 | 4,042,892.0 | 1.43 | 97.8 | 2,822,977.5 | False |
| 8 | ml | knn_1 | x200 SL30 TP30 hold1 | 12063 | 5,449,339.2 | 1.94 | 96.3 | 2,803,301.5 | False |
| 9 | ml | lgbm_l | x200 SL30 TP30 hold1 | 11813 | 5,434,700.7 | 1.94 | 96.3 | 2,795,789.6 | False |
| 10 | ml | lgbm_l | x200 SL20 TP- hold1 | 5873 | 3,966,491.8 | 1.43 | 97.9 | 2,769,500.9 | False |
| 11 | ml | lgbm_m | x200 SL15 TP30 holdmax | 7779 | 5,567,072.5 | 2.06 | 95.6 | 2,704,017.9 | False |
| 12 | ml | lgbm_m | x200 SL15 TP30 holdmax | 6161 | 4,686,883.4 | 1.80 | 97.3 | 2,604,203.7 | False |
| 13 | ml | lgbm_l | x200 SL15 TP30 holdmax | 9050 | 6,053,627.9 | 2.43 | 93.8 | 2,492,627.5 | False |
| 14 | ml | knn_1 | x200 SL15 TP30 holdmax | 9070 | 6,048,826.1 | 2.43 | 93.8 | 2,490,650.3 | False |
| 15 | ml | knn_1 | x200 SL30 TP50 hold1 | 3868 | 3,224,631.8 | 1.32 | 98.0 | 2,442,417.2 | False |
| 16 | ml | lgbm_l | x200 SL15 TP30 holdmax | 9143 | 5,967,867.0 | 2.46 | 93.5 | 2,430,094.9 | False |
| 17 | ml | knn_1 | x200 SL15 TP30 holdmax | 9149 | 5,962,696.1 | 2.46 | 93.5 | 2,428,003.1 | False |
| 18 | ml | lgbm_m | x200 SL15 TP30 holdmax | 8803 | 5,830,700.3 | 2.43 | 93.2 | 2,400,826.2 | False |
| 19 | ml | lgbm_l | x200 SL15 TP30 holdmax | 9183 | 5,857,420.6 | 2.46 | 93.1 | 2,385,142.7 | False |
| 20 | ml | lgbm_l | x200 SL30 TP- hold1 | 12711 | 4,917,944.6 | 2.07 | 95.9 | 2,381,053.0 | False |
| 21 | ml | knn_1 | x200 SL15 TP30 holdmax | 9188 | 5,853,937.7 | 2.46 | 93.1 | 2,379,406.0 | False |
| 22 | ml | knn_1 | x200 SL30 TP- hold1 | 12967 | 4,907,146.2 | 2.07 | 95.8 | 2,375,757.1 | False |
| 23 | ml | lgbm_l | x200 SL30 TP50 hold1 | 3707 | 3,136,113.5 | 1.32 | 97.9 | 2,375,496.4 | False |
| 24 | ml | knn_1 | x200 SL30 TP50 hold1 | 6559 | 4,294,618.1 | 1.81 | 97.6 | 2,370,630.7 | False |
| 25 | ml | lgbm_l | x200 SL30 TP50 hold1 | 6281 | 4,219,394.6 | 1.81 | 97.7 | 2,329,154.1 | False |
| 26 | ml | lgbm_l | x200 SL30 TP- hold1 | 15443 | 4,472,436.6 | 1.92 | 93.1 | 2,324,033.4 | False |
| 27 | ml | knn_1 | x200 SL30 TP- hold1 | 15559 | 4,446,692.5 | 1.92 | 93.3 | 2,316,251.4 | False |
| 28 | ml | knn_1 | x200 SL30 TP- hold1 | 6251 | 4,124,698.0 | 1.79 | 97.8 | 2,299,811.4 | False |
| 29 | ml | knn_1 | x200 SL30 TP- hold1 | 10428 | 4,891,695.0 | 2.14 | 96.7 | 2,289,384.1 | False |
| 30 | ml | lgbm_m | x200 SL20 TP- hold1 | 9480 | 4,131,890.8 | 1.81 | 92.8 | 2,284,719.6 | False |
| 31 | ml | lgbm_l | x200 SL30 TP- hold1 | 10145 | 4,870,592.7 | 2.14 | 96.8 | 2,279,519.8 | False |
| 32 | ml | knn_1 | x200 SL20 TP- hold1 | 3496 | 2,971,470.2 | 1.31 | 98.3 | 2,259,975.8 | False |
| 33 | ml | lgbm_l | x200 SL30 TP- hold1 | 5973 | 4,042,865.9 | 1.79 | 97.8 | 2,254,161.3 | False |
| 34 | ml | lgbm_l | x200 SL20 TP- hold1 | 12596 | 4,828,265.3 | 2.14 | 96.0 | 2,254,043.7 | False |
| 35 | ml | knn_1 | x200 SL20 TP- hold1 | 12815 | 4,812,459.3 | 2.15 | 95.7 | 2,242,305.3 | False |
| 36 | ml | lgbm_l | x200 SL30 TP50 hold1 | 13106 | 5,070,120.5 | 2.28 | 95.8 | 2,227,045.1 | False |
| 37 | ml | knn_1 | x200 SL30 TP50 hold1 | 13322 | 5,049,020.8 | 2.28 | 95.6 | 2,217,791.5 | False |
| 38 | ml | knn_1 | x200 SL30 TP50 hold1 | 10776 | 5,046,369.2 | 2.28 | 96.6 | 2,216,668.3 | False |
| 39 | ml | knn_1 | x200 SL20 TP- hold1 | 10282 | 4,804,033.9 | 2.17 | 96.7 | 2,211,157.2 | False |
| 40 | ml | lgbm_l | x200 SL30 TP50 hold1 | 10496 | 5,019,773.2 | 2.28 | 96.7 | 2,204,949.1 | False |
| 41 | ml | lgbm_l | x200 SL20 TP- hold1 | 10024 | 4,787,212.8 | 2.18 | 96.8 | 2,200,362.2 | False |
| 42 | ml | lgbm_l | x200 SL20 TP- hold1 | 3347 | 2,890,779.1 | 1.32 | 98.3 | 2,196,515.1 | False |
| 43 | ml | knn_1 | x200 SL30 TP30 hold1 | 7956 | 4,815,246.4 | 2.19 | 97.3 | 2,194,923.2 | False |
| 44 | ml | lgbm_l | x200 SL30 TP30 hold1 | 7694 | 4,735,726.4 | 2.19 | 97.4 | 2,161,648.3 | False |
| 45 | ml | lgbm_m | x200 SL30 TP30 hold1 | 11365 | 4,731,886.0 | 2.19 | 92.6 | 2,155,955.6 | False |
| 46 | ml | knn_1 | x200 SL30 TP- hold1 | 3569 | 3,045,625.5 | 1.47 | 98.3 | 2,070,158.5 | False |
| 47 | ml | lgbm_l | x200 SL30 TP- hold1 | 3415 | 2,967,843.5 | 1.47 | 98.4 | 2,017,036.2 | False |
| 48 | ml | lgbm_m | x200 SL30 TP30 hold1 | 3749 | 2,411,900.3 | 1.29 | 98.4 | 1,873,260.8 | False |
| 49 | ml | lgbm_l | x200 SL30 TP50 hold1 | 15766 | 4,590,712.3 | 2.47 | 93.2 | 1,859,185.7 | False |
| 50 | ml | knn_1 | x200 SL30 TP50 hold1 | 15890 | 4,563,183.9 | 2.47 | 93.2 | 1,849,764.1 | False |
| 51 | ml | lgbm_m | x200 SL20 TP- hold1 | 2804 | 2,287,754.2 | 1.28 | 98.0 | 1,792,642.7 | False |
| 52 | ml | lgbm_l | x200 SL20 TP- hold1 | 15308 | 4,387,817.6 | 2.47 | 93.1 | 1,777,767.4 | False |
| 53 | ml | knn_1 | x200 SL20 TP- hold1 | 15428 | 4,354,363.6 | 2.47 | 93.2 | 1,762,038.6 | False |
| 54 | ml | lgbm_m | x200 SL30 TP30 hold1 | 6466 | 3,693,194.6 | 2.14 | 97.2 | 1,723,749.4 | False |
| 55 | ml | lgbm_m | x200 SL30 TP50 hold1 | 10026 | 4,336,173.6 | 2.60 | 92.6 | 1,666,096.1 | False |
| 56 | ml | lgbm_m | x200 SL30 TP- hold1 | 9723 | 4,180,258.9 | 2.53 | 92.4 | 1,651,523.8 | False |
| 57 | ml | lgbm_m | x200 SL30 TP50 hold1 | 5384 | 3,408,918.0 | 2.17 | 97.5 | 1,567,472.9 | False |
| 58 | ml | lgbm_l | x200 SL30 TP30 hold1 | 14347 | 5,390,125.5 | 3.61 | 95.4 | 1,493,176.9 | False |
| 59 | ml | knn_1 | x200 SL30 TP30 hold1 | 14567 | 5,368,082.7 | 3.60 | 95.3 | 1,489,079.8 | False |
| 60 | ml | lgbm_l | x200 SL- TP- hold1 | 12773 | 4,950,477.3 | 3.40 | 96.0 | 1,454,681.0 | False |
| 61 | ml | knn_1 | x200 SL- TP- hold1 | 12997 | 4,941,090.1 | 3.40 | 95.8 | 1,451,896.0 | False |
| 62 | ml | lgbm_l | x200 SL- TP50 hold1 | 13134 | 5,100,622.2 | 3.61 | 95.9 | 1,412,374.0 | False |
| 63 | ml | knn_1 | x200 SL- TP50 hold1 | 13353 | 5,076,089.8 | 3.61 | 95.6 | 1,405,552.9 | False |
| 64 | ml | lgbm_l | x200 SL30 TP30 hold1 | 17038 | 4,865,661.7 | 3.60 | 93.0 | 1,349,721.3 | False |
| 65 | ml | knn_1 | x200 SL30 TP30 hold1 | 17133 | 4,829,631.0 | 3.61 | 93.1 | 1,337,907.1 | False |
| 66 | ml | lgbm_m | x200 SL30 TP- hold1 | 5027 | 3,209,414.9 | 2.55 | 97.4 | 1,258,971.5 | False |
| 67 | ml | lgbm_m | x200 SL30 TP- hold1 | 2860 | 2,306,913.9 | 1.85 | 98.0 | 1,247,622.0 | False |
| 68 | ml | knn_1 | x200 SL30 TP50 hold1 | 1625 | 1,726,401.5 | 1.40 | 98.3 | 1,230,961.7 | False |
| 69 | ml | lgbm_l | x200 SL30 TP50 hold1 | 1580 | 1,682,476.6 | 1.40 | 98.3 | 1,200,148.8 | False |
| 70 | ml | lgbm_m | x200 SL15 TP30 holdmax | 2465 | 1,887,131.0 | 1.59 | 99.6 | 1,189,578.1 | False |
| 71 | ml | lgbm_m | x200 SL30 TP50 hold1 | 3190 | 2,502,834.1 | 2.12 | 98.2 | 1,180,584.0 | False |
| 72 | ml | lgbm_m | x200 SL20 TP- hold1 | 4963 | 3,174,968.2 | 3.12 | 97.5 | 1,018,533.4 | False |
| 73 | ml | knn_1 | x200 SL20 TP- hold1 | 1218 | 1,421,210.6 | 1.44 | 98.5 | 987,797.1 | False |
| 74 | ml | lgbm_l | x200 SL20 TP- hold1 | 1171 | 1,376,530.7 | 1.45 | 98.5 | 948,504.6 | False |
| 75 | ml | knn_1 | x200 SL30 TP- hold1 | 1252 | 1,469,431.2 | 1.72 | 98.4 | 853,910.3 | False |
| 76 | ml | lgbm_l | x200 SL30 TP- hold1 | 1203 | 1,422,547.1 | 1.72 | 98.4 | 826,674.9 | False |
| 77 | ml | lgbm_m | x200 SL30 TP50 hold1 | 1315 | 1,207,061.1 | 1.46 | 98.6 | 824,650.0 | False |
| 78 | ml | knn_5 | x200 SL15 TP30 holdmax | 3217 | 1,842,738.3 | 2.57 | 90.0 | 717,390.0 | False |
| 79 | ml | knn_1 | x200 SL15 TP30 holdmax | 1469 | 1,162,083.2 | 1.85 | 99.9 | 626,534.7 | False |
| 80 | ml | knn_5 | x100 SL30 TP50 hold8 | 2164 | 927,887.4 | 1.63 | 94.8 | 570,827.7 | False |
| 81 | ml | lgbm_l | x200 SL15 TP30 holdmax | 1234 | 925,183.9 | 1.85 | 99.9 | 498,825.0 | False |
| 82 | ml | lgbm_m | x200 SL20 TP- hold1 | 515 | 566,098.9 | 1.45 | 99.0 | 389,978.5 | False |
| 83 | ml | lgbm_m | x200 SL30 TP- hold1 | 1119 | 1,159,836.4 | 3.10 | 99.1 | 373,923.1 | False |
| 84 | ml | knn_5 | x200 SL- TP- hold4 | 2830 | 2,438,758.9 | 6.78 | 85.3 | 359,854.9 | False |
| 85 | ml | lgbm_m | x200 SL30 TP30 hold1 | 1011 | 507,554.7 | 1.54 | 99.3 | 329,856.7 | False |
| 86 | ml | lgbm_m | x200 SL30 TP- hold1 | 530 | 586,080.1 | 1.83 | 99.1 | 319,404.6 | False |
| 87 | ml | lgbm_m | x200 SL20 TP- hold1 | 1080 | 1,128,678.6 | 4.40 | 99.0 | 256,546.9 | False |
| 88 | ml | lgbm_m | x200 SL30 TP50 hold1 | 590 | 440,745.6 | 1.78 | 99.2 | 247,000.9 | False |
| 89 | ml | lgbm_s | x100 SL30 TP50 hold8 | 3560 | 698,603.3 | 2.89 | 72.9 | 242,017.1 | False |
| 90 | ml | knn_5 | x100 SL50 TP80 holdmax | 890 | 711,279.7 | 3.28 | 99.6 | 217,037.3 | False |
| 91 | ml | lgbm_s | x200 SL- TP- hold4 | 3852 | 1,743,691.1 | 8.77 | 68.5 | 198,752.8 | False |
| 92 | ml | knn_1 | x200 SL30 TP30 hold1 | 539 | 197,077.6 | 1.22 | 100.0 | 161,030.7 | False |
| 93 | ml | lgbm_s | x100 SL- TP- hold4 | 3865 | 652,381.7 | 4.81 | 68.2 | 135,566.4 | False |
| 94 | ml | knn_25 | x200 SL- TP- hold4 | 3447 | 1,279,315.1 | 9.92 | 69.1 | 129,004.4 | False |
| 95 | ml | lgbm_s | x200 SL- TP- hold4 | 1374 | 975,565.2 | 9.83 | 78.2 | 99,279.7 | False |
| 96 | ml | knn_25 | x200 SL- TP- hold4 | 5221 | 1,442,563.1 | 14.56 | 63.2 | 99,099.2 | False |
| 97 | ml | lgbm_m | x200 SL15 TP30 holdmax | 521 | 134,306.9 | 1.44 | 100.0 | 93,043.0 | False |
| 98 | ml | knn_25 | x100 SL50 TP80 holdmax | 1860 | 584,862.2 | 7.06 | 68.8 | 82,793.2 | False |
| 99 | ml | lgbm_l | x200 SL30 TP30 hold1 | 416 | 72,756.4 | 0.93 | 100.0 | 78,117.0 | False |
| 100 | ml | knn_25 | x100 SL- TP- hold4 | 3511 | 490,949.9 | 6.58 | 68.8 | 74,601.6 | False |
| 101 | ml | lgbm_m | x200 SL20 TP- hold1 | 150 | 40,691.2 | 1.37 | 98.7 | 29,664.6 | False |
| 102 | ml | lgbm_m | x200 SL30 TP- hold1 | 150 | 36,522.0 | 1.84 | 98.7 | 19,861.9 | False |
| 103 | ml | lgbm_m | x200 SL30 TP30 hold1 | 162 | 885.6 | 1.25 | 100.0 | 711.3 | False |
| 104 | ml | lgbm_m | x200 SL30 TP50 hold1 | 56 | 279.5 | 0.98 | 100.0 | 286.6 | False |
| 105 | r4 | peer2_ret_4 > q90 -> Up AND peer2_ret_24 < q20 | only profitable pair x hour cells (15) | x100 SL- TP- holdmax | 39 | 73.7 | 4.54 | 74.4 | 16.2 | False |
| 106 | r3 | ret_48 < q10 -> Up AND prevday_range_pos > q80 | x100 SL- TP80 holdmax | 9 | 16.1 | 1.96 | 100.0 | 8.2 | False |
| 107 | r4 | ret_48 < q10 -> Up AND prevday_range_pos > q80 | only profitable pair x hour cells (14) | x100 SL- TP80 holdmax | 9 | 16.1 | 1.96 | 100.0 | 8.2 | False |
| 108 | r3 | ret_120 < q30 -> Up AND sma_dist_200 > q70 | x100 SL- TP- holdmax | 4 | 14.2 | 3.13 | 100.0 | 4.5 | False |
| 109 | r4 | ret_120 < q30 -> Up AND sma_dist_200 > q70 | only profitable pair x hour cells (8) | x100 SL- TP- holdmax | 4 | 14.2 | 3.13 | 100.0 | 4.5 | False |
| 110 | r3 | sma_dist_50 > q80 -> Up AND ret_48 < q30 | x100 SL- TP80 holdmax | 11 | 13.4 | 2.98 | 81.8 | 4.5 | False |
| 111 | r2 | upper_wick > q70 -> Up | x100 SL- TP- holdmax | 660 | 70.1 | 38.47 | 47.6 | 1.8 | False |
| 112 | r2 | sma_dist_100 < q30 -> Up | x100 SL- TP80 holdmax | 924 | 56.4 | 31.56 | 58.0 | 1.8 | False |
| 113 | r2 | d20_ret < q10 -> Up | x100 SL- TP80 holdmax | 341 | 30.5 | 23.17 | 60.7 | 1.3 | False |
| 114 | r1 | None | x100 SL- TP- holdmax | 370 | 24.5 | 43.73 | 47.8 | 0.6 | False |
| 115 | r1 | None | x200 SL- TP- holdmax | 1166 | 20.5 | 53.05 | 52.4 | 0.4 | False |
| 116 | r1 | None | x100 SL50 TP- hold24 | 1042 | 3.5 | 35.39 | 45.0 | 0.1 | False |
