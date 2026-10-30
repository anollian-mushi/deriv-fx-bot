"""Deriv forex trading calendar, shared by the backtester and the live bot.

All times are UTC. Rules (CLAUDE.md, reports/costs.md):
- Market open Monday to Friday 00:00-23:59:59, Friday until 20:55.
- Closed days (Christmas, New Year) count like a weekend. On 24 and 31 Dec
  the market closes early (22:00 in our data).
- Deriv refuses new trades 20:55-21:30 every weekday (the daily pause).
- New trades open only in the entry window 06:00-17:59 (PROVISIONAL, see
  CLAUDE.md).
- Before every weekend or closed day, every open trade is closed by 20:30 on
  the last trading day before it.
- An x200 trade is closed by 20:50 on the day it opened (before the pause and
  rollover); only x100 may be held past its opening day.
"""

from __future__ import annotations

import datetime as dt

DAY = 86400
FRIDAY_CLOSE = 20 * 3600 + 55 * 60
EARLY_CLOSE = 22 * 3600                  # 24 and 31 December
PAUSE_START, PAUSE_END = 20 * 3600 + 55 * 60, 21 * 3600 + 30 * 60
ENTRY_START, ENTRY_END = 6 * 3600, 18 * 3600
PRE_CLOSURE_EXIT = 20 * 3600 + 30 * 60   # close everything before a weekend / closed day
X200_EXIT = 20 * 3600 + 50 * 60          # close x200 trades on their opening day


def utc_date(epoch: int) -> dt.date:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).date()


def day_start(day: dt.date) -> int:
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp())


def is_closed_day(day: dt.date) -> bool:
    """Christmas and New Year's Day (Deriv trading_times lists both)."""
    return (day.month, day.day) in ((12, 25), (1, 1))


def is_trading_day(day: dt.date) -> bool:
    return day.weekday() < 5 and not is_closed_day(day)


def session_end(day: dt.date) -> int:
    """Seconds after midnight when the market closes on a trading day."""
    if day.weekday() == 4:
        return FRIDAY_CLOSE
    if (day.month, day.day) in ((12, 24), (12, 31)):
        return EARLY_CLOSE
    return DAY


def market_open(epoch: int) -> bool:
    day = utc_date(epoch)
    return is_trading_day(day) and epoch - day_start(day) < session_end(day)


def in_pause(epoch: int) -> bool:
    sod = epoch % DAY
    return PAUSE_START <= sod < PAUSE_END


def in_entry_window(epoch: int) -> bool:
    return ENTRY_START <= epoch % DAY < ENTRY_END


def entry_allowed_by_calendar(epoch: int) -> tuple[bool, str]:
    """Can a new trade open at this minute, by the calendar alone?"""
    if not market_open(epoch):
        return False, "market_closed"
    if in_pause(epoch):
        return False, "daily_pause"
    if not in_entry_window(epoch):
        return False, "outside_entry_window"
    if epoch >= exit_deadline(epoch, 100):
        return False, "pre_closure"
    return True, ""


def last_day_before_closure(day: dt.date) -> bool:
    """True if the next calendar day is a weekend or closed day."""
    return not is_trading_day(day + dt.timedelta(days=1))


def exit_deadline(open_epoch: int, multiplier: int) -> int:
    """Latest epoch a trade opened at open_epoch may stay open."""
    day = utc_date(open_epoch)
    deadline = None
    if multiplier != 100:
        deadline = day_start(day) + X200_EXIT
    d = day
    for _ in range(14):
        if is_trading_day(d) and last_day_before_closure(d):
            pre = day_start(d) + min(PRE_CLOSURE_EXIT, session_end(d))
            if pre >= open_epoch or d > day:
                deadline = pre if deadline is None else min(deadline, pre)
                break
        d += dt.timedelta(days=1)
    return deadline


def pair_order(symbols: list[str], epoch: int) -> list[str]:
    """The pairs rotated so a different one is checked first from minute to minute.

    Used wherever pairs compete for the position limits (backtester and live
    bot), so no pair is always first. A plain minute counter would not do: a
    day has 1,440 minutes (divisible by 3), so the same pair would come first
    at every 10:00. The offset is a fixed scramble of the minute number (a
    32-bit integer mix): repeatable, but with no daily or hourly cycle.
    """
    n = len(symbols)
    if n < 2:
        return list(symbols)
    x = (epoch // 60) & 0xFFFFFFFF
    for _ in range(2):
        x = ((x ^ (x >> 16)) * 0x45D9F3B) & 0xFFFFFFFF
    k = (x ^ (x >> 16)) % n
    return list(symbols[k:]) + list(symbols[:k])
