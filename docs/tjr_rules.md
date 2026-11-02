# TJR method: mechanical rules

Status: **approved by the owner on 2 Nov 2026, with changes to C18, C23 and C28** (marked
"owner" below). No data has been read for this document. The code is
`src/fxbot/strategies/tjr.py` and `tjr_calendar.py`; the Step 2 test plan is
`docs/tjr_test_plan.md`. Written 2 Nov 2026 on branch `tjr-smc` from the owner's 11 course notes
(1 Candlesticks, 2 Trends, 3 Break of structure, 4 Liquidity, 5 Fair value gaps, 6 News,
7 Order block, 8 Equilibrium, 9 Execution, 10 Take profit and stop loss, 11 Final touch).

The notes are written for a person looking at a chart. A backtest needs every word turned
into a yes/no rule a program can check. Wherever the notes leave room for interpretation, this
document makes one choice and names one alternative. They are numbered **C1, C2, ...** and
collected in the table in section 14.

Two rules from the notes apply everywhere:

- **Closed candles only** (note 1, "never make decisions on a candle that is still forming").
  Every check below runs when a candle has closed. A level, sweep, break or gap is known only
  from the moment its last candle closes. That moment is also the earliest a trade can open.
  This is what keeps the backtest from seeing the future.
- **Single candle patterns are not entry signals.** Note 1 reads hammers, dojis and wicks *in
  context*. In this method the context is the liquidity sweep (section 4), which is exactly a
  long rejection wick at a prominent level. Candle shapes are not used as a separate filter.
  (C1)

---

## 1. Words, times and candles

- **Pip**: 0.0001 for EUR/USD-style pairs, 0.01 for JPY pairs (`fxbot.symbols`).
- **Candles** are built from Deriv/Dukascopy 1m data. 5m, 15m, 30m, 1h and 4h candles
  start on round UTC times (for example 4h candles start at 00:00, 04:00, 08:00 ... UTC).
  Daily candles use UTC midnight, as everywhere else in this project. (C2)
- **Timeframes used**

  | Job | Timeframe | Notes source |
  |---|---|---|
  | Bias (direction allowed) | Daily and 4h | notes 2, 3, 9, 11 |
  | Liquidity sweep | 30m | notes 2, 4 ("30M sweep, 5M BOS") |
  | Execution: break of structure, order block, FVG, entry | 5m or 15m (both tested) | notes 2, 4, 5 |

  The sweep timeframe is 30m for both execution timeframes. (C3)
- **Session clocks** follow New York time, including its summer-time changes (C4).
  New York is UTC-5 in winter and UTC-4 in summer. Example: 07:00 New York is 12:00 UTC
  in winter and 11:00 UTC in summer.

---

## 2. Swing highs and swing lows

Note 3: a valid high needs "a clear movement up followed immediately by a movement down",
at least two candles, and the point is the highest wick.

**Rule.** A candle is a **swing high** with strength *k* if its high is higher than the highs
of the *k* candles before it and the *k* candles after it. A **swing low** is the mirror image,
using lows. For a tie on the left side (equal highs), the later candle counts. The level is
the wick (high or low), not the body.

**Strength used** (C5):

| Where | k | Why |
|---|---|---|
| Execution timeframe (5m/15m) | 1 | the notes' "two candle" minimum: one candle each side |
| 30m liquidity levels | 2 | "prominent" levels should stand out more than every small wiggle |
| 4h and daily bias | 2 | same reason |

**When it is known.** A swing is only confirmed after the *k* candles to its right have
closed. For example, a 5m swing high at the 10:05 candle is known at 10:15, when the 10:10
candle closes.

*Example (5m, EUR/USD).* Highs: 10:00 1.16480, 10:05 **1.16520**, 10:10 1.16490. The
10:05 candle is a swing high at 1.16520, known from 10:15.

---

## 3. Prominent highs and lows (where the liquidity sits)

Note 4: liquidity rests above "prominent highs" (buy-stops) and below "prominent lows"
(sell-stops). Note 11's GBP/JPY case sweeps "the Asian and London session highs". A level
is **prominent** if it is one of these:

