"""TJR rules (docs/tjr_rules.md as approved 2 Nov 2026): calendar, building blocks, the four
entry models on a hand-built EUR/USD morning, the luck replay and no look-ahead."""

import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot import sessions
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.strategies import tjr
from fxbot.strategies import tjr_calendar as cal
from fxbot.strategies.base import Enter, ExitPosition

UTC = dt.timezone.utc


def at(y, m, d, hh, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=UTC).timestamp())


# ----------------------------------------------------------------------------- calendar
def test_session_windows_follow_new_york_summer_time():
    assert cal.day_windows(dt.date(2025, 1, 14))["london"] == (at(2025, 1, 14, 7), at(2025, 1, 14, 10))
    assert cal.day_windows(dt.date(2025, 1, 14))["newyork"] == (at(2025, 1, 14, 12), at(2025, 1, 14, 16))
    assert cal.day_windows(dt.date(2025, 7, 15))["london"] == (at(2025, 7, 15, 6), at(2025, 7, 15, 9))
    assert cal.day_windows(dt.date(2025, 7, 15))["newyork"] == (at(2025, 7, 15, 11), at(2025, 7, 15, 15))
    # Asian range: 20:00-00:00 New York the evening before
    assert cal.day_windows(dt.date(2025, 1, 14))["asia_range"] == (at(2025, 1, 14, 1), at(2025, 1, 14, 5))
    # both windows always inside the CLAUDE.md entry window 06:00-17:59 UTC
    d = dt.date(2021, 10, 27)
    while d < dt.date(2026, 10, 31):
        for name in ("london", "newyork"):
            a, b = cal.day_windows(d)[name]
            assert sessions.in_entry_window(a) and sessions.in_entry_window(b - 60)
        d += dt.timedelta(days=1)


def test_session_at():
    assert cal.session_at(at(2025, 1, 14, 7, 30))[0] == "london"
    assert cal.session_at(at(2025, 1, 14, 10, 0))[0] is None
    assert cal.session_at(at(2025, 1, 14, 15, 59))[0] == "newyork"
    assert cal.session_at(at(2025, 7, 15, 15, 0))[0] is None


def test_news_blocks_by_currency_and_local_time():
    # USD: 08:15-09:00 New York = 13:15-14:00 UTC in winter, 12:15-13:00 in summer
    assert cal.news_blocked("frxEURUSD", at(2025, 1, 14, 13, 15))
    assert not cal.news_blocked("frxEURUSD", at(2025, 1, 14, 13, 14))
    assert not cal.news_blocked("frxEURUSD", at(2025, 1, 14, 14, 0))
    assert cal.news_blocked("frxUSDJPY", at(2025, 7, 15, 12, 30))
    # the old 09:45-10:30 block is gone (owner, 2 Nov 2026)
    assert not cal.news_blocked("frxEURUSD", at(2025, 1, 14, 14, 50))
    # GBP: 06:45-07:30 London = UTC in winter, 05:45-06:30 UTC in summer
    assert cal.news_blocked("frxGBPJPY", at(2025, 1, 14, 7, 0))
    assert cal.news_blocked("frxEURGBP", at(2025, 7, 15, 6, 0))
    assert not cal.news_blocked("frxEURGBP", at(2025, 1, 14, 13, 30))     # no USD in EUR/GBP
    assert not cal.news_blocked("frxEURJPY", at(2025, 1, 14, 13, 30))
    assert not cal.news_blocked("frxEURJPY", at(2025, 1, 14, 7, 0))
    assert cal.news_blocked("frxGBPUSD", at(2025, 1, 14, 7, 0)) and cal.news_blocked("frxGBPUSD", at(2025, 1, 14, 13, 30))


def test_us_bank_holidays():
    assert cal.us_bank_holidays(2025) == frozenset({
        dt.date(2025, 1, 1), dt.date(2025, 1, 20), dt.date(2025, 2, 17), dt.date(2025, 5, 26),
        dt.date(2025, 6, 19), dt.date(2025, 7, 4), dt.date(2025, 9, 1), dt.date(2025, 10, 13),
        dt.date(2025, 11, 11), dt.date(2025, 11, 27), dt.date(2025, 12, 25)})
    assert cal.is_us_bank_holiday(dt.date(2021, 7, 5))          # 4 July 2021 was a Sunday
    assert cal.is_us_bank_holiday(dt.date(2022, 6, 20))         # Juneteenth 2022 was a Sunday
    assert not cal.is_us_bank_holiday(dt.date(2021, 6, 18))     # Juneteenth not yet a Fed holiday
    assert not cal.is_us_bank_holiday(dt.date(2026, 7, 3))      # Saturday holiday: Fed open on Friday


