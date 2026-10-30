"""Round 4 track A: the machine-learning day strategy, walk-forward with retraining.

Pre-holdout data only. Stages (each resumes; the long ones stop before the time
budget with exit code 2, run again to continue):

  python scripts/research_ml.py table     # feature rows at every 08:00 UTC close, all pairs
  python scripts/research_ml.py fit       # per walk-forward round: inner 18+6 month selection runs,
                                          #   full 24-month refit, test-window runs (all 24 variants)
  python scripts/research_ml.py oos       # picks per round (inner score only), stitched OOS run
  python scripts/research_ml.py luck      # 500 random runs on the candidate's own signal days
  python scripts/research_ml.py summary   # pass/fail, what the picked models learned, log rows

Selection rule (owner, 30 Oct 2026): in each round every variant is trained on
the first 18 months of the 24-month training window and judged on the last 6
through the real engine (net / max drawdown, as Phase 4). The winner is retrained
on all 24 months and traded on the next 6 test months. Test-window runs of the
other variants exist only for the "nearby settings work" check; they are never
used to pick.

Outputs: research/phase4/a1_ml_day/ (committed: table, picks, grid results, the
5 picked models, luck, summary, explain), reports/backtests/phase4_a1_ml_day_oos/,
state/research/a1_ml_day/ (every fitted model and run, not committed).
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
from research_family import KEEP, STATE as _STATE, _jdump, _jload, _pool_run, _read_trades  # noqa: E402

from fxbot.backtest import research as R  # noqa: E402
from fxbot.backtest.candles import aggregate  # noqa: E402
from fxbot.backtest.metrics import summarise  # noqa: E402
from fxbot.backtest.report import write_run  # noqa: E402
from fxbot.backtest.walkforward import _add_months  # noqa: E402
from fxbot.strategies import ml_day as M  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
NAME = R.ML_NAME
OUT = ROOT / "research" / "phase4" / NAME
STATE = _STATE / NAME
GRID = R.ML_GRID
INNER_MONTHS = 18
CONFIGS = sorted({(g["model"], g["feats"], g["pool"]) for g in GRID})      # 8 model fits per window


def _cfg_of(params: dict) -> int:
    return CONFIGS.index((params["model"], params["feats"], params["pool"]))


def _model_path(cfg: int, k: int, which: str) -> Path:
    return STATE / "models" / f"c{cfg}_w{k}_{which}.pkl"


def _inner_split(w) -> tuple[dt.date, dt.date]:
    """(last day of the inner training part, first day of the inner validation part)."""
    inner_end = _add_months(w.train_start, INNER_MONTHS) - dt.timedelta(days=1)
    return inner_end, inner_end + dt.timedelta(days=1)


def _table() -> M.Table:
    return M.Table.load(OUT / "table.npz")


# ----------------------------------------------------------------------------- stages
def stage_table():
    data = R.market_data("1h", R.DATA_START, R.DATA_END)
    bars = {s: aggregate(m1, "1h") for s, (m1, _) in data.items()}
    t = M.build_table(bars)
    assert int(t.epoch.max()) < R.epoch_of(R.DATA_END + dt.timedelta(days=1)), "holdout data in the table"
    t.save(OUT / "table.npz")
    per = {s: int((t.symbol == s).sum()) for s in M.SYMBOLS}
    print(f"table: {len(t.epoch)} rows {per}, {int(np.isnan(t.y).sum())} without a 20:00 label, "
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
    """One engine run of variant v in round k: 'inner' (inner-validation months, inner model) or
    'test' (the round's test window, full model)."""
    v, k, which = job
    w = R.windows()[k]
    inner_end, inner_start = _inner_split(w)
    params = dict(GRID[v])
    cfg = _cfg_of(params)
    if which == "inner":
        start, end = inner_start, w.train_end
    else:
        start, end = w.valid_start, w.valid_end
    params["model_file"] = str(_model_path(cfg, k, "inner" if which == "inner" else "full"))
    s = R.Scheduled(M.MLDay, [(R.epoch_of(start), params)])
    eng = R.run_engine(s, start - dt.timedelta(days=M.MLDay.warmup_days), end)
    trades = [{kk: t[kk] for kk in KEEP} for t in eng.state.trades]
    sc = R.window_score(trades, R.epoch_of(start), R.epoch_of(end + dt.timedelta(days=1)))
    _jdump(STATE / "runs" / f"v{v:02d}_w{k}_{which}.json.gz",
           {"variant": v, "round": k, "which": which, "params": GRID[v], "span": [str(start), str(end)],
            "trades": trades, "kill_events": eng.state.kill_events, "score": sc})
    return v, k, which


def stage_fit(budget_s, t0):
    ws = R.windows()
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
        R.market_data("1h", R.DATA_START, R.DATA_END)          # load once before forking
        done, left = _pool_run(_run_task, runs, budget_s, t0)
        print(f"fit: {done} engine runs done now, {left} left")
        return left == 0
    print("fit: nothing left to do")
    return True


def _runs(which: str) -> dict[int, list[dict]]:
    """{variant: [run of round 0, ..., round 4]}."""
    ws = R.windows()
    return {v: [_jload(STATE / "runs" / f"v{v:02d}_w{k}_{which}.json.gz") for k in range(len(ws))]
            for v in range(len(GRID))}


def picks_from_inner(inner: dict[int, list[dict]]) -> list[dict]:
    """Per round, the variant with the best inner-validation score (ties: lowest index)."""
    out = []
    for k, w in enumerate(R.windows()):
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
        schedule.append((R.epoch_of(p["window"].valid_start),
                         {**GRID[p["variant"]], "model_file": str(dst.relative_to(ROOT))}))
    rows = []
    for v, g in enumerate(GRID):
        row = {"variant": v, **g}
        for k in range(len(R.windows())):
            si, st = inner[v][k]["score"], test[v][k]["score"]
            row[f"inner{k + 1}_trades"], row[f"inner{k + 1}_net_pct"] = si["trades"], round(si["net"] * 100, 2)
            row[f"inner{k + 1}_score"] = round(si["score"], 3) if np.isfinite(si["score"]) else None
            row[f"test{k + 1}_trades"], row[f"test{k + 1}_net_usd"] = st["trades"], \
                round(sum(t["profit"] for t in test[v][k]["trades"]), 2)
        rows.append(row)
    _jdump(OUT / "grid.json", rows)
    _jdump(OUT / "picks.json", [{"round": k + 1, "train": f"{p['window'].train_start}..{p['window'].train_end}",
                                 "inner_validation": f"{_inner_split(p['window'])[1]}..{p['window'].train_end}",
                                 "test": f"{p['window'].valid_start}..{p['window'].valid_end}",
                                 "variant": p["variant"], "params": GRID[p["variant"]],
                                 "inner_score": round(p["train"]["score"], 3) if np.isfinite(p["train"]["score"]) else None,
                                 "inner_trades": p["train"]["trades"], "model_file": schedule[k][1]["model_file"]}
                                for k, p in enumerate(picks)])
    sched_abs = [(t, {**p, "model_file": str(ROOT / p["model_file"])}) for t, p in schedule]
    meas = R.Scheduled(M.MLDay, sched_abs)
    e_m = R.run_oos(meas)
    e_s = R.run_oos(R.Scheduled(M.MLDay, sched_abs), stress=1.5)
    v0, v1 = R.oos_span()
    info = {"strategy": "fxbot.strategies.ml_day:MLDay (walk-forward schedule, model retrained per round)",
            "timeframe": "1h", "label": "Round 4 track A, stitched out-of-sample",
            "params": {"schedule": [(dt.datetime.fromtimestamp(t, dt.timezone.utc).date().isoformat(), p)
                                    for t, p in schedule]},
            "symbols": list(R.SYMBOLS), "start": v0.isoformat(), "end": v1.isoformat(),
            "include_holdout": False, "starting_balance": 100.0, "kill_switch_mode": "observe"}
    rep = write_run(f"phase4_{NAME}_oos", info, e_m.state, e_s.state)
    _jdump(OUT / "oos_signals.json", {"schedule": schedule, "signals": R.entry_signals(e_m.state)})
    print(f"{NAME}: picks {[p['variant'] for p in picks]}, OOS {len(e_m.state.trades)} trades, net "
          f"{round(sum(t['profit'] for t in e_m.state.trades), 2)} USD -> {rep.relative_to(ROOT)}")
    return True


def _luck_task(job):
    schedule, signals, seed = job
    sched = [(t, {**p, "model_file": str(ROOT / p["model_file"])}) for t, p in schedule]
    s = R.SignalDays(M.MLDay, sched, [tuple(x) for x in signals], seed)
    eng = R.run_oos(s)
    tr = eng.state.trades
    out = {"seed": seed, "trades": len(tr), "net_profit": round(sum(t["profit"] for t in tr), 2),
           "kill_events": len(eng.state.kill_events)}
    _jdump(STATE / "luck" / f"s{seed:03d}.json", out)
    return out


def stage_luck(budget_s, t0, runs):
    cfg = _jload(OUT / "oos_signals.json")
    jobs = [(cfg["schedule"], cfg["signals"], seed) for seed in range(runs)
            if not (STATE / "luck" / f"s{seed:03d}.json").exists()]
    if jobs:
        v0, v1 = R.oos_span()
        R.market_data("1h", v0 - dt.timedelta(days=M.MLDay.warmup_days), v1)
        done, left = _pool_run(_luck_task, jobs, budget_s, t0)
        print(f"{NAME}: luck runs {done} done now, {left} left")
        if left:
            return False
    res = sorted((_jload(STATE / "luck" / f"s{s:03d}.json") for s in range(runs)), key=lambda r: r["seed"])
    _jdump(OUT / "luck.json", res)
    return True


def explain(picks: list[dict]) -> list[dict]:
    """What each round's picked model learned: for logistic regression the standardised
    coefficients (sign = direction); for gradient boosting the permutation importance on its
    own training rows plus the sign of the link between the feature and the prediction."""
    from sklearn.inspection import permutation_importance
    table = _table()
    out = []
    for k, p in enumerate(picks):
        m = M.load_frozen(str(ROOT / p["model_file"]))
        g = GRID[p["variant"]]
        mask = M.training_rows(table, dt.date.fromisoformat(m.train_start), dt.date.fromisoformat(m.train_end), m.feats)
        idx = [table.columns.index(c) for c in m.columns]
        feats = []
        for key, pipe in m.models.items():
            sel = mask if key == "all" else mask & (table.symbol == key)
            X, y = table.X[sel][:, idx], table.y[sel]
            prob = pipe.predict_proba(X)[:, 1]
            if m.kind == "lr":
                coef = pipe.named_steps["clf"].coef_[0]
                imp = {c: float(w) for c, w in zip(m.columns, coef)}
                direction = {c: float(np.sign(w)) for c, w in zip(m.columns, coef)}
            else:
                pi = permutation_importance(pipe, X, y, scoring="neg_log_loss", n_repeats=5, random_state=M.SEED)
                imp = {c: float(v) for c, v in zip(m.columns, pi.importances_mean)}
                direction = {}
                for j, c in enumerate(m.columns):
                    x = X[:, j]
                    direction[c] = float(np.sign(np.corrcoef(x, prob)[0, 1])) if x.std() > 0 else 0.0
            acc = float(((prob > 0.5) == (y > 0.5)).mean())
            ranked = sorted(imp, key=lambda c: -abs(imp[c]))
            feats.append({"model_for": key, "rows": int(sel.sum()), "train_accuracy": round(acc, 3),
                          "prob_spread_sd": round(float(prob.std()), 4),
                          "share_beyond_margin": round(float((np.abs(prob - 0.5) >= g["margin"]).mean()), 3),
                          "importance": {c: round(imp[c], 4) for c in ranked},
                          "direction": {c: direction[c] for c in ranked},
                          "top": [{"feature": c, "plain": M.PLAIN.get(c, c), "weight": round(imp[c], 4),
                                   "pushes": "up" if direction[c] > 0 else ("down" if direction[c] < 0 else "none")}
                                  for c in ranked[:6]]})
        out.append({"round": k + 1, "variant": p["variant"], "params": g, "trained_on": f"{m.train_start}..{m.train_end}",
                    "training_rows": m.rows, "models": feats})
    return out


def stage_summary():
    met = json.loads((ROOT / "reports" / "backtests" / f"phase4_{NAME}_oos" / "metrics.json").read_text())
    trades = _read_trades(ROOT / "reports" / "backtests" / f"phase4_{NAME}_oos" / "trades.csv")
    luck = _jload(OUT / "luck.json") if (OUT / "luck.json").exists() else []
    picks_json = _jload(OUT / "picks.json")
    m, s = met["measured"], met["stress_1_5x"]
    per_pair = {sym: round(sum(t["profit"] for t in trades if t["symbol"] == sym), 2) for sym in R.SYMBOLS}
    pct, need_runs = (99, 500)
    lk = R.luck_result([r["net_profit"] for r in luck], m["net_profit"], pct, need_runs)
    test = _runs("test")
    gt = {v: [t for k in range(len(R.windows())) for t in test[v][k]["trades"]] for v in test}
    picks = [{"window": R.windows()[p["round"] - 1], "variant": p["variant"]} for p in picks_json]
    rob = R.robustness([{**t, "entry_epoch": int(t["entry_epoch"])} for t in trades], gt, picks, GRID)
    checks = {
        "profitable_pairs_2_of_3": sum(v > 0 for v in per_pair.values()) >= 2,
        "net_profit_positive": m["net_profit"] > 0,
        "oos_trades_200_plus": m["trades"] >= 200,
        "params_5_or_fewer": len(GRID[0]) <= 5,
        "min_target_3x_commission": bool(m["min_target_met"]),
        "no_kill_switch": not met["kill_switch"],
        "luck_check_beats_p95": lk["passed"],
        **rob["checks"],
    }
    ex = explain(picks_json)
    _jdump(OUT / "explain.json", ex)
    res = {"sub_grid": NAME, "variants": len(GRID), "oos": m, "stress_1_5x": s,
           "mt5_micro": met["mt5_micro_comparison_only"], "per_pair_net": per_pair,
           "kill_events": len(met.get("kill_events", [])), "kill_events_stress": len(met.get("kill_events_stress", [])),
           "robustness": rob["detail"], "round": R.ML_ROUND, "variants_running_total": R.variants_through_round(R.ML_ROUND),
           "luck": {**{k: lk[k] for k in ("runs", "percentile", "p50", "p95", "share_beaten")}, "mode": "signals",
                    "random_trades_mean": (round(sum(r["trades"] for r in luck) / len(luck), 1) if luck else None)},
           "checks": checks, "candidate": all(checks.values()), "picks": picks_json}
    _jdump(OUT / "summary.json", res)
    print(json.dumps({k: res[k] for k in ("sub_grid", "variants", "per_pair_net", "kill_events", "luck", "checks",
                                          "candidate")}, default=str))
    print("  OOS:", {k: m[k] for k in ("trades", "net_profit", "max_drawdown_pct", "win_rate_pct", "avg_win",
                                       "avg_loss", "profit_factor", "avg_commission")},
          "\n  1.5x:", {k: s[k] for k in ("trades", "net_profit", "max_drawdown_pct", "profit_factor")},
          "\n  MT5:", {k: met["mt5_micro_comparison_only"][k] for k in ("net_profit", "profit_factor")},
          "\n  robustness:", rob["detail"])
    for e in ex:
        print(f"  round {e['round']}: variant {e['variant']} {e['params']} rows {e['training_rows']}")
        for mm in e["models"]:
            print(f"    {mm['model_for']}: train acc {mm['train_accuracy']}, prob sd {mm['prob_spread_sd']}, "
                  f"beyond margin {mm['share_beyond_margin']}; top: " +
                  "; ".join(f"{t['feature']} ({t['pushes']}, {t['weight']})" for t in mm["top"]))
    write_log(res)
    return True


def write_log(summ: dict) -> None:
    log = ROOT / "research" / "log.md"
    text = log.read_text()
    today = dt.date.today().isoformat()
    rows = _jload(OUT / "grid.json")
    picked = {}
    for p in summ["picks"]:
        picked.setdefault(p["variant"], []).append(str(p["round"]))
    n = len(R.windows())
    lines = [f"<!-- phase4:{NAME} start -->", "",
             f"### {NAME} (1h, track A, round 4): {len(GRID)} variants", "",
             "Each round: the variant is fitted on the first 18 months of the training window and scored on "
             "the last 6 (inner validation, real engine, measured costs); the best inner score is picked, "
             "refitted on all 24 months and traded on the test window. Test-window columns are shown for "
             "every variant for the record (used only for the nearby-settings check, never to pick).", "",
             "| Date | Variant | Params | Inner-validation net % by round | Test-window net USD by round "
             "| Test trades | Picked in rounds |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        prm = ", ".join(f"{k}={r[k]}" for k in GRID[r["variant"]])
        inner = " / ".join(f"{r[f'inner{k + 1}_net_pct']}" for k in range(n))
        test = " / ".join(f"{r[f'test{k + 1}_net_usd']}" for k in range(n))
        ntr = sum(r[f"test{k + 1}_trades"] for k in range(n))
        lines.append(f"| {today} | {NAME} v{r['variant']:02d} | {prm} | {inner} | {test} | {ntr} "
                     f"| {', '.join(picked.get(r['variant'], [])) or '-'} |")
    m = summ["oos"]
    lines += ["", f"Stitched OOS (2023-10-27 to 2026-04-26): {m['trades']} trades, net {m['net_profit']} USD, "
                  f"max drawdown {m['max_drawdown_pct']}%, per pair {summ['per_pair_net']}, kill events "
                  f"{summ['kill_events']}, luck check (p{summ['luck']['percentile']} of {summ['luck']['runs']} "
                  f"random runs on the candidate's own signal days = {summ['luck']['p95']}): "
                  f"{summ['checks']['luck_check_beats_p95']}. Failed checks: "
                  f"{[k for k, v in summ['checks'].items() if not v] or 'none'}. "
                  f"**Candidate: {summ['candidate']}**. Report: `reports/backtests/phase4_{NAME}_oos/`, "
                  f"`research/phase4/{NAME}/`.", "", f"<!-- phase4:{NAME} end -->"]
    block = "\n".join(lines)
    start, end = f"<!-- phase4:{NAME} start -->", f"<!-- phase4:{NAME} end -->"
    if start in text:
        i, j = text.index(start), text.index(end) + len(end)
        text = text[:i] + block + text[j:]
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    log.write_text(text)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("table", "fit", "oos", "luck", "summary"))
    p.add_argument("--max-minutes", type=float, default=8.5)
    p.add_argument("--runs", type=int, default=500)
    a = p.parse_args()
    t0 = time.time()
    budget = a.max_minutes * 60
    ok = {"table": stage_table, "fit": lambda: stage_fit(budget, t0), "oos": stage_oos,
          "luck": lambda: stage_luck(budget, t0, a.runs), "summary": stage_summary}[a.stage]()
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