| Level | Definition | Known from |
|---|---|---|
| Previous day high / low (PDH / PDL) | high and low of the previous UTC day (C2) | 00:00 UTC |
| Asian session high / low | high and low from 20:00 to 00:00 New York time (C6) | 00:00 New York |
| London session high / low | high and low from 02:00 to 05:00 New York time. Used as a level only for New York session trades | 05:00 New York |
| Recent 30m swing highs / lows | 30m swings (k = 2) formed in the last 24 hours (C7) | when confirmed |

**A level can be used once.** As soon as any 30m candle's wick has gone beyond a level, that
level is "taken" and is no longer a liquidity pool, whether or not the move counted as a
sweep.

Equal highs and lows (note 2 mentions them) are not a separate type. A double top on 30m
already appears as a 30m swing. (C8)

---

## 4. Liquidity sweep

Notes 3 and 4: price pushes just past a prominent level, triggers the resting orders, and
"immediately reverses", leaving a long wick. Only a wick goes through. A close beyond the
level is a breakout, not a sweep.

**Rule (sweep of a high, buy-side liquidity, sets up a SHORT).** A closed 30m candle is a
sweep if:

1. its **high is above** an untaken prominent high (any distance above counts) (C9), and
2. it **closes back below** that level (wick beyond, close back inside).

**Sweep of a low** (sets up a LONG) is the mirror image.

- If one candle sweeps several highs, the setup is the same. The sweep extreme is the
  candle's high.
- If one candle sweeps both a high and a low, it is ignored (no clear direction).
- **The sweep extreme** is the wick tip (the 30m candle's high for a short). It is used for
  the stop loss (section 10) and the dealing range (section 8).
- The sweep must happen inside the London or New York session window (section 11). The
  level itself may be older (for example the Asian high).

*Example (30m, EUR/USD, short setup).* The Asian high is 1.16400. The 08:00-08:30 UTC candle
trades up to **1.16460** and closes at 1.16370. It swept the Asian high by 6 pips and closed
back inside, so this is a sweep. The sweep extreme is 1.16460, known at 08:30. If that
candle had closed at 1.16420 (above the level), it would be a breakout, not a sweep. The
level would still count as taken.

---

## 5. Break of structure (BOS) on the execution timeframe

Note 3 sets the body-close rule: "a BOS is ONLY valid when a candle body closes completely
beyond the key high or low". Note 2: after the 30m sweep, "wait for the 5M price action to
break its immediate higher low".

**Rule (short after a high was swept).**

1. **Reference level** = the most recent execution-timeframe swing low (k = 1) whose
   candle is **before the candle that made the sweep extreme**. This is the last "higher
   low" of the move up into the sweep (C10).
2. **The BOS** is the first execution candle that **closes below** the reference level
   (a close, not just a wick) (C11), with:
   - its close time at or after the 30m sweep candle's close (so we never act inside a
     30m candle that has not finished), and
   - its close time within **N execution candles** of the sweep candle's close. N is a
     Step 2 setting, for example 6 or 12 candles.
3. **Setup cancelled** if, before the BOS, any execution candle trades above the sweep
   extreme (the sweep failed), or if N candles pass without a BOS.

A long setup is the mirror image (break of the last swing high before the swept low,
by a close above it).

*Example (5m, continued).* Before the sweep, the last 5m swing low below the 08:15 UTC
candle that made the 1.16460 high was **1.16310** (the 07:45 candle). At 08:30 the sweep
is confirmed. The 08:40-08:45 candle closes at **1.16290**, below 1.16310. That is the BOS,
known at 08:45, 3 candles after the sweep (inside N).

---

## 6. Higher-timeframe bias (daily and 4h)

Notes 2, 3, 9 and 11: the daily and 4h charts decide the direction. "A daily BOS will
always override a 15-minute BOS." Trading against the daily bias is the main reason a
perfect setup fails (note 9).

**Rule.** On each of daily and 4h, separately:

- track swing highs and lows (k = 2, section 2);
- a **bullish BOS** is a candle that closes above the most recent confirmed swing high;
  a **bearish BOS** closes below the most recent confirmed swing low. Each swing level can
  be broken only once ("rule of recency": only the latest pivot counts);
- the **bias** is the direction of the most recent BOS on that timeframe. It stays until
  an opposite BOS.

