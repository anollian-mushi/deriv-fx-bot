# Are there forex traders worth copying or testing? (trader research)

Researched 2026-10-31. Public pages only: no login, no account, nothing bought,
no seller contacted, no robot (EA) or file downloaded. This is a side task: no
strategy, rule, data or holdout was touched.

## The short answer

**No account passes all seven checks, so there is no shortlist.** None passes
even the first six (leaving out "are the rules published?"). Every account that
looked good on the surface failed something important once I looked closer:

- **Every one is a black box.** Each sells a closed robot or a copy
  subscription, and none publishes rules our engine could test.
- **50 of 57 trade through an offshore branch** of a broker, or a little-known
  broker, rather than a branch with a strong regulator.
- **29 of 57 are too smooth**: almost no losing months in years. That is the
  classic look of a strategy that hides its losses by averaging down.
- **24 of 57 have a headline gain inflated by deposit timing.** The gain on
  money actually put in is a fraction of the advertised figure: in the worst
  cases 10-35% against an advertised 500-6,500%.
- **The few with honest-looking curves make 1-5 pips a trade at their own
  broker.** Deriv's ~3 pips a trade would erase most of that.

None of them is worth our time to test. This agrees with what our own research
found (no strategy passed after 234 variants): a small, repeatable forex edge
that survives retail costs is rare, and nothing public changes that.

## What I looked at, and what I could not

**Myfxbook: blocked.** Every Myfxbook page, even `robots.txt`, returns a
Cloudflare "Just a moment..." bot check (HTTP 403). I tried two normal
fetchers, got the same block from both, and stopped: getting past it would mean
working around their protection. A web search returns Myfxbook page titles, but
not the badges, gains or deposit history, so I could not check any Myfxbook
account. No Myfxbook account appears in the table. To check one yourself, see
"How to check an account yourself" at the end.

**MQL5 Signals: open, and its robots.txt allows the signal list and signal
pages.** I made about 80 requests, one every 7 seconds. MQL5 only shows the
trade-by-trade history to logged-in users, so I could not see individual
trades (lot sizes, how many were open at once). For check 4 I used the
summary numbers MQL5 shows publicly instead (see below).

**How the 57 were chosen.**
1. I took the top 480 signals by MQL5's own rating (5 pages each of the MT4
   and MT5 lists). MQL5 lists about 4,300 rated signals in total.
2. I kept those marked "Real Account", with at least 52 weeks of history and a
   listed drawdown under 30%: 117 left.
3. To keep the slow page-by-page fetch reasonable, I opened the 58 of those
   with at least 100 weeks (about 2 years) of history. One page failed to
   download, which leaves 57.

So every account in the table already passes checks 1 and 2 and looked good on
the surface. That was deliberate: these are the best-looking accounts MQL5
lists, and the question is whether they hold up when examined.

Most of these accounts trade gold, crypto or "commodity currency" crosses
(AUD/CAD, NZD/CAD, AUD/NZD), not our three pairs. Only 36 of 57 do 80% or more
of their deals in forex.

## How each check was measured

| Check | How I measured it on MQL5 |
|---|---|
| 1. Verified | MQL5 copies every signal straight from the broker's server, so the numbers are not typed in by the seller. The "Real Account" badge separates real money from demo. All 57 have it. |
| 2. Real, 12+ months | Real Account badge and at least 52 weeks of trading. All 57 pass (most have 2-10 years). |
| 3. Drawdown and losing months | Worst of MQL5's drawdown by balance and by equity must be under 30%. **And** at least 1 month in 10 must be a losing month. Real trading loses some months. A line that almost never dips usually means losses are being hidden, not avoided. |
| 4. No grid, martingale or averaging down | Fail if any of these: win rate 80%+ with the average loss 3x the average win or more (or 90%+ with 2x); "max deposit load" (margin in use at the busiest moment) 50% or more; one month losing 20% or more; 40+ trades a week at a 75%+ win rate (positions stacking up); or the seller's own description or a buyer review describes averaging down, lot multipliers or deposit tricks. I could not see lot sizes trade by trade (login needed), so this check can miss things. |
| 5. Gain not inflated by deposits | MQL5's "Growth" works like Myfxbook's "gain": it chains each period's % return, so it ignores how much money was in the account at the time. I compared it with the **money gain**: profit divided by all money deposited (Myfxbook calls this "absolute gain"). **Fail if the money gain is under a third of the headline growth** and the owner deposited more than the starting amount later on. That pattern means the big % was made on a tiny balance, and results got worse once real money went in. |
| 6. Known, regulated broker | Judged from the broker server name. Pass only if the server belongs to a branch regulated by a strong regulator (Australia ASIC, UK FCA, EU CySEC/CBI and similar). Many big brands run offshore branches (Seychelles, Bahamas, Belize, BVI) with much weaker oversight, and their servers usually say so ("ICMarketsSC", "EightcapInternational", "XMGlobal"). Those fail. Caveat: a server name is a strong hint, not proof of the branch. |
| 7. Rules published | Read each signal's description. A link to a robot for sale, or vague words like "statistical probability" or "AI filter", count as a black box. |

