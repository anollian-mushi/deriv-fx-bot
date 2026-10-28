"""Candle records, cleaning, resampling and daily file storage.

Daily files are gzip CSV with one row per candle and a `source` column, so
data from different providers can never be mixed silently:

    epoch,open,high,low,close,source            (Deriv feed price)
    epoch,open,high,low,close,spread,source     (sources with bid/ask)

`epoch` is the candle's start time in UTC seconds.
"""

from __future__ import annotations

import csv
import gzip
import io
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, NamedTuple

GRANULARITIES = {"1m": 60, "15m": 900, "1h": 3600}
DAY = 86400


class Candle(NamedTuple):
    epoch: int
    open: float
    high: float
    low: float
    close: float
    spread: float | None = None


@dataclass
class CleanStats:
    received: int = 0
    kept: int = 0
    unaligned: int = 0
    duplicates: int = 0
    invalid: int = 0
    notes: list[str] = field(default_factory=list)


def is_valid_ohlc(c: Candle) -> bool:
    prices = (c.open, c.high, c.low, c.close)
    if any(p is None or p <= 0 for p in prices):
        return False
    if c.spread is not None and c.spread < 0:
        return False
    return c.high >= max(c.open, c.close) and c.low <= min(c.open, c.close)


def clean_candles(raw: Iterable[Candle], seconds: int) -> tuple[list[Candle], CleanStats]:
    """Sort, drop unaligned, invalid and duplicate candles.

    Unaligned: epoch not a multiple of the granularity (Deriv returns a partial
    candle stamped with the request start when the start is not aligned).
    Duplicates: same epoch twice. Identical copies are dropped quietly; if the
    copies differ, the first one is kept and a note is recorded.
    """
    stats = CleanStats()
    by_epoch: dict[int, Candle] = {}
    for c in raw:
        stats.received += 1
        if c.epoch % seconds:
            stats.unaligned += 1
            continue
        if not is_valid_ohlc(c):
            stats.invalid += 1
            stats.notes.append(f"invalid candle at {c.epoch}: {tuple(c)[1:]}")
            continue
        if c.epoch in by_epoch:
            stats.duplicates += 1
            if by_epoch[c.epoch] != c:
                stats.notes.append(f"conflicting duplicate at {c.epoch}")
            continue
        by_epoch[c.epoch] = c
    out = [by_epoch[e] for e in sorted(by_epoch)]
    stats.kept = len(out)
    return out, stats


def resample(candles: Iterable[Candle], seconds: int) -> list[Candle]:
    """Combine smaller candles into `seconds`-wide candles (e.g. 1m -> 15m).

    Input must be sorted. Spread, if present, is averaged.
    """
    out: list[Candle] = []
    bucket: list[Candle] = []

    def flush() -> None:
        if not bucket:
            return
        spreads = [c.spread for c in bucket if c.spread is not None]
        out.append(
            Candle(
                epoch=bucket[0].epoch - bucket[0].epoch % seconds,
                open=bucket[0].open,
                high=max(c.high for c in bucket),
                low=min(c.low for c in bucket),
                close=bucket[-1].close,
                spread=sum(spreads) / len(spreads) if spreads else None,
            )
        )
        bucket.clear()

    for c in candles:
        if bucket and c.epoch - c.epoch % seconds != bucket[0].epoch - bucket[0].epoch % seconds:
            flush()
        bucket.append(c)
    flush()
    return out


def _fmt(x: float) -> str:
    return f"{x:.8f}".rstrip("0").rstrip(".")


def encode_day(candles: list[Candle], source: str) -> bytes:
    """Gzip CSV bytes. Deterministic: same candles -> same bytes."""
    has_spread = any(c.spread is not None for c in candles)
    header = ["epoch", "open", "high", "low", "close"] + (["spread"] if has_spread else []) + ["source"]
    buf = io.StringIO()
    buf.write(",".join(header) + "\n")
    for c in candles:
        row = [str(c.epoch), _fmt(c.open), _fmt(c.high), _fmt(c.low), _fmt(c.close)]
        if has_spread:
            row.append(_fmt(c.spread) if c.spread is not None else "")
        row.append(source)
        buf.write(",".join(row) + "\n")
    raw = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, compresslevel=9, mtime=0) as gz:
        gz.write(buf.getvalue().encode())
    return raw.getvalue()


def write_day(path: Path, candles: list[Candle], source: str) -> None:
    """Write atomically (temp file + rename) so a killed run leaves no half file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(encode_day(candles, source))
    os.replace(tmp, path)


def read_day(path: Path) -> tuple[list[Candle], str]:
    """Return (candles, source). Raises if a file mixes sources."""
    with gzip.open(path, "rt", newline="") as f:
        rows = list(csv.DictReader(f))
    sources = {r["source"] for r in rows}
    if len(sources) > 1:
        raise ValueError(f"{path} mixes sources: {sorted(sources)}")
    candles = [
        Candle(
            int(r["epoch"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
            float(r["spread"]) if r.get("spread") else None,
        )
        for r in rows
    ]
    return candles, (sources.pop() if sources else "")
