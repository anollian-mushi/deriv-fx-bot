"""Step 2 of the TJR test: walk-forward, out-of-sample runs, coin-toss luck runs, summary.

Plan and variants: docs/tjr_test_plan.md, fxbot.backtest.tjr_test. Data before 2026-10-31 only
(fxbot.backtest.prescreen never reads the untouched period).

Run ONLY after BOTH Monday's (2 Nov) new-pairs cost decision and the 5 Nov clock-change re-check
have updated the cost tables (owner, 2 Nov 2026; scheduled start Friday 6 Nov). `setup` refuses
to start without --costs-rechecked or if `preflight` finds a problem, records the commission
tables' SHA-256 and the new pairs dropped for cost, and every later stage stops if a table
changed after setup.

Every stage saves progress and stops before its time budget (default 8.5 minutes, exit code 2):
run the same command again to continue.

  python scripts/tjr_test.py preflight          # are both cost inputs final? (exit 2 if not)
  python scripts/tjr_test.py setup --costs-rechecked
  python scripts/tjr_test.py grid          # 16 walk-forward variants over 2021-10-27..2026-10-30
  python scripts/tjr_test.py oos           # 22 schedules x (measured, 1.5x) out of sample
  python scripts/tjr_test.py luck          # 200 coin-toss replays per variant with gross > 0
  python scripts/tjr_test.py summary       # research/tjr/summary.json, results.md, research/log.md
  python scripts/tjr_test.py status

Outputs: research/tjr/ (committed); engine states and raw runs in state/tjr/ (not committed).
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import multiprocessing as mp
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.backtest import prescreen as P
from fxbot.backtest import research as R
from fxbot.backtest import tjr_test as TT
from fxbot.backtest.audit import gross_of
from fxbot.backtest import engine as E
from fxbot.backtest.engine import Engine
from fxbot.backtest.metrics import summarise
from fxbot.strategies.tjr import TJRReplay

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "tjr"
OUT = ROOT / "research" / "tjr"
KEEP = ("symbol", "direction", "entry_epoch", "exit_epoch", "entry", "exit", "profit", "balance_after",
        "commission", "reason", "stake", "multiplier", "sl_pips", "stop_moved_time", "rate_pct")


def _jdump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    if path.suffix == ".gz":
        tmp.write_bytes(gzip.compress(json.dumps(obj, default=str).encode()))
    else:
        tmp.write_text(json.dumps(obj, indent=1, default=str))
    tmp.replace(path)


def _jload(path: Path):
    if path.suffix == ".gz":
        return json.loads(gzip.decompress(path.read_bytes()))
    return json.loads(path.read_text())


# ----------------------------------------------------------------------------- setup
def setup_info() -> dict:
    f = OUT / "setup.json"
    if not f.exists():
        raise SystemExit("run `python scripts/tjr_test.py setup --costs-rechecked` first")
    info = _jload(f)
    for path, digest in info["table_sha256"].items():
        if TT.sha256(path) != digest:
            raise SystemExit(f"{path} changed after setup: results would mix two commission tables. "
                             "Delete research/tjr/ and state/tjr/ and start again from setup.")
    return info


def stage_preflight() -> bool:
    res = TT.preflight()
    print(json.dumps(res, indent=1, default=str))
    return res["ok"]


def stage_setup(rechecked: bool) -> bool:
    if not rechecked:
        raise SystemExit("not started: the owner's rule is to run only after BOTH Monday's new-pairs cost "
                         "decision and the 5 Nov clock-change re-check have updated the cost tables "
                         "(check with `preflight`, then pass --costs-rechecked)")
    pre = TT.preflight()
    if not pre["ok"]:
        print(json.dumps(pre, indent=1, default=str))
        raise SystemExit("not started: the cost inputs are not final (see problems above)")
    syms, tables, dropped = TT.pair_list()
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    info = {"created_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "commit": commit,
            "symbols": list(syms), "tables": tables, "table_sha256": {p: TT.sha256(p) for p in tables},
            "new_pairs_dropped_for_cost": dropped, "preflight": pre["facts"],
            "data_end": P.DATA_END.isoformat(), "oos_span": [d.isoformat() for d in P.oos_span()],
            "variants": TT.variant_count()}
    _jdump(OUT / "setup.json", info)
    print(json.dumps(info, indent=1))
    return True


# ----------------------------------------------------------------------------- engine jobs
def _table(info):
    return TT.table(info["tables"])


def _run(job) -> bool:
    """One resumable engine run. job = (kind, key, payload, budget_s)."""
    kind, key, payload, budget = job
    info = setup_info()
    syms = tuple(info["symbols"])
    if kind == "grid":
        idea = TT.ideas()[payload["idea"]]
        cls = TT.CLASSES[idea["tf"]]
        strat = cls(**payload["params"])
        start, end = P.DATA_START, P.DATA_END
        data = P.market_data(cls.timeframe, start, end, syms)
        stress = 1.0
    elif kind == "oos":
        cls = TT.CLASSES[TT.ideas()[payload["idea"]]["tf"]]
        strat = R.Scheduled(cls, [(t, p) for t, p in payload["schedule"]], syms)
        v0, end = P.oos_span()
        start = v0 - dt.timedelta(days=cls.warmup_days)
        data = P.market_data(cls.timeframe, start, end, syms)
        stress = payload["stress"]
    else:                                               # luck
        cls = TT.CLASSES[TT.ideas()[payload["idea"]]["tf"]]
        sigs = TT.parse_signals(payload["signals"])
        strat = TJRReplay(cls.timeframe, sigs, payload["seed"], syms)
        v0, end = P.oos_span()
        start = v0 - dt.timedelta(days=cls.warmup_days)
        data = TT.replay_data(P.market_data(cls.timeframe, start, end, syms), sigs, cls.timeframe)
        stress = 1.0
    # Resumable engine states live under state/tjr/engine/ and carry this setup's id, so a state
    # left by an earlier setup or a test run can never be resumed by mistake (6 Nov 2026: leftover
    # synthetic-data states under state/backtest/ were resumed by four grid and ten OOS runs).
    E.STATE_DIR = STATE / "engine"
    sid = TT.hashlib.sha256(info["created_utc"].encode()).hexdigest()[:10]
    eng = Engine(strat, list(syms), start, end, stress=stress, data=data, kill_switch="observe",
                 table=_table(info), run_name=None if kind == "luck" else f"tjr_{kind}_{key}_{sid}")
    if not eng.run(max_seconds=budget):
        return False
    st = eng.state
    trades = [{k: t.get(k) for k in KEEP} for t in st.trades]
    if kind == "luck":
        _jdump(STATE / "luck" / payload["variant"] / f"s{payload['seed']:03d}.json",
               {"seed": payload["seed"], "trades": len(trades), "net_profit": round(sum(t["profit"] for t in trades), 2),
                "gross": round(sum(gross_of(t) for t in trades), 2), "kill_events": len(st.kill_events),
                "per_pair_net": {s: round(sum(t["profit"] for t in trades if t["symbol"] == s), 2) for s in syms}})
        return True
    inner = getattr(eng.strategy, "inner", None)
    stats = Counter()
    for s in (inner.values() if inner else [eng.strategy]):
        stats.update(getattr(s, "stats", {}))
    out = {"key": key, "payload": {k: v for k, v in payload.items() if k != "signals"}, "trades": trades,
           "kill_events": st.kill_events, "refused": dict(st.refused), "blocked": dict(st.blocked),
           "stats": dict(stats),
           "signals": [[sym, int(t), a] for t, sym, a in st.signals if a.startswith("Enter(")]}
    _jdump(STATE / kind / f"{key}.json.gz", out)
    return True


def _preload(jobs) -> None:
    """Load (and cache) the market data once in this process before forking, so workers share it
    and never build the same cache file at the same time."""
    syms = tuple(setup_info()["symbols"])
    v0, v1 = P.oos_span()
    for kind, _, payload, _ in jobs:
        cls = TT.CLASSES[TT.ideas()[payload["idea"]]["tf"]]
        if kind == "grid":
            P.market_data(cls.timeframe, P.DATA_START, P.DATA_END, syms)
        else:
            P.market_data(cls.timeframe, v0 - dt.timedelta(days=cls.warmup_days), v1, syms)


def _pool(jobs, workers, budget_s, t0) -> int:
    """Run jobs in parallel until the budget is spent. Returns how many are still unfinished."""
    if not jobs:
        return 0
    _preload(jobs)
    left = list(jobs)
    unfinished = 0
    ctx = mp.get_context("fork")
    with ctx.Pool(workers, maxtasksperchild=1) as pool:
        running = []
        while left or running:
            while left and len(running) < workers:
                remaining = budget_s - (time.time() - t0)
                if remaining < 30:
                    break
                kind, key, payload, _ = left.pop(0)
                running.append(pool.apply_async(_run, ((kind, key, payload, remaining - 20),)))
            if not running:
                break
            for r in list(running):
                if r.ready():
                    unfinished += 0 if r.get() else 1
                    running.remove(r)
            time.sleep(0.5)
    return unfinished + len(left)


# ----------------------------------------------------------------------------- stages
def grid_jobs():
    for idea, spec in TT.ideas().items():
        for i, params in enumerate(spec["grid"]):
            key = f"{idea}_v{i}"
            if not (STATE / "grid" / f"{key}.json.gz").exists():
                yield ("grid", key, {"idea": idea, "params": params}, 0)


def stage_grid(budget_s, t0, workers) -> bool:
    jobs = list(grid_jobs())
    # 1m-fed runs (5m execution) need about 3 GB each: never more than 2 at once
    jobs.sort(key=lambda j: TT.ideas()[j[2]["idea"]]["tf"])
    left = _pool(jobs, workers, budget_s, t0)
    print(f"grid: {len(jobs) - left} of {len(jobs)} pending runs finished now; {left} left")
    return left == 0


def schedules() -> dict[str, dict]:
    """variant -> {idea, schedule}, from the finished grid (walk-forward picks per round)."""
    out = {}
    for idea, spec in TT.ideas().items():
        files = [STATE / "grid" / f"{idea}_v{i}.json.gz" for i in range(len(spec["grid"]))]
        if not all(f.exists() for f in files):
            continue
        raw = {i: _jload(f) for i, f in enumerate(files)}
        picks = P.pick_per_window({i: r["trades"] for i, r in raw.items()})
        sched = P.schedule_from(picks, spec["grid"])
        _jdump(OUT / idea / "picks.json", [{"round": k + 1, "train": f"{p['window'].train_start}..{p['window'].train_end}",
                                            "test": f"{p['window'].valid_start}..{p['window'].valid_end}",
                                            "variant": p["variant"], "params": spec["grid"][p["variant"]],
                                            "train_score": round(p["train"]["score"], 3) if p["train"]["score"] > -1e9 else None,
                                            "train_trades": p["train"]["trades"]} for k, p in enumerate(picks)])
        _jdump(OUT / idea / "grid.json", [{"variant": i, **spec["grid"][i], "trades": len(r["trades"]),
                                           "net_profit": round(sum(t["profit"] for t in r["trades"]), 2),
                                           "gross": round(sum(gross_of(t) for t in r["trades"]), 2),
                                           "kill_events": len(r["kill_events"]), "stats": r["stats"],
                                           "refused": r["refused"]} for i, r in raw.items()])
        out[idea] = {"idea": idea, "schedule": sched}
        for name, d in TT.derived().items():
            if d["idea"] == idea:
                out[name] = {"idea": idea, "schedule": [(t, {**p, **d["change"]}) for t, p in sched]}
    return out


def stage_oos(budget_s, t0, workers) -> bool:
    sch = schedules()
    if len(sch) < len(TT.ideas()) + len(TT.derived()):
        print("oos: the grid is not finished")
        return False
    jobs = []
    for variant, s in sch.items():
        for stress in (1.0, 1.5):
            key = f"{variant}_x{stress}"
            if not (STATE / "oos" / f"{key}.json.gz").exists():
                jobs.append(("oos", key, {"idea": s["idea"], "variant": variant, "schedule": s["schedule"],
                                          "stress": stress}, 0))
    jobs.sort(key=lambda j: TT.ideas()[j[2]["idea"]]["tf"])
    left = _pool(jobs, workers, budget_s, t0)
    print(f"oos: {len(jobs) - left} of {len(jobs)} pending runs finished now; {left} left")
    return left == 0


def _oos(variant):
    m, s = STATE / "oos" / f"{variant}_x1.0.json.gz", STATE / "oos" / f"{variant}_x1.5.json.gz"
    return (_jload(m), _jload(s)) if m.exists() and s.exists() else (None, None)


def stage_luck(budget_s, t0, workers, runs) -> bool:
    sch = schedules()
    jobs, skipped = [], []
    for variant, s in sch.items():
        meas, _ = _oos(variant)
        if meas is None:
            print("luck: oos is not finished")
            return False
        if sum(gross_of(t) for t in meas["trades"]) <= 0:
            skipped.append(variant)                  # as in the pre-screen: not run when gross <= 0
            continue
        for seed in range(runs):
            if not (STATE / "luck" / variant / f"s{seed:03d}.json").exists():
                jobs.append(("luck", f"{variant}_s{seed}", {"idea": s["idea"], "variant": variant, "seed": seed,
                                                             "signals": meas["signals"]}, 0))
    left = _pool(jobs, workers, budget_s, t0)
    print(f"luck: {len(jobs) - left} of {len(jobs)} runs finished now; {left} left; "
          f"not run (gross <= 0): {skipped}")
    return left == 0


def stage_summary(runs) -> bool:
    info = setup_info()
    syms = tuple(info["symbols"])
    sch = schedules()
    allres = {}
    for variant in sch:
        meas, stress = _oos(variant)
        if meas is None:
            continue
        trades = meas["trades"]
        lfiles = sorted((STATE / "luck" / variant).glob("s*.json")) if (STATE / "luck" / variant).exists() else []
        luck = [_jload(f) for f in lfiles]
        net = round(sum(t["profit"] for t in trades), 2)
        gross = round(sum(gross_of(t) for t in trades), 2)
        lk = P.luck_summary([r["net_profit"] for r in luck], [r["gross"] for r in luck], net, gross)
        lk["complete"] = len(luck) >= runs
        res = P.summary(trades, stress["trades"], len(meas["kill_events"]), lk, 2, 4, syms)
        res["checks"].update(TT.trades_per_day_check(res["trades_per_day"]))
        res.update({"variant": variant, "idea": sch[variant]["idea"], "schedule": sch[variant]["schedule"],
                    "metrics": summarise(sorted(trades, key=lambda t: t["exit_epoch"]), 100.0),
                    "gross_pips": TT.gross_pips_per_trade(trades), "cost_share_of_risk": TT.cost_share_of_risk(trades),
                    "mt5_majors": TT.mt5_view(trades), "funnel": meas["stats"], "engine_refused": meas["refused"],
                    "engine_blocked": meas["blocked"],
                    "stops_moved": sum(1 for t in trades if t.get("stop_moved_time")),
                    "pairs_profitable": sum(1 for v in res["per_pair"].values() if v["net"] > 0)})
        allres[variant] = res
        _jdump(OUT / variant / "summary.json", res)
        _jdump(OUT / variant / "oos_trades.json.gz", {"measured": trades, "stress_1_5x": stress["trades"]})
    _jdump(OUT / "summary.json", allres)
    lines = ["| Variant | Trades (/day) | Gross pips/trade | Net / 1.5x USD | Cost share of risk | Coin toss beaten | Checks failed |",
             "|---|---|---|---|---|---|---|"]
    for v, r in allres.items():
        failed = [k for k, ok in r["checks"].items() if not ok and k != "c3_waivable_at_0_3"]
        lk = r["luck"]
        lines.append(f"| {v} | {r['trades']} ({r['trades_per_day']}) | {r['gross_pips']['all']} | {r['net_measured']} / "
                     f"{r['net_1_5x']} | {r['cost_share_of_risk']['median']} | "
                     f"{str(round(100 * lk['share_beaten_net'])) + '%' if lk.get('runs') else 'not run'} | {failed or 'none'} |")
    head = [f"Pairs: {', '.join(info['symbols'])}. New pairs dropped by Monday's cost check: "
            f"{', '.join(info.get('new_pairs_dropped_for_cost') or []) or 'none'}.", ""]
    (OUT / "results.md").write_text("\n".join(head + lines) + "\n")
    print("\n".join(lines))
    return True


def stage_status() -> bool:
    for kind in ("grid", "oos"):
        d = STATE / kind
        print(kind, len(list(d.glob("*.json.gz"))) if d.exists() else 0, "finished")
    d = STATE / "luck"
    if d.exists():
        for v in sorted(p.name for p in d.iterdir()):
            print("luck", v, len(list((d / v).glob("s*.json"))))
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("preflight", "setup", "grid", "oos", "luck", "summary", "status"))
    p.add_argument("--costs-rechecked", action="store_true")
    p.add_argument("--max-minutes", type=float, default=8.5)
    p.add_argument("--workers", type=int, default=2)
    p.add_argument("--runs", type=int, default=TT.LUCK_RUNS)
    a = p.parse_args()
    t0 = time.time()
    budget = a.max_minutes * 60
    if a.stage == "preflight":
        ok = stage_preflight()
    elif a.stage == "setup":
        ok = stage_setup(a.costs_rechecked)
    elif a.stage == "status":
        ok = stage_status()
    else:
        setup_info()
        if a.stage == "grid":
            ok = stage_grid(budget, t0, a.workers)
        elif a.stage == "oos":
            ok = stage_oos(budget, t0, a.workers)
        elif a.stage == "luck":
            ok = stage_luck(budget, t0, max(a.workers, 4), a.runs)
        else:
            ok = stage_summary(a.runs)
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
