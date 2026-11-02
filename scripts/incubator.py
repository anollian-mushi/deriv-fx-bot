"""Strategy incubator command line (paper only; never places orders).

    python scripts/incubator.py register --id ID --module families|ml_day --class NAME \
        --params '{"a": 1}' [--model-file PATH] [--notes TEXT]
    python scripts/incubator.py verify          # every candidate exactly as registered?
    python scripts/incubator.py daily           # forward replay + graduation exams (Actions)
    python scripts/incubator.py weekly          # leaderboard to Telegram (Actions, Mondays)
    python scripts/incubator.py watchdog        # stale-run check (Actions, daily)
    python scripts/incubator.py notify --text T # send one Telegram message

See incubator/README.md.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys

import _bootstrap  # noqa: F401

from fxbot.incubator import registry


def cmd_register(a) -> int:
    c = registry.register(a.id, a.module, a.cls, json.loads(a.params), a.model_file or [],
                          notes=a.notes, origin=json.loads(a.origin) if a.origin else None,
                          symbols=tuple(a.symbols or registry.DEFAULT_SYMBOLS),
                          cost_table=a.cost_table or registry.DEFAULT_COST_TABLE)
    print(f"registered {c.id} on {c.manifest['registered']} (first scored day "
          f"{c.manifest['first_scored_day']}), fingerprint {c.fingerprint}")
    return 0


def cmd_verify(a) -> int:
    status = registry.verify_all()
    for cid, s in status.items():
        print(f"{cid}: {s}")
    return 0 if all(s == "ok" for s in status.values()) else 1


def _send(text: str, pre: bool = False) -> bool:
    from fxbot.incubator import notify
    try:
        notify.send(text, pre=pre)
        return True
    except notify.NotifyError as err:
        print(f"::warning::Telegram: {err}")
        print(text)
        return False


def cmd_daily(a) -> int:
    from fxbot.incubator.daily import run_daily
    out = run_daily(exam_budget_s=a.exam_minutes * 60, workers=a.workers or None)
    idx = out["index"]
    print(f"data up to {idx['data_end']}")
    for cid, r in idx["candidates"].items():
        m = r.get("measured", {})
        print(f"{cid}: {r['status']} trades={m.get('trades')} net={m.get('net_profit')} exam={r.get('exam')}")
    for text in out["notices"]:
        _send(text)
    if out["problems"]:
        _send("Incubator daily run found problems:\n" + "\n".join(out["problems"]))
        for p in out["problems"]:
            print(f"::error::{p}")
        return 1
    return 0


def cmd_weekly(a) -> int:
    from fxbot.incubator.leaderboard import build
    from fxbot.incubator.registry import INCUBATOR
    text, md = build()
    (INCUBATOR / "leaderboard.md").write_text(md)
    print(text)
    return 0 if _send(text, pre=True) or a.no_fail else 1


def cmd_watchdog(a) -> int:
    from fxbot.incubator.watchdog import check
    alerts = check(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"])
    for text in alerts:
        print(f"::warning::{text}")
    if alerts:
        return 0 if _send("\n\n".join(alerts)) else 1
    print("all scheduled jobs ran recently")
    return 0


def cmd_notify(a) -> int:
    return 0 if _send(a.text) else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("register", help="register a new candidate (today's UTC date)")
    r.add_argument("--id", required=True)
    r.add_argument("--module", required=True, choices=[m[:-3] for m in registry.FROZEN_MODULES])
    r.add_argument("--class", dest="cls", required=True)
    r.add_argument("--params", required=True, help="JSON object")
    r.add_argument("--model-file", action="append")
    r.add_argument("--notes", default="")
    r.add_argument("--origin", default="", help="JSON object: where the idea came from")
    r.add_argument("--symbols", nargs="+", help="pairs the candidate trades (default: the three majors)")
    r.add_argument("--cost-table", help="commission table it is replayed with (default: research/phase2/cost_by_hour.json)")
    r.set_defaults(func=cmd_register)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    d = sub.add_parser("daily", help="forward replay of every candidate + graduation exams")
    d.add_argument("--exam-minutes", type=float, default=25.0, help="time budget for exam random runs")
    d.add_argument("--workers", type=int, default=0, help="processes for exam runs (0 = up to 4)")
    d.set_defaults(func=cmd_daily)
    w = sub.add_parser("weekly", help="write incubator/leaderboard.md and send it to Telegram")
    w.add_argument("--no-fail", action="store_true", help="exit 0 even if Telegram fails")
    w.set_defaults(func=cmd_weekly)
    sub.add_parser("watchdog", help="alert if a scheduled job has not succeeded recently").set_defaults(func=cmd_watchdog)
    n = sub.add_parser("notify", help="send one Telegram message")
    n.add_argument("--text", required=True)
    n.set_defaults(func=cmd_notify)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
