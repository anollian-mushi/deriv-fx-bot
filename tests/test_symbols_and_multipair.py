"""Per-candidate symbol lists and commission tables (31 Oct 2026, multi-pair test of i13)."""

import datetime as dt
import json

import pytest

from fxbot import symbols as S
from fxbot.backtest import fills
from fxbot.backtest import prescreen as P
from fxbot.incubator import forward as fw
from fxbot.incubator import registry
from fxbot.incubator import leaderboard


def test_symbol_table_and_check():
    assert S.PIP["frxGBPJPY"] == 0.01 and S.PIP_SIZE["frxGBPJPY"] == 0.001
    assert S.PIP["frxEURGBP"] == 0.0001 and S.display("frxAUDUSD") == "AUD/USD"
    assert fills.PIP is S.PIP and fills.PIP_SIZE is S.PIP_SIZE
    assert S.check(S.PAIRS2) == S.PAIRS2
    with pytest.raises(ValueError):
        S.check(("frxEURUSD", "frxXXXYYY"))
    with pytest.raises(ValueError):
        S.check(("frxEURUSD", "frxEURUSD"))


def test_pairs2_idea_is_the_unchanged_i13_rule_on_the_new_pairs_only():
    i = P.IDEAS["morning_overnight_pairs2"]
    assert i.name == "i13_morning_overnight" and i.grid == [{"decision_hour": 8, "k": 0.4, "stop": 0.0}]
    assert i.symbols == S.PAIRS2 and not set(i.symbols) & set(S.MAJORS)
    assert i.table == "research/phase2/cost_by_hour_pairs2.json"
    assert P.IDEAS["morning_overnight"].symbols == S.MAJORS and P.IDEAS["morning_overnight"].table is None


def _table(path, symbols, rate_pct=0.03):
    path.write_text(json.dumps({"base_rate_pct": {s: rate_pct for s in symbols},
                                "hours": {str(h): {"max_rate_pct": {s: rate_pct for s in symbols}} for h in range(24)}}))


def test_register_stores_symbols_and_table_and_checks_them(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, "ROOT", tmp_path)
    table = tmp_path / "cost.json"
    _table(table, S.PAIRS2)
    now = dt.datetime(2026, 11, 2, 19, tzinfo=dt.timezone.utc)
    c = registry.register("pairs2_test", "families", "MorningOvernight", {"decision_hour": 8, "k": 0.4, "stop": 0.0},
                          root=tmp_path / "inc", now=now, require_clean=False, symbols=S.PAIRS2, cost_table="cost.json")
    assert c.symbols == S.PAIRS2 and c.cost_table == "cost.json"
    assert c.manifest["symbols"] == list(S.PAIRS2)
    with pytest.raises(registry.RegistryError):            # a table without every pair's base rate
        registry.register("pairs2_bad", "families", "MorningOvernight", {}, root=tmp_path / "inc2", now=now,
                          require_clean=False, symbols=S.PAIRS2 + ("frxEURUSD",), cost_table="cost.json")
    with pytest.raises(registry.RegistryError):            # a missing table
        registry.register("pairs2_bad2", "families", "MorningOvernight", {}, root=tmp_path / "inc3", now=now,
                          require_clean=False, symbols=S.PAIRS2, cost_table="nope.json")
    with pytest.raises(ValueError):                        # an unknown pair
        registry.register("pairs2_bad3", "families", "MorningOvernight", {}, root=tmp_path / "inc4", now=now,
                          require_clean=False, symbols=("frxABCDEF",), cost_table="cost.json")


def test_old_manifests_default_to_the_majors_and_the_phase2_table():
    c = registry.Candidate("x", registry.INCUBATOR / "candidates" / "x", {"module": "families"}, "fp", 0)
    assert c.symbols == S.MAJORS and c.cost_table == "research/phase2/cost_by_hour.json"
    for real in registry.candidates():
        assert real.symbols == S.MAJORS and real.cost_table == registry.DEFAULT_COST_TABLE


def test_coin_toss_indexes_the_candidates_own_symbols():
    class Inner:
        name, timeframe, params = "t", "1h", {}
        def on_candle(self, *a):
            return []
    t = 1_800_000_000
    a = fw.CoinToss(Inner(), 0, [("frxGBPJPY", t)], 1, None, symbols=S.PAIRS2)
    b = fw.CoinToss(Inner(), 0, [("frxGBPJPY", t)], 1, None, symbols=("frxGBPJPY",))
    assert a._entry("frxGBPJPY", type("C", (), {"end": [t]})()) in ("MULTUP", "MULTDOWN")
    assert a._entry("frxAUDUSD", type("C", (), {"end": [t]})()) is None
    # a different position in the list gives an independent draw stream, as intended
    assert isinstance(b._entry("frxGBPJPY", type("C", (), {"end": [t]})()), str)


def test_leaderboard_shows_other_pairs(tmp_path):
    index = {"data_end": "2026-11-10", "candidates": {
        "pairs2": {"status": "active", "forward_days": 7, "first_scored_day": "2026-11-03", "stress_net": 0.5,
                   "measured": {"trades": 3, "open_trades": 0, "net_profit": 1.0, "max_drawdown_pct": 2.0,
                                "win_rate_pct": 66.7, "profit_factor": 2.0, "avg_win": 1.0, "avg_loss": -0.5,
                                "per_pair": {s: {"trades": 1, "net": 0.3, "wins": 1} for s in S.PAIRS2[:3]}},
                   "exam": None}}}
    md = leaderboard.markdown(index, dt.date(2026, 11, 11))
    assert "| Other pairs |" in md and "AUD/USD +0.30 (1)" in md and "| - | - | - |" in md
    text = leaderboard.telegram_text(index, dt.date(2026, 11, 11))
    assert "AUDUSD +0.30" in text
