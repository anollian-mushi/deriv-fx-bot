import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.strategies.base import CancelPending, Enter, ExitPosition, Strategy

MON = dt.date(2025, 3, 3)


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


class Scripted(Strategy):
    """Fires given actions at given candle end times."""
    name = "scripted"

    def __init__(self, plan, timeframe="1h", max_wait=12.0):
        self.plan, self.timeframe, self.max_wait_hours = plan, timeframe, max_wait

    def on_candle(self, symbol, candles, position, pending):
        return self.plan.get((symbol, int(candles.end[-1])), [])


class SmaCross(Strategy):
    name = "sma"
    timeframe = "1h"

    def on_candle(self, symbol, candles, position, pending):
        c = candles.close
        if len(c) < 21:
            return []
        fast, slow = c[-5:].mean(), c[-20:].mean()
        pf, ps = c[-6:-1].mean(), c[-21:-1].mean()
        if pf <= ps and fast > slow:
            return [ExitPosition(), Enter("MULTUP")] if position else [Enter("MULTUP")]
        if pf >= ps and fast < slow:
            return [ExitPosition(), Enter("MULTDOWN")] if position else [Enter("MULTDOWN")]
        return []


def run(strategy, symbols=("frxEURUSD",), days=5, data=None, **kw):
    data = data or data_for(symbols, strategy.timeframe, MON, days)
    e = Engine(strategy, list(symbols), MON, MON + dt.timedelta(days=days), data=data, **kw)
    e.run()
    return e.state


def test_no_look_ahead_future_changes_do_not_change_past_signals():
    data = data_for(["frxEURUSD"], "1h", MON, 12)
    cut = ep(2025, 3, 10, 0)
    m1 = data["frxEURUSD"][0]
    changed = m1.close.copy()
    changed[m1.epoch >= cut] *= 1.05
    m1b = Bars(m1.epoch, m1.end, np.where(m1.epoch >= cut, m1.open * 1.05, m1.open),
               np.where(m1.epoch >= cut, m1.high * 1.05, m1.high),
               np.where(m1.epoch >= cut, m1.low * 1.05, m1.low), changed)
    a = run(SmaCross(), data=data, days=12)
    b = run(SmaCross(), data={"frxEURUSD": (m1b, aggregate(m1b, "1h"))}, days=12)
    before = lambda st: [s for s in st.signals if s[0] <= cut]
    assert before(a) and before(a) == before(b)
    closed_before = lambda st: [t for t in st.trades if t["exit_epoch"] < cut]
    assert closed_before(a) == closed_before(b)


def test_signal_outside_window_waits_and_fills_at_first_allowed_minute():
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 3)): [Enter("MULTUP")]}))
    t = st.trades[0]
    assert t["entry_epoch"] == ep(2025, 3, 4, 6, 0)
    assert t["delay_min"] == 180
    assert st.blocked["outside_entry_window"] == 1


def test_signal_expires_after_max_wait_and_can_be_cancelled():
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 3)): [Enter("MULTUP")]}, max_wait=2.0))
    assert not st.trades and st.refused["expired"] == 1
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 3)): [Enter("MULTUP")],
                       ("frxEURUSD", ep(2025, 3, 4, 4)): [CancelPending()]}))
    assert not st.trades and st.refused["cancelled"] == 1


def test_cost_gate_blocks_noon_hours_and_logs_rate():
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 12)): [Enter("MULTUP")]}))
    # EUR/USD table: 12:00 and 13:00 at 3x base -> first allowed minute 14:00
    assert st.trades[0]["entry_epoch"] == ep(2025, 3, 4, 14, 0)
    assert st.blocked["cost_gate"] == 1
    assert st.gate_skips[0][1] == "frxEURUSD" and st.gate_skips[0][2] == pytest.approx(0.0717)


def test_friday_close_at_20_30_and_x200_at_20_50():
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 7, 10)): [Enter("MULTUP")]}))
    assert st.trades[0]["exit_epoch"] == ep(2025, 3, 7, 20, 30)
    assert st.trades[0]["reason"] == "forced_deadline"
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 10)): [Enter("MULTUP", multiplier=200)]}))
    assert st.trades[0]["exit_epoch"] == ep(2025, 3, 4, 20, 50)


