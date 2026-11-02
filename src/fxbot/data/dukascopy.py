"""Dukascopy 1-minute history (secondary source, research only).

Dukascopy publishes one LZMA-compressed file per instrument, UTC day and side:
    https://datafeed.dukascopy.com/datafeed/EURUSD/2024/00/10/BID_candles_min_1.bi5
(the month is 0-based). Each record is 24 bytes, big-endian:
    seconds since midnight (int32), open, close, low, high (int32 points), volume (float32)

We download BID and ASK and store one row per minute with
    mid open/high/low/close = (bid + ask) / 2, field by field
    spread = average of the open and close spreads (ask - bid), in price units
Mid high/low are the average of the bid and ask highs/lows, a close
approximation of the true mid extremes. Minutes with no ticks on either side
(volume 0) are dropped.

Files go to data_external/dukascopy/<symbol>/1m/YYYY-MM-DD.csv.gz with
source=dukascopy, never into data/ (Deriv). Only Monday-Friday UTC days are
kept, matching the days Deriv trades.
"""

from __future__ import annotations

import datetime as dt
import lzma
import struct
import time
from pathlib import Path
from typing import Callable

import httpx

from fxbot.data.calendar import day_start, find_gaps, is_trading_day
from fxbot.data.candles import Candle, clean_candles, write_day
from fxbot.data.collector import Manifest

SOURCE = "dukascopy"
BASE_URL = "https://datafeed.dukascopy.com/datafeed"
# Deriv symbol -> (Dukascopy instrument, points per price unit, decimals for mid)
INSTRUMENTS = {
    "frxEURUSD": ("EURUSD", 100_000, 6),
    "frxGBPUSD": ("GBPUSD", 100_000, 6),
    "frxUSDJPY": ("USDJPY", 1_000, 4),
    # Added 31 Oct 2026 for the multi-pair test of i13 (owner's request): the same encoding
    # (points per unit and decimals of the mid) as the majors above; JPY crosses are quoted
    # to 3 decimals like USD/JPY.
    "frxAUDUSD": ("AUDUSD", 100_000, 6),
    "frxUSDCAD": ("USDCAD", 100_000, 6),
    "frxUSDCHF": ("USDCHF", 100_000, 6),
    "frxEURGBP": ("EURGBP", 100_000, 6),
    "frxEURJPY": ("EURJPY", 1_000, 4),
    "frxGBPJPY": ("GBPJPY", 1_000, 4),
}
RECORD = struct.Struct(">5if")


def url(instrument: str, day: dt.date, side: str) -> str:
    return f"{BASE_URL}/{instrument}/{day.year}/{day.month - 1:02d}/{day.day:02d}/{side}_candles_min_1.bi5"


def decode_bi5(blob: bytes, day: dt.date) -> dict[int, tuple[int, int, int, int, float]]:
    """epoch -> (open, high, low, close, volume) in integer points."""
    if not blob:
        return {}
    raw = lzma.decompress(blob)
    if len(raw) % RECORD.size:
        raise ValueError(f"corrupt bi5 file for {day}: {len(raw)} bytes")
    start = day_start(day)
    out = {}
    for offset, o, c, lo, hi, vol in RECORD.iter_unpack(raw):
        out[start + offset] = (o, hi, lo, c, vol)
    return out


def combine(bid: dict, ask: dict, point: int, decimals: int) -> list[Candle]:
    """Mid-price candles with spread, from bid and ask candles in points."""
    out = []
    for epoch in sorted(bid.keys() & ask.keys()):
        b, a = bid[epoch], ask[epoch]
        if b[4] == 0 and a[4] == 0:
            continue  # no ticks this minute: Dukascopy repeats the last price
        mid = [round((b[i] + a[i]) / 2 / point, decimals) for i in range(4)]
        spread = round(((a[0] - b[0]) + (a[3] - b[3])) / 2 / point, decimals)
        out.append(Candle(epoch, *mid, spread))
    return out


class Fetcher:
    """Polite HTTP client: paced, with long back-off on 429 and network errors."""

    def __init__(self, min_interval: float = 0.5, max_tries: int = 10, sleep: Callable = time.sleep,
                 transport: httpx.BaseTransport | None = None):
        self.min_interval = min_interval
        self.max_tries = max_tries
        self.sleep = sleep
        self.requests = 0
        self.throttled = 0
        self._last = 0.0
        self._http = httpx.Client(timeout=30, transport=transport,
                                  headers={"User-Agent": "deriv-fx-bot research downloader"})

    def get(self, target: str) -> bytes:
        delay = 5.0
        for attempt in range(1, self.max_tries + 1):
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                self.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                response = self._http.get(target)
            except httpx.TransportError:
                response = None
            if response is not None and response.status_code == 200:
                return response.content
            if response is not None and response.status_code == 404:
                return b""
            if response is not None and response.status_code not in (429, 500, 502, 503, 504):
                raise RuntimeError(f"Dukascopy HTTP {response.status_code} for {target}")
            self.throttled += 1
            if attempt < self.max_tries:
                self.sleep(delay)
                delay = min(delay * 2, 120)
        raise RuntimeError(f"Dukascopy kept refusing {target} after {self.max_tries} tries")


def series_dir(root: Path, symbol: str) -> Path:
    return root / symbol / "1m"


def collect(
    fetcher: Fetcher,
    root: Path,
    symbol: str,
    first_day: dt.date,
    last_day: dt.date,
    deadline: float,
    log=print,
) -> tuple[int, int]:
    """Download weekdays from last_day back to first_day (newest first).

    Returns (days still missing, days written this run). Days with a file, or
    recorded as closed, are skipped, so the function can be re-run at will.
    """
    instrument, point, decimals = INSTRUMENTS[symbol]
    folder = series_dir(root, symbol)
    manifest = Manifest.load(folder / "_manifest.json", symbol, "1m", source=SOURCE)
    closed = set(manifest.data["closed_days"])
    days = []
    d = last_day
    while d >= first_day:
        if is_trading_day(d) and d.isoformat() not in closed and not (folder / f"{d}.csv.gz").exists():
            days.append(d)
        d -= dt.timedelta(days=1)

    written = 0
    remaining = 0
    for i, day in enumerate(days):
        if time.monotonic() >= deadline:
            remaining = len(days) - i
            break
        bid = decode_bi5(fetcher.get(url(instrument, day, "BID")), day)
        ask = decode_bi5(fetcher.get(url(instrument, day, "ASK")), day)
        candles, stats = clean_candles(combine(bid, ask, point, decimals), 60)
        key = day.isoformat()
        if not candles:
            manifest.data["closed_days"].append(key)
        else:
            gaps, small, outside = find_gaps((c.epoch for c in candles), day, 60)
            write_day(folder / f"{key}.csv.gz", candles, SOURCE)
            manifest.data["days"][key] = {
                "candles": len(candles),
                "gaps": [g.describe(60) for g in gaps],
                "small_missing": small,
                "outside_deriv_session": outside,
                "dropped_invalid": stats.invalid,
                "median_spread": sorted(c.spread for c in candles)[len(candles) // 2],
                "notes": stats.notes[:10],
            }
            written += 1
        if written % 20 == 0:
            manifest.save()
    manifest.data["history_start"] = min(manifest.data["days"], default=None)
    manifest.save()
    return remaining, written
