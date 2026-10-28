"""Summarise the saved candle data as Markdown tables (for reports/data_quality.md).

- date range, day counts, closed days, gaps and dropped candles per series
- Deriv 15m/1h candles vs the same candles built from Deriv 1m data
- Dukascopy vs Deriv 1m on the days both have
- size on disk

    python scripts/data_quality.py > /tmp/summary.md
"""

import json
import subprocess
from collections import Counter
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.config import REPO_ROOT
from fxbot.data.candles import GRANULARITIES, read_day, resample

SYMBOLS = ["frxEURUSD", "frxGBPUSD", "frxUSDJPY"]
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
DERIV = REPO_ROOT / "data"
DUKA = REPO_ROOT / "data_external" / "dukascopy"


def manifest(folder: Path) -> dict | None:
    path = folder / "_manifest.json"
    return json.loads(path.read_text()) if path.is_file() else None


def series_table() -> None:
    print("| Source | Symbol | Granularity | First day | Last day | Days | Closed days | Days with gaps | Gaps | Small missing 1m | Outside session | Dropped |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    rows = [(DERIV, s, g) for s in SYMBOLS for g in GRANULARITIES] + [(DUKA, s, "1m") for s in SYMBOLS]
    for root, symbol, gran in rows:
        m = manifest(root / symbol / gran)
        if not m or not m["days"]:
            continue
        days = m["days"]
        gaps = sum(len(d["gaps"]) for d in days.values())
        gap_days = sum(1 for d in days.values() if d["gaps"])
        small = sum(d.get("small_missing", 0) for d in days.values())
        outside = sum(d.get("outside_session", d.get("outside_deriv_session", 0)) for d in days.values())
        dropped = sum(d.get("dropped_unaligned", 0) + d.get("dropped_duplicates", 0) + d.get("dropped_invalid", 0)
                      for d in days.values())
        print(f"| {m['source']} | {symbol} | {gran} | {min(days)} | {max(days)} | {len(days)} | "
              f"{', '.join(m['closed_days']) or '-'} | {gap_days} | {gaps} | {small if gran == '1m' else '-'} | "
              f"{outside} | {dropped} |")


def gap_details(limit: int = 15) -> None:
    print("\nLargest gaps (Deriv):\n")
    found = []
    for symbol in SYMBOLS:
        for gran in GRANULARITIES:
            m = manifest(DERIV / symbol / gran) or {"days": {}}
            for day, d in m["days"].items():
                for g in d["gaps"]:
                    n = int(g.split("(")[1].split()[0])
                    found.append((n * GRANULARITIES[gran], symbol, gran, day, g))
    for _, symbol, gran, day, g in sorted(found, reverse=True)[:limit]:
        print(f"- {symbol} {gran} {day}: {g}")
    times = Counter(g.split()[0] for *_, gran, day, g in found if gran == "1m")
    if times:
        print("\nMost common 1m gap windows (UTC):", ", ".join(f"{t} x{n}" for t, n in times.most_common(5)))


def compare_resampled() -> None:
    print("\n| Symbol | Built from 1m | Candles compared | Only in one | Identical | Max diff (pips) O/H/L/C |")
    print("|---|---|---|---|---|---|")
    for symbol in SYMBOLS:
        for gran in ("15m", "1h"):
            seconds = GRANULARITIES[gran]
            compared = only_one = identical = 0
            max_diff = [0.0] * 4
            for path in sorted((DERIV / symbol / "1m").glob("*.csv.gz")):
                other = DERIV / symbol / gran / path.name
                if not other.exists():
                    continue
                built = {c.epoch: c for c in resample(read_day(path)[0], seconds)}
                theirs = {c.epoch: c for c in read_day(other)[0]}
                only_one += len(built.keys() ^ theirs.keys())
                for e in built.keys() & theirs.keys():
                    a, b = built[e], theirs[e]
                    diffs = [abs(x - y) / PIP[symbol] for x, y in zip(a[1:5], b[1:5])]
                    compared += 1
                    identical += all(d < 1e-6 for d in diffs)
                    max_diff = [max(m, d) for m, d in zip(max_diff, diffs)]
            if compared:
                print(f"| {symbol} | {gran} | {compared} | {only_one} | {identical / compared:.2%} | "
                      f"{' / '.join(f'{d:.2f}' for d in max_diff)} |")


def compare_sources() -> None:
    print("\n| Symbol | Days both have | Minutes compared | Median close diff (pips) | 95th pct (pips) | Median Dukascopy spread (pips) |")
    print("|---|---|---|---|---|---|")
    for symbol in SYMBOLS:
        diffs, spreads, days = [], [], 0
        for path in sorted((DERIV / symbol / "1m").glob("*.csv.gz")):
            other = DUKA / symbol / "1m" / path.name
            if not other.exists():
                continue
            days += 1
            deriv = {c.epoch: c for c in read_day(path)[0]}
            for c in read_day(other)[0]:
                if c.epoch in deriv:
                    diffs.append(abs(c.close - deriv[c.epoch].close) / PIP[symbol])
                spreads.append(c.spread / PIP[symbol])
        if diffs:
            diffs.sort()
            spreads.sort()
            print(f"| {symbol} | {days} | {len(diffs)} | {diffs[len(diffs) // 2]:.2f} | "
                  f"{diffs[int(len(diffs) * 0.95)]:.2f} | {spreads[len(spreads) // 2]:.2f} |")


def sizes() -> None:
    def du(path: Path) -> str:
        if not path.exists():
            return "0"
        return subprocess.run(["du", "-sh", str(path)], capture_output=True, text=True).stdout.split()[0]

    print(f"\nSize: data/ {du(DERIV)}, data_external/ {du(REPO_ROOT / 'data_external')}, "
          f".git {du(REPO_ROOT / '.git')}")


if __name__ == "__main__":
    series_table()
    gap_details()
    compare_resampled()
    compare_sources()
    sizes()
