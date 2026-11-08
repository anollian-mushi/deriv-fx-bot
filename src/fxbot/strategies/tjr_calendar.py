"""Session windows, news blocks and U.S. bank holidays for the TJR test (docs/tjr_rules.md).

All rules are in local market time and follow each city's summer-time changes (zoneinfo):
- Sessions (section 12, C26): London 02:00-05:00 and New York 07:00-11:00, New York time.
- Liquidity ranges (section 3, C6): Asian session 20:00-00:00 New York time (the evening
  before), London session 02:00-05:00 New York time.
- News (section 13, owner's change of 2 Nov 2026 to C28): no new entries 08:15-09:00 New
  York time on every weekday for pairs containing USD (the 08:30 releases: CPI, PPI, NFP,
  claims), and 06:45-07:30 London time on every weekday for pairs containing GBP. FOMC is
  avoided by the 17:55 UTC flat time.
- Days off (section 12, C27): U.S. Federal Reserve holidays, for all pairs.

Everything is computed once per New York date and cached, so the per-candle cost is a lookup.
"""

from __future__ import annotations

import datetime as dt
from functools import lru_cache
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")
LONDON = ZoneInfo("Europe/London")
UTC = dt.timezone.utc

FLAT_SECOND_OF_DAY = 17 * 3600 + 55 * 60          # close every trade at 17:55 UTC (C25)


def _epoch(day: dt.date, hh: int, mm: int, tz: ZoneInfo) -> int:
    return int(dt.datetime(day.year, day.month, day.day, hh, mm, tzinfo=tz).timestamp())


def ny_date(epoch: int) -> dt.date:
    return dt.datetime.fromtimestamp(epoch, NY).date()


# ----------------------------------------------------------------------------- holidays
def _nth_weekday(year: int, month: int, weekday: int, n: int) -> dt.date:
    d = dt.date(year, month, 1)
    d += dt.timedelta(days=(weekday - d.weekday()) % 7)
    return d + dt.timedelta(weeks=n - 1)


def _last_weekday(year: int, month: int, weekday: int) -> dt.date:
    d = dt.date(year + (month == 12), month % 12 + 1, 1) - dt.timedelta(days=1)
    return d - dt.timedelta(days=(d.weekday() - weekday) % 7)


@lru_cache(maxsize=None)
def us_bank_holidays(year: int) -> frozenset[dt.date]:
    """Federal Reserve holidays. A fixed-date holiday on a Sunday is observed on the Monday; on a
    Saturday the Fed stays open (no Friday holiday). Juneteenth from 2022 (first Fed observance)."""
    fixed = [dt.date(year, 1, 1), dt.date(year, 7, 4), dt.date(year, 11, 11), dt.date(year, 12, 25)]
    if year >= 2022:
        fixed.append(dt.date(year, 6, 19))
    days = {d + dt.timedelta(days=1) if d.weekday() == 6 else d for d in fixed}
    days |= {
        _nth_weekday(year, 1, 0, 3),     # Martin Luther King Jr. Day
        _nth_weekday(year, 2, 0, 3),     # Washington's Birthday
        _last_weekday(year, 5, 0),       # Memorial Day
        _nth_weekday(year, 9, 0, 1),     # Labor Day
        _nth_weekday(year, 10, 0, 2),    # Columbus Day
        _nth_weekday(year, 11, 3, 4),    # Thanksgiving
    }
    return frozenset(days)


def is_us_bank_holiday(day: dt.date) -> bool:
    return day in us_bank_holidays(day.year)


# ----------------------------------------------------------------------------- per-day windows
@lru_cache(maxsize=4096)
def day_windows(day: dt.date) -> dict:
    """UTC epoch windows [start, end) for one New York date."""
    prev = day - dt.timedelta(days=1)
    return {
        "london": (_epoch(day, 2, 0, NY), _epoch(day, 5, 0, NY)),
        "newyork": (_epoch(day, 7, 0, NY), _epoch(day, 11, 0, NY)),
        "asia_range": (_epoch(prev, 20, 0, NY), _epoch(day, 0, 0, NY)),
        "london_range": (_epoch(day, 2, 0, NY), _epoch(day, 5, 0, NY)),
        "news_usd": (_epoch(day, 8, 15, NY), _epoch(day, 9, 0, NY)),
        "news_gbp": (_epoch(day, 6, 45, LONDON), _epoch(day, 7, 30, LONDON)),
    }


def session_at(epoch: int) -> tuple[str | None, dt.date, tuple[int, int] | None]:
    """(session name or None, New York date, window) for a moment."""
    day = ny_date(epoch)
    w = day_windows(day)
    for name in ("london", "newyork"):
        a, b = w[name]
        if a <= epoch < b:
            return name, day, (a, b)
    return None, day, None


def news_blocked(symbol: str, epoch: int) -> bool:
    """True if a new entry on this pair is blocked by a news window at this moment."""
    day = ny_date(epoch)
    if day.weekday() >= 5:
        return False
    w = day_windows(day)
    pair = symbol[3:] if symbol.startswith("frx") else symbol
    if "USD" in pair:
        a, b = w["news_usd"]
        if a <= epoch < b:
            return True
    if "GBP" in pair:
        a, b = w["news_gbp"]
        if a <= epoch < b:
            return True
    return False


def entry_allowed(symbol: str, epoch: int) -> tuple[bool, str]:
    """TJR calendar rules for a new entry at `epoch` (on top of the CLAUDE.md risk module)."""
    if epoch % 86400 >= FLAT_SECOND_OF_DAY:
        return False, "after_flat_time"
    name, day, _ = session_at(epoch)
    if name is None:
        return False, "outside_session"
    if is_us_bank_holiday(day):
        return False, "us_bank_holiday"
    if news_blocked(symbol, epoch):
        return False, "news"
    return True, ""
