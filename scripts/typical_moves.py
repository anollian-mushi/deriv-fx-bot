"""Typical price moves on 1h, 4h and daily candles, in pips.

Used to compare trading costs with how far price usually moves in one
candle (reports/product_choice.md). Reads Deriv 1h candles (about one year)
and Dukascopy 1m mid prices (five years, research only), builds 4h and daily
candles on UTC boundaries, and writes research/typical_moves.json.

"Move" measures per candle:
- range: high - low (how far price travels inside the candle)
- body:  |close - open| (net move from start to end)
Only Deriv trading hours are used (Dukascopy minutes after Friday 20:55 UTC
are dropped).

Run: python scripts/typical_moves.py
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.data.candles import Candle, read_day, resample

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
FRAMES = {"1h": 3600, "4h": 4 * 3600, "1d": 86400}
OUT = ROOT / "research" / "typical_moves.json"


def _in_deriv_hours(epoch: int) -> bool:
    t = datetime.fromtimestamp(epoch, timezone.utc)
    if t.weekday() >= 5:
        return False
    return not (t.weekday() == 4 and (t.hour, t.minute) >= (20, 55))


def load(folder: Path) -> list[Candle]:
    candles: list[Candle] = []
    for path in sorted(folder.glob("*.csv.gz")):
        day, _ = read_day(path)
        candles.extend(c for c in day if _in_deriv_hours(c.epoch))
    return candles


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
    result: dict = {}
    for sym in SYMBOLS:
        sources = {
            "deriv_1y": load(ROOT / "data" / sym / "1h"),
            "dukascopy_5y": load(ROOT / "data_external" / "dukascopy" / sym / "1m"),
        }
        for src, base in sources.items():
            for name, seconds in FRAMES.items():
                bars = resample(base, seconds) if seconds > 3600 or src.startswith("dukascopy") else base
                if name == "1d":
                    bars = [b for b in bars if datetime.fromtimestamp(b.epoch, timezone.utc).weekday() < 5]
                result.setdefault(sym, {}).setdefault(src, {})[name] = stats(bars, PIP[sym])
                s = result[sym][src][name]
                print(f"{sym} {src:12} {name}: range median {s['range_median']:6.1f} pips "
                      f"(p25 {s['range_p25']}, p75 {s['range_p75']}), body median {s['body_median']:5.1f}, "
                      f"n={s['candles']}")
    OUT.write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
