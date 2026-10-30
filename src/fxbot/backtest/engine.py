"""Event-driven backtester on 1m candles.

Each minute of the merged timeline (all pairs together, so position limits
work across pairs):
1. A new UTC day resets the start-of-day balance (daily loss limit).
2. Every strategy candle that has closed by this minute is handed to the
   strategy, with only the candles up to and including it.
3. Per pair with a 1m candle this minute, in an order that rotates from
   minute to minute (sessions.pair_order), so no pair is always first:
   a. manual exits, then forced exits (deadline passed: 20:30 before a
      weekend/closed day, 20:50 for x200), at the open, mid price;
   b. TP / SL / stop out checks on this candle (fills.check_bar);
   c. a pending signal asks the risk module; if approved it opens at this
      open (+0.5 pip) and is checked against the rest of this candle; if the
      answer is "not now" it waits, at most the fixed wait for its timeframe
      (1h: 1 hour, 4h: 4 hours, daily: 12 hours; strategies.base).
4. Equity = balance + open profit at this minute's close. Kill switch -> all
   trades closed at this close, run stops.

Research option kill_switch="observe" (never for live trading): when the kill
switch fires, the event is recorded, all trades are closed as live would, and
the "manual restart" is acted out by resetting the balance to the starting
balance. The run continues, so results cover the whole period. Any recorded
event still counts as a fail (`kill_switch_fired`).

State is saved after every month so a long run can stop and resume.
"""

from __future__ import annotations

import datetime as dt
import pickle
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from fxbot import sessions
from fxbot.backtest import fills
from fxbot.backtest.candles import Bars, load_candles
from fxbot.risk.limits import AccountState, OrderRequest, RiskLimits, RiskManager
from fxbot.strategies.base import (CancelPending, Enter, ExitPosition, PositionView, Strategy,
                                   max_wait_seconds)

ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = ROOT / "state" / "backtest"


@dataclass
class Pending:
    request: OrderRequest
    signal_epoch: int
    expires: int
    first_block: str = ""


@dataclass
class EngineState:
    balance: float
    day_start_balance: float
    starting_balance: float
    current_day: int = -1
    timeline_pos: int = 0
    m1_pos: dict = field(default_factory=dict)
    tf_pos: dict = field(default_factory=dict)
    positions: dict = field(default_factory=dict)       # symbol -> fills.Position
    pending: dict = field(default_factory=dict)         # symbol -> Pending
    exit_requests: set = field(default_factory=set)
    last_close: dict = field(default_factory=dict)
    trades: list = field(default_factory=list)
    equity: list = field(default_factory=list)          # (epoch, equity) hourly + at trade closes
    signals: list = field(default_factory=list)         # (signal_epoch, symbol, action)
    blocked: Counter = field(default_factory=Counter)   # first reason a signal could not fill at once
    refused: Counter = field(default_factory=Counter)   # signals dropped: expired / rejected / too tight
    gate_skips: list = field(default_factory=list)      # (epoch, symbol, rate) first gate block per signal
    killed: bool = False
    kill_events: list = field(default_factory=list)     # observe mode: each time the kill switch fired
    done: bool = False
    strategy_state: object = None


