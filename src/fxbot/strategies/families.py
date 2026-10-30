"""Phase 4 strategy families (approved by the owner, 30 Oct 2026).

Every family has the same shape, so the luck check can swap only the entry:
- direction(): the entry idea -> "MULTUP", "MULTDOWN" or None
- stops(): stop loss / take profit in pips for a trade opened now (may say
  "no trade" by returning None, e.g. no London box today)
- exit_now(): price- or time-based exits that do not depend on the entry idea

Fixed for every family (not tunable): x100, 3% stake, one trade per pair at a
time, a new signal only when flat and nothing pending. The engine and risk
module add the entry window, cost gate, fixed signal wait, Friday close and
all hard limits. A strategy sees closed candles only and keeps no state, so
the same code gives the same answer in the backtester and the live bot.

Each family has at most 5 tunable parameters (CLAUDE.md).
"""

from __future__ import annotations

import numpy as np

from fxbot.backtest.candles import Bars
from fxbot.strategies.base import Enter, ExitPosition, PositionView, Strategy

PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
DAY = 86400
HOUR = 3600


def atr(c: Bars, n: int = 14) -> float | None:
    """Average true range of the last n candles (simple mean)."""
    if len(c) < n + 1:
        return None
    h, low, pc = c.high[-n:], c.low[-n:], c.close[-n - 1:-1]
    tr = np.maximum(h - low, np.maximum(np.abs(h - pc), np.abs(low - pc)))
    return float(tr.mean())


def hour_of(epoch: int) -> int:
    return int(epoch % DAY) // HOUR


def daily_closes(c: Bars, tail_days: int) -> np.ndarray:
    """Closes of completed UTC days, built from intraday candles (last tail_days)."""
    n = min(len(c), (tail_days + 2) * 24)
    end, close = c.end[-n:], c.close[-n:]
    day = (end - 1) // DAY                     # the day a candle belongs to
    last = np.r_[day[1:] != day[:-1], True]    # last candle of each day
    closes = close[last]
    if (int(c.end[-1]) % DAY) != 0:            # today's day is not finished yet
        closes = closes[:-1]
    return closes[-tail_days:]


class FamilyStrategy(Strategy):
    """Shared on_candle: exits first, then a new entry only when flat."""
    name = "family"
    family = ""
    multiplier = 100
    risk_fraction = 0.03

    def __init__(self, **params):
        self.params = {**self.defaults, **params}

    defaults: dict = {}

    def direction(self, symbol: str, c: Bars) -> str | None:
        raise NotImplementedError

    def stops(self, symbol: str, c: Bars, direction: str) -> tuple[float | None, float | None] | None:
        raise NotImplementedError

    def exit_now(self, symbol: str, c: Bars, position: PositionView) -> bool:
        return False

    def entry(self, symbol: str, c: Bars) -> str | None:
        """Hook the luck check overrides; normally the family's own direction()."""
        return self.direction(symbol, c)

    def on_candle(self, symbol, candles, position, pending):
        if position is not None:
            return [ExitPosition()] if self.exit_now(symbol, candles, position) else []
        if pending:
            return []
        d = self.entry(symbol, candles)
        if d is None:
            return []
        s = self.stops(symbol, candles, d)
        if s is None:
            return []
        sl, tp = s
        return [Enter(d, multiplier=self.multiplier, stop_loss_pips=sl, take_profit_pips=tp,
                      risk_fraction=self.risk_fraction)]


