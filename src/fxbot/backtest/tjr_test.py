"""Step 2 of the TJR test (docs/tjr_test_plan.md): the 30 variants, fixed before any run.

Method: the incubator pre-screen (fxbot.backtest.prescreen) on data before 2026-10-31 only:
the same six walk-forward rounds (24 months train, 6 months test, out of sample 2023-10-27 to
2026-10-26), the measured commission by hour, 0.5 / 1 pip slippage, every CLAUDE.md hard limit
and the calendar rules, a 1.5x commission run, and the luck check against coin-toss runs on the
candidate's own signals.

Variants (30 = 16 + 8 + 6):
- 8 ideas = 4 entry models x 2 execution timeframes. Each has 2 grid points, n = 6 or 12
  execution candles (the only setting the walk-forward chooses): 16 variants.
- "be": each idea's walk-forward schedule with the break-even stop update on: 8 variants.
- "touch": the labelled C18 alternative (enter at the execution close that touched the zone)
  for models 2-4, on each idea's schedule: 6 variants.
Settings per variant (at most 5): model, n, breakeven, confirm (the execution timeframe is the
strategy class).

The luck check replays the candidate's own signals with a coin-toss direction (TJRReplay). Every
trade is closed by 17:55 UTC on its opening day, so the replay engine only needs the 05:00-18:00
UTC part of days with a signal; days without a signal cannot change the result.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from fxbot import symbols as symbols_mod
from fxbot.backtest import fills
from fxbot.backtest import prescreen as P
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.mt5 import SPREAD_MICRO, mt5_profit
from fxbot.strategies.base import Enter
from fxbot.strategies.tjr import TJR5m, TJR15m

ROOT = Path(__file__).resolve().parents[3]
MAJORS_TABLE = "research/phase2/cost_by_hour.json"
PAIRS2_TABLE = "research/phase2/cost_by_hour_pairs2.json"
PAIRS2_RULE = "research/incubator_prescreen/pairs2_cost_rule.json"
REQUIRED_NEW_PAIR = "frxGBPJPY"            # the owner asked for GBP/JPY by name
CLASSES = {"5m": TJR5m, "15m": TJR15m}
N_GRID = (6, 12)
LUCK_RUNS = P.LUCK_RUNS                     # 200, as in the incubator pre-screen
MIN_TRADES_PER_DAY_WAIVED = 0.3            # owner: the 1.5/day check may be waived only above this
MAX_VARIANTS = 30


def ideas() -> dict[str, dict]:
    out = {}
    for model in (1, 2, 3, 4):
        for tf in ("5m", "15m"):
            out[f"m{model}_{tf}"] = {"tf": tf, "model": model,
                                     "grid": [{"model": model, "n": n, "breakeven": False, "confirm": "ltf"}
                                              for n in N_GRID]}
    return out


def derived() -> dict[str, dict]:
    """Variants run on an idea's walk-forward schedule with one setting changed."""
    out = {}
    for key, idea in ideas().items():
        out[f"{key}_be"] = {"idea": key, "change": {"breakeven": True}}
        if idea["model"] != 1:
            out[f"{key}_touch"] = {"idea": key, "change": {"confirm": "touch"}}
    return out


def variant_count() -> int:
    return sum(len(i["grid"]) for i in ideas().values()) + len(derived())


assert variant_count() <= MAX_VARIANTS
assert all(len(p) <= 5 for i in ideas().values() for p in i["grid"])


# ----------------------------------------------------------------------------- setup
def sha256(path: str) -> str:
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def pair_list() -> tuple[tuple[str, ...], list[str]]:
    """(symbols, commission table files): the majors plus the new pairs kept by Monday's cost check."""
    rule = ROOT / PAIRS2_RULE
    if not rule.exists():
        raise SystemExit(f"{PAIRS2_RULE} is missing: run Monday's cost check (scripts/pairs2_cost_rule.py) first")
    kept = json.loads(rule.read_text())["kept"]
    if REQUIRED_NEW_PAIR not in kept:
        raise SystemExit(f"{REQUIRED_NEW_PAIR} did not pass Monday's cost check (kept: {kept}); "
                         "ask the owner before running without it")
    syms = symbols_mod.MAJORS + tuple(s for s in symbols_mod.PAIRS2 if s in kept)
    return symbols_mod.check(syms), [MAJORS_TABLE, PAIRS2_TABLE]


