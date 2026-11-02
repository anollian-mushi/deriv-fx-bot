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

Intraday timeframes (1m, 5m, 15m; owner's research exception for the TJR test,
2 Nov 2026) wait at most 2 minutes: an intraday setup is worth taking only at
once, so a signal that cannot fill at the next minute (or the one after, if a
quiet minute has no candle) is dropped, not delayed.

Optional Enter fields (all off by default, so older strategies are unchanged):
- min_stop_cost_multiple: skip the trade at fill time if the stop is closer
  than this many times the cost per trade (commission at the fill hour's
  measured rate + 0.5 pip entry slippage, in pips). Owner's TJR cost rule: 4.
- require_stop: skip the trade if its stop loss would lie at or beyond Deriv's
  stop out (then the stop would never be the real exit).
- move_stop_at_r: once price has moved this many times the stop distance in the
  trade's favour, move the stop loss to near break-even with Deriv's stop-loss
  update (contract_update): the smallest stop Deriv accepts, commission +
  0.02 USD. Takes effect from the next minute.
"""

from __future__ import annotations

from dataclasses import dataclass

from fxbot.backtest.candles import Bars


MAX_WAIT_HOURS = {"1m": 2 / 60, "5m": 2 / 60, "15m": 2 / 60, "1h": 1.0, "4h": 4.0, "1d": 12.0}


def max_wait_seconds(strategy: "Strategy") -> int:
    """Fixed maximum wait for a delayed signal, by the strategy's timeframe."""
    if hasattr(strategy, "max_wait_hours"):
        raise ValueError("the signal wait is fixed by timeframe (MAX_WAIT_HOURS); "
                         "strategies may not set max_wait_hours")
    if strategy.timeframe not in MAX_WAIT_HOURS:
        raise ValueError(f"timeframe must be one of {sorted(MAX_WAIT_HOURS)}")
    return int(round(MAX_WAIT_HOURS[strategy.timeframe] * 3600))


@dataclass(frozen=True)
class Enter:
    direction: str                      # MULTUP or MULTDOWN
    multiplier: int = 100
    stop_loss_pips: float | None = None
    take_profit_pips: float | None = None
    risk_fraction: float = 0.03
    min_stop_cost_multiple: float | None = None
    require_stop: bool = False
    move_stop_at_r: float | None = None


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
    timeframe = "1h"                    # 1h, 4h or 1d (CLAUDE.md); 1m/5m/15m only for the TJR research exception
    params: dict = {}
    # A strategy that compares pairs sets needs_peers; before each call the caller (backtester
    # or live bot) sets self.peers = {other symbol: its candles closed by this candle's end}.
    needs_peers = False
    peers: dict = {}

    def on_candle(self, symbol: str, candles: Bars, position: PositionView | None,
                  pending: bool) -> list[Action]:
        raise NotImplementedError
