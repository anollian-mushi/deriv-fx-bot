"""Market features for the perfect-fit experiment, from closed 1h candles only.

The same function feeds model training (research) and the live strategy, so
both see identical numbers. It reads only the candles it is handed (the engine
and the live bot pass closed candles up to now), never anything later.

No calendar-date features (year, month, day number): they could only memorise
past dates and say nothing about new ones. Hour of day and weekday are allowed.
"""

from __future__ import annotations

import numpy as np

from fxbot.backtest.candles import Bars

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
DAY, HOUR = 86400, 3600
TAIL = 600                       # 1h candles read per call (about 25 trading days)
MIN_BARS = 260

RET_LAGS = (1, 2, 3, 4, 6, 8, 12, 24, 48, 120)
RANGE_LENS = (12, 24, 72, 240)
SMA_LENS = (10, 24, 50, 100, 200)
PEER_LAGS = (1, 4, 24)

FEATURE_NAMES = (
    ["sym", "hour", "weekday", "atr14_pips", "atr_ratio", "rsi14", "body", "upper_wick", "lower_wick",
     "today_ret", "today_range_pos", "prevday_range_pos", "prevday_ret", "d5_ret", "d20_ret"]
    + [f"ret_{n}" for n in RET_LAGS]
    + [f"rng_pos_{n}" for n in RANGE_LENS]
    + [f"sma_dist_{n}" for n in SMA_LENS]
    + [f"peer{k}_ret_{n}" for k in (1, 2) for n in PEER_LAGS]
)


def _rsi(close: np.ndarray, n: int = 14) -> float:
    d = np.diff(close[-n - 1:])
    up, dn = d[d > 0].sum(), -d[d < 0].sum()
    return 50.0 if up + dn == 0 else 100.0 * up / (up + dn)


def _atr(h, low, c, n):
    pc = c[-n - 1:-1]
    tr = np.maximum(h[-n:] - low[-n:], np.maximum(np.abs(h[-n:] - pc), np.abs(low[-n:] - pc)))
    return float(tr.mean())


def _peer_rets(p: Bars | None, t: int) -> list[float]:
    if p is None or len(p) < 30 or int(p.end[-1]) < t - 3 * HOUR:
        return [0.0] * len(PEER_LAGS)
    c = p.close
    a = _atr(p.high, p.low, c, 24) or 1e-12
    return [float((c[-1] - c[-1 - n]) / a) for n in PEER_LAGS]


def features(symbol: str, c: Bars, peers: dict | None = None) -> np.ndarray | None:
    """Feature vector at the close of the last candle in c (None if not enough history)."""
    if len(c) < MIN_BARS:
        return None
    n = min(len(c), TAIL)
    end, h, low, cl, op = c.end[-n:], c.high[-n:], c.low[-n:], c.close[-n:], c.open[-n:]
    t = int(end[-1])
    pip = PIP[symbol]
    a14 = _atr(h, low, cl, 14)
    a24 = _atr(h, low, cl, 24) or 1e-12
    a100 = _atr(h, low, cl, 100) or 1e-12
    rng = (h[-1] - low[-1]) or 1e-12
    # day structure (UTC days; a candle belongs to the day of its start)
    day = (end - 1) // DAY
    today = day == day[-1] if t % DAY else day == day[-1] + 1     # empty if the day just closed
    last = np.r_[day[1:] != day[:-1], True]
    dclose = cl[last]
    if t % DAY:
        dclose_done, cur_day = dclose[:-1], day[-1]
    else:
        dclose_done, cur_day = dclose, day[-1] + 1
    prev = day == cur_day - 1
    k = 1
    while not prev.any() and k < 5:                      # skip weekends
        k += 1
        prev = day == cur_day - k
    if today.any():
        t_open = op[today][0]
        t_hi, t_lo = h[today].max(), low[today].min()
        today_ret = (cl[-1] - t_open) / a24
        today_pos = (cl[-1] - t_lo) / ((t_hi - t_lo) or 1e-12)
    else:
        today_ret, today_pos = 0.0, 0.5
    if prev.any():
        p_hi, p_lo = h[prev].max(), low[prev].min()
        prev_pos = (cl[-1] - p_lo) / ((p_hi - p_lo) or 1e-12)
        prev_ret = (cl[prev][-1] - op[prev][0]) / a24
    else:
        prev_pos, prev_ret = 0.5, 0.0
    d5 = (cl[-1] - dclose_done[-6]) / a24 if len(dclose_done) >= 6 else 0.0
    d20 = (cl[-1] - dclose_done[-21]) / a24 if len(dclose_done) >= 21 else 0.0
    peers = peers or {}
    others = [s for s in SYMBOLS if s != symbol]
    f = [SYMBOLS.index(symbol), (t % DAY) // HOUR, ((t - 1) // DAY + 3) % 7, a14 / pip, a14 / a100,
         _rsi(cl), (cl[-1] - op[-1]) / rng, (h[-1] - max(cl[-1], op[-1])) / rng,
         (min(cl[-1], op[-1]) - low[-1]) / rng, today_ret, today_pos, prev_pos, prev_ret, d5, d20]
    f += [(cl[-1] - cl[-1 - m]) / a24 for m in RET_LAGS]
    for m in RANGE_LENS:
        hh, ll = h[-m:].max(), low[-m:].min()
        f.append((cl[-1] - ll) / ((hh - ll) or 1e-12))
    f += [(cl[-1] - cl[-m:].mean()) / a24 for m in SMA_LENS]
    for s in others:
        f += _peer_rets(peers.get(s), t)
    return np.asarray(f, dtype=np.float64)
