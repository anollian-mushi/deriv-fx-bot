import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot.backtest import research as R
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.strategies import families as F

MON = dt.date(2025, 3, 3)


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


def bars(closes, start=ep(2025, 3, 3), step=3600, spread=0.0002):
    c = np.asarray(closes, dtype=float)
    e = start + step * np.arange(len(c))
    o = np.r_[c[0], c[:-1]]
    return Bars(e, e + step, o, np.maximum(o, c) + spread, np.minimum(o, c) - spread, c)


def test_grids_within_budget_and_parameter_limit():
    for fam, subs in R.FAMILIES.items():
        assert sum(len(g) for _, g in subs) <= 30
        for name, grid in subs:
            assert name in F.REGISTRY
            assert all(len(p) <= 5 for p in grid)
            assert len({tuple(sorted(p.items())) for p in grid}) == len(grid)


@pytest.mark.parametrize("name", sorted(F.REGISTRY))
def test_no_look_ahead(name):
    cls = F.REGISTRY[name]
    long_history = cls.timeframe == "1d" or cls.family == "f3"     # needs ~50 days first
    days = 120 if long_history else 45
    data = data_for(["frxEURUSD"], cls.timeframe, MON, days, seed=3)
    cut = ep(2025, 6, 10) if long_history else ep(2025, 4, 1)
    m1 = data["frxEURUSD"][0]
    f = np.where(m1.epoch >= cut, 1.03, 1.0)
    m1b = Bars(m1.epoch, m1.end, m1.open * f, m1.high * f, m1.low * f, m1.close * f)
    a = _run(cls(), data)
    b = _run(cls(), {"frxEURUSD": (m1b, aggregate(m1b, cls.timeframe))})
    before = lambda st: [s for s in st.signals if s[0] < cut]
    assert before(a) == before(b)
    assert before(a) or cls.timeframe == "1d"      # daily breakouts may not fire in 4 weeks


def _run(strategy, data):
    e = Engine(strategy, list(data), MON, MON, data=data)
    e.run()
    return e.state


def test_atr_and_daily_closes():
    b = bars([1.0, 1.001, 1.002, 1.001], spread=0.0)
    assert F.atr(b, 3) == pytest.approx(0.001)
    # 30 hourly candles from Monday 00:00: Monday complete (24), Tuesday unfinished.
    b = bars(np.arange(30) * 0.0001 + 1.0)
    dc = F.daily_closes(b, 5)
    assert len(dc) == 1 and dc[-1] == pytest.approx(1.0 + 23 * 0.0001)


def test_trend_breakout_direction_and_trailing_exit():
    s = F.TrendBreakout(n=5, m=3, sl_atr=2.0)
    up = bars([1.0, 1.001, 1.0005, 1.001, 1.0008, 1.0009, 1.003], step=4 * 3600)
    assert s.direction("frxEURUSD", up) == "MULTUP"
    dn = bars([1.0, 1.001, 1.0005, 1.001, 1.0008, 1.0009, 0.998], step=4 * 3600)
    assert s.direction("frxEURUSD", dn) == "MULTDOWN"
    pos = F.PositionView("MULTUP", 100, 1.0, 0)
    assert s.exit_now("frxEURUSD", dn, pos)


def test_london_breakout_one_signal_per_day_and_box_stops():
    # Monday 00:00-07:00 range 1.1000-1.1015, then a close above at the 08:00 candle close.
    closes = [1.1005, 1.1015, 1.1000, 1.1010, 1.1005, 1.1008, 1.1007, 1.1030, 1.1040]
    b = bars(closes, spread=0.0)
    s = F.LondonBreakout(box_start=0, cutoff=11, sl_frac=0.5, tp_mult=2.0)
    first, second = b.slice(8), b.slice(9)        # candles ending 08:00 and 09:00
    assert s.direction("frxEURUSD", first) == "MULTUP"
    sl, tp = s.stops("frxEURUSD", first, "MULTUP")
    assert sl == pytest.approx(7.5) and tp == pytest.approx(30.0)
    assert s.direction("frxEURUSD", second) is None             # already broke out today


def test_session_drift_directions_fixed_from_research():
    d = F.SessionDrift.session_direction
    assert d("frxEURUSD", 8) == "MULTDOWN" and d("frxGBPUSD", 8) == "MULTDOWN"
    assert d("frxUSDJPY", 8) is None
    assert d("frxEURUSD", 16) == "MULTUP" and d("frxUSDJPY", 17) == "MULTDOWN"
    assert d("frxEURUSD", 13) is None


