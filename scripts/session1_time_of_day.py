"""Session 1: time-of-day test (definition: research/session1/definition.md, fixed before the run).

    python scripts/session1_time_of_day.py

Reads Dukascopy 1m mid prices dated 2021-10-27 to 2026-10-27 (never anything on or after
2026-10-31), builds UTC 1h candles over Deriv trading minutes, and writes
research/session1/results.json. Measurement only: no engine, no orders.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
import time
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401

from fxbot import sessions
from fxbot.data.candles import read_day
from fxbot.data.split import UNTOUCHED_START

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "session1" / "results.json"
PAIRS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
FIRST, LAST = dt.date(2021, 10, 27), dt.date(2026, 10, 27)
SPLIT = dt.date(2024, 4, 27)                     # newer half starts here
MIN_MINUTES = 30
SESSIONS = {"asian": range(0, 7), "london": range(7, 12), "overlap": range(12, 16),
            "new_york": range(16, 21), "late": range(21, 24)}
RANALDO = [  # (pair, session, predicted sign, whose home hours)
    ("frxEURUSD", "london", -1, "EUR"), ("frxEURUSD", "new_york", +1, "USD"),
    ("frxGBPUSD", "london", -1, "GBP"), ("frxGBPUSD", "new_york", +1, "USD"),
    ("frxUSDJPY", "asian", +1, "JPY"), ("frxUSDJPY", "new_york", -1, "USD"),
]
ENTRY_WINDOW = range(6, 18)
SHUFFLES = 200
SEED = 20261110
COST_TABLE = ROOT / "research" / "phase2" / "cost_by_hour.json"

assert LAST < UNTOUCHED_START


# ----------------------------------------------------------------------------- data
def hourly(pair: str) -> dict:
    """Arrays over 1h candles: day index, date ordinal, hour, return pips, range pips, open price."""
    rows = []
    d = FIRST
    while d <= LAST:
        if d >= UNTOUCHED_START:
            raise RuntimeError("refusing to read the untouched period")
        f = ROOT / "data_external" / "dukascopy" / pair / "1m" / f"{d:%Y-%m-%d}.csv.gz"
        if sessions.is_trading_day(d) and f.exists():
            candles, _ = read_day(f)
            by_hour: dict[int, list] = {}
            for c in candles:
                if sessions.market_open(c.epoch) and sessions.utc_date(c.epoch) == d:
                    by_hour.setdefault((c.epoch % 86400) // 3600, []).append(c)
            for h, cs in sorted(by_hour.items()):
                if len(cs) < MIN_MINUTES:
                    continue
                cs.sort(key=lambda c: c.epoch)
                o, cl = cs[0].open, cs[-1].close
                hi, lo = max(c.high for c in cs), min(c.low for c in cs)
                rows.append((d.toordinal(), h, (cl - o) / PIP[pair], (hi - lo) / PIP[pair], o))
        d += dt.timedelta(days=1)
    a = np.array(rows, dtype=float)
    return {"day": a[:, 0].astype(np.int64), "hour": a[:, 1].astype(int), "ret": a[:, 2],
            "rng": a[:, 3], "open": a[:, 4]}


def cost_pips(pair: str, hours: np.ndarray, opens: np.ndarray, table: dict) -> np.ndarray:
    rate = np.array([table["hours"][str(h)]["max_rate_pct"][pair] / 100 for h in range(24)])
    return rate[hours] * opens / PIP[pair]


# ----------------------------------------------------------------------------- statistics
def tstat(x: np.ndarray) -> float | None:
    if len(x) < 3 or x.std(ddof=1) == 0:
        return None
    return float(x.mean() / (x.std(ddof=1) / np.sqrt(len(x))))


def score(ret, cost, older, s=None):
    """(direction, S after cost, S before cost, per-half figures) for one pattern."""
    s = s if s is not None else (1 if ret.mean() >= 0 else -1)
    halves = {}
    for name, m in (("older", older), ("newer", ~older)):
        r, c = ret[m], cost[m]
        halves[name] = {"n": int(m.sum()), "mean": float(r.mean()), "cost": float(c.mean()),
                        "edge_after_cost": float(s * r.mean() - c.mean()), "t": tstat(r)}
    S = min(h["edge_after_cost"] for h in halves.values())
    S_gross = min(s * h["mean"] for h in halves.values())
    return s, S, S_gross, halves


def session_days(d: dict, cost: np.ndarray, hours: range):
    """Per day: summed return over the session's hours and the cost of its first hour."""
    m = np.isin(d["hour"], list(hours))
    day, hr, ret, c = d["day"][m], d["hour"][m], d["ret"][m], cost[m]
    out_day, out_ret, out_cost = [], [], []
    order = np.lexsort((hr, day))
    day, hr, ret, c = day[order], hr[order], ret[order], c[order]
    starts = np.r_[0, np.flatnonzero(np.diff(day)) + 1]
    ends = np.r_[starts[1:], len(day)]
    need = (len(hours) + 1) // 2
    for a, b in zip(starts, ends):
        if b - a >= need:
            out_day.append(day[a])
            out_ret.append(ret[a:b].sum())
            out_cost.append(c[a])
    return np.array(out_day), np.array(out_ret), np.array(out_cost)


def best_hourly(data: dict, costs: dict, split_ord: int, ret_override: dict | None = None,
                cost_override: dict | None = None) -> tuple[float, float, int]:
    """Best S (after cost), best S before cost, and number of passing combos over the 72."""
    best, best_g, passes = -np.inf, -np.inf, 0
    for p in PAIRS:
        d = data[p]
        ret = ret_override[p] if ret_override else d["ret"]
        cost = cost_override[p] if cost_override else costs[p]
        older = d["day"] < split_ord
        for h in range(24):
            m = d["hour"] == h
            _, S, Sg, _ = score(ret[m], cost[m], older[m])
            best, best_g = max(best, S), max(best_g, Sg)
            passes += S > 0
    return best, best_g, passes


