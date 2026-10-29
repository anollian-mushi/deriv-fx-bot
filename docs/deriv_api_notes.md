# Deriv API notes

Written in Phase 0 (2026-10-28) from the current docs at
https://developers.deriv.com (the `llms.txt` index and its pages) plus live
checks against the public WebSocket and the demo account. Items marked
**measured** come from real API replies, not from the docs. Re-check them
before relying on them: Deriv can change prices, limits and ranges.

Old tutorials that use `ws.derivws.com/websockets/v3` and an `authorize`
message describe the previous API. Do not use them.

## 1. Endpoints

| What | Address | Login |
|---|---|---|
| REST API | `https://api.derivws.com` | `Authorization: Bearer <PAT>` + `Deriv-App-ID: <app id>` |
| Public WebSocket (market data, pricing) | `wss://api.derivws.com/trading/v1/options/ws/public` | none |
| Demo trading WebSocket | `wss://api.derivws.com/trading/v1/options/ws/demo?otp=…` | one-time URL from REST |
| Real trading WebSocket | `wss://api.derivws.com/trading/v1/options/ws/real?otp=…` | one-time URL from REST |
| OAuth (not used by this bot) | `https://auth.deriv.com/oauth2/auth`, `/oauth2/token` | browser login |

The symbol field everywhere is `underlying_symbol`.

REST calls we use:
- `GET /trading/v1/options/accounts` lists the accounts this token can use:
  `account_id`, `account_type` (`demo`/`real`), `balance`, `currency`,
  `group`, `status`.
- `POST /trading/v1/options/accounts/{accountId}/otp` returns
  `{"data": {"url": "wss://…/ws/demo?otp=…"}}`.
- `POST /trading/v1/options/accounts/{account_id}/reset-demo-balance` resets
  the demo balance (useful for tests later).

WebSocket calls we will use:
- Market data (public): `active_symbols`, `trading_times`, `contracts_for`,
  `ticks_history` (candles), `ticks`, `proposal` (price quotes), `time`, `ping`.
- Trading (demo/real): `balance`, `buy`, `sell`, `contract_update`,
  `proposal_open_contract`, `portfolio`, `profit_table`, `statement`,
  `transaction`, `forget`/`forget_all`.

## 2. Login flow: PAT + Deriv-App-ID + one-time URL

1. A Personal Access Token (PAT) is created in the Deriv account settings and
   stored as `DERIV_PAT`. It needs the `trade` scope.
2. Every authenticated REST call sends both headers:
   `Authorization: Bearer <PAT>` and `Deriv-App-ID: <DERIV_APP_ID>`.
   Without the App ID header a PAT gets `401 "Deriv-App-ID header is required
   for PAT tokens"`.
3. Call `POST …/accounts/{accountId}/otp`. The reply holds a WebSocket URL
   with a one-time password (OTP) in it. That URL is already tied to one
   account, demo or real.
4. Connect to that URL and send messages directly. There is no `authorize`
   message any more.
5. If the connection drops or the OTP has expired, ask for a **new** OTP URL
   and reconnect. Never reuse an old one.

The OTP URL is a password. We never print or log it, just like the PAT.

`scripts/check_demo_balance.py` does steps 2 to 4 and prints the demo balance.
It refuses to continue unless the chosen account is `account_type: demo` and
the URL path ends in `/ws/demo`.

## 3. Demo vs real

- Demo and real are separate accounts with separate IDs (demo IDs seen so far
  start with `DOT`, real with `ROT`). One PAT can see both.
- The account ID you request the OTP for decides demo or real. The returned
  URL goes to `/ws/demo` or `/ws/real` accordingly.
- Public market data and pricing are the same for both.
- Our rule: the bot only touches the real account when `DERIV_MODE=real`, and
  only places orders when `TRADING_ENABLED=true`. `DERIV_ACCOUNT_ID` is
  optional; without it the scripts pick the demo account automatically.

## 4. Request and rate limits

From the docs (Deriv may change these):

