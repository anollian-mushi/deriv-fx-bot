"""Run a backtest: measured Multiplier costs, then the 1.5x stress run, then the report.

Resumable: each run saves its state monthly under state/backtest/. If the time
budget runs out the script stops with exit code 2; run the same command again
to continue. Pre-holdout data only unless --include-holdout (final test only).

Run:
  python scripts/run_backtest.py --strategy fxbot.strategies.ma_cross_example:MaCrossExample \
      --symbols frxEURUSD --start 2021-10-27 --end 2026-04-27 --name ma_cross_example_eurusd_1h
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import shutil
import sys
import time

import _bootstrap  # noqa: F401

from fxbot.backtest.engine import STATE_DIR, Engine
from fxbot.backtest.report import write_run
from fxbot.data.split import HOLDOUT_START
from fxbot.risk.limits import RiskLimits


def load_strategy(spec: str):
    mod, cls = spec.split(":")
    return getattr(importlib.import_module(mod), cls)()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", required=True, help="module:Class")
    p.add_argument("--symbols", default="frxEURUSD,frxGBPUSD,frxUSDJPY")
    p.add_argument("--start", default="2021-10-27")
    p.add_argument("--end", default=(HOLDOUT_START - dt.timedelta(days=1)).isoformat())
    p.add_argument("--name", required=True)
    p.add_argument("--balance", type=float, default=100.0)
    p.add_argument("--max-minutes", type=float, default=9.0)
    p.add_argument("--include-holdout", action="store_true")
    p.add_argument("--restart", action="store_true", help="discard saved progress for this name")
    a = p.parse_args()
    if a.include_holdout:
        print("WARNING: holdout data included. This is only for the single final test.")
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    symbols = a.symbols.split(",")
    t0 = time.time()
    states = {}
    for label, stress in (("measured", 1.0), ("stress", 1.5)):
        run_name = f"{a.name}_{label}"
        if a.restart:
            (STATE_DIR / f"{run_name}.pkl").unlink(missing_ok=True)
        eng = Engine(load_strategy(a.strategy), symbols, start, end, RiskLimits(starting_balance=a.balance),
                     stress=stress, include_holdout=a.include_holdout, run_name=run_name)
        left = a.max_minutes * 60 - (time.time() - t0)
        if not eng.run(max_seconds=max(left, 0)):
            print(f"{label} run paused at {eng.state.timeline_pos:,}/{len(eng.timeline):,} minutes. "
                  "Run the same command again to continue.")
            return 2
        states[label] = eng.state
        print(f"{label}: {len(eng.state.trades)} trades, balance {eng.state.balance}")
    strat = load_strategy(a.strategy)
    info = {"strategy": a.strategy, "timeframe": strat.timeframe, "label": getattr(strat, "label", ""),
            "params": getattr(strat, "params", {}), "symbols": symbols, "start": a.start, "end": a.end,
            "include_holdout": a.include_holdout, "starting_balance": a.balance}
    out = write_run(a.name, info, states["measured"], states["stress"], a.include_holdout)
    print(f"report: {out.relative_to(out.parents[2])} ({time.time() - t0:.0f}s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
