"""Incubator forward test and graduation exam: forward-only scoring, the luck-check numbers,
N counting, retakes, and one end-to-end daily run on past Deriv data (exam thresholds lowered
for the test only)."""

import datetime as dt
import json
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot.incubator import daily, exam, registry as reg
from fxbot.incubator import forward as fw
from fxbot.strategies.base import Enter
from fxbot.strategies.families import FamilyStrategy

UTC = dt.timezone.utc
SYMS = list(fw.SYMBOLS)


class AlwaysUp(FamilyStrategy):
    name, timeframe = "always_up", "1h"

    def direction(self, symbol, c):
        return "MULTUP"

    def stops(self, symbol, c, direction):
        return (20.0, 20.0)


def _cand(first_day: dt.date, legs=None):
    reg_day = first_day - dt.timedelta(days=1)
    m = {"registered": reg_day.isoformat(), "timeframe": "1h", "warmup_days": 10, "legs": legs}
    return reg.Candidate("x_test", reg.ROOT, m, "f" * 64, 0)


# ----------------------------------------------------------------------------- forward only
def test_forward_wrapper_never_trades_before_first_scored_day():
    data = data_for(SYMS, "1h", dt.date(2026, 6, 1), 21)
    c = _cand(dt.date(2026, 6, 15))
    eng = fw.run(c, data, strategy=fw.Forward(AlwaysUp(), c.start_epoch))
    assert eng.state.trades, "the dummy strategy should trade after the first day"
    assert min(t for t, _, _ in eng.state.signals) >= c.start_epoch
    assert min(t["entry_epoch"] for t in eng.state.trades) >= c.start_epoch
    fw.check_forward_only(c, eng)


def test_check_forward_only_rejects_earlier_signals_and_trades():
    c = _cand(dt.date(2026, 11, 2))
    early = c.start_epoch - 3600
    eng = SimpleNamespace(state=SimpleNamespace(signals=[(early, "frxEURUSD", repr(Enter("MULTUP")))], trades=[]))
    with pytest.raises(fw.ForwardViolation):
        fw.check_forward_only(c, eng)
    eng = SimpleNamespace(state=SimpleNamespace(signals=[], trades=[{"entry_epoch": early}]))
    with pytest.raises(fw.ForwardViolation):
        fw.check_forward_only(c, eng)


def test_forward_data_refuses_days_before_untouched_period():
    with pytest.raises(fw.ForwardViolation):
        fw.forward_data(_cand(dt.date(2026, 10, 1)), dt.date(2026, 10, 30))


def test_forward_data_starts_timeline_on_first_day_with_warmup_candles(monkeypatch):
    monkeypatch.setattr(fw, "UNTOUCHED_START", dt.date(2026, 1, 1))
    c = _cand(dt.date(2026, 10, 26))
    d = fw.forward_data(c, dt.date(2026, 10, 30))
    for s in SYMS:
        m1, tf = d[s]
        assert m1.epoch[0] >= c.start_epoch and tf.epoch[0] < c.start_epoch
        assert tf.end[-1] <= fw.epoch_of(dt.date(2026, 10, 31))


def test_coin_toss_uses_only_candidate_signals_and_keeps_legs_hedged():
    c = _cand(dt.date(2026, 6, 15), legs={"frxEURUSD": 1, "frxGBPUSD": -1})
    t = c.start_epoch + 7 * 3600
    ct = fw.CoinToss(AlwaysUp(), c.start_epoch, [("frxEURUSD", t), ("frxGBPUSD", t)], seed=5, legs=c.legs)
    bars = SimpleNamespace(end=np.array([t]))
    a, b = ct._entry("frxEURUSD", bars), ct._entry("frxGBPUSD", bars)
    assert {a, b} == {"MULTUP", "MULTDOWN"}
    assert ct._entry("frxUSDJPY", bars) is None
    assert ct._entry("frxEURUSD", SimpleNamespace(end=np.array([t + 3600]))) is None
    dirs = {fw.CoinToss(AlwaysUp(), 0, [("frxUSDJPY", t)], seed=s)._entry("frxUSDJPY", bars) for s in range(20)}
    assert dirs == {"MULTUP", "MULTDOWN"}


# ----------------------------------------------------------------------------- exam numbers
def test_runs_and_bar_follow_the_rule():
    assert exam.runs_needed(4) == 2000 and exam.runs_needed(5) == 2000
    assert exam.runs_needed(6) == 2400 and exam.runs_needed(13) == 5200
    assert exam.bar_percentile(5) == pytest.approx(99.0)
    for n in (5, 6, 13):
        assert exam.runs_needed(n) * exam.ALPHA / n >= 20 - 1e-9