WebSocket, each line is one shared budget, per minute **and** per hour:
- `proposal`, `proposal_open_contract`, `buy`, `sell`: 360/min, 14,400/hour
- `balance`, `statement`: 100/min, 2,000/hour
- `portfolio`, `profit_table`: 30/min, 1,500/hour
- everything else (incl. `contracts_for`, `ticks_history`): 220/min, 14,400/hour
- `ping` is outside these budgets (max 10 per second per connection).

REST:
- per IP: 300 per minute and 1,000 per 10 minutes
- per logged-in user: 80 per minute (you hit this first)

Good practice from the docs: send `ping` every 30 s, reconnect with
exponential backoff, always send `req_id`, check `error` on every reply,
`forget` streams you no longer need. Error code `RateLimit` (WebSocket) or
HTTP 429 (REST) means slow down.

### Candle history (measured, Phase 1)

- `ticks_history` with `style: "candles"` works on the public WebSocket for
  `granularity` 60 (1m), 900 (15m) and 3600 (1h).
- **History depth is about one year, at every granularity**, and it is a
  rolling window: on 2026-10-28 the first full day was 2025-10-29 for all
  three pairs. Older data cannot be fetched again later, which is why the
  collector saves every day and a daily workflow keeps it up to date.
- **Reply cap:** about 1,000 candles for 1m and about 700 for 15m/1h, even
  with `count: 5000`. When a window has more, you get the most recent ones.
  The collector asks for 600 candle slots at a time.
- **Pitfall 1:** asking for a window older than the available history does
  not return an error. It returns the most recent candles instead. The
  collector checks that every returned candle lies inside the window it
  asked for.
- **Pitfall 2:** if `start` is not on a candle boundary, the first candle is
  a partial one stamped with the `start` time (e.g. a 1h candle at 19:07).
  The collector only asks for aligned windows and drops unaligned candles.
- **Separate, stricter rate limit for history:** old-data requests count
  against `ticks_history_expensive` (not on the Limits page): about 30
  requests, then about 30 per minute. The error is `RateLimit` with the
  message "You have reached the rate limit for ticks_history_expensive".
  The collector waits 2.2 s between requests (~27 per minute) and backs off
  30 s on this error.
- Holiday hours: 24 and 31 December closed early at 22:15 GMT; 25 December
  and 1 January were closed.

## 5. Multiplier contracts

### What it is, in plain language

You choose a direction (`MULTUP` = price goes up, `MULTDOWN` = price goes
down), a **stake** (the money you put in) and a **multiplier**. Your position
behaves like a position worth `stake × multiplier`. The most you can lose is
the stake. There is no expiry; the trade stays open until you close it, a
take profit or stop loss is hit, or it is stopped out.

### Forex details (measured on 2026-10-28)

| | EUR/USD | GBP/USD | USD/JPY |
|---|---|---|---|
| Symbol | `frxEURUSD` | `frxGBPUSD` | `frxUSDJPY` |
| Pip size | 0.00001 | 0.00001 | 0.001 |
| Hours (GMT) | Mon–Fri 00:00–23:59:59 | same | same |
| Early close | Fridays at 20:55 | same | same |
| Holidays listed | 2026-12-25, 2027-01-01 | same | same |
| Multipliers (demo and real account) | 100, 200, 300, 500, 800 | same | same |
| Base commission (share of stake × multiplier) | 0.0239% | 0.0203% | 0.0275% |
| Stake | 1 to 2,000 USD | same | same |
| Deal cancellation | not available | not available | not available |

**Updated in Phase 2 (2026-10-29), see `reports/costs.md`:**
- The multiplier list depends on the connection:
  - The **public** connection (no login) quotes 50/100/150/250/500.
  - The **demo and real** accounts quote and buy 100/200/300/500/800, the
    same as `contracts_for`.

  The Phase 0 figures above this note came from the public connection.
- **Commission changes during the day and around news**, and is identical on
  real and demo at the same moment:
  - base rate 06:00–17:59 UTC;
  - 2–12× in the evening, highest just after the daily pause.
- **New trades are refused 20:55–21:30 UTC daily.** This is not shown in
  `trading_times`.

