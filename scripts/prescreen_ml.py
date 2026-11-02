"""Incubator pre-screen of the nearest-neighbour path idea (a2_knn_path), walk-forward with
refitting per round, on data before the untouched period (fxbot.backtest.prescreen).

  python scripts/prescreen_ml.py table    # feature rows at every 08:00 UTC close (to 2026-10-30)
  python scripts/prescreen_ml.py fit      # per round: inner 18+6 month selection runs, full refit, test runs
  python scripts/prescreen_ml.py oos      # picks per round (inner score only), stitched OOS run
  python scripts/prescreen_ml.py luck     # 200 coin-toss runs on the candidate's own signal days
  python scripts/prescreen_ml.py summary  # checks, log rows
  python scripts/prescreen_ml.py final    # the model to register: fitted on the last 24 months

Selection rule as Round 4 (owner, 30 Oct 2026): in each round every variant is fitted on the
first 18 months of the 24-month training window and judged on the last 6 through the real
engine (net / max drawdown); the winner is refitted on all 24 months and traded on the next
6 test months. Outputs: research/incubator_prescreen/knn_path/ (committed) and
state/prescreen/knn_path/ (not committed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401
from prescreen import KEEP, OUT as _OUT, STATE as _STATE, _jdump, _jload, _pool_run, write_log  # noqa: E402

from fxbot.backtest import prescreen as P  # noqa: E402
from fxbot.backtest import research as R  # noqa: E402
from fxbot.backtest.audit import gross_of  # noqa: E402
from fxbot.backtest.candles import aggregate  # noqa: E402
from fxbot.backtest.walkforward import _add_months  # noqa: E402
from fxbot.strategies import ml_day as M  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
IDEA = "knn_path"
NAME = M.KnnPath.name
OUT = _OUT / IDEA
STATE = _STATE / IDEA
GRID = P._grid(model=list(M.KNN_KINDS), feats=("path", "pathpeers"), pool=("pair",), margin=(0.05, 0.1))
INNER_MONTHS = 18
CONFIGS = sorted({(g["model"], g["feats"], g["pool"]) for g in GRID})
FINAL_TRAIN_MONTHS = 24


def _cfg_of(params: dict) -> int:
    return CONFIGS.index((params["model"], params["feats"], params["pool"]))


def _model_path(cfg: int, k: int, which: str) -> Path:
    return STATE / "models" / f"c{cfg}_w{k}_{which}.pkl"


def _inner_split(w) -> tuple[dt.date, dt.date]:
    inner_end = _add_months(w.train_start, INNER_MONTHS) - dt.timedelta(days=1)
    return inner_end, inner_end + dt.timedelta(days=1)


def _table() -> M.Table:
    return M.Table.load(OUT / "table.npz")


# ----------------------------------------------------------------------------- stages
def stage_table():
    data = P.market_data("1h", P.DATA_START, P.DATA_END)
    bars = {s: aggregate(m1, "1h") for s, (m1, _) in data.items()}
    t = M.build_table(bars)
    assert int(t.epoch.max()) < P.epoch_of(P.DATA_END + dt.timedelta(days=1)), "untouched data in the table"
    t.save(OUT / "table.npz")
    per = {s: int((t.symbol == s).sum()) for s in M.SYMBOLS}
    nan_path = int(np.isnan(t.X[:, [t.columns.index(c) for c in M.PATH]]).any(axis=1).sum())
    print(f"table: {len(t.epoch)} rows {per}, {int(np.isnan(t.y).sum())} without a 20:00 label, "
          f"{nan_path} without a full 24-hour path, "
          f"{dt.datetime.fromtimestamp(int(t.epoch.min()), dt.timezone.utc).date()} .. "
          f"{dt.datetime.fromtimestamp(int(t.epoch.max()), dt.timezone.utc).date()}")
    return True


def _fit_task(job):
    cfg, k, which, t0, t1 = job
    kind, feats, pool = CONFIGS[cfg]
    m = M.fit_frozen(_table(), dt.date.fromisoformat(t0), dt.date.fromisoformat(t1), kind, feats, pool)
    m.save(_model_path(cfg, k, which))
    return cfg, k, which


def _run_task(job):
    v, k, which = job
    w = P.windows()[k]
    inner_end, inner_start = _inner_split(w)
    params = dict(GRID[v])
    cfg = _cfg_of(params)
    if which == "inner":
        start, end = inner_start, w.train_end
    else:
        start, end = w.valid_start, w.valid_end
    params["model_file"] = str(_model_path(cfg, k, "inner" if which == "inner" else "full"))
    s = R.Scheduled(M.KnnPath, [(P.epoch_of(start), params)])
    eng = P.run_engine(s, start - dt.timedelta(days=M.KnnPath.warmup_days), end)
    trades = [{kk: t[kk] for kk in KEEP} for t in eng.state.trades]
    sc = R.window_score(trades, P.epoch_of(start), P.epoch_of(end + dt.timedelta(days=1)))
    _jdump(STATE / "runs" / f"v{v:02d}_w{k}_{which}.json.gz",
           {"variant": v, "round": k, "which": which, "params": GRID[v], "span": [str(start), str(end)],
            "trades": trades, "kill_events": eng.state.kill_events, "score": sc})
    return v, k, which


def stage_fit(budget_s, t0):
    ws = P.windows()
    fits = []
    for k, w in enumerate(ws):
        inner_end, _ = _inner_split(w)
        for cfg in range(len(CONFIGS)):
            for which, end in (("inner", inner_end), ("full", w.train_end)):
                if not _model_path(cfg, k, which).exists():
                    fits.append((cfg, k, which, str(w.train_start), str(end)))
    if fits:
        done, left = _pool_run(_fit_task, fits, budget_s, t0)
        print(f"fit: {done} models fitted, {left} left")
        if left:
            return False
    runs = [(v, k, which) for k in range(len(ws)) for v in range(len(GRID)) for which in ("inner", "test")
            if not (STATE / "runs" / f"v{v:02d}_w{k}_{which}.json.gz").exists()]
    if runs:
        P.market_data("1h", P.DATA_START, P.DATA_END)
        done, left = _pool_run(_run_task, runs, budget_s, t0)
        print(f"fit: {done} engine runs done now, {left} left")
        return left == 0
    print("fit: nothing left to do")
    return True


def _runs(which: str) -> dict[int, list[dict]]:
    ws = P.windows()
    return {v: [_jload(STATE / "runs" / f"v{v:02d}_w{k}_{which}.json.gz") for k in range(len(ws))]
            for v in range(len(GRID))}


def picks_from_inner(inner: dict[int, list[dict]]) -> list[dict]:
    out = []
    for k, w in enumerate(P.windows()):
        scores = {v: inner[v][k]["score"]["score"] for v in inner}
        best = max(sorted(scores), key=lambda v: scores[v])
        out.append({"window": w, "variant": best, "train": inner[best][k]["score"]})
    return out


def stage_oos():
    inner, test = _runs("inner"), _runs("test")
    picks = picks_from_inner(inner)
    (OUT / "models").mkdir(parents=True, exist_ok=True)
    schedule = []
    for k, p in enumerate(picks):
        src = _model_path(_cfg_of(GRID[p["variant"]]), k, "full")
        dst = OUT / "models" / f"round{k + 1}_full.pkl"
        shutil.copyfile(src, dst)
        schedule.append((P.epoch_of(p["window"].valid_start),
                         {**GRID[p["variant"]], "model_file": str(dst.relative_to(ROOT))}))
    rows = []
    n = len(P.windows())
    for v, g in enumerate(GRID):
        row = {"variant": v, **g, "trades": sum(len(test[v][k]["trades"]) for k in range(n)),
               "net_profit": round(sum(t["profit"] for k in range(n) for t in test[v][k]["trades"]), 2),
               "kill_events": sum(len(test[v][k]["kill_events"]) for k in range(n))}
        for k in range(n):
            si = inner[v][k]["score"]
            row[f"train{k + 1}_score"] = round(si["score"], 3) if np.isfinite(si["score"]) else None
        rows.append(row)
    _jdump(OUT / "grid.json", rows)
    _jdump(OUT / "picks.json", [{"round": k + 1, "train": f"{p['window'].train_start}..{p['window'].train_end}",
                                 "inner_validation": f"{_inner_split(p['window'])[1]}..{p['window'].train_end}",
                                 "test": f"{p['window'].valid_start}..{p['window'].valid_end}",
                                 "variant": p["variant"], "params": GRID[p["variant"]],
                                 "train_score": round(p["train"]["score"], 3) if np.isfinite(p["train"]["score"]) else None,
                                 "train_trades": p["train"]["trades"], "model_file": schedule[k][1]["model_file"]}
                                for k, p in enumerate(picks)])
    sched_abs = [(t, {**p, "model_file": str(ROOT / p["model_file"])}) for t, p in schedule]
    e_m = P.run_oos(R.Scheduled(M.KnnPath, sched_abs))
    e_s = P.run_oos(R.Scheduled(M.KnnPath, sched_abs), stress=1.5)
    _jdump(OUT / "oos_trades.json.gz", {"schedule": schedule,
                                        "measured": [{k: t[k] for k in KEEP} for t in e_m.state.trades],
                                        "stress_1_5x": [{k: t[k] for k in KEEP} for t in e_s.state.trades],
                                        "kill_events": len(e_m.state.kill_events),
                                        "blocked": dict(e_m.state.blocked), "refused": dict(e_m.state.refused)})
    _jdump(OUT / "oos_signals.json", {"schedule": schedule, "signals": R.entry_signals(e_m.state)})
    print(f"{IDEA}: picks {[p['variant'] for p in picks]}, OOS {len(e_m.state.trades)} trades, net "
          f"{round(sum(t['profit'] for t in e_m.state.trades), 2)} USD")
    return True


def _luck_task(job):
    schedule, signals, seed = job
    sched = [(t, {**p, "model_file": str(ROOT / p["model_file"])}) for t, p in schedule]
    s = R.SignalDays(M.KnnPath, sched, [tuple(x) for x in signals], seed)
    eng = P.run_oos(s)
    tr = eng.state.trades
    out = {"seed": seed, "trades": len(tr), "net_profit": round(sum(t["profit"] for t in tr), 2),
           "gross": round(sum(gross_of(t) for t in tr), 2), "kill_events": len(eng.state.kill_events)}
    _jdump(STATE / "luck" / f"s{seed:03d}.json", out)
    return out


def stage_luck(budget_s, t0, runs):
    cfg = _jload(OUT / "oos_signals.json")
    jobs = [(cfg["schedule"], cfg["signals"], seed) for seed in range(runs)
            if not (STATE / "luck" / f"s{seed:03d}.json").exists()]
    if jobs:
        v0, v1 = P.oos_span()
        P.market_data("1h", v0 - dt.timedelta(days=M.KnnPath.warmup_days), v1)
        done, left = _pool_run(_luck_task, jobs, budget_s, t0)
        print(f"{IDEA}: luck runs {done} done now, {left} left")
        if left:
            return False
    res = sorted((_jload(STATE / "luck" / f"s{s:03d}.json") for s in range(runs)), key=lambda r: r["seed"])
    _jdump(OUT / "luck.json", res)
    return True


def stage_summary():
    oos = _jload(OUT / "oos_trades.json.gz")
    luck = _jload(OUT / "luck.json") if (OUT / "luck.json").exists() else []
    trades = oos["measured"]
    net = round(sum(t["profit"] for t in trades), 2)
    gross = round(sum(gross_of(t) for t in trades), 2)
    lk = P.luck_summary([r["net_profit"] for r in luck], [r["gross"] for r in luck], net, gross)
    res = {"idea": IDEA, "strategy": NAME, "timeframe": "1h",
           **P.summary(trades, oos["stress_1_5x"], oos["kill_events"], lk, len(GRID), len(GRID[0])),
           "picks": _jload(OUT / "picks.json"), "blocked": oos["blocked"], "refused": oos["refused"]}
    _jdump(OUT / "summary.json", res)
    print(json.dumps({k: res[k] for k in ("idea", "trades", "trades_per_day", "net_measured", "net_1_5x", "gross",
                                          "gross_pips_per_trade", "win_rate_pct", "profit_factor", "kill_events",
                                          "move_vs_cost", "per_pair", "per_window_gross", "checks",
                                          "prescreen_pass", "all_checks")}, default=str))
    print("  luck:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in lk.items()})
    P.IDEAS[IDEA] = P.Idea(NAME, GRID)
    write_log(IDEA)
    return True


def stage_final(params: dict):
    """The model to register: the given settings fitted on the last FINAL_TRAIN_MONTHS months of
    pre-untouched data (to 2026-10-30), saved under research/incubator_prescreen/knn_path/models/."""
    end = P.DATA_END
    start = _add_months(end + dt.timedelta(days=1), -FINAL_TRAIN_MONTHS)
    m = M.fit_frozen(_table(), start, end, params["model"], params["feats"], params["pool"])
    path = OUT / "models" / "final_full.pkl"
    m.save(path)
    print(f"final model: {params} fitted on {start}..{end}, {m.rows} rows, {sorted(m.models)} -> {path.relative_to(ROOT)}")
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("table", "fit", "oos", "luck", "summary", "final"))
    p.add_argument("--max-minutes", type=float, default=8.5)
    p.add_argument("--runs", type=int, default=P.LUCK_RUNS)
    p.add_argument("--params", default="", help="final: JSON settings of the variant to register")
    a = p.parse_args()
    t0 = time.time()
    budget = a.max_minutes * 60
    ok = {"table": stage_table, "fit": lambda: stage_fit(budget, t0), "oos": stage_oos,
          "luck": lambda: stage_luck(budget, t0, a.runs), "summary": stage_summary,
          "final": lambda: stage_final(json.loads(a.params))}[a.stage]()
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
