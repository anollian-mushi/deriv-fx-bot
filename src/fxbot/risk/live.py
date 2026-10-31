"""Live order gate: every live buy passes through here (CLAUDE.md hard risk limits).

The hard limits themselves stay in fxbot.risk.limits (shared with the
backtester and the incubator, unchanged). This module adds what only exists
live:

1. A HALT file (kill switch, Telegram /stop) and the /pause flag block every
   new order, checked again right before each buy.
2. The live cost gate reads the commission in the quotes, not a table:
   - a probe quote at a large stake gives the exact rate (the quote shows
     commission rounded to the cent; at 1000 USD x100 that rounding is
     0.00005% of the rate, at a 3 USD stake it would be about 5%);
   - the real quote for the order is checked again with its own commission.
   The trade is skipped if either rate is above 1.5x the pair's base rate
   (EUR/USD 0.0239%, GBP/USD 0.0203%, USD/JPY 0.0275%). Every skip is
   journalled with the rates seen.
3. Broker.buy() only accepts a BuyTicket, and only LiveRisk.authorize() can
   make one, after RiskManager.check_entry() approved the order. A ticket is
   single-use and expires after 20 seconds.

Strategy code never sees the broker, so it cannot bypass any of this.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

from fxbot.risk.limits import AccountState, Approval, Decision, OrderRequest, RiskManager

PROBE_STAKE = 1000.0           # USD; quotes only, never bought
TICKET_TTL = 20.0              # seconds
_TOKEN = object()


class TicketError(PermissionError):
    pass


class BuyTicket:
    """Permission to buy one specific quote. Only LiveRisk.authorize() can make one."""

    def __init__(self, token, approval: Approval, proposal_id: str, ask_price: float, symbol: str,
                 direction: str, stake: float, multiplier: int, rate_probe: float, rate_quote: float,
                 issued: float):
        if token is not _TOKEN:
            raise TicketError("only LiveRisk can issue buy tickets")
        self.approval, self.proposal_id, self.ask_price = approval, proposal_id, ask_price
        self.symbol, self.direction, self.stake, self.multiplier = symbol, direction, stake, multiplier
        self.rate_probe, self.rate_quote, self.issued = rate_probe, rate_quote, issued
        self.used = False

    def redeem(self, now: float) -> None:
        """Called by the broker right before sending the buy."""
        if self.used:
            raise TicketError("buy ticket already used (no duplicate orders)")
        if now - self.issued > TICKET_TTL:
            raise TicketError("buy ticket expired; quote again")
        self.used = True


@dataclass
class GateResult:
    ok: bool
    reason: str = ""
    rate_probe: float | None = None
    rate_quote: float | None = None
    limit: float | None = None


class LiveRisk:
    def __init__(self, manager: RiskManager, blocked: Callable[[], str | None], clock=time.time):
        """blocked() returns a reason ("halted", "paused") when no new order may be placed."""
        self.manager = manager
        self.blocked = blocked
        self.clock = clock

    def gate_limit(self, symbol: str) -> float:
        return self.manager.limits.gate_factor * self.manager.base_rates[symbol]

    def precheck(self, req: OrderRequest, acct: AccountState, epoch: int) -> Decision:
        """Everything except the price: calendar, limits, kill switch. Saves quoting when it is pointless."""
        why = self.blocked()
        if why:
            return Decision(False, why)
        return self.manager.check_entry(req, acct, epoch, 0.0)

    def check(self, req: OrderRequest, acct: AccountState, epoch: int, rate_probe: float | None) -> Decision:
        """Full check with the exact rate from the probe quote."""
        why = self.blocked()
        if why:
            return Decision(False, why)
        return self.manager.check_entry(req, acct, epoch, rate_probe)

    def quote_gate(self, symbol: str, commission: float, stake: float, multiplier: int) -> tuple[bool, float]:
        """Gate on the order's own quote. Returns (ok, rate). The shown commission is rounded to the cent."""
        rate = commission / (stake * multiplier)
        return rate <= self.gate_limit(symbol) * (1 + 1e-9), rate

    def authorize(self, decision: Decision, quote: dict, rate_probe: float) -> tuple[BuyTicket | None, GateResult]:
        if not decision.allowed or decision.approval is None:
            return None, GateResult(False, decision.reason or "not_approved")
        why = self.blocked()
        if why:
            return None, GateResult(False, why)
        a = decision.approval
        r = a.request
        limit = self.gate_limit(r.symbol)
        ok, rate_quote = self.quote_gate(r.symbol, float(quote["commission"]), a.stake, r.multiplier)
        res = GateResult(ok, "" if ok else "cost_gate", rate_probe, rate_quote, limit)
        if rate_probe > limit * (1 + 1e-9):
            res.ok, res.reason = False, "cost_gate"
        if not res.ok:
            return None, res
        if float(quote["ask_price"]) > a.stake + 1e-9:
            return None, GateResult(False, "price_above_stake", rate_probe, rate_quote, limit)
        ticket = BuyTicket(_TOKEN, a, str(quote["id"]), float(quote["ask_price"]), r.symbol, r.direction,
                           a.stake, r.multiplier, rate_probe, rate_quote, self.clock())
        return ticket, res
