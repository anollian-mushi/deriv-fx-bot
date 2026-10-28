"""Forex trading calendar for Deriv and gap detection.

Deriv forex hours (trading_times, checked 2026-10-28): Monday to Friday,
00:00 to 23:59:59 GMT, with an early close at 20:55 on Fridays. Weekends are
closed. Holidays (e.g. 25 Dec, 1 Jan) are only listed in advance, so a whole
weekday without candles is treated as a closed day, not as a gap.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Iterable

DAY = 86400
FRIDAY_CLOSE = 20 * 3600 + 55 * 60  # seconds after midnight
SMALL_GAP_1M = 5  # missing 1m runs shorter than this are normal quiet minutes


def day_start(day: dt.date) -> int:
    return int(dt.datetime(day.year, day.month, day.day, tzinfo=dt.timezone.utc).timestamp())


def utc_date(epoch: int) -> dt.date:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).date()


def is_trading_day(day: dt.date) -> bool:
    return day.weekday() < 5


def session_end(day: dt.date) -> int:
    """Seconds after midnight when trading stops on this day."""
    return FRIDAY_CLOSE if day.weekday() == 4 else DAY


def expected_epochs(day: dt.date, seconds: int) -> list[int]:
    """Candle start times expected on a trading day (empty on weekends)."""
    if not is_trading_day(day):
        return []
    start = day_start(day)
    return [start + s for s in range(0, session_end(day), seconds)]


@dataclass(frozen=True)
class Gap:
    start: int  # first missing candle epoch
    missing: int  # number of missing candles in a row

    def describe(self, seconds: int) -> str:
        a = dt.datetime.fromtimestamp(self.start, dt.timezone.utc)
        b = a + dt.timedelta(seconds=self.missing * seconds)
        return f"{a:%H:%M}-{b:%H:%M} ({self.missing} candles)"


def find_gaps(epochs: Iterable[int], day: dt.date, seconds: int) -> tuple[list[Gap], int, int]:
    """Compare a day's candles with the trading calendar.

    Returns (gaps, small_missing, outside_session):
    - gaps: runs of missing candles inside trading hours. For 1m, runs shorter
      than SMALL_GAP_1M are not gaps (no trades in a quiet minute is normal);
      they are only counted in small_missing.
    - outside_session: candles found where the market should be closed
      (weekend, after the Friday close). Suspicious, reported separately.
    """
    have = set(epochs)
    expected = expected_epochs(day, seconds)
    expected_set = set(expected)
    outside = len(have - expected_set)
    min_run = SMALL_GAP_1M if seconds == 60 else 1
    gaps: list[Gap] = []
    small = 0
    run_start, run_len = None, 0
    for e in expected + [None]:
        if e is not None and e not in have:
            if run_start is None:
                run_start = e
            run_len += 1
            continue
        if run_start is not None:
            if run_len >= min_run:
                gaps.append(Gap(run_start, run_len))
            else:
                small += run_len
            run_start, run_len = None, 0
    return gaps, small, outside
