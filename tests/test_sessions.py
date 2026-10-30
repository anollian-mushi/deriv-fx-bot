import datetime as dt

from fxbot import sessions as s


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


def test_market_hours_weekend_friday_and_holidays():
    assert s.market_open(ep(2025, 3, 3, 0, 0))            # Monday 00:00
    assert s.market_open(ep(2025, 3, 7, 20, 54))          # Friday 20:54
    assert not s.market_open(ep(2025, 3, 7, 20, 55))      # Friday close
    assert not s.market_open(ep(2025, 3, 8, 12, 0))       # Saturday
    assert not s.market_open(ep(2025, 12, 25, 12, 0))     # Christmas (Thursday)
    assert not s.market_open(ep(2026, 1, 1, 12, 0))       # New Year (Thursday)
    assert s.market_open(ep(2025, 12, 24, 21, 59))
    assert not s.market_open(ep(2025, 12, 24, 22, 0))     # early close


def test_entry_window_and_pause():
    assert s.entry_allowed_by_calendar(ep(2025, 3, 4, 6, 0))[0]
    assert s.entry_allowed_by_calendar(ep(2025, 3, 4, 17, 59))[0]
    assert s.entry_allowed_by_calendar(ep(2025, 3, 4, 5, 59)) == (False, "outside_entry_window")
    assert s.entry_allowed_by_calendar(ep(2025, 3, 4, 18, 0)) == (False, "outside_entry_window")
    assert s.entry_allowed_by_calendar(ep(2025, 3, 4, 21, 0)) == (False, "daily_pause")
    assert s.entry_allowed_by_calendar(ep(2025, 3, 8, 10, 0)) == (False, "market_closed")


def test_exit_deadlines_weekend_holiday_and_x200():
    # x100 opened Monday: held until Friday 20:30.
    assert s.exit_deadline(ep(2025, 3, 3, 10), 100) == ep(2025, 3, 7, 20, 30)
    # x200 opened Monday: closed Monday 20:50.
    assert s.exit_deadline(ep(2025, 3, 3, 10), 200) == ep(2025, 3, 3, 20, 50)
    # x200 opened Friday: Friday 20:30 comes first.
    assert s.exit_deadline(ep(2025, 3, 7, 10), 200) == ep(2025, 3, 7, 20, 30)
    # Christmas 2025 is a Thursday: trades opened on the 22nd close by Wed 24th 20:30.
    assert s.exit_deadline(ep(2025, 12, 22, 10), 100) == ep(2025, 12, 24, 20, 30)
    # Opened Friday 26 Dec: next closure is the weekend.
    assert s.exit_deadline(ep(2025, 12, 26, 10), 100) == ep(2025, 12, 26, 20, 30)
    # New Year 2026 (Thursday): opened Mon 29 Dec, close Wed 31 Dec 20:30.
    assert s.exit_deadline(ep(2025, 12, 29, 10), 100) == ep(2025, 12, 31, 20, 30)


def test_pre_closure_blocks_late_entries():
    # Entry window ends 17:59, before 20:30, so this only matters on early-close days.
    assert s.entry_allowed_by_calendar(ep(2025, 3, 7, 17, 0))[0]