**Trades are allowed only when the daily bias and the 4h bias agree, and only in that
direction** (C12). A short needs both daily and 4h bearish. When they disagree, no trade
(note 11, GBP/USD case: "fighting the daily trend"; note 11, gold case: conflicting
timeframes = no-trade zone).

Only closed candles count. A trade at 09:00 UTC uses yesterday's daily candle and the 4h
candles closed by 08:00 UTC.

---

## 7. Fair value gap (FVG): the three-candle rule

Note 5, exactly:

- **Bullish FVG**: candles 1, 2, 3 in a row, candle 2 bullish (close above open), and the
  **low of candle 3 is above the high of candle 1**. The zone is from candle 1's high
  (bottom) to candle 3's low (top).
- **Bearish FVG**: candle 2 bearish, the **high of candle 3 is below the low of candle 1**.
  The zone is from candle 3's high (bottom) to candle 1's low (top).
- If the wicks of candles 1 and 3 touch or overlap, there is no FVG.
- Any gap size above zero counts. No minimum size, and no "big candle 2" test beyond its
  colour (C13).
- **Invalidated** (note 5, rule 3) when an execution candle closes beyond the far side of
  the zone. For a bearish FVG that is a close above its top. An invalid FVG is never used.
- Known when candle 3 closes.

**Which FVG a setup uses.** Only bearish FVGs formed in the **displacement leg** of a short
setup count: candle 1 at or after the candle that made the sweep extreme, candle 3 at or
before the BOS candle. That is "the FVG left behind by the breakout" (note 9). If there are
several, the setup uses the first one price reaches on its way back, which is the one
nearest to the current price (C14). This keeps to note 5's rule that an FVG is a
continuation tool, never a reversal tool: the FVG points in the new direction that the BOS
has just confirmed.

*Example (5m).* Candle 1 (08:30) low 1.16380. Candle 2 (08:35) bearish. Candle 3 (08:40)
high 1.16350. The bearish FVG is 1.16350-1.16380.

---

## 8. Order block, equilibrium, premium and discount

### Order block (note 7)

Note 7: the order block is "the final candle that directly engineered the liquidity sweep",
"the last contrasting candle ... that directly caused the liquidity sweep". There is
"ONLY ONE valid order block per trend". Note 9 says "the exact candle responsible for the
initial sweep".

**Rule (short setup).** The order block is the **last bullish execution candle (close above
open) at or before the candle that made the sweep extreme**. That is the final up-candle
that pushed price into the buy-side liquidity. **Zone = that candle's full range, low to
high, wicks included** (C15). One order block per setup. It is used up after the first
retracement into it.

Long setup: the last bearish candle at or before the swept low.

*Example.* The 08:15 5m candle (open 1.16380, close 1.16440, high 1.16460, low 1.16370)
made the sweep high and is bullish. It is the order block, zone 1.16370-1.16460.

### Equilibrium, premium and discount (note 8)

Note 8: equilibrium is the 50% point between a swing high and a swing low "born from a
recent liquidity sweep". A dealing range is marked "from the exact wick of the swing high
to the wick of the swing low". It is a filter, never an entry signal on its own.

**Rule (short setup).** The **dealing range** runs from the sweep extreme (top) down to the
lowest low the execution candles have made since the sweep, up to the moment of the check
(C16). **Equilibrium** = its midpoint.

- **Premium** = above equilibrium. Shorts only.
- **Discount** = below equilibrium. Longs only.

*Example.* The sweep high is 1.16460. The lowest low since then is 1.16260. Equilibrium is
1.16360. A short is in premium only above 1.16360.

---

## 9. The four entry models (note 9)

All four start the same way: **bias agrees (section 6) → 30m sweep against the bias
(section 4) → execution-timeframe BOS in the bias direction (section 5).** A short needs a
bearish bias, a sweep of a high, then a bearish BOS. This is note 2's stack: "Daily/4H bias
→ 30M sweep → 5M BOS". They differ only in where the trade is entered.

| Model | Note 9 formula | Entry rule (short; long is the mirror image) |
|---|---|---|
| **1 Foundation** | sweep + BOS | Enter when the BOS candle closes. |
| **2 Order block** | sweep + BOS + OB | After the BOS, wait for price to come back up into the order block zone. |
| **3 FVG** | sweep + BOS + FVG | After the BOS, wait for price to come back up into the displacement FVG. |
| **4 Sniper** | sweep + BOS + (OB or FVG) + equilibrium | As 2 or 3, but only if the **whole zone** is in premium (its bottom edge above equilibrium) (C17). If both the OB and an FVG qualify, the first one reached is used. |

