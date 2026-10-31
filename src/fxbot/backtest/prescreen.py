"""Incubator pre-screen (31 Oct 2026): walk-forward test of a new idea on data before the
untouched period, before it may be registered as an incubator candidate.

The owner's rule for a new candidate (check 6): pre-screen on data BEFORE 2026-10-31
only, walk-forward as in Phase 4, profitable before costs, and better than the median
of 200 random-direction runs. This module is that test. It differs from
fxbot.backtest.research in two ways only:

- Data: Dukascopy 1m to 2026-04-27 and then Deriv 1m from the used-up holdout
  (2026-04-28 to 2026-10-30). The untouched period (2026-10-31 on) is never read:
  fxbot.backtest.candles raises UntouchedError for any date in it unless the caller is
  the incubator, and nothing here passes forward=True.
- Walk-forward: the same 24-month train / 6-month test windows, stepped by 6 months,
  now with six rounds (test windows from 2023-10-27 to 2026-10-26).

Everything else is the Phase 4 harness: each grid point is one variant run once over
the whole period; in each round the variant with the best net / max drawdown on its
training window is picked; the picks are stitched into one out-of-sample run at the
measured commission by hour, 0.5 / 1 pip slippage, every hard risk limit and the
calendar rules; the luck check replays the candidate's own signal candles with a
coin-toss direction (the Round 4 / incubator rule). The pre-screen verdict is
"gross profit (costs added back) above zero AND net profit above the median of the
random runs". The other owner checks (cost ratio, trades per day) are reported from
the same run.
"""

from __future__ import annotations

import datetime as dt
import math
from functools import lru_cache

import numpy as np

from fxbot import sessions
from fxbot.backtest import research as R
from fxbot.backtest.audit import cost_of, gross_of
from fxbot.backtest.candles import Bars, aggregate, load_m1
from fxbot.backtest.engine import Engine
from fxbot.backtest.walkforward import Window, _add_months
from fxbot.data.split import UNTOUCHED_START, UntouchedError
from fxbot.strategies.base import Strategy

SYMBOLS = R.SYMBOLS
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
DATA_START = dt.date(2021, 10, 27)
DATA_END = UNTOUCHED_START - dt.timedelta(days=1)          # 2026-10-30, the last allowed day
TRAIN_MONTHS, VALID_MONTHS = 24, 6
WARMUP_DAYS = 120
LUCK_RUNS = 200
MIN_TRADES_PER_DAY = 1.5           # owner check 3
MIN_MOVE_TO_COST = 3.0             # owner check 2