def test_window_score_compounds_trade_returns():
    tr = [{"entry_epoch": 10, "profit": 10.0, "balance_after": 110.0},
          {"entry_epoch": 20, "profit": -11.0, "balance_after": 99.0},
          {"entry_epoch": 99, "profit": 50.0, "balance_after": 149.0}]
    sc = R.window_score(tr, 0, 50)
    assert sc["trades"] == 2 and sc["net"] == pytest.approx(-0.01)
    assert sc["dd"] == pytest.approx(0.1) and sc["score"] == pytest.approx(-0.1)
    assert R.window_score(tr, 200, 300)["score"] == -np.inf


def test_scheduled_switches_parameters_and_waits_for_first_window():
    sched = [(ep(2025, 3, 5), {"entry_hour": 8, "exit_hour": 12, "stop_pips": 0}),
             (ep(2025, 3, 6), {"entry_hour": 10, "exit_hour": 12, "stop_pips": 0})]
    s = R.Scheduled(F.SessionDrift, sched)
    st = _run(s, data_for(["frxEURUSD"], "1h", MON, 5))
    entries = sorted(t["entry_epoch"] for t in st.trades)
    assert entries == [ep(2025, 3, 5, 8), ep(2025, 3, 6, 10), ep(2025, 3, 7, 10)]
    assert s.entries[("frxEURUSD", 8)] == 1 and s.entries[("frxEURUSD", 10)] == 2


def test_random_entry_keeps_hours_and_exits():
    sched = [(ep(2025, 3, 3), {"entry_hour": 8, "exit_hour": 12, "stop_pips": 0})]
    r = R.RandomEntry(F.SessionDrift, sched, {("frxEURUSD", 9): 1.0}, seed=1)
    st = _run(r, data_for(["frxEURUSD"], "1h", MON, 5))
    assert len(st.trades) == 5
    assert all(t["entry_time"].endswith("09:00") and t["exit_time"].endswith("12:00") for t in st.trades)
    none = R.RandomEntry(F.SessionDrift, sched, {}, seed=1)
    assert not _run(none, data_for(["frxEURUSD"], "1h", MON, 5)).trades


def test_pick_per_window_takes_best_training_score():
    w = R.windows()[0]
    t = R.epoch_of(w.train_start) + 86400
    good = [{"entry_epoch": t, "profit": 5.0, "balance_after": 105.0}]
    bad = [{"entry_epoch": t, "profit": -5.0, "balance_after": 95.0}]
    picks = R.pick_per_window({0: bad, 1: good})
    assert picks[0]["variant"] == 1


def test_luck_rule_tightens_above_150_variants():
    assert R.variants_through_round(1) == 132
    assert R.luck_rule("f3") == (95, 200)
    assert R.variants_through_round(2) > 150 and R.luck_rule("f7") == (99, 500)


def test_neighbours_one_step_on_one_setting():
    grid = R._grid(a=(1, 2, 3), b=(10, 20))
    i = grid.index({"a": 2, "b": 10})
    got = sorted((grid[j]["a"], grid[j]["b"]) for j in R.neighbours(grid, i))
    assert got == [(1, 10), (2, 20), (3, 10)]


def _tr(sym, epoch, profit):
    return {"symbol": sym, "entry_epoch": epoch, "profit": profit, "balance_after": 100 + profit}


def test_robustness_flags_one_pair_and_few_big_trades():
    ws = R.windows()
    trades = []
    for w in ws:
        t = R.epoch_of(w.valid_start) + 86400
        trades += [_tr("frxEURUSD", t, 30.0)] + [_tr(s, t, -1.0) for s in ("frxGBPUSD", "frxUSDJPY")] * 5
    grid = [{"x": 1}, {"x": 2}]
    picks = [{"window": w, "variant": 0} for w in ws]
    gt = {0: trades, 1: trades}
    r = R.robustness(trades, gt, picks, grid)
    assert not r["checks"]["not_one_pair"] and not r["checks"]["not_few_big_trades"]
    assert r["checks"]["not_one_period"] and r["checks"]["nearby_settings_work"]


