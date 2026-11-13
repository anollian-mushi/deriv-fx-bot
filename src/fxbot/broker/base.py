"""The broker-neutral interface: what the trading engine needs from any broker.

One adapter per broker (Deriv Multipliers, cTrader, the paper broker) turns
these calls into that broker's own API. The engine (fxbot.trading) only ever
talks to a BrokerAdapter, so the same strategy and the same risk module run
on every broker.

Conventions every adapter follows:
- symbol: the project's symbol name from fxbot.symbols (e.g. "frxEURUSD"),
  so the risk module's per-pair base rates and the strategies' symbol lists
  stay the same everywhere. Each adapter maps it to its broker's own name
  (cTrader "EURUSD", symbol id 1, ...).
- direction: "up" (buy / MULTUP) or "down" (sell / MULTDOWN).
- prices: the broker's quoted prices; sizes in Instrument.size_unit:
  "usd_stake" (Deriv Multipliers: size = stake in USD, the most it can lose)
  or "units" (cTrader: base-currency units, 1 lot = 100,000).
- money: USD, the account currency.
- times: UTC epoch seconds.

Sizing rule (quote): the adapter sizes the position so that the loss at the
stop loss (or at the broker's forced close, such as Deriv's stop out),
including the costs it knows of, never exceeds intent.max_loss_usd. The
size is rounded DOWN to the size step. If that leaves less than the
broker's minimum size, quote() raises BrokerError("below_minimum_size"): a
size is never rounded up. A units broker has no forced close at a fixed
loss, so it needs a stop loss: without one quote() raises
BrokerError("stop_required").

Cost (Quote.cost_usd, cost_rate): everything the trade costs that is known
at entry: Deriv's commission; for cTrader the spread plus commission on
both sides. cost_rate = cost_usd / notional in USD. The engine hands it to
the risk module's live cost gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from fxbot.backtest.candles import Bars

UP, DOWN = "up", "down"
SIZE_UNITS = ("usd_stake", "units")

# BrokerError codes the engine acts on. Adapters may use others (then the engine records and skips).
BELOW_MINIMUM_SIZE = "below_minimum_size"     # the allowed loss buys less than the minimum size
STOP_REQUIRED = "stop_required"               # a units broker cannot cap the loss without a stop loss
STOP_TOO_CLOSE = "stop_too_close"             # the broker's minimum stop distance is not met
QUOTE_EXPIRED = "quote_expired"               # open() was called after Quote.expires_epoch
WRONG_ACCOUNT_TYPE = "wrong_account_type"     # connect(): demo expected and a real account found, or the reverse
NOT_FOUND = "not_found"                       # position(ref) / modify / close of an unknown ref
REJECTED = "rejected"                         # the broker refused the order (market closed, margin, ...)

# BrokerPosition.close_reason values
CLOSE_REASONS = ("stop_loss", "take_profit", "stop_out", "closed", "broker")


def direction_of(contract_type: str) -> str:
    """Strategy direction (MULTUP / MULTDOWN, or up / down) -> "up" / "down"."""
    d = contract_type.strip().lower()
    if d in ("multup", "up", "buy", "long"):
        return UP
    if d in ("multdown", "down", "sell", "short"):
        return DOWN
    raise ValueError(f"unknown direction {contract_type!r}")


@dataclass(frozen=True)
class AccountInfo:
    broker: str
    account_id: str
    is_demo: bool
    currency: str
    balance: float
    equity: float


@dataclass(frozen=True)
class Instrument:
    symbol: str
    pip: float
    price_step: float
    min_size: float
    size_step: float
    size_unit: str                    # "usd_stake" or "units"


@dataclass(frozen=True)
class OrderIntent:
    symbol: str
    direction: str                    # "up" | "down"
    max_loss_usd: float               # approved by the risk module: the most this trade may lose
    stop_loss_pips: float | None
    take_profit_pips: float | None
    multiplier: int | None            # Deriv x100 / x200; None for a units broker
    client_order_id: str              # unique per order; the key that makes open() idempotent


@dataclass(frozen=True)
class Quote:
    intent: OrderIntent
    price: float                      # expected fill price (ask for up, bid for down)
    size: float                       # in Instrument.size_unit, rounded down to the step
    cost_usd: float                   # all costs known at entry (see module notes)
    cost_pips: float                  # the same cost in pips of this position
    cost_rate: float | None           # cost_usd / notional USD; the live cost gate reads it
    stop_loss_price: float | None
    take_profit_price: float | None
    worst_case_loss_usd: float        # loss at the stop / forced close, costs included
    expires_epoch: float              # open() refuses the quote after this
    raw: dict = field(default_factory=dict, compare=False)


@dataclass
class BrokerPosition:
    ref: str                          # the broker's id for the position (contract id, position id)
    symbol: str
    direction: str                    # "up" | "down"
    size: float
    entry_price: float
    entry_epoch: float
    stop_loss_price: float | None
    take_profit_price: float | None
    open_profit_usd: float            # profit if closed now (0 once closed)
    is_open: bool
    exit_price: float | None = None
    exit_epoch: float | None = None
    profit_usd: float | None = None   # final result, costs included, once closed
    close_reason: str | None = None   # one of CLOSE_REASONS once closed
    client_order_id: str | None = None   # None for positions this bot did not open
    cost_usd: float | None = None     # costs charged so far (commission, swap), if the broker reports them


class BrokerError(Exception):
    """The broker refused or could not do something. retryable: the same call may work later."""

    def __init__(self, code: str, message: str = "", retryable: bool = False):
        super().__init__(f"{code}: {message}" if message else code)
        self.code, self.message, self.retryable = code, message or code, retryable


class BrokerDisconnected(ConnectionError):
    """The connection dropped or a reply did not arrive. Reconnect, then reconcile before anything else."""


@runtime_checkable
class BrokerAdapter(Protocol):
    name: str

    async def connect(self) -> AccountInfo:
        """Log in. Must verify the account type matches the configured mode (demo unless real was
        explicitly configured) and raise BrokerError(WRONG_ACCOUNT_TYPE) otherwise."""

    async def close(self) -> None: ...

    @property
    def alive(self) -> bool: ...

    async def account(self) -> AccountInfo: ...

    async def instrument(self, symbol: str) -> Instrument: ...

    async def price(self, symbol: str) -> tuple[float, float, float]:
        """(bid, ask, epoch) of the latest price."""

    async def candles(self, symbol: str, timeframe: str, count: int) -> Bars:
        """The last `count` CLOSED candles (mid prices), oldest first."""

    async def quote(self, intent: OrderIntent) -> Quote:
        """Size and price an order (module notes). Never rounds the size up."""

    async def open(self, quote: Quote) -> BrokerPosition:
        """Open the quoted position. Idempotent on client_order_id: a retry after a lost reply returns
        the position already opened, never a second one."""

    async def positions(self) -> list[BrokerPosition]:
        """Every open position on the account, including ones this bot did not open."""

    async def position(self, ref: str) -> BrokerPosition:
        """One position, open or closed, with its final result once closed."""

    async def modify(self, ref: str, *, stop_loss_price: float | None = None,
                     take_profit_price: float | None = None) -> BrokerPosition: ...

    async def close_position(self, ref: str) -> BrokerPosition:
        """Close at market. Closing an already-closed position returns it unchanged (no error)."""

    async def history(self, since_epoch: float) -> list[BrokerPosition]:
        """Positions closed since since_epoch, for reconciliation."""
