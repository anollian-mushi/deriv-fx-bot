"""Engine support added for the TJR test (owner, 2 Nov 2026): intraday timeframes, the 4x-cost
stop rule, the stop-beyond-stop-out skip and Deriv's stop-loss update (near break-even)."""

import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot import sessions
from fxbot.backtest import fills
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.contracts import multiplier as mc
from fxbot.strategies.base import Enter, Strategy, max_wait_seconds

SYM = "frxEURUSD"
DAY = dt.date(2025, 1, 14)            # a Tuesday
T0 = sessions.day_start(DAY) + 8 * 3600


class OneShot(Strategy):
    """Enters once, at the candle that closes at `at`."""
    name = "one_shot"

    def __init__(self, timeframe, at, **enter):
        self.timeframe, self.at, self.enter = timeframe, at, enter

    def on_candle(self, symbol, candles, position, pending):
        if int(candles.end[-1]) == self.at and symbol == SYM:
            return [Enter(**{"direction": "MULTUP", "multiplier": 200, **self.enter})]
        return []


def path_m1(points: list[tuple[int, float]], day=DAY) -> Bars:
    """1m candles for a whole trading day, price linear between (minute of day, price) points."""
    s0 = sessions.day_start(day)
    e = np.array([s0 + 60 * m for m in range(1440) if sessions.market_open(s0 + 60 * m)], dtype=np.int64)
    mins = (e - s0) / 60
    xs, ys = zip(*points)
    o = np.interp(mins, xs, ys)
    c = np.interp(mins + 1, xs, ys)
    return Bars(e, e + 60, o, np.maximum(o, c), np.minimum(o, c), c)


def run(strategy, m1: Bars, symbols=(SYM,)):
    data = {s: (m1, aggregate(m1, strategy.timeframe)) for s in symbols}
    eng = Engine(strategy, list(symbols), DAY, DAY, data=data)
    eng.run()
    return eng


def test_intraday_timeframes_wait_two_minutes_and_daily_ones_are_unchanged():
    for tf in ("1m", "5m", "15m"):
        assert max_wait_seconds(OneShot(tf, 0)) == 120
    assert max_wait_seconds(OneShot("1h", 0)) == 3600
    with pytest.raises(ValueError):
        max_wait_seconds(OneShot("30m", 0))


@pytest.mark.parametrize("tf,sec", [("1m", 60), ("5m", 300), ("15m", 900)])
def test_intraday_signal_fills_at_the_next_minute_open(tf, sec):
    m1 = path_m1([(0, 1.1000), (1440, 1.1000)])
    at = T0 + sec
    eng = run(OneShot(tf, at, stop_loss_pips=30, take_profit_pips=30), m1)
    assert len(eng.state.trades) == 1
    assert eng.state.trades[0]["entry_epoch"] == at


def test_intraday_signal_blocked_longer_than_two_minutes_is_dropped():
    # 06:00 UTC opens the entry window; a 1m signal at 05:55 must not wait until 06:00.
    m1 = path_m1([(0, 1.1000), (1440, 1.1000)])
    eng = run(OneShot("1m", sessions.day_start(DAY) + 5 * 3600 + 55 * 60, stop_loss_pips=30), m1)
    assert eng.state.trades == []
    assert eng.state.refused["expired"] == 1


def test_cost_floor_skips_tight_stops_at_the_measured_rate():
    m1 = path_m1([(0, 1.1000), (1440, 1.1000)])
    rate = fills.CommissionTable().rate(SYM, T0 + 60)
    cost = fills.cost_pips(SYM, 1.1000, rate)
    assert 3.0 < cost < 3.6                       # about 2.6-2.8 pips commission + 0.5 slippage
    tight = run(OneShot("1m", T0 + 60, stop_loss_pips=3.9 * cost, min_stop_cost_multiple=4.0), m1)
    assert tight.state.trades == [] and tight.state.refused["stop_under_cost_floor"] == 1
    ok = run(OneShot("1m", T0 + 60, stop_loss_pips=4.1 * cost, min_stop_cost_multiple=4.0), m1)
    assert len(ok.state.trades) == 1
    # judged at the measured rate even in the 1.5x run, so both runs keep the same trades
    data = {SYM: (m1, aggregate(m1, "1m"))}
    eng = Engine(OneShot("1m", T0 + 60, stop_loss_pips=4.1 * cost, min_stop_cost_multiple=4.0), [SYM],
                 DAY, DAY, data=data, stress=1.5)
    eng.run()
    assert len(eng.state.trades) == 1


def test_require_stop_skips_a_stop_beyond_the_stop_out():
    m1 = path_m1([(0, 1.1000), (1440, 1.1000)])
    # x200 stops out after about 0.5% (55 pips at 1.10): a 70-pip stop would never be the exit
    eng = run(OneShot("1m", T0 + 60, stop_loss_pips=70, require_stop=True), m1)
    assert eng.state.trades == [] and eng.state.refused["stop_beyond_stop_out"] == 1
    old = run(OneShot("1m", T0 + 60, stop_loss_pips=70), m1)          # without the flag: unchanged
    assert len(old.state.trades) == 1 and old.state.trades[0]["sl_amount"] is None


