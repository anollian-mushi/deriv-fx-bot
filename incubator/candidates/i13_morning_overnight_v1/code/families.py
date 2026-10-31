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

    When Monday's daily candle closes (Tuesday 00:00 UTC, filled at 06:00),
    go Up if the close is above the close `lookback` trading days earlier,
    else Down. Held to the end of the week; the engine closes it Friday
    20:30. (A first version signalled on Friday's close: under the fixed
    12-hour wait for daily signals that signal expires over the weekend, so
    it never traded. Its 9 variants still count in the running total.) Stop =
    sl_atr x the 14-day average range (0 = no stop: the stop out caps the
    loss at the stake). No target.
    """
    name = "f7_weekly_momentum_tue"
    family = "f7"
    timeframe = "1d"
    warmup_days = 200
    defaults = {"lookback": 60, "sl_atr": 0}

    def direction(self, symbol, c):
        t = int(c.end[-1])
        L = self.params["lookback"]
        # Monday's candle ends Tuesday 00:00 UTC (weekday 1).
        if t % DAY or ((t // DAY) + 3) % 7 != 1 or len(c) < L + 1:
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


# =========================================================================== Round 3
# Rounds 1-2: every single-pair price pattern had about zero edge before costs,
# so the commission made each one a loss. Round 3 tries two kinds of idea not
# yet tested: a hedged bet on two currencies against each other (family 9),
# and following unusually large daily moves, which are often news (family 10).

class EurGbpConvergence(FamilyStrategy):
    """Family 9: EUR vs GBP convergence, two hedged legs (daily candles).

    Gap = log(EUR/USD) - log(GBP/USD), i.e. EUR/GBP. z = (gap - its
    `length`-day average) / its standard deviation. z <= -z_in (EUR cheap
    against GBP): EUR/USD Up and GBP/USD Down; z >= z_in: the opposite. Both
    legs open at 06:00 the next day and close after `hold_days` days. Stop
    per leg 1.5 x the 14-day average range (fixed; usually the stop out
    comes first at x100). USD/JPY is not traded.
    """
    name = "f9_eur_gbp_convergence"
    family = "f9"
    timeframe = "1d"
    needs_peers = True
    LEGS = {"frxEURUSD": 1, "frxGBPUSD": -1}
    defaults = {"length": 20, "z_in": 2.0, "hold_days": 5}
    SL_ATR = 1.5

    def _z(self, symbol, c) -> float | None:
        other = "frxGBPUSD" if symbol == "frxEURUSD" else "frxEURUSD"
        o = self.peers.get(other)
        L = self.params["length"]
        if o is None or len(o) < L + 1 or len(c) < L + 1:
            return None
        common, ia, ib = np.intersect1d(c.end[-(L + 10):], o.end[-(L + 10):], return_indices=True)
        if len(common) < L or common[-1] != c.end[-1]:
            return None
        a = c.close[-(L + 10):][ia][-L:]
        b = o.close[-(L + 10):][ib][-L:]
        eur, gbp = (a, b) if symbol == "frxEURUSD" else (b, a)
        gap = np.log(eur) - np.log(gbp)
        sd = gap.std()
        return None if sd == 0 else float((gap[-1] - gap.mean()) / sd)

    def direction(self, symbol, c):
        if symbol not in self.LEGS:
            return None
        z = self._z(symbol, c)
        if z is None or abs(z) < self.params["z_in"]:
            return None
        eur_up = z < 0
        return "MULTUP" if eur_up == (self.LEGS[symbol] > 0) else "MULTDOWN"

    def stops(self, symbol, c, direction):
        a = atr(c)
        return None if a is None else (self.SL_ATR * a / PIP[symbol], None)

    def exit_now(self, symbol, c, position):
        return int(c.end[-1]) - position.entry_epoch >= self.params["hold_days"] * DAY - 6 * HOUR


class ShockDay(FamilyStrategy):
    """Family 10: continuation after a shock day (daily candles).

    A day whose range is at least k x the average range of the 20 days
    before it, and which closes in the top third of its range (bottom
    third), is followed by an Up (Down) trade opened at 06:00 the next day
    and closed after `hold_days` days. Stop = sl_atr x that average range.
    Fixed: the close must be in the outer third.
    """
    name = "f10_shock_day"
    family = "f10"
    timeframe = "1d"
    defaults = {"k": 1.5, "hold_days": 1, "sl_atr": 1.0}

    def _avg_range(self, c) -> float | None:
        if len(c) < 21:
            return None
        return float((c.high[-21:-1] - c.low[-21:-1]).mean())

    def direction(self, symbol, c):
        a = self._avg_range(c)
        if a is None:
            return None
        rng = c.high[-1] - c.low[-1]
        if rng < self.params["k"] * a or rng <= 0:
            return None
        loc = (c.close[-1] - c.low[-1]) / rng
        if loc >= 2 / 3:
            return "MULTUP"
        if loc <= 1 / 3:
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        a = self._avg_range(c)
        return None if a is None else (self.params["sl_atr"] * a / PIP[symbol], None)

    def exit_now(self, symbol, c, position):
        return int(c.end[-1]) - position.entry_epoch >= self.params["hold_days"] * DAY - 6 * HOUR


# =========================================================================== Round 4 (last)
# Track B, approved 30 Oct 2026. Phase 4 looked at each pair on its own. These two
# families read all three pairs at once to tell a dollar move from a move on one
# pair alone. Measurement: each pair's move since 00:00 UTC in the dollar's
# direction, as a fraction of its own 20-day average daily range.

USD_SIGN = {"frxEURUSD": -1.0, "frxGBPUSD": -1.0, "frxUSDJPY": 1.0}   # pair up = dollar down / up
ALL_PAIRS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")


def usd_moves(symbol: str, c: Bars, peers: dict, hour: int) -> dict | None:
    """{pair: move since 00:00 UTC in the dollar's direction / 20-day average daily range} for
    all three pairs at the close of the `hour` candle, or None if any pair's candle or history
    is missing."""
    t = int(c.end[-1])
    if t % DAY != hour * HOUR:
        return None
    d0 = t - hour * HOUR
    out = {}
    for s in ALL_PAIRS:
        b = c if s == symbol else peers.get(s)
        if b is None or not len(b) or int(b.end[-1]) != t:
            return None
        r = daily_atr(b, 20)
        if r is None or r <= 0:
            return None
        today = b.epoch >= d0
        if today.sum() < hour * 0.75:
            return None
        out[s] = USD_SIGN[s] * float(b.close[-1] - b.open[today][0]) / r
    return out


def _pair_direction(symbol: str, usd_up: bool) -> str:
    return "MULTUP" if usd_up == (USD_SIGN[symbol] > 0) else "MULTDOWN"


class DollarWideCatchUp(FamilyStrategy):
    """Family 11: dollar-wide move, catch-up (1h).

    At the decision hour, if all three pairs point the same way for the dollar
    and the average move is at least k daily ranges, buy the dollar on the two
    pairs that have moved least (the leader is skipped). Exit at 20:00 UTC;
    optional stop of `stop` daily ranges. Reason: a move on all three pairs at
    once is a dollar flow, not pair noise; large flows take hours to work
    through the market, and the pairs that moved least have the most left.
    """
    name = "f11_dollar_catch_up"
    family = "f11"
    timeframe = "1h"
    needs_peers = True
    defaults = {"decision_hour": 8, "k": 0.3, "stop": 0.0}
    EXIT_HOUR = 20

    def _signal(self, symbol, c) -> bool | None:
        """True = dollar up, False = dollar down, None = no trade on this pair now."""
        m = usd_moves(symbol, c, self.peers, self.params["decision_hour"])
        if m is None:
            return None
        v = np.array([m[s] for s in ALL_PAIRS])
        if not (np.all(v > 0) or np.all(v < 0)) or np.abs(v).mean() < self.params["k"]:
            return None
        leader = max(m, key=lambda s: abs(m[s]))
        if symbol == leader:
            return None
        return bool(v[0] > 0)

    def direction(self, symbol, c):
        up = self._signal(symbol, c)
        return None if up is None else _pair_direction(symbol, up)

    def stops(self, symbol, c, direction):
        if usd_moves(symbol, c, self.peers, self.params["decision_hour"]) is None:
            return None
        s = self.params["stop"]
        return (s * daily_atr(c, 20) / PIP[symbol] if s else None), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.EXIT_HOUR * HOUR


class LoneMoverReverts(FamilyStrategy):
    """Family 12: lone mover reverts (1h).

    At the decision hour, if this pair has moved at least k daily ranges in
    the dollar's direction while the other two together show the dollar
    roughly flat (their average within k/3), trade this pair back toward where
    it started. Exit at 20:00 UTC; optional stop of `stop` daily ranges.
    Reason: a move on one pair with no dollar move behind it is most often a
    single-currency order or thin-market push, which tends to be absorbed and
    partly undone. Family 9, the only Phase 4 idea with a real before-cost
    edge, worked by cancelling the dollar out; this does that intraday.
    """
    name = "f12_lone_mover_reverts"
    family = "f12"
    timeframe = "1h"
    needs_peers = True
    defaults = {"decision_hour": 8, "k": 0.3, "stop": 0.0}
    EXIT_HOUR = 20

    def direction(self, symbol, c):
        m = usd_moves(symbol, c, self.peers, self.params["decision_hour"])
        if m is None:
            return None
        own = m[symbol]
        others = np.mean([m[s] for s in ALL_PAIRS if s != symbol])
        k = self.params["k"]
        if abs(own) < k or abs(others) > k / 3:
            return None
        return _pair_direction(symbol, usd_up=own < 0)       # against the pair's own dollar move

    def stops(self, symbol, c, direction):
        if usd_moves(symbol, c, self.peers, self.params["decision_hour"]) is None:
            return None
        s = self.params["stop"]
        return (s * daily_atr(c, 20) / PIP[symbol] if s else None), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.EXIT_HOUR * HOUR



# =========================================================================== Incubator ideas (31 Oct 2026)
# New candidate ideas for the strategy incubator, each pre-screened on data before the untouched
# period (fxbot.backtest.prescreen) before registration. Every idea here was chosen for a reason
# that is not "the data said so": a market structure (a benchmark fix, the New York option cut,
# clustered stop and take-profit orders, thin-session moves, scheduled data releases) with an
# identifiable loser on the other side. The reasons are in incubator/README.md.

def _nth_sunday(year: int, month: int, n: int) -> int:
    """Day of month of the n-th Sunday (n = 1, 2) or the last Sunday (n = -1)."""
    import calendar
    sundays = [d for d in range(1, 32) if d <= calendar.monthrange(year, month)[1]
               and calendar.weekday(year, month, d) == 6]
    return sundays[n - 1] if n > 0 else sundays[-1]


def _utc(y: int, m: int, d: int, h: int) -> int:
    import datetime as _dt
    return int(_dt.datetime(y, m, d, h, tzinfo=_dt.timezone.utc).timestamp())


def london_summer(epoch: int) -> bool:
    """British Summer Time: last Sunday of March 01:00 UTC to last Sunday of October 01:00 UTC."""
    import datetime as _dt
    y = _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).year
    return _utc(y, 3, _nth_sunday(y, 3, -1), 1) <= epoch < _utc(y, 10, _nth_sunday(y, 10, -1), 1)


def new_york_summer(epoch: int) -> bool:
    """US daylight time: second Sunday of March 07:00 UTC to first Sunday of November 06:00 UTC."""
    import datetime as _dt
    y = _dt.datetime.fromtimestamp(epoch, _dt.timezone.utc).year
    return _utc(y, 3, _nth_sunday(y, 3, 2), 7) <= epoch < _utc(y, 11, _nth_sunday(y, 11, 1), 6)


def london_fix_hour(epoch: int) -> int:
    """UTC hour of the 16:00 London WM/Reuters fix on this day: 15 in summer, 16 in winter."""
    return 15 if london_summer(epoch) else 16


def ny_cut_hour(epoch: int) -> int:
    """UTC hour of the 10:00 New York option expiry cut: 14 in summer, 15 in winter."""
    return 14 if new_york_summer(epoch) else 15


def today_view(c: Bars, max_candles: int = 30):
    """(t, d0, candles since 00:00 UTC today as arrays) for a candle that closed at t inside a
    day (t % DAY != 0). Returns None at a 00:00 close."""
    t = int(c.end[-1])
    if t % DAY == 0:
        return None
    d0 = t - t % DAY
    n = min(len(c), max_candles)
    ep = c.epoch[-n:]
    sel = ep >= d0
    return t, d0, c.epoch[-n:][sel], c.end[-n:][sel], c.open[-n:][sel], c.high[-n:][sel], c.low[-n:][sel], c.close[-n:][sel]


def prev_day_hlc(c: Bars, min_candles: int = 12) -> tuple[float, float, float] | None:
    """(high, low, close) of the last completed UTC trading day before the current candle's day."""
    n = min(len(c), 80)
    end, hi, lo, cl = c.end[-n:], c.high[-n:], c.low[-n:], c.close[-n:]
    day = (end - 1) // DAY
    prev = day < day[-1]
    if not prev.any():
        return None
    last = day[prev][-1]
    sel = day == last
    if sel.sum() < min_candles:
        return None
    return float(hi[sel].max()), float(lo[sel].min()), float(cl[sel][-1])


class IdeaStrategy(FamilyStrategy):
    """Shared pieces: x100, 3% stake, exit at a fixed UTC hour on the entry day unless a
    subclass says otherwise, optional stop as a fraction of the 20-day average daily range."""
    EXIT_HOUR = 20

    def _adr(self, c: Bars) -> float | None:
        a = daily_atr(c, 20)
        return a if a and a > 0 else None

    def _stop_pips(self, symbol: str, c: Bars, frac: float) -> float | None:
        a = self._adr(c)
        return None if not frac or a is None else frac * a / PIP[symbol]

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.EXIT_HOUR * HOUR


# --------------------------------------------------------------------------- i1
class FixReversal(IdeaStrategy):
    """Idea 1: fade the hour before the 16:00 London WM/Reuters fix (1h).

    Benchmark-tracking funds execute at the fix; dealers who take those orders hedge ahead of
    it, which pushes the price in the order's direction during the hour before the fix and is
    partly undone once the fix is printed (Evans 2018; Marsh, Panagiotou and Payne 2017). The
    strategy: at the close of the pre-fix hour (15:00-16:00 UTC in winter, 14:00-15:00 in
    summer; the clock change is a calendar fact, not a setting), if that hour moved at least
    k x the 20-day average daily range, trade the other way. Exit `hold_hours` later;
    optional stop of `stop` daily ranges. Loser: the fund paying the fix price.
    """
    name = "i1_fix_reversal"
    family = "i1"
    timeframe = "1h"
    defaults = {"k": 0.1, "hold_hours": 4, "stop": 0.0}

    def _prefix_move(self, symbol, c):
        t = int(c.end[-1])
        if t % HOUR or hour_of(t) != london_fix_hour(t):
            return None
        a = self._adr(c)
        if a is None:
            return None
        return float(c.close[-1] - c.open[-1]) / a

    def direction(self, symbol, c):
        m = self._prefix_move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTDOWN" if m > 0 else "MULTUP"

    def stops(self, symbol, c, direction):
        if self._prefix_move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None

    def exit_now(self, symbol, c, position):
        return int(c.end[-1]) >= position.entry_epoch + self.params["hold_hours"] * HOUR


# --------------------------------------------------------------------------- i2
class TurtleSoup(IdeaStrategy):
    """Idea 2: failed sweep of yesterday's high or low (1h), "turtle soup" (Connors and
    Raschke 1995), the mirror image of the breakouts Phase 4 tested.

    Stop-loss and breakout orders cluster just beyond the previous day's high and low. When a
    1h candle (06:00 to `cutoff` UTC) trades through yesterday's high but closes back below it,
    and no earlier candle today had reached it, those orders have been filled and absorbed:
    trade Down toward the middle of yesterday's range. Mirror for the low. Target tp_frac and
    stop sl_frac of yesterday's range; closed at 20:00 UTC. Loser: the breakout trader filled at
    the extreme and the stop placed just beyond it.
    """
    name = "i2_turtle_soup"
    family = "i2"
    timeframe = "1h"
    defaults = {"sl_frac": 0.5, "tp_frac": 0.5, "cutoff": 17}
    MIN_RANGE_PIPS = {"frxEURUSD": 20, "frxGBPUSD": 20, "frxUSDJPY": 30}

    def _setup(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        h = hour_of(t)
        if t % HOUR or not 6 <= h <= self.params["cutoff"] or len(ep) < 2:
            return None
        y = prev_day_hlc(c)
        if y is None:
            return None
        yh, yl, _ = y
        rng = yh - yl
        if rng / PIP[symbol] < self.MIN_RANGE_PIPS[symbol]:
            return None
        earlier_hi, earlier_lo = hi[:-1].max(), lo[:-1].min()
        if hi[-1] > yh and cl[-1] < yh and earlier_hi <= yh:
            return "MULTDOWN", rng
        if lo[-1] < yl and cl[-1] > yl and earlier_lo >= yl:
            return "MULTUP", rng
        return None

    def direction(self, symbol, c):
        s = self._setup(symbol, c)
        return None if s is None else s[0]

    def stops(self, symbol, c, direction):
        s = self._setup(symbol, c)
        if s is None:
            return None
        rng = s[1] / PIP[symbol]
        return self.params["sl_frac"] * rng, self.params["tp_frac"] * rng


# --------------------------------------------------------------------------- i3 / i4
def round_level(symbol: str, price: float, step: float) -> float:
    return float(np.round(price / step) * step)


class RoundBounce(IdeaStrategy):
    """Idea 3: rejection at a round number (1h). Osler (2003): take-profit orders cluster at
    rates ending in 00, so the rate tends to reverse there. A 1h candle (06:00-17:00 UTC) that
    opens on one side of a 00 level, trades through it, and closes back on the opening side has
    met that cluster: trade back away from the level. Target tp_frac and stop sl_frac of the
    20-day average daily range; closed at 20:00 UTC. Loser: the trader who chased the level.
    """
    name = "i3_round_bounce"
    family = "i3"
    timeframe = "1h"
    defaults = {"sl_frac": 0.2, "tp_frac": 0.4}
    STEP = {"frxEURUSD": 0.01, "frxGBPUSD": 0.01, "frxUSDJPY": 1.0}

    def _event(self, symbol, c):
        t = int(c.end[-1])
        if t % HOUR or not 6 <= hour_of(t) <= 17 or self._adr(c) is None:
            return None
        step = self.STEP[symbol]
        o, h, lo, cl = float(c.open[-1]), float(c.high[-1]), float(c.low[-1]), float(c.close[-1])
        up_level = float(np.ceil(o / step) * step)          # nearest 00 above the open
        dn_level = float(np.floor(o / step) * step)         # nearest 00 below the open
        if up_level > o and h >= up_level and cl < up_level:
            return "MULTDOWN"
        if dn_level < o and lo <= dn_level and cl > dn_level:
            return "MULTUP"
        return None

    def direction(self, symbol, c):
        return self._event(symbol, c)

    def stops(self, symbol, c, direction):
        if self._event(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["sl_frac"]), self._stop_pips(symbol, c, self.params["tp_frac"])


class RoundBreak(IdeaStrategy):
    """Idea 4: close through a round number (1h). Osler (2003): stop-loss orders cluster just
    beyond 00 levels, so once the rate closes through one, the stops feed the move. A 1h candle
    (06:00-17:00 UTC) that opens on one side of a 00 level and closes at least `thru` daily
    ranges beyond it: trade in the direction of the break. Stop sl_frac of the daily range
    (back through the level); closed at 20:00 UTC. Loser: the stop-loss holder just past the
    figure. The bounce (idea 3) and the break are the two halves of Osler's finding.
    """
    name = "i4_round_break"
    family = "i4"
    timeframe = "1h"
    defaults = {"thru": 0.05, "sl_frac": 0.2}
    STEP = RoundBounce.STEP

    def _event(self, symbol, c):
        t = int(c.end[-1])
        a = self._adr(c)
        if t % HOUR or not 6 <= hour_of(t) <= 17 or a is None:
            return None
        step = self.STEP[symbol]
        o, cl = float(c.open[-1]), float(c.close[-1])
        up_level = float(np.ceil(o / step) * step)
        dn_level = float(np.floor(o / step) * step)
        thru = self.params["thru"] * a
        if up_level > o and cl >= up_level + thru:
            return "MULTUP"
        if dn_level < o and cl <= dn_level - thru:
            return "MULTDOWN"
        return None

    def direction(self, symbol, c):
        return self._event(symbol, c)

    def stops(self, symbol, c, direction):
        if self._event(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["sl_frac"]), None


# --------------------------------------------------------------------------- i5
class AsiaFade(IdeaStrategy):
    """Idea 5: London fades the Asian session (1h). A move made between 00:00 UTC and the
    first London hour happens in the thinnest hours of the day, often on one regional flow;
    when European liquidity arrives it is partly absorbed and undone. At the `decision_hour`
    close, if the move since 00:00 is at least k daily ranges, trade back toward the day's
    open; exit at `exit_hour`. No stop beyond the stop out. Unlike families 11 and 12 the other
    pairs are not consulted, and unlike family 8 the move is faded, not followed. Loser: the
    Asian-session momentum trader holding into London.
    """
    name = "i5_asia_fade"
    family = "i5"
    timeframe = "1h"
    defaults = {"decision_hour": 7, "k": 0.3, "exit_hour": 12}

    def _move(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        if t % HOUR or hour_of(t) != self.params["decision_hour"] or len(ep) < self.params["decision_hour"] * 0.75:
            return None
        a = self._adr(c)
        return None if a is None else float(cl[-1] - op[0]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTDOWN" if m > 0 else "MULTUP"

    def stops(self, symbol, c, direction):
        return None if self._move(symbol, c) is None else (None, None)

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.params["exit_hour"] * HOUR


# --------------------------------------------------------------------------- i6
class UsDataDrift(IdeaStrategy):
    """Idea 6: drift after the US data hours (1h). Scheduled US releases land at 12:30 or 13:30
    UTC; Deriv triples its commission in those hours, so Phase 4 never traded them. The
    reaction is quick but the follow-through takes hours as slower money repositions. At the
    14:00 close (commission back to base), if the 12:00-14:00 move is at least k daily ranges,
    follow it to `exit_hour`; optional stop of `stop` daily ranges. Loser: the position caught
    on the wrong side of the release, unwinding through the afternoon.
    """
    name = "i6_us_data_drift"
    family = "i6"
    timeframe = "1h"
    defaults = {"k": 0.2, "exit_hour": 20, "stop": 0.0}
    DECISION_HOUR = 14

    def _move(self, symbol, c):
        t = int(c.end[-1])
        if t % HOUR or hour_of(t) != self.DECISION_HOUR or len(c) < 3:
            return None
        if int(c.end[-3]) != t - 2 * HOUR:
            return None
        a = self._adr(c)
        return None if a is None else float(c.close[-1] - c.open[-2]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTUP" if m > 0 else "MULTDOWN"

    def stops(self, symbol, c, direction):
        if self._move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.params["exit_hour"] * HOUR


# --------------------------------------------------------------------------- i7
class NyIntoAsia(IdeaStrategy):
    """Idea 7: the New York session's move carries into Asia (1h, held overnight at x100).
    At the 17:00 UTC close (the last entry hour), if the 13:00-17:00 move is at least k daily
    ranges, follow it and exit at `exit_hour` the next morning (00:00 = before Tokyo, 06:00 =
    after Asia). Asian participants trade the US news of the day when their market opens, in
    the same direction; nothing in Phase 4 held overnight on purpose. No signal on Fridays
    (every trade is closed 20:30 before the weekend). Optional stop of `stop` daily ranges.
    Loser: the US-session fader who goes home flat and is run over in Asia.
    """
    name = "i7_ny_into_asia"
    family = "i7"
    timeframe = "1h"
    defaults = {"k": 0.25, "exit_hour": 6, "stop": 0.0}
    DECISION_HOUR = 17

    def _move(self, symbol, c):
        t = int(c.end[-1])
        if t % HOUR or hour_of(t) != self.DECISION_HOUR or len(c) < 5:
            return None
        if ((t // DAY) + 3) % 7 == 4:                  # Friday
            return None
        if int(c.end[-5]) != t - 4 * HOUR:
            return None
        a = self._adr(c)
        return None if a is None else float(c.close[-1] - c.open[-4]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTUP" if m > 0 else "MULTDOWN"

    def stops(self, symbol, c, direction):
        if self._move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + DAY + self.params["exit_hour"] * HOUR


# --------------------------------------------------------------------------- i8
class LondonReversal(IdeaStrategy):
    """Idea 8: the London session's move is squared in the afternoon (1h). At the 14:00 UTC
    close, if the move since 06:00 is at least k daily ranges, trade against it until
    `exit_hour`. European desks cut intraday positions before their 16:00 close and US traders
    fade an extended London move. Family 8 followed the move at 10:00; this fades it at 14:00
    once the London session is nearly done. Optional stop of `stop` daily ranges. Loser: the
    London trend-follower holding into the US afternoon.
    """
    name = "i8_london_reversal"
    family = "i8"
    timeframe = "1h"
    defaults = {"k": 0.4, "exit_hour": 20, "stop": 0.0}
    DECISION_HOUR = 14

    def _move(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        if t % HOUR or hour_of(t) != self.DECISION_HOUR:
            return None
        sel = ep >= d0 + 6 * HOUR
        if sel.sum() < 6:
            return None
        a = self._adr(c)
        return None if a is None else float(cl[-1] - op[sel][0]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTDOWN" if m > 0 else "MULTUP"

    def stops(self, symbol, c, direction):
        if self._move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + self.params["exit_hour"] * HOUR


# --------------------------------------------------------------------------- i9
class RangeExhaustion(IdeaStrategy):
    """Idea 9: a day that has already used its range reverts toward its middle (1h). From the
    10:00 UTC close to 17:00, the first candle on which the day's range reaches r x the 20-day
    average daily range while the close sits in the outer 15% of that range: trade back toward
    the midpoint of the day's range (target), stop sl_frac daily ranges beyond; closed at
    20:00 UTC. Dealers' intraday risk limits and the day's natural range cap further extension
    without news. Family 4 faded distance from a moving average in calm markets; this fades
    only an exhausted day. Loser: the late breakout chaser at the day's extreme.
    """
    name = "i9_range_exhaustion"
    family = "i9"
    timeframe = "1h"
    defaults = {"r": 1.0, "sl_frac": 0.3}
    EDGE = 0.15

    def _setup(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        if t % HOUR or not 10 <= hour_of(t) <= 17 or len(ep) < 8:
            return None
        a = self._adr(c)
        if a is None:
            return None
        day_hi, day_lo = hi.max(), lo.min()
        rng = day_hi - day_lo
        if rng < self.params["r"] * a:
            return None
        # First candle of the day on which the range condition holds.
        prev_rng = np.maximum.accumulate(hi)[:-1] - np.minimum.accumulate(lo)[:-1]
        if len(prev_rng) and prev_rng[-1] >= self.params["r"] * a:
            return None
        loc = (cl[-1] - day_lo) / rng
        mid = (day_hi + day_lo) / 2
        if loc >= 1 - self.EDGE:
            return "MULTDOWN", float(cl[-1] - mid)
        if loc <= self.EDGE:
            return "MULTUP", float(mid - cl[-1])
        return None

    def direction(self, symbol, c):
        s = self._setup(symbol, c)
        return None if s is None else s[0]

    def stops(self, symbol, c, direction):
        s = self._setup(symbol, c)
        if s is None:
            return None
        return self._stop_pips(symbol, c, self.params["sl_frac"]), s[1] / PIP[symbol]


# --------------------------------------------------------------------------- i10
class TrendIntraday(IdeaStrategy):
    """Idea 10: short-term time-series momentum traded only in the liquid hours (1h). At the
    06:00 UTC close, if yesterday's close is at least k daily ranges above (below) the close
    `lookback` trading days earlier, go Up (Down) and exit at 20:00 the same day. Trend-
    followers add to positions during London and New York hours, so a multi-day trend shows
    up as intraday drift; the overnight hours (where Phase 4's weekly momentum sat through
    reversals) are skipped. Optional stop of `stop` daily ranges. Loser: the counter-trend
    trader fading a trend that is still being built.
    """
    name = "i10_trend_intraday"
    family = "i10"
    timeframe = "1h"
    defaults = {"lookback": 5, "k": 0.5, "stop": 0.0}
    DECISION_HOUR = 6

    def _move(self, symbol, c):
        t = int(c.end[-1])
        if t % HOUR or hour_of(t) != self.DECISION_HOUR:
            return None
        L = self.params["lookback"]
        days = daily_closes(c, L + 2)
        if len(days) < L + 1:
            return None
        a = self._adr(c)
        return None if a is None else float(days[-1] - days[-1 - L]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTUP" if m > 0 else "MULTDOWN"

    def stops(self, symbol, c, direction):
        if self._move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None


# --------------------------------------------------------------------------- i11
class NyCutBreakout(IdeaStrategy):
    """Idea 11: release after the 10:00 New York option cut (1h). Dealers hedging options that
    expire at the cut (14:00 UTC in summer, 15:00 in winter) pin the spot rate near big strikes
    in the hours before; when the options expire that hedging stops and the rate is free to
    move. The first 1h candle after the cut (and at most the second) that closes outside the
    range of the `range_hours` before the cut: trade the break. Stop sl_frac of that range on
    the other side; closed at 20:00 UTC. Fixed: the pre-cut range must be at least 5 pips (8
    on USD/JPY). Loser: the range trader fading the breakout as if the pin still held.
    """
    name = "i11_ny_cut_breakout"
    family = "i11"
    timeframe = "1h"
    defaults = {"range_hours": 2, "sl_frac": 1.0}
    MIN_RANGE_PIPS = {"frxEURUSD": 5, "frxGBPUSD": 5, "frxUSDJPY": 8}

    def _setup(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        cut = ny_cut_hour(t)
        h = hour_of(t)
        if t % HOUR or not cut + 1 <= h <= min(cut + 2, 17):
            return None
        rh = self.params["range_hours"]
        pre = (end > d0 + (cut - rh) * HOUR) & (end <= d0 + cut * HOUR)
        if pre.sum() < rh:
            return None
        top, bot = float(hi[pre].max()), float(lo[pre].min())
        if (top - bot) / PIP[symbol] < self.MIN_RANGE_PIPS[symbol]:
            return None
        post = (end > d0 + cut * HOUR) & (end < t)
        if np.any(cl[post] > top) or np.any(cl[post] < bot):
            return None                                    # already broke out after the cut
        if cl[-1] > top:
            return "MULTUP", top - bot
        if cl[-1] < bot:
            return "MULTDOWN", top - bot
        return None

    def direction(self, symbol, c):
        s = self._setup(symbol, c)
        return None if s is None else s[0]

    def stops(self, symbol, c, direction):
        s = self._setup(symbol, c)
        if s is None:
            return None
        return self.params["sl_frac"] * s[1] / PIP[symbol], None


# --------------------------------------------------------------------------- i12
class TwapPullback(IdeaStrategy):
    """Idea 12: pullback to the day's average price on a trending day (1h). Institutional
    orders are worked by VWAP/TWAP algorithms, which buy more aggressively when the rate dips
    below the day's average on a day they are net buyers. From the 09:00 to the 16:00 UTC
    close, on the first candle where the day's net move since 00:00 is at least k daily
    ranges, the candle's low touches the day's average price (mean of the hourly OHLC4 since
    00:00) and the close is back above it: go Up (mirror for Down). Stop sl_frac daily ranges;
    closed at 20:00 UTC. Family 3 bought RSI dips in a daily trend; this is the intraday
    execution-flow version with the day's own average as the level. Loser: the intraday
    fader selling into the algorithm's bids.
    """
    name = "i12_twap_pullback"
    family = "i12"
    timeframe = "1h"
    defaults = {"k": 0.3, "sl_frac": 0.3}

    def _setup(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        if t % HOUR or not 9 <= hour_of(t) <= 16 or len(ep) < 8:
            return None
        a = self._adr(c)
        if a is None:
            return None
        twap = float(((op + hi + lo + cl) / 4).mean())
        move = (cl[-1] - op[0]) / a
        if move >= self.params["k"] and lo[-1] <= twap < cl[-1]:
            return "MULTUP"
        if move <= -self.params["k"] and hi[-1] >= twap > cl[-1]:
            return "MULTDOWN"
        return None

    def direction(self, symbol, c):
        return self._setup(symbol, c)

    def stops(self, symbol, c, direction):
        if self._setup(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["sl_frac"]), None


# --------------------------------------------------------------------------- i13
class MorningOvernight(IdeaStrategy):
    """Idea 13: a strong London morning, held through New York and Asia (1h, x100 overnight).
    At the `decision_hour` close, if the move since 00:00 UTC is at least k daily ranges,
    follow it and exit at 06:00 UTC the next day. Family 8 followed the same move but closed
    at 20:00; its before-cost edge (about 2 pips) was real but smaller than the cost. A flow
    big enough to move a pair a third of its daily range by mid-morning takes more than one
    session to absorb, and the horizon is what sets the pips available against a fixed cost.
    No signal on Fridays (the weekend close would cut the hold). Optional stop of `stop`
    daily ranges. Loser: the intraday fader, and the Asian desk reacting a session late.
    """
    name = "i13_morning_overnight"
    family = "i13"
    timeframe = "1h"
    defaults = {"decision_hour": 8, "k": 0.3, "stop": 0.0}
    EXIT_HOUR = 6

    def _move(self, symbol, c):
        v = today_view(c)
        if v is None:
            return None
        t, d0, ep, end, op, hi, lo, cl = v
        h = self.params["decision_hour"]
        if t % HOUR or hour_of(t) != h or len(ep) < h * 0.75 or ((t // DAY) + 3) % 7 == 4:
            return None
        a = self._adr(c)
        return None if a is None else float(cl[-1] - op[0]) / a

    def direction(self, symbol, c):
        m = self._move(symbol, c)
        if m is None or abs(m) < self.params["k"]:
            return None
        return "MULTUP" if m > 0 else "MULTDOWN"

    def stops(self, symbol, c, direction):
        if self._move(symbol, c) is None:
            return None
        return self._stop_pips(symbol, c, self.params["stop"]), None

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + DAY + self.EXIT_HOUR * HOUR


# --------------------------------------------------------------------------- i14
class NyCutOvernight(NyCutBreakout):
    """Idea 14: the post-cut break (idea 11) held overnight to 06:00 UTC the next day.
    Designed from idea 11's pre-screen (31 Oct 2026): the break direction after the New York
    option cut beat 94% of coin-toss runs but earned about 1 pip a trade against 4 pips of
    cost by the 20:00 close. If the release of the pinned rate is a flow that keeps going
    through the US afternoon and Asia, a longer horizon collects more of it for the same
    cost; if the information is spent by 20:00, this loses it back. No signal on Fridays.
    Same settings as idea 11 (pre-cut range hours, stop as a fraction of that range).
    """
    name = "i14_ny_cut_overnight"
    family = "i14"
    EXIT_HOUR = 6

    def _setup(self, symbol, c):
        t = int(c.end[-1])
        if ((t // DAY) + 3) % 7 == 4:                      # Friday: the weekend close would cut the hold
            return None
        return super()._setup(symbol, c)

    def exit_now(self, symbol, c, position):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + DAY + self.EXIT_HOUR * HOUR


IDEA_CLASSES = (FixReversal, TurtleSoup, RoundBounce, RoundBreak, AsiaFade, UsDataDrift, NyIntoAsia,
                LondonReversal, RangeExhaustion, TrendIntraday, NyCutBreakout, TwapPullback, MorningOvernight, NyCutOvernight)


REGISTRY = {cls.name: cls for cls in (LondonBreakout, TrendBreakout, TrendBreakout1d, TrendPullback,
                                     TrendPullback1h, MeanReversion, MeanReversion4h, SessionDrift,
                                     QuietLondonBreakout, WeeklyMomentum, MorningMomentum,
                                     EurGbpConvergence, ShockDay, DollarWideCatchUp, LoneMoverReverts,
                                     *IDEA_CLASSES)}
