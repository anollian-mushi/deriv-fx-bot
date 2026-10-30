"""Synthetic market data for engine tests (trading hours only)."""

import datetime as dt

import numpy as np

from fxbot import sessions
from fxbot.backtest.candles import Bars, aggregate


def synthetic_m1(start: dt.date, days: int, seed: int = 1, price: float = 1.10,
                 vol: float = 0.00008) -> Bars:
    rng = np.random.default_rng(seed)
    epochs = []
    d = start
    for _ in range(days):
        if sessions.is_trading_day(d):
            s0 = sessions.day_start(d)
            epochs.extend(e for e in range(s0, s0 + 86400, 60) if sessions.market_open(e))
        d += dt.timedelta(days=1)
    e = np.array(epochs, dtype=np.int64)
    closes = price + np.cumsum(rng.normal(0, vol, len(e)))
    opens = np.r_[price, closes[:-1]]
    highs = np.maximum(opens, closes) + vol / 2
    lows = np.minimum(opens, closes) - vol / 2
    return Bars(e, e + 60, opens, highs, lows, closes)


def data_for(symbols, timeframe, start, days, **kw):
    out = {}
    for i, s in enumerate(symbols):
        m1 = synthetic_m1(start, days, seed=kw.get("seed", 1) + i,
                          price=150.0 if s == "frxUSDJPY" else 1.10,
                          vol=0.008 if s == "frxUSDJPY" else 0.00008)
        out[s] = (m1, aggregate(m1, timeframe))
    return out
