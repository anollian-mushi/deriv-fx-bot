"""The daily incubator run: verify, replay every candidate forward, run graduation exams.

Writes incubator/records/<id>/ (summary.json, trades.csv, equity.csv,
signals.json, state.json, exam files) and incubator/records/index.json, and
returns the Telegram notices for the day. Paper only.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import traceback
from pathlib import Path

from fxbot.incubator import exam
from fxbot.incubator import forward as fw
from fxbot.incubator.registry import INCUBATOR, TamperedError, candidates, verify

PAIR = {"frxEURUSD": "EUR/USD", "frxGBPUSD": "GBP/USD", "frxUSDJPY": "USD/JPY"}


def records_dir(root: Path = INCUBATOR) -> Path:
    return root / "records"


def _load(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def _save(p: Path, obj) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True) + "\n")
    tmp.replace(p)


def per_pair_lines(summary: dict) -> list[str]:
    out = []
    for key, label in (("measured", "measured commission"), ("stress_1_5x", "1.5x commission")):
        out.append(f"Per pair, {label}:")
        for s, v in summary[key]["per_pair"].items():
            out.append(f"  {PAIR[s]}: {v['trades']} trades, {v['wins']} wins, net {v['net']:+.2f} USD")
    return out


def graduation_message(cid: str, st: dict) -> str:
    s, r = st["summary_at_cutoff"], st["result"]
    m, x = s["measured"], s["stress_1_5x"]
    lines = [
        f"GRADUATED: {cid}",
        f"Forward data {s['first_scored_day']} to {st['cutoff']} ({s['forward_days']} days). Paper only: nothing was traded.",
        "",
        f"Trades {m['trades']}, net {m['net_profit']:+.2f} USD at measured commission, "
        f"{x['net_profit']:+.2f} USD at 1.5x.",
        f"Max drawdown {m['max_drawdown_pct']}%, kill switch never fired, win rate {m['win_rate_pct']}%, "
        f"profit factor {m['profit_factor']}.",
        f"Luck check: beat {r['share_beaten'] * 100:.2f}% of {r['runs']} random-direction runs "
        f"(bar: {r['percentile']}th percentile = {r['bar']:+.2f} USD, N = {st['N']}).",
        "",
        *per_pair_lines(s),
        "",
        "What to do next (see incubator/README.md, 'If something graduates'):",
        "1. Do NOT put real money on it. Graduation means 'worth a closer look', not proof.",
        "2. Read incubator/records/" + cid + "/ (trades.csv, summary.json, exam.json).",
        "3. If profit comes from one pair or a few big trades, be extra sceptical.",
        "4. With help (a developer or AI), plan a Phase 5 demo-account test of this exact frozen candidate.",
        "5. Real money only after a demo period, and only by you setting DERIV_MODE=real yourself.",
    ]
    return "\n".join(lines)


def exam_failed_message(cid: str, st: dict) -> str:
    r = st["result"]
    nxt = dt.date.fromisoformat(st["cutoff"]) + dt.timedelta(days=exam.RETAKE_DAYS)
    return (f"Exam not passed: {cid} (attempt {st['attempt']}, data to {st['cutoff']}).\n"
            f"Its net {r['candidate_net']:+.2f} USD beat {r['share_beaten'] * 100:.2f}% of {r['runs']} random-direction "
            f"runs; it needed to beat the {r['percentile']}th percentile ({r['bar']:+.2f} USD).\n"
            f"In plain words: its results are not clearly better than coin tosses on the same days.\n"
            f"It keeps running. A retake is allowed with data up to {nxt} or later, if rules 1-3 still hold.")


def run_daily(root: Path = INCUBATOR, data_dir: Path = fw.DATA, exam_budget_s: float = 1500.0,
              workers: int | None = None, now: dt.datetime | None = None) -> dict:
    """One daily run. Returns {"notices": [...], "problems": [...], "index": {...}}."""
    now = now or dt.datetime.now(dt.timezone.utc)
    t_start = time.time()
    notices, problems = [], []
    end = fw.latest_complete_day(data_dir)
    index = {"run_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "data_end": end.isoformat() if end else None,
             "engine_fingerprint": fw.engine_fingerprint(), "candidates": {}}
    cache: dict = {}
    for c in candidates(root):                      # raises TamperedError if the registry chain broke
        rec = records_dir(root) / c.id
        state = _load(rec / "state.json", {"status": "waiting"})
        row = {"registered": c.manifest.get("registered"), "first_scored_day": c.first_day.isoformat()}
        try:
            verify(c)
        except TamperedError as err:
            state["status"] = "tampered"
            problems.append(f"TAMPERED: {err}. This candidate is skipped until its files are restored "
                            "exactly (git checkout of its folder).")
            _save(rec / "state.json", state)
            index["candidates"][c.id] = {**row, "status": "tampered"}
            continue
        if end is None or end < c.first_day:
            state["status"] = "waiting"
            _save(rec / "state.json", state)
            index["candidates"][c.id] = {**row, "status": "waiting"}
            continue
        try:
            res = fw.evaluate(c, end, cache)
        except Exception as err:
            problems.append(f"{c.id}: replay failed: {type(err).__name__}: {err}")
            traceback.print_exc()
            index["candidates"][c.id] = {**row, "status": state.get("status", "error"), "error": str(err)}
            continue
        fw.write_record(rec, res)
        summary = {k: v for k, v in res.items() if not k.startswith("_")}
        signals = fw.entry_signals(res["_engines"][0])
        if summary["measured"]["kill_switch_fired"] and state.get("status") != "dead":
            state["status"] = "dead"
            state["dead_since"] = end.isoformat()
            notices.append(f"Kill switch fired (paper): {c.id}. Its paper equity fell to half the starting "
                           f"100 USD. It is out for good and can never graduate. Nothing to do.")
        elif state.get("status") not in ("dead", "graduated"):
            state["status"] = "active"

        st = exam.load_exam(rec)
        if state["status"] == "active":
            ok, why = exam.can_start(c, summary, rec, root)
            state["exam_check"] = why
            if ok:
                st = exam.start(c, summary, signals, rec, root, now)
                notices.append(f"Exam started: {c.id} met rules 1-3 with data to {st['cutoff']} "
                               f"({summary['measured']['trades']} trades, net {summary['measured']['net_profit']:+.2f} USD). "
                               f"Now running {st['runs_needed']} random-direction runs (N = {st['N']}); "
                               f"this can take a few days.")
        if st and "result" not in st:
            left = exam_budget_s - (time.time() - t_start)
            if left > 60 and exam.advance(c, st, rec, left, workers):
                st = exam.finish(c, st, rec, root, now)
                if st["result"]["passed"]:
                    state["status"] = "graduated"
                    state["graduated_on"] = st["cutoff"]
                    notices.append(graduation_message(c.id, st))
                else:
                    notices.append(exam_failed_message(c.id, st))
        _save(rec / "state.json", state)
        index["candidates"][c.id] = {
            **row, "status": state["status"], "forward_days": summary["forward_days"],
            "measured": {k: summary["measured"][k] for k in ("trades", "open_trades", "net_profit", "max_drawdown_pct",
                                                             "win_rate_pct", "avg_win", "avg_loss", "profit_factor",
                                                             "kill_switch_fired", "per_pair")},
            "stress_net": summary["stress_1_5x"]["net_profit"],
            "rules": {k: v["ok"] for k, v in exam.rules_1_to_3(summary).items()},
            "exam": _exam_row(st),
        }
    _save(records_dir(root) / "index.json", index)
    return {"notices": notices, "problems": problems, "index": index}


def _exam_row(st: dict | None) -> dict | None:
    if not st:
        return None
    row = {"attempt": st["attempt"], "cutoff": st["cutoff"], "N": st["N"], "runs_done": len(st["nets"]),
           "runs_needed": st["runs_needed"]}
    if "result" in st:
        row.update(passed=st["result"]["passed"], share_beaten=st["result"]["share_beaten"])
    return row