def test_entry_allowed():
    assert cal.entry_allowed("frxEURUSD", at(2025, 1, 14, 8)) == (True, "")
    assert cal.entry_allowed("frxEURUSD", at(2025, 1, 14, 11))[1] == "outside_session"
    assert cal.entry_allowed("frxEURUSD", at(2025, 1, 14, 13, 30))[1] == "news"
    assert cal.entry_allowed("frxEURUSD", at(2025, 1, 20, 8))[1] == "us_bank_holiday"


# ----------------------------------------------------------------------------- building blocks
def _series(highs, lows, sec=300):
    s = tjr._Series(sec)
    for k, (h, lo) in enumerate(zip(highs, lows)):
        s.add(k * sec, (h + lo) / 2, h, lo, (h + lo) / 2, (k + 1) * sec)
    return s


def test_series_aggregates_closed_candles_on_utc_boundaries():
    s = tjr._Series(300)
    closed = []
    for m in range(12):
        closed += s.add(m * 60, 1.0 + m, 1.5 + m, 0.5 + m, 1.2 + m, (m + 1) * 60)
    assert closed == [0, 1] and len(s) == 2
    assert s.get(0) == (0, 1.0, 5.5, 0.5, 5.2)
    # a missing last minute: the candle closes when the next bucket starts
    s2 = tjr._Series(300)
    out = []
    for m in (0, 1, 2, 3, 5):
        out += s2.add(m * 60, 1.0, 2.0, 0.5, 1.0, (m + 1) * 60)
    assert out == [0]


def test_swings_strength_one_and_two_with_ties_to_the_later_candle():
    highs = [1.0, 1.2, 1.1, 1.1, 1.3, 1.3, 1.0]
    s = _series(highs, [h - 0.5 for h in highs])
    sw = tjr._Swings(1)
    for i in range(len(highs)):
        sw.update(s, i)
    assert [(k, p) for k, p, _ in sw.highs] == [(1, 1.2), (5, 1.3)]       # equal highs: the later one
    assert sw.highs[0][2] == 2                                              # known one candle later
    s2 = _series([1, 2, 3, 2, 1, 2, 5], [0] * 7)
    sw2 = tjr._Swings(2)
    for i in range(7):
        sw2.update(s2, i)
    assert [(k, p) for k, p, _ in sw2.highs] == [(2, 3)]


def test_bias_is_the_direction_of_the_last_break():
    b = tjr._Bias()
    closes = [1, 2, 3, 2, 1, 2, 4, 3, 2, 1, 0.5]
    s = tjr._Series(14400)
    for k, c in enumerate(closes):
        s.add(k * 14400, c, c + 0.1, c - 0.1, c, (k + 1) * 14400)
        b.update(s, k)
        if k == 6:
            assert b.bias == 1                  # closed above the swing high at 3.1
    assert b.bias == -1                         # then below the swing low at 0.9


# ----------------------------------------------------------------------------- a hand-built morning
SYM = "frxEURUSD"


def _m1_path(points, wicks=None):
    """1m candles (Mon 13 and Tue 14 Jan 2025), linear between (epoch, price) points, 0.1-pip wicks;
    wicks = {candle start epoch: high} adds a longer upper wick to one candle."""
    e0, e1 = at(2025, 1, 13, 0), at(2025, 1, 15, 0)
    e = np.array([t for t in range(e0, e1, 60) if sessions.market_open(t)], dtype=np.int64)
    xs, ys = zip(*points)
    o = np.interp(e, xs, ys)
    c = np.interp(e + 60, xs, ys)
    h = np.maximum(o, c) + 1e-5
    for t, v in (wicks or {}).items():
        h[int(np.searchsorted(e, t))] = v
    return Bars(e, e + 60, o, h, np.minimum(o, c) - 1e-5, c)