def epoch_of(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def windows() -> list[Window]:
    """Six walk-forward rounds, the last test window ending 2026-10-26."""
    out, k = [], 0
    while True:
        t0 = _add_months(DATA_START, k * VALID_MONTHS)
        t1 = _add_months(DATA_START, k * VALID_MONTHS + TRAIN_MONTHS) - dt.timedelta(days=1)
        v0 = t1 + dt.timedelta(days=1)
        v1 = _add_months(v0, VALID_MONTHS) - dt.timedelta(days=1)
        if v1 > DATA_END:
            break
        out.append(Window(t0, t1, v0, v1))
        k += 1
    return out


def oos_span() -> tuple[dt.date, dt.date]:
    ws = windows()
    return ws[0].valid_start, ws[-1].valid_end


# ----------------------------------------------------------------------------- data
@lru_cache(maxsize=None)
def _m1(symbol: str) -> Bars:
    # include_holdout=True: the 2026-04-28 holdout is used up and allowed here (CLAUDE.md).
    # forward stays False, so the untouched period raises before any file is read.
    return load_m1(symbol, DATA_START, DATA_END, include_holdout=True)


@lru_cache(maxsize=None)
def market_data(timeframe: str, start: dt.date, end: dt.date) -> dict:
    if end >= UNTOUCHED_START:
        raise UntouchedError("pre-screen data must end before the untouched period")
    out = {}
    for s in SYMBOLS:
        m1 = R.slice_bars(_m1(s), epoch_of(start), epoch_of(end + dt.timedelta(days=1)))
        out[s] = (m1, aggregate(m1, timeframe))
    return out


def run_engine(strategy: Strategy, start: dt.date = DATA_START, end: dt.date = DATA_END,
               stress: float = 1.0) -> Engine:
    eng = Engine(strategy, list(SYMBOLS), start, end, stress=stress,
                 data=market_data(strategy.timeframe, start, end), kill_switch="observe")
    eng.run()
    return eng


# ----------------------------------------------------------------------------- walk-forward
def pick_per_window(grid_trades: dict[int, list[dict]]) -> list[dict]:
    picks = []
    for w in windows():
        t0, t1 = epoch_of(w.train_start), epoch_of(w.train_end + dt.timedelta(days=1))
        scores = {i: R.window_score(tr, t0, t1) for i, tr in grid_trades.items()}
        best = max(sorted(scores), key=lambda i: scores[i]["score"])
        picks.append({"window": w, "variant": best, "train": scores[best]})
    return picks


def schedule_from(picks: list[dict], grid: list[dict]) -> list[tuple[int, dict]]:
    return [(epoch_of(p["window"].valid_start), grid[p["variant"]]) for p in picks]


def run_oos(strategy: R.Scheduled, stress: float = 1.0) -> Engine:
    v0, v1 = oos_span()
    warm = getattr(strategy.cls, "warmup_days", WARMUP_DAYS)
    return run_engine(strategy, v0 - dt.timedelta(days=warm), v1, stress)


# ----------------------------------------------------------------------------- checks
def trading_days(start: dt.date, end: dt.date) -> int:
    n, d = 0, start
    while d <= end:
        n += sessions.is_trading_day(d)
        d += dt.timedelta(days=1)
    return n


def move_and_cost_pips(trades: list[dict]) -> dict:
    """Owner check 2: the average size of the price move a trade captured (|exit - entry| in
    pips, before costs) against the average cost it paid (commission + slippage, in pips)."""
    if not trades:
        return {"avg_abs_move_pips": None, "avg_cost_pips": None, "ratio": None}
    moves, costs = [], []
    for t in trades:
        pip = PIP[t["symbol"]]
        moves.append(abs(t["exit"] - t["entry"]) / pip)
        size = t["stake"] * t["multiplier"]
        c = cost_of(t)
        usd = c["commission"] + c["entry_slippage"] + c["sl_slippage"]
        costs.append(usd * t["entry"] / size / pip)          # USD cost -> pips at this size
    m, c = float(np.mean(moves)), float(np.mean(costs))
    return {"avg_abs_move_pips": round(m, 2), "avg_cost_pips": round(c, 2),
            "ratio": round(m / c, 2) if c else None}


def luck_summary(random_nets, random_gross, net: float, gross: float) -> dict:
    nets = np.asarray(list(random_nets), dtype=float)
    gr = np.asarray(list(random_gross), dtype=float)
    if not len(nets):
        return {"runs": 0}
    return {"runs": int(len(nets)), "median_net": float(np.median(nets)), "p95_net": float(np.percentile(nets, 95)),
            "p99_net": float(np.percentile(nets, 99)), "share_beaten_net": float((nets < net).mean()),
            "median_gross": float(np.median(gr)), "share_beaten_gross": float((gr < gross).mean()),
            "beats_median": bool(net > np.median(nets))}


def summary(trades: list[dict], stress_trades: list[dict], kill_events: int, luck: dict, grid_size: int,
            params: int) -> dict:
    v0, v1 = oos_span()
    days = trading_days(v0, v1)
    net = round(sum(t["profit"] for t in trades), 2)
    gross = round(sum(gross_of(t) for t in trades), 2)
    ws = windows()
    per_win = [round(sum(t["profit"] for t in trades if epoch_of(w.valid_start) <= t["entry_epoch"]
                         < epoch_of(w.valid_end + dt.timedelta(days=1))), 2) for w in ws]
    per_win_gross = [round(sum(gross_of(t) for t in trades if epoch_of(w.valid_start) <= t["entry_epoch"]
                               < epoch_of(w.valid_end + dt.timedelta(days=1))), 2) for w in ws]
    per_pair = {s: {"trades": sum(t["symbol"] == s for t in trades),
                    "net": round(sum(t["profit"] for t in trades if t["symbol"] == s), 2),
                    "gross": round(sum(gross_of(t) for t in trades if t["symbol"] == s), 2)} for s in SYMBOLS}
    wins = [t["profit"] for t in trades if t["profit"] > 0]
    losses = [t["profit"] for t in trades if t["profit"] <= 0]
    mc = move_and_cost_pips(trades)
    per_day = len(trades) / days if days else 0.0
    checks = {
        "c2_move_3x_cost": bool(mc["ratio"] is not None and mc["ratio"] >= MIN_MOVE_TO_COST),
        "c3_trades_per_day_1_5": per_day >= MIN_TRADES_PER_DAY,
        "c5_params_5_or_fewer": params <= 5,
        "c6_gross_positive": gross > 0,
        "c6_beats_random_median": bool(luck.get("beats_median", False)),
        "no_kill_switch": kill_events == 0,
    }
    return {
        "oos_span": [v0.isoformat(), v1.isoformat()], "trading_days": days,
        "trades": len(trades), "trades_per_day": round(per_day, 2),
        "net_measured": net, "net_1_5x": round(sum(t["profit"] for t in stress_trades), 2), "gross": gross,
        "gross_pips_per_trade": round(float(np.mean([gross_of(t) * t["entry"] / (t["stake"] * t["multiplier"])
                                                     / PIP[t["symbol"]] for t in trades])), 2) if trades else None,
        "win_rate_pct": round(100 * len(wins) / len(trades), 1) if trades else None,
        "avg_win": round(float(np.mean(wins)), 3) if wins else None,
        "avg_loss": round(float(np.mean(losses)), 3) if losses else None,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
        "kill_events": kill_events, "per_pair": per_pair, "per_window_net": per_win,
        "per_window_gross": per_win_gross, "move_vs_cost": mc, "luck": luck, "grid_size": grid_size,
        "checks": checks, "prescreen_pass": all(checks[k] for k in ("c6_gross_positive", "c6_beats_random_median")),
        "all_checks": all(checks.values()),
    }


# ----------------------------------------------------------------------------- the ideas
def _grid(**axes) -> list[dict]:
    out = [{}]
    for k, vals in axes.items():
        out = [{**g, k: v} for g in out for v in vals]
    return out


# idea -> (strategy name, grid). Declared before testing; every grid point is one variant;
# at most 8 variants and 5 settings per idea (the settings are chosen before testing, the
# walk-forward only picks among them).
IDEAS: dict[str, tuple[str, list[dict]]] = {
    "fix_reversal": ("i1_fix_reversal", _grid(k=(0.1, 0.2), hold_hours=(2, 4), stop=(0.0, 0.5))),
    "turtle_soup": ("i2_turtle_soup", _grid(sl_frac=(0.25, 0.5), tp_frac=(0.5, 0.75), cutoff=(12, 17))),
    "round_bounce": ("i3_round_bounce", _grid(sl_frac=(0.15, 0.3), tp_frac=(0.3, 0.6))),
    "round_break": ("i4_round_break", _grid(thru=(0.05, 0.1), sl_frac=(0.15, 0.3))),
    "asia_fade": ("i5_asia_fade", _grid(decision_hour=(7, 8), k=(0.25, 0.4), exit_hour=(12, 20))),
    "us_data_drift": ("i6_us_data_drift", _grid(k=(0.2, 0.3), exit_hour=(17, 20), stop=(0.0, 0.5))),
    "ny_into_asia": ("i7_ny_into_asia", _grid(k=(0.25, 0.4), exit_hour=(0, 6), stop=(0.0, 0.5))),
    "london_reversal": ("i8_london_reversal", _grid(k=(0.4, 0.6), exit_hour=(17, 20), stop=(0.0, 0.5))),
    "range_exhaustion": ("i9_range_exhaustion", _grid(r=(1.0, 1.3), sl_frac=(0.25, 0.5))),
    "trend_intraday": ("i10_trend_intraday", _grid(lookback=(5, 10), k=(0.5, 1.0), stop=(0.0, 0.5))),
    "ny_cut_breakout": ("i11_ny_cut_breakout", _grid(range_hours=(2, 3), sl_frac=(0.5, 1.0))),
    "twap_pullback": ("i12_twap_pullback", _grid(k=(0.3, 0.5), sl_frac=(0.2, 0.4))),
    "morning_overnight": ("i13_morning_overnight", _grid(decision_hour=(8, 10), k=(0.25, 0.4), stop=(0.0, 0.5))),
    "ny_cut_overnight": ("i14_ny_cut_overnight", _grid(range_hours=(2, 3), sl_frac=(0.5, 1.0))),
}
MAX_VARIANTS = 8
for _k, (_n, _g) in IDEAS.items():
    assert len(_g) <= MAX_VARIANTS and all(len(p) <= 5 for p in _g), _k
