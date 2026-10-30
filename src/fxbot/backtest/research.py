"""Phase 4 research harness: walk-forward selection, stitched out-of-sample run, luck check.

Pre-holdout data only (before 2026-04-28); every date here is checked.

1. Grid: each parameter set of a family (one "variant", logged in
   research/log.md) is backtested once over the whole pre-holdout period at the
   measured commission, kill switch in research "observe" mode.
2. Walk-forward: 24 months to choose, the next 6 months out of sample, stepped
   by 6 months (5 rounds, 2023-10-27 to 2026-04-26). In each round the variant
   with the best net profit / max drawdown on the training window (3 pairs
   combined, trade returns compounded) is picked (owner's rule, 30 Oct).
3. Out of sample: one continuous run over the 5 test windows, switching to
   each round's pick at its start (Scheduled). Measured and 1.5x commission;
   MT5 for comparison.
4. Luck check: the same run with random entries (RandomEntry): same stops and
   exits, same candle hours, same rate of signals per pair and hour, random
   direction. The candidate must beat the 95th percentile of >= 200 such runs.

Scoring a training window from a full-period run is fair: the engine has no
look-ahead, so trades opened inside the window only used data up to their own
time.
"""

from __future__ import annotations

import datetime as dt
import math
from collections import Counter
from functools import lru_cache

import numpy as np

from fxbot.backtest.candles import Bars, aggregate, load_m1
from fxbot.backtest.engine import Engine
from fxbot.backtest.metrics import max_drawdown
from fxbot.backtest.walkforward import Window, rolling_windows
from fxbot.data.split import HOLDOUT_START, HoldoutError
from fxbot.strategies.base import Strategy
from fxbot.strategies.families import FamilyStrategy, hour_of

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
DATA_START = dt.date(2021, 10, 27)
DATA_END = HOLDOUT_START - dt.timedelta(days=1)
TRAIN_MONTHS, VALID_MONTHS = 24, 6
WARMUP_DAYS = 120          # candles before the first out-of-sample day, for indicators only


def epoch_of(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def windows() -> list[Window]:
    return rolling_windows(DATA_START, DATA_END, TRAIN_MONTHS, VALID_MONTHS)


# ----------------------------------------------------------------------------- data
@lru_cache(maxsize=None)
def _m1(symbol: str) -> Bars:
    return load_m1(symbol, DATA_START, DATA_END)


def slice_bars(b: Bars, t0: int, t1: int) -> Bars:
    i, j = np.searchsorted(b.epoch, [t0, t1])
    return Bars(*(a[i:j] for a in (b.epoch, b.end, b.open, b.high, b.low, b.close)))


@lru_cache(maxsize=None)
def market_data(timeframe: str, start: dt.date, end: dt.date) -> dict:
    """{symbol: (1m bars, timeframe bars)} for start..end inclusive (pre-holdout only)."""
    if end >= HOLDOUT_START:
        raise HoldoutError("research data must end before the holdout")
    out = {}
    for s in SYMBOLS:
        m1 = slice_bars(_m1(s), epoch_of(start), epoch_of(end + dt.timedelta(days=1)))
        out[s] = (m1, aggregate(m1, timeframe))
    return out


def run_engine(strategy: Strategy, start: dt.date = DATA_START, end: dt.date = DATA_END,
               stress: float = 1.0) -> Engine:
    eng = Engine(strategy, list(SYMBOLS), start, end, stress=stress,
                 data=market_data(strategy.timeframe, start, end), kill_switch="observe")
    eng.run()
    return eng


# ----------------------------------------------------------------------------- scoring
def window_score(trades: list[dict], t0: int, t1: int) -> dict:
    """Net return / max drawdown of trades opened in [t0, t1), returns compounded."""
    sel = [t for t in trades if t0 <= t["entry_epoch"] < t1]
    if not sel:
        return {"trades": 0, "net": 0.0, "dd": 0.0, "score": -math.inf}
    r = np.array([t["profit"] / (t["balance_after"] - t["profit"]) for t in sel])
    curve = np.cumprod(1 + r)
    net = float(curve[-1] - 1)
    dd = max_drawdown([1.0, *curve.tolist()])
    return {"trades": len(sel), "net": net, "dd": dd, "score": net / max(dd, 0.01)}


def pick_per_window(grid_trades: dict[int, list[dict]]) -> list[dict]:
    """For each walk-forward round, the variant with the best training score."""
    picks = []
    for w in windows():
        t0, t1 = epoch_of(w.train_start), epoch_of(w.train_end + dt.timedelta(days=1))
        scores = {i: window_score(tr, t0, t1) for i, tr in grid_trades.items()}
        best = max(sorted(scores), key=lambda i: scores[i]["score"])
        picks.append({"window": w, "variant": best, "train": scores[best]})
    return picks


# ----------------------------------------------------------------------------- stitched OOS
class Scheduled(Strategy):
    """Runs one family with the parameters picked for each out-of-sample window.

    No new entries before the first window starts (that part only warms up
    indicators). Exits of an open trade keep working across a switch.
    """

    def __init__(self, cls: type[FamilyStrategy], schedule: list[tuple[int, dict]]):
        self.cls = cls
        self.schedule = sorted(schedule, key=lambda x: x[0])
        self.inner = {i: cls(**p) for i, (_, p) in enumerate(self.schedule)}
        self.name, self.timeframe = cls.name, cls.timeframe
        self.params = {"schedule": [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), p)
                                    for t, p in self.schedule]}
        self.flat = Counter()         # (symbol, hour) -> candles seen while flat with nothing pending
        self.entries = Counter()      # (symbol, hour) -> entry signals

    def _active(self, t: int) -> FamilyStrategy | None:
        k = None
        for i, (t0, _) in enumerate(self.schedule):
            if t >= t0:
                k = i
        return None if k is None else self.inner[k]

    def on_candle(self, symbol, candles, position, pending):
        t = int(candles.end[-1])
        s = self._active(t)
        if s is None:
            return []
        if position is None and not pending:
            self.flat[(symbol, hour_of(t))] += 1
        acts = s.on_candle(symbol, candles, position, pending)
        if position is None and not pending and acts:
            self.entries[(symbol, hour_of(t))] += 1
        return acts