## Every account checked

"Gain / money gain" is MQL5's headline growth, then profit as a % of all money
deposited. "Losing months" is losing months out of all months traded. The
failed-check numbers match the list above. Ranked by checks passed, then by age.
Data as shown on 2026-10-31; MQL5 pages change daily.

| # | Account | Main pairs (share of deals) | Age | Gain / money gain | Max DD | Losing months | Broker (server) | Failed checks | Main problems |
|---|---|---|---|---|---|---|---|---|---|
| 1 | [Commodity Accumulation Plan](https://www.mql5.com/en/signals/2270674) (Paolo Torlaschi) | WHEAT 38%, PLATINUM 26%, COPPER 16% | 9.8 y | 382% / 171% | 20% | 45/117 | AvaTrade | 4, 7 | description: "continues to buy on weakness" (accumulation = averaging down); mostly not forex |
| 2 | [SCR EURAUD](https://www.mql5.com/en/signals/2358336) (Maksym Viunik) | EURAUD 71%, AUDCAD 28%, EURUSD 1% | 7.8 y | 349% / 302% | 12% | 16/94 | FXGiants | 6, 7 | offshore or unclear branch of a known broker |
| 3 | [TP TRADER](https://www.mql5.com/en/signals/1932739) (Wei Chen) | EURUSD 35%, XAUUSD 29%, GBPUSD 13% | 6.9 y | 2,846% / 1,413% | 19% | 25/83 | CPT Markets | 6, 7 | offshore or unclear branch of a known broker |
| 4 | [NightVisionEA ICM](https://www.mql5.com/en/signals/731021) (Alexander Kalinkin) | USDJPY 13%, EURCHF 13%, USDCHF 10% | 6.8 y | 343% / 146% | 21% | 28/82 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 5 | [RFactor Portfolio JM](https://www.mql5.com/en/signals/743742) (Raphael Minato) | GBPUSD 18%, EURUSD 13%, EURAUD 8% | 6.5 y | 1,483% / 1,483% | 20% | 22/79 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 6 | [R Factor Broker FPMarkets](https://www.mql5.com/en/signals/973927) (Raphael Minato) | AUDCAD 13%, EURCAD 13%, EURUSD 12% | 5.7 y | 236% / 53% | 27% | 21/68 | FP Markets | 5, 7 | money gain only 53% vs headline 236% |
| 7 | [EEVCC Night IC 6](https://www.mql5.com/en/signals/2361862) (Xiaoyu Huang) | EURUSD 11%, XAUUSD 8%, EURGBP 6% | 5.4 y | 112% / 71% | 12% | 21/65 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 8 | [Stable growth pro](https://www.mql5.com/en/signals/1737977) (Profalgo Limited) | AUDCAD 18%, NZDCAD 15%, AUDNZD 15% | 4.2 y | 242% / 237% | 29% | 12/50 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 9 | [QImpulse_ValuT](https://www.mql5.com/en/signals/1857208) (Stanislav Pokalyuk) | XAUUSD 33%, USDJPY 16%, EURUSD 14% | 4.1 y | 285% / 305% | 22% | 16/47 | Valutrades (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 10 | [Pacific Way](https://www.mql5.com/en/signals/2280709) (Armen Khachatryan) | GBPCAD 20%, NZDCAD 12%, AUDCAD 10% | 4.1 y | 124% / 121% | 25% | 18/49 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker |
| 11 | [R Factor Neural Network 2](https://www.mql5.com/en/signals/1911819) (Raphael Minato) | USDCHF 18%, EURUSD 17%, GBPUSD 17% | 4.0 y | 110% / 110% | 25% | 19/48 | Fusion Markets | 6, 7 | offshore or unclear branch of a known broker |
| 12 | [Blue Agressive CFDs Fiat FIC04](https://www.mql5.com/en/signals/2031876) (Fabio Aparecido De Almeida) | XAUUSD 31%, USDJPY 26%, EURUSD 19% | 3.9 y | 320% / 320% | 14% | 13/44 | Infinox (Bahamas entity) | 6, 7 | offshore or unclear branch of a known broker |
| 13 | [Kosciuszko HR by SecureFX Trader](https://www.mql5.com/en/signals/1858780) (SecureFX Trader) | EURUSD 46%, EURJPY 32%, EURGBP 8% | 3.8 y | 195% / 177% | 28% | 0/45 | IC Markets Australia | 3, 7 | too smooth (0 losing months of 45) |
| 14 | [UZUNAMI88](https://www.mql5.com/en/signals/2392805) (Virgiawan Ilham Pratomo) | XAUUSD 52%, GBPJPY 48% | 3.7 y | 249% / 197% | 18% | 21/45 | Maxrich Group | 6, 7 | little-known/offshore broker; mostly not forex |
| 15 | [SFE Impulse](https://www.mql5.com/en/signals/2049326) (Joel Juanpere) | ETHUSD 55%, BTCUSD 45% | 3.2 y | 271% / 204% | 28% | 15/38 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker; mostly not forex |
| 16 | [HYPER GROWTH X](https://www.mql5.com/en/signals/2355321) (Chun Man Cheung) | BTCUSD 29%, XAUUSD 14%, USDJPY 14% | 2.4 y | 87% / 311% | 24% | 7/23 | Vantage | 6, 7 | offshore or unclear branch of a known broker; mostly not forex |
| 17 | [Gold Reaper New V2 2](https://www.mql5.com/en/signals/2265877) (Profalgo Limited) | XAUUSD 100% | 2.0 y | 340% / 321% | 17% | 5/25 | Capital Point Trading | 6, 7 | little-known/offshore broker; mostly not forex |
| 18 | [Soma PureGold Indexes and Oil](https://www.mql5.com/en/signals/2268766) (Andrii Soma) | USTEC 33%, XAUUSD 29%, BTCUSD 15% | 2.0 y | 902% / 305% | 29% | 5/24 | IC Markets (Seychelles entity) | 6, 7 | offshore or unclear branch of a known broker; mostly not forex |
| 19 | [Gold Important Sniper Level MT4](https://www.mql5.com/en/signals/2290292) (Ren Cheng Yao) | XAUUSD 86%, Gold 14% | 2.0 y | 402% / 402% | 27% | 9/24 | Weltrade | 6, 7 | little-known/offshore broker; mostly not forex |
| 20 | [Solnce](https://www.mql5.com/en/signals/2288975) (Dmitrii Kuropatkin) | XAUUSD 57%, GBPUSD 30%, USDJPY 13% | 1.9 y | 215% / 126% | 13% | 3/23 | RoboForex | 6, 7 | little-known/offshore broker; mostly not forex |
| 21 | [SFE Portfolio1](https://www.mql5.com/en/signals/138420) (Joel Juanpere) | LNKUSD 17%, BTCUSD 13%, ETHUSD 11% | 11.0 y | 1,952% / 174% | 24% | 46/133 | IC Markets (Seychelles entity) | 5, 6, 7 | money gain only 174% vs headline 1,952%; offshore or unclear branch of a known broker; mostly not forex |
| 22 | [JINNIUFX7](https://www.mql5.com/en/signals/2330430) (Fuchao Wang) | GBPUSD 100% | 10.1 y | 684% / 444% | 8% | 1/118 | Blackwell Global | 3, 6, 7 | too smooth (1 losing month of 118); offshore or unclear branch of a known broker |
| 23 | [PAI Unique Mode No Limits with AI Filter](https://www.mql5.com/en/signals/1919885) (Valeriia Mishchenko) | GBPCHF 20%, NZDCAD 18%, AUDCAD 17% | 7.3 y | 348% / 285% | 18% | 0/87 | ICE Markets | 3, 6, 7 | too smooth (0 losing months of 87); little-known/offshore broker |
| 24 | [MySingalStart 2](https://www.mql5.com/en/signals/840474) (Vladimira Sepelakova) | NZDCAD 47%, AUDCAD 24%, AUDNZD 17% | 6.7 y | 490% / 21% | 29% | 1/81 | IC Markets | 3, 5, 7 | too smooth (1 losing month of 81); money gain only 21% vs headline 490% |
| 25 | [Longterm ICM](https://www.mql5.com/en/signals/1627034) (Michael Fuss) | EURUSD 22%, AUDCAD 13%, NZDCAD 13% | 6.2 y | 560% / 39% | 28% | 17/75 | IC Markets (Seychelles entity) | 5, 6, 7 | money gain only 39% vs headline 560%; offshore or unclear branch of a known broker |
| 26 | [NoPain MT5](https://www.mql5.com/en/signals/2262642) (Daniel Moraes Da Silva) | AUDCAD 100% | 5.0 y | 2,187% / 400% | 21% | 1/60 | OANDA (Global Markets, BVI entity) | 3, 6, 7 | too smooth (1 losing month of 60); offshore or unclear branch of a known broker |
| 27 | [Pinnacle Alpha](https://www.mql5.com/en/signals/2274644) (Foong Jin Xin) | AUDCAD 39%, NZDCAD 36%, AUDNZD 25% | 4.8 y | 305% / 274% | 24% | 1/58 | Fortune Prime Global | 3, 6, 7 | too smooth (1 losing month of 58); little-known/offshore broker |
| 28 | [Nord Way AI](https://www.mql5.com/en/signals/2313989) (Armen Khachatryan) | GBPCAD 18%, AUDCAD 10%, NZDCAD 10% | 4.3 y | 123% / 112% | 25% | 16/52 | IC Markets (Seychelles entity) | 4, 6, 7 | one month lost -21.1%; offshore or unclear branch of a known broker |
| 29 | [Dudu Whale](https://www.mql5.com/en/signals/2351032) (Xue Mei) | XAUUSD 33%, USDJPY 24%, GBPJPY 19% | 4.2 y | 228% / 46% | 19% | 24/51 | IC Markets (Seychelles entity) | 5, 6, 7 | money gain only 46% vs headline 228%; offshore or unclear branch of a known broker |
| 30 | [Temanggung](https://www.mql5.com/en/signals/1771343) (Kendran Dwijo Santoso) | EURJPY 21%, AUDCAD 17%, AUDNZD 17% | 4.0 y | 147% / 89% | 25% | 3/48 | FBS | 3, 6, 7 | too smooth (3 losing months of 48); offshore or unclear branch of a known broker |
| 31 | [RAZOR EA](https://www.mql5.com/en/signals/2300694) (Anton Kondratev) | NZDCAD 40%, AUDCAD 28%, AUDNZD 23% | 3.9 y | 2,331% / 63% | 22% | 1/43 | Tickmill | 3, 5, 7 | too smooth (1 losing month of 43); money gain only 63% vs headline 2,331% |
| 32 | [EA Happy News Eightcap](https://www.mql5.com/en/signals/1864588) (Jaroslav Rajcher) | GBPUSD 29%, USDJPY 29%, EURUSD 23% | 3.7 y | 10,106% / 10,106% | 9% | 3/45 | Eightcap (Bahamas entity) | 3, 6, 7 | too smooth (3 losing months of 45); offshore or unclear branch of a known broker |
| 33 | [Steady Long term](https://www.mql5.com/en/signals/2373736) (Mirco Lupinetti) | AUDCAD 39%, NZDCAD 33%, AUDNZD 28% | 3.3 y | 124% / 85% | 16% | 0/39 | IC Markets (Seychelles entity) | 3, 6, 7 | too smooth (0 losing months of 39); offshore or unclear branch of a known broker |
| 34 | [UpEverest MT4](https://www.mql5.com/en/signals/2363323) (Daniel Moraes Da Silva) | AUDCAD 100% | 2.8 y | 573% / 288% | 15% | 0/34 | FP Markets (offshore entity) | 3, 6, 7 | too smooth (0 losing months of 34); offshore or unclear branch of a known broker |
| 35 | [Dudu 001 MT5](https://www.mql5.com/en/signals/2361784) (Xue Mei) | XAUUSD 36%, USDJPY 27%, GBPJPY 21% | 2.4 y | 332% / 54% | 25% | 11/29 | IC Markets (Seychelles entity) | 5, 6, 7 | money gain only 54% vs headline 332%; offshore or unclear branch of a known broker |
| 36 | [Wisdom Trading](https://www.mql5.com/en/signals/2361095) (Taman Talappetsakun) | NZDUSD.p 17%, EURGBP.p 17%, EURCHF.p 9% | 2.3 y | 384% / 10% | 29% | 7/28 | Axi | 4, 5, 7 | win 85% but avg loss 3.88x avg win; max deposit load 151%; money gain only 10% vs headline 384% |
| 37 | [EA Happy Japanese Market FM](https://www.mql5.com/en/signals/2295123) (Jaroslav Rajcher) | GBPJPY.fx 100% | 2.2 y | 388% / 155% | 23% | 0/27 | ForexMart | 3, 6, 7 | too smooth (0 losing months of 27); little-known/offshore broker |
| 38 | [Range Breakout EA Live](https://www.mql5.com/en/signals/2271995) (Jimmy Peter Eriksson) | USDJPY 28%, US30 20%, DE40 19% | 2.0 y | 344% / 109% | 28% | 9/24 | IC Markets (Seychelles entity) | 5, 6, 7 | money gain only 109% vs headline 344%; offshore or unclear branch of a known broker; mostly not forex |
| 39 | [EU Zone Arsenal](https://www.mql5.com/en/signals/2385553) (Gjuseppe Lppolito Ippolito) | GBPUSD 31%, EURJPY 29%, EURUSD 23% | 1.9 y | 124% / 124% | 9% | 0/22 | Fortune Prime Global | 3, 6, 7 | too smooth (0 losing months of 22); little-known/offshore broker |
| 40 | [MySingalStart 3](https://www.mql5.com/en/signals/1760039) (Vladimira Sepelakova) | NZDCAD 26%, USDCAD 17%, NZDCHF 14% | 9.4 y | 540% / 68% | 26% | 3/110 | IC Markets | 3, 4, 5, 7 | too smooth (3 losing months of 110); win 86% but avg loss 3.47x avg win; one month lost -26.4%; 65 trades/week at 86% win (stacked positions likely); money gain only 68% vs headline 540% |
| 41 | [Deux ex machina](https://www.mql5.com/en/signals/2271402) (Victor Gomez Sanchez) | AUDCAD 56%, AUDNZD 12%, NZDCAD 12% | 5.5 y | 6,489% / 35% | 26% | 3/65 | IC Markets (Seychelles entity) | 3, 5, 6, 7 | too smooth (3 losing months of 65); money gain only 35% vs headline 6,489%; offshore or unclear branch of a known broker |
| 42 | [EansPRO V3 XAUUSD](https://www.mql5.com/en/signals/2378480) (Ade Yonathan Lisanto) | GOLDmicro 100%, AUDUSDmicro 0% | 5.0 y | 224% / 18% | 10% | 0/58 | XM (Global entity) | 3, 5, 6, 7 | too smooth (0 losing months of 58); money gain only 18% vs headline 224%; offshore or unclear branch of a known broker; mostly not forex |
| 43 | [TT ic 001](https://www.mql5.com/en/signals/1270954) (Yu Chen) | AUDCAD 23%, NZDCAD 20%, EURUSD 15% | 4.9 y | 267% / 45% | 22% | 14/59 | IC Markets (Seychelles entity) | 4, 5, 6, 7 | description changelog: position multipliers 1.25-1.35 and "doubling" on some pairs (lot scaling); money gain only 45% vs headline 267%; offshore or unclear branch of a known broker |
| 44 | [FX Fun](https://www.mql5.com/en/signals/2355082) (Van Tung To) | AUDCADf 38%, NZDCADf 33%, AUDNZDf 28% | 4.4 y | 765% / 52% | 15% | 0/53 | LiteFinance | 3, 5, 6, 7 | too smooth (0 losing months of 53); money gain only 52% vs headline 765%; little-known/offshore broker |
| 45 | [LazyProV2 AUDCAD](https://www.mql5.com/en/signals/2378478) (Ade Yonathan Lisanto) | AUDCADmicro 100% | 3.8 y | 354% / 26% | 7% | 0/46 | XM (Global entity) | 3, 5, 6, 7 | too smooth (0 losing months of 46); money gain only 26% vs headline 354%; offshore or unclear branch of a known broker |
| 46 | [MSC Gold Invest Pro](https://www.mql5.com/en/signals/1988269) (Bui Huy Dat) | XAUUSD 100%, AUDCAD 0% | 3.4 y | 944% / 224% | 26% | 3/41 | Neotech Financial Services | 3, 5, 6, 7 | too smooth (3 losing months of 41); money gain only 224% vs headline 944%; little-known/offshore broker; mostly not forex |
| 47 | [UpFuji MT4](https://www.mql5.com/en/signals/2308093) (Daniel Moraes Da Silva) | AUDCAD 100% | 3.1 y | 318% / 157% | 27% | 0/37 | RoboForex | 3, 4, 6, 7 | too smooth (0 losing months of 37); seller says shown drawdown is too low because early history was not loaded; little-known/offshore broker |
| 48 | [YW Robot Safe and Steady Growth](https://www.mql5.com/en/signals/2345820) (Samuel Teo Kok Min) | AUDCAD 100% | 3.1 y | 135% / 21% | 10% | 2/35 | IC Markets (Seychelles entity) | 3, 5, 6, 7 | too smooth (2 losing months of 35); money gain only 21% vs headline 135%; offshore or unclear branch of a known broker |
| 49 | [BAS 2 11](https://www.mql5.com/en/signals/2325779) (Aleksandr Dziuba) | S1U6 6%, SVZ5 5%, SVM6 5% | 3.0 y | 935% / 114% | 21% | 2/37 | FINAM | 3, 5, 6, 7 | too smooth (2 losing months of 37); money gain only 114% vs headline 935%; offshore or unclear branch of a known broker; mostly not forex |
| 50 | [KaKa 2](https://www.mql5.com/en/signals/2379008) (Nguyen Van Loc) | GBPUSD 8%, USDCAD 7%, EURNZD 6% | 2.9 y | 387% / 118% | 23% | 0/31 | IC Markets (Seychelles entity) | 3, 5, 6, 7 | too smooth (0 losing months of 31); money gain only 118% vs headline 387%; offshore or unclear branch of a known broker |
| 51 | [Meaw](https://www.mql5.com/en/signals/2393078) (Prapat Kijsangpakdee) | XAUUSD+ 46%, USOUSD 19%, XAGUSD 14% | 2.7 y | 243% / 61% | 28% | 8/31 | Vantage | 4, 5, 6, 7 | max deposit load 58%; money gain only 61% vs headline 243%; offshore or unclear branch of a known broker; mostly not forex |
| 52 | [GoQuant](https://www.mql5.com/en/signals/2341150) (Tosin Komolafe) | XAUUSD 96%, EURUSD 4%, AUDCAD 0% | 2.4 y | 418% / 388% | 14% | 1/29 | Karios Markets | 3, 4, 6, 7 | too smooth (1 losing month of 29); max deposit load 82%; little-known/offshore broker; mostly not forex |
| 53 | [Harmonizer Extreme](https://www.mql5.com/en/signals/2360068) (Amir Hossein Moharreri) | AUDCAD 54%, NZDCAD 46% | 2.2 y | 2,739% / 59% | 22% | 0/27 | Alpari | 3, 5, 6, 7 | too smooth (0 losing months of 27); money gain only 59% vs headline 2,739%; little-known/offshore broker |
| 54 | [Dax Old New Acc](https://www.mql5.com/en/signals/2262806) (Kamil Filip Maleszka) | .DE40Cash 100%, EURUSD 0% | 2.1 y | 115% / 94% | 21% | 0/25 | RoboForex | 3, 4, 6, 7 | too smooth (0 losing months of 25); max deposit load 72%; little-known/offshore broker; mostly not forex |
| 55 | [Harmonizer High Risk](https://www.mql5.com/en/signals/2394758) (Amir Hossein Moharreri) | AUDCAD 54%, NZDCAD 46% | 2.1 y | 3,734% / 21% | 15% | 0/25 | Alpari | 3, 5, 6, 7 | too smooth (0 losing months of 25); money gain only 21% vs headline 3,734%; little-known/offshore broker |
| 56 | [ICTrading Signal 2](https://www.mql5.com/en/signals/926651) (Vladimira Sepelakova) | NZDCAD 48%, AUDCAD 24%, NZDCHF 6% | 9.2 y | 497% / 10% | 19% | 1/111 | Capital Point Trading | 3, 4, 5, 6, 7 | too smooth (1 losing month of 111); buyer review: owner adds deposits during drawdowns so copiers take losses the master does not; money gain only 10% vs headline 497%; little-known/offshore broker |
| 57 | [TwoHundredPercentAnnually](https://www.mql5.com/en/signals/2172246) (Vladimira Sepelakova) | NZDCAD 50%, AUDCAD 35%, AUDNZD 15% | 3.8 y | 557% / 12% | 29% | 1/46 | IC Markets (Seychelles entity) | 3, 4, 5, 6, 7 | too smooth (1 losing month of 46); win 88% but avg loss 3.94x avg win; money gain only 12% vs headline 557%; offshore or unclear branch of a known broker |

The full numbers for every account (deposits, withdrawals, win rate, average
win and loss, deposit load, trades per week, broker notes) are in
[research/trader_research/accounts.csv](../research/trader_research/accounts.csv).

## Shortlist

**Empty. No account passes all seven checks.**

For completeness, here are the closest misses and why none of them is worth
testing either. The "pips" figures come from MQL5's gross profit and loss in
points, divided by 10 to get normal pips. That is only meaningful for
accounts that trade forex almost exclusively, so they are given only for those.
Treat them as rough.

| Account | Checks failed | Avg win | Avg loss | Net per trade at their broker | After Deriv's ~3 pips | Why not |
|---|---|---|---|---|---|---|
| [Kosciuszko HR](https://www.mql5.com/en/signals/1858780) (EUR/USD, EUR/JPY) | 3, 7 | 17 pips | 39 pips | +6.8 | about +4 | The closest one, at a properly regulated broker (IC Markets Australia). But it has **zero losing months in 45**, wins 81% of trades and loses about twice as much on a loser as it makes on a winner: the shape of averaging down. Yearly gain has faded from 59% to 14%. Rules are not public; it is sold as a service. |
| [SCR EURAUD](https://www.mql5.com/en/signals/2358336) (EUR/AUD, AUD/CAD) | 6, 7 | 13 | 18 | +5.0 | about +2.5 | Not our pairs. Yearly gain has faded from 30-40% (2019-2022) to 3-12% since. Broker branch unclear. Sold as a robot. |
| [NightVisionEA ICM](https://www.mql5.com/en/signals/731021) | 6, 7 | 10 | 17 | +1.5 | negative | **Has lost money in 2025 and in 2026 so far**, after +154% in 2020. Offshore IC Markets branch. Sold as a robot. |
| [Pacific Way](https://www.mql5.com/en/signals/2280709) (crosses) | 6, 7 | 10 | 14 | +2.5 | about 0 | Mostly manual trading on CAD and SGD crosses; would not survive Deriv costs. Offshore branch. |
| [RFactor Portfolio JM](https://www.mql5.com/en/signals/743742), [R Factor NN 2](https://www.mql5.com/en/signals/1911819), [R Factor FPMarkets](https://www.mql5.com/en/signals/973927) (same seller) | 6, 7 (the FPMarkets one: 5, 7) | 4-6 | 6-10 | +0.8 to +1.4 | negative | Scalpers making about 1 pip a trade. Deriv's cost alone is 2-3 times that. The seller himself writes that copiers "may not get the same results". Huge first years (+249%, +155%), then 0-21% a year. |
| [TP TRADER](https://www.mql5.com/en/signals/1932739) (EUR/USD and gold) | 6, 7 | - | - | - | - | **MQL5 flags that 80% of its growth came in 5 days out of 1,220.** A buyer review points out that every stop loss filled at exactly the requested price with zero slippage, which a real market does not do. That points to a broker giving unusually kind fills. |

**Would any of them survive Deriv's costs?** Our project requires the average
win to be at least 3x the commission, about 9 pips on EUR/USD. Only Kosciuszko
HR (17 pips) and SCR EURAUD (13) clear that, and both fail other checks. All
the others earn 1-2.5 pips a trade at a cheap ECN broker that charges about
0.5-1 pip. Deriv charges about 3 (USD/JPY about 4), so those results would turn
into losses.

**Could our engine test any of them?** No. Not one publishes its entry and
exit rules. "Testing" them would mean guessing at a black box. The only
alternatives are buying the robot or copying the signal, and both are
outside this task and outside our rules (no EA downloads, and every order must
go through our own risk module).

## Red flags seen, so you can recognise them yourself

Each one below was seen in this list, with a real example.

1. **Headline gain far above the money gain.** *Harmonizer High Risk* shows
   **+3,734%**, but profit is only **21%** of the money deposited. *Deux ex
   machina*: +6,489% vs 35%. *RAZOR EA*: +2,331% vs 63%. How it works: grow a
   $50 account a lot (a huge %), then deposit thousands, and the % keeps the
   early glory. Always compare "Gain" with "Absolute gain" (Myfxbook) or
   profit ÷ deposits (MQL5).
2. **Deposits timed to hide losses.** A buyer review of *ICTrading Signal 2*
   says that when the system is in drawdown, the owner doubles the
   account balance. Copiers' trades are scaled to the bigger balance, so they take
   the full loss while the master account looks calm. Its money gain is 10%
   against a 497% headline. Clue: many deposits **and** withdrawals.
3. **Almost no losing months.** 29 of 57 accounts had at most 1 losing month
   in 10, several with **zero in 3-7 years** (*PAI Unique Mode*: 0 of 87
   months). Real trading has losing months. A smooth line usually means
   losing trades are held open and averaged down until they come back,
   until one day they don't.
4. **High win rate, small wins, big losses.** *TwoHundredPercentAnnually*
   wins 88% of trades, but the average loss is 3.9x the average win.
   *Wisdom Trading*: 85% wins, losses 3.9x wins, and at its busiest it used
   **151%** of the account as margin. That is the fingerprint of grids and
   averaging down.
5. **AUD/CAD, NZD/CAD, AUD/NZD only.** These pairs move in narrow ranges, so
   they are the favourite pairs of grid robots. A large share of the
   "smoothest" accounts here (UpFuji, UpEverest, LazyPro, Harmonizer, FX
   Fun, Steady Long term, NoPain) trade almost nothing else.
6. **The seller admits the history is incomplete.** *UpFuji MT4*'s own
   description says its drawdown statistics look low "because the account was
   not on mql5.com from the beginning". The early, worse part of the history is
   missing.
7. **Most of the gain from a handful of days.** MQL5 shows "80% of growth
   achieved within N days". *TP TRADER*: 5 days out of 1,220. *UZUNAMI88*: 6
   days out of 1,310. *SFE Portfolio1*: 21 days out of 4,018. That is a few
   lucky (or very risky) bets, not a steady edge.
8. **Great first years, then fading.** *RFactor Portfolio JM* made +249% and
   +155%, then 0-21% a year. *NightVisionEA* made +154%, then losses. It is
   what you expect when a strategy was tuned to past data, or got lucky early
   and attracted buyers afterwards.
9. **Fills that are too good.** No slippage on any stop loss (*TP TRADER*
   review). Either a very unusual broker or a broker that is not a real
   market. Copiers at normal brokers will not get those prices.
10. **Offshore branch of a famous name.** "IC Markets", "XM", "Eightcap",
    "OANDA" sound safe, but the server names here mostly point to their
    Seychelles, Belize, Bahamas or BVI branches. Weak oversight means less
    protection, and less certainty that the fills are real-market fills.
11. **Seller warns copying won't work.** Several scalpers (R Factor) tell you
    to buy the robot instead, because copied trades arrive late. A strategy
    that only works with millisecond execution won't work on Deriv's
    Multipliers either.
12. **"AI", "neural network", "statistical probability" with no rules.**
    Marketing words, not a strategy you can check.

## Survivorship bias: how much could we trust a "winner"?

Not much, even if one had passed every check.

- **MQL5 lists about 4,300 rated signals, and those are only the
  survivors.** Accounts that blew up or stopped trading drop off the list. We
  looked at the top of the survivors, sorted by MQL5's own rating, so we were
  looking at the luckiest end of a large group by design.
- **Luck alone produces good-looking records.** If 4,000 people each flipped
  a coin every month, about 4 of them would get 10 heads in a row. With
  trading, risky sizing makes lucky streaks even bigger. A 3-5 year record
  with a few hundred trades cannot tell "modest skill" apart from "lucky
  survivor" among thousands. The fading pattern seen in several accounts (red
  flag 8) is what luck looks like over time.
- **MQL5's own concentration warnings say the same.** For many of these
  accounts, 80% of all growth came from about 5% of trading days or less.
- **Their results are on a different price feed and cost.** Even a real edge
  at an ECN broker at 0.5 pip a trade may vanish at Deriv's ~3 pips.

**Confidence in any account found this way: low.** The most a good public
record could ever give us is an idea to test: published rules, run through our
own walk-forward backtest on our data with Deriv's costs, under the same
pass bar as our own strategies. None of these accounts publishes rules, so
there is nothing to test.

## How to check an account yourself (Myfxbook or MQL5)

Do this in a phone browser; you don't need to log in.

1. **Badges** (Myfxbook): both "Track record: verified" **and** "Trading
   privileges: verified". Track record verified alone only means the numbers
   come from the broker. Trading privileges verified means the owner proved
   it is their account and they trade it.
2. **Real or demo** label, and the **start date**: at least 12 months, ideally
   several years.
3. **Gain vs absolute gain** (Myfxbook) or growth vs profit ÷ deposits (MQL5).
   If absolute gain is under a third of gain, look at the deposit history.
4. **Monthly table:** expect some red months. Zero red months in years is a
   warning, not a selling point.
5. **Average win vs average loss** (pips and money) next to the **win rate**.
   80-90%+ wins with losses 3x the wins means averaging down.
6. **Drawdown** under 30%, and check that no single month lost 20%+.
7. **Broker:** look up the exact company name on the regulator's own register
   (UK FCA register, Australia ASIC Connect, Cyprus CySEC). The brand's website
   is not enough; check which branch your account would be in.
8. **Rules:** if you can't write down when it buys and sells, it can't be
   tested, and it shouldn't be trusted with money.

## Method notes

- Sources: MQL5 signal list pages (MT4 and MT5, rating order, pages 1-5) and
  57 signal pages, fetched 2026-10-31. Only paths that MQL5's robots.txt allows
  were fetched, about 80 requests, one every 7 seconds. Myfxbook returned a
  Cloudflare bot check on every page and was not used.
- Pips: MQL5 counts points as "pips" (an MQL5 staff answer in their
  forum), so pip figures above are MQL5's numbers divided by 10.
- Broker branches were judged from the MetaTrader server name and general
  knowledge of each broker's group. Treat a "pass" there as "probably", and
  check the register before relying on it.
- Nothing here changes the trading code, strategies, rules, data or holdout.