def test_max_two_positions_across_pairs():
    plan = {(s, ep(2025, 3, 4, 10)): [Enter("MULTUP")] for s in ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")}
    st = run(Scripted(plan), symbols=("frxEURUSD", "frxGBPUSD", "frxUSDJPY"))
    entries = sorted((t["entry_epoch"], t["symbol"]) for t in st.trades)
    assert st.blocked["max_positions"] == 1
    assert len(entries) == 2 and entries[0][0] == entries[1][0] == ep(2025, 3, 4, 10)
    # The two open trades run to Friday 20:30, longer than the 12 h wait: the third expires.
    assert st.refused["expired"] == 1


def test_crash_stops_out_with_loss_capped_at_stake():
    data = data_for(["frxEURUSD"], "1h", MON, 5)
    m1 = data["frxEURUSD"][0]
    crash = m1.epoch >= ep(2025, 3, 4, 11)
    f = np.where(crash, 0.97, 1.0)
    m1c = Bars(m1.epoch, m1.end, m1.open * f, m1.high * f, m1.low * f, m1.close * f)
    plan = {("frxEURUSD", ep(2025, 3, 4, 10)): [Enter("MULTUP")]}
    st = run(Scripted(plan), data={"frxEURUSD": (m1c, aggregate(m1c, "1h"))})
    assert st.trades[0]["reason"] == "stop_out"
    assert st.trades[0]["profit"] == -st.trades[0]["stake"]           # loss = stake, never more


def test_kill_switch_triggers_on_equity():
    from fxbot.risk.limits import RiskLimits
    data = data_for(["frxEURUSD"], "1h", MON, 5)
    eng = Engine(Scripted({}), ["frxEURUSD"], MON, MON, data=data, limits=RiskLimits())
    from fxbot.backtest.fills import open_position
    eng.state.balance = 50.5
    pos = open_position("frxEURUSD", "MULTUP", 100, 1.0, 1.1, ep(2025, 3, 3, 10), 0.000239)
    pos.deadline = ep(2025, 3, 7, 20, 30)
    eng.state.positions["frxEURUSD"] = pos
    eng.run()
    # Equity = 50.5 + open loss falls to 50% of 100 -> everything closed, run stopped.
    assert eng.state.killed and eng.state.trades[-1]["reason"] == "kill_switch"
    assert eng.state.timeline_pos < len(eng.timeline) - 1


def test_kill_switch_also_stops_with_no_open_trade():
    data = data_for(["frxEURUSD"], "1h", MON, 5)
    eng = Engine(Scripted({("frxEURUSD", ep(2025, 3, 4, 10)): [Enter("MULTUP")]}), ["frxEURUSD"],
                 MON, MON, data=data)
    eng.state.balance = 50.0
    eng.run()
    assert eng.state.killed and not eng.state.trades


def test_resume_gives_same_result(tmp_path, monkeypatch):
    from fxbot.backtest import engine as eng_mod
    monkeypatch.setattr(eng_mod, "STATE_DIR", tmp_path)
    data = data_for(["frxEURUSD"], "1h", MON, 70)
    full = Engine(SmaCross(), ["frxEURUSD"], MON, MON, data=data)
    full.run()
    part = Engine(SmaCross(), ["frxEURUSD"], MON, MON, data=data, run_name="r1")
    assert part.run(max_seconds=0) is False                 # stopped at the first month boundary
    resumed = Engine(SmaCross(), ["frxEURUSD"], MON, MON, data=data, run_name="r1")
    assert resumed.state.timeline_pos > 0
    assert resumed.run() is True
    assert resumed.state.trades == full.state.trades


def _engine_near_kill(kill_switch):
    from fxbot.backtest.fills import open_position
    data = data_for(["frxEURUSD"], "1h", MON, 5)
    plan = {("frxEURUSD", ep(2025, 3, 5, 10)): [Enter("MULTUP")]}
    eng = Engine(Scripted(plan), ["frxEURUSD"], MON, MON, data=data, kill_switch=kill_switch)
    eng.state.balance = 50.5
    pos = open_position("frxEURUSD", "MULTUP", 100, 1.0, 1.1, ep(2025, 3, 3, 10), 0.000239)
    pos.deadline = ep(2025, 3, 7, 20, 30)
    eng.state.positions["frxEURUSD"] = pos
    return eng


def test_kill_switch_observe_records_resets_balance_and_keeps_running():
    eng = _engine_near_kill("observe")
    eng.run()
    st = eng.state
    assert not st.killed and len(st.kill_events) == 1 and eng.kill_switch_fired
    ev = st.kill_events[0]
    assert ev["equity"] <= 50.0 and st.trades[0]["reason"] == "kill_switch"
    assert ev["top_up"] == round(100.0 - st.trades[0]["balance_after"], 2)
    # Trading carried on after the restart, sized on the reset 100 USD balance.
    later = [t for t in st.trades if t["entry_epoch"] >= ep(2025, 3, 5, 10)]
    assert later and later[0]["stake"] == 3.0
    assert st.timeline_pos == len(eng.timeline)


def test_kill_switch_enforce_is_unchanged_and_default():
    eng = _engine_near_kill("enforce")
    eng.run()
    assert eng.state.killed and not eng.state.kill_events and eng.kill_switch_fired
    assert all(t["entry_epoch"] < ep(2025, 3, 5) for t in eng.state.trades)
    with pytest.raises(ValueError):
        Engine(Scripted({}), ["frxEURUSD"], MON, MON, data=data_for(["frxEURUSD"], "1h", MON, 2),
               kill_switch="off")


def test_metrics_use_real_balance_across_restarts():
    from fxbot.backtest.metrics import summarise
    trades = [{"profit": -50.0, "balance_after": 50.0, "commission": 0.02},
              {"profit": 10.0, "balance_after": 110.0, "commission": 0.02}]   # reset to 100 between
    s = summarise(trades, 100.0)
    assert s["net_profit"] == -40.0 and s["net_return_pct"] == -40.0 and s["final_balance"] == 110.0