**What "enter" means here.** Deriv Multipliers have no limit orders. Every entry is a market
buy at the open of the next 1m candle, plus 0.5 pip of slippage (the project's standard
fill).

- **Model 1:** the entry is at the first 1m open after the BOS candle closes.
- **Models 2-4 (retracement), owner's C18:** as notes 7 and 8 say, touching the zone is not
  enough. Inside the zone, wait for a fresh **lower-timeframe sweep plus a break of
  structure** on the *confirmation timeframe*: 1m candles for 5m execution, 5m candles for
  15m execution.
  1. **Touch:** a confirmation candle reaches into the zone (its high reaches the zone's
     bottom, for a short). It must happen within N execution candles after the BOS. If
     several zones are reached at once, the first one on the way (the lowest, for a short)
     is used.
  2. **Fresh sweep inside the zone:** a confirmation candle whose wick reaches into the zone
     goes above a confirmation-timeframe swing high (k = 1) that formed *after* the BOS, and
     closes back below it. Each such swing can be swept once.
  3. **Break:** within N confirmation candles of that sweep, a confirmation candle closes
     below the last confirmation-timeframe swing low that formed before the sweep candle.
     The trade opens at that close. If price trades above the small sweep's wick first,
     that small sweep is void and the next one is awaited.
  - The zone is dropped if an execution candle closes beyond its far side (above the top,
    for a short). The setup is cancelled when no zone is left, or when the session window
    ends.
  - The setup is also cancelled if price trades through the 30m sweep wick (the stop level),
    or if price reaches the "draw" before the entry. The draw is the nearest untaken opposing
    liquidity level beyond the low made since the sweep ("the market moved without you",
    note 7).
  - At the moment of entry, the entry price must be in premium for every short (note 8:
    "shorting below equilibrium ... is institutional suicide"). Model 1 is exempt: the
    BOS close is normally in discount, and note 9 says model 1 accepts a wider stop.
  - **Labelled alternative (C18-alt, "touch"):** enter at the close of the first execution
    candle that reached into the zone and closed below the zone's top. This was the first
    draft's rule. It is tested as one variant per model, never as the main version.

**One trade per sweep, and at most one trade per pair per session** (London, New York)
(C19). A pair has at most one setup at a time. While it waits, a new sweep on that pair is
ignored, unless it trades through the waiting setup's stop level, which cancels the old
setup first. The CLAUDE.md risk module still applies on top: at most 2 open trades, at most 1 per
pair, and so on.

Notes 7 and 8 also describe a "full top-down" version: price first retraces into a
*higher-timeframe* order block or FVG, and only then the sweep and BOS on the execution
chart count. This is not one of note 9's four models, so it is left out (C20).

---

## 10. Stop loss

Note 10: the stop goes "strictly just beyond the high or low of the initial liquidity sweep"
plus a spread buffer ("at least a 0.5-point buffer"). It is never placed at the small swing
of the entry candle.

**Rule (short).** Stop = **the 30m sweep candle's wick + 1 pip** (C21). That holds for all four
models (owner's point 4, 2 Nov 2026). It is never placed at an execution-timeframe or
confirmation-timeframe swing, not even after the 1m/5m confirmation of models 2-4. The stop
distance is measured from the actual entry price (slippage included). In models 2-4 the
entry is closer to the sweep, so the stop is tighter. That is the point of those models.

Notes 7 and 10 allow a tighter stop behind an internal OB or FVG. That is not used: note 10
warns that it raises the chance of being wicked out.

**How it maps onto a Deriv Multiplier.** The stake is the most a trade can lose (CLAUDE.md:
stake at most 3% of balance). The stop loss is set as a USD amount = stake x multiplier x
(stop distance / entry price). The multiplier is x200, or x100 when the stop is wider than 0.4%
of the price (80% of the x200 stop-out move). A trade is skipped if its stop is wider than
0.8% of the price (C22), because then Deriv's stop out (about 1% at x100, about 116 pips on
EUR/USD) could come first and the stop would not be the real exit. As a second guard, the
engine refuses any stop at or beyond the stop out.