# --------------------------------------------------------------------------- 1
class LondonBreakout(FamilyStrategy):
    """Family 1: London open breakout of the Asian range (1h, closed the same day).

    Box = high/low of the 1h candles from box_start to 06:00 UTC. From the
    07:00 close to `cutoff`, the first close above the box goes Up, below it
    Down (one breakout per pair per day). Stop = sl_frac x box height, target
    = tp_mult x box height. Closed at 20:00 UTC if still open.
    Fixed: boxes under 10 pips (15 on USD/JPY) are skipped (too small to
    clear costs and the 3x-commission target).
    """
    name = "f1_london_breakout"
    family = "f1"
    timeframe = "1h"
    defaults = {"box_start": 0, "cutoff": 11, "sl_frac": 1.0, "tp_mult": 1.5}
    EXIT_HOUR = 20
    MIN_BOX_PIPS = {"frxEURUSD": 10, "frxGBPUSD": 10, "frxUSDJPY": 15}

    def _today(self, c: Bars):
        t = int(c.end[-1])
        d0 = t - t % DAY if t % DAY else t - DAY
        n = min(len(c), 30)
        sel = slice(len(c) - n, len(c))
        return t, d0, c.epoch[sel], c.end[sel], c.high[sel], c.low[sel], c.close[sel]

    def _box(self, symbol, c: Bars):
        t, d0, ep, end, hi, lo, cl = self._today(c)
        start = d0 + self.params["box_start"] * HOUR
        inbox = (ep >= start) & (end <= d0 + 6 * HOUR)
        if inbox.sum() < (6 - self.params["box_start"]) * 0.75:     # gaps (Monday open, missing data)
            return None
        return float(hi[inbox].max()), float(lo[inbox].min()), d0, ep, end, cl

    def direction(self, symbol, c):
        t = int(c.end[-1])
        h = hour_of(t)
        if not 7 <= h <= self.params["cutoff"] or t % DAY == 0:
            return None
        box = self._box(symbol, c)
        if box is None:
            return None
        top, bot, d0, ep, end, cl = box
        if (top - bot) / PIP[symbol] < self.MIN_BOX_PIPS[symbol]:
            return None
        after = (ep >= d0 + 6 * HOUR) & (end < t)          # earlier candles today after the box
        if np.any(cl[after] > top) or np.any(cl[after] < bot):
            return None                                     # already broke out today
        if cl[-1] > top:
            return "MULTUP"
        if cl[-1] < bot:
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        box = self._box(symbol, c)
        if box is None:
            return None
        height = (box[0] - box[1]) / PIP[symbol]
        if height < self.MIN_BOX_PIPS[symbol]:
            return None
        return self.params["sl_frac"] * height, self.params["tp_mult"] * height

    def exit_now(self, symbol, c, position):
        t = int(c.end[-1])
        e = position.entry_epoch
        return t >= e - e % DAY + self.EXIT_HOUR * HOUR


# --------------------------------------------------------------------------- 2
class TrendBreakout(FamilyStrategy):
    """Family 2: multi-day trend breakout (Donchian channel), 4h or daily.

    Close above the highest high of the previous `n` candles goes Up; below
    the lowest low goes Down. Stop = sl_atr x ATR(14). No target: a trailing
    exit closes the trade when a candle closes beyond the opposite `m`-candle
    channel. The engine closes everything by Friday 20:30.
    """
    name = "f2_trend_breakout"
    family = "f2"
    timeframe = "4h"
    defaults = {"n": 55, "sl_atr": 2.5, "m": 20}

    def direction(self, symbol, c):
        n = self.params["n"]
        if len(c) < n + 1:
            return None
        if c.close[-1] > c.high[-n - 1:-1].max():
            return "MULTUP"
        if c.close[-1] < c.low[-n - 1:-1].min():
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        a = atr(c)
        return None if a is None else (self.params["sl_atr"] * a / PIP[symbol], None)

    def exit_now(self, symbol, c, position):
        m = self.params["m"]
        if len(c) < m + 1:
            return False
        if position.direction == "MULTUP":
            return bool(c.close[-1] < c.low[-m - 1:-1].min())
        return bool(c.close[-1] > c.high[-m - 1:-1].max())


class TrendBreakout1d(TrendBreakout):
    name = "f2_trend_breakout_1d"
    timeframe = "1d"
    defaults = {"n": 20, "sl_atr": 1.0, "m": 10}