class RandomEntry(Scheduled):
    """The luck check: same schedule, stops and exits, random entries.

    At each candle where the candidate was flat, enter with the candidate's
    own frequency for that pair and hour (entries / flat candles), in a
    random direction.
    """

    def __init__(self, cls, schedule, rates: dict, seed: int):
        super().__init__(cls, schedule)
        self.rates = rates
        self.rng = np.random.default_rng(seed)
        for s in self.inner.values():
            s.entry = self._random_entry

    def _random_entry(self, symbol, c):
        p = self.rates.get((symbol, hour_of(int(c.end[-1]))), 0.0)
        u, d = self.rng.random(), self.rng.random()
        if u >= p:
            return None
        return "MULTUP" if d < 0.5 else "MULTDOWN"


def oos_span() -> tuple[dt.date, dt.date]:
    ws = windows()
    return ws[0].valid_start, ws[-1].valid_end


def schedule_from(picks: list[dict], grid: list[dict]) -> list[tuple[int, dict]]:
    return [(epoch_of(p["window"].valid_start), grid[p["variant"]]) for p in picks]


def run_oos(strategy: Scheduled, stress: float = 1.0) -> Engine:
    v0, v1 = oos_span()
    warm = getattr(strategy.cls, "warmup_days", WARMUP_DAYS)
    return run_engine(strategy, v0 - dt.timedelta(days=warm), v1, stress)


def entry_rates(s: Scheduled) -> dict:
    return {k: s.entries[k] / n for k, n in s.flat.items() if n and s.entries[k]}


# ----------------------------------------------------------------------------- the grids
def _grid(**axes) -> list[dict]:
    out = [{}]
    for k, vals in axes.items():
        out = [{**g, k: v} for g in out for v in vals]
    return out


def _f5_grid() -> list[dict]:
    out = []
    for entry in (6, 8, 10, 16, 17):
        exits = (12, 14, 16) if entry < 12 else (19, 20, 21)
        out += [{"entry_hour": entry, "exit_hour": x, "stop_pips": s} for x in exits for s in (0, 20)]
    return out