### How it is priced and charged

Checked against real quotes (stake 10 USD on EUR/USD):

- **Position size** = stake × multiplier. At x100, 10 USD acts like 1,000 USD.
- **Commission** = max(0.02 USD, commission rate × stake × multiplier),
  charged once when the trade opens. At x100: 0.02% × 1,000 = **0.20 USD**
  (quote said 0.2). At x50 it was 0.10 USD.
  - The rate varies by hour and around news (Phase 2), so read it from each
    quote.
  - The `commission` field is rounded to cents, but Deriv sets TP/SL/stop-out
    prices with the **unrounded** amount.
- **Profit/loss** = stake × multiplier × (price change ÷ entry price) −
  commission. For Down trades the sign of the price change is flipped.
  (Deriv's own formula: "(% of price difference × multiplier × stake) –
  commission".)
- The quote's `longcode` text says "multiplied by 1000" for a x100 contract.
  The stop-out and take-profit prices in the same quote match x100, so the
  text is just a display quirk.

### How it is closed

1. **Stop out (automatic, always on):** the trade closes when the loss,
   including the commission, reaches the whole stake. Example at x100, stake
   10, EUR/USD at 1.11249: stop out at 1.10158. That is a 0.98% move, which
   is (10 − 0.20) ÷ 1,000. Higher multiplier = stop out closer to the entry
   price.
   - The price is rounded to the pip size **away from the entry**.
   - Our formula matches every demo and real quote exactly (Phase 2).
2. **Take profit (optional):** `limit_order.take_profit` in USD. The amount
   is **after** commission: take profit 5 USD at x100 was set at a +0.52%
   move = (5 + 0.20) ÷ 1,000. Allowed range from the quote: min 0.10, max
   varies (450 at x50, 500 at x100 for a 10 USD stake).
3. **Stop loss (optional):** `limit_order.stop_loss` in USD, also after
   commission. Must be larger than the commission (min 0.21 at x100, 0.11 at
   x50) and at most the stake.
   - Use at least **commission + 0.02**: Deriv's own check sometimes rejects
     the exact minimum.
   - Deriv closes at the first tick at or past the level, at that tick's
     mid, so a jump past the level costs the size of the jump.
4. **Manual close:** `sell` with the `contract_id` and `price: 0` (sell at
   market). The fill can differ from the last price you saw (slippage).
5. Take profit and stop loss can be changed or removed on an open trade with
   `contract_update` (`null` removes one).
6. Watch an open trade with `proposal_open_contract`: `bid_price`, `profit`,
   `commission`, `is_sold`, `is_valid_to_sell`, `status`
   (`open`/`sold`/`won`/`lost`/`cancelled`) and the current `limit_order`.
   - Contracts Deriv closes itself (TP, SL, stop out) come back with
     `status: null`, so check `is_sold`.

### Buying safely

- Get a `proposal` first, then `buy` with the proposal `id` and
  `price` = the quoted `ask_price` (the maximum we are willing to pay).
- A buy by proposal ID cannot be bought twice; a buy with `buy: 1` and
  parameters can. If a buy reply is lost, check `statement` (action `buy`,
  recent `date_from`) before trying again. Never resend blindly.
- Before resending a `sell`, check `is_sold` with `proposal_open_contract`.

### What this means for our risk limits

- With 50 to 100 USD, the 3% per-trade cap allows a stake of 1.50 to 3.00
  USD. Deriv's minimum stake is 1 USD, so it fits.
- Because the stake is the most a trade can lose, "stake = max loss" holds
  even without a stop loss. A stop loss lets us lose less than the stake.

### Still unknown (to check on demo in later phases)

Answered in Phase 2 (`reports/costs.md`):
- **Overnight charge:** none, on one weekday night.
- **Entry slippage:** 0–0.5 pip. Entry and exit fill at the mid price, with
  no spread.
- **Limits:** do not change with stake size.

Still open, for the Phase 6 demo run:
- Weekend: any charge, and what a Monday gap does to an open contract (stop
  loss fill, stop out).
- Commission by hour on more than one day, especially on news days.
