"""Numbers for reports/session1_findings_part1.md, from files already in the repo.

Reads only local files (no downloads, no API calls) and only data dated before
2026-10-31 (CLAUDE.md untouched period):
- commission per pair in the 06:00-17:59 UTC entry window, from
  research/phase2/cost_by_hour.json (majors) and cost_by_hour_pairs2.json
  (six newer pairs), in pips at each table's own `price_used`;
- average candle moves (high - low) on 15m, 1h and 4h candles built from 1m data
  on UTC boundaries, Deriv trading hours only (Mon-Fri, Friday until 20:55),
  from Dukascopy 1m (five years) and from Deriv 1m (what exists);
- data inventory and quality counts from every data folder's _manifest.json.

Writes research/session1_findings.json. Run: python scripts/session1_findings.py
"""

from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import pandas as pd

import _bootstrap  # noqa: F401

from fxbot import symbols as S

ROOT = Path(__file__).resolve().parents[1]
CUTOFF = "2026-10-31"                       # untouched period starts here: never read
PAIRS = S.MAJORS + S.PAIRS2
TABLES = {"research/phase2/cost_by_hour.json": S.MAJORS,
          "research/phase2/cost_by_hour_pairs2.json": S.PAIRS2}
WINDOW = range(6, 18)                       # 06:00-17:59 UTC
FRAMES = {"15m": "15min", "1h": "1h", "4h": "4h"}


def day_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.glob("????-??-??.csv.gz") if p.name[:10] < CUTOFF)


def load_1m(folder: Path) -> pd.DataFrame:
    parts = []
    for p in day_files(folder):
        with gzip.open(p, "rt") as f:
            parts.append(pd.read_csv(f, usecols=["epoch", "open", "high", "low", "close"]))
    df = pd.concat(parts, ignore_index=True)
    df.index = pd.to_datetime(df.pop("epoch"), unit="s", utc=True)
    df = df[~df.index.duplicated()].sort_index()
    wd, mins = df.index.weekday, df.index.hour * 60 + df.index.minute
    keep = (wd < 4) | ((wd == 4) & (mins < 20 * 60 + 55))      # Deriv hours: Mon-Thu, Fri < 20:55
    return df[keep]


def moves(m1: pd.DataFrame, pip: float) -> dict:
    out = {}
    for name, rule in FRAMES.items():
        bars = m1.resample(rule, origin="epoch", label="left", closed="left").agg(
            {"high": "max", "low": "min"}).dropna()
        rng = (bars["high"] - bars["low"]) / pip
        out[name] = {"candles": int(len(rng)), "range_mean": round(float(rng.mean()), 1),
                     "range_median": round(float(rng.median()), 1)}
    return out


def window_cost(table: dict, sym: str) -> dict:
    price, pip = table["price_used"][sym], S.PIP[sym]
    rates = [table["hours"][str(h)]["max_rate_pct"][sym] for h in WINDOW
             if table["hours"][str(h)].get("max_rate_pct")]
    base = table["base_rate_pct"][sym]
    pips = lambda r: round(r / 100 * price / pip, 2)            # noqa: E731
    return {"base_rate_pct": base, "window_max_rate_pct": max(rates), "price_used": price,
            "base_pips": pips(base), "window_max_pips": pips(max(rates)),
            "hours_sampled": len(rates)}


def quality(folder: Path) -> dict | None:
    m = folder / "_manifest.json"
    if not m.exists():
        return None
    man = json.loads(m.read_text())
    days = {d: v for d, v in man["days"].items() if d < CUTOFF}
    gaps = sum(len(v.get("gaps", [])) for v in days.values())
    blips = sum(v.get("small_missing", 0) for v in days.values())
    bad = sum(v.get("dropped_invalid", 0) for v in days.values())
    dup = sum(v.get("dropped_duplicates", 0) for v in days.values())
    return {"first": min(days), "last": max(days), "days": len(days),
            "closed_days": [d for d in man.get("closed_days", []) if d < CUTOFF],
            "gaps_5min_plus": gaps, "short_blips_minutes": blips, "bad_candles": bad, "duplicates": dup}


def main() -> int:
    out: dict = {"_meta": {"data_before": CUTOFF, "entry_window_utc": "06:00-17:59",
                           "move": "mean and median of high-low per candle, Deriv trading hours"},
                 "pairs": {}}
    tables = {path: json.loads((ROOT / path).read_text()) for path in TABLES}
    for sym in PAIRS:
        path = next(p for p, syms in TABLES.items() if sym in syms)
        rec = {"name": S.display(sym), "cost_table": path, "cost": window_cost(tables[path], sym),
               "moves": {}, "data": {}}
        for label, folder in (("dukascopy_1m", ROOT / "data_external" / "dukascopy" / sym / "1m"),
                              ("deriv_1m", ROOT / "data" / sym / "1m")):
            if day_files(folder):
                m1 = load_1m(folder)
                rec["moves"][label] = moves(m1, S.PIP[sym])
                rec["moves"][label]["period"] = [m1.index[0].date().isoformat(), m1.index[-1].date().isoformat()]
        for label, folder in (("deriv_1m", ROOT / "data" / sym / "1m"), ("deriv_15m", ROOT / "data" / sym / "15m"),
                              ("deriv_1h", ROOT / "data" / sym / "1h"),
                              ("dukascopy_1m", ROOT / "data_external" / "dukascopy" / sym / "1m")):
            q = quality(folder)
            if q:
                rec["data"][label] = q
        c = rec["cost"]["window_max_pips"]
        rec["cost_share_of_mean_move"] = {
            src: {tf: round(c / mv[tf]["range_mean"], 3) for tf in FRAMES} for src, mv in rec["moves"].items()}
        out["pairs"][sym] = rec
        print(sym, rec["cost"]["base_pips"], rec["cost"]["window_max_pips"],
              {src: {tf: mv[tf]["range_mean"] for tf in FRAMES} for src, mv in rec["moves"].items()}, flush=True)
    (ROOT / "research" / "session1_findings.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
