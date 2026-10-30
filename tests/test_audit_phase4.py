"""Phase 4 audit (30 Oct 2026): positive controls and wiring checks.

Everything in this file is a DIAGNOSTIC, never a trading candidate. The
controls prove the research pipeline can see an edge when one exists:
- a cheating strategy that reads the next candle's close must win big;
- synthetic prices with a small built-in drift must be profitable before
  costs and pass the luck check;
- flipping a strategy's signals must mirror its before-cost result.
The wiring checks pin down Up/Down, which pair a signal reaches, what a
candle's timestamp means, UTC, and that every cost is charged exactly once.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for, synthetic_m1
from fxbot import sessions
from fxbot.backtest import audit, fills
from fxbot.backtest import research as R
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.strategies import families as F
from fxbot.strategies.base import Enter, ExitPosition, Strategy

MON = dt.date(2025, 3, 3)
PAIRS = ["frxEURUSD", "frxGBPUSD", "frxUSDJPY"]
PIP = fills.PIP


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


def run(strategy, data, **kw):
    e = Engine(strategy, list(data), MON, MON, data=data, **kw)
    e.run()
    return e.state


def net(st):
    return round(sum(t["profit"] for t in st.trades), 2)


@pytest.fixture
def no_costs():
    """Zero commission and slippage: the 'before costs' engine."""
    with audit.no_costs():
        yield


# ----------------------------------------------------------------------------- (a) cheat
def test_cheating_strategy_wins_big_and_beats_every_random_run():
    data = data_for(PAIRS, "1h", MON, 60, seed=11)
    future = {s: tf for s, (_, tf) in data.items()}
    cheat = run(audit.Cheat(future), data)
    assert len(cheat.trades) > 100
    randoms = [net(run(audit.Cheat(future, rng=np.random.default_rng(seed)), data)) for seed in range(20)]
    assert net(cheat) > 20                                  # a large profit after full costs
    assert net(cheat) > max(randoms) + 10                   # far beyond the best random run
    assert np.mean(randoms) < 0                             # random direction loses the costs
    assert cheat.trades[0]["commission"] > 0                # costs were charged on the cheat too


# ----------------------------------------------------------------------------- (b) drift
def drifting_data(days: int, pips: float = 2.0, vol: float = 0.00003, seed: int = 5) -> dict:
    """A random walk that gains `pips` between 08:00 and 12:00 UTC every day."""
    m1 = synthetic_m1(MON, days, seed=seed, vol=vol)
    sod = m1.epoch % 86400
    step = np.where((sod >= 8 * 3600) & (sod < 12 * 3600), pips * 0.0001 / 240, 0.0)
    drift = np.cumsum(step)
    b = Bars(m1.epoch, m1.end, m1.open + drift - step, m1.high + drift, m1.low + drift - step, m1.close + drift)
    return {"frxEURUSD": (b, aggregate(b, "1h"))}


def test_small_built_in_edge_is_profitable_before_costs_and_passes_luck_check(no_costs):
    data = drifting_data(days=180)
    before = run(audit.AuditDrift(), data)
    assert len(before.trades) > 100
    assert before.trades[0]["commission"] == 0
    # about +2 pips a trade before costs
    pips = [(t["exit"] - t["entry"]) / 0.0001 for t in before.trades]
    assert 1.0 < np.mean(pips) < 3.0 and net(before) > 0


def test_small_built_in_edge_passes_the_luck_check_with_full_costs():
    data = drifting_data(days=180)
    sched = [(ep(2025, 3, 3), {})]
    cand = R.Scheduled(audit.AuditDrift, sched)
    st = run(cand, data)
    rates = R.entry_rates(cand)
    assert rates == {(0, "frxEURUSD", 8): 1.0}
    randoms = []
    for seed in range(40):
        r = run(R.RandomEntry(audit.AuditDrift, sched, rates, seed), data)
        assert len(r.trades) == len(st.trades)             # same days, same hours
        assert all(t["exit_time"].endswith("12:00") for t in r.trades)
        randoms.append(net(r))
    res = R.luck_result(randoms, net(st), 95, 40)
    assert res["passed"] and res["share_beaten"] >= 0.95
    assert net(st) < 0                                      # 2 pips of edge do not pay 2.6 pips of commission


# ----------------------------------------------------------------------------- (c) flip
def test_flipped_signals_mirror_the_result_before_costs(no_costs):
    data = data_for(PAIRS, "1h", MON, 60, seed=2)
    a = run(F.SessionDrift(entry_hour=8, exit_hour=12, stop_pips=0), data)
    b = run(audit.flipped(F.SessionDrift)(entry_hour=8, exit_hour=12, stop_pips=0), data)
    assert len(a.trades) == len(b.trades) > 50
    assert all(x["direction"] != y["direction"] and x["entry_epoch"] == y["entry_epoch"]
               for x, y in zip(a.trades, b.trades))
    # stake sizes drift apart with the balance, so compare returns per unit of stake
    ra = sum(t["profit"] / t["stake"] for t in a.trades)
    rb = sum(t["profit"] / t["stake"] for t in b.trades)
    assert abs(ra) > 0.05
    assert ra == pytest.approx(-rb, abs=0.02)


# ----------------------------------------------------------------------------- wiring
class Scripted(Strategy):
    name = "scripted"
    timeframe = "1h"

    def __init__(self, plan):
        self.plan = plan

    def on_candle(self, symbol, candles, position, pending):
        return self.plan.get((symbol, int(candles.end[-1])), [])


def ramp_data(pips_per_minute: float, start_hour=10, hours=2):
    """Flat price, then a steady move from start_hour for `hours`."""
    m1 = synthetic_m1(MON, 5, seed=1, vol=0.0)
    sod = m1.epoch % 86400
    on = (sod >= start_hour * 3600) & (sod < (start_hour + hours) * 3600) & (m1.epoch // 86400 == ep(2025, 3, 4) // 86400)
    step = np.where(on, pips_per_minute * 0.0001, 0.0)
    cum = np.cumsum(step)
    b = Bars(m1.epoch, m1.end, m1.open + cum - step, m1.high + cum, m1.low + cum - step, m1.close + cum)
    return {"frxEURUSD": (b, aggregate(b, "1h"))}


def test_up_wins_when_price_rises_and_down_loses():
    data = ramp_data(+1.0)                                  # +60 pips an hour from 10:00 Tuesday
    plan = lambda d: Scripted({("frxEURUSD", ep(2025, 3, 4, 10)): [Enter(d)],
                               ("frxEURUSD", ep(2025, 3, 4, 11)): [ExitPosition()]})
    up, down = run(plan("MULTUP"), data).trades[0], run(plan("MULTDOWN"), data).trades[0]
    assert up["exit"] > up["entry"] and up["profit"] > 0.3
    assert down["exit"] > down["entry"] and down["profit"] < -0.3
    # the profit is exactly the Multiplier formula: stake x 100 x move / entry, minus commission
    for t, sign in ((up, 1), (down, -1)):
        expect = round(sign * t["stake"] * 100 * (t["exit"] - t["entry"]) / t["entry"] - t["commission"], 2)
        assert t["profit"] == pytest.approx(expect, abs=0.011)


def test_signal_reaches_only_its_own_pair_with_that_pairs_prices():
    data = data_for(PAIRS, "1h", MON, 5)
    plan = {("frxUSDJPY", ep(2025, 3, 4, 10)): [Enter("MULTUP")], ("frxGBPUSD", ep(2025, 3, 5, 10)): [Enter("MULTDOWN")]}
    st = run(Scripted(plan), data)
    assert sorted(t["symbol"] for t in st.trades) == ["frxGBPUSD", "frxUSDJPY"]
    for t in st.trades:
        m1 = data[t["symbol"]][0]
        o = float(m1.open[np.searchsorted(m1.epoch, t["entry_epoch"])])
        assert t["entry"] == pytest.approx(fills.entry_price(t["symbol"], t["direction"], o))
    jpy = next(t for t in st.trades if t["symbol"] == "frxUSDJPY")
    assert 100 < jpy["entry"] < 200                          # USD/JPY prices, not EUR/USD's


class CandleSpy(Strategy):
    name = "spy"
    timeframe = "1h"

    def __init__(self):
        self.seen = []

    def on_candle(self, symbol, candles, position, pending):
        self.seen.append((symbol, int(candles.epoch[-1]), int(candles.end[-1]), float(candles.open[-1]),
                          float(candles.close[-1]), len(candles)))
        return []


def test_candle_timestamps_mean_start_and_close_time():
    data = data_for(["frxEURUSD"], "1h", MON, 3)
    m1 = data["frxEURUSD"][0]
    spy = CandleSpy()
    run(spy, data)
    assert spy.seen and all(e % 3600 == 0 and end == e + 3600 for _, e, end, *_ in spy.seen)
    at = {int(x): i for i, x in enumerate(m1.epoch)}
    for _, e, end, o, c, n in spy.seen:
        assert o == m1.open[at[e]]                           # open = the first minute's open
        assert c == m1.close[at[end - 60]]                   # close = the last minute's close
    assert [n for *_, n in spy.seen] == list(range(1, len(spy.seen) + 1))   # one new closed candle each call


def test_entry_fills_at_the_first_minute_after_the_candle_closes():
    data = data_for(["frxEURUSD"], "1h", MON, 3)
    m1 = data["frxEURUSD"][0]
    st = run(Scripted({("frxEURUSD", ep(2025, 3, 4, 10)): [Enter("MULTUP")]}), data)
    t = st.trades[0]
    assert t["signal_time"] == "2025-03-04 10:00" and t["entry_time"] == "2025-03-04 10:00"
    o = float(m1.open[np.searchsorted(m1.epoch, ep(2025, 3, 4, 10))])
    assert t["entry"] == pytest.approx(o + 0.5 * 0.0001)     # the 10:00 minute's open, 0.5 pip against us


@pytest.mark.parametrize("day", [dt.date(2025, 1, 7), dt.date(2025, 7, 8)])     # winter and summer
def test_utc_everywhere_no_daylight_saving(day):
    t = sessions.day_start(day) + 8 * 3600
    assert dt.datetime.fromtimestamp(t, dt.timezone.utc).hour == 8
    assert F.hour_of(t) == 8 and sessions.in_entry_window(t)
    assert sessions.in_entry_window(sessions.day_start(day) + 5 * 3600 + 59 * 60) is False
    assert sessions.in_entry_window(sessions.day_start(day) + 6 * 3600) is True
    assert sessions.in_entry_window(sessions.day_start(day) + 18 * 3600) is False
    data = {"frxEURUSD": (lambda b: (b, aggregate(b, "1h")))(synthetic_m1(day - dt.timedelta(days=1), 3))}
    st = Engine(Scripted({("frxEURUSD", t): [Enter("MULTUP")]}), ["frxEURUSD"], day, day, data=data)
    st.run()
    assert st.state.trades[0]["entry_time"] == f"{day} 08:00"
    tf = aggregate(synthetic_m1(day - dt.timedelta(days=1), 3), "1d")
    assert all(e % 86400 == 0 for e in tf.epoch)             # daily candles start at 00:00 UTC


# ----------------------------------------------------------------------------- costs once
T0 = ep(2025, 3, 4, 10)
RATE = 0.000239


def test_each_cost_is_charged_exactly_once_per_exit_type():
    mid, stake, mult, pips = 1.10000, 3.0, 100, 20
    size = stake * mult
    p = fills.open_position("frxEURUSD", "MULTUP", mult, stake, mid, T0, RATE, pips, pips)
    comm = RATE * size
    assert p.commission == pytest.approx(comm) and p.entry == pytest.approx(mid + 0.00005)
    # take profit: level = entry + 20 pips; pays the 20-pip move minus the commission, nothing else
    tp = fills.check_bar(p, T0 + 60, p.entry, p.tp_price, p.entry, p.entry)
    assert tp.reason == "take_profit"
    assert tp.profit == pytest.approx(round(size * pips * 0.0001 / p.entry - comm, 2), abs=0.006)
    # stop loss: Deriv takes the loss as a whole-cent amount (20 pips + commission, rounded up to
    # the cent, so the level is 20.1 pips from the entry); filled 1 pip worse than the level
    sl = fills.check_bar(p, T0 + 60, p.entry, p.entry, p.sl_price, p.entry)
    assert sl.reason == "stop_loss" and sl.price == pytest.approx(p.sl_price - 0.0001)
    assert p.sl_amount == pytest.approx(round(size * pips * 0.0001 / p.entry + comm, 2))
    assert sl.profit == pytest.approx(-(p.sl_amount + size * 0.0001 / p.entry), abs=0.006)
    assert sl.profit == pytest.approx(-size * (pips + 1) * 0.0001 / p.entry - comm, abs=0.011)
    # a plain close at the mid price: the move from the slipped entry, minus the commission
    ex = fills.close_at(p, T0 + 60, mid + 0.0010, "strategy_exit")
    assert ex.profit == pytest.approx(round(size * (0.0010 - 0.00005) / p.entry - comm, 2), abs=0.006)
    # stop out (a trade without a stop loss): the whole stake and not a cent more
    q = fills.open_position("frxEURUSD", "MULTUP", mult, stake, mid, T0, RATE)
    so = fills.check_bar(q, T0 + 60, q.entry, q.entry, q.stop_out - 0.01, q.entry)
    assert (so.reason, so.profit) == ("stop_out", -stake)
    # ...and a crash through both levels takes the stop loss first (SL-first rule), once
    both = fills.check_bar(p, T0 + 60, p.entry, p.entry, p.stop_out - 0.01, p.entry)
    assert both.reason == "stop_loss" and both.profit == sl.profit
    # round trip cost of a flat trade = commission + the 0.5 pip entry slippage, once
    flat = fills.close_at(p, T0 + 60, mid, "strategy_exit")
    assert flat.profit == pytest.approx(round(-size * 0.00005 / p.entry - comm, 2), abs=0.006)


def test_stress_changes_only_the_commission():
    a = fills.open_position("frxEURUSD", "MULTUP", 100, 3.0, 1.1, T0, RATE, 20, 20)
    b = fills.open_position("frxEURUSD", "MULTUP", 100, 3.0, 1.1, T0, RATE, 20, 20, stress=1.5)
    assert b.commission == pytest.approx(1.5 * a.commission)
    assert a.entry == b.entry
    # levels move by at most the whole-cent rounding of the amounts (0.2 pips here), not by a pip
    assert abs(a.sl_price - b.sl_price) <= 0.00003 and abs(a.tp_price - b.tp_price) <= 0.00003
    assert b.tp_amount == pytest.approx(a.tp_amount - 0.5 * a.commission, abs=0.011)
    assert b.sl_amount == pytest.approx(a.sl_amount + 0.5 * a.commission, abs=0.011)


def test_engine_net_equals_engine_gross_minus_costs():
    data = data_for(PAIRS, "1h", MON, 40, seed=9)
    s = lambda: F.SessionDrift(entry_hour=8, exit_hour=16, stop_pips=0)
    with_costs = run(s(), data)
    with audit.no_costs():
        free = run(s(), data)
    assert len(with_costs.trades) > 50
    paired = [(a, b) for a, b in zip(with_costs.trades, free.trades)
              if a["entry_epoch"] == b["entry_epoch"] and a["reason"] == b["reason"] == "strategy_exit"]
    assert len(paired) > 0.8 * len(with_costs.trades)
    for a, b in paired:
        # same trade without costs = recorded profit + commission + entry slippage (per unit of stake)
        assert audit.gross_of(a) / a["stake"] == pytest.approx(b["profit"] / b["stake"], abs=0.01)


# ----------------------------------------------------------------------------- luck check
def test_luck_percentiles_and_pass_rule():
    nets = list(range(100))                                  # 0..99
    r = R.luck_result(nets, net=95.5, pct=95, need_runs=100)
    assert r["p95"] == pytest.approx(np.percentile(nets, 95)) and r["passed"]
    assert R.luck_result(nets, 94.0, 95, 100)["passed"] is False
    assert R.luck_result(nets, 95.5, 95, 200)["passed"] is False      # not enough runs
    assert R.luck_result(nets, 98.5, 99, 100)["passed"] is True and R.luck_result(nets, 97.0, 99, 100)["passed"] is False
    assert R.luck_result(nets, 50.0, 95, 100)["share_beaten"] == 0.5
    assert R.luck_result([], 1.0, 95, 100)["passed"] is False


def test_random_runs_keep_trade_count_when_the_signal_hour_changes_between_windows():
    """Family 8 picked entry hour 10 in rounds 1-2 and 9 in rounds 3-5. Before the fix the
    random runs made 41% fewer trades: the per-hour rate was averaged over every window."""
    data = data_for(PAIRS, "1h", MON, 80, seed=4)
    sched = [(ep(2025, 3, 3), {"entry_hour": 10, "exit_hour": 16, "stop_pips": 0}),
             (ep(2025, 4, 14), {"entry_hour": 8, "exit_hour": 16, "stop_pips": 0})]
    cand = R.Scheduled(F.SessionDrift, sched)
    st = run(cand, data)
    rates = R.entry_rates(cand)
    assert set(k[0] for k in rates) == {0, 1} and all(v == 1.0 for v in rates.values())
    counts, hours = [], set()
    for seed in range(3):
        r = run(R.RandomEntry(F.SessionDrift, sched, rates, seed), data)
        counts.append(len(r.trades))
        hours |= {(t["entry_epoch"] >= ep(2025, 4, 14), t["entry_time"][-5:]) for t in r.trades}
        assert all(t["commission"] > 0 and t["exit_time"].endswith("16:00") for t in r.trades)
    assert all(abs(c - len(st.trades)) <= 0.05 * len(st.trades) for c in counts)
    assert hours == {(False, "10:00"), (True, "08:00")}     # the candidate's own hour in each window


def test_random_runs_do_not_apply_an_entry_filter_twice():
    """Family 6 filters on a quiet night inside stops(); the random rate must be measured over
    the candles that passed the filter, or the random runs trade only on quiet nights AND at a
    rate diluted by the busy ones (30% fewer trades before the fix)."""
    data = data_for(PAIRS, "1h", MON, 120, seed=6)
    sched = [(ep(2025, 3, 3), {"box_max": 0.5, "tp_atr": 0.8, "sl_frac": 1.0})]
    cand = R.Scheduled(F.QuietLondonBreakout, sched)
    st = run(cand, data)
    assert len(st.trades) >= 20
    counts = [len(run(R.RandomEntry(F.QuietLondonBreakout, sched, R.entry_rates(cand), s), data).trades)
              for s in range(4)]
    assert abs(np.mean(counts) - len(st.trades)) <= 0.2 * len(st.trades), (counts, len(st.trades))


def test_random_entry_refuses_old_rate_keys():
    with pytest.raises(ValueError):
        R.RandomEntry(F.SessionDrift, [(0, {})], {("frxEURUSD", 8): 1.0}, seed=0)