# --------------------------------------------------------------------------- 3
class TrendPullback(FamilyStrategy):
    """Family 3: buy the dip in a daily trend (1h or 4h entries).

    Trend: the last completed daily close is above (below) its `trend_len`-day
    average -> only Up (Down) trades. Entry: RSI(3) on the entry timeframe
    falls below `pullback` (rises above 100 - pullback), i.e. a short dip
    against the trend. Stop = sl_atr x ATR(14) of the entry timeframe; target
    = tp_r x the stop. Fixed time limit: 24 candles on 1h, 30 on 4h.
    """
    name = "f3_trend_pullback"
    family = "f3"
    timeframe = "4h"
    defaults = {"trend_len": 50, "pullback": 20, "sl_atr": 2.0, "tp_r": 2.0}
    MAX_HOLD = {"1h": 24 * HOUR, "4h": 30 * 4 * HOUR}

    @staticmethod
    def rsi(close: np.ndarray, n: int = 3) -> float | None:
        if len(close) < n * 5 + 1:
            return None
        d = np.diff(close[-(n * 5 + 1):])
        up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
        a = 1 / n                                  # Wilder smoothing over a short warm-up
        au, ad = up[:n].mean(), dn[:n].mean()
        for u, w in zip(up[n:], dn[n:]):
            au, ad = au + a * (u - au), ad + a * (w - ad)
        if ad == 0:
            return 100.0
        return float(100 - 100 / (1 + au / ad))

    def direction(self, symbol, c):
        L = self.params["trend_len"]
        days = daily_closes(c, L + 1)
        if len(days) < L:
            return None
        trend_up = days[-1] > days[-L:].mean()
        r = self.rsi(c.close)
        if r is None:
            return None
        pb = self.params["pullback"]
        if trend_up and r < pb:
            return "MULTUP"
        if not trend_up and r > 100 - pb:
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        a = atr(c)
        if a is None:
            return None
        sl = self.params["sl_atr"] * a / PIP[symbol]
        return sl, self.params["tp_r"] * sl

    def exit_now(self, symbol, c, position):
        return int(c.end[-1]) - position.entry_epoch >= self.MAX_HOLD[self.timeframe]


class TrendPullback1h(TrendPullback):
    name = "f3_trend_pullback_1h"
    timeframe = "1h"


# --------------------------------------------------------------------------- 4
class MeanReversion(FamilyStrategy):
    """Family 4: short-term mean reversion in calm markets (1h or 4h).

    Stretch = (close - SMA(length)) / ATR(14). Stretch <= -stretch goes Up,
    >= +stretch goes Down, but only when the market is calm: the efficiency
    ratio over the last 3 x length candles (net move / total path) is below
    er_max. Target = the distance back to the average at entry; stop =
    sl_atr x ATR(14). Fixed time limit: 24 candles on 1h, 12 on 4h.
    """
    name = "f4_mean_reversion"
    family = "f4"
    timeframe = "1h"
    defaults = {"length": 20, "stretch": 2.0, "er_max": 0.3, "sl_atr": 2.0}
    MAX_HOLD = {"1h": 24 * HOUR, "4h": 12 * 4 * HOUR}

    def _calc(self, c: Bars):
        L = self.params["length"]
        if len(c) < 3 * L + 1:
            return None
        a = atr(c)
        if not a:
            return None
        sma = float(c.close[-L:].mean())
        path = c.close[-3 * L - 1:]
        er = abs(path[-1] - path[0]) / max(np.abs(np.diff(path)).sum(), 1e-12)
        return sma, a, er

    def direction(self, symbol, c):
        k = self._calc(c)
        if k is None:
            return None
        sma, a, er = k
        if er >= self.params["er_max"]:
            return None
        z = (c.close[-1] - sma) / a
        if z <= -self.params["stretch"]:
            return "MULTUP"
        if z >= self.params["stretch"]:
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        k = self._calc(c)
        if k is None:
            return None
        sma, a, _ = k
        return self.params["sl_atr"] * a / PIP[symbol], abs(c.close[-1] - sma) / PIP[symbol]

    def exit_now(self, symbol, c, position):
        return int(c.end[-1]) - position.entry_epoch >= self.MAX_HOLD[self.timeframe]


class MeanReversion4h(MeanReversion):
    name = "f4_mean_reversion_4h"
    timeframe = "4h"