**Cost rule (owner, Step 2):** a trade is skipped if its stop is closer than 4x its cost
per trade. Cost per trade = commission at the rate for the entry hour (from
`research/phase2/cost_by_hour.json`) + 0.5 pip entry slippage. At the base rates that floor
is about:

| Pair | Commission (pips) | + slippage | Minimum stop (4x) |
|---|---|---|---|
| EUR/USD | 2.8 | 3.3 | **13 pips** |
| GBP/USD | 2.7 | 3.2 | **13 pips** |
| USD/JPY | 4.3 | 4.8 | **19 pips** |

Heads-up: many 5m sweep-to-BOS stops are 5-15 pips, and the tighter OB/FVG stops of models
2-4 are smaller still. This rule will therefore remove a large share of 5m setups,
especially in models 2-4. That is intended: it is what Deriv's cost does to small stops.
The Step 2 report will show how many setups each rule removes.

---

## 11. Take profit and the end of the trade

Note 10 ranks take profit as the least important part, rejects "arbitrary, rigid profit
ratios", and sets targets at opposing liquidity: "Target 1 at the nearest liquidity or 1:1,
targets 2 and 3 at higher-timeframe gaps or swings", taken as partial profits.

**Constraint.** One Deriv contract has one take profit, and CLAUDE.md allows only one open
trade per pair. Partial profits (splitting into 3-4 positions) are therefore not possible.
Owner's C23: **one contract, one target at opposing liquidity**, plus one variant with a
stop update.

- **Target (all variants):** the nearest untaken prominent level on the other side
  (section 3: PDL, Asian low, London low, 30m swing lows for a short). Only levels beyond
  the lowest price since the sweep count; levels the move already traded through are used
  up. If that level is less than 1R from the entry (reward smaller than the risk), the next
  one beyond it is used. If none exists within 5R, the target is 5R (C24).
