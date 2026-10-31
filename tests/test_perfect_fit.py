"""Perfect-fit experiment: features see no future candles, fast sim matches fills.py,
and the strategy keeps to its hours and exit rules."""

import datetime as dt
import json

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot.backtest import fastsim, fills
from fxbot.strategies.base import Enter, ExitPosition, PositionView
from fxbot.strategies.pf_features import FEATURE_NAMES, features

numba = pytest.importorskip("numba")
SYMS = ["frxEURUSD", "frxGBPUSD", "frxUSDJPY"]


@pytest.fixture(scope="module")
def data():
    return data_for(SYMS, "1h", dt.date(2024, 1, 1), 40)


def _peers(data, sym, t):
    return {s: data[s][1].slice(int(np.searchsorted(data[s][1].end, t, "right"))) for s in SYMS if s != sym}


def test_features_use_only_closed_candles(data):
    c = data["frxEURUSD"][1]
    i = 400
    t = int(c.end[i])
    a = features("frxEURUSD", c.slice(i + 1), _peers(data, "frxEURUSD", t))
    # Change every later candle wildly: the features at t must not move.
    fut = {s: (m1, type(tf)(*(x.copy() for x in (tf.epoch, tf.end, tf.open, tf.high, tf.low, tf.close))))
           for s, (m1, tf) in data.items()}
    for s, (_, tf) in fut.items():
        j = int(np.searchsorted(tf.end, t, "right"))
        for arr in (tf.open, tf.high, tf.low, tf.close):
            arr[j:] *= 1.5
    c2 = fut["frxEURUSD"][1]
    b = features("frxEURUSD", c2.slice(i + 1), _peers(fut, "frxEURUSD", t))
    assert len(a) == len(FEATURE_NAMES)
    np.testing.assert_array_equal(a, b)


@pytest.mark.parametrize("cfg", [(100, 20, 30, 4), (200, 0, 0, 0), (100, 0, 50, 0), (100, 10, 0, 2)])
def test_fast_sim_matches_fills(data, cfg):
    m1, tf = data["frxEURUSD"]
    mult, sl, tp, hold = cfg
    rate = 0.000239
    for j0 in range(2000, 20000, 1500):
        t0 = int(m1.epoch[j0])
        from fxbot import sessions
        dl = sessions.exit_deadline(t0, mult)
        t_exit = t0 + hold * 3600 if hold else 2 ** 62
        for up in (True, False):
            p, x = fastsim._one(m1.epoch, m1.open, m1.high, m1.low, j0, dl, t_exit, up, float(mult), rate,
                                1e-4, float(sl), float(tp))
            pos = fills.open_position("frxEURUSD", "MULTUP" if up else "MULTDOWN", mult, 1000.0,
                                      float(m1.open[j0]), t0, rate, sl or None, tp or None)
            ex = None
            for j in range(j0, len(m1)):
                t = int(m1.epoch[j])
                if j > j0 and (t >= t_exit or t >= dl):
                    ex = fills.close_at(pos, t, float(m1.open[j]), "x")
                    break
                o = pos.entry if j == j0 else float(m1.open[j])
                ex = fills.check_bar(pos, t, o, float(m1.high[j]), float(m1.low[j]), float(m1.close[j]))
                if ex:
                    break
            assert ex is not None and ex.epoch == x
            assert ex.profit / 1000.0 == pytest.approx(p, abs=0.003)


def test_portfolio_limits():
    # three overlapping trades on three pairs: only two may be open at once
    t_in = np.array([0, 10, 20], dtype=np.int64)
    t_out = np.array([100, 100, 100], dtype=np.int64)
    sym = np.array([0, 1, 2], dtype=np.int64)
    net, dd, n, killed = fastsim.portfolio(t_in, t_out, sym, np.array([0.5, 0.5, 0.5]))
    assert n == 2 and not killed
    # one pair twice at once: the second is refused
    _, _, n, _ = fastsim.portfolio(t_in[:2], t_out[:2], np.array([0, 0]), np.array([0.5, 0.5]))
    assert n == 1


def _strategy(tmp_path, hold=3, thr=0.1):
    from fxbot.strategies.perfect_fit import PerfectFit
    spec = {"model": {"kind": "rule"}, "exit": {"mult": 100, "sl": 20, "tp": 30, "hold": hold},
            "threshold": thr,
            "rule": {"f": [FEATURE_NAMES.index("hour")], "thr": [[-1, -1, -1]], "above": [True], "sign": 1}}
    (tmp_path / "spec.json").write_text(json.dumps(spec))
    return PerfectFit(model_dir=tmp_path)


def test_strategy_hours_and_exit(tmp_path, data):
    s = _strategy(tmp_path)
    c = data["frxEURUSD"][1]
    seen_hours = set()
    for i in range(300, 670):
        t = int(c.end[i])
        s.peers = _peers(data, "frxEURUSD", t)
        acts = s.on_candle("frxEURUSD", c.slice(i + 1), None, False)
        if acts:
            assert isinstance(acts[0], Enter) and acts[0].multiplier == 100
            assert acts[0].stop_loss_pips == 20 and acts[0].take_profit_pips == 30
            seen_hours.add((t % 86400) // 3600)
    assert seen_hours == {6, 7, 8, 9, 10, 11, 14, 15, 16, 17}   # no 12:00, no 13:00 on EUR/USD
    i = 500
    t = int(c.end[i])
    pos = PositionView("MULTUP", 100, 1.1, t - 3 * 3600)
    assert s.on_candle("frxEURUSD", c.slice(i + 1), pos, False) == [ExitPosition()]
    pos = PositionView("MULTUP", 100, 1.1, t - 2 * 3600)
    assert s.on_candle("frxEURUSD", c.slice(i + 1), pos, False) == []


def test_strategy_waits_for_trade_from(tmp_path, data):
    s = _strategy(tmp_path)
    c = data["frxGBPUSD"][1]
    s.trade_from = int(c.end[-1]) + 1
    for i in range(300, 500):
        s.peers = _peers(data, "frxGBPUSD", int(c.end[i]))
        assert s.on_candle("frxGBPUSD", c.slice(i + 1), None, False) == []
