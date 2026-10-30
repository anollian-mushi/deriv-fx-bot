"""Phase 4 audit on real (pre-holdout) data: can the pipeline see an edge, and are the
costs and the luck check right? Diagnostics only; nothing here is a candidate.

Stages (each well under 10 minutes; results go to research/audit/<stage>.json):

  python scripts/audit_phase4.py trades        # consistency of every committed OOS trades.csv
  python scripts/audit_phase4.py utc           # the US jobs-report spike sits at 13:30/12:30 UTC
  python scripts/audit_phase4.py cheat         # next-candle cheat vs 20 random-direction twins, 2024
  python scripts/audit_phase4.py grossnet      # gross (no cost) vs net for the OOS runs + engine check
  python scripts/audit_phase4.py flip          # families with reversed signals, before and after costs
  python scripts/audit_phase4.py luck-preview --family f8 --runs 100   # corrected luck check (resumable)
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import multiprocessing as mp
import sys
import time
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401

import numpy as np

from fxbot import sessions
from fxbot.backtest import audit, fills
from fxbot.backtest import research as R
from fxbot.backtest.candles import load_m1
from fxbot.contracts import multiplier as mc
from fxbot.strategies.families import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "audit"
STATE = ROOT / "state" / "audit"
OOS_NAMES = [n for _, subs in R.FAMILIES.items() for n, _ in subs]


def save(stage: str, obj) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{stage}.json").write_text(json.dumps(obj, indent=1, default=str))
    print(f"-> {OUT.relative_to(ROOT) / (stage + '.json')}")


def read_trades(name: str) -> list[dict]:
    path = ROOT / "reports" / "backtests" / f"phase4_{name}_oos" / "trades.csv"
    rows = []
    for r in csv.DictReader(path.open()):
        for k in ("stake", "entry", "exit", "profit", "commission", "rate_pct"):
            r[k] = float(r[k])
        for k in ("multiplier", "entry_epoch", "exit_epoch"):
            r[k] = int(r[k])
        r["sl_amount"] = float(r["sl_amount"]) if r["sl_amount"] else None
        r["tp_amount"] = float(r["tp_amount"]) if r["tp_amount"] else None
        rows.append(r)
    return rows


def schedule_of(name: str) -> list[tuple[int, dict]]:
    cfg = json.loads((ROOT / "research" / "phase4" / name / "oos_rates.json").read_text())
    return [(t, p) for t, p in cfg["schedule"]]


def net(trades) -> float:
    return round(sum(t["profit"] for t in trades), 2)


# ----------------------------------------------------------------------------- trades
def stage_trades():
    table = fills.CommissionTable()
    out, total = {}, Counter()
    for name in OOS_NAMES:
        c = Counter()
        for r in read_trades(name):
            sym, up = r["symbol"], r["direction"] == "MULTUP"
            ee, xe = r["entry_epoch"], r["exit_epoch"]
            if abs(mc.commission(r["stake"], r["multiplier"], table.rate(sym, ee)) - r["commission"]) > 1e-4:
                c["commission_not_table_rate_x_stake_x_multiplier"] += 1
            gross = (1 if up else -1) * (r["exit"] - r["entry"]) / r["entry"] * r["stake"] * r["multiplier"]
            if r["reason"] == "take_profit":
                if abs(r["profit"] - r["tp_amount"]) > 1e-9 or abs(gross - r["commission"] - r["profit"]) > 0.011:
                    c["take_profit_amount_mismatch"] += 1
            elif r["reason"] == "stop_out":
                if abs(r["profit"] + r["stake"]) > 1e-9:
                    c["stop_out_not_whole_stake"] += 1
            elif abs(round(max(gross - r["commission"], -r["stake"]), 2) - r["profit"]) > 0.011:
                c["profit_not_direction_x_move_minus_commission"] += 1
            if r["reason"] == "stop_loss" and r["profit"] > -r["sl_amount"] + 0.011:
                c["stop_loss_lost_less_than_its_amount"] += 1
            if not sessions.in_entry_window(ee) or not sessions.market_open(ee) or sessions.in_pause(ee):
                c["entry_outside_window"] += 1
            h = (ee % 86400) // 3600
            if h == 12 or (h == 13 and sym == "frxEURUSD"):
                c["entry_in_cost_gate_hour"] += 1
            lo, hi = {"frxEURUSD": (0.95, 1.25), "frxGBPUSD": (1.05, 1.45), "frxUSDJPY": (100, 170)}[sym]
            if not lo <= r["entry"] <= hi:
                c["price_not_this_pairs_range"] += 1
            w = dt.datetime.fromtimestamp(xe, dt.timezone.utc)
            if w.weekday() >= 5 or (w.weekday() == 4 and xe % 86400 > 20 * 3600 + 30 * 60):
                c["held_past_friday_2030"] += 1
            if xe < ee:
                c["exit_before_entry"] += 1
            if xe == ee:
                c["closed_in_the_entry_minute"] += 1
            if r["direction"] not in ("MULTUP", "MULTDOWN") or r["multiplier"] != 100:
                c["bad_direction_or_multiplier"] += 1
            c["trades"] += 1
        out[name] = dict(c)
        total.update(c)
        print(f"{name:28s} {dict(c)}")
    print("TOTAL", dict(total))
    save("trades", {"per_family": out, "total": dict(total),
                    "note": "every count other than 'trades' and 'closed_in_the_entry_minute' is a defect"})


# ----------------------------------------------------------------------------- utc
def stage_utc():
    """US jobs report: first Friday, 08:30 New York = 13:30 UTC in winter, 12:30 UTC in summer."""
    def us_dst(d):
        mar = dt.date(d.year, 3, 8); mar += dt.timedelta(days=(6 - mar.weekday()) % 7)
        nov = dt.date(d.year, 11, 1); nov += dt.timedelta(days=(6 - nov.weekday()) % 7)
        return mar <= d < nov
    res = {}
    for sym in R.SYMBOLS:
        b = load_m1(sym, R.DATA_START, R.DATA_END)
        rng = (b.high - b.low) / fills.PIP[sym]
        day = b.epoch // 86400
        sod = b.epoch % 86400
        firsts = {int(d) for d in np.unique(day)
                  if (dt.date(1970, 1, 1) + dt.timedelta(days=int(d))).weekday() == 4
                  and (dt.date(1970, 1, 1) + dt.timedelta(days=int(d))).day <= 7}
        res[sym] = {}
        for season, pick in (("winter", lambda d: not us_dst(d)), ("summer", us_dst)):
            sel = np.isin(day, [d for d in firsts if pick(dt.date(1970, 1, 1) + dt.timedelta(days=d))])
            prof = {}
            for hh, mm in [(11, 30), (12, 0), (12, 30), (13, 0), (13, 30), (14, 0), (14, 30)]:
                m = sel & (sod == hh * 3600 + mm * 60)
                prof[f"{hh:02d}:{mm:02d}"] = round(float(rng[m].mean()), 1)
            peak = max(prof, key=prof.get)
            res[sym][season] = {"days": int(sel.sum() and len(set(day[sel]))), "mean_1m_range_pips": prof,
                                "peak_minute": peak, "expected": "13:30" if season == "winter" else "12:30"}
            print(sym, season, prof, "peak", peak)
    ok = all(v["peak_minute"] == v["expected"] for s in res.values() for v in s.values())
    print("UTC alignment:", "OK" if ok else "WRONG")
    save("utc", {"ok": ok, "per_symbol": res})


# ----------------------------------------------------------------------------- cheat
CHEAT_START, CHEAT_END = dt.date(2024, 1, 1), dt.date(2024, 12, 31)


def _cheat_run(seed):
    data = R.market_data("1h", CHEAT_START, CHEAT_END)
    future = {s: tf for s, (_, tf) in data.items()}
    rng = None if seed is None else np.random.default_rng(seed)
    eng = R.run_engine(audit.Cheat(future, rng=rng), CHEAT_START, CHEAT_END)
    tr = eng.state.trades
    return {"seed": seed, "trades": len(tr), "net": net(tr), "gross": round(sum(audit.gross_of(t) for t in tr), 2),
            "kill_events": len(eng.state.kill_events),
            "per_pair": {s: net([t for t in tr if t["symbol"] == s]) for s in R.SYMBOLS}}


def stage_cheat(runs: int = 20):
    R.market_data("1h", CHEAT_START, CHEAT_END)
    with mp.get_context("fork").Pool(4) as pool:
        res = pool.map(_cheat_run, [None] + list(range(runs)))
    cheat, randoms = res[0], res[1:]
    nets = [r["net"] for r in randoms]
    out = {"period": f"{CHEAT_START}..{CHEAT_END}", "cheat": cheat,
           "random_direction_twins": {"runs": runs, "net_mean": round(float(np.mean(nets)), 2),
                                      "net_max": max(nets), "net_min": min(nets),
                                      "trades_mean": round(float(np.mean([r["trades"] for r in randoms])), 1),
                                      "kill_events_total": sum(r["kill_events"] for r in randoms)},
           "cheat_beats_every_random_run": cheat["net"] > max(nets),
           "all_runs": randoms}
    print(json.dumps({k: v for k, v in out.items() if k != "all_runs"}, indent=1))
    save("cheat", out)


# ----------------------------------------------------------------------------- gross vs net
GROSSNET_ENGINE_CHECK = ("f5_session_drift", "f1_london_breakout", "f9_eur_gbp_convergence")


def stage_grossnet():
    out = {}
    for name in OOS_NAMES:
        tr = read_trades(name)
        costs = [audit.cost_of(t) for t in tr]
        row = {"trades": len(tr), "net": net(tr), "gross": round(sum(audit.gross_of(t) for t in tr), 2),
               "commission": round(sum(c["commission"] for c in costs), 2),
               "entry_slippage": round(sum(c["entry_slippage"] for c in costs), 2),
               "sl_slippage": round(sum(c["sl_slippage"] for c in costs), 2),
               "gross_per_pair": {s: round(sum(audit.gross_of(t) for t in tr if t["symbol"] == s), 2) for s in R.SYMBOLS},
               "net_per_pair": {s: net([t for t in tr if t["symbol"] == s]) for s in R.SYMBOLS}}
        row["gross_pips_per_trade"] = round(float(np.mean([
            (1 if t["direction"] == "MULTUP" else -1) * (t["exit"] - t["entry"]) / fills.PIP[t["symbol"]]
            + fills.ENTRY_SLIPPAGE_PIPS + (fills.SL_SLIPPAGE_PIPS if t["reason"] == "stop_loss" else 0)
            for t in tr])), 2)
        out[name] = row
        print(f"{name:28s} trades {row['trades']:5d} gross {row['gross']:8.2f} net {row['net']:8.2f} "
              f"commission {row['commission']:7.2f} slippage {row['entry_slippage'] + row['sl_slippage']:6.2f} "
              f"gross pips/trade {row['gross_pips_per_trade']:6.2f}")
    # Engine cross-check: the same schedules run with zero costs. The two gross figures differ
    # only through stake sizes (the balance path) and stop levels shifted by the 0.5 pip entry
    # slippage, so they should be close; a cost charged twice would show as a gap of about one
    # commission per trade.
    for name in GROSSNET_ENGINE_CHECK:
        cls, sched = REGISTRY[name], schedule_of(name)
        with audit.no_costs():
            eng = R.run_oos(R.Scheduled(cls, sched))
        tr = eng.state.trades
        ref = out[name]
        rep = {"engine_trades": len(tr), "engine_gross": net(tr),
               "engine_gross_per_unit_stake": round(sum(t["profit"] / t["stake"] for t in tr), 3),
               "repriced_gross_per_unit_stake": round(sum(audit.gross_of(t) / t["stake"] for t in read_trades(name)), 3),
               "commission_per_trade": round(ref["commission"] / ref["trades"], 4),
               "zero_commission_recorded": all(t["commission"] == 0 for t in tr)}
        rep["gap_per_trade"] = round((rep["engine_gross"] - ref["gross"]) / ref["trades"], 4)
        out[name]["engine_no_cost_check"] = rep
        print(name, "engine no-cost run:", rep)
    save("grossnet", out)


# ----------------------------------------------------------------------------- flip
FLIP = ("f5_session_drift", "f1_london_breakout", "f8_morning_momentum", "f3_trend_pullback")


def _flip_run(job):
    name, flip, costs = job
    cls = REGISTRY[name]
    if flip:
        cls = audit.flipped(cls)
    if costs:
        eng = R.run_oos(R.Scheduled(cls, schedule_of(name)))
    else:
        with audit.no_costs():
            eng = R.run_oos(R.Scheduled(cls, schedule_of(name)))
    tr = eng.state.trades
    return {"family": name, "flipped": flip, "costs": costs, "trades": len(tr), "net": net(tr),
            "per_unit_stake": round(sum(t["profit"] / t["stake"] for t in tr), 3),
            "kill_events": len(eng.state.kill_events),
            "exit_reasons": dict(Counter(t["reason"] for t in tr))}


def stage_flip():
    for tf in {REGISTRY[n].timeframe for n in FLIP}:
        R.market_data(tf, *_oos_load_span(tf))
    jobs = [(n, f, c) for n in FLIP for c in (False, True) for f in (False, True)]
    with mp.get_context("fork").Pool(4) as pool:
        res = pool.map(_flip_run, jobs)
    out = {}
    for r in res:
        key = f"{'with' if r['costs'] else 'no'}_costs_{'flipped' if r['flipped'] else 'original'}"
        out.setdefault(r["family"], {})[key] = r
        print(r)
    for name, d in out.items():
        a, b = d["no_costs_original"], d["no_costs_flipped"]
        d["mirror_before_costs"] = {"original_per_unit_stake": a["per_unit_stake"],
                                    "flipped_per_unit_stake": b["per_unit_stake"],
                                    "sum (0 = exact mirror)": round(a["per_unit_stake"] + b["per_unit_stake"], 3)}
    save("flip", out)


def _oos_load_span(tf):
    v0, v1 = R.oos_span()
    warm = max([getattr(REGISTRY[n], "warmup_days", R.WARMUP_DAYS) for n in OOS_NAMES if REGISTRY[n].timeframe == tf]
               + [R.WARMUP_DAYS])
    return v0 - dt.timedelta(days=warm), v1


# ----------------------------------------------------------------------------- luck preview
def _luck_job(job):
    name, sched, rates, seed = job
    cls = REGISTRY[name]
    eng = R.run_oos(R.RandomEntry(cls, sched, rates, seed))
    tr = eng.state.trades
    out = {"seed": seed, "trades": len(tr), "net_profit": net(tr), "kill_events": len(eng.state.kill_events)}
    p = STATE / name / f"s{seed:03d}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out))
    return out


def stage_luck_preview(family: str, runs: int, budget_s: float, t0: float):
    """The luck check with the corrected signal rates, at a reduced number of runs. A preview
    for the audit report, NOT an official re-run: committed luck.json files are untouched."""
    for name, _ in R.FAMILIES[family]:
        cls, sched = REGISTRY[name], schedule_of(name)
        rates_path = STATE / name / "rates.json"
        if rates_path.exists():
            saved = json.loads(rates_path.read_text())
            rates, cand = {tuple(k): v for k, v in saved["rates"]}, saved["candidate"]
        else:
            R.market_data(cls.timeframe, *_oos_load_span(cls.timeframe))
            s = R.Scheduled(cls, sched)
            eng = R.run_oos(s)
            rates = R.entry_rates(s)
            cand = {"trades": len(eng.state.trades), "net_profit": net(eng.state.trades),
                    "flat_candles": sum(s.flat.values()), "entry_signals": sum(s.entries.values())}
            rates_path.parent.mkdir(parents=True, exist_ok=True)
            rates_path.write_text(json.dumps({"rates": [[list(k), v] for k, v in rates.items()], "candidate": cand}))
        jobs = [(name, sched, rates, seed) for seed in range(runs) if not (STATE / name / f"s{seed:03d}.json").exists()]
        if jobs:
            R.market_data(cls.timeframe, *_oos_load_span(cls.timeframe))
            ctx = mp.get_context("fork")
            with ctx.Pool(3) as pool:
                pending, running, done = list(jobs), [], 0
                while pending or running:
                    while pending and len(running) < 3 and time.time() - t0 < budget_s:
                        running.append(pool.apply_async(_luck_job, (pending.pop(0),)))
                    if not running:
                        break
                    for r in list(running):
                        if r.ready():
                            r.get(); running.remove(r); done += 1
                    time.sleep(0.5)
            if pending:
                print(f"{name}: {done} runs done now, {len(pending)} left; run again to continue")
                return False
        res = sorted((json.loads((STATE / name / f"s{s:03d}.json").read_text()) for s in range(runs)
                      if (STATE / name / f"s{s:03d}.json").exists()), key=lambda r: r["seed"])
        pct, need = R.luck_rule(family)
        nets = [r["net_profit"] for r in res]
        old = json.loads((ROOT / "research" / "phase4" / name / "luck.json").read_text())
        old_nets = [r["net_profit"] for r in old]
        summary = {
            "sub_grid": name, "candidate": cand, "rule": {"percentile": pct, "runs_required": need},
            "preview_runs": len(res), "preview_is_official": False,
            "corrected": {"random_trades_mean": round(float(np.mean([r["trades"] for r in res])), 1),
                          "random_trades_min_max": [min(r["trades"] for r in res), max(r["trades"] for r in res)],
                          "random_net_mean": round(float(np.mean(nets)), 2),
                          **R.luck_result(nets, cand["net_profit"], pct, len(res))},
            "committed_before_fix": {"runs": len(old), "random_trades_mean": round(float(np.mean([r["trades"] for r in old])), 1),
                                     "random_net_mean": round(float(np.mean(old_nets)), 2),
                                     **R.luck_result(old_nets, cand["net_profit"], pct, need)},
        }
        print(json.dumps(summary, indent=1))
        save(f"luck_preview_{name}", summary)
    return True


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("stage", choices=("trades", "utc", "cheat", "grossnet", "flip", "luck-preview"))
    p.add_argument("--family", choices=sorted(R.FAMILIES))
    p.add_argument("--runs", type=int, default=100)
    p.add_argument("--max-minutes", type=float, default=8.5)
    a = p.parse_args()
    t0 = time.time()
    ok = True
    if a.stage == "trades":
        stage_trades()
    elif a.stage == "utc":
        stage_utc()
    elif a.stage == "cheat":
        stage_cheat(a.runs if a.runs != 100 else 20)
    elif a.stage == "grossnet":
        stage_grossnet()
    elif a.stage == "flip":
        stage_flip()
    else:
        if not a.family:
            raise SystemExit("--family is required for luck-preview")
        ok = stage_luck_preview(a.family, a.runs, a.max_minutes * 60, t0)
    print(f"({time.time() - t0:.0f}s)")
    return 0 if ok else 2


if __name__ == "__main__":
    sys.exit(main())