T = lambda hh, mm=0: at(2025, 1, 14, hh, mm)
MORNING = [
    (at(2025, 1, 13, 0), 1.1000), (at(2025, 1, 13, 12), 1.0900), (at(2025, 1, 13, 23, 59), 1.1000),  # PDL 1.0900
    (T(0), 1.1000), (T(1), 1.1000), (T(2), 1.1010), (T(3), 1.0980), (T(4), 1.1000), (T(7), 1.0998),   # Asia 1.0980-1.1010
    (T(7, 7), 1.0990),                       # 5m swing low (the higher low before the sweep)
    (T(7, 15), 1.1005), (T(7, 22), 1.1020),  # sweep of the Asian high, wick to 1.1020
    (T(7, 29), 1.1004), (T(7, 30), 1.1004),  # 30m candle closes back below 1.1010
    (T(7, 35), 1.0995), (T(7, 38), 1.0950), (T(7, 40), 1.0985),   # 07:35-07:40 closes below 1.0990: BOS
    (T(7, 44), 1.0998), (T(7, 46), 1.0994),  # back up into the FVG 1.0995-1.1004, 1m swing high 1.0998
    (T(7, 48), 1.0997), (T(7, 49), 1.0996),  # the 07:48 candle wicks to 1.1001 (WICKS): a 1m sweep of 1.0998
    (T(7, 52), 1.0985), (T(9), 1.0940), (T(12), 1.0920), (T(23, 59), 1.0920),
]


WICKS = {T(7, 48): 1.1001}


def _feed(strategy, m1, symbol=SYM):
    if strategy.timeframe != "1m":
        m1 = aggregate(m1, strategy.timeframe)
    st = strategy.state[symbol] = tjr._Sym(strategy.base_sec, strategy.exec_sec)
    st.bias4.bias = st.bias1.bias = -1
    out = []
    for i in range(len(m1)):
        acts = strategy.on_candle(symbol, m1.slice(i + 1), None, False)
        out += [(int(m1.end[i]), a) for a in acts if isinstance(a, Enter)]
    return out


@pytest.fixture
def fixed_bias(monkeypatch):
    monkeypatch.setattr(tjr._Bias, "update", lambda self, ser, i: None)


def test_model_1_short_after_sweep_and_break(fixed_bias):
    sigs = _feed(tjr.TJR5m(model=1, n=12), _m1_path(MORNING, WICKS))
    assert len(sigs) == 1
    t, e = sigs[0]
    assert t == T(7, 40) and e.direction == "MULTDOWN" and e.multiplier == 200
    entry = 1.0985 - 0.00005
    assert e.stop_loss_pips == pytest.approx((1.10201 + 0.0001 - entry) / 1e-4, abs=0.02)   # wick + 1 pip
    assert e.take_profit_pips == pytest.approx((entry - 1.08999) / 1e-4, abs=0.02)           # previous day low
    assert e.min_stop_cost_multiple == 4.0 and e.require_stop and e.move_stop_at_r is None


def test_model_1_needs_the_break_within_n_candles(fixed_bias):
    s = tjr.TJR5m(model=1, n=1)            # the break comes 2 execution candles after the sweep
    assert _feed(s, _m1_path(MORNING, WICKS)) == []
    assert s.stats["cancel_no_bos_in_time"] == 1


def test_no_trade_against_the_bias(fixed_bias):
    s = tjr.TJR5m(model=1)
    m1 = _m1_path(MORNING, WICKS)
    st = s.state[SYM] = tjr._Sym(60, 300)
    st.bias4.bias, st.bias1.bias = -1, 1          # daily and 4h disagree
    for i in range(len(m1)):
        assert not [a for a in s.on_candle(SYM, m1.slice(i + 1), None, False) if isinstance(a, Enter)]
    assert s.stats["sweep_against_bias"] >= 1


def test_model_3_waits_for_a_1m_sweep_and_break_inside_the_fvg(fixed_bias):
    sigs = _feed(tjr.TJR5m(model=3, n=12), _m1_path(MORNING, WICKS))
    assert len(sigs) == 1
    t, e = sigs[0]
    assert t == T(7, 50)                        # the 1m candle that closed below the 1m swing low 1.0994
    entry = (1.0996 - (1.0996 - 1.0985) / 3) - 0.00005
    assert e.stop_loss_pips == pytest.approx((1.10211 - entry) / 1e-4, abs=0.05)    # still the 30m wick


def test_model_3_touch_alternative_enters_at_the_execution_close(fixed_bias):
    sigs = _feed(tjr.TJR5m(model=3, n=12, confirm="touch"), _m1_path(MORNING, WICKS))
    assert [t for t, _ in sigs] == [T(7, 45)]   # 07:40-07:45 reached 1.0998 and closed inside the zone


def test_model_2_order_block_is_the_last_up_candle_into_the_sweep(fixed_bias):
    s = tjr.TJR5m(model=2, n=12)
    assert _feed(s, _m1_path(MORNING, WICKS)) == []    # price never returns to 1.1005-1.1016
    assert s.stats["cancel_no_retrace_in_time"] == 1 or s.stats["cancel_session_ended"] == 1


