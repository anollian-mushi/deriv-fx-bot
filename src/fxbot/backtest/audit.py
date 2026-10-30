"""Diagnostics for auditing the research pipeline (Phase 4 audit, 30 Oct 2026).

NOTHING here is a trading strategy. These are positive controls: they prove
the backtester and the luck check can see an edge when one exists, and they
let a result be re-priced without costs. They are never registered in
fxbot.strategies.families.REGISTRY and must never be run live.
"""

from __future__ import annotations

import contextlib

import numpy as np

from fxbot.backtest import fills
from fxbot.backtest.candles import Bars
from fxbot.contracts import multiplier as mc
from fxbot.strategies import families as F
from fxbot.strategies.base import Enter, ExitPosition, Strategy

PIP = fills.PIP


class Cheat(Strategy):
    """DIAGNOSTIC ONLY: looks at the NEXT candle's close (look-ahead) and trades its
    direction when the move is at least `min_pips`, holding one candle.

    With `rng` set it keeps the same candles and exits but picks a random direction:
    the control's own luck check. Signals only at hours where every pair fills at
    once (inside the entry window, outside the cost-gate hours), so the trade count
    does not depend on the wait rule.
    """
    name = "audit_cheat"
    timeframe = "1h"
    HOURS = {6, 7, 8, 9, 10, 11, 14, 15, 16, 17}

    def __init__(self, future: dict[str, Bars], min_pips: float = 8.0, rng=None):
        self.future, self.min_pips, self.rng = future, min_pips, rng

    def on_candle(self, symbol, candles, position, pending):
        if position is not None:
            return [ExitPosition()]
        if pending:
            return []
        t = int(candles.end[-1])
        if F.hour_of(t) not in self.HOURS:
            return []
        fut = self.future[symbol]
        i = int(np.searchsorted(fut.end, t, "right"))        # the first candle ending after t
        if i >= len(fut):
            return []
        move = (fut.close[i] - candles.close[-1]) / PIP[symbol]
        if abs(move) < self.min_pips:
            return []
        d = "MULTUP" if move > 0 else "MULTDOWN"
        if self.rng is not None:
            d = "MULTUP" if self.rng.random() < 0.5 else "MULTDOWN"
        return [Enter(d)]


class AuditDrift(F.FamilyStrategy):
    """DIAGNOSTIC ONLY: Up at the 08:00 candle close, out at 12:00, no stops. Trades a
    synthetic price that drifts up between those hours."""
    name = "audit_drift"
    family = "audit"
    timeframe = "1h"

    def direction(self, symbol, c):
        t = int(c.end[-1])
        return "MULTUP" if t % F.HOUR == 0 and F.hour_of(t) == 8 else None

    def stops(self, symbol, c, direction):
        return None, None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % F.DAY + 12 * F.HOUR


def flipped(cls: type[F.FamilyStrategy]) -> type[F.FamilyStrategy]:
    """The same family with every entry direction reversed (exits and stops unchanged)."""

    class Flipped(cls):
        name = f"{cls.name}_flipped"

        def direction(self, symbol, c):
            d = super().direction(symbol, c)
            return None if d is None else ("MULTDOWN" if d == "MULTUP" else "MULTUP")

    Flipped.__qualname__ = Flipped.__name__ = f"Flipped{cls.__name__}"
    return Flipped


def gross_of(t: dict) -> float:
    """A recorded trade's profit with every modelled cost added back: the commission, the
    0.5 pip entry slippage and, on stop-loss exits, the 1 pip stop slippage."""
    size = t["stake"] * t["multiplier"]
    slip = size * fills.ENTRY_SLIPPAGE_PIPS * PIP[t["symbol"]] / t["entry"]
    if t["reason"] == "stop_loss":
        slip += size * fills.SL_SLIPPAGE_PIPS * PIP[t["symbol"]] / t["entry"]
    return t["profit"] + t["commission"] + slip


def cost_of(t: dict) -> dict:
    size = t["stake"] * t["multiplier"]
    return {"commission": t["commission"],
            "entry_slippage": size * fills.ENTRY_SLIPPAGE_PIPS * PIP[t["symbol"]] / t["entry"],
            "sl_slippage": (size * fills.SL_SLIPPAGE_PIPS * PIP[t["symbol"]] / t["entry"]
                            if t["reason"] == "stop_loss" else 0.0)}


@contextlib.contextmanager
def no_costs():
    """Run the engine with zero commission and zero slippage (the 'before costs' result).
    The cost gate still uses the measured table, so entry timing is unchanged."""
    saved = fills.ENTRY_SLIPPAGE_PIPS, fills.SL_SLIPPAGE_PIPS, mc.commission
    fills.ENTRY_SLIPPAGE_PIPS, fills.SL_SLIPPAGE_PIPS = 0.0, 0.0
    mc.commission = lambda stake, mult, rate, minimum=0.0: 0.0
    try:
        yield
    finally:
        fills.ENTRY_SLIPPAGE_PIPS, fills.SL_SLIPPAGE_PIPS, mc.commission = saved
