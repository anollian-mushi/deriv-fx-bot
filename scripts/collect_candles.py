"""Download Deriv candles into data/<symbol>/<granularity>/ (resumable).

Run it again after a timeout: it continues where it stopped.

    python scripts/collect_candles.py                    # all pairs, 1h, 15m, 1m
    python scripts/collect_candles.py --max-minutes 9    # stop cleanly after ~9 minutes
    python scripts/collect_candles.py --symbols frxEURUSD --granularities 1h

Exit codes: 0 = everything up to yesterday is saved, 2 = stopped by the time
limit with days still to fetch (run again), 1 = error.
"""

import argparse
import asyncio
import datetime as dt
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.config import REPO_ROOT
from fxbot.data.collector import DerivCandleFeed, collect_series

SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxUSDJPY",
           # added 31 Oct 2026 for the multi-pair test of the i13 rule (1m only: the engine builds
           # 1h/4h/daily candles from 1m; the extra 1h and 15m series are kept for the majors only)
           "frxAUDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP", "frxEURJPY", "frxGBPJPY"]
GRANULARITIES = ["1h", "15m", "1m"]  # cheap ones first
ONLY_1M = {"frxAUDUSD", "frxUSDCAD", "frxUSDCHF", "frxEURGBP", "frxEURJPY", "frxGBPJPY"}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=SYMBOLS)
    parser.add_argument("--granularities", nargs="+", default=GRANULARITIES)
    parser.add_argument("--max-minutes", type=float, default=9)
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data")
    parser.add_argument("--start", type=dt.date.fromisoformat, default=None,
                        help="for a new series: first day to keep (default: the oldest Deriv has)")
    args = parser.parse_args()

    started = time.monotonic()
    deadline = started + args.max_minutes * 60
    today = dt.datetime.now(dt.timezone.utc).date()
    print(f"Collecting Deriv candles up to {today - dt.timedelta(days=1)} "
          f"(time limit {args.max_minutes:g} min)")

    all_done = True
    async with DerivCandleFeed() as feed:
        for granularity in args.granularities:
            for symbol in args.symbols:
                if symbol in ONLY_1M and granularity != "1m":
                    continue
                r = await collect_series(feed, args.data_dir, symbol, granularity, today, deadline,
                                         not_before=args.start)
                if r.finished:
                    status = "complete"
                elif r.pending < 0:
                    status = "not started (time limit)"
                else:
                    status = f"{r.pending} days still to fetch"
                print(f"  {symbol:<10} {granularity:<3}: +{r.written} days saved, "
                      f"+{r.closed} closed days, {status}")
                all_done &= r.finished
        requests = feed.requests
    print(f"Done in {(time.monotonic() - started) / 60:.1f} min, {requests} requests.")
    if not all_done:
        print("Time limit reached. Run the same command again to continue.")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except Exception as err:
        print(f"ERROR: {type(err).__name__}: {err}", file=sys.stderr)
        sys.exit(1)