def test_model_4_needs_the_zone_in_premium(fixed_bias):
    s = tjr.TJR5m(model=4, n=12)
    sigs = _feed(s, _m1_path(MORNING, WICKS))
    # equilibrium of 1.1020 .. 1.0950 is 1.0985: the FVG 1.0995-1.1004 lies wholly above it
    assert [t for t, _ in sigs] == [T(7, 50)]


def test_no_entry_in_the_us_news_window_or_on_a_us_holiday(fixed_bias):
    # move the same morning to the New York session news slot: 13:00 UTC sweep, 13:40 break
    shift = 6 * 3600
    pts = [(t + shift if t >= T(5) else t, p) for t, p in MORNING]
    s = tjr.TJR5m(model=1)
    assert _feed(s, _m1_path(pts, WICKS)) == []
    assert s.stats["skip_news"] == 1


def test_flat_at_17_55_utc():
    s = tjr.TJR5m(model=1)
    m1 = _m1_path(MORNING, WICKS)
    i = int(np.searchsorted(m1.end, T(17, 55)))
    from fxbot.strategies.base import PositionView
    pos = PositionView("MULTDOWN", 200, 1.0985, T(7, 41))
    assert any(isinstance(a, ExitPosition) for a in s.on_candle(SYM, m1.slice(i + 1), pos, False))
    assert not any(isinstance(a, ExitPosition) for a in s.on_candle(SYM, m1.slice(i), pos, False))


def test_breakeven_variant_sets_the_stop_rule(fixed_bias):
    (_, e), = _feed(tjr.TJR5m(model=1, breakeven=True), _m1_path(MORNING, WICKS))
    assert e.move_stop_at_r == 1.0


def test_tjr15m_runs_on_5m_candles(fixed_bias):
    s = tjr.TJR15m(model=1, n=6)
    _feed(s, _m1_path(MORNING, WICKS))
    assert s.stats["setups"] == 1


def test_settings_are_checked():
    with pytest.raises(ValueError):
        tjr.TJR5m(model=5)
    with pytest.raises(ValueError):
        tjr.TJR5m(confirm="maybe")
    assert len(tjr.TJR5m.defaults) <= 5


# ----------------------------------------------------------------------------- engine-level checks
def test_no_look_ahead_future_changes_do_not_change_past_signals():
    syms = ["frxEURUSD", "frxGBPUSD"]
    start = dt.date(2025, 1, 6)
    data = data_for(syms, "1m", start, 40, seed=3)
    cut = at(2025, 1, 30, 0)
    changed = {}
    for s, (m1, _) in data.items():
        b = Bars(*(a.copy() for a in (m1.epoch, m1.end, m1.open, m1.high, m1.low, m1.close)))
        k = b.epoch >= cut
        b.open[k] += 0.01
        b.high[k] += 0.02
        b.low[k] += 0.005
        b.close[k] += 0.015
        changed[s] = (b, aggregate(b, "1m"))
    runs = []
    for d in (data, changed):
        eng = Engine(tjr.TJR5m(model=1), syms, start, start + dt.timedelta(days=40), data=d)
        eng.run()
        runs.append([x for x in eng.state.signals if x[0] < cut])
    assert runs[0] == runs[1]


def test_replay_keeps_signals_and_tosses_directions():
    e = Enter("MULTDOWN", multiplier=200, stop_loss_pips=20.5, take_profit_pips=41.0,
              min_stop_cost_multiple=4.0, require_stop=True, move_stop_at_r=1.0)
    assert eval(repr(e), {"Enter": Enter}) == e
    sigs = {(SYM, 1000 + 60 * k): e for k in range(200)}
    r = tjr.TJRReplay("1m", sigs, seed=7, symbols=(SYM,))
    dirs = []
    for k in range(200):
        bars = Bars(*(np.array([v]) for v in (940 + 60 * k, 1000 + 60 * k, 1.1, 1.1, 1.1, 1.1)))
        (a,) = r.on_candle(SYM, bars, None, False)
        assert (a.stop_loss_pips, a.take_profit_pips, a.multiplier, a.move_stop_at_r) == (20.5, 41.0, 200, 1.0)
        dirs.append(a.direction)
    assert 70 < dirs.count("MULTUP") < 130
    r2 = tjr.TJRReplay("1m", sigs, seed=7, symbols=(SYM,))
    bars = Bars(*(np.array([v]) for v in (940, 1000, 1.1, 1.1, 1.1, 1.1)))
    assert r2.on_candle(SYM, bars, None, False)[0].direction == dirs[0]
