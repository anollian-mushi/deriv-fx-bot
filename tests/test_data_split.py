from datetime import date

from fxbot.data.candles import Candle
from fxbot.data.split import HOLDOUT_START, before_holdout, day_in_holdout, in_holdout


def test_holdout_start_is_fixed():
    assert HOLDOUT_START == date(2026, 4, 28)


def test_boundary():
    last_train_minute = 1777334340   # 2026-04-27 23:59 UTC
    first_holdout = 1777334400       # 2026-04-28 00:00 UTC
    assert not in_holdout(last_train_minute)
    assert in_holdout(first_holdout)
    assert day_in_holdout(date(2026, 4, 28)) and not day_in_holdout(date(2026, 4, 27))


def test_before_holdout_drops_holdout_candles():
    c1 = Candle(1777334340, 1, 1, 1, 1)
    c2 = Candle(1777334400, 1, 1, 1, 1)
    assert before_holdout([c1, c2]) == [c1]


def test_untouched_start_is_fixed():
    from fxbot.data.split import UNTOUCHED_START, UNTOUCHED_START_EPOCH, in_untouched
    assert UNTOUCHED_START == date(2026, 10, 31)
    assert in_untouched(UNTOUCHED_START_EPOCH) and not in_untouched(UNTOUCHED_START_EPOCH - 60)


def test_untouched_period_needs_forward_flag():
    import pytest
    from fxbot.backtest.candles import check_dates, load_m1
    from fxbot.data.split import HoldoutError, UntouchedError
    with pytest.raises(UntouchedError):
        check_dates(date(2026, 10, 1), date(2026, 10, 31), include_holdout=True)
    with pytest.raises(UntouchedError):
        load_m1("frxEURUSD", date(2026, 11, 2), date(2026, 11, 3), include_holdout=True)
    assert issubclass(UntouchedError, HoldoutError)
    check_dates(date(2026, 10, 1), date(2026, 10, 30), include_holdout=True)
    check_dates(date(2026, 10, 1), date(2026, 11, 5), include_holdout=True, forward=True)
