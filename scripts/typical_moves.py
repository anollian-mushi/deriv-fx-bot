"""Typical price moves on 15m, 1h, 4h and daily candles, in pips.

Used to compare trading costs with how far price usually moves in one
candle (reports/product_choice.md). Reads Deriv 1h candles (about one year)
(15m candles from the 15m files) and Dukascopy 1m mid prices (five years,
research only), builds 4h and daily
candles on UTC boundaries, and writes research/typical_moves.json.

"Move" measures per candle:
- range: high - low (how far price travels inside the candle)
- body:  |close - open| (net move from start to end)
Only Deriv trading hours are used (Dukascopy minutes after Friday 20:55 UTC
are dropped).

Holdout: by default every candle dated 2026-04-28 or later (any source) is
left out, as CLAUDE.md requires. --include-holdout reads it anyway and writes
research/typical_moves_with_holdout.json instead, so the default output can
never contain holdout data.

Run: python scripts/typical_moves.py [--include-holdout]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.data.candles import Candle, read_day, resample
from fxbot.data.split import HOLDOUT_START, before_holdout, day_in_holdout

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
FRAMES = {"15m": 900, "1h": 3600, "4h": 4 * 3600, "1d": 86400}
OUT = ROOT / "research" / "typical_moves.json"
OUT_WITH_HOLDOUT = ROOT / "research" / "typical_moves_with_holdout.json"


def _in_deriv_hours(epoch: int) -> bool:
    t = datetime.fromtimestamp(epoch, timezone.utc)
    if t.weekday() >= 5:
        return False
    return not (t.weekday() == 4 and (t.hour, t.minute) >= (20, 55))


def load(folder: Path, include_holdout: bool = False) -> list[Candle]:
    candles: list[Candle] = []
    for path in sorted(folder.glob("*.csv.gz")):
        if not include_holdout and day_in_holdout(datetime.strptime(path.name[:10], "%Y-%m-%d").date()):
            continue  # never even open a holdout file
        day, _ = read_day(path)
        candles.extend(c for c in day if _in_deriv_hours(c.epoch))
    return candles if include_holdout else before_holdout(candles)


def stats(candles: list[Candle], pip: float) -> dict:
    ranges = sorted((c.high - c.low) / pip for c in candles)
    bodies = sorted(abs(c.close - c.open) / pip for c in candles)
    q = lambda xs, p: round(xs[min(len(xs) - 1, int(p * len(xs)))], 1)
    return {
        "candles": len(candles),
        "range_median": q(ranges, 0.5), "range_p25": q(ranges, 0.25), "range_p75": q(ranges, 0.75),
        "body_median": q(bodies, 0.5), "body_mean": round(statistics.mean(bodies), 1),
        "price_median": round(statistics.median(c.close for c in candles), 5),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-holdout", action="store_true",
                        help="also read data dated 2026-04-28 or later (final test only)")
    args = parser.parse_args()
    if args.include_holdout:
        print("WARNING: including holdout-period data. Only for the single final test.")
    result: dict = {"_meta": {"includes_holdout": args.include_holdout,
                              "data_before": None if args.include_holdout else HOLDOUT_START.isoformat()}}
    for sym in SYMBOLS:
        deriv_15m = load(ROOT / "data" / sym / "15m", args.include_holdout)
        sources = {
            "deriv": load(ROOT / "data" / sym / "1h", args.include_holdout),
            "dukascopy": load(ROOT / "data_external" / "dukascopy" / sym / "1m", args.include_holdout),
        }
        for src, base in sources.items():
            if base:
                result["_meta"][f"{sym}_{src}"] = {
                    "first": datetime.fromtimestamp(base[0].epoch, timezone.utc).date().isoformat(),
                    "last": datetime.fromtimestamp(base[-1].epoch, timezone.utc).date().isoformat()}
        for src, base in sources.items():
            for name, seconds in FRAMES.items():
                if src == "deriv" and seconds == 900:
                    bars = deriv_15m
                elif seconds > 3600 or src == "dukascopy":
                    bars = resample(base, seconds)
                else:
                    bars = base
                if name == "1d":
                    bars = [b for b in bars if datetime.fromtimestamp(b.epoch, timezone.utc).weekday() < 5]
                result.setdefault(sym, {}).setdefault(src, {})[name] = stats(bars, PIP[sym])
                s = result[sym][src][name]
                print(f"{sym} {src:12} {name}: range median {s['range_median']:6.1f} pips "
                      f"(p25 {s['range_p25']}, p75 {s['range_p75']}), body median {s['body_median']:5.1f}, "
                      f"n={s['candles']}")
    out = OUT_WITH_HOLDOUT if args.include_holdout else OUT
    out.write_text(json.dumps(result, indent=1))
    print(f"wrote {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
