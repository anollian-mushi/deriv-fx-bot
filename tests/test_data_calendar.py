import datetime as dt

from fxbot.data.calendar import day_start, expected_epochs, find_gaps

WED = dt.date(2026, 10, 21)
FRI = dt.date(2026, 10, 23)
SAT = dt.date(2026, 10, 24)


def test_expected_epochs_weekday_friday_weekend():
    assert len(expected_epochs(WED, 60)) == 1440
    assert len(expected_epochs(WED, 3600)) == 24
    fri = expected_epochs(FRI, 60)
    assert len(fri) == 20 * 60 + 55  # closes at 20:55
    assert fri[-1] == day_start(FRI) + 20 * 3600 + 54 * 60
    assert len(expected_epochs(FRI, 900)) == 84  # 20:45 candle is the last
    assert len(expected_epochs(FRI, 3600)) == 21
    assert expected_epochs(SAT, 60) == []


def test_full_day_has_no_gaps():
    gaps, small, outside = find_gaps(expected_epochs(WED, 900), WED, 900)
    assert (gaps, small, outside) == ([], 0, 0)


def test_friday_close_is_not_a_gap():
    gaps, small, _ = find_gaps(expected_epochs(FRI, 60), FRI, 60)
    assert gaps == [] and small == 0


def test_1m_short_missing_runs_are_small_long_runs_are_gaps():
    epochs = expected_epochs(WED, 60)
    start = day_start(WED)
    missing = {start + 60 * m for m in (10, 11)}                      # 2 quiet minutes
    missing |= {start + 60 * m for m in range(600, 610)}              # 10-minute hole
    gaps, small, _ = find_gaps([e for e in epochs if e not in missing], WED, 60)
    assert small == 2
    assert len(gaps) == 1 and gaps[0].missing == 10
    assert gaps[0].describe(60) == "10:00-10:10 (10 candles)"


def test_any_missing_15m_candle_is_a_gap():
    epochs = expected_epochs(WED, 900)
    gaps, small, _ = find_gaps(epochs[:5] + epochs[6:], WED, 900)
    assert len(gaps) == 1 and small == 0


def test_candles_after_friday_close_or_on_weekend_are_flagged():
    late = day_start(FRI) + 21 * 3600
    _, _, outside = find_gaps(expected_epochs(FRI, 60) + [late], FRI, 60)
    assert outside == 1
    _, _, outside = find_gaps([day_start(SAT) + 3600], SAT, 60)
    assert outside == 1
