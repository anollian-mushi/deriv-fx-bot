import csv
from pathlib import Path

import pytest

from fxbot.backtest import whatif as W

ROOT = Path(__file__).resolve().parents[1]


def _trades(name):
    path = ROOT / "reports" / "backtests" / f"phase4_{name}_oos" / "trades.csv"
    if not path.exists():
        pytest.skip("Phase 4 trade files not present")
    out = []
    with path.open() as f:
        for r in csv.DictReader(f):
            out.append({**r, **{k: float(r[k]) for k in ("stake", "entry", "exit", "commission", "profit",
                                                       "balance_after")},
                        "multiplier": int(r["multiplier"]), "entry_epoch": int(r["entry_epoch"]),
                        "exit_epoch": int(r["exit_epoch"])})
    return out


@pytest.mark.parametrize("name", ["f9_eur_gbp_convergence", "f3_trend_pullback", "f5_session_drift"])
def test_recorded_cost_reproduces_the_recorded_result(name):
    tr = _trades(name)
    r = W.reprice(tr, W.cost_recorded)
    assert len(r["trades"]) == len(tr)
    recorded = sum(t["profit"] for t in tr)
    # Same trades, same costs: within a cent per trade from rounding and stake re-derivation.
    assert r["net"] == pytest.approx(recorded, abs=0.01 * len(tr) + 0.5)


def _t(direction="MULTUP", entry=1.1, exit_=1.101, reason="manual", **kw):
    t = {"symbol": "frxEURUSD", "direction": direction, "stake": 3.0, "multiplier": 100, "entry": entry,
         "exit": exit_, "reason": reason, "commission": 0.0, "entry_epoch": 1_740_996_000,
         "exit_epoch": 1_740_999_600}
    size = 300
    move = (exit_ - entry) if direction == "MULTUP" else (entry - exit_)
    t["profit"] = round(size * move / entry, 2)
    t.update(kw)
    return t


def test_total_cost_is_floored_at_the_trades_own_slippage():
    t = _t()
    pip_frac = 0.0001 / 1.1
    assert W.cost_total(0.0)(t)[0] == pytest.approx(0.5 * pip_frac)
    assert W.cost_total(2.0)(t)[0] == pytest.approx(2.0 * pip_frac)
    assert W.cost_total(1.0)(_t(reason="stop_loss"))[0] == pytest.approx(1.5 * pip_frac)


def test_reprice_charges_the_new_cost_once_and_caps_at_stake():
    # A 10-pip winner (recorded with 0.5 pip slippage already in its entry) at 2 pips total.
    t = _t(exit_=1.1010)
    r = W.reprice([t], W.cost_total(2.0))
    gross_pips = 10 + 0.5
    assert r["trades"][0]["profit"] == pytest.approx(round(300 * (gross_pips - 2.0) * 0.0001 / 1.1, 2))
    crash = _t(exit_=1.05)
    assert W.reprice([crash], W.cost_total(2.0))["trades"][0]["profit"] == -3.0
    assert W.reprice([crash], W.cost_broker())["trades"][0]["profit"] < -3.0     # a CFD has no cap


def test_broker_swap_charged_per_night():
    day = _t()
    night = _t(exit_epoch=1_740_996_000 + 86400)            # held over one 21:00 rollover
    assert W.swap_fraction(day) == 0.0
    assert W.swap_fraction(night) == pytest.approx(-11.42 * 0.00001 / 1.1)   # EUR/USD long swap


def test_kill_switch_observe_restart_on_closed_balance():
    losers = [_t(exit_=1.05, entry_epoch=1_740_996_000 + k * 7200, exit_epoch=1_740_999_600 + k * 7200)
              for k in range(30)]
    r = W.reprice(losers, W.cost_total(1.0))
    assert r["kill_events"]
    first = r["kill_events"][0]
    k = next(i for i, t in enumerate(r["trades"]) if t["balance_after"] <= 50)
    assert r["trades"][k + 1]["stake"] == 3.0               # sized on the restarted 100 USD
    assert first["balance"] <= 50
