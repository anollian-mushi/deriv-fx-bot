"""Download Dukascopy 1m history (research only) into data_external/dukascopy/.

Newest days first, so a stopped run still has the most recent years. Re-run
to continue. Prices are mid (average of bid and ask) plus the spread.

    python scripts/collect_dukascopy.py --years 5 --max-minutes 9

Exit codes: 0 = done, 2 = time limit reached (run again), 1 = error.
"""

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.config import REPO_ROOT
from fxbot.data.dukascopy import INSTRUMENTS, Fetcher, collect


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--symbols", nargs="+", default=list(INSTRUMENTS))
    parser.add_argument("--years", type=float, default=5)
    parser.add_argument("--max-minutes", type=float, default=9)
    parser.add_argument("--min-interval", type=float, default=0.5, help="seconds between requests")
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data_external" / "dukascopy")
    parser.add_argument("--end", type=dt.date.fromisoformat, default=None,
                        help="last day to fetch (default yesterday); research data must stop at 2026-10-30")
    args = parser.parse_args()

    started = time.monotonic()
    deadline = started + args.max_minutes * 60
    last_day = args.end or dt.datetime.now(dt.timezone.utc).date() - dt.timedelta(days=1)
    first_day = last_day - dt.timedelta(days=round(args.years * 365.25))
    print(f"Dukascopy 1m, {first_day} to {last_day}, time limit {args.max_minutes:g} min")

    fetcher = Fetcher(min_interval=args.min_interval)
    remaining_total = 0
    for symbol in args.symbols:
        remaining, written = collect(fetcher, args.data_dir, symbol, first_day, last_day, deadline)
        remaining_total += remaining
        print(f"  {symbol}: +{written} days saved, "
              f"{'complete' if remaining == 0 else f'{remaining} days still to fetch'}")
    print(f"Done in {(time.monotonic() - started) / 60:.1f} min: {fetcher.requests} requests, "
          f"{fetcher.throttled} refused/retried.")
    if remaining_total:
        print("Time limit reached. Run the same command again to continue.")
        return 2
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as err:
        print(f"ERROR: {type(err).__name__}: {err}", file=sys.stderr)
        sys.exit(1)