# --------------------------------------------------------------------------- 5
class SessionDrift(FamilyStrategy):
    """Family 5: time-of-day drift (1h, fixed clock times).

    Directions are fixed in advance from published research, not from our
    data (sources in research/log.md): a currency tends to weaken during its
    own country's working hours and strengthen outside them (Ranaldo 2009;
    Breedon and Ranaldo 2013).
    - European-only hours (entry 06:00-11:59 UTC): EUR and GBP local -> Down
      on EUR/USD and GBP/USD. USD/JPY: neither currency local -> no trade.
    - US-only hours (entry 16:00-17:59 UTC, after the London close): USD
      local -> Up on EUR/USD and GBP/USD, Down on USD/JPY.
    - 12:00-15:59 (Europe and US both open): no direction, no trade.
    Tunable: entry hour, exit hour, optional stop (pips; 0 = none).
    """
    name = "f5_session_drift"
    family = "f5"
    timeframe = "1h"
    defaults = {"entry_hour": 8, "exit_hour": 12, "stop_pips": 0}
    EUROPE = {"frxEURUSD": "MULTDOWN", "frxGBPUSD": "MULTDOWN", "frxUSDJPY": None}
    US = {"frxEURUSD": "MULTUP", "frxGBPUSD": "MULTUP", "frxUSDJPY": "MULTDOWN"}

    @classmethod
    def session_direction(cls, symbol: str, hour: int) -> str | None:
        if 6 <= hour <= 11:
            return cls.EUROPE[symbol]
        if 16 <= hour <= 17:
            return cls.US[symbol]
        return None

    def direction(self, symbol, c):
        t = int(c.end[-1])
        h = self.params["entry_hour"]
        if t % HOUR or hour_of(t) != h:
            return None
        return self.session_direction(symbol, h)

    def stops(self, symbol, c, direction):
        s = self.params["stop_pips"]
        return (s * (1.5 if symbol == "frxUSDJPY" else 1.0) if s else None), None

    def exit_now(self, symbol, c, position):
        t = int(c.end[-1])
        e = position.entry_epoch
        return t >= e - e % DAY + self.params["exit_hour"] * HOUR


# =========================================================================== Round 2
# Designed 30 Oct 2026 from what failed in round 1 (reports/strategy_research.md):
# - 1h strategies with ~1,000 trades were eaten by the ~3-pip commission; the
#   nearest misses held longer and won bigger. -> fewer trades, wider targets.
# - The London breakout was the only entry that beat random entries, but its
#   moves were too small. -> trade it only after a quiet Asian session, with a
#   target sized on the daily range (family 6).
# - Fading stretched moves and fading the session did worse than random: short-
#   term moves tended to continue. -> follow a strong morning move (family 8).
# - Breakouts of multi-day highs failed and the Friday close cuts trends. ->
#   one trade per week, Monday to Friday, in the direction of the past months
#   (family 7; time-series momentum, Moskowitz, Ooi and Pedersen 2012).

def daily_ranges(c: Bars, days: int) -> np.ndarray:
    """High-low range of the last `days` completed UTC days, from intraday candles."""
    n = min(len(c), (days + 2) * 24)
    end, hi, lo = c.end[-n:], c.high[-n:], c.low[-n:]
    day = (end - 1) // DAY
    starts = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1]
    rng = np.maximum.reduceat(hi, starts) - np.minimum.reduceat(lo, starts)
    if int(c.end[-1]) % DAY != 0:
        rng = rng[:-1]
    return rng[-days:]


def daily_atr(c: Bars, days: int = 14) -> float | None:
    r = daily_ranges(c, days)
    return float(r.mean()) if len(r) == days else None


