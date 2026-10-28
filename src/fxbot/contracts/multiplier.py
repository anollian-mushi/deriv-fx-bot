"""Deriv Multiplier contract math (see docs/deriv_api_notes.md, section 5).

Plain-language summary:
- A trade with stake S and multiplier M behaves like a position of S x M.
- Commission is charged once, at the start: rate x S x M.
- Profit = S x M x (price change / entry price) - commission, with the sign of
  the price change flipped for Down (MULTDOWN) trades.
- Take profit, stop loss and stop out are all set as profit amounts in USD,
  after commission: take profit at +TP, stop loss at -SL, stop out at -S
  (the whole stake is lost).

Used by both the backtester and the live bot, so they agree on every price.
"""

from __future__ import annotations

import math
from typing import Literal

Direction = Literal["MULTUP", "MULTDOWN"]


def _sign(direction: Direction) -> int:
    if direction == "MULTUP":
        return 1
    if direction == "MULTDOWN":
        return -1
    raise ValueError(f"unknown direction {direction!r}")


def position_size(stake: float, multiplier: float) -> float:
    return stake * multiplier


def commission(stake: float, multiplier: float, rate: float) -> float:
    """Commission in USD. rate is a fraction, e.g. 0.0002 for 0.02%."""
    return rate * position_size(stake, multiplier)


def profit(
    direction: Direction, stake: float, multiplier: float, entry: float, exit_price: float,
    commission_usd: float,
) -> float:
    """Profit in USD at exit_price, after commission. Never below -stake."""
    move = _sign(direction) * (exit_price - entry) / entry
    return max(position_size(stake, multiplier) * move - commission_usd, -stake)


def price_at_profit(
    direction: Direction, stake: float, multiplier: float, entry: float, target: float,
    commission_usd: float,
) -> float:
    """Exit price where profit (after commission) equals target USD.

    target > 0: take profit level. target < 0: stop loss level.
    target = -stake: stop out level.
    """
    move = (target + commission_usd) / position_size(stake, multiplier)
    return entry * (1 + _sign(direction) * move)


def stop_out_price(
    direction: Direction, stake: float, multiplier: float, entry: float, commission_usd: float
) -> float:
    return price_at_profit(direction, stake, multiplier, entry, -stake, commission_usd)


def take_profit_price(
    direction: Direction, stake: float, multiplier: float, entry: float, take_profit: float,
    commission_usd: float,
) -> float:
    return price_at_profit(direction, stake, multiplier, entry, take_profit, commission_usd)


def stop_loss_price(
    direction: Direction, stake: float, multiplier: float, entry: float, stop_loss: float,
    commission_usd: float,
) -> float:
    return price_at_profit(direction, stake, multiplier, entry, -stop_loss, commission_usd)


def stop_out_move(stake: float, multiplier: float, commission_usd: float) -> float:
    """Adverse price move (fraction of entry) that stops the trade out."""
    return (stake - commission_usd) / position_size(stake, multiplier)


def round_price(price: float, pip_size: float, mode: Literal["nearest", "up", "down"] = "nearest") -> float:
    """Round a price to the symbol's pip size (e.g. 0.00001 for EUR/USD)."""
    steps = price / pip_size
    # Guard against float noise like 112540.99999999 before ceil/floor.
    steps = round(steps, 6)
    if mode == "nearest":
        n = math.floor(steps + 0.5)
    elif mode == "up":
        n = math.ceil(steps)
    elif mode == "down":
        n = math.floor(steps)
    else:
        raise ValueError(f"unknown rounding mode {mode!r}")
    decimals = max(0, -int(math.floor(math.log10(pip_size))))
    return round(n * pip_size, decimals)
