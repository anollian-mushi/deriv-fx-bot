"""Cost what-if for the Phase 4 families (research only: no new strategy, no holdout).

Keeps each family's already-chosen walk-forward settings and its recorded
out-of-sample trades, and re-prices them at other costs per trade
(fxbot.backtest.whatif). Stages:

  python scripts/cost_whatif.py scan      # every family: all checks from 0.5 to 5.0 pips + broker model
  python scripts/cost_whatif.py random    # 500 random-entry runs (corrected rates) where needed
  python scripts/cost_whatif.py luck      # luck check (p99 of 500) at the threshold and broker costs
  python scripts/cost_whatif.py zero      # reference: every check with no cost at all

Results: research/cost_whatif/*.json. Random-run trades: state/cost_whatif/ (not committed).
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import multiprocessing as mp
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from fxbot.backtest import fills
from fxbot.backtest import research as R
from fxbot.backtest import whatif as W
from fxbot.strategies.families import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "cost_whatif"
STATE = ROOT / "state" / "cost_whatif"
GRID_STATE = ROOT / "state" / "research"
LEVELS = [round(0.5 + 0.1 * k, 1) for k in range(46)]          # 0.5 .. 5.0 pips total per trade
RUNS, PCT = 500, 99
KEEP = ("symbol", "direction", "stake", "multiplier", "entry", "exit", "entry_epoch", "exit_epoch",
        "reason", "commission", "profit")


def sub_grids():
    return [(fam, name, grid) for fam, subs in R.FAMILIES.items() for name, grid in subs]


def _num(r):
    out = dict(r)
    for k in ("stake", "entry", "exit", "commission", "profit", "balance_after"):
        if k in out and out[k] != "":
            out[k] = float(out[k])
    for k in ("multiplier", "entry_epoch", "exit_epoch"):
        out[k] = int(out.get(k, 100))
    return out


def oos_trades(name):
    with (ROOT / "reports" / "backtests" / f"phase4_{name}_oos" / "trades.csv").open() as f:
        return [_num(r) for r in csv.DictReader(f)]


def grid_trades(name, n):
    """Grid runs with an entry price taken from the 1m open at entry (+0.5 pip slippage)."""
    out = {}
    for i in range(n):
        raw = json.loads(gzip.decompress((GRID_STATE / name / "grid" / f"v{i:02d}.json.gz").read_bytes()))
        trs = []
        for t in raw["trades"]:
            m1 = R._m1(t["symbol"])
            j = int(np.searchsorted(m1.epoch, t["entry_epoch"]))
            entry = fills.entry_price(t["symbol"], t["direction"], float(m1.open[j]))
            trs.append({**t, "entry": entry, "exit": entry, "multiplier": 100})
        out[i] = trs
    return out


def evaluate(fam, name, grid, oos, grid_tr, picks, fn) -> dict:
    """Every CLAUDE.md rule and the four 'not fake' checks, at one cost model (luck excluded)."""
    rep = W.reprice(oos, fn)
    tr = rep["trades"]
    pairs = {s: round(sum(t["profit"] for t in tr if t["symbol"] == s), 2) for s in R.SYMBOLS}
    wins = [t["profit"] for t in tr if t["profit"] > 0]
    cost = [max(t["cost_usd"], 0.0) for t in tr]
    checks = {
        "profitable_pairs_2_of_3": sum(v > 0 for v in pairs.values()) >= 2,
        "net_profit_positive": rep["net"] > 0,
        "oos_trades_200_plus": len(tr) >= 200,
        "params_5_or_fewer": len(grid[0]) <= 5,
        "min_target_3x_cost": bool(wins) and np.mean(wins) >= 3 * np.mean(cost),
        "no_kill_switch": not rep["kill_events"],
    }
    res = {"net": rep["net"], "trades": len(tr), "per_pair": pairs, "kill_events": len(rep["kill_events"]),
           "avg_cost_usd": round(float(np.mean(cost)), 4) if cost else 0.0,
           "avg_slippage_pips": round(float(np.mean([W.slippage_pips(t) for t in oos])), 3)}
    if all(checks.values()):           # robustness only where everything else passes (it is slow)
        gt = {i: W.reprice(t, fn)["trades"] for i, t in grid_tr.items()}
        rob = R.robustness(tr, gt, picks, grid)
        checks.update(rob["checks"])
        res["robustness"] = rob["detail"]
    else:
        checks.update({k: None for k in ("not_one_pair", "not_one_period", "not_few_big_trades",
                                         "nearby_settings_work")})
    res["checks"] = {k: (None if v is None else bool(v)) for k, v in checks.items()}
    res["passes_without_luck"] = all(v is True for v in checks.values())
    return res


def stage_scan():
    OUT.mkdir(parents=True, exist_ok=True)
    allres = {}
    for fam, name, grid in sub_grids():
        t0 = time.time()
        oos = oos_trades(name)
        recorded = W.reprice(oos, W.cost_recorded)["net"]
        gt_raw = grid_trades(name, len(grid))
        picks = R.pick_per_window({i: [{**t, "profit": t["profit"]} for t in trs] for i, trs in gt_raw.items()})
        grid_rec = {i: W.reprice(t, W.cost_recorded)["trades"] for i, t in gt_raw.items()}
        # The settings stay exactly as chosen: picks are made once, on the recorded grid results.
        scan = {}
        for c in LEVELS:
            scan[str(c)] = evaluate(fam, name, grid, oos, gt_raw, picks, W.cost_total(c))
        broker = evaluate(fam, name, grid, oos, gt_raw, picks, W.cost_broker())
        passing = [c for c in LEVELS if scan[str(c)]["passes_without_luck"]]
        gross_pips = float(np.mean([W.gross_move(t) * t["entry"] / fills.PIP[t["symbol"]] for t in oos]))
        allres[name] = {
            "family": fam, "trades": len(oos), "recorded_net": round(sum(t["profit"] for t in oos), 2),
            "repriced_at_recorded_cost": recorded,
            "gross_pips_per_trade": round(gross_pips, 2),
            "picks": [{"round": k + 1, "variant": p["variant"], "params": grid[p["variant"]]}
                      for k, p in enumerate(picks)],
            "threshold_total_pips": max(passing) if passing else None,
            "passing_levels": passing,
            "scan": scan, "broker": broker,
            "grid_recorded_check": {i: round(sum(t["profit"] for t in v), 2) for i, v in grid_rec.items()},
        }
        print(f"{name}: gross {gross_pips:+.2f} pips/trade, threshold "
              f"{allres[name]['threshold_total_pips']}, broker passes {broker['passes_without_luck']} "
              f"(net {broker['net']}), recorded {allres[name]['recorded_net']} vs re-priced {recorded} "
              f"({time.time() - t0:.0f}s)", flush=True)
    (OUT / "scan.json").write_text(json.dumps(allres, indent=1, default=str))


# ----------------------------------------------------------------------------- random runs
def _needs_luck(res):
    return res["threshold_total_pips"] is not None or res["broker"]["passes_without_luck"] or \
        res["scan"]["2.0"]["passes_without_luck"]


def _random_task(job):
    name, schedule, rates, seed = job
    cls = REGISTRY[name]
    s = R.RandomEntry(cls, schedule, rates, seed)
    eng = R.run_oos(s)
    trs = [{k: t[k] for k in KEEP} for t in eng.state.trades]
    p = STATE / name / f"s{seed:03d}.json.gz"
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_bytes(gzip.compress(json.dumps(trs).encode()))
    tmp.replace(p)
    return seed


def stage_random(budget_s, t0):
    scan = json.loads((OUT / "scan.json").read_text())
    for fam, name, grid in sub_grids():
        if not _needs_luck(scan[name]):
            continue
        rates_path = OUT / f"rates_{name}.json"
        if rates_path.exists():
            cfg = json.loads(rates_path.read_text())
        else:
            # Corrected rates (audit fix): rebuilt from the candidate's own OOS run, in memory.
            sched = [(t, p) for t, p in R.schedule_from(R.pick_per_window(
                {i: json.loads(gzip.decompress((GRID_STATE / name / "grid" / f"v{i:02d}.json.gz")
                                               .read_bytes()))["trades"] for i in range(len(grid))}), grid)]
            meas = R.Scheduled(REGISTRY[name], sched)
            eng = R.run_oos(meas)
            cfg = {"schedule": sched, "rates": [[list(k), v] for k, v in R.entry_rates(meas).items()],
                   "candidate_trades": len(eng.state.trades),
                   "candidate_net": round(sum(t["profit"] for t in eng.state.trades), 2)}
            rates_path.write_text(json.dumps(cfg))
        rates = {tuple(k): v for k, v in cfg["rates"]}
        jobs = [(name, cfg["schedule"], rates, s) for s in range(RUNS)
                if not (STATE / name / f"s{s:03d}.json.gz").exists()]
        if not jobs:
            continue
        R.market_data(REGISTRY[name].timeframe, *_span(name))
        ctx = mp.get_context("fork")
        with ctx.Pool(4) as pool:
            running = []
            while jobs or running:
                while jobs and len(running) < 4 and time.time() - t0 < budget_s:
                    running.append(pool.apply_async(_random_task, (jobs.pop(0),)))
                if not running:
                    break
                for r in list(running):
                    if r.ready():
                        r.get()
                        running.remove(r)
                time.sleep(0.5)
        left = len([s for s in range(RUNS) if not (STATE / name / f"s{s:03d}.json.gz").exists()])
        print(f"{name}: random runs left {left}", flush=True)
        if left:
            return False
    return True


def _span(name):
    import datetime as dt
    v0, v1 = R.oos_span()
    return v0 - dt.timedelta(days=getattr(REGISTRY[name], "warmup_days", R.WARMUP_DAYS)), v1


def stage_luck():
    scan = json.loads((OUT / "scan.json").read_text())
    out = {}
    for fam, name, grid in sub_grids():
        res = scan[name]
        if not _needs_luck(res):
            continue
        rand = [json.loads(gzip.decompress((STATE / name / f"s{s:03d}.json.gz").read_bytes()))
                for s in range(RUNS)]
        rand = [[_num(t) for t in trs] for trs in rand]
        oos = oos_trades(name)
        models = {"broker": W.cost_broker(), "total_2.0": W.cost_total(2.0)}
        if res["threshold_total_pips"] is not None:
            models[f"total_{res['threshold_total_pips']}"] = W.cost_total(res["threshold_total_pips"])
        out[name] = {}
        for label, fn in models.items():
            cand = W.reprice(oos, fn)["net"]
            nets = [W.reprice(trs, fn)["net"] for trs in rand]
            lk = R.luck_result(nets, cand, PCT, RUNS)
            out[name][label] = {"candidate_net": cand, "random_trades_mean": round(float(np.mean([len(t) for t in rand])), 1),
                                **{k: lk[k] for k in ("runs", "percentile", "p50", "p95", "share_beaten", "passed")}}
            print(name, label, out[name][label], flush=True)
    (OUT / "luck.json").write_text(json.dumps(out, indent=1))
    return True


def stage_zero():
    out = {}
    for fam, name, grid in sub_grids():
        gt = grid_trades(name, len(grid))
        out[name] = evaluate(fam, name, grid, oos_trades(name), gt, R.pick_per_window(gt),
                             lambda t: (0.0, True))
        print(name, out[name]["net"], [k for k, v in out[name]["checks"].items() if v is False], flush=True)
    (OUT / "zero_cost.json").write_text(json.dumps(out, indent=1, default=str))


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("scan", "random", "luck", "zero"))
    p.add_argument("--max-minutes", type=float, default=8.5)
    a = p.parse_args()
    t0 = time.time()
    if a.stage == "scan":
        stage_scan()
        ok = True
    elif a.stage == "zero":
        stage_zero()
        ok = True
    elif a.stage == "random":
        ok = stage_random(a.max_minutes * 60, t0)
    else:
        ok = stage_luck()
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
