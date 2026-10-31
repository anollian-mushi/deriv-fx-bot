"""Weekly leaderboard from incubator/records/index.json (Telegram text and leaderboard.md).

Column meanings are explained in incubator/README.md.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from fxbot.incubator import exam
from fxbot.incubator.daily import PAIR, records_dir
from fxbot.incubator.registry import INCUBATOR

ORDER = {"graduated": 0, "active": 1, "waiting": 2, "dead": 3, "tampered": 4}


def _rows(index: dict) -> list[tuple[str, dict]]:
    rows = list(index.get("candidates", {}).items())
    return sorted(rows, key=lambda kv: (ORDER.get(kv[1]["status"], 9),
                                        -(kv[1].get("measured", {}).get("net_profit") or 0.0)))


def _fmt(v, spec: str, none: str = "-") -> str:
    return none if v is None else format(v, spec)


def _exam_text(e: dict | None) -> str:
    if not e:
        return "not started"
    if "passed" not in e:
        return f"running {e['runs_done']}/{e['runs_needed']} (attempt {e['attempt']})"
    return (f"{'PASSED' if e['passed'] else 'failed'} attempt {e['attempt']} "
            f"(beat {e['share_beaten'] * 100:.1f}% of random runs)")


def _todo(r: dict) -> str:
    rules = r.get("rules", {})
    m = r["measured"]
    need = []
    if not rules.get("days"):
        need.append(f"days {r['forward_days']}/{exam.MIN_DAYS}")
    if not rules.get("trades"):
        need.append(f"trades {m['trades']}/{exam.MIN_TRADES}")
    if not rules.get("net_measured"):
        need.append("net > 0")
    if not rules.get("net_1_5x"):
        need.append("net at 1.5x > 0")
    if not rules.get("max_drawdown"):
        need.append(f"DD < {exam.MAX_DD_PCT:.0f}%")
    return "still needs: " + ", ".join(need) if need else "rules 1-3 met"


def telegram_text(index: dict, today: dt.date) -> str:
    lines = [f"Incubator leaderboard {today} (paper only)", f"Data up to {index.get('data_end')}.", ""]
    for i, (cid, r) in enumerate(_rows(index), 1):
        lines.append(f"{i}. {cid} [{r['status'].upper()}]")
        if "measured" not in r:
            lines.append(f"   scoring starts {r['first_scored_day']}" if r["status"] == "waiting" else "   no record")
            lines.append("")
            continue
        m = r["measured"]
        lines.append(f"   {r['forward_days']}d  {m['trades']} trades  open {m['open_trades']}")
        lines.append(f"   Net {m['net_profit']:+.2f}  Net1.5x {r['stress_net']:+.2f}  DD {m['max_drawdown_pct']:.1f}%")
        lines.append(f"   Win {_fmt(m['win_rate_pct'], '.0f')}%  PF {_fmt(m['profit_factor'], '.2f')}  "
                     f"AvgW {_fmt(m['avg_win'], '.2f')}  AvgL {_fmt(m['avg_loss'], '.2f')}")
        lines.append("   " + "  ".join(f"{PAIR[s][:3]}{PAIR[s][4:]} {v['net']:+.2f}" for s, v in m["per_pair"].items()))
        if r["status"] == "dead":
            lines.append("   kill switch fired: out for good")
        else:
            lines.append("   " + _todo(r))
        lines.append("   exam: " + _exam_text(r.get("exam")))
        lines.append("")
    lines.append("Columns: see incubator/README.md. Net in USD from 100 USD paper.")
    return "\n".join(lines)


def markdown(index: dict, today: dt.date) -> str:
    out = [f"# Incubator leaderboard ({today})", "",
           f"Paper only. Forward Deriv data up to {index.get('data_end')}. Starting balance 100 USD per candidate.",
           "Column meanings: [README](README.md#reading-the-leaderboard).", "",
           "| # | Candidate | Status | Days | Trades | Open | Net | Net 1.5x | Max DD | Win % | PF | Avg win | Avg loss "
           "| EUR/USD | GBP/USD | USD/JPY | Exam |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, (cid, r) in enumerate(_rows(index), 1):
        if "measured" not in r:
            out.append(f"| {i} | {cid} | {r['status']} |" + " - |" * 13 + f" scoring from {r['first_scored_day']} |")
            continue
        m = r["measured"]
        pp = [f"{m['per_pair'][s]['net']:+.2f} ({m['per_pair'][s]['trades']})" for s in PAIR]
        out.append(f"| {i} | {cid} | {r['status']} | {r['forward_days']} | {m['trades']} | {m['open_trades']} "
                   f"| {m['net_profit']:+.2f} | {r['stress_net']:+.2f} | {m['max_drawdown_pct']:.1f}% "
                   f"| {_fmt(m['win_rate_pct'], '.0f')} | {_fmt(m['profit_factor'], '.2f')} "
                   f"| {_fmt(m['avg_win'], '.2f')} | {_fmt(m['avg_loss'], '.2f')} | {' | '.join(pp)} "
                   f"| {_exam_text(r.get('exam'))} |")
    out += ["", f"Engine fingerprint: `{(index.get('engine_fingerprint') or '')[:16]}` (changes if the engine, risk limits "
            "or cost table change)."]
    return "\n".join(out) + "\n"


def build(root: Path = INCUBATOR, today: dt.date | None = None) -> tuple[str, str]:
    today = today or dt.datetime.now(dt.timezone.utc).date()
    p = records_dir(root) / "index.json"
    index = json.loads(p.read_text()) if p.exists() else {"candidates": {}, "data_end": None}
    return telegram_text(index, today), markdown(index, today)