def _be_path(peak_pips: float):
    m = 8 * 60 + 1          # entry minute (08:01 open)
    return path_m1([(0, 1.1000), (m, 1.1000), (m + 10, 1.1000 + peak_pips * 1e-4),
                    (m + 30, 1.0960), (1440, 1.0960)])


def test_stop_moves_near_break_even_after_1r_and_then_fills_there():
    eng = run(OneShot("1m", T0 + 60, stop_loss_pips=20, take_profit_pips=100, move_stop_at_r=1.0), _be_path(25))
    (t,) = eng.state.trades
    assert t["reason"] == "stop_loss" and t["stop_moved_time"] is not None
    min_amount = round(t["commission"] + 0.02, 2)
    size = t["stake"] * t["multiplier"]
    expected = -(min_amount + size * 1e-4 / t["entry"])           # Deriv's smallest stop + 1 pip slippage
    assert t["profit"] == pytest.approx(expected, abs=0.011)
    # the same trade without the update loses the full 20 pips (+1 pip slippage)
    plain = run(OneShot("1m", T0 + 60, stop_loss_pips=20, take_profit_pips=100), _be_path(25))
    assert plain.state.trades[0]["profit"] < t["profit"] - 0.5 * size * 20e-4 / t["entry"]
    assert plain.state.trades[0]["stop_moved_time"] is None


def test_stop_does_not_move_before_1r():
    eng = run(OneShot("1m", T0 + 60, stop_loss_pips=20, take_profit_pips=100, move_stop_at_r=1.0), _be_path(15))
    (t,) = eng.state.trades
    assert t["stop_moved_time"] is None and t["sl_pips"] == 20


def test_stop_update_takes_effect_only_from_the_next_minute():
    # One minute rises 25 pips and falls back below the entry inside the same candle: the old stop
    # is still the one that counts in that minute.
    m = 8 * 60 + 1
    s0 = sessions.day_start(DAY)
    m1 = path_m1([(0, 1.1000), (1440, 1.1000)])
    i = int(np.searchsorted(m1.epoch, s0 + 60 * (m + 3)))
    m1.high[i] = 1.1025
    m1.low[i] = 1.0995
    eng = run(OneShot("1m", T0 + 60, stop_loss_pips=20, take_profit_pips=100, move_stop_at_r=1.0), m1)
    (t,) = eng.state.trades
    assert t["stop_moved_time"] == dt.datetime.fromtimestamp(s0 + 60 * (m + 4), dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
    assert t["reason"] != "stop_loss" or t["exit_epoch"] > s0 + 60 * (m + 3)


def test_move_stop_near_breakeven_contract_math():
    p = fills.open_position(SYM, "MULTDOWN", 200, 3.0, 1.1000, T0, 0.000239, stop_loss_pips=20)
    old = p.sl_price
    assert fills.move_stop_near_breakeven(p)
    assert p.sl_amount == round(p.commission + 0.02, 2)
    assert p.sl_price < old and p.sl_price > p.entry           # a short's stop sits just above entry
    assert mc.profit(p.direction, p.stake, p.multiplier, p.entry, p.sl_price, p.commission) == \
        pytest.approx(-p.sl_amount, abs=0.006)
    assert not fills.move_stop_near_breakeven(p)                # already there: nothing to tighten


def test_merged_commission_table(tmp_path):
    import json
    a = json.loads(fills.COST_TABLE.read_text())
    b = {"base_rate_pct": {"frxGBPJPY": 0.03}, "hours": {str(h): {"max_rate_pct": None if h == 21 else {"frxGBPJPY": 0.03}}
                                                          for h in range(24)}}
    pb = tmp_path / "b.json"
    pb.write_text(json.dumps(b))
    t = fills.CommissionTable.merged([fills.COST_TABLE, pb])
    assert t.base["frxGBPJPY"] == pytest.approx(0.0003) and t.base[SYM] == pytest.approx(a["base_rate_pct"][SYM] / 100)
    assert t.rate("frxGBPJPY", T0) == pytest.approx(0.0003) and t.rate(SYM, T0) is not None
    assert t.rate("frxGBPJPY", sessions.day_start(DAY) + 21 * 3600) is None
    with pytest.raises(ValueError):
        fills.CommissionTable.merged([fills.COST_TABLE, fills.COST_TABLE])


def test_existing_strategies_unaffected_by_new_enter_fields():
    e = Enter("MULTUP")
    assert e.min_stop_cost_multiple is None and not e.require_stop and e.move_stop_at_r is None
    data = data_for([SYM], "1h", DAY, 3)
    eng = Engine(OneShot("1h", T0 + 3600, stop_loss_pips=30, take_profit_pips=30), [SYM], DAY,
                 DAY + dt.timedelta(days=2), data=data)
    eng.run()
    assert len(eng.state.trades) == 1 and eng.state.trades[0]["stop_moved_time"] is None