def test_luck_verdict_needs_enough_runs_and_beats_bar():
    nets = np.random.default_rng(1).normal(0, 5, 2000)
    v = exam.luck_verdict(nets, 100.0, 5)
    assert v["passed"] and v["beyond_bar"] >= 20 and v["runs"] == 2000
    assert not exam.luck_verdict(nets, 0.0, 5)["passed"]
    assert not exam.luck_verdict(nets[:1999], 100.0, 5)["passed"]


def _summary(end="2027-02-01", days=93, trades=120, net=5.0, net_s=2.0, dd=10.0, kill=False):
    m = {"trades": trades, "net_profit": net, "max_drawdown_pct": dd, "kill_switch_fired": kill,
         "per_pair": {s: {"trades": 40, "net": 1.0, "wins": 20} for s in SYMS}}
    return {"data_end": end, "forward_days": days, "first_scored_day": "2026-11-01",
            "measured": m, "stress_1_5x": {**m, "net_profit": net_s}}


@pytest.mark.parametrize("change,ok", [({}, True), ({"days": 89}, False), ({"trades": 99}, False),
                                       ({"net": 0.0}, False), ({"net_s": -0.01}, False),
                                       ({"dd": 25.0}, False), ({"kill": True}, False)])
def test_rules_1_to_3(change, ok):
    assert all(r["ok"] for r in exam.rules_1_to_3(_summary(**change)).values()) is ok


def _two_candidates(root):
    for i, cid in enumerate(("f1_aa", "f1_bb")):
        reg.register(cid, "families", "LondonBreakout", {}, root=root,
                     now=dt.datetime(2026, 11, 1, i, tzinfo=UTC), require_clean=False)
    return reg.candidates(root)


def test_every_exam_attempt_adds_one_to_n_and_retakes_wait_28_days(tmp_path):
    ca, cb = _two_candidates(tmp_path)
    ra, rb = tmp_path / "records" / ca.id, tmp_path / "records" / cb.id
    assert exam.n_for_next_exam(tmp_path) == 3
    st = exam.start(ca, _summary("2027-02-01"), [], ra, tmp_path)
    assert st["N"] == 3 and st["attempt"] == 1
    assert exam.can_start(ca, _summary("2027-02-02"), ra, tmp_path) == (False, "exam in progress")
    st["nets"] = [100.0] * st["runs_needed"]                 # all random runs better: fails
    exam.finish(ca, st, ra, tmp_path)
    assert not exam.load_exam(ra)["result"]["passed"]
    ok, why = exam.can_start(ca, _summary("2027-02-28"), ra, tmp_path)
    assert not ok and "2027-03-01" in why
    assert exam.can_start(ca, _summary("2027-03-01"), ra, tmp_path)[0]
    st2 = exam.start(cb, _summary("2027-03-01"), [], rb, tmp_path)
    assert st2["N"] == 4                                     # 2 candidates + 2 attempts
    st3 = exam.start(ca, _summary("2027-03-01"), [], ra, tmp_path)
    assert st3["N"] == 5 and st3["attempt"] == 2
    log = reg.read_chain(reg.exams_path(tmp_path))
    assert [e["event"] for e in log] == ["start", "result", "start", "start"]


def test_exam_log_cannot_be_trimmed(tmp_path):
    ca, _ = _two_candidates(tmp_path)
    exam.start(ca, _summary(), [], tmp_path / "records" / ca.id, tmp_path)
    exam.start(ca, _summary(), [], tmp_path / "records" / ca.id, tmp_path)
    p = reg.exams_path(tmp_path)
    p.write_text(json.dumps(json.loads(p.read_text())[1:]))
    with pytest.raises(reg.TamperedError):
        exam.n_for_next_exam(tmp_path)


