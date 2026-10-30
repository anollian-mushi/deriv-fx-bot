"""Hard risk limits from CLAUDE.md, shared by the backtester and the live bot.

Strategies only produce OrderRequests. RiskManager.check_entry() is the only
way to get an Approval, and opening a position requires an Approval, so no
strategy (or caller) can open a trade the limits would refuse.

Limits:
- stake = risk fraction x current balance, never more than 3%, rounded down
  to the cent; no trade below Deriv's 1 USD minimum stake
- daily loss limit: equity 10% below the start-of-day balance -> no new
  trades until the next UTC day
- kill switch: equity at or below 50% of the starting balance -> close
  everything, stop trading, manual restart required
- at most 2 open positions and 1 per pair
- multiplier x100 or x200 only; x200 is closed by 20:50 UTC on its opening
  day (sessions.exit_deadline), so only x100 is held past the day it opened
- live cost gate: skip if the commission rate (quoted live, table rate in
  backtests) is above 1.5x the pair's base rate
- calendar: market open, entry window 06:00-17:59 UTC, never 20:55-21:30,
  every trade closed by 20:30 before a weekend or closed day
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from fxbot import sessions

# Reasons a new trade cannot open *now*; the signal may wait and try again.
WAIT_REASONS = {"market_closed", "daily_pause", "outside_entry_window", "pre_closure", "cost_gate",
                "no_price", "daily_loss_limit", "max_positions", "one_per_pair", "stake_below_minimum"}
# Reasons the request can never be approved.
REJECT_REASONS = {"multiplier_not_allowed", "kill_switch", "bad_risk_fraction"}


@dataclass(frozen=True)
class RiskLimits:
    starting_balance: float = 100.0
    max_risk_fraction: float = 0.03
    daily_loss_fraction: float = 0.10
    kill_switch_fraction: float = 0.50
    max_positions: int = 2
    max_per_pair: int = 1
    allowed_multipliers: tuple[int, ...] = (100, 200)
    gate_factor: float = 1.5
    min_stake: float = 1.0
    max_stake: float = 2000.0

    def __post_init__(self):
        if not 50 <= self.starting_balance <= 100:
            raise ValueError("starting balance must be 50-100 USD (CLAUDE.md)")
        if self.max_risk_fraction > 0.03 or self.daily_loss_fraction > 0.10 or self.kill_switch_fraction < 0.50:
            raise ValueError("limits cannot be loosened beyond CLAUDE.md")
        if set(self.allowed_multipliers) - {100, 200} or self.max_positions > 2 or self.gate_factor > 1.5:
            raise ValueError("limits cannot be loosened beyond CLAUDE.md")


@dataclass
class OrderRequest:
    symbol: str
    direction: str
    multiplier: int = 100
    risk_fraction: float = 0.03
    stop_loss_pips: float | None = None
    take_profit_pips: float | None = None
    strategy: str = ""


@dataclass
class AccountState:
    balance: float
    equity: float
    day_start_balance: float
    starting_balance: float
    open_symbols: list[str] = field(default_factory=list)
    killed: bool = False


_TOKEN = object()


class Approval:
    """Proof that RiskManager approved an order. Only RiskManager can make one."""

    def __init__(self, token, request: OrderRequest, stake: float, epoch: int, rate: float):
        if token is not _TOKEN:
            raise PermissionError("only RiskManager can approve orders")
        self.request, self.stake, self.epoch, self.rate = request, stake, epoch, rate


@dataclass
class Decision:
    allowed: bool
    reason: str = ""
    approval: Approval | None = None
    rate_seen: float | None = None

    @property
    def wait(self) -> bool:
        return not self.allowed and self.reason in WAIT_REASONS


class RiskManager:
    def __init__(self, limits: RiskLimits, base_rates: dict[str, float]):
        self.limits = limits
        self.base_rates = base_rates

    def stake_for(self, balance: float, risk_fraction: float) -> float:
        f = min(risk_fraction, self.limits.max_risk_fraction)
        return min(math.floor(balance * f * 100 + 1e-9) / 100, self.limits.max_stake)

    def kill_switch_hit(self, acct: AccountState) -> bool:
        return acct.killed or acct.equity <= self.limits.kill_switch_fraction * acct.starting_balance + 1e-9

    def daily_limit_hit(self, acct: AccountState) -> bool:
        return acct.equity <= (1 - self.limits.daily_loss_fraction) * acct.day_start_balance + 1e-9

    def check_entry(self, req: OrderRequest, acct: AccountState, epoch: int,
                    rate: float | None) -> Decision:
        """Approve or refuse opening `req` at `epoch` with commission `rate` (fraction)."""
        lim = self.limits
        if self.kill_switch_hit(acct):
            return Decision(False, "kill_switch")
        if req.multiplier not in lim.allowed_multipliers:
            return Decision(False, "multiplier_not_allowed")
        if not 0 < req.risk_fraction <= lim.max_risk_fraction:
            return Decision(False, "bad_risk_fraction")
        ok, why = sessions.entry_allowed_by_calendar(epoch)
        if not ok:
            return Decision(False, why)
        if rate is None:
            return Decision(False, "no_price")
        if rate > lim.gate_factor * self.base_rates[req.symbol] * (1 + 1e-9):
            return Decision(False, "cost_gate", rate_seen=rate)
        if self.daily_limit_hit(acct):
            return Decision(False, "daily_loss_limit")
        if len(acct.open_symbols) >= lim.max_positions:
            return Decision(False, "max_positions")
        if acct.open_symbols.count(req.symbol) >= lim.max_per_pair:
            return Decision(False, "one_per_pair")
        stake = self.stake_for(acct.balance, req.risk_fraction)
        if stake < lim.min_stake:
            return Decision(False, "stake_below_minimum")
        return Decision(True, approval=Approval(_TOKEN, req, stake, epoch, rate), rate_seen=rate)

    @staticmethod
    def exit_deadline(open_epoch: int, multiplier: int) -> int:
        """Forced close time: 20:30 before any weekend/closed day; x200 by 20:50 same day."""
        return sessions.exit_deadline(open_epoch, multiplier)
