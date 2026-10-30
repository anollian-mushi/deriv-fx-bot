"""Phase 4: test one strategy family (grid -> walk-forward -> out of sample -> luck check).

Pre-holdout data only. Each stage saves progress and stops before its time
budget (default 8.5 minutes, exit code 2); run the same command again to
continue. Stages, in order:

  python scripts/research_family.py grid    --family f1   # every variant, full period
  python scripts/research_family.py oos     --family f1   # walk-forward picks, stitched OOS run
  python scripts/research_family.py luck    --family f1   # >= 200 random-entry runs
  python scripts/research_family.py summary --family f1   # pass/fail table

Outputs: research/phase4/<sub-grid>/ (committed), reports/backtests/phase4_<sub-grid>_oos/,
raw grid trades in state/research/ (not committed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401


from fxbot.backtest import research as R
from fxbot.backtest.engine import EngineState
from fxbot.backtest.metrics import summarise
from fxbot.backtest.report import write_run
from fxbot.strategies.families import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "research"
OUT = ROOT / "research" / "phase4"
KEEP = ("symbol", "direction", "entry_epoch", "exit_epoch", "profit", "balance_after", "commission",
        "reason", "stake")
LUCK_RUNS = 200


def _jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.suffix == ".gz":
        tmp.write_bytes(gzip.compress(json.dumps(obj).encode()))
    else:
        tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(path)


def _jload(path: Path):
    if path.suffix == ".gz":
        return json.loads(gzip.decompress(path.read_bytes()))
    return json.loads(path.read_text())


# ----------------------------------------------------------------------------- workers
def _grid_task(job):
    name, i, params = job
    eng = R.run_engine(REGISTRY[name](**params))
    trades = [{k: t[k] for k in KEEP} for t in eng.state.trades]
    _jdump(STATE / name / "grid" / f"v{i:02d}.json.gz",
           {"params": params, "trades": trades, "kill_events": eng.state.kill_events})
    return name, i


def _luck_task(job):
    name, schedule, rates, seed, mode = job
    cls = REGISTRY[name]
    if mode == "signals":          # Round 4: the candidate's own signal days and pairs, coin-toss direction
        s = R.SignalDays(cls, [(t, p) for t, p in schedule], rates, seed)
    else:
        s = R.RandomEntry(cls, [(t, p) for t, p in schedule], {tuple(k): v for k, v in rates}, seed)
    eng = R.run_oos(s)
    tr = eng.state.trades
    out = {"seed": seed, "trades": len(tr), "net_profit": round(sum(t["profit"] for t in tr), 2),
           "kill_events": len(eng.state.kill_events)}
    _jdump(STATE / name / "luck" / f"s{seed:03d}.json", out)
    return out


def _pool_run(fn, jobs, budget_s, t0):
    """Run jobs on 4 processes; stop handing out new ones when the budget is spent."""
    done = 0
    ctx = mp.get_context("fork")
    with ctx.Pool(4) as pool:
        pending = list(jobs)
        running = []
        while pending or running:
            while pending and len(running) < 4 and time.time() - t0 < budget_s:
                running.append(pool.apply_async(fn, (pending.pop(0),)))
            if not running:
                break
            for r in list(running):
                if r.ready():
                    r.get()
                    running.remove(r)
                    done += 1
            time.sleep(0.5)
    return done, len(pending)


# ----------------------------------------------------------------------------- stages
def stage_grid(family, budget_s, t0):
    jobs = [(name, i, p) for name, grid in R.FAMILIES[family] for i, p in enumerate(grid)
            if not (STATE / name / "grid" / f"v{i:02d}.json.gz").exists()]
    for tf in {REGISTRY[name].timeframe for name, _ in R.FAMILIES[family]}:
        R.market_data(tf, R.DATA_START, R.DATA_END)                     # load once before forking
    done, left = _pool_run(_grid_task, jobs, budget_s, t0)
    print(f"grid: {done} variants run, {left} left")
    return left == 0


def _grid_trades(name, n):
    return {i: _jload(STATE / name / "grid" / f"v{i:02d}.json.gz") for i in range(n)}


def stage_oos(family):
    v0, v1 = R.oos_span()
    for name, grid in R.FAMILIES[family]:
        raw = _grid_trades(name, len(grid))
        picks = R.pick_per_window({i: r["trades"] for i, r in raw.items()})
        rows = []
        for i, p in enumerate(grid):
            m = summarise(raw[i]["trades"], 100.0)
            row = {"variant": i, **p, "trades": m["trades"], "net_profit": m["net_profit"],
                   "max_dd_pct": m["max_drawdown_pct"], "profit_factor": m["profit_factor"],
                   "kill_events": len(raw[i]["kill_events"])}
            for k, w in enumerate(R.windows()):
                sc = R.window_score(raw[i]["trades"], R.epoch_of(w.train_start),
                                    R.epoch_of(w.train_end + dt.timedelta(days=1)))
                row[f"train{k + 1}_score"] = round(sc["score"], 3)
            rows.append(row)
        schedule = R.schedule_from(picks, grid)
        cls = REGISTRY[name]
        meas = R.Scheduled(cls, schedule)
        e_m = R.run_oos(meas)
        e_s = R.run_oos(R.Scheduled(cls, schedule), stress=1.5)
        info = {"strategy": f"fxbot.strategies.families:{cls.__name__} (walk-forward schedule)",
                "timeframe": cls.timeframe, "label": f"Phase 4 family {cls.family}, stitched out-of-sample",
                "params": meas.params, "symbols": list(R.SYMBOLS), "start": v0.isoformat(),
                "end": v1.isoformat(), "include_holdout": False, "starting_balance": 100.0,
                "kill_switch_mode": "observe"}
        rep = write_run(f"phase4_{name}_oos", info, e_m.state, e_s.state)
        out = OUT / name
        _jdump(out / "grid.json", rows)
        _jdump(out / "picks.json", [{"round": k + 1, "train": f"{p['window'].train_start}..{p['window'].train_end}",
                                     "test": f"{p['window'].valid_start}..{p['window'].valid_end}",
                                     "variant": p["variant"], "params": grid[p["variant"]],
                                     "train_score": round(p["train"]["score"], 3),
                                     "train_trades": p["train"]["trades"]} for k, p in enumerate(picks)])
        _jdump(out / "oos_rates.json", {"schedule": schedule, "rates_key": ["window", "symbol", "hour"],
                                        "rates": [[list(k), v] for k, v in R.entry_rates(meas).items()]})
        _jdump(out / "oos_signals.json", {"schedule": schedule, "signals": R.entry_signals(e_m.state)})
        print(f"{name}: OOS {len(e_m.state.trades)} trades, net "
              f"{round(sum(t['profit'] for t in e_m.state.trades), 2)} USD -> {rep.relative_to(ROOT)}")
    return True


def stage_luck(family, budget_s, t0, runs):
    for name, _ in R.FAMILIES[family]:
        mode = R.luck_mode(family)
        if mode == "signals":
            cfg = _jload(OUT / name / "oos_signals.json")
            draws = [tuple(x) for x in cfg["signals"]]
        else:
            cfg = _jload(OUT / name / "oos_rates.json")
            if any(len(k) != 3 for k, _ in cfg["rates"]):
                raise SystemExit(f"{name}: oos_rates.json has the old (symbol, hour) keys; "
                                 "run the oos stage again first (luck-check fix, audit 30 Oct 2026)")
            draws = cfg["rates"]
        jobs = [(name, cfg["schedule"], draws, seed, mode) for seed in range(runs)
                if not (STATE / name / "luck" / f"s{seed:03d}.json").exists()]
        if jobs:
            R.market_data(REGISTRY[name].timeframe, *_oos_load_span())
        done, left = _pool_run(_luck_task, jobs, budget_s, t0)
        print(f"{name}: luck runs {done} done now, {left} left")
        if left:
            return False
        res = sorted((_jload(STATE / name / "luck" / f"s{s:03d}.json") for s in range(runs)),
                     key=lambda r: r["seed"])
        _jdump(OUT / name / "luck.json", res)
    return True


def _oos_load_span():
    v0, v1 = R.oos_span()
    return v0 - dt.timedelta(days=R.WARMUP_DAYS), v1


def stage_summary(family):
    out = []
    for name, grid in R.FAMILIES[family]:
        d = OUT / name
        met = json.loads((ROOT / "reports" / "backtests" / f"phase4_{name}_oos" / "metrics.json").read_text())
        trades = _read_trades(ROOT / "reports" / "backtests" / f"phase4_{name}_oos" / "trades.csv")
        luck = _jload(d / "luck.json") if (d / "luck.json").exists() else []
        m, s = met["measured"], met["stress_1_5x"]
        per_pair = {sym: round(sum(t["profit"] for t in trades if t["symbol"] == sym), 2) for sym in R.SYMBOLS}
        pct, need_runs = R.luck_rule(family)
        lk = R.luck_result([r["net_profit"] for r in luck], m["net_profit"], pct, need_runs)
        raw = _grid_trades(name, len(grid))
        gt = {i: r["trades"] for i, r in raw.items()}
        rob = R.robustness([{**t, "entry_epoch": int(t["entry_epoch"])} for t in trades], gt,
                           R.pick_per_window(gt), grid)
        checks = {
            "profitable_pairs_2_of_3": sum(v > 0 for v in per_pair.values()) >= 2,
            "net_profit_positive": m["net_profit"] > 0,
            "oos_trades_200_plus": m["trades"] >= 200,
            "params_5_or_fewer": len(grid[0]) <= 5,
            "min_target_3x_commission": bool(m["min_target_met"]),
            "no_kill_switch": not met["kill_switch"],
            "luck_check_beats_p95": lk["passed"],
            **rob["checks"],
        }
        res = {"sub_grid": name, "variants": len(grid), "oos": m, "stress_1_5x": s,
               "mt5_micro": met["mt5_micro_comparison_only"], "per_pair_net": per_pair,
               "kill_events": len(met.get("kill_events", [])),
               "kill_events_stress": len(met.get("kill_events_stress", [])),
               "robustness": rob["detail"], "round": R.ROUND[family],
               "variants_running_total": R.variants_through_round(R.ROUND[family]),
               "luck": {k: lk[k] for k in ("runs", "percentile", "p50", "p95", "share_beaten"),
                        "mode": R.luck_mode(family),
                        "random_trades_mean": (round(sum(r["trades"] for r in luck) / len(luck), 1) if luck else None)},
               "checks": checks, "candidate": all(checks.values())}
        _jdump(d / "summary.json", res)
        out.append(res)
        print(json.dumps({k: res[k] for k in ("sub_grid", "variants", "per_pair_net", "kill_events", "luck",
                                              "checks", "candidate")}, default=str))
        print("  OOS:", {k: m[k] for k in ("trades", "net_profit", "max_drawdown_pct", "win_rate_pct",
                                           "avg_win", "avg_loss", "profit_factor", "avg_commission")},
              "\n  1.5x:", {k: s[k] for k in ("trades", "net_profit", "max_drawdown_pct", "profit_factor")},
              "\n  MT5:", {k: met["mt5_micro_comparison_only"][k] for k in ("net_profit", "profit_factor")})
    return True


def write_log(family) -> None:
    """Add / refresh this family's variant rows in research/log.md (between markers)."""
    log = ROOT / "research" / "log.md"
    text = log.read_text()
    today = dt.date.today().isoformat()
    for name, grid in R.FAMILIES[family]:
        d = OUT / name
        rows = _jload(d / "grid.json")
        picks = _jload(d / "picks.json")
        summ = _jload(d / "summary.json") if (d / "summary.json").exists() else None
        picked = {}
        for p in picks:
            picked.setdefault(p["variant"], []).append(str(p["round"]))
        tf = REGISTRY[name].timeframe
        lines = [f"<!-- phase4:{name} start -->", "",
                 f"### {name} ({tf}): {len(grid)} variants", "",
                 "Full-period result (2021-10-27 to 2026-04-27, measured cost) is for reference; "
                 "selection used only each round's training window.", "",
                 "| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events "
                 "| Picked in rounds |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            prm = ", ".join(f"{k}={r[k]}" for k in grid[r["variant"]])
            lines.append(f"| {today} | {name} v{r['variant']:02d} | {prm} | {r['trades']} | {r['net_profit']} "
                         f"| {r['kill_events']} | {', '.join(picked.get(r['variant'], [])) or '-'} |")
        if summ:
            m = summ["oos"]
            lines += ["", f"Stitched OOS (2023-10-27 to 2026-04-26): {m['trades']} trades, net "
                          f"{m['net_profit']} USD, max drawdown {m['max_drawdown_pct']}%, per pair "
                          f"{summ['per_pair_net']}, kill events {summ['kill_events']}, luck check "
                          f"(p{summ['luck'].get('percentile', 95)} of {summ['luck']['runs']} random runs = "
                          f"{summ['luck']['p95']}): {summ['checks']['luck_check_beats_p95']}. "
                          f"Failed checks: {[k for k, v in summ['checks'].items() if not v] or 'none'}. "
                          f"**Candidate: {summ['candidate']}**. "
                          f"Report: `reports/backtests/phase4_{name}_oos/`, `research/phase4/{name}/`."]
        lines += ["", f"<!-- phase4:{name} end -->"]
        block = "\n".join(lines)
        start, end = f"<!-- phase4:{name} start -->", f"<!-- phase4:{name} end -->"
        if start in text:
            i, j = text.index(start), text.index(end) + len(end)
            text = text[:i] + block + text[j:]
        else:
            text = text.rstrip("\n") + "\n\n" + block + "\n"
    log.write_text(text)


def _read_trades(path: Path):
    import csv
    if not path.exists():
        return []
    with path.open() as f:
        return [{**r, "profit": float(r["profit"])} for r in csv.DictReader(f)]


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("grid", "oos", "luck", "summary"))
    p.add_argument("--family", required=True, choices=sorted(R.FAMILIES))
    p.add_argument("--max-minutes", type=float, default=8.5)
    p.add_argument("--runs", type=int, default=LUCK_RUNS)
    a = p.parse_args()
    t0 = time.time()
    budget = a.max_minutes * 60
    if a.stage == "grid":
        ok = stage_grid(a.family, budget, t0)
    elif a.stage == "oos":
        ok = stage_oos(a.family)
    elif a.stage == "luck":
        ok = stage_luck(a.family, budget, t0, max(a.runs, R.luck_rule(a.family)[1]))
    else:
        ok = stage_summary(a.family)
        write_log(a.family)
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