# ----------------------------------------------------------------------------- end to end
def test_daily_run_end_to_end_on_past_deriv_data(tmp_path, monkeypatch):
    """Registered 2026-09-30 in a scratch incubator: replay, records, an exam with lowered
    thresholds (test only), a result and the notices. Real Deriv data, single process."""
    monkeypatch.setattr(fw, "UNTOUCHED_START", dt.date(2026, 1, 1))
    c = reg.register("f9_e2e", "families", "EurGbpConvergence", {"length": 20, "z_in": 1.0, "hold_days": 3},
                     root=tmp_path, now=dt.datetime(2026, 9, 30, 12, tzinfo=UTC), require_clean=False)
    monkeypatch.setattr(exam, "rules_1_to_3", lambda s: {"days": {"ok": True}})
    monkeypatch.setattr(exam, "MIN_RUNS", 12)
    monkeypatch.setattr(exam, "BEYOND", 0.01)
    out = daily.run_daily(tmp_path, exam_budget_s=600, workers=1, now=dt.datetime(2026, 10, 31, tzinfo=UTC))
    rec = tmp_path / "records" / c.id
    summary = json.loads((rec / "summary.json").read_text())
    assert summary["data_end"] == "2026-10-30" and summary["first_scored_day"] == "2026-10-01"
    assert summary["forward_days"] == 30
    trades = (rec / "trades.csv").read_text().splitlines()
    assert trades[0].startswith("symbol,") and all(r.split(",")[5] >= "2026-10-01" for r in trades[1:])
    st = exam.load_exam(rec)
    assert st["N"] == 2 and len(st["nets"]) == 12 and "result" in st
    assert any(n.startswith("Exam started") for n in out["notices"])
    assert any(n.startswith(("GRADUATED", "Exam not passed")) for n in out["notices"])
    if st["result"]["passed"]:
        msg = next(n for n in out["notices"] if n.startswith("GRADUATED"))
        assert "EUR/USD" in msg and "GBP/USD" in msg and "USD/JPY" in msg and "Do NOT put real money" in msg
    idx = json.loads((tmp_path / "records" / "index.json").read_text())
    assert idx["candidates"][c.id]["exam"]["runs_done"] == 12
    assert not out["problems"]
    # The same random runs again give the same nets (seeded by id, fingerprint, cutoff, attempt).
    again = [exam._one_run(st["seed"] + i) for i in range(3)]
    assert again == st["nets"][:3]


def test_daily_flags_tampered_candidate_and_skips_it(tmp_path):
    ca, _ = _two_candidates(tmp_path)
    (ca.dir / "code" / "families.py").write_text("# changed\n")
    out = daily.run_daily(tmp_path, now=dt.datetime(2026, 11, 1, tzinfo=UTC))
    assert out["problems"] and "TAMPERED" in out["problems"][0]
    assert out["index"]["candidates"][ca.id]["status"] == "tampered"


def test_leaderboard_renders_every_status(tmp_path, monkeypatch):
    from fxbot.incubator import leaderboard
    m = {"trades": 3, "open_trades": 1, "net_profit": -1.5, "max_drawdown_pct": 2.0, "win_rate_pct": 33.3,
         "avg_win": 1.0, "avg_loss": -1.25, "profit_factor": 0.4, "kill_switch_fired": False,
         "per_pair": {s: {"trades": 1, "net": -0.5, "wins": 0} for s in SYMS}}
    idx = {"data_end": "2026-11-20", "candidates": {
        "a_live": {"status": "active", "first_scored_day": "2026-11-01", "forward_days": 20, "measured": m,
                   "stress_net": -2.0, "rules": {"days": False, "trades": False}, "exam": None},
        "b_wait": {"status": "waiting", "first_scored_day": "2026-12-01"},
        "c_dead": {"status": "dead", "first_scored_day": "2026-11-01", "forward_days": 20,
                   "measured": {**m, "kill_switch_fired": True}, "stress_net": -50.0, "rules": {}, "exam": None}}}
    t = leaderboard.telegram_text(idx, dt.date(2026, 11, 23))
    md = leaderboard.markdown(idx, dt.date(2026, 11, 23))
    assert "a_live [ACTIVE]" in t and "days 20/90" in t and "scoring starts 2026-12-01" in t and "out for good" in t
    assert md.count("\n| ") >= 4 and "c_dead" in md


def test_watchdog_counts_only_scheduled_days():
    from fxbot.incubator import watchdog as wd
    sat, mon, tue, wed = (dt.date(2026, 11, d) for d in (7, 9, 10, 11))
    assert wd.missed_daily(sat, mon) == 0          # Sunday and Monday have no runs
    assert wd.missed_daily(sat, tue) == 1 and not wd.stale("daily", sat, tue)
    assert wd.missed_daily(sat, wed) == 2 and wd.stale("daily", sat, wed)
    assert not wd.stale("weekly", dt.date(2026, 11, 9), dt.date(2026, 11, 17))
    assert wd.stale("weekly", dt.date(2026, 11, 9), dt.date(2026, 11, 18))


def test_incubator_never_imports_order_code():
    import pathlib
    src = pathlib.Path(reg.ROOT / "src" / "fxbot" / "incubator")
    for p in src.glob("*.py"):
        text = p.read_text()
        assert "fxbot.deriv" not in text and "fxbot.live" not in text, p.name
