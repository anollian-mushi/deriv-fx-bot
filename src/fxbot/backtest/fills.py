"""How a Multiplier trade fills and closes in the backtester.

Measured in Phase 2 (reports/costs.md, sections 7, 8 and 10):
- Commission: the rate for the UTC hour the trade opens, ONLY from
  research/phase2/cost_by_hour.json (CLAUDE.md). A stress factor (1.5)
  multiplies it. The unrounded amount sets TP/SL/stop-out prices.
- Entry at the mid price, plus 0.5 pip against us.
- Take profit pays exactly the amount set.
- Stop loss exits 1 pip past its level; if a candle opens beyond the level
  (a gap), at that open plus 1 pip. The loss can never exceed the stake.
- Stop out by the measured formula (loss = whole stake).
- If one 1m candle touches both TP and SL (or stop out), SL is taken first.
- Manual and forced closes fill at the mid price (sells filled exactly at the
  shown price on all demo trades).
- Profit is rounded to the nearest cent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from fxbot.contracts import multiplier as mc

ROOT = Path(__file__).resolve().parents[3]
COST_TABLE = ROOT / "research" / "phase2" / "cost_by_hour.json"
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
PIP_SIZE = {"frxEURUSD": 0.00001, "frxGBPUSD": 0.00001, "frxUSDJPY": 0.001}
ENTRY_SLIPPAGE_PIPS = 0.5
SL_SLIPPAGE_PIPS = 1.0
SL_MIN_ABOVE_COMMISSION = 0.02


class CommissionTable:
    """Commission rates by UTC hour (fractions, e.g. 0.000239 for 0.0239%)."""

    def __init__(self, path: Path = COST_TABLE):
        data = json.loads(path.read_text())
        self.base = {s: v / 100 for s, v in data["base_rate_pct"].items()}
        self.by_hour: dict[int, dict[str, float] | None] = {}
        for h, info in data["hours"].items():
            rates = info.get("max_rate_pct")
            self.by_hour[int(h)] = {s: v / 100 for s, v in rates.items()} if rates else None

    def rate(self, symbol: str, epoch: int) -> float | None:
        """Rate for the UTC hour of `epoch`; None if no price was measured (paused hour)."""
        rates = self.by_hour.get((epoch % 86400) // 3600)
        return rates[symbol] if rates else None


@dataclass
class Position:
    symbol: str
    direction: str            # MULTUP / MULTDOWN
    multiplier: int
    stake: float
    entry: float
    entry_epoch: int
    commission: float         # unrounded USD
    rate: float
    stop_out: float
    sl_amount: float | None = None
    tp_amount: float | None = None
    sl_price: float | None = None
    tp_price: float | None = None
    deadline: int = 0
    signal_epoch: int = 0
    strategy: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def up(self) -> bool:
        return self.direction == "MULTUP"


@dataclass
class Exit:
    epoch: int
    price: float
    reason: str               # take_profit / stop_loss / stop_out / manual / forced_*
    profit: float             # rounded to the cent


def entry_price(symbol: str, direction: str, mid_open: float) -> float:
    slip = ENTRY_SLIPPAGE_PIPS * PIP[symbol]
    return mid_open + slip if direction == "MULTUP" else mid_open - slip


def open_position(symbol: str, direction: str, multiplier: int, stake: float, mid_open: float,
                  epoch: int, rate: float, stop_loss_pips: float | None = None,
                  take_profit_pips: float | None = None, stress: float = 1.0) -> Position:
    """Open a contract. Raises ValueError if the stop loss is too tight for Deriv."""
    entry = entry_price(symbol, direction, mid_open)
    rate = rate * stress
    comm = mc.commission(stake, multiplier, rate)
    size = mc.position_size(stake, multiplier)
    pos = Position(symbol, direction, multiplier, stake, entry, epoch, comm, rate,
                   stop_out=mc.deriv_stop_out_price(direction, stake, multiplier, entry, comm,
                                                     PIP_SIZE[symbol]))
    if stop_loss_pips is not None:
        amount = round(size * stop_loss_pips * PIP[symbol] / entry + comm, 2)
        if amount < round(comm + SL_MIN_ABOVE_COMMISSION, 2):
            raise ValueError("stop_loss_too_tight")
        if amount < stake:              # otherwise the stop out comes first anyway
            pos.sl_amount = amount
            pos.sl_price = mc.round_price(
                mc.stop_loss_price(direction, stake, multiplier, entry, amount, comm), PIP_SIZE[symbol])
    if take_profit_pips is not None:
        amount = max(round(size * take_profit_pips * PIP[symbol] / entry - comm, 2), 0.10)
        pos.tp_amount = amount
        pos.tp_price = mc.round_price(
            mc.take_profit_price(direction, stake, multiplier, entry, amount, comm), PIP_SIZE[symbol])
    return pos


def profit_at(pos: Position, price: float) -> float:
    return round(mc.profit(pos.direction, pos.stake, pos.multiplier, pos.entry, price, pos.commission), 2)


def _sl_exit(pos: Position, epoch: int, level: float) -> Exit:
    slip = SL_SLIPPAGE_PIPS * PIP[pos.symbol]
    price = level - slip if pos.up else level + slip
    return Exit(epoch, price, "stop_loss", profit_at(pos, price))


def check_bar(pos: Position, epoch: int, o: float, h: float, low: float, c: float) -> Exit | None:
    """Did this 1m candle close the trade? SL/stop out beat TP inside one candle."""
    sign = 1 if pos.up else -1
    worst = low if pos.up else h            # adverse extreme
    best = h if pos.up else low             # favourable extreme
    beyond = lambda price, level: sign * (price - level) <= 0   # at or past an adverse level
    reached = lambda price, level: sign * (price - level) >= 0  # at or past a favourable level
    # 1) gap at the open
    if pos.sl_price is not None and beyond(o, pos.sl_price):
        return _sl_exit(pos, epoch, o)
    if beyond(o, pos.stop_out):
        return Exit(epoch, pos.stop_out, "stop_out", -pos.stake)
    if pos.tp_price is not None and reached(o, pos.tp_price):
        return Exit(epoch, pos.tp_price, "take_profit", pos.tp_amount)
    # 2) inside the candle: adverse first
    if pos.sl_price is not None and beyond(worst, pos.sl_price):
        return _sl_exit(pos, epoch, pos.sl_price)
    if beyond(worst, pos.stop_out):
        return Exit(epoch, pos.stop_out, "stop_out", -pos.stake)
    if pos.tp_price is not None and reached(best, pos.tp_price):
        return Exit(epoch, pos.tp_price, "take_profit", pos.tp_amount)
    return None


def close_at(pos: Position, epoch: int, mid: float, reason: str) -> Exit:
    """Manual or forced close at the mid price."""
    return Exit(epoch, mid, reason, profit_at(pos, mid))