class QuietLondonBreakout(LondonBreakout):
    """Family 6: London breakout only after a quiet Asian session, wide target.

    Same box (00:00-06:00 UTC) and entry as family 1, with entries until the
    10:00 close (both fixed from round 1). New: trade only when the box is at
    most box_max x the average daily range of the last 14 days (a quiet night,
    so the day's range is still ahead); target = tp_atr x that daily range;
    stop = sl_frac x the box. Closed at 20:00 UTC.
    """
    name = "f6_quiet_london_breakout"
    family = "f6"
    defaults = {"box_max": 0.4, "tp_atr": 0.8, "sl_frac": 1.0, "box_start": 0, "cutoff": 10}

    def _quiet(self, symbol, c) -> tuple[float, float] | None:
        box = self._box(symbol, c)
        a = daily_atr(c)
        if box is None or a is None:
            return None
        height = box[0] - box[1]
        if height / PIP[symbol] < self.MIN_BOX_PIPS[symbol] or height > self.params["box_max"] * a:
            return None
        return height / PIP[symbol], a / PIP[symbol]

    def direction(self, symbol, c):
        return super().direction(symbol, c) if self._quiet(symbol, c) else None

    def stops(self, symbol, c, direction):
        q = self._quiet(symbol, c)
        if q is None:
            return None
        height, a = q
        return self.params["sl_frac"] * height, self.params["tp_atr"] * a


class WeeklyMomentum(FamilyStrategy):
    """Family 7: weekly time-series momentum (daily candles).

    When Friday's daily candle closes (seen Monday 00:00, filled at 06:00),
    go Up if the close is above the close `lookback` trading days earlier,
    else Down. Held all week; the engine closes it Friday 20:30. Stop =
    sl_atr x the 14-day average range (0 = no stop: the stop out caps the
    loss at the stake). No target.
    """
    name = "f7_weekly_momentum"
    family = "f7"
    timeframe = "1d"
    warmup_days = 200
    defaults = {"lookback": 60, "sl_atr": 0}

    def direction(self, symbol, c):
        t = int(c.end[-1])
        L = self.params["lookback"]
        # Friday's candle ends Saturday 00:00 UTC (weekday 5).
        if t % DAY or ((t // DAY) + 3) % 7 != 5 or len(c) < L + 1:
            return None
        return "MULTUP" if c.close[-1] > c.close[-1 - L] else "MULTDOWN"

    def stops(self, symbol, c, direction):
        k = self.params["sl_atr"]
        if not k:
            return None, None
        a = atr(c)
        return None if a is None else (k * a / PIP[symbol], None)


class MorningMomentum(FamilyStrategy):
    """Family 8: follow a strong morning move (1h).

    At the close of the `entry_hour` candle, if price has moved at least
    k x the 14-day average daily range since the day's open (00:00 UTC),
    trade in the same direction. Stop = sl_frac x that morning move (at least
    10 pips, 15 on USD/JPY); no target; closed at 20:00 UTC.
    """
    name = "f8_morning_momentum"
    family = "f8"
    timeframe = "1h"
    defaults = {"entry_hour": 10, "k": 0.3, "sl_frac": 0.5}
    EXIT_HOUR = 20
    MIN_SL = {"frxEURUSD": 10, "frxGBPUSD": 10, "frxUSDJPY": 15}

    def _move(self, symbol, c) -> tuple[float, float] | None:
        t = int(c.end[-1])
        if t % HOUR or hour_of(t) != self.params["entry_hour"]:
            return None
        d0 = t - t % DAY
        n = min(len(c), 30)
        today = c.epoch[-n:] >= d0
        if today.sum() < self.params["entry_hour"] * 0.75:
            return None
        a = daily_atr(c)
        if a is None:
            return None
        move = float(c.close[-1] - c.open[-n:][today][0])
        return move, a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m[0]) < self.params["k"] * m[1]:
            return None
        return "MULTUP" if m[0] > 0 else "MULTDOWN"

    def stops(self, symbol, c, direction):
        m = self._move(symbol, c)
        if m is None:
            return None
        return max(self.params["sl_frac"] * abs(m[0]) / PIP[symbol], self.MIN_SL[symbol]), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.EXIT_HOUR * HOUR


REGISTRY = {cls.name: cls for cls in (LondonBreakout, TrendBreakout, TrendBreakout1d, TrendPullback,
                                     TrendPullback1h, MeanReversion, MeanReversion4h, SessionDrift,
                                     QuietLondonBreakout, WeeklyMomentum, MorningMomentum)}
