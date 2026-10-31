"""Incubator pre-screen of one idea (grid -> walk-forward -> stitched OOS -> coin-toss luck runs).

Data before the untouched period only (to 2026-10-30; fxbot.backtest.prescreen). Each stage
saves progress and stops before its time budget (default 8.5 minutes, exit code 2); run the
same command again to continue. `all` runs the stages in order.

  python scripts/prescreen.py all --idea wmr_fix_reversal
  python scripts/prescreen.py summary --idea wmr_fix_reversal   # pass/fail, writes research/log.md rows

Outputs: research/incubator_prescreen/<idea>/ (grid.json, picks.json, oos_trades.json.gz,
oos_signals.json, luck.json, summary.json); raw grid trades in state/prescreen/ (not committed).
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

from fxbot.backtest import prescreen as P
from fxbot.backtest import research as R
from fxbot.strategies.families import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "state" / "prescreen"
OUT = ROOT / "research" / "incubator_prescreen"
KEEP = ("symbol", "direction", "entry_epoch", "exit_epoch", "entry", "exit", "profit", "balance_after",
        "commission", "reason", "stake", "multiplier")
WORKERS = 4


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


def _registry():
    reg = dict(REGISTRY)
    try:
        from fxbot.strategies import ml_day
        reg.update(getattr(ml_day, "REGISTRY", {}))
    except ImportError:
        pass
    return reg


# ----------------------------------------------------------------------------- workers
def _grid_task(job):
    idea, name, i, params = job
    spec = P.IDEAS[idea]
    eng = P.run_engine(_registry()[name](**params), symbols=spec.symbols, table=spec.table)
    trades = [{k: t[k] for k in KEEP} for t in eng.state.trades]
    _jdump(STATE / idea / "grid" / f"v{i:02d}.json.gz",
           {"params": params, "trades": trades, "kill_events": eng.state.kill_events})
    return i


def _luck_task(job):
    idea, name, schedule, signals, seed = job
    cls = _registry()[name]
    spec = P.IDEAS[idea]
    s = R.SignalDays(cls, [(t, p) for t, p in schedule], signals, seed, symbols=spec.symbols)
    eng = P.run_oos(s, table=spec.table)
    tr = eng.state.trades
    from fxbot.backtest.audit import gross_of
    out = {"seed": seed, "trades": len(tr), "net_profit": round(sum(t["profit"] for t in tr), 2),
           "gross": round(sum(gross_of(t) for t in tr), 2), "kill_events": len(eng.state.kill_events)}
    _jdump(STATE / idea / "luck" / f"s{seed:03d}.json", out)
    return out


def _pool_run(fn, jobs, budget_s, t0):
    done = 0
    ctx = mp.get_context("fork")
    with ctx.Pool(WORKERS) as pool:
        pending = list(jobs)
        running = []
        while pending or running:
            while pending and len(running) < WORKERS and time.time() - t0 < budget_s:
                running.append(pool.apply_async(fn, (pending.pop(0),)))
            if not running:
                break
            for r in list(running):
                if r.ready():
                    r.get()
                    running.remove(r)
                    done += 1
            time.sleep(0.3)
    return done, len(pending)


# ----------------------------------------------------------------------------- stages
def stage_grid(idea, budget_s, t0):
    name, grid = P.IDEAS[idea]
    jobs = [(idea, name, i, p) for i, p in enumerate(grid)
            if not (STATE / idea / "grid" / f"v{i:02d}.json.gz").exists()]
    if jobs:
        P.market_data(_registry()[name].timeframe, P.DATA_START, P.DATA_END, P.IDEAS[idea].symbols)   # load once before forking
    done, left = _pool_run(_grid_task, jobs, budget_s, t0)
    print(f"{idea} grid: {done} variants run now, {left} left")
    return left == 0


def _grid_trades(idea, n):
    return {i: _jload(STATE / idea / "grid" / f"v{i:02d}.json.gz") for i in range(n)}


def stage_oos(idea):
    name, grid = P.IDEAS[idea]
    cls = _registry()[name]
    raw = _grid_trades(idea, len(grid))
    picks = P.pick_per_window({i: r["trades"] for i, r in raw.items()})
    rows = []
    for i, p in enumerate(grid):
        tr = raw[i]["trades"]
        row = {"variant": i, **p, "trades": len(tr), "net_profit": round(sum(t["profit"] for t in tr), 2),
               "kill_events": len(raw[i]["kill_events"])}
        for k, w in enumerate(P.windows()):
            sc = R.window_score(tr, P.epoch_of(w.train_start), P.epoch_of(w.train_end + dt.timedelta(days=1)))
            row[f"train{k + 1}_score"] = round(sc["score"], 3) if sc["score"] > -1e9 else None
        rows.append(row)
    schedule = P.schedule_from(picks, grid)
    spec = P.IDEAS[idea]
    meas = R.Scheduled(cls, schedule, spec.symbols)
    e_m = P.run_oos(meas, table=spec.table)
    e_s = P.run_oos(R.Scheduled(cls, schedule, spec.symbols), stress=1.5, table=spec.table)
    out = OUT / idea
    _jdump(out / "grid.json", rows)
    _jdump(out / "picks.json", [{"round": k + 1, "train": f"{p['window'].train_start}..{p['window'].train_end}",
                                 "test": f"{p['window'].valid_start}..{p['window'].valid_end}",
                                 "variant": p["variant"], "params": grid[p["variant"]],
                                 "train_score": round(p["train"]["score"], 3) if p["train"]["score"] > -1e9 else None,
                                 "train_trades": p["train"]["trades"]} for k, p in enumerate(picks)])
    _jdump(out / "oos_trades.json.gz", {"schedule": schedule,
                                        "measured": [{k: t[k] for k in KEEP} for t in e_m.state.trades],
                                        "stress_1_5x": [{k: t[k] for k in KEEP} for t in e_s.state.trades],
                                        "kill_events": len(e_m.state.kill_events),
                                        "blocked": dict(e_m.state.blocked), "refused": dict(e_m.state.refused)})
    _jdump(out / "oos_signals.json", {"schedule": schedule, "signals": R.entry_signals(e_m.state)})
    print(f"{idea}: OOS {len(e_m.state.trades)} trades, net {round(sum(t['profit'] for t in e_m.state.trades), 2)} USD")
    return True


def stage_luck(idea, budget_s, t0, runs):
    name, _ = P.IDEAS[idea]
    cfg = _jload(OUT / idea / "oos_signals.json")
    signals = [tuple(x) for x in cfg["signals"]]
    jobs = [(idea, name, cfg["schedule"], signals, seed) for seed in range(runs)
            if not (STATE / idea / "luck" / f"s{seed:03d}.json").exists()]
    if jobs:
        v0, v1 = P.oos_span()
        P.market_data(_registry()[name].timeframe, v0 - dt.timedelta(days=P.WARMUP_DAYS), v1, P.IDEAS[idea].symbols)
    done, left = _pool_run(_luck_task, jobs, budget_s, t0)
    print(f"{idea}: luck runs {done} done now, {left} left")
    if left:
        return False
    res = sorted((_jload(STATE / idea / "luck" / f"s{s:03d}.json") for s in range(runs)), key=lambda r: r["seed"])
    _jdump(OUT / idea / "luck.json", res)
    return True


def stage_summary(idea):
    name, grid = P.IDEAS[idea]
    d = OUT / idea
    oos = _jload(d / "oos_trades.json.gz")
    luck = _jload(d / "luck.json") if (d / "luck.json").exists() else []
    trades = oos["measured"]
    net = round(sum(t["profit"] for t in trades), 2)
    from fxbot.backtest.audit import gross_of
    gross = round(sum(gross_of(t) for t in trades), 2)
    lk = P.luck_summary([r["net_profit"] for r in luck], [r["gross"] for r in luck], net, gross)
    res = {"idea": idea, "strategy": name, "timeframe": _registry()[name].timeframe,
           "symbols": list(P.IDEAS[idea].symbols), "cost_table": P.IDEAS[idea].table,
           **P.summary(trades, oos["stress_1_5x"], oos["kill_events"], lk, len(grid), len(grid[0]),
                       P.IDEAS[idea].symbols),
           "picks": [p for p in _jload(d / "picks.json")], "blocked": oos["blocked"], "refused": oos["refused"]}
    _jdump(d / "summary.json", res)
    print(json.dumps({k: res[k] for k in ("idea", "trades", "trades_per_day", "net_measured", "net_1_5x", "gross",
                                          "gross_pips_per_trade", "win_rate_pct", "profit_factor", "kill_events",
                                          "move_vs_cost", "per_pair", "per_window_gross", "checks",
                                          "prescreen_pass", "all_checks")}, default=str))
    print("  luck:", {k: (round(v, 2) if isinstance(v, float) else v) for k, v in lk.items()})
    return True


def write_log(idea) -> None:
    """Add / refresh this idea's rows in research/log.md (between markers)."""
    log = ROOT / "research" / "log.md"
    text = log.read_text()
    today = dt.date.today().isoformat()
    name, grid = P.IDEAS[idea]
    d = OUT / idea
    rows = _jload(d / "grid.json")
    picks = _jload(d / "picks.json")
    summ = _jload(d / "summary.json") if (d / "summary.json").exists() else None
    picked = {}
    for p in picks:
        picked.setdefault(p["variant"], []).append(str(p["round"]))
    tf = _registry()[name].timeframe
    lines = [f"<!-- prescreen:{idea} start -->", "",
             f"### {idea} ({name}, {tf}): {len(grid)} variants", "",
             "Full-period result (2021-10-27 to 2026-10-30, measured cost) is for reference; "
             "selection used only each round's training window.", "",
             "| Date | Variant | Params | Full-period trades | Full-period net USD | Kill events | Picked in rounds |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        prm = ", ".join(f"{k}={r[k]}" for k in grid[r["variant"]])
        lines.append(f"| {today} | {idea} v{r['variant']:02d} | {prm} | {r['trades']} | {r['net_profit']} "
                     f"| {r['kill_events']} | {', '.join(picked.get(r['variant'], [])) or '-'} |")
    if summ:
        lk = summ["luck"]
        lines += ["", f"Stitched OOS ({summ['oos_span'][0]} to {summ['oos_span'][1]}, {summ['trading_days']} trading days): "
                      f"{summ['trades']} trades ({summ['trades_per_day']}/day), net {summ['net_measured']} USD "
                      f"(1.5x: {summ['net_1_5x']}), gross before costs {summ['gross']} USD "
                      f"({summ['gross_pips_per_trade']} pips/trade), avg |move| {summ['move_vs_cost']['avg_abs_move_pips']} pips "
                      f"vs cost {summ['move_vs_cost']['avg_cost_pips']} pips (ratio {summ['move_vs_cost']['ratio']}), "
                      f"win rate {summ['win_rate_pct']}%, PF {summ['profit_factor']}, kill events {summ['kill_events']}, "
                      f"per pair net/gross {{{', '.join(f'{s[3:]}: {v['net']}/{v['gross']} ({v['trades']})' for s, v in summ['per_pair'].items())}}}, "
                      f"per window gross {summ['per_window_gross']}. Luck ({lk.get('runs', 0)} coin-toss runs on the "
                      f"candidate's own signals): median net {round(lk.get('median_net', 0), 2)}, share beaten "
                      f"{round(100 * lk.get('share_beaten_net', 0))}%. Checks failed: "
                      f"{[k for k, v in summ['checks'].items() if not v] or 'none'}. "
                      f"**Pre-screen (check 6): {'PASS' if summ['prescreen_pass'] else 'FAIL'}**; "
                      f"all 2/3/5/6 checks: {summ['all_checks']}. Files: `research/incubator_prescreen/{idea}/`."]
    lines += ["", f"<!-- prescreen:{idea} end -->"]
    block = "\n".join(lines)
    start, end = f"<!-- prescreen:{idea} start -->", f"<!-- prescreen:{idea} end -->"
    if start in text:
        i, j = text.index(start), text.index(end) + len(end)
        text = text[:i] + block + text[j:]
    else:
        text = text.rstrip("\n") + "\n\n" + block + "\n"
    log.write_text(text)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("grid", "oos", "luck", "summary", "all"))
    p.add_argument("--idea", required=True, choices=sorted(P.IDEAS))
    p.add_argument("--max-minutes", type=float, default=8.5)
    p.add_argument("--runs", type=int, default=P.LUCK_RUNS)
    a = p.parse_args()
    t0 = time.time()
    budget = a.max_minutes * 60
    stages = [a.stage] if a.stage != "all" else ["grid", "oos", "luck", "summary"]
    ok = True
    for st in stages:
        if st == "grid":
            ok = stage_grid(a.idea, budget, t0)
        elif st == "oos":
            if (OUT / a.idea / "oos_signals.json").exists() and a.stage == "all":
                continue
            ok = stage_oos(a.idea)
        elif st == "luck":
            ok = stage_luck(a.idea, budget, t0, a.runs)
        else:
            ok = stage_summary(a.idea)
            write_log(a.idea)
        if not ok:
            break
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
