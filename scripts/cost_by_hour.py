"""Phase 2: commission cost by UTC hour, from every demo and real proposal sample.

Real and demo quote the same rate at the same moment (research/phase2/
real_vs_demo.md), so both count. The public (no login) connection quotes a
different rate and is left out.

For each sample the rate is read from the largest x100 quote (most digits).
Samples are grouped by the UTC hour they were taken in. For each hour the
table shows every reading and the highest one; backtests use the highest
(cautious: we have only one or two days per hour).

Cost in pips = rate x price / pip, with price = median close before
2026-04-28 (research/typical_moves.json; holdout data is not used).

Writes research/phase2/cost_by_hour.json and research/phase2/cost_by_hour.md.

Run: python scripts/cost_by_hour.py
"""

from __future__ import annotations

import argparse
import gzip
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot import symbols as symbols_mod

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / "research" / "phase2"
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = symbols_mod.PIP
PAUSE = "20:55-21:30"
# Set on the command line for another sample set (31 Oct 2026: the six extra pairs sampled on
# Monday 2 Nov into research/phase2/pairs2/, priced from the quotes' own spot price).
SAMPLE_DIR = PHASE2
SPOT: dict[str, list[float]] = defaultdict(list)


def samples(symbols=None) -> list[dict]:
    symbols = symbols or SYMBOLS
    out = []
    for path in sorted(SAMPLE_DIR.glob("proposals_*.jsonl.gz")):
        with gzip.open(path, "rt") as f:
            rows = [json.loads(line) for line in f]
        meta = rows[0]
        if meta.get("connection") not in ("demo", "real"):
            continue
        t = datetime.fromisoformat(meta["started_utc"])
        rates, paused = {}, False
        for sym in symbols:
            best = None
            for r in rows[1:]:
                if r.get("kind") != "grid" or r.get("symbol") != sym:
                    continue
                if not r["accepted"]:
                    paused |= "not available" in r.get("error", "").lower()
                    continue
                if r["multiplier"] != 100:
                    continue
                if r["proposal"].get("spot"):
                    SPOT[sym].append(float(r["proposal"]["spot"]))
                size = r["stake"] * 100
                if best is None or size > best[0]:
                    best = (size, r["proposal"]["commission"] / size)
            if best:
                rates[sym] = best[1]
        out.append({"time": t.strftime("%a %H:%M"), "hour": t.hour, "connection": meta["connection"],
                    "rates": rates, "paused": paused and not rates})
    return out


def main() -> int:
    global SAMPLE_DIR, SYMBOLS
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbols", nargs="+", default=list(SYMBOLS))
    ap.add_argument("--samples-dir", type=Path, default=PHASE2, help="folder of proposals_*.jsonl.gz")
    ap.add_argument("--out", default="cost_by_hour", help="output name under research/phase2/ (json + md)")
    ap.add_argument("--note", default="", help="note stored in the table")
    a = ap.parse_args()
    SAMPLE_DIR, SYMBOLS = a.samples_dir, tuple(a.symbols)
    all_samples = samples(SYMBOLS)
    if a.out == "cost_by_hour":
        moves = json.loads((ROOT / "research" / "typical_moves.json").read_text())
        if moves.get("_meta", {}).get("includes_holdout"):
            raise SystemExit("typical_moves.json includes holdout data; re-run scripts/typical_moves.py")
        price = {s: moves[s]["deriv"]["1h"]["price_median"] for s in SYMBOLS}
    else:
        # Other sample sets: the median spot price of the quotes themselves (no candle data needed).
        price = {s: round(statistics.median(SPOT[s]), 5) for s in SYMBOLS if SPOT[s]}
        missing = [s for s in SYMBOLS if s not in price]
        if missing:
            raise SystemExit(f"no accepted x100 quotes for {missing}")
    base = {s: min(x["rates"][s] for x in all_samples if s in x["rates"]) for s in SYMBOLS}
    by_hour: dict[int, list[dict]] = defaultdict(list)
    for x in all_samples:
        by_hour[x["hour"]].append(x)

    table = {"_note": a.note or ("The only commission source for backtests (CLAUDE.md). The 06:00-17:59 UTC "
                                 "base window is PROVISIONAL: measured 28-29 Oct 2026, between the European "
                                 "(25 Oct) and US (1 Nov) clock changes; re-checked in the week after 1 Nov."),
             "provisional_base_window_utc": "06:00-17:59",
             "symbols": list(SYMBOLS),
             "base_rate_pct": {s: round(base[s] * 100, 5) for s in SYMBOLS},
             "price_used": price, "hours": {}}
    names = [symbols_mod.display(s) for s in SYMBOLS]
    lines = ["| UTC hour | Samples | " + " | ".join(f"{n} max rate (x base)" for n in names) + " | "
             + " | ".join(f"{n} cost" for n in names) + " |", "|---|---|" + "---|" * (2 * len(SYMBOLS))]
    for h in range(24):
        group = by_hour.get(h, [])
        priced = [x for x in group if x["rates"]]
        times = ", ".join(x["time"] + (" (paused)" if x["paused"] else "") for x in group) or "none"
        if not priced:
            note = "trading paused" if any(x["paused"] for x in group) else "no sample"
            lines.append(f"| {h:02d} | {times} | {note} |" + " |" * (2 * len(SYMBOLS) - 1))
            table["hours"][h] = {"samples": times, "max_rate_pct": None}
            continue
        mx = {s: max(x["rates"][s] for x in priced if s in x["rates"]) for s in SYMBOLS}
        cost = {s: mx[s] * price[s] / PIP[s] for s in SYMBOLS}
        table["hours"][h] = {"samples": times,
                             "max_rate_pct": {s: round(mx[s] * 100, 5) for s in SYMBOLS},
                             "multiple_of_base": {s: round(mx[s] / base[s], 2) for s in SYMBOLS},
                             "cost_pips": {s: round(cost[s], 1) for s in SYMBOLS}}
        cells = " | ".join(f"{mx[s] * 100:.4f}% ({mx[s] / base[s]:.1f}x)" for s in SYMBOLS)
        pips = " | ".join(f"{cost[s]:.1f} pips" for s in SYMBOLS)
        lines.append(f"| {h:02d} | {times} | {cells} | {pips} |")
    (PHASE2 / f"{a.out}.json").write_text(json.dumps(table, indent=1))
    (PHASE2 / f"{a.out}.md").write_text(
        "# Commission by UTC hour (generated by scripts/cost_by_hour.py)\n\n"
        "Base rate (lowest seen): " + ", ".join(f"{symbols_mod.display(s)} {base[s] * 100:.4f}%" for s in SYMBOLS)
        + f". New trades are refused {PAUSE} UTC.\n\n"
        "The 06:00-17:59 UTC base window is **provisional**: it was measured 28-29 Oct "
        "2026, between the European (25 Oct) and US (1 Nov) clock changes, and is re-checked "
        "in the week after 1 Nov.\n\n" + "\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