class Engine:
    def __init__(self, strategy: Strategy, symbols: list[str], start: dt.date, end: dt.date,
                 limits: RiskLimits = RiskLimits(), stress: float = 1.0, include_holdout: bool = False,
                 data: dict[str, tuple[Bars, Bars]] | None = None, run_name: str | None = None,
                 table: fills.CommissionTable | None = None, kill_switch: str = "enforce"):
        if kill_switch not in ("enforce", "observe"):
            raise ValueError("kill_switch must be 'enforce' or 'observe'")
        self.kill_switch = kill_switch
        self.max_wait = max_wait_seconds(strategy)
        self.strategy, self.symbols, self.stress = strategy, list(symbols), stress
        self.table = table or fills.CommissionTable()
        self.risk = RiskManager(limits, self.table.base)
        self.data = data or {s: load_candles(s, strategy.timeframe, start, end, include_holdout)
                             for s in self.symbols}
        self.m1 = {s: tuple(a.tolist() for a in (b.epoch, b.open, b.high, b.low, b.close))
                   for s, (b, _) in self.data.items()}
        self.tf = {s: tf for s, (_, tf) in self.data.items()}
        self.tf_end = {s: tf.end.tolist() for s, tf in self.tf.items()}
        self.timeline = np.unique(np.concatenate([self.data[s][0].epoch for s in self.symbols])).tolist()
        self.run_name = run_name
        self.state = EngineState(limits.starting_balance, limits.starting_balance, limits.starting_balance,
                                 m1_pos={s: 0 for s in self.symbols}, tf_pos={s: 0 for s in self.symbols})
        if run_name and self._state_path().exists():
            self._resume()

    # ------------------------------------------------------------- persistence
    def _state_path(self) -> Path:
        return STATE_DIR / f"{self.run_name}.pkl"

    def _save(self) -> None:
        if not self.run_name:
            return
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        self.state.strategy_state = self.strategy
        tmp = self._state_path().with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(self.state))
        tmp.replace(self._state_path())

    def _resume(self) -> None:
        self.state = pickle.loads(self._state_path().read_bytes())
        if self.state.strategy_state is not None:
            self.strategy = self.state.strategy_state

    # ------------------------------------------------------------- helpers
    def _account(self) -> AccountState:
        st = self.state
        return AccountState(st.balance, self._equity(), st.day_start_balance, st.starting_balance,
                            list(st.positions), st.killed)

    def _equity(self) -> float:
        st = self.state
        return st.balance + sum(fills.profit_at(p, st.last_close.get(s, p.entry))
                                for s, p in st.positions.items())

    def _close(self, sym: str, ex: fills.Exit) -> None:
        st = self.state
        p = st.positions.pop(sym)
        st.exit_requests.discard(sym)
        st.balance = round(st.balance + ex.profit, 2)
        st.trades.append({
            "strategy": self.strategy.name, "symbol": sym, "direction": p.direction,
            "multiplier": p.multiplier, "stake": p.stake,
            "signal_time": _iso(p.signal_epoch), "entry_time": _iso(p.entry_epoch),
            "delay_min": round((p.entry_epoch - p.signal_epoch) / 60, 1),
            "entry": p.entry, "exit_time": _iso(ex.epoch), "exit": round(ex.price, 6),
            "reason": ex.reason, "rate_pct": round(p.rate * 100, 5),
            "commission": round(p.commission, 4), "sl_amount": p.sl_amount, "tp_amount": p.tp_amount,
            "profit": ex.profit, "balance_after": st.balance,
            "entry_epoch": p.entry_epoch, "exit_epoch": ex.epoch,
        })
        st.equity.append((ex.epoch, self._equity()))

    def _strategy_step(self, sym: str, t: int) -> None:
        st = self.state
        ends = self.tf_end[sym]
        i = st.tf_pos[sym]
        while i < len(ends) and ends[i] <= t:
            i += 1
            pos = st.positions.get(sym)
            view = PositionView(pos.direction, pos.multiplier, pos.entry, pos.entry_epoch) if pos else None
            sig_epoch = ends[i - 1]
            if getattr(self.strategy, "needs_peers", False):
                # Other pairs' candles closed by this candle's end (no look-ahead).
                self.strategy.peers = {s: self.tf[s].slice(int(np.searchsorted(self.tf[s].end, sig_epoch, "right")))
                                       for s in self.symbols if s != sym}
            actions = self.strategy.on_candle(sym, self.tf[sym].slice(i), view, sym in st.pending)
            for a in actions or []:
                st.signals.append((sig_epoch, sym, repr(a)))
                if isinstance(a, Enter):
                    req = OrderRequest(sym, a.direction, a.multiplier, a.risk_fraction,
                                       a.stop_loss_pips, a.take_profit_pips, self.strategy.name)
                    st.pending[sym] = Pending(req, sig_epoch, sig_epoch + self.max_wait)
                elif isinstance(a, ExitPosition) and sym in st.positions:
                    st.exit_requests.add(sym)
                elif isinstance(a, CancelPending):
                    if st.pending.pop(sym, None):
                        st.refused["cancelled"] += 1
        st.tf_pos[sym] = i

    def _try_entry(self, sym: str, t: int, o: float) -> None:
        st = self.state
        pend = st.pending[sym]
        if t > pend.expires:
            st.pending.pop(sym)
            st.refused["expired"] += 1
            return
        rate = self.table.rate(sym, t)
        d = self.risk.check_entry(pend.request, self._account(), t, rate)
        if not d.allowed:
            if not pend.first_block:
                pend.first_block = d.reason
                st.blocked[d.reason] += 1
                if d.reason == "cost_gate":
                    st.gate_skips.append((_iso(t), sym, round(d.rate_seen * 100, 5)))
            if not d.wait:
                st.pending.pop(sym)
                st.refused[d.reason] += 1
            return
        st.pending.pop(sym)
        r = d.approval.request
        try:
            p = fills.open_position(sym, r.direction, r.multiplier, d.approval.stake, o, t, rate,
                                    r.stop_loss_pips, r.take_profit_pips, self.stress)
        except ValueError as err:
            st.refused[str(err)] += 1
            return
        p.deadline = self.risk.exit_deadline(t, r.multiplier)
        p.signal_epoch = pend.signal_epoch
        p.strategy = self.strategy.name
        st.positions[sym] = p

    def _restart_after_kill(self, t: int, equity: float) -> None:
        """Observe mode: record the event, then reset the balance as a manual restart would."""
        st = self.state
        st.kill_events.append({"time": _iso(t), "epoch": t, "equity": round(equity, 2),
                               "balance_after_close": st.balance, "trade_number": len(st.trades),
                               "top_up": round(st.starting_balance - st.balance, 2)})
        st.balance = st.day_start_balance = st.starting_balance
        st.pending.clear()
        st.equity.append((t, st.balance))

    @property
    def kill_switch_fired(self) -> bool:
        return self.state.killed or bool(self.state.kill_events)

    # ------------------------------------------------------------- main loop
    def run(self, max_seconds: float | None = None) -> bool:
        """Run (or continue). Returns True when finished, False if stopped for time."""
        st = self.state
        t_start = time.time()
        timeline = self.timeline
        last_month = None
        while st.timeline_pos < len(timeline) and not st.done:
            t = timeline[st.timeline_pos]
            month = t // (86400 * 30)
            if last_month is not None and month != last_month:
                self._save()
                if max_seconds is not None and time.time() - t_start > max_seconds:
                    return False
            last_month = month
            day = t // 86400
            if day != st.current_day:
                st.current_day = day
                st.day_start_balance = st.balance
            order = sessions.pair_order(self.symbols, t)      # no pair is always first
            for sym in order:
                self._strategy_step(sym, t)
            for sym in order:
                ep, op, hi, lo, cl = self.m1[sym]
                i = st.m1_pos[sym]
                if i >= len(ep) or ep[i] != t:
                    continue
                o, h, low, c = op[i], hi[i], lo[i], cl[i]
                st.m1_pos[sym] = i + 1
                pos = st.positions.get(sym)
                if pos is not None:
                    if sym in st.exit_requests:
                        self._close(sym, fills.close_at(pos, t, o, "strategy_exit"))
                    elif t >= pos.deadline:
                        self._close(sym, fills.close_at(pos, t, o, "forced_deadline"))
                    else:
                        ex = fills.check_bar(pos, t, o, h, low, c)
                        if ex:
                            self._close(sym, ex)
                if sym in st.pending:
                    self._try_entry(sym, t, o)
                    pos = st.positions.get(sym)
                    if pos is not None:
                        ex = fills.check_bar(pos, t, pos.entry, h, low, c)
                        if ex:
                            self._close(sym, ex)
                st.last_close[sym] = c
            if self.risk.kill_switch_hit(self._account()):
                equity = self._equity()
                for sym, pos in list(st.positions.items()):
                    self._close(sym, fills.close_at(pos, t, st.last_close[sym], "kill_switch"))
                if self.kill_switch == "observe":
                    self._restart_after_kill(t, equity)
                else:
                    st.killed = st.done = True
            if t % 3600 == 0:
                st.equity.append((t, self._equity()))
            st.timeline_pos += 1
        if not st.done:
            # End of data: close what is still open at the last price.
            t = timeline[-1] + 60 if timeline else 0
            for sym, pos in list(st.positions.items()):
                self._close(sym, fills.close_at(pos, t, st.last_close[sym], "end_of_data"))
            st.done = True
        self._save()
        return True


def _iso(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
