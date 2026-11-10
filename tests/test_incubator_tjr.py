"""Incubator support for TJR candidates (8 Nov 2026): frozen tjr/tjr_calendar code, several commission
tables per candidate, forward replay of a 1m-fed strategy with the break-even stop update, and a
coin-toss luck check that works for strategies without an entry() hook."""

import datetime as dt

import numpy as np
import pytest

from backtest_helpers import synthetic_m1
from fxbot.backtest.candles import aggregate
from fxbot.backtest.engine import Engine
from fxbot.incubator import forward as fw
from fxbot.incubator import registry as reg
from fxbot.risk.limits import RiskLimits
from fxbot.strategies import tjr
from fxbot.strategies.base import Enter

UTC = dt.timezone.utc
TABLES = ["research/phase2/cost_by_hour.json", "research/phase2/cost_by_hour_pairs2.json"]
NINE = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY", "frxAUDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP",
        "frxEURJPY", "frxGBPJPY")
PARAMS = {"model": 1, "n": 12, "breakeven": True, "confirm": "ltf"}
REG_DAY = dt.datetime(2025, 1, 5, 9, tzinfo=UTC)          # first scored day 2025-01-06 (synthetic data)
SYMS = ("frxEURUSD", "frxGBPUSD", "frxEURJPY", "frxGBPJPY")


def _register(root, symbols=NINE, tables=TABLES, cid="tjr_test"):
    return reg.register(cid, "tjr", "TJR5m", PARAMS, root=root, now=REG_DAY, require_clean=False,
                        symbols=symbols, cost_table=tables)


def _data(c, days=100, start=dt.date(2024, 11, 1)):
    out = {}
    for i, s in enumerate(c.symbols):
        m1 = synthetic_m1(start, days, seed=40 + i, price=150.0 if "JPY" in s else 1.10,
                          vol=0.02 if "JPY" in s else 0.00015)
        out[s] = (fw.slice_bars(m1, c.start_epoch), aggregate(m1, c.timeframe))
    return out


def test_register_freezes_tjr_code_and_both_tables(tmp_path):
    c = _register(tmp_path)
    m = c.manifest
    assert m["module"] == "tjr" and m["class"] == "TJR5m" and m["timeframe"] == "1m" and m["warmup_days"] == 70
    assert m["symbols"] == list(NINE) and m["cost_table"] == TABLES and c.cost_tables == TABLES
    assert {"code/tjr.py", "code/tjr_calendar.py", "code/families.py", "code/ml_day.py"} <= set(m["files"])
    frozen = (c.dir / "code" / "tjr.py").read_text()
    assert "from . import tjr_calendar as cal" in frozen and "from fxbot.strategies import tjr_calendar" not in frozen
    s = reg.load_strategy(c)
    assert type(s).__module__.startswith("_fxinc_tjr_test_")            # runs from the frozen copy
    assert s.params == PARAMS and s.breakeven and s.n == 12
    reg.verify(c)


def test_tables_must_cover_every_pair_and_not_overlap(tmp_path):
    with pytest.raises(reg.RegistryError, match="no base rate"):
        _register(tmp_path, tables=[TABLES[0]])
    with pytest.raises(reg.RegistryError, match="overlap"):
        _register(tmp_path, tables=[TABLES[0], TABLES[0]])


def test_existing_candidates_still_load_from_their_frozen_copies():
    # Only the five candidates registered on 31 Oct 2026, before TJR support existed. Later
    # candidates (tjr_m1_5m_be_v1 from 8 Nov) may use tjr code and several cost tables.
    first = [c for c in reg.candidates() if c.manifest.get("registered") == "2026-10-31"]
    assert len(first) == 5
    for c in first:
        assert reg.verify_all()[c.id] == "ok"
        s = reg.load_strategy(c)
        assert type(s).__module__.startswith(f"_fxinc_{c.id}_")
        assert not (c.dir / "code" / "tjr.py").exists()        # their frozen code is unchanged
        assert fw.coin_toss_mode(c) == "entry" and len(c.cost_tables) == 1


def test_forward_replay_matches_the_source_strategy_and_moves_stops(tmp_path):
    c = _register(tmp_path, symbols=SYMS, tables=TABLES)
    data = _data(c)
    eng = fw.run(c, data)
    fw.check_forward_only(c, eng)
    src = Engine(fw.Forward(tjr.TJR5m(**PARAMS), c.start_epoch), list(SYMS), c.first_day, c.first_day,
                 limits=RiskLimits(starting_balance=100.0), data=data, kill_switch="enforce",
                 table=fw.commission_table(c))
    src.run()
    key = lambda e: [(t["symbol"], t["entry_epoch"], t["exit_epoch"], t["profit"]) for t in e.state.trades]
    assert key(eng) == key(src) and len(eng.state.trades) >= 3
    summ = fw.summarise(eng, c.symbols)
    assert summ["stops_moved"] == sum(1 for t in eng.state.trades if t["stop_moved_time"])
    assert all(t["exit_epoch"] % 86400 <= 18 * 3600 for t in eng.state.trades)   # flat by 17:55 UTC


def test_tjr_coin_toss_keeps_signals_and_stops_and_matches_the_prescreen_replay(tmp_path):
    c = _register(tmp_path, symbols=SYMS, tables=TABLES)
    assert fw.coin_toss_mode(c) == "actions"
    data = _data(c)
    cand = fw.run(c, data)
    sigs = fw.entry_signals(cand)
    assert sigs
    seed = 11
    ct = fw.CoinToss(reg.load_strategy(c, check=False), c.start_epoch, sigs, seed, None, c.symbols,
                     mode=fw.coin_toss_mode(c))
    eng = fw.run(c, data, strategy=ct)
    fw.check_forward_only(c, eng)
    assert {(s, t) for s, t in fw.entry_signals(eng)} <= set(map(tuple, sigs))
    # Same trades as the pre-screen's replay of the recorded Enter actions with the same seed.
    enters = {(s, int(t)): eval(a, {"__builtins__": {}}, {"Enter": Enter})
              for t, s, a in cand.state.signals if a.startswith("Enter(")}
    rep = Engine(tjr.TJRReplay("1m", enters, seed, c.symbols), list(SYMS), c.first_day, c.first_day,
                 limits=RiskLimits(starting_balance=100.0), data=data, kill_switch="enforce",
                 table=fw.commission_table(c))
    rep.run()
    key = lambda e: [(t["symbol"], t["direction"], t["entry_epoch"], t["exit_epoch"], t["profit"]) for t in e.state.trades]
    assert key(eng) == key(rep)
    # The coin really is tossed: over a few seeds, directions differ from the candidate's.
    flips = 0
    for sd in range(5):
        e = fw.run(c, data, strategy=fw.CoinToss(reg.load_strategy(c, check=False), c.start_epoch, sigs, sd,
                                                 None, c.symbols, mode="actions"))
        flips += sum(a["direction"] != b["direction"] for a, b in zip(e.state.trades, cand.state.trades))
    assert flips > 0


def test_coin_toss_entry_mode_is_unchanged_for_family_strategies():
    ct = fw.CoinToss(tjr.TJR5m(), 0, [], 1)
    assert ct.mode == "entry"
    with pytest.raises(ValueError):
        fw.CoinToss(tjr.TJR5m(), 0, [], 1, mode="other")
