# Running the bot on your VPS (from a phone)

This guide assumes an **Ubuntu 24.04** VPS and an SSH app on your phone
(for example Termius, Blink or JuiceSSH). Every command below is one line:
copy it, paste it into the SSH app, press Enter.

**What runs:** the live bot trades the **demo** account with one incubator
candidate. It uses a pretend balance of 100 USD, so stakes are about 3 USD.
It never touches real money unless three separate things are all set (see
[Real money](#real-money-not-yet)).

## Contents
1. [Before you start](#before-you-start)
2. [Install (once)](#install-once)
3. [Start, stop, restart](#start-stop-restart)
4. [Is it working?](#is-it-working)
5. [Telegram](#telegram)
6. [Logs](#logs)
7. [Switch the candidate (STRATEGY_ID)](#switch-the-candidate-strategy_id)
8. [Update to a new release](#update-to-a-new-release)
9. [Roll back](#roll-back)
10. [Clear a halt (kill switch or /stop)](#clear-a-halt-kill-switch-or-stop)
11. [Copy the journal](#copy-the-journal)
12. [Alerts and what to do](#alerts-and-what-to-do)
13. [Forced test trade](#forced-test-trade)
14. [Real money (not yet)](#real-money-not-yet)
15. [Where things are](#where-things-are)

## Before you start

You need:
- the VPS's IP address, user name and password (or key), from your VPS provider;
- your Deriv **App ID** and a **Personal Access Token (PAT)** with the `trade`
  scope (Deriv account settings → API token);
- the Telegram **bot token** and **chat id** you already use for the incubator
  (incubator/README.md, "One-time setup: Telegram").

Check the Ubuntu version once you are logged in:

```
lsb_release -d
```

It should say `Ubuntu 24.04...`. Other versions may work; the setup script warns you.

## Install (once)

1. Log in to the VPS with your SSH app.
2. Run the setup (takes 3-5 minutes; it downloads the code and the recent
   Deriv candles, but not the large Dukascopy history):

   ```
   curl -fsSL https://raw.githubusercontent.com/anollian-mushi/deriv-fx-bot/main/deploy/setup.sh | sudo bash
   ```

   It ends with "Installed v0.x.y" and three NEXT lines.
3. Open the settings file:

   ```
   sudo nano /opt/fxbot/shared/.env
   ```

   Fill in `DERIV_APP_ID`, `DERIV_PAT`, `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`
   after the `=` signs, with no spaces and no quotes. Leave the rest as it is:
   `DERIV_MODE=demo`, `TRADING_ENABLED=true`, `STRATEGY_ID=leader`.
   Save with **Ctrl+O, Enter**, exit with **Ctrl+X**. (In Termius, Ctrl is
   on the extra keyboard row.)
4. Check the settings (nothing is traded):

   ```
   fxbot check
   ```

   You want to see `fingerprint ... OK` and `Mode: demo`. Secrets are only
   shown as `set` or `missing`.
5. Start it:

   ```
   fxbot start
   ```

   Within a minute Telegram says **"Bot started: DEMO mode, candidate ..."**.

The bot now runs all the time. It restarts by itself 30 seconds after a crash
and after the VPS reboots.

## Start, stop, restart

| What | Command |
|---|---|
| Start | `fxbot start` |
| Stop | `fxbot stop` |
| Restart (after changing a setting) | `fxbot restart` |

**Stopping does not close trades.** Open trades stay at Deriv with their stop
loss and take profit. When the bot starts again, it first checks every trade
with Deriv. To close everything, send **/stop** in Telegram instead.

While the bot is stopped, the health check sends one alert after 5 minutes.
That is expected.

## Is it working?

```
fxbot status
```

This shows `active (running)`, the bot balance, open trades, waiting signals,
and the heartbeat age. A heartbeat under 60 seconds means the trading loop is
alive. From Telegram, **/status** shows the same.

## Telegram

The bot answers only your chat id. Messages from anyone else are ignored.

| Command | What it does |
|---|---|
| /status | Running, paused or halted; mode; candidate; balance; heartbeat |
| /balance | Bot balance and equity, today's start, daily loss limit level, kill switch level |
| /open | Open trades with their current profit, stop loss, take profit, closing deadline |
| /pause | No new trades. Open trades are still managed (stops, deadlines) |
| /resume | Allow new trades again after /pause |
| /stop | Close ALL bot trades and halt. Works even if the trading loop is stuck. Stays halted after restarts |
| /report | Last 7 days: trades, profit, win rate, profit factor, skipped signals |
| /export | Sends 3 CSV files: orders, journal events, every quote with its commission rate |

**Messages you get by themselves:**
- **Bot started / Bot stopped**;
- **Trade opened**: pair, direction, stake, stop loss, take profit,
  commission rate, latest closing time;
- **Trade closed**: won or lost, how much, why, new balance;
- **Daily summary** at about 21:35 UTC on weekdays (also lists the day's
  commission rates);
- **Reconnected to Deriv**, **Deriv error / Bot error**, **Daily loss limit
  reached**, **KILL SWITCH**, **HEALTH ALERT**.

## Logs

| What | Command |
|---|---|
| Last 50 lines | `fxbot logs` |
| Last 200 lines | `fxbot logs 200` |
| Live log (stop with Ctrl+C) | `fxbot follow` |
| Warnings and errors only | `fxbot errors` |

Logs are capped and rotated automatically: the system log keeps at most
200 MB, and the bot's own log file keeps 14 days, compressed. The **journal**
(every signal, order, skip, close and quote) is separate and is kept for good.

## Switch the candidate (STRATEGY_ID)

`STRATEGY_ID=leader` means "the candidate at the top of the incubator
leaderboard". The bot picks it each time it starts. Right now no candidate
has forward data yet, so it uses `LEADER_FALLBACK` (`f1_london_breakout_r5`).

To run one specific candidate instead:

```
fxbot set STRATEGY_ID f3_trend_pullback_4h_r5
fxbot check
fxbot restart
```

To go back to following the leader:

```
fxbot set STRATEGY_ID leader
fxbot restart
```

Things to know:
- The candidate's frozen files are checked against their fingerprint at every
  start. If they do not match, the bot refuses to start and tells you in Telegram.
- A trade still open from the previous candidate keeps its stop loss, take
  profit and closing deadline. It is not handed to the new candidate.
- The bot only knows the candidates and leaderboard that were in its release.
  Every Monday at 09:10 UTC it compares itself with the leaderboard on
  GitHub. If the leader changed, you get a Telegram message. To follow the
  new leader: [make a new release](#update-to-a-new-release), then run
  `fxbot update`. With `STRATEGY_ID=leader` it switches by itself at that restart.
- Candidates registered after the release you run are not on the VPS until
  you update.

## Update to a new release

A release is a tagged version of the code on GitHub, such as `v0.1.0`.

**Make a release (phone browser):** open the repository on GitHub →
**Releases** → **Draft a new release** → **Choose a tag** → type a new
number, one higher than the last (e.g. `v0.1.1`) → **Create new tag** →
target **main** → **Publish release**.

**Install it on the VPS:**

```
fxbot update
```

This installs the newest release:
1. downloads it into its own folder, next to the running one;
2. builds its Python environment;
3. runs the full test suite (a few minutes);
4. **only if every test passes**, switches to it and restarts the bot;
5. if the new version shows no heartbeat within 3 minutes, switches back by itself.

If the tests fail, the old version keeps running and Telegram tells you. For a
specific version, use `fxbot update v0.1.0`. To see which version runs:
`fxbot version`.

## Roll back

```
fxbot rollback
```

This goes back to the release that ran before the last update. For an older
installed one, use `fxbot rollback v0.1.0` (`fxbot version` lists them). The
journal, settings and halt state are shared, so nothing is lost.

## Clear a halt (kill switch or /stop)

After the kill switch or /stop, the bot is **halted**. It keeps running and
answers Telegram, but it opens no trades, even after restarts or reboots.
/resume does not clear a halt. This is deliberate: a human has to decide.

1. Find out why: `fxbot status` (the `halted` line), `/report` in Telegram,
   `fxbot logs 200`.
2. If the kill switch fired, the pretend balance is at or below 50 USD.
   Clearing the halt does not reset it, so the next loss would fire the kill
   switch again. To start a fresh 100 USD test with the same candidate, keep
   the old journal and start a new one:

   ```
   fxbot stop
   sudo mv /opt/fxbot/shared/home/journal.sqlite /opt/fxbot/shared/home/journal_old_$(date +%F).sqlite
   ```

3. Clear the halt and restart:

   ```
   fxbot unhalt
   ```

## Copy the journal

The journal is a SQLite file:
`/opt/fxbot/shared/home/journal.sqlite`. It is never committed to git.

**Easiest:** send **/export** in Telegram. You get the last 7 days as CSV
files, which open in any spreadsheet app.

**On the VPS:**
- `fxbot journal` makes a safe copy of the full journal (while the bot runs)
  in your home folder, e.g. `~/journal_20261102_1830.sqlite`.
- `fxbot export 30` writes 30 days as CSV files into `~/fxbot_export_<date>/`.

**Download to the phone:** in Termius, open the host's **SFTP** tab, go to
your home folder and download the file. **To a computer:**
`scp user@VPS-IP:journal_20261102_1830.sqlite .`

For a review, put the CSV files into `reviews/` in the repository.

## Alerts and what to do

| Message | What it means | What to do |
|---|---|---|
| **HEALTH ALERT: ... last heartbeat N minutes ago** | The trading loop is stuck or the bot is stopped | `fxbot status`, then `fxbot logs 100`. Usually `fxbot restart` fixes it. Open trades keep their stops at Deriv. If you stopped it yourself, ignore it. |
| **Health OK again** | The heartbeat is back | Nothing |
| **Reconnected to Deriv** | The connection dropped and the bot logged in again, with a fresh one-time URL, then checked all trades | Nothing, unless it repeats every few minutes |
| **Still cannot reach Deriv** | Deriv or the VPS network is down | Wait. It keeps retrying (every 60 s at most). Check that the VPS has internet: `curl -sI https://api.derivws.com` |
| **Deriv error / Bot error** | Something failed once; the bot carries on | Ignore one. If it repeats, `fxbot errors` |
| **Order refused by Deriv** | Deriv rejected a buy | Nothing was bought. If it says the token is wrong or expired, make a new PAT and put it in `.env` |
| **Daily loss limit reached** | Equity is 10% below today's start | Nothing. New trades resume at 00:00 UTC |
| **KILL SWITCH** | The pretend balance fell to half its start | See [Clear a halt](#clear-a-halt-kill-switch-or-stop). Think before restarting |
| **Bot did NOT start: ...** | Bad settings, tampered candidate, or real-money checks failed | Read the reason, fix `.env` (`fxbot check`), `fxbot restart` |
| **Found an open contract the bot did not open** | Something else is open on the demo account (e.g. the weekend test) | Nothing. The bot counts it toward its 2-trade limit and never closes it |
| **Leader check: the incubator leader is now ...** | A different candidate leads the leaderboard | Optional: [Switch the candidate](#switch-the-candidate-strategy_id) |
| **Update to ... FAILED its tests** | The new release is broken | Nothing. The old one keeps running. Ask for help |

## Forced test trade

To check that orders work without waiting for a signal (demo only):

```
fxbot test-trade --symbol frxEURUSD --direction MULTUP --hold-minutes 10
```

The running bot picks it up within a minute. The trade goes through the same
risk checks and cost gate as a real signal: the entry window 06:00-17:59 UTC,
3% stake, and the limits. It is closed after 10 minutes and marked
`[test trade]` in Telegram.

## Real money (not yet)

The bot refuses real money unless **all** of these hold:
1. `DERIV_MODE=real`;
2. `TRADING_ENABLED=true`;
3. the candidate has **GRADUATED** in the incubator: its record says
   graduated, and a passed exam is in the hash-chained `incubator/exams.json`;
4. `CONFIRM_REAL=yes`.

Even then, the real starting balance must be 50-100 USD, and the real ledger
needs its own journal (a fresh `journal.sqlite`). Do none of this before a
candidate graduates and has had several good weeks on demo (incubator/README.md,
"If something graduates").

## Where things are

| Path on the VPS | What |
|---|---|
| `/opt/fxbot/shared/.env` | Settings and secrets (only root and the bot can read it) |
| `/opt/fxbot/shared/home/journal.sqlite` | The journal: signals, orders, skips, closes, P/L, quotes, Telegram messages |
| `/opt/fxbot/shared/home/status.json` | Latest state, written every minute |
| `/opt/fxbot/shared/home/heartbeat` | Time of the last loop pass (health check) |
| `/opt/fxbot/shared/home/HALT` | Exists only while halted; holds the reason |
| `/opt/fxbot/shared/home/data/` | Candles the bot downloaded itself |
| `/opt/fxbot/shared/home/logs/bot.log` | The bot's log file (rotated daily) |
| `/opt/fxbot/current` | Link to the release that runs |
| `/opt/fxbot/releases/` | Installed releases (the 3 newest are kept) |
| `/etc/systemd/system/fxbot*.service`, `fxbot*.timer` | The service, the 1-minute health check, the weekly leader check |
