import csv
import datetime as dt
from pathlib import Path

import pytest

from fxbot.backtest import fills as f
from fxbot.contracts import multiplier as mc

ROOT = Path(__file__).resolve().parents[1]
TABLE = f.CommissionTable()
T0 = int(dt.datetime(2025, 3, 4, 10, 0, tzinfo=dt.timezone.utc).timestamp())


def test_commission_comes_from_hourly_table():
    assert TABLE.rate("frxEURUSD", T0) == pytest.approx(0.000239)
    noon = T0 + 2 * 3600
    assert TABLE.rate("frxEURUSD", noon) == pytest.approx(3 * 0.000239, rel=1e-3)
    assert TABLE.base["frxGBPUSD"] == pytest.approx(0.000203)


def test_demo_trades_reproduced_within_a_cent():
    """All 11 Phase 2 demo trades: entry/exit spots + table rate for the opening hour."""
    rows = [r for r in csv.DictReader((ROOT / "research/demo_cost_trades.csv").open()) if r.get("contract_id")]
    assert len(rows) == 11
    for r in rows:
        opened = int(dt.datetime.strptime(r["entry_time_utc"], "%Y-%m-%dT%H:%M:%SZ")
                     .replace(tzinfo=dt.timezone.utc).timestamp())
        rate = TABLE.rate(r["symbol"], opened)
        stake, mult = float(r["stake"]), int(r["multiplier"])
        if r["close_reason"] == "take_profit":
            ours = float(r["kind"].split("tp=")[1])       # TP pays exactly the amount set
        else:
            comm = mc.commission(stake, mult, rate)
            ours = round(mc.profit(r["direction"], stake, mult, float(r["entry_spot"]),
                                   float(r["exit_spot"]), comm), 2)
        assert abs(ours - float(r["profit"])) <= 0.01 + 1e-9, r["trade_no"]


def _pos(**kw):
    args = dict(symbol="frxEURUSD", direction="MULTUP", multiplier=100, stake=3.0, mid_open=1.10000,
                epoch=T0, rate=0.000239)
    args.update(kw)
    return f.open_position(**args)


def test_entry_slippage_against_us():
    assert _pos().entry == pytest.approx(1.10005)
    assert _pos(direction="MULTDOWN").entry == pytest.approx(1.09995)


def test_stop_loss_minimum():
    with pytest.raises(ValueError):
        _pos(stop_loss_pips=0.1)          # below commission + 0.02
    p = _pos(stop_loss_pips=20)
    assert p.sl_amount >= round(p.commission + 0.02, 2)


def test_sl_beats_tp_in_same_candle_with_1_pip_slippage():
    p = _pos(stop_loss_pips=20, take_profit_pips=20)
    ex = f.check_bar(p, T0 + 60, p.entry, p.tp_price + 0.001, p.sl_price - 0.001, p.entry)
    assert ex.reason == "stop_loss"
    assert ex.price == pytest.approx(p.sl_price - 0.0001)
    assert ex.profit < -p.sl_amount + 0.005


def test_tp_pays_exactly_and_gap_through_sl():
    p = _pos(stop_loss_pips=20, take_profit_pips=20)
    ex = f.check_bar(p, T0 + 60, p.entry, p.tp_price, p.entry - 0.0001, p.entry)
    assert (ex.reason, ex.profit) == ("take_profit", p.tp_amount)
    gap = p.sl_price - 0.0030
    ex = f.check_bar(p, T0 + 60, gap, gap, gap, gap)
    assert ex.reason == "stop_loss" and ex.price == pytest.approx(gap - 0.0001)


def test_stop_out_caps_loss_at_stake():
    p = _pos()
    crash = p.stop_out - 0.0100
    ex = f.check_bar(p, T0 + 60, crash, crash, crash, crash)
    assert (ex.reason, ex.profit) == ("stop_out", -3.0)
    # SL far beyond stop out is dropped: the stop out protects the trade.
    assert _pos(stop_loss_pips=500).sl_price is None


def test_down_trade_mirror():
    p = _pos(direction="MULTDOWN", stop_loss_pips=20, take_profit_pips=20)
    assert p.sl_price > p.entry > p.tp_price
    ex = f.check_bar(p, T0 + 60, p.entry, p.sl_price, p.tp_price, p.entry)
    assert ex.reason == "stop_loss"


def test_stress_raises_commission():
    assert _pos(stress=1.5).commission == pytest.approx(1.5 * _pos().commission)


def test_profit_rounded_to_cent():
    p = _pos()
    assert f.close_at(p, T0 + 60, 1.10037, "manual").profit == round(f.profit_at(p, 1.10037), 2)
