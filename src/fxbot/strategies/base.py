"""Strategy interface, shared by the backtester and the live bot.

A strategy never places orders. It is called once each time one of its
candles has closed, sees only closed candles (a read-only slice), and
returns actions. The engine passes Enter actions to the risk module
(fxbot.risk), which alone can approve a trade.

A signal that cannot be filled at once (outside the entry window, cost gate,
daily pause, weekend, position limits...) waits and fills at the open of the
first allowed minute, unless the strategy cancels it or the fixed maximum
wait for its timeframe passes (MAX_WAIT_HOURS: 1h -> 1 hour, 4h -> 4 hours,
daily -> 12 hours). The wait is not a tunable parameter: a strategy may not
set its own.
"""

from __future__ import annotations

from dataclasses import dataclass

from fxbot.backtest.candles import Bars


MAX_WAIT_HOURS = {"1h": 1.0, "4h": 4.0, "1d": 12.0}


def max_wait_seconds(strategy: "Strategy") -> int:
    """Fixed maximum wait for a delayed signal, by the strategy's timeframe."""
    if hasattr(strategy, "max_wait_hours"):
        raise ValueError("the signal wait is fixed by timeframe (MAX_WAIT_HOURS); "
                         "strategies may not set max_wait_hours")
    if strategy.timeframe not in MAX_WAIT_HOURS:
        raise ValueError(f"timeframe must be one of {sorted(MAX_WAIT_HOURS)}")
    return int(MAX_WAIT_HOURS[strategy.timeframe] * 3600)


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
    params: dict = {}

    def on_candle(self, symbol: str, candles: Bars, position: PositionView | None,
                  pending: bool) -> list[Action]:
        raise NotImplementedError
