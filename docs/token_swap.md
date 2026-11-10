# Swapping the Deriv token for one that cannot reach real money

Goal (owner, 10 Nov 2026): the VPS should hold a Deriv token that cannot
touch the real account, the old token should be deleted, and no Deriv token
should be left in the claude.ai cloud environment.

**Do this only after the VPS runs v0.1.1 and has worked normally for a day.**

## What Deriv actually allows (checked 10 Nov 2026)

Sources: Deriv's developer docs (developers.deriv.com: authentication, OAuth,
accounts and WebSocket pages) and our own measurements in
`docs/deriv_api_notes.md`.

- **A token cannot be limited to the demo account.** Deriv's docs describe no
  per-account or demo-only token. We measured on 28 Oct 2026 that one token
  sees every account of its login, demo (`DOT...`) and real (`ROT...`).
- **A token can probably be limited to the "trade" permission.** The docs list
  these permissions (called scopes) for logins through apps: `trade` (trading
  and contract status), `payment` (wallet, transfers, payment agents,
  withdrawals), `account_manage` (creating accounts) and `application_read`.
  The bot needs only `trade`: listing accounts, getting the one-time trading
  link, buying and selling all need `trade`. The docs do not describe the
  token page itself, so tick only `trade` if the page offers a choice.
- **But "trade" on your normal login can still trade the real account.**
  Without `payment` the token should not be able to withdraw or transfer
  money. It could still place trades on the real account, though, if someone
  stole it and wrote their own program. The bot itself refuses real money
  unless `DERIV_MODE=real`, a graduated candidate and `CONFIRM_REAL=yes` are
  all set.
- **The only way to make real money truly unreachable: a separate Deriv login
  that has only a demo account.** Sign up again with another email address,
  create only the demo account, never verify it or add money, and make the
  token there. A token can only see the accounts of its own login, so it
  cannot reach your real account at all. Before you do this, check that
  Deriv's terms allow a second, demo-only login.

**Recommendation:** use a separate demo-only login (option A). If you would
rather not, use option B: a new `trade`-only token on your normal login.
Either way, delete the old token afterwards.

Things nothing in the docs answers: whether tokens expire, whether they can be
limited to one IP address, and whether the App ID must belong to the same
login as the token. The steps below cover the App ID case.

## Before you start (5 minutes)

1. In Telegram, send **/open**. It must say **0 bot trades**.
   - If a trade is open, send **/pause**, then wait until /open shows none.
     Trades close by their stop, take profit or deadline. With option A the
     old demo account becomes invisible to the bot, so no trade may be open
     there when you swap.
2. On the VPS, check the version and that the bot is healthy:
   ```
   fxbot version
   fxbot status
   ```
   You want `v0.1.1`, `active (running)` and a heartbeat under 60 seconds.

## Step 1: create the new token (Deriv website, phone browser)

**Option A (separate demo-only login, recommended)**
1. Log out of Deriv. Sign up with a different email address.
2. Create only the demo (virtual) account. Do not add a real account, do not
   verify your identity, do not deposit.
3. Go to account settings, then the **API token** page (it may be called
   "Personal access token").
4. Create a token named `vps-demo`. Tick **only `trade`**. If `trade` is
   called "Trade", tick that. Leave everything else (payments, admin,
   account management, read) unticked.
5. Copy the token once and keep it in your phone's notes app for the next
   step only. Never paste it into a chat, an email or GitHub.

**Option B (same login, minimal permission)**
- Log in as usual, open the **API token** page, create `vps-trade-only` with
  **only `trade`** ticked, and copy it the same way. Do not delete the old
  token yet.

## Step 2: put it on the VPS and restart (SSH app)

1. Open the settings file:
   ```
   sudo nano /opt/fxbot/shared/.env
   ```
2. Change these lines (move with the arrow keys; delete the old value; paste
   the new one; no spaces, no quotes):
   - `DERIV_PAT=` the new token.
   - `DERIV_ACCOUNT_ID=` **leave it empty**. The bot then picks the demo
     account of the new token by itself. If you set it, it must be the new
     demo account's ID (starts with `DOT`).
   - `DERIV_MODE=demo`: check that it still says `demo`.
   - `DERIV_APP_ID=` leave it as it is for now.
3. Save with **Ctrl+O, Enter**, exit with **Ctrl+X**.
4. Check the settings (nothing is traded):
   ```
   fxbot check
   ```
   You want `DERIV_PAT: set` and `Mode: demo`.
5. Restart:
   ```
   fxbot restart
   ```
6. Within a minute Telegram says **"Bot started: DEMO mode"**. Then:
   ```
   fxbot status
   ```
   You want `connected: true` and `account_id` starting with `DOT`. With
   option A it is the NEW demo account's ID.
7. If you sent /pause earlier, send **/resume**. Send **/status** to confirm
   it says running.

**If it does not start:**
- Telegram says "Bot did NOT start" or `fxbot logs 50` mentions `401` or
  `Deriv-App-ID`: with option A the App ID may have to belong to the new
  login. On Deriv's developer site, logged in as the new login, register an
  app (any name), copy its App ID, put it in `DERIV_APP_ID=` in the same file,
  save, `fxbot restart`.
- Anything else: put the old token back in `.env` (you have not deleted it
  yet) and `fxbot restart`. Nothing is lost.

Wait until the bot has run normally for a few hours (Telegram /status, the
daily summary at about 21:35 UTC). Then go on.

## Step 3: delete the old token (Deriv website)

1. Log in with your **normal** login (the one with the real account).
2. Open the **API token** page. Delete **every** token you no longer use.
   - Option A: delete them all. Nothing should use your normal login any more.
   - Option B: delete all except `vps-trade-only`.
3. The old token was also used by the claude.ai cloud sessions. Deleting it
   stops them from reaching Deriv, which is intended.
4. On the VPS, `fxbot status` should still show `connected: true`. It uses
   the new token.

## Step 4: remove the tokens from the claude.ai cloud environment

1. On claude.ai/code, open the environment menu in a session's title bar (or
   the environments list), choose **Fx-bot**, then **Edit**.
2. Under **Environment variables**, delete:
   - `DERIV_PAT` (the Deriv token);
   - `TELEGRAM_BOT_TOKEN` (also a token; the VPS and GitHub keep their own
     copies, so alerts keep working);
   - `DERIV_ACCOUNT_ID`, `DERIV_APP_ID`, `DERIV_MODE`, `TRADING_ENABLED` and
     `TELEGRAM_CHAT_ID` too, if you want nothing Deriv- or bot-related left.
     None of them is secret, but none is needed without the token.
3. Save. Sessions started afterwards no longer have them. A session that is
   already open keeps its old copy until it restarts.

What keeps working afterwards:
- **GitHub Actions** (data collection, incubator, leaderboard): they use no
  Deriv token. GitHub keeps only the Telegram bot token and chat ID as
  repository secrets.
- **The VPS bot**, with the new token.

What stops: cloud sessions can no longer sample Deriv quotes or check the
demo account. A future session that needs them must be given a token again.
