"""Graduation exam (CLAUDE.md, Strategy incubator, graduation rule; fixed 31 Oct 2026).

All must hold on forward data up to the exam cutoff day:
1. at least 90 calendar days of forward data and at least 100 closed trades;
2. net profit above zero at the measured commission and at 1.5x;
3. max drawdown under 25% at the measured commission, kill switch never fired;
4. luck check: net profit at the measured commission beats the (1 - 0.05/N)
   percentile of random-direction runs on the candidate's own forward signal
   days. N = candidates ever registered + exam attempts ever started (all
   candidates, counting this one). Runs: max(2000, ceil(20 N / 0.05)), so
   at least 20 random runs lie beyond the bar.

An exam starts on the first daily run where 1-3 hold; the cutoff (the newest
data day then) is frozen. The random runs are spread over as many daily runs
as needed and resume from incubator/records/<id>/exam.json. A failed exam
can be retaken only with a cutoff at least 28 days after the previous one.
Every start and every result is appended to incubator/exams.json, a hash
chain like the registry, so the count behind N cannot quietly shrink.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

from fxbot.incubator import forward as fw
from fxbot.incubator.registry import INCUBATOR, Candidate, append_chain, candidates, exams_path, load_strategy, read_chain

ALPHA = 0.05
MIN_RUNS = 2000
BEYOND = 20                 # random runs that must lie beyond the bar
MIN_DAYS = 90
MIN_TRADES = 100
MAX_DD_PCT = 25.0
RETAKE_DAYS = 28
SAVE_EVERY = 50


# ----------------------------------------------------------------------------- the numbers
def n_for_next_exam(root: Path = INCUBATOR) -> int:
    starts = [e for e in read_chain(exams_path(root)) if e["event"] == "start"]
    return len(candidates(root)) + len(starts) + 1


def runs_needed(n: int) -> int:
    return max(MIN_RUNS, math.ceil(BEYOND * n / ALPHA - 1e-9))


def bar_percentile(n: int) -> float:
    return 100.0 * (1.0 - ALPHA / n)


def rules_1_to_3(summary: dict) -> dict[str, dict]:
    """Each rule: {"ok": bool, "value": ..., "need": ...}."""
    m, s = summary["measured"], summary["stress_1_5x"]
    return {
        "days": {"ok": summary["forward_days"] >= MIN_DAYS, "value": summary["forward_days"], "need": f">= {MIN_DAYS}"},
        "trades": {"ok": m["trades"] >= MIN_TRADES, "value": m["trades"], "need": f">= {MIN_TRADES}"},
        "net_measured": {"ok": m["net_profit"] > 0, "value": m["net_profit"], "need": "> 0"},
        "net_1_5x": {"ok": s["net_profit"] > 0, "value": s["net_profit"], "need": "> 0"},
        "max_drawdown": {"ok": m["max_drawdown_pct"] < MAX_DD_PCT, "value": m["max_drawdown_pct"],
                         "need": f"< {MAX_DD_PCT}%"},
        "kill_switch": {"ok": not m["kill_switch_fired"], "value": m["kill_switch_fired"], "need": "never fired"},
    }


def luck_verdict(nets, candidate_net: float, n: int) -> dict:
    nets = np.asarray(nets, dtype=float)
    pct = bar_percentile(n)
    bar = float(np.percentile(nets, pct))
    return {"runs": int(len(nets)), "percentile": round(pct, 4), "bar": round(bar, 2),
            "candidate_net": candidate_net, "beyond_bar": int((nets > bar).sum()),
            "share_beaten": round(float((nets < candidate_net).mean()), 5),
            "median": round(float(np.median(nets)), 2),
            "passed": bool(len(nets) >= runs_needed(n) and candidate_net > bar)}


# ----------------------------------------------------------------------------- exam state
def exam_file(rec_dir: Path) -> Path:
    return rec_dir / "exam.json"


def load_exam(rec_dir: Path) -> dict | None:
    p = exam_file(rec_dir)
    return json.loads(p.read_text()) if p.exists() else None


def save_exam(rec_dir: Path, st: dict) -> None:
    rec_dir.mkdir(parents=True, exist_ok=True)
    tmp = exam_file(rec_dir).with_suffix(".tmp")
    tmp.write_text(json.dumps(st, indent=1) + "\n")
    tmp.replace(exam_file(rec_dir))


def past_attempts(cid: str, root: Path = INCUBATOR) -> list[dict]:
    return [e for e in read_chain(exams_path(root)) if e["id"] == cid and e["event"] == "start"]


def can_start(c: Candidate, summary: dict, rec_dir: Path, root: Path = INCUBATOR) -> tuple[bool, str]:
    st = load_exam(rec_dir)
    if st and "result" not in st:
        return False, "exam in progress"
    if st and st["result"]["passed"]:
        return False, "graduated"
    rules = rules_1_to_3(summary)
    if not all(r["ok"] for r in rules.values()):
        return False, "rules 1-3 not met: " + ", ".join(k for k, r in rules.items() if not r["ok"])
    prev = past_attempts(c.id, root)
    if prev:
        last = dt.date.fromisoformat(prev[-1]["cutoff"])
        cutoff = dt.date.fromisoformat(summary["data_end"])
        if cutoff < last + dt.timedelta(days=RETAKE_DAYS):
            return False, f"retake allowed from cutoff {last + dt.timedelta(days=RETAKE_DAYS)}"
    return True, "ok"


def start(c: Candidate, summary: dict, signals: list, rec_dir: Path, root: Path = INCUBATOR,
          now: dt.datetime | None = None) -> dict:
    n = n_for_next_exam(root)
    attempt = len(past_attempts(c.id, root)) + 1
    cutoff = summary["data_end"]
    seed = int(hashlib.sha256(f"{c.id}|{c.fingerprint}|{cutoff}|{attempt}".encode()).hexdigest()[:8], 16)
    now = now or dt.datetime.now(dt.timezone.utc)
    entry = {"event": "start", "id": c.id, "attempt": attempt, "cutoff": cutoff, "N": n,
             "runs_needed": runs_needed(n), "percentile": round(bar_percentile(n), 4),
             "candidate_net": summary["measured"]["net_profit"], "started": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    append_chain(exams_path(root), entry)
    st = {**entry, "seed": seed, "signals": signals, "nets": [], "summary_at_cutoff": summary}
    save_exam(rec_dir, st)
    return st


# ----------------------------------------------------------------------------- random runs
_W: dict = {}


def _init_worker(c: Candidate, cutoff: str, signals: list) -> None:
    _W["c"], _W["signals"] = c, signals
    _W["data"] = fw.forward_data(c, dt.date.fromisoformat(cutoff))


def _one_run(seed: int) -> float:
    c = _W["c"]
    s = fw.CoinToss(load_strategy(c, check=False), c.start_epoch, _W["signals"], seed, c.legs)
    return fw.net_profit(fw.run(c, _W["data"], strategy=s))


def advance(c: Candidate, st: dict, rec_dir: Path, budget_s: float, workers: int | None = None) -> bool:
    """Add random runs until enough or the time budget is used. True when complete."""
    t0 = time.time()
    need = st["runs_needed"]
    workers = workers or max(1, min(4, os.cpu_count() or 1))
    if len(st["nets"]) >= need:
        return True
    if workers == 1:
        _init_worker(c, st["cutoff"], st["signals"])
        while len(st["nets"]) < need and time.time() - t0 < budget_s:
            st["nets"].append(_one_run(st["seed"] + len(st["nets"])))
            if len(st["nets"]) % SAVE_EVERY == 0:
                save_exam(rec_dir, st)
    else:
        with ProcessPoolExecutor(workers, initializer=_init_worker,
                                 initargs=(c, st["cutoff"], st["signals"])) as pool:
            while len(st["nets"]) < need and time.time() - t0 < budget_s:
                k = len(st["nets"])
                batch = range(k, min(need, k + SAVE_EVERY * workers // 2))
                st["nets"].extend(pool.map(_one_run, [st["seed"] + i for i in batch]))
                save_exam(rec_dir, st)
    save_exam(rec_dir, st)
    return len(st["nets"]) >= need


def finish(c: Candidate, st: dict, rec_dir: Path, root: Path = INCUBATOR,
           now: dt.datetime | None = None) -> dict:
    v = luck_verdict(st["nets"], st["candidate_net"], st["N"])
    now = now or dt.datetime.now(dt.timezone.utc)
    st["result"] = {**v, "finished": now.strftime("%Y-%m-%dT%H:%M:%SZ")}
    append_chain(exams_path(root), {"event": "result", "id": c.id, "attempt": st["attempt"], "cutoff": st["cutoff"],
                                    "N": st["N"], **{k: v[k] for k in ("runs", "percentile", "bar", "candidate_net",
                                                                         "beyond_bar", "passed")}})
    save_exam(rec_dir, st)
    history = rec_dir / "exam_history.json"
    past = json.loads(history.read_text()) if history.exists() else []
    past.append({k: st[k] for k in ("attempt", "cutoff", "N", "runs_needed", "percentile", "candidate_net", "result")})
    history.write_text(json.dumps(past, indent=1) + "\n")
    return st
