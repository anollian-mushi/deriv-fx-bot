"""Strategy interface, shared by the backtester and the live bot.

A strategy never places orders. It is called once each time one of its
candles has closed, sees only closed candles (a read-only slice), and
returns actions. The engine passes Enter actions to the risk module
(fxbot.risk), which alone can approve a trade.

A signal that cannot be filled at once (outside the entry window, cost gate,
daily pause, weekend, position limits...) waits and fills at the open of the
first allowed minute, unless the strategy cancels it or `max_wait_hours`
passes (default 12 hours).
"""

from __future__ import annotations

from dataclasses import dataclass

from fxbot.backtest.candles import Bars


@dataclass(frozen=True)
class Enter:
    direction: str                      # MULTUP or MULTDOWN
    multiplier: int = 100
    stop_loss_pips: float | None = None
    take_profit_pips: float | None = None
    risk_fraction: float = 0.03


@dataclass(frozen=True)
class ExitPosition:
    pass


@dataclass(frozen=True)
class CancelPending:
    pass


Action = Enter | ExitPosition | CancelPending


@dataclass(frozen=True)
class PositionView:
    """What a strategy may know about its open trade."""
    direction: str
    multiplier: int
    entry: float
    entry_epoch: int


class Strategy:
    name = "base"
    timeframe = "1h"                    # 1h, 4h or 1d (CLAUDE.md)
    max_wait_hours = 12.0
    params: dict = {}

    def on_candle(self, symbol: str, candles: Bars, position: PositionView | None,
                  pending: bool) -> list[Action]:
        raise NotImplementedError
