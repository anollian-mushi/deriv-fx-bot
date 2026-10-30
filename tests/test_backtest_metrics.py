import datetime as dt

import pytest

from fxbot.backtest import metrics, mt5, walkforward as wf
from fxbot.data.split import HoldoutError


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


def test_summary_metrics():
    trades = [{"profit": p, "commission": 0.07, "delay_min": d} for p, d in
              [(1.0, 0), (-0.5, 30), (2.0, 0), (-1.0, 90)]]
    s = metrics.summarise(trades, 100.0)
    assert s["trades"] == 4 and s["final_balance"] == 101.5 and s["net_return_pct"] == 1.5
    assert s["win_rate_pct"] == 50.0 and s["avg_win"] == 1.5 and s["avg_loss"] == -0.75
    assert s["profit_factor"] == 2.0
    assert s["late_fills"] == 2 and s["avg_delay_min"] == 60.0
    assert s["min_target_met"]                       # 1.5 >= 3 x 0.07
    assert s["max_drawdown_pct"] == 0.98             # 102.5 -> 101.5
    mc = s["monte_carlo_drawdown_pct"]
    assert mc["runs"] == 1000 and mc["p50"] <= mc["p95"] <= mc["p99"]


def test_mt5_reprice_and_swap_nights():
    # Mon 10:00 -> Thu 10:00 crosses Mon, Tue rollovers and Wednesday (x3) = 5 nights
    assert mt5.rollovers(ep(2025, 3, 3, 10), ep(2025, 3, 6, 10)) == 5
    assert mt5.rollovers(ep(2025, 3, 3, 10), ep(2025, 3, 3, 15)) == 0
    t = {"symbol": "frxEURUSD", "direction": "MULTUP", "entry": 1.1, "exit": 1.101, "stake": 3.0,
         "multiplier": 100, "entry_epoch": ep(2025, 3, 3, 10), "exit_epoch": ep(2025, 3, 3, 15)}
    units = 300 / 1.1
    assert mt5.mt5_profit(t) == round(units * (0.001 - 0.00007), 2)
    j = dict(t, symbol="frxUSDJPY", entry=150.0, exit=150.5)
    assert mt5.mt5_profit(j) == round(300 * (0.5 - 0.009) / 150.5, 2)


def test_walk_forward_windows_and_holdout():
    w = wf.rolling_windows(dt.date(2022, 1, 1), dt.date(2023, 12, 31), 12, 3)
    assert w[0].train_start == dt.date(2022, 1, 1) and w[0].train_end == dt.date(2022, 12, 31)
    assert w[0].valid_start == dt.date(2023, 1, 1) and w[0].valid_end == dt.date(2023, 3, 31)
    assert len(w) == 4 and w[-1].valid_end == dt.date(2023, 12, 31)
    assert all(a.valid_end < b.valid_start for a, b in zip(w, w[1:]))
    anchored = wf.rolling_windows(dt.date(2022, 1, 1), dt.date(2023, 12, 31), 12, 3, anchored=True)
    assert all(x.train_start == dt.date(2022, 1, 1) for x in anchored)
    with pytest.raises(HoldoutError):
        wf.rolling_windows(dt.date(2022, 1, 1), dt.date(2026, 4, 28), 12, 3)