# family -> [(strategy name, timeframe fixed per sub-grid, grid)]. Declared before testing;
# every grid point is one variant. Budget: at most 30 variants per family.
FAMILIES = {
    "f1": [("f1_london_breakout", _grid(box_start=(0, 3), cutoff=(10, 15), sl_frac=(0.5, 1.0),
                                        tp_mult=(1.0, 1.5, 2.5)))],
    "f2": [("f2_trend_breakout", _grid(n=(20, 55, 100), sl_atr=(1.5, 2.5, 3.5), m=(10, 20))),
           ("f2_trend_breakout_1d", _grid(n=(10, 20, 55), sl_atr=(0.75, 1.25), m=(5, 10)))],
    "f3": [("f3_trend_pullback", _grid(trend_len=(20, 50), pullback=(15, 30), sl_atr=(1.5, 2.5),
                                       tp_r=(1.5, 2.5))),
           ("f3_trend_pullback_1h", _grid(trend_len=(20, 50), pullback=(15, 30), sl_atr=(2.0,),
                                          tp_r=(1.5, 2.5)))],
    "f4": [("f4_mean_reversion", _grid(length=(20, 50), stretch=(2.0, 3.0), er_max=(0.2, 0.35),
                                       sl_atr=(1.5, 3.0))),
           ("f4_mean_reversion_4h", _grid(length=(20, 50), stretch=(2.0, 3.0), er_max=(0.2, 0.35),
                                          sl_atr=(2.0,)))],
    "f5": [("f5_session_drift", _f5_grid())],
}
# Round 2 (owner, 30 Oct: up to 4 new families designed from round 1's failures).
FAMILIES.update({
    "f6": [("f6_quiet_london_breakout", _grid(box_max=(0.3, 0.5), tp_atr=(0.6, 1.0), sl_frac=(0.5, 1.0)))],
    "f7": [("f7_weekly_momentum", _grid(lookback=(20, 60, 120), sl_atr=(0, 1.0, 1.5)))],
    "f8": [("f8_morning_momentum", _grid(entry_hour=(9, 10, 11), k=(0.25, 0.4), sl_frac=(0.5, 1.0)))],
})
ROUND = {"f1": 1, "f2": 1, "f3": 1, "f4": 1, "f5": 1, "f6": 2, "f7": 2, "f8": 2}
MAX_VARIANTS = 30
for _f, _subs in FAMILIES.items():
    assert sum(len(g) for _, g in _subs) <= MAX_VARIANTS, _f


def variants_through_round(r: int) -> int:
    """Running total of variants tried, all families up to and including round r."""
    return sum(len(g) for f, subs in FAMILIES.items() if ROUND[f] <= r for _, g in subs)


def luck_rule(family: str) -> tuple[int, int]:
    """(percentile to beat, random runs). Owner's rule: p95 while the running total is at most
    150 variants, p99 above. Judged on the total at the end of the family's round. p99 needs
    more runs to be stable, so 500 instead of 200."""
    return (95, 200) if variants_through_round(ROUND[family]) <= 150 else (99, 500)


# ----------------------------------------------------------------------------- "is it fake?"
def neighbours(grid: list[dict], i: int) -> list[int]:
    """Grid points one step away from point i on exactly one setting."""
    axes = {k: sorted({g[k] for g in grid}) for k in grid[i]}
    out = []
    for j, g in enumerate(grid):
        diff = [k for k in g if g[k] != grid[i][k]]
        if len(diff) == 1:
            k = diff[0]
            if abs(axes[k].index(g[k]) - axes[k].index(grid[i][k])) == 1:
                out.append(j)
    return out


def robustness(trades: list[dict], grid_trades: dict[int, list[dict]], picks: list[dict],
               grid: list[dict]) -> dict:
    """Owner's checks before calling anything a candidate (out-of-sample trades).

    - not one pair: without its best pair, the other pairs together still make money
    - not one period: profitable in at least 3 of the 5 half-year test windows, and
      still profitable without the best window
    - not a few huge trades: still profitable without its largest 2% of trades (at least 5)
    - not one exact setting: in each round's test window, the picked setting's grid
      neighbours made money on average, and at least half of them made money
    """
    net = lambda ts: sum(t["profit"] for t in ts)
    pairs = {s: net([t for t in trades if t["symbol"] == s]) for s in SYMBOLS}
    best_pair = max(pairs, key=pairs.get)
    ws = windows()
    per_win = [net([t for t in trades if epoch_of(w.valid_start) <= t["entry_epoch"]
                    < epoch_of(w.valid_end + dt.timedelta(days=1))]) for w in ws]
    k = max(5, math.ceil(0.02 * len(trades)))
    rest = sorted(t["profit"] for t in trades)[:-k] if len(trades) > k else []
    nb_returns = []
    for p in picks:
        w = p["window"]
        t0, t1 = epoch_of(w.valid_start), epoch_of(w.valid_end + dt.timedelta(days=1))
        nb_returns += [window_score(grid_trades[j], t0, t1)["net"] for j in neighbours(grid, p["variant"])]
    nb = np.array(nb_returns)
    checks = {
        "not_one_pair": net([t for t in trades if t["symbol"] != best_pair]) > 0,
        "not_one_period": sum(v > 0 for v in per_win) >= 3 and sum(per_win) - max(per_win) > 0,
        "not_few_big_trades": sum(rest) > 0,
        "nearby_settings_work": bool(len(nb)) and nb.mean() > 0 and (nb > 0).mean() >= 0.5,
    }
    detail = {"per_pair": {s: round(v, 2) for s, v in pairs.items()},
              "per_test_window": [round(v, 2) for v in per_win],
              "net_without_top_trades": round(sum(rest), 2), "top_trades_removed": k,
              "neighbour_window_returns_pct": [round(x * 100, 1) for x in nb_returns]}
    return {"checks": {k2: bool(v) for k2, v in checks.items()}, "detail": detail}
