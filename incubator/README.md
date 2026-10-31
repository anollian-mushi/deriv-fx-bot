# Strategy incubator: manual for running it alone

The incubator tests trading strategies on new market data, one day at a time,
with pretend money. It runs on GitHub by itself. No AI is needed and nobody
has to touch the repository.

**It never trades.** It has no Deriv login and no code that can place an order,
on a real account or a demo one. The most it ever does is send you a Telegram
message.

## Contents
1. [What it does, in short](#what-it-does-in-short)
2. [One-time setup: Telegram](#one-time-setup-telegram)
3. [What runs when](#what-runs-when)
4. [The candidates](#the-candidates)
4b. [New ideas pre-screened on 31 Oct 2026: none registered](#new-ideas-pre-screened-on-31-oct-2026-none-registered)
5. [Reading the leaderboard](#reading-the-leaderboard)
6. [The graduation rule](#the-graduation-rule)
7. [Alerts: what they mean and what to do](#alerts-what-they-mean-and-what-to-do)
8. [If something graduates](#if-something-graduates)
9. [What could make GitHub stop it](#what-could-make-github-stop-it)
10. [Things you can do without AI](#things-you-can-do-without-ai)
11. [Never do these](#never-do-these)
12. [Where things are](#where-things-are)

## What it does, in short

- A **candidate** is one strategy with fixed settings. It was **registered**
  (frozen) on a given day and can never be changed afterwards.
- Every weekday, after GitHub saves the previous day's Deriv prices, the
  **daily forward test** replays every candidate from the day after its
  registration up to the newest day. Each replay is a simulation that applies
  the same rules a live bot would face:
  - Deriv's commission as measured for each hour of the day, plus slippage;
  - every hard risk limit from CLAUDE.md: 3% stake, 10% daily loss limit,
    50% kill switch, at most 2 trades open, x100/x200 only, the cost gate;
  - the calendar rules: new trades only 06:00-17:59 UTC, nothing 20:55-21:30,
    everything closed by Friday 20:30.
- Each candidate starts with **100 USD of pretend money**.
- The same replay is also run with **1.5x the commission**, to see whether a
  candidate survives higher costs.
- A candidate is only ever scored on days after it was registered. It never
  saw those prices while it was being designed, so this is an honest test.
  The code enforces this.
- If a candidate meets the [graduation rule](#the-graduation-rule), you get a
  Telegram message saying what to do next. Nothing else happens.

"No candidate graduates" is a normal and useful result. All four starting
candidates narrowly failed the earlier research, so expect most or all of
them to fail here too.

## One-time setup: Telegram

You add two **GitHub Secrets**. Secrets are stored encrypted by GitHub, and
nobody can read them back from the repository.

1. In Telegram, open **@BotFather**, send `/newbot` and follow the steps. It
   gives you a **token** that looks like `123456789:AA...`. Keep it private.
2. Send any message (for example "hi") to your new bot.
3. In a browser, open `https://api.telegram.org/bot<TOKEN>/getUpdates`,
   replacing `<TOKEN>` with your token. Find `"chat":{"id":` followed by a
   number. That number is your **chat id**. It can start with a minus sign;
   keep the sign.
4. On GitHub, open the repository, then **Settings → Secrets and variables →
   Actions → New repository secret**, and add:
   - Name `TELEGRAM_BOT_TOKEN`, value: the token.
   - Name `TELEGRAM_CHAT_ID`, value: the chat id.
5. Test it: **Actions → Incubator weekly leaderboard → Run workflow**. Within
   a few minutes you should get the leaderboard in Telegram. If you don't,
   open that run and read the yellow warning: it says what Telegram replied.

No Deriv secrets are needed. The price data is public.

## What runs when

All times are UTC. **GitHub often starts scheduled jobs late, sometimes by
several hours.** That is normal.

| Job (Actions tab name) | When | What it does |
|---|---|---|
| Collect Deriv candles | Tue-Sat 00:15, backup 07:40 | Saves the previous weekday's Deriv prices into `data/`. The backup run only fills in what is missing. |
| Incubator daily forward test | Right after each collection, fallback 10:20 | Checks every candidate's fingerprint, replays all candidates, runs exams, and commits `incubator/records/`. |
| Incubator weekly leaderboard | Monday 07:00 | Sends the leaderboard to Telegram and commits `incubator/leaderboard.md`. |
| Incubator watchdog | Daily 14:10 | Alerts you if one of the jobs above has stopped running. |

There are no runs on Sunday or Monday, because the forex market is shut at
the weekend.

The repository is public, so GitHub Actions minutes are free. The daily job
takes about 2-5 minutes. An exam adds up to 25 minutes a day while it runs.

## The candidates

All four were registered on 2026-10-31 and are scored from 2026-11-01. Each
is frozen exactly as the research left it: the settings it would have used
next, with the model file unchanged.

| Candidate | Idea, in plain words | Candles |
|---|---|---|
| `f1_london_breakout_r5` | Marks the high and low of the quiet early hours. When London opens and the price breaks out of that box, trade in the direction of the break. | 1h |
| `f3_trend_pullback_4h_r5` | In a clear trend, wait for a short dip against it, then trade with the trend. | 4h |
| `f9_eur_gbp_convergence_r5` | When EUR and GBP drift unusually far apart, buy the cheap one and sell the dear one (two trades at once), held up to 8 days. | daily |
| `a1_ml_day_r5` | A machine-learning model, trained only on old data and never retrained, guesses each morning whether a pair rises by evening. It trades only when fairly sure. | 1h |

## New ideas pre-screened on 31 Oct 2026: none registered

On 31 Oct 2026 the owner asked for new candidate ideas, each to pass eight
checks before registration: a written reason for the edge and how it differs
from everything tested before; an expected move per trade of at least 3x the
cost; at least 1.5 expected trades per trading day across the three pairs
(so 100 trades come in about 90 days); executable under every CLAUDE.md rule;
at most 5 settings chosen before testing; a pre-screen on data before
2026-10-31 (the Phase 4 walk-forward extended by one round, out of sample
2023-10-27 to 2026-10-26, 776 trading days) that is profitable before costs
and beats the median of 200 coin-toss runs on the idea's own signals; the
engine's look-ahead test; and no two candidates that are minor variants.

**Result: fifteen ideas were pre-screened and none passes all eight checks,
so no new candidate was registered.** Thirteen more were rejected on
reasoning alone (too rare to reach 1.5 trades a day, outside the entry
window, or a minor variant of something already tested); they are listed in
`research/log.md`. N stays at 4 for the graduation rule. "No new candidate"
is a normal result under these rules, and the one near miss is below.

How to read the table: *gross* is the profit before any cost (the cost added
back), in USD from a 100 USD start over the 36 months, with the average pips
a trade in brackets; *net* is after Deriv's measured commission and slippage,
and at 1.5x the commission; *coin toss* is the share of 200 random-direction
replays of the same signals the idea beat (not run when the gross result was
already negative, or when the idea fails the frequency check so the answer
could not change the verdict). Files: `research/incubator_prescreen/<idea>/`.

| Idea (strategy) | What it does, in plain words | Trades (per day) | Gross (pips/trade) | Net / at 1.5x | Coin toss | Why it fails |
|---|---|---|---|---|---|---|
| fix_reversal (i1) | Fade the hour before the 16:00 London fix, hold 2-4 h | 670 (0.86) | -11 (-1.4) | -57 / -78 | not run | loses before costs; too few trades; kill switch once |
| turtle_soup (i2) | Fade a failed sweep of yesterday's high or low | 327 (0.42) | +0.2 (-0.1) | -28 / -35 | 52% | a coin toss; too few trades |
| round_bounce (i3) | Fade a rejection at a 00 round number | 1,593 (2.05) | -36 (-1.0) | -142 / -185 | not run | loses before costs; kill switch twice |
| round_break (i4) | Follow a close through a 00 round number | 1,088 (1.40) | -29 (-1.2) | -108 / -140 | not run | loses before costs; kill switch twice |
| asia_fade (i5) | Fade the overnight move at the London open | 277 (0.36) | -19 (-3.0) | -37 / -44 | not run | loses before costs (the overnight move continues); too few trades |
| us_data_drift (i6) | Follow the 12:00-14:00 (US data) move to 20:00 | 425 (0.55) | -22 (-3.1) | -48 / -61 | not run | loses before costs (the data move partly reverses); too few trades |
| ny_into_asia (i7) | Follow the New York session's move overnight | 471 (0.61) | -5 (-0.3) | -37 / -47 | not run | a coin toss; too few trades |
| london_reversal (i8) | Fade the London session's move at 14:00 | 457 (0.59) | +3 (+0.5) | -29 / -39 | 70% | too few trades; the edge is well below the cost |
| range_exhaustion (i9) | Fade a day that has used its whole normal range | 271 (0.35) | -9 (-1.5) | -28 / -35 | not run | loses before costs; too few trades |
| trend_intraday (i10) | Trade the 5-10 day trend during the day session only | 1,227 (1.58) | -54 (-2.3) | -134 / -164 | not run | loses before costs; kill switch twice |
| ny_cut_breakout (i11) | Trade the first break out of the range pinned before the 10:00 New York option cut, to 20:00 | 1,109 (1.43) | +15 (+1.0) | -54 / -85 | 94% | the direction carries real information, but about 1 pip a trade against 4 of cost; 1.43 trades a day; kill switch once |
| twap_pullback (i12) | Buy a pullback to the day's average price on an up day (mirror for down) | 357 (0.46) | -13 (-2.2) | -40 / -47 | not run | loses before costs; too few trades |
| morning_overnight (i13) | A strong move by 08:00 (at least 0.4 of a normal day's range), followed and held to 06:00 the next day | 297 (0.38) | +45 (+7.2) | +17 / +4 | 100% | **passes every check except trades per day**: at 0.38 a day it would need about a year, not 90 days, to reach 100 trades (see below) |
| ny_cut_overnight (i14) | Idea 11 held to 06:00 the next day | 871 (1.12) | +20 (+1.1) | -44 / -68 | see log | the information is spent by 20:00: the longer hold adds nothing; loses after costs |
| knn_path (a2) | A nearest-neighbour model that matches the last 24 hours' shape to past days and votes on the direction to 20:00 | 443 (0.57) | +1 (+0.3) | -33 / -43 | not run | about zero before costs; every setting loses after costs; too few trades |

**What the round taught.** At the 1-hour-to-1-day scale these pairs show mild
*continuation*, not reversal: every fading idea (fix, round numbers, Asia,
London session, range exhaustion, pullbacks) lost before costs, and the ideas
that follow a move (NY cut break, morning move) are the ones with real
directional information. The information is small (about 1 pip a trade) on
the frequent signals and large (about 7 pips) only on rare, big-move days.
That is the conflict with the 1.5-trades-a-day rule: the signals that are
frequent enough are worth less than the 4 pips of cost, and the one signal
worth more than the cost fires about twice a week.

**A decision for the owner (nothing was registered).** `i13_morning_overnight`
(settings: decision hour 08:00, move at least 0.4 of the 20-day average daily
range, no stop, exit 06:00 the next day, no Friday signals) is the only idea
of the whole project so far that is profitable after costs out of sample
(+17 USD at the measured commission, +4 USD at 1.5x, 297 trades, no kill
switch, profit before costs in 5 of 6 half-years, beat all 200 coin-toss
runs; per pair EUR/USD +12, GBP/USD -8, USD/JPY +13). Its weaknesses: only
0.38 trades a day, so the 100-trade bar would take about a year; the gain
leans on USD/JPY; the neighbouring threshold (0.25 of a day's range) lost
money, so the edge sits on rare, large moves only. Registering it would be a
deliberate exception to the frequency check and would raise N to 5 for every
candidate. The code is committed (`src/fxbot/strategies/families.py`,
class `MorningOvernight`), so it can be registered in one command if you
decide so:

```
python scripts/incubator.py register --id i13_morning_overnight_v1 --module families \
    --class MorningOvernight --params '{"decision_hour": 8, "k": 0.4, "stop": 0.0}' \
    --notes "pre-screen 31 Oct 2026: passes all checks except 1.5 trades/day (0.38)"
```

**Running the pre-screen on a new idea** (for a developer or an AI): add the
strategy class to `src/fxbot/strategies/families.py`, declare its grid (at
most 8 variants, 5 settings) in `fxbot.backtest.prescreen.IDEAS`, then
`python scripts/prescreen.py all --idea <name>` (resumable, about 15 minutes
of compute). It writes `research/incubator_prescreen/<name>/` and the rows in
`research/log.md`. The data layer refuses anything dated 2026-10-31 or later.

## Reading the leaderboard

Candidates are sorted by status (graduated first, then active, waiting, dead),
then by net profit. In Telegram each candidate takes a few lines:

```
1. f9_eur_gbp_convergence_r5 [ACTIVE]
   45d  18 trades  open 2
   Net +3.10  Net1.5x +1.95  DD 6.2%
   Win 56%  PF 1.21  AvgW 1.80  AvgL -1.75
   EURUSD +2.40  GBPUSD +0.70  USDJPY +0.00
   still needs: days 45/90, trades 18/100
   exam: not started
```

| Column | Meaning |
|---|---|
| **Status** | `WAITING`: no data after its registration yet. `ACTIVE`: being scored. `DEAD`: its kill switch fired; it stays listed but can never graduate. `GRADUATED`: passed the rule. `TAMPERED`: its frozen files changed; see [Alerts](#alerts-what-they-mean-and-what-to-do). |
| **d / Days** | Calendar days of scoring so far. 90 are needed. |
| **trades** | Trades that have opened and closed. 100 are needed. |
| **open** | Trades still open at the end of the newest day. Their current profit or loss is included in Net. |
| **Net** | Profit or loss in USD from the 100 USD start, after Deriv's measured commission and slippage. +3.10 means the pretend account holds 103.10 USD. |
| **Net1.5x** | The same replay with commission 1.5 times higher. It must also be above zero. |
| **DD** (max drawdown) | The biggest drop from a high point, in %. A fall from 110 to 88 USD is 20%. It must stay under 25%. |
| **Win** | Share of closed trades that made money. A strategy can win less than half the time and still profit, if its wins are bigger than its losses. |
| **PF** (profit factor) | Money won divided by money lost. Above 1.0 means profitable overall; 1.2 means 1.20 USD won for every 1 USD lost. |
| **AvgW / AvgL** | Average winning and average losing trade, in USD. |
| **EURUSD / GBPUSD / USDJPY** | Net result per pair. This shows whether the profit comes from one pair only. |
| **still needs** | Which of graduation rules 1-3 are not met yet. "rules 1-3 met" means the exam can start. |
| **exam** | `not started`; `running 800/2000` (random runs done so far); `failed` or `PASSED`, with the share of random runs it beat. |

`incubator/leaderboard.md` on GitHub has the same numbers as one table, with
the trade count per pair in brackets.

## The graduation rule

This rule is fixed in CLAUDE.md and must never be loosened. All of these
must hold on forward data (days after registration):

1. **At least 90 days and at least 100 closed trades.** Fewer would be too
   little evidence.
2. **Net profit above zero at the measured commission AND at 1.5x it.** It
   must survive costs being higher than measured.
3. **Max drawdown under 25%, and the kill switch never fired.**
4. **It beats luck.** The exam replays the candidate many times on exactly
   the same days and pairs where it took trades, but each time it picks Up
   or Down with a coin toss. Everything else stays the same: stops, exits,
   costs and limits. For `f9`, the two trades of a pair stay opposite to
   each other. The candidate's real net profit must beat almost all of
   these coin-toss runs:
   - It must beat the **(1 - 0.05/N)** share of them. **N** counts every
     candidate ever registered plus every exam attempt ever started,
     including the current one. With 4 candidates the first exam has N = 5,
     so the candidate must beat 99% of the coin-toss runs.
   - N only ever grows. Every new candidate and every retake makes the bar
     a little higher. The more ideas you test, the more likely one passes
     by pure luck, and the growing bar corrects for that.
   - Number of coin-toss runs: at least 2,000, or 20 × N / 0.05 if that is
     more (2,400 at N = 6). That leaves at least 20 runs above the bar, so
     the bar itself is measured reliably.

**How an exam runs:** it starts automatically on the first daily run where
rules 1-3 hold. The data end on that day is frozen as the exam's **cutoff**.
The coin-toss runs can take several days; each daily run continues where the
last one stopped, and you get a Telegram message when the exam starts and
when it ends. If it fails, the candidate keeps running, and a **retake** is
allowed once the data reaches at least 28 days past the previous cutoff
(and rules 1-3 still hold then). Every attempt adds 1 to N.

The "profitable on 2 of the 3 pairs" rule from the research phase is **not**
part of graduation, but the graduation message lists the results per pair so
you can judge that yourself.

## Alerts: what they mean and what to do

| Telegram message | What it means | What to do |
|---|---|---|
| **ALERT: the daily Deriv collector failed** | GitHub could not download yesterday's prices (Deriv down, network trouble, or a change on Deriv's side). | Nothing at first: it retries at the next run and fills in the missed days. If it repeats for 3+ days, open **Actions → Collect Deriv candles**, open the red run and read the red lines. If Deriv changed its API, a developer or AI has to update `src/fxbot/data/collector.py`. |
| **ALERT: the daily forward test failed** | The replay or one of its checks broke. | Open **Actions → Incubator daily forward test → the red run**. Read the step with the red cross. A failing "Incubator tests" step means files were changed by hand (see TAMPERED below). One failure followed by a success the next day can be ignored. |
| **STALE: ... has not succeeded for 2 or more scheduled days** | A daily job has stopped running at all. | Open **Actions** and look for a yellow banner such as "This scheduled workflow is disabled". If it is there, open that workflow and click **Enable workflow**. Otherwise run it by hand (**Run workflow**) and see whether it fails. |
| **STALE: the weekly leaderboard ...** | The Monday job has not run for more than 8 days. | Same as above, for **Incubator weekly leaderboard**. |
| **Incubator daily run found problems: TAMPERED ...** | A frozen candidate's files no longer match their fingerprint. Someone edited them. | That candidate is skipped until its files are restored. Restore them to how they were with `git checkout <commit-before-the-edit> -- incubator/candidates/<id>` (or ask someone to). Never "fix" the fingerprint: a changed idea must be registered as a new candidate. |
| **Exam started: ...** | A candidate met rules 1-3. | Nothing. Wait for the result (usually 1-3 days). |
| **Exam not passed: ...** | It did not beat the coin-toss runs clearly enough. | Nothing. It keeps running; a retake can happen automatically later. |
| **Kill switch fired (paper): ...** | That candidate lost half its pretend money. | Nothing. It is out for good. |
| **GRADUATED: ...** | See [If something graduates](#if-something-graduates). | |
| **ALERT: the incubator watchdog itself failed** | The checker broke, so a stopped job might go unnoticed. | Open **Actions → Incubator watchdog** and look. |

**No Monday leaderboard at all?** Then GitHub Actions may be switched off
entirely, and in that case even the watchdog cannot warn you. Open the
repository's **Actions** tab and check.

## If something graduates

Graduation means "this is worth a closer look". **It is not proof that the
strategy makes money, and it is not a signal to trade.**

1. **Do not put real money on it.** Nothing has been traded and nothing will
   be traded automatically.
2. Look at its record in `incubator/records/<id>/`:
   - `trades.csv`: every simulated trade;
   - `summary.json`: all the numbers;
   - `exam.json`: the exam and every coin-toss result.
3. Be extra sceptical if:
   - most of the profit came from one pair or from a handful of big trades;
   - the profit came mostly in the first weeks and has been flat since;
   - the net profit at 1.5x commission is barely above zero.
4. With help (a developer or an AI assistant), plan the next step from the
   project plan: a **demo-account** test of exactly this frozen candidate,
   with the live bot's risk module, for at least several weeks.
5. Real money comes only after a good demo period, within the CLAUDE.md
   limits (50-100 USD start, 3% per trade), and only when you set
   `DERIV_MODE=real` yourself.

A graduated candidate keeps being replayed and stays on the leaderboard, so
you can keep watching it.

## What could make GitHub stop it

- **60 days with no activity.** On public repositories, GitHub pauses
  scheduled jobs after 60 days without any repository activity. The daily
  data commits and the weekly leaderboard commit count as activity, so this
  should never happen. If it does, the Actions tab shows a banner with an
  **Enable** button.
- **GitHub having a busy moment.** Scheduled jobs can start hours late or
  occasionally be skipped. The backup schedules and the watchdog cover this.
- **Your account.** If your GitHub account is suspended or the repository is
  archived or deleted, everything stops, and no alert can reach you. The
  missing Monday leaderboard is your sign.
- **Deriv changing or blocking its data feed.** The collector alerts you.
  The incubator then has no new days to score until it is fixed.
- **Telegram.** If you delete the bot or revoke its token, messages stop.
  The runs still show red or yellow on the Actions tab.
- **Slow ageing.** GitHub retires old runner systems and action versions
  every few years. These workflows use current versions (ubuntu-24.04,
  checkout v5, setup-python v6), which should last well beyond a year. If a
  job starts failing with a message about a deprecated or retired version,
  a developer or AI has to bump the version numbers in
  `.github/workflows/`.
- **Size.** The data grows about 15 MB a year. That is far below GitHub's
  limits.

## Things you can do without AI

All of this works from a phone browser or the GitHub app.

- **Run any job now:** Actions → pick the job → **Run workflow** → Run.
- **Read the latest numbers:** open `incubator/leaderboard.md`, or
  `incubator/records/index.json`.
- **Pause everything:** Actions → each "Incubator ..." workflow → "..." menu
  → **Disable workflow**. Enable it again the same way. Nothing is lost:
  the next run catches up on all missed days.
- **Register a new candidate** (needs a computer with Python 3.12 and this
  repository; the strategy class must already exist in
  `src/fxbot/strategies/families.py` or `ml_day.py`, committed):

  ```
  pip install -r requirements.txt
  python scripts/incubator.py register --id my_idea_v1 --module families \
      --class TrendPullback --params '{"trend_len": 30, "pullback": 20, "sl_atr": 2.0, "tp_r": 2.0}' \
      --notes "what this is and why"
  python -m pytest -q tests/test_incubator_registry.py
  git add incubator/ && git commit -m "Register my_idea_v1" && git push
  ```

  The registration date is always today. Scoring starts tomorrow. Every new
  candidate raises the luck bar for all exams (N grows by 1), so register
  only ideas you really believe in, and never re-register a candidate that
  failed with slightly different settings hoping it passes.
- **Check that nothing was changed:** `python scripts/incubator.py verify`.

## Never do these

- Edit, rename or delete anything in `incubator/candidates/`,
  `incubator/registry.json` or `incubator/exams.json`. These files are
  fingerprinted and hash-chained, and any edit is detected and flagged.
- Change the graduation rule or the risk limits to help a candidate pass.
- Change `research/phase2/cost_by_hour.json` without a real new measurement.
  The incubator uses that file for commission. If it ever changes (for
  example after the planned clock-change re-check), every candidate is
  re-scored with the new rates, and the "Engine fingerprint" line in
  `leaderboard.md` changes.
- Add trading code or Deriv secrets to the incubator. It is paper only by
  design.

## Where things are

| Path | What |
|---|---|
| `incubator/registry.json` | One entry per registered candidate: id, date, fingerprint, chained to the previous entry. |
| `incubator/candidates/<id>/` | The frozen candidate: `code/` (its strategy code), `models/` (model files), `manifest.json` (settings, commit, date, SHA-256 of every file). |
| `incubator/records/<id>/` | Its forward record: `summary.json`, `trades.csv`, `equity.csv` (end-of-day pretend balance), `signals.json`, `state.json`, and exam files. |
| `incubator/records/index.json` | The numbers behind the leaderboard. |
| `incubator/exams.json` | Every exam start and result, hash-chained. This is where N comes from. |
| `incubator/leaderboard.md` | The latest weekly leaderboard. |
| `src/fxbot/incubator/` | The code: `registry.py`, `forward.py`, `exam.py`, `daily.py`, `leaderboard.py`, `watchdog.py`, `notify.py`. |
| `scripts/incubator.py` | The command line used by the jobs. |
| `.github/workflows/incubator-*.yml` | The three incubator jobs. |
