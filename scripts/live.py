"""Live bot command line (see deploy/DEPLOY.md).

    python scripts/live.py run [--dry-run] [--hours H]   start the bot (systemd runs this)
    python scripts/live.py check                         settings, candidate and mode, no trading
    python scripts/live.py status                        print BOT_HOME/status.json and heartbeat age
    python scripts/live.py leader                        which candidate leads the incubator
    python scripts/live.py test-trade --symbol frxEURUSD --direction MULTUP [--hold-minutes 10]
                                                         ask the RUNNING bot for one forced test trade
                                                         (demo only; passes the risk module and cost gate)
    python scripts/live.py unhalt                        clear a HALT (kill switch or /stop); restart after
    python scripts/live.py export [--days 7]             write the journal as CSV files into reviews/
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import _bootstrap  # noqa: F401

from fxbot.live import candidate as cand
from fxbot.live.settings import load_live_settings


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--dry-run", action="store_true")
    r.add_argument("--hours", type=float)
    sub.add_parser("check")
    sub.add_parser("status")
    sub.add_parser("leader")
    t = sub.add_parser("test-trade")
    t.add_argument("--symbol", default="frxEURUSD", choices=["frxEURUSD", "frxGBPUSD", "frxUSDJPY"])
    t.add_argument("--direction", default="MULTUP", choices=["MULTUP", "MULTDOWN"])
    t.add_argument("--hold-minutes", type=int, default=10)
    t.add_argument("--sl-pips", type=float, default=10.0)
    t.add_argument("--tp-pips", type=float, default=10.0)
    sub.add_parser("unhalt")
    e = sub.add_parser("export")
    e.add_argument("--days", type=float, default=7)
    a = ap.parse_args()
    ls = load_live_settings()

    if a.cmd == "run":
        from fxbot.live.main import run
        return run(a.dry_run, a.hours)
    if a.cmd == "check":
        from fxbot.live.main import ModeError, decide_mode
        print("Settings:", json.dumps(ls.base.summary()))
        cid, how = cand.resolve_id(ls.strategy_id, ls.leader_fallback)
        c, s = cand.load(cid)
        print(f"Candidate: {cid} (chosen by {how}), fingerprint {c.fingerprint[:16]} OK, "
              f"timeframe {s.timeframe}, graduated: {cand.is_graduated(cid)}")
        try:
            print("Mode:", decide_mode(ls, cand.is_graduated(cid)))
        except ModeError as err:
            print("Mode: REFUSED:", err)
            return 2
        print("BOT_HOME:", ls.home, "| HALT:", ls.halt_path.read_text().strip() if ls.halt_path.exists() else "no")
        return 0
    if a.cmd == "status":
        st = json.loads(ls.status_path.read_text()) if ls.status_path.exists() else {}
        hb = int(ls.heartbeat_path.read_text()) if ls.heartbeat_path.exists() else None
        print(json.dumps(st, indent=1))
        print("heartbeat age:", f"{time.time() - hb:.0f} s" if hb else "none")
        return 0
    if a.cmd == "leader":
        lid = cand.leader_id()
        print(lid or f"No active candidate yet; STRATEGY_ID=leader would use {ls.leader_fallback}")
        return 0
    if a.cmd == "test-trade":
        if ls.base.deriv_mode != "demo":
            print("Test trades are demo only.")
            return 2
        ls.requests_dir.mkdir(parents=True, exist_ok=True)
        req = {"symbol": a.symbol, "direction": a.direction, "multiplier": 100, "hold_minutes": a.hold_minutes,
               "sl_pips": a.sl_pips, "tp_pips": a.tp_pips}
        p = ls.requests_dir / f"test_trade_{int(time.time() * 1000)}.json"
        p.write_text(json.dumps(req))
        print("Request written; the running bot picks it up within a minute:", p.name)
        return 0
    if a.cmd == "unhalt":
        from fxbot.live.journal import Journal
        j = Journal(ls.journal_path)
        was = ls.halt_path.read_text().strip() if ls.halt_path.exists() else None
        ls.halt_path.unlink(missing_ok=True)
        j.set("killed", False)
        j.event("unhalt", was=was)
        print(f"Halt cleared (was: {was}). Restart the bot: sudo systemctl restart fxbot")
        return 0
    if a.cmd == "export":
        from fxbot.config import REPO_ROOT
        from fxbot.live.journal import Journal
        j = Journal(ls.journal_path)
        since = time.time() - a.days * 86400
        out = REPO_ROOT / "reviews"
        out.mkdir(exist_ok=True)
        stamp = time.strftime("%Y%m%d_%H%M", time.gmtime())
        (out / f"live_orders_{stamp}.csv").write_text(j.orders_csv(since))
        (out / f"live_events_{stamp}.csv").write_text(j.events_csv(since))
        print("Wrote", out / f"live_orders_{stamp}.csv", "and", out / f"live_events_{stamp}.csv")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