- **Break-even variant (owner's C23):** once price has moved 1R in the trade's favour, the
  stop is moved with Deriv's stop-loss update (contract_update) to the smallest stop Deriv
  accepts: **commission + 0.02 USD**. The trade can then lose only about the commission,
  the 2 cents and the usual 1 pip of stop slippage. The backtest models it on 1m candles:
  the update takes effect from the minute *after* the one that reached 1R. If a single
  minute reaches 1R and falls back, the old stop still applies in that minute. After that,
  the moved stop fills like any stop (1 pip past it, or past a gap open).

*Example.* Short at 1.16380, stop 1.16470 (9 pips, so R = 9 pips). The Asian low 1.16180
is 20 pips away (2.2R), so the take profit is 1.16180. In the break-even variant, the stop
moves to about 1.16383 once price trades at 1.16290. (On EUR/USD this trade would be skipped
anyway: a 9-pip stop is under the 13-pip cost floor.)

**Time exit.** Every trade still open at **17:55 UTC** is closed at market (C25). TJR trades
the morning sessions. This also gets out before FOMC statements (14:00 New York = 18:00 or
19:00 UTC) and before Deriv's evening cost rise. No trade is held overnight, so x200 is
allowed by CLAUDE.md. The Friday 20:30 UTC rule is then automatic.

---

## 12. Sessions (note 11: London and New York only)

New trades open only inside these windows, in New York time (C4, C26):

| Session | New York time | UTC in winter | UTC in summer |
|---|---|---|---|
| London | 02:00-05:00 | 07:00-10:00 | 06:00-09:00 |
| New York | 07:00-11:00 | 12:00-16:00 | 11:00-15:00 |

Both windows lie inside CLAUDE.md's fixed entry window (06:00-17:59 UTC) all year round. The
Asian session is used only to mark its high and low (note 11: "avoid the low-liquidity chop
of the Asian session").

**Days off:** no trading on U.S. bank holidays (note 10, "bank holiday freeze"), using the
Federal Reserve holiday list worked out from its fixed date rules (C27). No trading on
weekends or Deriv's closed days (CLAUDE.md calendar).

---

## 13. News rules (notes 6, 7, 11)

Notes: trade around red-folder (high-impact) news only, and only for **the currencies in the
pair** (note 6, "currency specialization"). Never trade during CPI, PPI, FOMC or NFP. After a
red-folder release, wait 15-30 minutes before looking for a setup. Note 11 adds: on CPI, PPI
and claims days, "do not force trades".

We have no historical calendar, so the rules use **known release times every weekday**,
whether or not a release happened that day (C28). That blocks more than needed. It never
blocks less than needed for releases at these times. Owner's C28 (2 Nov 2026) sets the full
list:

| Currency | Releases (all red folder) | Release time | No new entries |
|---|---|---|---|
| USD | CPI, PPI, NFP, jobless claims (and the other 08:30 data) | 08:30 New York | **08:15-09:00 New York, every weekday** |
| GBP | UK CPI, GDP, jobs | 07:00 London | **06:45-07:30 London, every weekday** |
| USD | FOMC statement / press conference | 14:00 / 14:30 New York | after the session window anyway; **all trades are closed by 17:55 UTC** (section 11) |

- A block applies to a pair if either of its currencies is in the row. For example, the
  USD row applies to EUR/USD, USD/JPY and USD/CAD but not to EUR/GBP or GBP/JPY. The GBP
  row applies to GBP/USD, EUR/GBP and GBP/JPY.
- The first draft's 09:45-10:30 New York block (ISM, JOLTS) is removed. Its euro-area, ECB,
  Bank of England and SNB rows are not part of the owner's list either, so they are not
  used.
- Each window starts 15 minutes before the release and ends 30 minutes after it (note 6:
  wait 15-30 minutes).
- Trades already open are kept through a release, protected by their stop (C29). The notes
  forbid *executing* during news. They do not say to close.
- Each local time follows its own city's summer-time changes.
- Not modelled: note 6's "if the chart is a volatile mess after the news, don't trade the
  rest of the day" and "skip heavy news days". Without a calendar we cannot tell which
  days were heavy (C30).

---

## 14. Every interpretation choice and one alternative

| # | Topic | Choice made | One alternative |
|---|---|---|---|
| C1 | Candle patterns | not a separate filter; the sweep already is the rejection wick | require the 30m sweep candle's wick to be at least 2x its body |
| C2 | Day boundary | UTC midnight (project standard) | New York 17:00 close (common forex daily candle) |
| C3 | Sweep timeframe | 30m for both 5m and 15m execution | 1h when executing on 15m |
| C4 | Session clock | New York local time, following summer time | fixed UTC hours all year |
| C5 | Swing strength | k = 1 on execution, k = 2 on 30m, 4h and daily | k = 1 everywhere (more swings, more signals) |
| C6 | Asian session | 20:00-00:00 New York | 00:00-06:00 UTC (Tokyo hours) |
| C7 | "Recent" 30m swings | formed in the last 24 hours and not yet taken | last 48 hours |
| C8 | Equal highs/lows | not a separate level type | add pairs of 30m highs within 2 pips as an extra level |
| C9 | Sweep depth | any distance beyond the level | at least 1 pip beyond, and no more than half a typical 30m range (deeper = breakout) |
| C10 | BOS reference | last execution swing low before the sweep extreme (the "higher low" of the move up) | most recent execution swing low at BOS time, which may form after the sweep (earlier, more frequent entries) |
| C11 | Body close | the close is beyond the level | the whole body (open and close) is beyond the level |
| C12 | Bias | daily and 4h must agree | daily only, as note 9 calls daily bias "the anchor" (note 11 suggests half size when 4h disagrees) |
| C13 | FVG size | any gap above zero; candle 2 only needs the right colour | gap at least 10% of the 14-candle average range, and candle 2's body at least half its range |
| C14 | Which FVG | the displacement-leg FVG nearest to price (reached first) | the FVG made by the BOS candle itself |
| C15 | Order block zone | last opposite candle before the sweep extreme, full range | the same candle's body only (open to close), a tighter zone |
| C16 | Dealing range | sweep extreme to the lowest low since the sweep | the most recent 4h swing high to swing low (note 8 mentions 4H) |
| C17 | Model 4 "inside premium" | the whole zone above equilibrium | the zone's midpoint above equilibrium |
| C18 | Retracement entry | **owner:** inside the zone, a fresh confirmation-timeframe sweep plus a break (1m for 5m execution, 5m for 15m) | the first draft's touch-and-close, kept as one labelled alternative variant ("touch") |
| C19 | Trade count | one per sweep, at most one per pair per session | one per sweep, no session cap (only the risk module's limits) |
| C20 | Top-down HTF zone version | not tested (not one of the four models) | add as a fifth model: 1h order block or FVG retracement, then 5m sweep and BOS inside it |
| C21 | Stop buffer | 1 pip beyond the sweep wick | 0.5 pip (note 10's "0.5 point") |
| C22 | Stop beyond Deriv stop out | x200; x100 if the stop is wider than 0.4% of price; skip if wider than 0.8% | take it and let Deriv's stop out act as the stop |
| C23 | Partials / break even | **owner:** one contract, one target at opposing liquidity; fixed-R targets dropped | variant: at +1R the stop moves to Deriv's smallest stop (commission + 0.02) via contract_update, modelled in the backtest |
| C24 | Liquidity target | nearest untaken opposing level beyond the low since the sweep and at least 1R away, else 5R | nearest opposing level whatever its distance; skip the trade if under 1R |
| C25 | Time exit | close everything at 17:55 UTC | hold until stop or target, up to 20:30 UTC |
| C26 | Session windows | London 02:00-05:00 NY, New York 07:00-11:00 NY | the whole CLAUDE.md entry window 06:00-17:59 UTC |
| C27 | Bank holidays | no trading on U.S. Federal Reserve holidays, all pairs | only pairs containing USD |
| C28 | News calendar | **owner:** every weekday, USD pairs 08:15-09:00 New York, GBP pairs 06:45-07:30 London; FOMC avoided by the 17:55 UTC flat time | build a dated calendar from official archives (Fed, BLS, ONS) and block only real release days, plus the whole day on CPI, PPI, NFP and FOMC days (note 11) |
| C29 | Open trades at news | kept, protected by the stop | closed 5 minutes before a blocked release |
| C30 | Messy chart after news | not modelled | skip the rest of the day if the release's 30m candle is over 2x the pair's average 30m range |

---

## 15. How this fits the project rules, and what to expect

**Every CLAUDE.md hard limit applies unchanged.** The strategy only proposes trades. The risk
module decides: stake at most 3% of balance, daily loss limit 10%, kill switch at 50%, at
most 2 open trades and 1 per pair, x100 or x200 only, the live cost gate (skip if the
commission is above 1.5x the pair's base rate), the entry window 06:00-17:59 UTC, the daily
pause, and flat before weekends.

**Approved by the owner (2 Nov 2026):**

1. **5m and 15m execution, for this research only.** This is an exception to CLAUDE.md's
   "research 1h and 4h candles ... 15m is out". The 4x-cost stop rule is the safeguard. The
   engine now also runs 1m, 5m and 15m strategies; existing strategies behave exactly as
   before. A 1m/5m/15m signal that cannot fill within 2 minutes (blocked by a limit or the
   calendar) is dropped, not delayed.
2. **The 4x-cost stop rule**, C3, C5, C10, C12 and C26 as written.
3. **News by fixed times** (C28, as changed by the owner).

The live bot (`src/fxbot/live/`) does not yet know the stop-loss update or the 1m/5m/15m
timeframes. That is only needed if a TJR variant ever passes and is approved for more than
paper testing.

**Honest expectations (from earlier research, before any TJR test).**
- The incubator pre-screen already tested a close cousin of model 1 on 1h candles,
  `turtle_soup`: fade a failed sweep of yesterday's high or low. It earned +0.2 USD before
  costs over 3 years (a coin toss) and too few trades.
- That round also found these pairs show mild *continuation*, not reversal, at the
  1h-to-1-day scale.
- What TJR's method adds is the bias filter (trade the sweep only *with* the daily/4h trend,
  which is a continuation idea), the execution-timeframe BOS confirmation, and session
  levels. So it is not the same test. But the bar is clear: about 3-5 pips of cost per
  trade, against small 5m stops.

**No data has been read for this document.** In Step 2, all data stays strictly before
2026-10-31 (`fxbot.data.split.UNTOUCHED_START`).

**Next:** Step 2 (`docs/tjr_test_plan.md`). The 30 variants are fixed there before anything
runs. The runs start only after the 3 and 5 Nov clock-change re-check has updated
`research/phase2/cost_by_hour.json`.
