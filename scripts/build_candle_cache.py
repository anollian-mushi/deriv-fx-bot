"""Build (or refresh) the cached 1m arrays the backtester reads.

Resumable: each pair is cached as soon as it is built, and a pair already in
the cache is skipped. Pre-holdout data only unless --include-holdout.

Run: python scripts/build_candle_cache.py [--start 2021-10-27] [--end 2026-04-27]
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time

import _bootstrap  # noqa: F401

from fxbot.backtest.candles import load_m1
from fxbot.data.split import HOLDOUT_START

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default="2021-10-27")
    p.add_argument("--end", default=(HOLDOUT_START - dt.timedelta(days=1)).isoformat())
    p.add_argument("--include-holdout", action="store_true")
    a = p.parse_args()
    start, end = dt.date.fromisoformat(a.start), dt.date.fromisoformat(a.end)
    for sym in SYMBOLS:
        t0 = time.time()
        bars = load_m1(sym, start, end, a.include_holdout)
        print(f"{sym}: {len(bars):,} 1m candles {start}..{end} in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
