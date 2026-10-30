"""ENGINE TEST ONLY, NOT FOR TRADING.

A plain moving-average cross used to show the backtester works end to end.
It was not researched, tuned or validated, and must never be traded.

Rules (fixed, no tuning): on each closed 1h candle, if the 20-candle simple
average crosses above the 50-candle average, go Up; if it crosses below, go
Down. An open trade in the other direction is closed first. x100, 3% stake,
no stop loss or take profit (the stop out protects the stake). Signals wait
up to the fixed 1 hour (1h timeframe) for an allowed minute.
"""

from __future__ import annotations

from fxbot.strategies.base import Enter, ExitPosition, Strategy


class MaCrossExample(Strategy):
    name = "ma_cross_example"
    label = "ENGINE TEST ONLY, NOT FOR TRADING"
    timeframe = "1h"
    params = {"fast": 20, "slow": 50}

    def on_candle(self, symbol, candles, position, pending):
        fast, slow = self.params["fast"], self.params["slow"]
        c = candles.close
        if len(c) < slow + 1:
            return []
        f_now, s_now = c[-fast:].mean(), c[-slow:].mean()
        f_prev, s_prev = c[-fast - 1:-1].mean(), c[-slow - 1:-1].mean()
        if f_prev <= s_prev and f_now > s_now:
            want = "MULTUP"
        elif f_prev >= s_prev and f_now < s_now:
            want = "MULTDOWN"
        else:
            return []
        actions = []
        if position is not None:
            if position.direction == want:
                return []
            actions.append(ExitPosition())
        actions.append(Enter(want, multiplier=100))
        return actions