def shuffle_within_days(d: dict, cost: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """Shuffle each day's hourly returns (with their costs) among that day's hours."""
    order = np.argsort(d["day"], kind="stable")
    day = d["day"][order]
    starts = np.r_[0, np.flatnonzero(np.diff(day)) + 1]
    ends = np.r_[starts[1:], len(day)]
    new_ret, new_cost = d["ret"].copy(), cost.copy()
    for a, b in zip(starts, ends):
        idx = order[a:b]
        perm = idx[rng.permutation(len(idx))]
        new_ret[idx] = d["ret"][perm]
        new_cost[idx] = cost[perm]
    return new_ret, new_cost


# ----------------------------------------------------------------------------- main
def main() -> int:
    t0 = time.time()
    table = json.loads(COST_TABLE.read_text())
    data = {p: hourly(p) for p in PAIRS}
    costs = {p: cost_pips(p, data[p]["hour"], data[p]["open"], table) for p in PAIRS}
    split_ord = SPLIT.toordinal()
    res = {"definition": "research/session1/definition.md", "data": {}, "hours": {}, "sessions": {},
           "ranaldo": [], "tests_counted": 0}
    for p in PAIRS:
        d = data[p]
        res["data"][p] = {"candles": int(len(d["ret"])), "days": int(len(np.unique(d["day"]))),
                          "first": dt.date.fromordinal(int(d["day"].min())).isoformat(),
                          "last": dt.date.fromordinal(int(d["day"].max())).isoformat()}
        older = d["day"] < split_ord
        rows = []
        for h in range(24):
            m = d["hour"] == h
            r = d["ret"][m]
            s, S, Sg, halves = score(r, costs[p][m], older[m])
            rows.append({"hour": h, "n": int(m.sum()), "mean_return": float(r.mean()), "sd": float(r.std(ddof=1)),
                         "t": tstat(r), "mean_range": float(d["rng"][m].mean()), "mean_cost": float(costs[p][m].mean()),
                         "edge_after_cost": float(abs(r.mean()) - costs[p][m].mean()), "direction": s,
                         "S": S, "S_gross": Sg, "passes": S > 0, "halves": halves,
                         "in_entry_window": h in ENTRY_WINDOW})
        res["hours"][p] = rows
        res["sessions"][p] = {}
        for name, hours in SESSIONS.items():
            day, ret, cost = session_days(d, costs[p], hours)
            s, S, Sg, halves = score(ret, cost, day < split_ord)
            res["sessions"][p][name] = {"hours_utc": f"{hours[0]:02d}-{hours[-1]:02d}", "n": int(len(ret)),
                                        "mean_return": float(ret.mean()), "t": tstat(ret),
                                        "mean_cost": float(cost.mean()),
                                        "edge_after_cost": float(abs(ret.mean()) - cost.mean()),
                                        "direction": s, "S": S, "S_gross": Sg, "passes": S > 0, "halves": halves}
    for p, name, sign, home in RANALDO:
        day, ret, cost = session_days(data[p], costs[p], SESSIONS[name])
        _, S, Sg, halves = score(ret, cost, day < split_ord, s=sign)
        res["ranaldo"].append({"pair": p, "session": name, "home": home, "predicted_sign": sign,
                               "mean_return": float(ret.mean()), "t": tstat(ret),
                               "sign_matches": bool(np.sign(ret.mean()) == sign),
                               "edge_after_cost_in_predicted_direction": float(sign * ret.mean() - cost.mean()),
                               "S": S, "S_gross": Sg, "passes": S > 0, "halves": halves})
    res["tests_counted"] = 24 * len(PAIRS) + len(SESSIONS) * len(PAIRS) + len(RANALDO)

    # Luck: 200 within-day shuffles of the hour labels.
    real_best, real_best_g, real_passes = best_hourly(data, costs, split_ord)
    sh_best, sh_best_g, sh_passes = [], [], []
    for k in range(SHUFFLES):
        rng = np.random.default_rng(SEED + k)
        rets, cs = {}, {}
        for p in PAIRS:
            rets[p], cs[p] = shuffle_within_days(data[p], costs[p], rng)
        b, bg, n = best_hourly(data, costs, split_ord, rets, cs)
        sh_best.append(b)
        sh_best_g.append(bg)
        sh_passes.append(n)
    sb, sbg, sp = np.array(sh_best), np.array(sh_best_g), np.array(sh_passes)
    res["luck"] = {
        "shuffles": SHUFFLES, "seed": SEED,
        "after_cost": {"real_best_S": real_best, "shuffled_median": float(np.median(sb)),
                       "shuffled_p95": float(np.percentile(sb, 95)),
                       "share_shuffles_at_least_as_good": float((sb >= real_best).mean()),
                       "real_passes": int(real_passes), "shuffled_passes_median": float(np.median(sp)),
                       "shuffled_passes_p95": float(np.percentile(sp, 95)),
                       "share_shuffles_with_as_many_passes": float((sp >= real_passes).mean())},
        "before_cost": {"real_best_S_gross": real_best_g, "shuffled_median": float(np.median(sbg)),
                        "shuffled_p95": float(np.percentile(sbg, 95)),
                        "share_shuffles_at_least_as_good": float((sbg >= real_best_g).mean())},
    }
    res["runtime_s"] = round(time.time() - t0, 1)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(res, indent=1, default=lambda x: x.item() if hasattr(x, "item") else str(x)) + "\n")
    print(f"wrote {OUT.relative_to(ROOT)} ({res['runtime_s']}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
