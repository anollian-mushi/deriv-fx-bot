"""Incubator ideas (31 Oct 2026): rule checks for the i1-i12 strategies and the pre-screen harness."""

import datetime as dt

import numpy as np
import pytest

from fxbot.backtest import prescreen as P
from fxbot.backtest.candles import Bars
from fxbot.data.split import UNTOUCHED_START
from fxbot.strategies import families as F

EUR = "frxEURUSD"


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


def hourly(start, closes, opens=None, highs=None, lows=None):
    c = np.asarray(closes, dtype=float)
    e = start + 3600 * np.arange(len(c))
    o = np.asarray(opens, dtype=float) if opens is not None else np.r_[c[0], c[:-1]]
    h = np.asarray(highs, dtype=float) if highs is not None else np.maximum(o, c) + 0.0001
    lo = np.asarray(lows, dtype=float) if lows is not None else np.minimum(o, c) - 0.0001
    return Bars(e, e + 3600, o, h, lo, c)


def flat_days(days, start=ep(2025, 3, 3), price=1.10, step=0.0003):
    """`days` full UTC days of hourly candles with a 12-pip daily range (day open = price)."""
    closes, opens, highs, lows = [], [], [], []
    for d in range(days):
        for h in range(24):
            o = price + (0.0001 if h % 2 else -0.0001)
            closes.append(price + (0.0002 if h % 2 else -0.0002))
            opens.append(o)
            highs.append(price + step * 2 if h == 10 else price + 0.0003)
            lows.append(price - step * 2 if h == 14 else price - 0.0003)
    return hourly(start, closes, opens, highs, lows)


def _append(c: Bars, o, h, lo, cl):
    e = int(c.epoch[-1]) + 3600
    return Bars(np.r_[c.epoch, e], np.r_[c.end, e + 3600], np.r_[c.open, o], np.r_[c.high, h],
                np.r_[c.low, lo], np.r_[c.close, cl])


def test_clock_changes_are_calendar_facts():
    assert F.london_fix_hour(ep(2026, 1, 15, 12)) == 16 and F.london_fix_hour(ep(2026, 7, 15, 12)) == 15
    assert F.ny_cut_hour(ep(2026, 1, 15, 12)) == 15 and F.ny_cut_hour(ep(2026, 7, 15, 12)) == 14
    # 30 Oct 2026: London is back on GMT (clocks changed 25 Oct), New York still on daylight time (1 Nov)
    assert F.london_fix_hour(ep(2026, 10, 30, 12)) == 16 and F.ny_cut_hour(ep(2026, 10, 30, 12)) == 14


def test_fix_reversal_fades_the_prefix_hour_only_at_the_fix():
    s = F.FixReversal(k=0.1, hold_hours=4, stop=0.0)
    base = flat_days(22)                                   # 22 days, so the 20-day range exists
    # Winter day: the candle ending 16:00 UTC rose 10 pips (daily range is 12 pips -> 0.83 ranges)
    while F.hour_of(int(base.end[-1])) != 15:
        base = _append(base, 1.10, 1.1003, 1.0997, 1.10)
    up = _append(base, 1.10, 1.1011, 1.0999, 1.1010)
    assert F.hour_of(int(up.end[-1])) == 16 and not F.london_summer(int(up.end[-1]))
    assert s.direction(EUR, up) == "MULTDOWN"
    dn = _append(base, 1.10, 1.1001, 1.0989, 1.0990)
    assert s.direction(EUR, dn) == "MULTUP"
    assert s.stops(EUR, dn, "MULTUP") == (None, None)
    # One hour earlier (15:00 close in winter) it is not the fix: no signal
    assert s.direction(EUR, base) is None
    # Exit after hold_hours
    pos = F.PositionView("MULTUP", 100, 1.099, int(dn.end[-1]))
    assert not s.exit_now(EUR, _append(dn, 1.1, 1.1, 1.1, 1.1), pos)
    later = dn
    for _ in range(4):
        later = _append(later, 1.1, 1.1, 1.1, 1.1)
    assert s.exit_now(EUR, later, pos)


def test_turtle_soup_needs_a_fresh_sweep_that_closes_back_inside():
    s = F.TurtleSoup(sl_frac=0.5, tp_frac=0.5, cutoff=17)
    base = flat_days(3)                                    # yesterday's high 1.1006, low 1.0994 (12 pips)
    assert F.prev_day_hlc(base) == pytest.approx((1.1006, 1.0994, 1.1002))
    # Range below 20 pips: skipped (fixed minimum)
    big = flat_days(3, step=0.0012)                        # yesterday's range 48 pips: 1.1024 / 1.0976
    while F.hour_of(int(big.end[-1])) != 8:
        big = _append(big, 1.10, 1.1003, 1.0997, 1.10)
    sweep = _append(big, 1.1020, 1.1030, 1.1015, 1.1018)    # through 1.1024, closes back below
    assert s.direction(EUR, sweep) == "MULTDOWN"
    assert s.stops(EUR, sweep, "MULTDOWN") == pytest.approx((24.0, 24.0))
    hold = _append(big, 1.1020, 1.1030, 1.1015, 1.1026)     # closes above: a real breakout, no trade
    assert s.direction(EUR, hold) is None
    second = _append(sweep, 1.1018, 1.1030, 1.1010, 1.1015)   # already swept earlier today: no trade
    assert s.direction(EUR, second) is None
    low = _append(big, 1.0980, 1.0985, 1.0970, 1.0982)       # through 1.0976, closes back above
    assert s.direction(EUR, low) == "MULTUP"
    assert s.direction(EUR, _append(base, 1.1004, 1.1010, 1.1000, 1.1005)) is None   # 12-pip range