def table(paths: list[str]) -> fills.CommissionTable:
    return fills.CommissionTable.merged([ROOT / p for p in paths])


# ----------------------------------------------------------------------------- luck data
def signal_day_windows(m1: Bars, days: set[int]) -> Bars:
    """Only 05:00-18:00 UTC of the given days (day = epoch // 86400)."""
    sod = m1.epoch % 86400
    keep = np.isin(m1.epoch // 86400, np.fromiter(days, dtype=np.int64)) & (sod >= 5 * 3600) & (sod < 18 * 3600)
    return Bars(*(a[keep] for a in (m1.epoch, m1.end, m1.open, m1.high, m1.low, m1.close)))


def replay_data(base: dict, signals: dict, timeframe: str) -> dict:
    days = {int(t) // 86400 for (_, t) in signals}
    out = {}
    for s, (m1, _) in base.items():
        b = signal_day_windows(m1, days)
        out[s] = (b, aggregate(b, timeframe))
    return out


def parse_signals(rows) -> dict:
    """[(symbol, epoch, repr(Enter))] -> {(symbol, epoch): Enter}."""
    return {(s, int(t)): eval(a, {"__builtins__": {}}, {"Enter": Enter}) for s, t, a in rows}


# ----------------------------------------------------------------------------- report figures
def cost_share_of_risk(trades: list[dict]) -> dict:
    """Cost per trade (commission + 0.5 pip entry slippage, in pips) as a share of the stop
    distance (the risk). The owner's rule keeps this at or under 25%."""
    shares, sl = [], []
    for t in trades:
        if not t.get("sl_pips"):
            continue
        size = t["stake"] * t["multiplier"]
        cost = t["commission"] * t["entry"] / size / symbols_mod.PIP[t["symbol"]] + fills.ENTRY_SLIPPAGE_PIPS
        shares.append(cost / t["sl_pips"])
        sl.append(t["sl_pips"])
    if not shares:
        return {"median": None, "mean": None, "avg_stop_pips": None}
    return {"median": round(float(np.median(shares)), 3), "mean": round(float(np.mean(shares)), 3),
            "avg_stop_pips": round(float(np.mean(sl)), 1)}


def gross_pips_per_trade(trades: list[dict]) -> dict:
    """Before-cost edge: the price move in the trade's favour, in pips, with the modelled slippage
    added back (so it is the move the setup itself captured)."""
    from fxbot.backtest.audit import gross_of
    per = {}
    for t in trades:
        pips = gross_of(t) * t["entry"] / (t["stake"] * t["multiplier"]) / symbols_mod.PIP[t["symbol"]]
        per.setdefault(t["symbol"], []).append(pips)
    allp = [x for v in per.values() for x in v]
    return {"all": round(float(np.mean(allp)), 2) if allp else None,
            "per_pair": {s: round(float(np.mean(v)), 2) for s, v in per.items()}}


def mt5_view(trades: list[dict]) -> dict:
    """COMPARISON ONLY (CLAUDE.md): the same trades at Deriv MT5 micro spreads, majors only (the
    project has MT5 specs for the majors only; every TJR trade closes the same day, so no swap)."""
    maj = [t for t in trades if t["symbol"] in SPREAD_MICRO]
    return {"pairs": sorted(SPREAD_MICRO), "trades": len(maj),
            "net_mt5": round(sum(mt5_profit(t) for t in maj), 2),
            "net_deriv_same_trades": round(sum(t["profit"] for t in maj), 2)}


def trades_per_day_check(per_day: float) -> dict:
    return {"c3_trades_per_day_1_5": per_day >= P.MIN_TRADES_PER_DAY,
            "c3_waivable_at_0_3": per_day >= MIN_TRADES_PER_DAY_WAIVED}


def oos_days() -> int:
    v0, v1 = P.oos_span()
    return P.trading_days(v0, v1)


def iso(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")
