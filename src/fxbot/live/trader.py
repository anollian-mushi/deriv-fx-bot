"""The live trading loop: one incubator candidate, demo by default.

It follows the backtest engine (fxbot.backtest.engine) step by step, so a
candidate behaves live as it does in its incubator record:

Once a minute (a few seconds after the minute closes):
1. Fetch the newest closed 1m candles (BOT_HOME/data, data/, Deriv).
2. A new UTC day sets the start-of-day balance (daily loss limit).
3. Check every open contract with Deriv; record the ones Deriv closed
   (take profit, stop loss, stop out).
4. Equity = ledger balance + open profit. Kill switch at <= 50% of the
   starting balance: close everything, write HALT, alert, stop trading
   until a manual restart (scripts/live.py unhalt).
5. Close trades whose deadline passed (20:30 before a weekend / closed day,
   20:50 for x200) and trades the strategy asked to exit.
6. While the market is open: hand each newly closed strategy candle to the
   strategy (pairs in the rotating order the backtester uses), then try every
   waiting signal: risk precheck, probe quote (exact commission rate),
   RiskManager.check_entry, order quote, cost gate on that quote, buy.
   A signal that cannot fill now waits, at most the fixed wait for its
   timeframe (1h: 1 hour, 4h: 4 hours, daily: 12 hours), like the backtester.

The ledger is the bot's own pretend account (demo: BOT_START_BALANCE, 100 USD
by default) = start + every closed trade's profit. Stakes, the daily loss
limit and the kill switch use it, not the demo account's 10,000 USD.

No duplicate orders: an order is journalled as "sending" before the buy.
If the reply is lost, the order becomes "unknown", the bot reconnects, and
reconciliation reads Deriv's statement and portfolio to settle it before any
other order is sent. The signal that caused it is dropped, never resent.

Contracts on the account that the journal does not know (e.g. the weekend
test) are "foreign": reported once, counted toward the 2-position limit and
the one-per-pair rule, and never closed by the bot.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import math
import time
import traceback
from dataclasses import dataclass
from pathlib import Path

from fxbot import sessions
from fxbot.backtest.fills import PIP, PIP_SIZE, SL_MIN_ABOVE_COMMISSION, CommissionTable
from fxbot.contracts import multiplier as mc
from fxbot.deriv.api import DerivError
from fxbot.live.broker import BrokerDisconnected, parse_shortcode
from fxbot.risk.limits import AccountState, OrderRequest, RiskLimits, RiskManager
from fxbot.risk.live import PROBE_STAKE, LiveRisk, TicketError
from fxbot.strategies.base import CancelPending, Enter, ExitPosition, PositionView, max_wait_seconds

log = logging.getLogger(__name__)
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PAIR = {"frxEURUSD": "EUR/USD", "frxGBPUSD": "GBP/USD", "frxUSDJPY": "USD/JPY"}
TICK_SECOND = 3                 # run each minute's work this many seconds after the minute closes
SUMMARY_AT = 21 * 3600 + 35 * 60
SAMPLE_MINUTE = 5               # hourly cost sample at hh:05
RECONNECT_ALERT_GAP = 600       # at most one reconnect alert per 10 minutes (each reconnect is journalled)
WAIT_REASONS_LIVE = {"paused"}


@dataclass
class Pending:
    request: OrderRequest
    signal_epoch: int
    expires: int
    first_block: str = ""
    test: dict | None = None


def iso(epoch: float) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def pips_text(symbol: str, price_move: float) -> str:
    return f"{price_move / PIP[symbol]:.1f} pips"


class Trader:
    def __init__(self, *, candidate_id: str, strategy, broker, store, journal, notifier, home: Path,
                 mode: str, start_balance: float, cost_sampling: bool = True, clock=time.time,
                 symbols=SYMBOLS, table: CommissionTable | None = None, sleep=asyncio.sleep,
                 halt_path: Path | None = None):
        if mode not in ("dry", "demo", "real"):
            raise ValueError("mode must be dry, demo or real")
        self.cid, self.strategy, self.broker, self.store = candidate_id, strategy, broker, store
        self.journal, self.notify, self.home, self.mode = journal, notifier, Path(home), mode
        self.clock, self.symbols, self.sleep = clock, list(symbols), sleep
        self.cost_sampling = cost_sampling
        self.halt_path = halt_path or self.home / "HALT"
        self.requests_dir = self.home / "requests"
        self.table = table or CommissionTable()
        self.limits = RiskLimits(starting_balance=start_balance)
        self.manager = RiskManager(self.limits, self.table.base)
        self.risk = LiveRisk(self.manager, self._blocked, clock)
        self.max_wait = max_wait_seconds(strategy)
        self.pending: dict[str, Pending] = {}
        self.exit_requests: set[str] = set()
        self.foreign: dict[int, dict] = {}
        self.poc: dict[int, dict] = {}           # contract_id -> latest proposal_open_contract
        self.last_end: dict[str, int] = journal.get("last_end", {}) or {}
        self.last_minute = 0
        self.last_error = ""
        self.deriv_balance: float | None = None
        self.stopping = False
        self._last_reconnect_alert = 0.0
        self._reconnects_unreported = 0
        self.feed_ok = True

    # ================================================================== state
    def halted(self) -> str | None:
        if self.halt_path.exists():
            return self.halt_path.read_text().strip() or "halted"
        return None

    def paused(self) -> bool:
        return bool(self.journal.get("paused", False))

    def _blocked(self) -> str | None:
        if self.halted():
            return "halted"
        if self.paused():
            return "paused"
        return None

    def write_halt(self, reason: str) -> None:
        self.halt_path.parent.mkdir(parents=True, exist_ok=True)
        self.halt_path.write_text(f"{reason} ({iso(self.clock())})\n")

    def balance(self) -> float:
        return self.journal.balance()

    def open_profit(self) -> float:
        total = 0.0
        for o in self.journal.open_orders():
            p = self.poc.get(o["contract_id"]) or {}
            if p.get("profit") is not None:
                total += float(p["profit"])
        return round(total, 2)

    def equity(self) -> float:
        return round(self.balance() + self.open_profit(), 2)

    def day_start_balance(self, now: float) -> float:
        day = sessions.utc_date(int(now)).isoformat()
        rec = self.journal.get("day_start") or {}
        if rec.get("day") != day:
            rec = {"day": day, "balance": self.balance()}
            self.journal.set("day_start", rec)
            self.journal.event("new_day", balance=rec["balance"])
        return float(rec["balance"])

    def account(self, now: float) -> AccountState:
        syms = [o["symbol"] for o in self.journal.open_orders()]
        syms += [f["symbol"] for f in self.foreign.values()]
        return AccountState(self.balance(), self.equity(), self.day_start_balance(now),
                            self.limits.starting_balance, syms, bool(self.journal.get("killed", False)))

    # ================================================================== connection
    async def connect(self) -> None:
        """Connect with backoff (1, 2, 4 ... 60 s), each time with a fresh OTP URL, then reconcile."""
        delay, attempt = 1.0, 0
        down_since = self.clock()
        while not self.stopping:
            attempt += 1
            try:
                await self.broker.connect()
                bal = await self.broker.balance()
                self.deriv_balance = float(bal.get("balance", 0))
                await self.reconcile()
                if self.broker.connects > 1:
                    self._reconnected(attempt, self.clock() - down_since)
                return
            except DerivError as err:
                if err.code in ("NotDemo", "WrongAccount", "WrongGateway", "NotReal", "NoDemoAccount",
                                "NoRealAccount", "MissingSettings", "AccountNotFound"):
                    raise
                self._connect_failed(attempt, err)
            except Exception as err:          # network, REST down, timeouts
                self._connect_failed(attempt, err)
            self.heartbeat(self.clock())
            await self.sleep(delay)
            delay = min(delay * 2, 60.0)

    def _connect_failed(self, attempt: int, err: Exception) -> None:
        self.last_error = f"connect: {type(err).__name__}: {err}"
        self.journal.event("connect_failed", attempt=attempt, error=f"{type(err).__name__}: {err}")
        if attempt in (3, 10) or attempt % 30 == 0:
            self.notify.send(f"Still cannot reach Deriv (attempt {attempt}): {type(err).__name__}. "
                             "Retrying with backoff; open trades keep their stop loss and take profit at Deriv.",
                             "error")

    def _reconnected(self, attempts: int, seconds: float) -> None:
        self.journal.event("reconnect", attempts=attempts, seconds=round(seconds, 1))
        self._reconnects_unreported += 1
        now = self.clock()
        if now - self._last_reconnect_alert >= RECONNECT_ALERT_GAP:
            n = self._reconnects_unreported
            self.notify.send(f"Reconnected to Deriv after {seconds:.0f} s ({attempts} attempt(s), fresh login). "
                             f"Open trades were checked against Deriv." + (f" {n} reconnects since the last alert."
                                                                             if n > 1 else ""), "reconnect")
            self._last_reconnect_alert, self._reconnects_unreported = now, 0

    # ================================================================== reconciliation
    async def reconcile(self) -> dict:
        """Match the journal with Deriv. Runs on startup and after every reconnect, before anything else."""
        contracts = await self.broker.portfolio()
        live = {int(c["contract_id"]): c for c in contracts if c.get("contract_id")}
        report = {"adopted": [], "failed": [], "closed": [], "foreign": [], "open": []}
        # 1) orders whose buy reply never arrived
        for o in self.journal.unresolved_orders():
            found = await self._find_lost_buy(o, live)
            if found:
                cid = int(found["contract_id"])
                self.journal.update_order(o["id"], state="open", contract_id=cid,
                                          buy_price=abs(float(found.get("amount", found.get("buy_price", o["stake"])))),
                                          purchase_time=int(found.get("purchase_time") or found.get("transaction_time")
                                                            or 0) or None,
                                          note="adopted by reconciliation (buy reply was lost)")
                report["adopted"].append(cid)
                self.notify.send(f"Reconciled: the {PAIR.get(o['symbol'], o['symbol'])} order whose reply was lost "
                                 f"DID fill (contract {cid}). It is now tracked; nothing was bought twice.", "reconcile")
            else:
                self.journal.update_order(o["id"], state="failed", note="reconciliation: no such buy at Deriv")
                report["failed"].append(o["id"])
        # 2) open orders: still open at Deriv?
        for o in self.journal.open_orders():
            cid = o["contract_id"]
            poc = await self.broker.contract(cid)
            self.poc[cid] = poc
            if poc.get("is_sold"):
                self._record_close(o, poc, None)
                report["closed"].append(cid)
            else:
                if not o.get("entry_spot") and poc.get("entry_spot"):
                    self._fill_entry(o, poc)
                report["open"].append(cid)
        # 3) contracts the journal does not know
        mine = {o["contract_id"] for o in self.journal.orders() if o["contract_id"]}
        self.foreign = {}
        alerted = set(self.journal.get("foreign_alerted", []) or [])
        for cid, c in live.items():
            if cid in mine:
                continue
            info = parse_shortcode(c.get("shortcode", ""))
            sym = c.get("underlying_symbol") or c.get("symbol") or info.get("symbol", "?")
            self.foreign[cid] = {"symbol": sym, "contract_type": c.get("contract_type") or info.get("contract_type"),
                                 "buy_price": c.get("buy_price"), "purchase_time": c.get("purchase_time")}
            report["foreign"].append(cid)
            if cid not in alerted:
                alerted.add(cid)
                self.notify.send(f"Found an open contract the bot did not open (contract {cid}, "
                                 f"{PAIR.get(sym, sym)}). It counts toward the 2-position limit and the bot "
                                 "will never close it.", "reconcile")
        self.journal.set("foreign_alerted", sorted(alerted))
        self.journal.event("reconcile", **report)
        return report

    async def _find_lost_buy(self, order: dict, live: dict) -> dict | None:
        """A buy for this order at Deriv (statement since just before it was sent), not already journalled."""
        known = {o["contract_id"] for o in self.journal.orders() if o["contract_id"]}
        try:
            txs = await self.broker.statement(int(order["created"]) - 120)
        except DerivError:
            txs = []
        for tx in txs:
            if tx.get("action_type") != "buy" or not tx.get("contract_id"):
                continue
            cid = int(tx["contract_id"])
            info = parse_shortcode(tx.get("shortcode", ""))
            if cid in known or not info:
                continue
            if (info["symbol"] == order["symbol"] and info["contract_type"] == order["direction"]
                    and info["multiplier"] == order["multiplier"] and abs(info["stake"] - order["stake"]) < 0.005):
                return {**tx, "purchase_time": info.get("purchase_time")}
        for cid, c in live.items():             # fall back to the portfolio
            info = parse_shortcode(c.get("shortcode", ""))
            if cid in known or not info:
                continue
            if (info["symbol"] == order["symbol"] and info["contract_type"] == order["direction"]
                    and info["multiplier"] == order["multiplier"] and abs(info["stake"] - order["stake"]) < 0.005
                    and int(info.get("purchase_time", 0)) >= int(order["created"]) - 120):
                return {**c, "purchase_time": info.get("purchase_time")}
        return None

    # ================================================================== positions
    def _fill_entry(self, o: dict, poc: dict) -> None:
        pt = int(poc.get("purchase_time") or poc.get("date_start") or o.get("purchase_time") or self.clock())
        fields = {"entry_spot": float(poc["entry_spot"]) if poc.get("entry_spot") else None,
                  "commission": poc.get("commission"), "purchase_time": pt}
        if not o.get("deadline"):
            fields["deadline"] = sessions.exit_deadline(pt, int(o["multiplier"]))
        self.journal.update_order(o["id"], **fields)

    def _close_reason(self, o: dict, poc: dict, profit: float) -> str:
        if o.get("tp_amount") and profit >= float(o["tp_amount"]) - 0.01:
            return "take_profit"
        if profit <= -float(o["stake"]) + 0.01:
            return "stop_out"
        if o.get("sl_amount") and profit <= -float(o["sl_amount"]) + 0.05:
            return "stop_loss"
        return "closed_by_deriv"

    def _record_close(self, o: dict, poc: dict, reason: str | None) -> None:
        profit = poc.get("profit")
        if profit is None and poc.get("sell_price") is not None:
            profit = float(poc["sell_price"]) - float(o.get("buy_price") or o["stake"])
        profit = round(float(profit or 0.0), 2)
        reason = reason or self._close_reason(o, poc, profit)
        exit_spot = poc.get("exit_spot") or poc.get("sell_spot") or poc.get("exit_tick")
        if not self.journal.close_order(o["id"], reason, profit, poc.get("sell_price"), exit_spot,
                                        poc.get("sell_time")):
            return                                 # already recorded (e.g. by /stop)
        self.poc.pop(o["contract_id"], None)
        self.exit_requests.discard(o["symbol"])
        bal = self.balance()
        self.journal.event("close", o["symbol"], contract_id=o["contract_id"], reason=reason, profit=profit,
                           balance=bal, sell_price=poc.get("sell_price"), exit_spot=exit_spot)
        word = "won" if profit > 0 else "lost"
        self.notify.send(
            f"Trade closed: {PAIR.get(o['symbol'], o['symbol'])} {'Up' if o['direction'] == 'MULTUP' else 'Down'} "
            f"x{o['multiplier']}, {word} {profit:+.2f} USD ({reason.replace('_', ' ')}). "
            f"Bot balance {bal:.2f} USD." + (" [test trade]" if o.get("test") else ""), "trade")

    async def update_positions(self) -> None:
        for o in self.journal.open_orders():
            poc = await self.broker.contract(o["contract_id"])
            self.poc[o["contract_id"]] = poc
            if poc.get("is_sold"):
                self._record_close(o, poc, None)
            elif not o.get("entry_spot") and poc.get("entry_spot"):
                self._fill_entry(o, poc)

    async def close_position(self, o: dict, reason: str) -> None:
        """Sell at market. Checks is_sold first, so a close is never sent twice."""
        poc = await self.broker.contract(o["contract_id"])
        if poc.get("is_sold"):
            self._record_close(o, poc, None)
            return
        try:
            sold = await self.broker.sell(o["contract_id"])
        except DerivError as err:
            poc = await self.broker.contract(o["contract_id"])
            if poc.get("is_sold"):
                self._record_close(o, poc, None)
                return
            self.journal.event("sell_refused", o["symbol"], contract_id=o["contract_id"], error=str(err))
            self.notify.send(f"Deriv refused to close contract {o['contract_id']}: {err.message}. Will retry.",
                             "error")
            return
        poc = await self.broker.contract(o["contract_id"])
        if not poc.get("is_sold"):
            poc = {**poc, "sell_price": sold.get("sold_for"),
                   "profit": float(sold.get("sold_for", 0)) - float(o.get("buy_price") or o["stake"])}
        self._record_close(o, poc, reason)

    # ================================================================== kill switch and limits
    async def check_limits(self, now: float) -> bool:
        """Kill switch and daily loss limit. Returns False if trading must stop now."""
        acct = self.account(now)
        if self.manager.kill_switch_hit(acct) and not self.journal.get("killed", False):
            eq = acct.equity
            self.journal.set("killed", True)
            self.write_halt("kill switch")
            for o in self.journal.open_orders():
                await self.close_position(o, "kill_switch")
            self.pending.clear()
            self.journal.event("kill_switch", equity=eq, balance=self.balance())
            self.notify.send(
                f"KILL SWITCH: bot equity {eq:.2f} USD is at or below 50% of the starting "
                f"{self.limits.starting_balance:.2f} USD. All bot trades were closed and trading has STOPPED. "
                "It stays stopped until you restart it by hand (deploy/DEPLOY.md, 'Clear a halt').", "kill_switch")
            return False
        if self.manager.daily_limit_hit(acct):
            day = sessions.utc_date(int(now)).isoformat()
            if self.journal.get("daily_limit_day") != day:
                self.journal.set("daily_limit_day", day)
                self.journal.event("daily_limit", equity=acct.equity, day_start=acct.day_start_balance)
                self.notify.send(
                    f"Daily loss limit reached: equity {acct.equity:.2f} USD is 10% below today's start "
                    f"({acct.day_start_balance:.2f} USD). No new trades until 00:00 UTC; open trades keep "
                    "their stops.", "daily_limit")
        return True

    async def forced_exits(self, now: float) -> None:
        # Trades of another candidate (STRATEGY_ID was switched) only get deadlines and the kill switch.
        for o in self.journal.open_orders():
            if o.get("deadline") and now >= o["deadline"]:
                await self.close_position(o, "forced_deadline")
            elif o["symbol"] in self.exit_requests and o["strategy"] == self.cid:
                await self.close_position(o, "strategy_exit")

    # ================================================================== strategy
    def strategy_step(self, t: int) -> None:
        """Hand each strategy candle that closed by minute t to the strategy (as the engine does)."""
        tf = self.strategy.timeframe
        open_by_sym = {o["symbol"]: o for o in self.journal.open_orders() if o["strategy"] == self.cid}
        for sym in sessions.pair_order(self.symbols, t):
            bars = self.store.bars(sym, tf, t)
            if len(bars) == 0:
                continue
            last = int(self.last_end.get(sym, 0))
            ends = bars.end
            new = [i for i in range(len(bars)) if int(ends[i]) > last]
            late = [i for i in new if t - int(ends[i]) > 300]
            if late and last:                        # closed while the bot was down: skipped, never traded late
                self.journal.event("candles_skipped", sym, count=len(late), last=iso(int(ends[late[-1]])))
            for i in new:
                sig_epoch = int(ends[i])
                if t - sig_epoch > 300:
                    continue
                o = open_by_sym.get(sym)
                view = None
                if o and o.get("entry_spot"):
                    pt = int(o["purchase_time"] or o["created"])
                    view = PositionView(o["direction"], int(o["multiplier"]), float(o["entry_spot"]), pt - pt % 60)
                if getattr(self.strategy, "needs_peers", False):
                    self.strategy.peers = {s: self.store.bars(s, tf, sig_epoch) for s in self.symbols if s != sym}
                actions = self.strategy.on_candle(sym, bars.slice(i + 1), view, sym in self.pending) or []
                for a in actions:
                    self.journal.event("signal", sym, action=repr(a), candle_end=iso(sig_epoch))
                    if isinstance(a, Enter):
                        req = OrderRequest(sym, a.direction, a.multiplier, a.risk_fraction,
                                           a.stop_loss_pips, a.take_profit_pips, self.cid)
                        self.pending[sym] = Pending(req, sig_epoch, sig_epoch + self.max_wait)
                    elif isinstance(a, ExitPosition) and o:
                        self.exit_requests.add(sym)
                    elif isinstance(a, CancelPending):
                        if self.pending.pop(sym, None):
                            self.journal.event("skip", sym, reason="cancelled")
            self.last_end[sym] = int(ends[-1])
        self.journal.set("last_end", self.last_end)

    # ================================================================== entries
    def _skip(self, sym: str, pend: Pending, reason: str, drop: bool, **detail) -> None:
        first = not pend.first_block
        if first:
            pend.first_block = reason
        if first or drop or reason == "cost_gate":
            self.journal.event("skip", sym, reason=reason, waiting=not drop, signal=iso(pend.signal_epoch), **detail)
        if drop:
            self.pending.pop(sym, None)

    def sl_tp_amounts(self, sym: str, direction: str, stake: float, mult: int, spot: float, rate: float,
                      sl_pips: float | None, tp_pips: float | None) -> tuple[float | None, float | None]:
        """USD amounts for Deriv's limit_order, as fills.open_position computes them in backtests."""
        comm = mc.commission(stake, mult, rate)
        size = mc.position_size(stake, mult)
        sl = tp = None
        if sl_pips is not None:
            amount = round(size * sl_pips * PIP[sym] / spot + comm, 2)
            if amount < round(comm + SL_MIN_ABOVE_COMMISSION, 2):
                raise ValueError("stop_loss_too_tight")
            if amount < stake:
                sl = amount
        if tp_pips is not None:
            tp = min(max(round(size * tp_pips * PIP[sym] / spot - comm, 2), 0.10), 50 * stake)
        return sl, tp

    async def try_entry(self, sym: str, now: float) -> None:
        pend = self.pending[sym]
        t = int(now)
        if t > pend.expires:
            self._skip(sym, pend, "expired", True)
            return
        req = pend.request
        acct = self.account(now)
        d = self.risk.precheck(req, acct, t)
        if not d.allowed:
            self._skip(sym, pend, d.reason, not (d.wait or d.reason in WAIT_REASONS_LIVE) or d.reason == "halted")
            return
        probe = await self.broker.proposal(sym, req.direction, PROBE_STAKE, req.multiplier)
        rate_probe = self.journal.quote(sym, req.direction, req.multiplier, PROBE_STAKE, float(probe["commission"]),
                                        probe.get("spot"), "entry_probe", self.mode)
        d = self.risk.check(req, self.account(now), t, rate_probe)
        if not d.allowed:
            self._skip(sym, pend, d.reason, not d.wait, rate_seen_pct=round(rate_probe * 100, 6),
                       limit_pct=round(self.risk.gate_limit(sym) * 100, 6))
            return
        stake = d.approval.stake
        spot = float(probe.get("spot") or self.store.last_price(sym))
        try:
            sl, tp = self.sl_tp_amounts(sym, req.direction, stake, req.multiplier, spot, rate_probe,
                                        req.stop_loss_pips, req.take_profit_pips)
        except ValueError as err:
            self._skip(sym, pend, str(err), True)
            return
        limit_order = {k: v for k, v in (("stop_loss", sl), ("take_profit", tp)) if v is not None}
        quote = await self.broker.proposal(sym, req.direction, stake, req.multiplier, limit_order or None)
        self.journal.quote(sym, req.direction, req.multiplier, stake, float(quote["commission"]), quote.get("spot"),
                           "order", self.mode)
        ticket, gate = self.risk.authorize(d, quote, rate_probe)
        if ticket is None:
            self._skip(sym, pend, gate.reason, gate.reason not in ("cost_gate", "paused"),
                       rate_probe_pct=round((gate.rate_probe or 0) * 100, 6),
                       rate_quote_pct=round((gate.rate_quote or 0) * 100, 6),
                       limit_pct=round((gate.limit or 0) * 100, 6))
            return
        self.pending.pop(sym, None)
        detail = dict(direction=req.direction, multiplier=req.multiplier, stake=stake, sl_amount=sl, tp_amount=tp,
                      rate_probe_pct=round(rate_probe * 100, 6), rate_quote_pct=round(gate.rate_quote * 100, 6),
                      ask_price=ticket.ask_price, spot=quote.get("spot"), signal=iso(pend.signal_epoch),
                      test=bool(pend.test))
        if self.mode == "dry":
            self.journal.event("dry_run_order", sym, **detail)
            self.notify.send(f"[dry run] Would buy {PAIR[sym]} {'Up' if req.direction == 'MULTUP' else 'Down'} "
                             f"x{req.multiplier}, stake {stake:.2f} USD, SL {sl} TP {tp}; commission rate "
                             f"{gate.rate_quote * 100:.4f}% (limit {gate.limit * 100:.4f}%).", "trade")
            return
        oid = self.journal.new_order(strategy=self.cid if not pend.test else "forced_test", symbol=sym,
                                     direction=req.direction, multiplier=req.multiplier, stake=stake, sl_amount=sl,
                                     tp_amount=tp, signal_epoch=pend.signal_epoch, proposal_id=ticket.proposal_id,
                                     rate_probe=rate_probe, rate_quote=gate.rate_quote, test=1 if pend.test else 0,
                                     deadline=(min(sessions.exit_deadline(t, req.multiplier),
                                                   t + int(pend.test["hold_minutes"]) * 60) if pend.test else None))
        self.journal.event("order", sym, order_id=oid, **detail)
        try:
            bought = await self.broker.buy(ticket)
        except TicketError as err:
            self.journal.update_order(oid, state="failed", note=f"ticket: {err}")
            self.journal.event("order_failed", sym, order_id=oid, error=str(err))
            return
        except DerivError as err:
            self.journal.update_order(oid, state="failed", note=f"{err.code}: {err.message}")
            self.journal.event("order_rejected", sym, order_id=oid, code=err.code, error=err.message)
            self.notify.send(f"Order refused by Deriv: {PAIR[sym]} {req.direction} x{req.multiplier} stake "
                             f"{stake:.2f}: {err.code} {err.message}. Signal dropped; nothing was bought.", "error")
            return
        except BrokerDisconnected:
            self.journal.update_order(oid, state="unknown", note="buy reply lost; reconciliation will settle it")
            self.journal.event("order_unknown", sym, order_id=oid)
            raise
        cid = int(bought["contract_id"])
        pt = int(bought.get("purchase_time") or bought.get("start_time") or t)
        deadline = sessions.exit_deadline(pt, req.multiplier)
        if pend.test:
            deadline = min(deadline, pt + int(pend.test["hold_minutes"]) * 60)
        self.journal.update_order(oid, state="open", contract_id=cid, buy_price=float(bought.get("buy_price", stake)),
                                  purchase_time=pt, deadline=deadline)
        try:
            poc = await self.broker.contract(cid)
            self.poc[cid] = poc
            if poc.get("entry_spot"):
                self._fill_entry(self.journal.order_by_contract(cid), poc)
        except (DerivError, BrokerDisconnected):
            poc = {}
        self.journal.event("opened", sym, order_id=oid, contract_id=cid, entry_spot=poc.get("entry_spot"),
                           commission=poc.get("commission"), deadline=iso(deadline))
        self.notify.send(
            f"Trade opened: {PAIR[sym]} {'Up' if req.direction == 'MULTUP' else 'Down'} x{req.multiplier}, "
            f"stake {stake:.2f} USD (max loss), stop loss {sl if sl else 'none'} / take profit {tp if tp else 'none'} USD. "
            f"Commission {poc.get('commission', quote.get('commission'))} USD, rate {gate.rate_quote * 100:.4f}% "
            f"(cost gate limit {gate.limit * 100:.4f}%). Closes by {iso(deadline)} at the latest."
            + (" [test trade]" if pend.test else ""), "trade")

    # ================================================================== test trades and cost samples
    def take_test_requests(self, now: float) -> None:
        if not self.requests_dir.exists():
            return
        for f in sorted(self.requests_dir.glob("test_trade_*.json")):
            try:
                r = json.loads(f.read_text())
                sym = r["symbol"]
                if sym not in self.symbols or r["direction"] not in ("MULTUP", "MULTDOWN"):
                    raise ValueError("bad symbol or direction")
                req = OrderRequest(sym, r["direction"], int(r.get("multiplier", 100)), float(r.get("risk_fraction", 0.03)),
                                   r.get("sl_pips", 10.0), r.get("tp_pips", 10.0), "forced_test")
                if sym in self.pending:
                    raise ValueError("a signal is already waiting on this pair")
                self.pending[sym] = Pending(req, int(now), int(now) + 600, test={"hold_minutes": int(r.get("hold_minutes", 10))})
                self.journal.event("test_trade_request", sym, **r)
            except Exception as err:
                self.journal.event("test_trade_refused", error=str(err), file=f.name)
            f.unlink(missing_ok=True)

    async def sample_costs(self, now: float) -> None:
        """Hourly quotes (never bought) so the journal collects the real commission rate by hour."""
        t = int(now)
        if not self.cost_sampling or (t % 3600) // 60 != SAMPLE_MINUTE or not sessions.market_open(t) \
                or sessions.in_pause(t):
            return
        key = t - t % 3600
        if self.journal.get("last_sample") == key:
            return
        self.journal.set("last_sample", key)
        for sym in self.symbols:
            for mult in (100, 200):
                try:
                    q = await self.broker.proposal(sym, "MULTUP", PROBE_STAKE, mult)
                    self.journal.quote(sym, "MULTUP", mult, PROBE_STAKE, float(q["commission"]), q.get("spot"),
                                       "hourly_sample", self.mode)
                except DerivError as err:
                    self.journal.event("sample_refused", sym, multiplier=mult, error=f"{err.code}: {err.message}")

    # ================================================================== reports
    def daily_summary(self, now: float) -> str:
        day0 = sessions.day_start(sessions.utc_date(int(now)))
        closed = [o for o in self.journal.orders(("closed",)) if (o["closed"] or 0) >= day0]
        skips = {}
        for e in self.journal.events(day0, ("skip",)):
            skips[e["detail"].get("reason")] = skips.get(e["detail"].get("reason"), 0) + 1
        q = [x for x in self.journal.quotes(day0)]
        pl = round(sum(o["profit"] for o in closed), 2)
        lines = [f"Daily summary {sessions.utc_date(int(now))} ({self.mode}, {self.cid})",
                 f"Trades closed today: {len(closed)}, P/L {pl:+.2f} USD",
                 f"Bot balance {self.balance():.2f} USD, equity {self.equity():.2f} USD "
                 f"(start {self.limits.starting_balance:.2f})",
                 f"Open: {len(self.journal.open_orders())} bot, {len(self.foreign)} other",
                 "Skipped signals: " + (", ".join(f"{k} {v}" for k, v in sorted(skips.items())) or "none"),
                 f"Quotes journalled today: {len(q)}"]
        rates = {}
        for x in q:
            if x["purpose"] in ("hourly_sample", "entry_probe") and x["multiplier"] == 100:
                rates.setdefault(x["symbol"], []).append(x["rate"])
        for s, r in sorted(rates.items()):
            lines.append(f"  {PAIR.get(s, s)} commission rate today: {min(r) * 100:.4f}% to {max(r) * 100:.4f}% "
                         f"(base {self.table.base[s] * 100:.4f}%)")
        return "\n".join(lines)

    def write_status(self, now: float) -> None:
        opens = []
        for o in self.journal.open_orders():
            p = self.poc.get(o["contract_id"]) or {}
            opens.append({"symbol": o["symbol"], "direction": o["direction"], "multiplier": o["multiplier"],
                          "stake": o["stake"], "contract_id": o["contract_id"], "profit": p.get("profit"),
                          "entry_spot": o["entry_spot"], "sl": o["sl_amount"], "tp": o["tp_amount"],
                          "opened": iso(o["purchase_time"] or o["created"]),
                          "deadline": iso(o["deadline"]) if o["deadline"] else None, "test": bool(o["test"])})
        st = {"ts": now, "utc": iso(now), "mode": self.mode, "candidate": self.cid,
              "account_id": self.broker.account_id, "deriv_balance": self.deriv_balance,
              "balance": self.balance(), "equity": self.equity(),
              "start_balance": self.limits.starting_balance, "day_start": (self.journal.get("day_start") or {}),
              "open": opens, "foreign": {str(k): v for k, v in self.foreign.items()},
              "pending": {s: {"direction": p.request.direction, "signal": iso(p.signal_epoch),
                              "expires": iso(p.expires), "waiting_because": p.first_block}
                          for s, p in self.pending.items()},
              "paused": self.paused(), "halted": self.halted(), "connected": self.broker.alive,
              "feed_ok": self.feed_ok, "last_error": self.last_error}
        path = self.home / "status.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, indent=1, default=str))
        tmp.replace(path)

    def heartbeat(self, now: float) -> None:
        p = self.home / "heartbeat"
        tmp = p.with_suffix(".tmp")
        tmp.write_text(f"{int(now)}\n")
        tmp.replace(p)

    # ================================================================== one minute
    async def tick(self, now: float) -> None:
        t = int(now) - int(now) % 60
        if self.halted():
            # Halted (kill switch or /stop): no new trades; keep closing any bot trade still open.
            await self.update_positions()
            for o in self.journal.open_orders():
                await self.close_position(o, "halt")
            self.pending.clear()
            return
        try:
            await self.store.refresh(now)
            self.feed_ok = True
        except Exception as err:
            self.feed_ok = False
            self.journal.event("feed_error", error=f"{type(err).__name__}: {err}")
            await self._reset_feed()
        self.day_start_balance(now)
        await self.update_positions()
        if not await self.check_limits(now):
            return
        if sessions.market_open(t) and self.feed_ok:
            self.strategy_step(t)                    # as the engine: strategy first, then exits, then entries
        await self.forced_exits(now)
        self.take_test_requests(now)
        for sym in sessions.pair_order(self.symbols, t):
            if sym in self.pending:
                await self.try_entry(sym, now)
        await self.sample_costs(now)
        if sessions.is_trading_day(sessions.utc_date(t)) and t % 86400 >= SUMMARY_AT:
            day = sessions.utc_date(t).isoformat()
            if self.journal.get("summary_day") != day:
                self.journal.set("summary_day", day)
                self.notify.send(self.daily_summary(now), "summary")
        if t % 3600 == 0:
            self.store.prune(max(130, getattr(self.strategy, "warmup_days", 120) + 10), now)

    async def _reset_feed(self) -> None:
        feed = getattr(self.store, "feed", None)
        if feed is not None and hasattr(feed, "_connect"):
            try:
                await feed._connect()
            except Exception as err:
                self.journal.event("feed_reconnect_failed", error=f"{type(err).__name__}: {err}")

    # ================================================================== main loop
    async def run(self, until: float | None = None) -> None:
        """Run until stop() or `until` (epoch). Survives disconnects and errors."""
        await self.connect()
        errors = 0
        while not self.stopping and (until is None or self.clock() < until):
            now = self.clock()
            minute = int(now) - int(now) % 60
            try:
                if not self.broker.alive:
                    raise BrokerDisconnected("connection dropped")
                if minute > self.last_minute and now - minute >= TICK_SECOND:
                    self.last_minute = minute
                    await self.tick(now)
                    self.write_status(now)
                    errors = 0
            except BrokerDisconnected as err:
                self.last_error = f"disconnected: {err}"
                self.journal.event("disconnect", error=str(err))
                await self.connect()
            except DerivError as err:
                self.last_error = f"{err.code}: {err.message}"
                self.journal.event("error", error=self.last_error)
                errors += 1
                if errors in (1, 5) or errors % 60 == 0:
                    self.notify.send(f"Deriv error: {self.last_error}. The bot carries on.", "error")
            except Exception as err:
                self.last_error = f"{type(err).__name__}: {err}"
                self.journal.event("error", error=self.last_error, trace=traceback.format_exc()[-2000:])
                log.exception("tick failed")
                errors += 1
                if errors in (1, 5) or errors % 60 == 0:
                    self.notify.send(f"Bot error: {self.last_error}. The bot carries on; see the journal.", "error")
            self.heartbeat(self.clock())
            await self.sleep(1.0)

    def stop(self) -> None:
        self.stopping = True