def test_round_number_bounce_and_break_are_mirror_events():
    bounce, brk = F.RoundBounce(), F.RoundBreak(thru=0.05)
    base = flat_days(22, price=1.1050)                     # 12-pip daily range -> thru = 0.6 pips
    while F.hour_of(int(base.end[-1])) != 9:
        base = _append(base, 1.1050, 1.1053, 1.1047, 1.1050)
    touch = _append(base, 1.1092, 1.1104, 1.1090, 1.1095)    # trades through 1.1100, closes below
    assert bounce.direction(EUR, touch) == "MULTDOWN" and brk.direction(EUR, touch) is None
    through = _append(base, 1.1092, 1.1110, 1.1090, 1.1104)  # closes 4 pips beyond 1.1100
    assert brk.direction(EUR, through) == "MULTUP" and bounce.direction(EUR, through) is None
    down = _append(base, 1.1004, 1.1006, 1.0994, 1.0997)     # closes 3 pips under 1.1000
    assert brk.direction(EUR, down) == "MULTDOWN"
    nothing = _append(base, 1.1050, 1.1060, 1.1040, 1.1055)  # no 00 level touched
    assert bounce.direction(EUR, nothing) is None and brk.direction(EUR, nothing) is None
    assert bounce.stops(EUR, touch, "MULTDOWN") == pytest.approx((0.2 * 12, 0.4 * 12))


def test_ny_into_asia_skips_fridays_and_exits_next_morning():
    s = F.NyIntoAsia(k=0.25, exit_hour=6, stop=0.0)
    thu = flat_days(22, start=ep(2025, 2, 10))              # Mondays from 10 Feb; 22 days later is a Tuesday
    while F.hour_of(int(thu.end[-1])) != 16:
        thu = _append(thu, 1.10, 1.1003, 1.0997, 1.10)
    sig = _append(thu, 1.10, 1.1012, 1.0999, 1.1010)         # 13:00-17:00 move = 10 pips of a 12-pip range
    assert F.hour_of(int(sig.end[-1])) == 17 and s.direction(EUR, sig) == "MULTUP"
    pos = F.PositionView("MULTUP", 100, 1.101, int(sig.end[-1]))
    later = sig
    for _ in range(12):
        later = _append(later, 1.1, 1.1, 1.1, 1.1)
    assert F.hour_of(int(later.end[-1])) == 5 and not s.exit_now(EUR, later, pos)
    assert s.exit_now(EUR, _append(later, 1.1, 1.1, 1.1, 1.1), pos)
    fri = flat_days(25, start=ep(2025, 2, 10))              # 25 days later is a Friday
    while F.hour_of(int(fri.end[-1])) != 16:
        fri = _append(fri, 1.10, 1.1003, 1.0997, 1.10)
    fsig = _append(fri, 1.10, 1.1012, 1.0999, 1.1010)
    assert ((int(fsig.end[-1]) // 86400) + 3) % 7 == 4 and s.direction(EUR, fsig) is None


def test_ny_cut_breakout_uses_the_pre_cut_range_and_the_first_break_only():
    s = F.NyCutBreakout(range_hours=2, sl_frac=1.0)
    base = flat_days(22, start=ep(2025, 1, 6))              # January: cut at 15:00 UTC
    while F.hour_of(int(base.end[-1])) != 13:
        base = _append(base, 1.10, 1.1003, 1.0997, 1.10)
    pre = _append(_append(base, 1.10, 1.1008, 1.0995, 1.1002), 1.1002, 1.1006, 1.0992, 1.1000)   # range 16 pips
    assert F.hour_of(int(pre.end[-1])) == 15
    assert s.direction(EUR, pre) is None                    # the cut candle itself is not a signal
    first = _append(pre, 1.1000, 1.1015, 1.0998, 1.1012)      # 16:00 close above 1.1008
    assert s.direction(EUR, first) == "MULTUP" and s.stops(EUR, first, "MULTUP") == pytest.approx((16.0, None))
    again = _append(first, 1.1012, 1.1020, 1.1005, 1.1015)    # already broke out: no second signal
    assert s.direction(EUR, again) is None
    late = _append(_append(_append(pre, 1.1, 1.1005, 1.0995, 1.1), 1.1, 1.1005, 1.0995, 1.1), 1.1, 1.102, 1.1, 1.1015)
    assert F.hour_of(int(late.end[-1])) == 18 and s.direction(EUR, late) is None   # past the entry window


def test_prescreen_windows_and_guard():
    ws = P.windows()
    assert len(ws) == 6 and ws[-1].valid_end == dt.date(2026, 10, 26) < UNTOUCHED_START
    assert ws[0].valid_start == dt.date(2023, 10, 27) and ws[-1].train_end == dt.date(2026, 4, 26)
    with pytest.raises(Exception):
        P.market_data("1h", P.DATA_START, UNTOUCHED_START)
    for name, grid in P.IDEAS.values():
        assert name in F.REGISTRY and len(grid) <= P.MAX_VARIANTS and all(len(g) <= 5 for g in grid)


def test_move_and_cost_pips():
    t = {"symbol": EUR, "exit": 1.1020, "entry": 1.1000, "stake": 3.0, "multiplier": 100,
         "commission": 0.0717, "reason": "take_profit", "profit": 0.47}
    mc = P.move_and_cost_pips([t])
    assert mc["avg_abs_move_pips"] == 20.0
    # commission 0.0717 USD on a 300 USD position = 2.63 pips at 1.10, plus 0.5 pip entry slippage
    assert mc["avg_cost_pips"] == pytest.approx(2.63 + 0.5, abs=0.02)