def test_weekly_momentum_signals_only_on_monday_close_and_trades():
    s = F.WeeklyMomentum(lookback=3)
    # Daily candles Tue 25 Feb .. Mon 3 Mar 2025, falling: the last ends Tue 4 Mar 00:00.
    b = bars([1.06, 1.05, 1.04, 1.03, 1.02, 1.01, 1.0], start=ep(2025, 2, 25), step=86400)
    assert s.direction("frxEURUSD", b) == "MULTDOWN"
    assert s.direction("frxEURUSD", b.slice(4)) is None          # Friday's candle
    st = _run(F.WeeklyMomentum(lookback=3), data_for(["frxEURUSD"], "1d", MON, 19))
    assert st.trades and all(t["entry_time"].endswith("06:00") for t in st.trades)
    assert {dt.date.fromisoformat(t["entry_time"][:10]).weekday() for t in st.trades} == {1}


def test_running_total_counts_void_variants():
    assert R.variants_through_round(2) == 132 + 8 + 9 + 9 + 12


def test_morning_momentum_follows_a_strong_move():
    # 15 days of 1h candles with a 20-pip daily range, then a morning that rises 30 pips by 10:00.
    base = [1.1000 + 0.0010 * ((h % 24) >= 12) for h in range(15 * 24)]
    day = [1.1010 + 0.0004 * (h + 1) for h in range(10)]      # candles ending 01:00 .. 10:00, +40 pips
    b = bars(base + day, spread=0.00045)
    s = F.MorningMomentum(entry_hour=10, k=0.3, sl_frac=0.5)
    assert s.direction("frxEURUSD", b) == "MULTUP"
    sl, tp = s.stops("frxEURUSD", b, "MULTUP")
    assert sl == pytest.approx(20.0) and tp is None
    assert s.direction("frxEURUSD", b.slice(len(b) - 1)) is None     # 09:00 candle: not the entry hour


class _PeerSpy(F.FamilyStrategy):
    name = "peer_spy"
    timeframe = "1h"
    needs_peers = True

    def __init__(self):
        super().__init__()
        self.seen = []

    def direction(self, symbol, c):
        t = int(c.end[-1])
        self.seen.append((t, {s: int(b.end[-1]) if len(b) else None for s, b in self.peers.items()}))
        return None


def test_peers_view_has_no_look_ahead():
    spy = _PeerSpy()
    _run(spy, data_for(["frxEURUSD", "frxGBPUSD"], "1h", MON, 3))
    assert spy.seen
    for t, peers in spy.seen:
        assert all(v is None or v <= t for v in peers.values())
    # The other pair's candle that closed at the same time is included.
    assert any(v == t for t, peers in spy.seen for v in peers.values())


def test_eur_gbp_convergence_opens_opposite_legs():
    s = F.EurGbpConvergence(length=20, z_in=1.5, hold_days=3)
    n = 25
    eur = bars(np.r_[np.full(n - 1, 1.10), 1.08], step=86400)       # EUR drops vs GBP on the last day
    gbp = bars(np.full(n, 1.30) + np.arange(n) * 1e-6, step=86400)
    s.peers = {"frxGBPUSD": gbp}
    assert s.direction("frxEURUSD", eur) == "MULTUP"
    s.peers = {"frxEURUSD": eur}
    assert s.direction("frxGBPUSD", gbp) == "MULTDOWN"
    assert s.direction("frxUSDJPY", eur) is None


def test_random_entry_keeps_two_legs_hedged():
    sched = [(ep(2025, 3, 3), {"length": 20, "z_in": 1.5, "hold_days": 3})]
    r = R.RandomEntry(F.EurGbpConvergence, sched, {("frxEURUSD", 0): 1.0, ("frxGBPUSD", 0): 1.0}, seed=4)
    st = _run(r, data_for(["frxEURUSD", "frxGBPUSD", "frxUSDJPY"], "1d", MON, 30))
    by_time = {}
    for t in st.trades:
        by_time.setdefault(t["entry_epoch"], {})[t["symbol"]] = t["direction"]
    assert by_time and all(set(v) == {"frxEURUSD", "frxGBPUSD"} for v in by_time.values())
    assert all(v["frxEURUSD"] != v["frxGBPUSD"] for v in by_time.values())


def test_shock_day_follows_a_big_close_near_the_extreme():
    closes = [1.10] * 21 + [1.115]
    b = bars(closes, step=86400, spread=0.0005)
    s = F.ShockDay(k=1.5, hold_days=1, sl_atr=1.0)
    assert s.direction("frxEURUSD", b) == "MULTUP"
    assert s.direction("frxEURUSD", b.slice(21)) is None
