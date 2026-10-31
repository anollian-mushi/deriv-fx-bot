"""Telegram commands for the live bot, answered from their own thread.

Only messages from TELEGRAM_CHAT_ID are accepted; anything else is ignored
and journalled. The thread reads the journal and BOT_HOME/status.json (written
by the trading loop every minute), so /status, /open and /stop keep working
even if the trading loop is stuck. /stop closes trades on its own Deriv
connection (fxbot.live.stop).

Commands: /status /balance /open /pause /resume /stop /report /export /help
"""

from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)
PAIR = {"frxEURUSD": "EUR/USD", "frxGBPUSD": "GBP/USD", "frxUSDJPY": "USD/JPY"}

HELP = """Commands:
/status  - running, paused or halted; mode; candidate; balance
/balance - bot balance, equity, daily limit and kill switch levels
/open    - open trades with their current profit
/pause   - no new trades (open trades are still managed)
/resume  - allow new trades again after /pause
/stop    - close ALL bot trades and halt (stays halted after restarts)
/report  - last 7 days: trades, profit, win rate, skips
/export  - last 7 days of the journal as CSV files"""


def _utc(ts: float | None) -> str:
    return time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ts)) if ts else "-"


class Commander(threading.Thread):
    def __init__(self, client, journal, home: Path, stop_fn, notifier=None, clock=time.time, poll_timeout: int = 25):
        super().__init__(name="telegram-commands", daemon=True)
        self.client, self.journal, self.home = client, journal, Path(home)
        self.stop_fn, self.notify, self.clock, self.poll_timeout = stop_fn, notifier, clock, poll_timeout
        self.started = clock()
        self.running = True

    # ------------------------------------------------------------------ loop
    def run(self) -> None:
        while self.running:
            try:
                self.poll_once()
            except Exception as err:
                log.warning("Telegram polling failed: %s", err)
                time.sleep(10)

    def poll_once(self) -> None:
        offset = self.journal.get("tg_offset")
        for u in self.client.updates(offset, self.poll_timeout):
            self.journal.set("tg_offset", int(u["update_id"]) + 1)
            msg = u.get("message") or {}
            chat = str((msg.get("chat") or {}).get("id", ""))
            text = (msg.get("text") or "").strip()
            if chat != str(self.client.chat_id):
                self.journal.event("command_ignored", chat=chat, text=text[:50])
                continue
            if msg.get("date", 0) < self.started - 120:
                self.journal.event("command_stale", text=text[:50])   # sent before this start: never replayed
                continue
            self.handle(text)

    def reply(self, text: str) -> None:
        self.journal.event("telegram", category="reply", text=text)
        try:
            self.client.send(text)
        except Exception as err:
            self.journal.event("telegram_failed", category="reply", error=str(err))

    def handle(self, text: str) -> None:
        cmd = text.split()[0].split("@")[0].lower() if text else ""
        self.journal.event("command", text=cmd)
        fn = {"/status": self.status, "/balance": self.balance, "/open": self.open, "/pause": self.pause,
              "/resume": self.resume, "/stop": self.stop, "/report": self.report, "/export": self.export,
              "/help": lambda: HELP, "/start": lambda: HELP}.get(cmd)
        if fn is None:
            self.reply("Unknown command.\n" + HELP)
            return
        try:
            out = fn()
        except Exception as err:
            out = f"{cmd} failed: {type(err).__name__}: {err}"
        if out:
            self.reply(out)

    # ------------------------------------------------------------------ helpers
    def state(self) -> dict:
        p = self.home / "status.json"
        return json.loads(p.read_text()) if p.exists() else {}

    def heartbeat_age(self) -> float | None:
        p = self.home / "heartbeat"
        try:
            return self.clock() - int(p.read_text().strip())
        except (OSError, ValueError):
            return None

    def halted(self) -> str | None:
        p = self.home / "HALT"
        return p.read_text().strip() if p.exists() else None

    # ------------------------------------------------------------------ commands
    def status(self) -> str:
        st = self.state()
        age = self.heartbeat_age()
        state = "HALTED: " + self.halted() if self.halted() else ("PAUSED" if self.journal.get("paused") else "running")
        loop = "ok" if age is not None and age < 120 else f"NO HEARTBEAT for {age:.0f} s" if age else "no heartbeat yet"
        return "\n".join([
            f"Bot: {state}",
            f"Mode: {st.get('mode', '?')}  candidate: {st.get('candidate', '?')}",
            f"Trading loop: {loop}; Deriv connection: {'up' if st.get('connected') else 'DOWN'}; "
            f"candles: {'ok' if st.get('feed_ok', True) else 'feed error'}",
            f"Bot balance {self.journal.balance():.2f} USD, equity {st.get('equity', 0):.2f} USD",
            f"Open trades: {len(st.get('open', []))} bot, {len(st.get('foreign', {}))} other; "
            f"waiting signals: {len(st.get('pending', {}))}",
            f"Last update: {st.get('utc', '-')}" + (f"\nLast error: {st['last_error']}" if st.get("last_error") else ""),
        ])

    def balance(self) -> str:
        st = self.state()
        start = float(st.get("start_balance") or self.journal.start_balance)
        day = st.get("day_start") or {}
        ds = float(day.get("balance", self.journal.balance()))
        return "\n".join([
            f"Bot balance (pretend ledger): {self.journal.balance():.2f} USD (started at {start:.2f})",
            f"Equity incl. open trades: {st.get('equity', self.journal.balance()):.2f} USD",
            f"Today started at {ds:.2f}; daily loss limit at {0.9 * ds:.2f} USD",
            f"Kill switch at {0.5 * start:.2f} USD",
            f"Deriv account balance ({st.get('mode', '?')}): {st.get('deriv_balance')}",
        ])

    def open(self) -> str:
        st = self.state()
        rows = st.get("open", [])
        if not rows and not st.get("foreign"):
            return "No open trades."
        out = []
        for r in rows:
            p = r.get("profit")
            out.append(f"{PAIR.get(r['symbol'], r['symbol'])} {'Up' if r['direction'] == 'MULTUP' else 'Down'} "
                       f"x{r['multiplier']} stake {r['stake']:.2f}: {('%+.2f' % p) if p is not None else '?'} USD, "
                       f"SL {r.get('sl')} TP {r.get('tp')}, opened {r.get('opened')}, closes by {r.get('deadline')}"
                       + (" [test]" if r.get("test") else ""))
        for cid, f in (st.get("foreign") or {}).items():
            out.append(f"Not the bot's: contract {cid} {PAIR.get(f['symbol'], f['symbol'])} {f.get('contract_type')}")
        return "\n".join(out)

    def pause(self) -> str:
        self.journal.set("paused", True)
        self.journal.event("pause")
        return "Paused: no new trades. Open trades keep their stops and deadlines. /resume to undo."

    def resume(self) -> str:
        if self.halted():
            return ("The bot is HALTED (" + self.halted() + "). /resume does not clear a halt; that needs a manual "
                    "restart on the VPS (deploy/DEPLOY.md, 'Clear a halt').")
        self.journal.set("paused", False)
        self.journal.event("resume")
        return "Resumed: new trades allowed again."

    def stop(self) -> str:
        self.reply("Stopping: halting and closing all bot trades on a separate connection...")
        return self.stop_fn()

    def report(self) -> str:
        since = self.clock() - 7 * 86400
        closed = [o for o in self.journal.orders(("closed",)) if (o["closed"] or 0) >= since]
        wins = [o["profit"] for o in closed if o["profit"] > 0]
        losses = [o["profit"] for o in closed if o["profit"] <= 0]
        skips: dict[str, int] = {}
        for e in self.journal.events(since, ("skip",)):
            r = e["detail"].get("reason", "?")
            skips[r] = skips.get(r, 0) + 1
        pf = f"{sum(wins) / -sum(losses):.2f}" if losses and sum(losses) < 0 else "-"
        per = {}
        for o in closed:
            per[o["symbol"]] = round(per.get(o["symbol"], 0) + o["profit"], 2)
        quotes = self.journal.quotes(since)
        return "\n".join([
            f"Last 7 days ({_utc(since)} to now)",
            f"Closed trades: {len(closed)}, net {sum(o['profit'] for o in closed):+.2f} USD",
            f"Win rate: {len(wins) / len(closed) * 100:.0f}%" if closed else "Win rate: -",
            f"Avg win {sum(wins) / len(wins):+.2f}, avg loss {sum(losses) / len(losses):+.2f}, profit factor {pf}"
            if wins and losses else f"Profit factor {pf}",
            "Per pair: " + (", ".join(f"{PAIR.get(k, k)} {v:+.2f}" for k, v in sorted(per.items())) or "-"),
            "Skipped signals: " + (", ".join(f"{k} {v}" for k, v in sorted(skips.items())) or "none"),
            f"Quotes journalled: {len(quotes)}; bot balance now {self.journal.balance():.2f} USD",
        ])

    def export(self) -> str:
        since = self.clock() - 7 * 86400
        stamp = time.strftime("%Y%m%d", time.gmtime(self.clock()))
        self.client.send_document(f"orders_{stamp}.csv", self.journal.orders_csv(since).encode(),
                                  "Orders, last 7 days")
        self.client.send_document(f"events_{stamp}.csv", self.journal.events_csv(since).encode(),
                                  "Journal events, last 7 days")
        q = self.journal.quotes(since)
        lines = ["utc,symbol,contract_type,multiplier,stake,commission,size,rate_pct,spot,purpose"]
        lines += [f"{_utc(x['ts'])},{x['symbol']},{x['contract_type']},{x['multiplier']},{x['stake']},"
                  f"{x['commission']},{x['size']},{(x['rate'] or 0) * 100:.6f},{x['spot']},{x['purpose']}" for x in q]
        self.client.send_document(f"quotes_{stamp}.csv", ("\n".join(lines) + "\n").encode(),
                                  "Every quote with its commission rate, last 7 days")
        return "Sent 3 CSV files: orders, events, quotes (last 7 days)."
