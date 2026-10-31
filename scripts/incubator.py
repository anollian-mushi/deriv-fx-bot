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
import json
import sys

import _bootstrap  # noqa: F401

from fxbot.incubator import registry


def cmd_register(a) -> int:
    c = registry.register(a.id, a.module, a.cls, json.loads(a.params), a.model_file or [],
                          notes=a.notes, origin=json.loads(a.origin) if a.origin else None)
    print(f"registered {c.id} on {c.manifest['registered']} (first scored day "
          f"{c.manifest['first_scored_day']}), fingerprint {c.fingerprint}")
    return 0


def cmd_verify(a) -> int:
    status = registry.verify_all()
    for cid, s in status.items():
        print(f"{cid}: {s}")
    return 0 if all(s == "ok" for s in status.values()) else 1


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
    r.set_defaults(func=cmd_register)
    sub.add_parser("verify").set_defaults(func=cmd_verify)
    a = p.parse_args(argv)
    return a.func(a)


if __name__ == "__main__":
    sys.exit(main())
