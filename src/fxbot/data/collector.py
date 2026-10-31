"""Resumable Deriv candle collector.

Saves one gzip CSV per symbol, granularity and UTC day:
    data/<symbol>/<1m|15m|1h>/YYYY-MM-DD.csv.gz
plus data/<symbol>/<granularity>/_manifest.json with the history start,
closed days (holidays) and per-day quality stats.

Progress lives in those files: a day is written only once it is over and
fully fetched, and days that already have a file are skipped. A run that is
stopped (timeout, --max-minutes, crash) loses at most the day in progress.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from fxbot.data.calendar import DAY, day_start, expected_epochs, find_gaps, is_trading_day, session_end, utc_date
from fxbot.data.candles import GRANULARITIES, Candle, clean_candles, write_day
from fxbot.deriv.api import WS_PUBLIC_URL, DerivError, ws_request

SOURCE = "deriv"
MAX_SLOTS = 600  # candles per request; Deriv caps replies at ~700 (15m/1h) or 1000 (1m)
MIN_INTERVAL = 2.2  # seconds between history requests (limit: ~30 per minute)
LOOKBACK_DAYS = 800  # how far back to search for the start of history
PARTIAL_DAY_COVERAGE = 0.9  # first day of history with less than this is skipped


class HistoryUnavailable(Exception):
    """Deriv returned candles outside the requested window: no history there."""


class CandleFeed(Protocol):
    async def candles(self, symbol: str, seconds: int, start: int, end: int) -> list[Candle]: ...


class DerivCandleFeed:
    """ticks_history over the public WebSocket, paced under the rate limit."""

    def __init__(self, url: str = WS_PUBLIC_URL, min_interval: float = MIN_INTERVAL):
        self.url = url
        self.min_interval = min_interval
        self.requests = 0
        self._ws: Any = None
        self._last = 0.0

    async def __aenter__(self) -> "DerivCandleFeed":
        await self._connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._ws is not None:
            await self._ws.close()

    async def _connect(self) -> None:
        from websockets.asyncio.client import connect

        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
        self._ws = await connect(self.url, open_timeout=30, ping_interval=20)

    async def candles(self, symbol: str, seconds: int, start: int, end: int) -> list[Candle]:
        payload = {
            "ticks_history": symbol,
            "style": "candles",
            "granularity": seconds,
            "start": start,
            "end": str(end),
        }
        rate_limited = reconnects = 0
        while True:
            wait = self._last + self.min_interval - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last = time.monotonic()
            self.requests += 1
            try:
                reply = await asyncio.wait_for(ws_request(self._ws, payload), timeout=60)
                break
            except DerivError as err:
                if err.code != "RateLimit" or rate_limited >= 6:
                    raise
                rate_limited += 1
                await asyncio.sleep(30)
            except Exception:  # dropped connection, timeout
                if reconnects >= 3:
                    raise
                reconnects += 1
                await asyncio.sleep(5 * reconnects)
                await self._connect()
        raw = reply.get("candles") or []
        out = [Candle(int(c["epoch"]), c["open"], c["high"], c["low"], c["close"]) for c in raw]
        if any(c.epoch < start - seconds or c.epoch > end for c in out):
            raise HistoryUnavailable(f"{symbol} {seconds}s: no history at {start}")
        return out


@dataclass
class Manifest:
    path: Path
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path, symbol: str, granularity: str, source: str = SOURCE) -> "Manifest":
        data: dict[str, Any] = {}
        if path.is_file():
            data = json.loads(path.read_text())
        data.setdefault("source", source)
        if data["source"] != source:
            raise ValueError(f"{path} belongs to source {data['source']!r}, not {source!r}")
        data.setdefault("symbol", symbol)
        data.setdefault("granularity", granularity)
        data.setdefault("history_start", None)
        data.setdefault("closed_days", [])
        data.setdefault("skipped_days", {})
        data.setdefault("days", {})
        return cls(path, data)

    def save(self) -> None:
        self.data["closed_days"] = sorted(set(self.data["closed_days"]))
        self.data["days"] = dict(sorted(self.data["days"].items()))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=1, sort_keys=True) + "\n")
        os.replace(tmp, self.path)


@dataclass
class SeriesResult:
    symbol: str
    granularity: str
    written: int = 0
    closed: int = 0
    pending: int = 0
    finished: bool = False


def series_dir(root: Path, symbol: str, granularity: str) -> Path:
    return root / symbol / granularity


def day_file(root: Path, symbol: str, granularity: str, day: dt.date) -> Path:
    return series_dir(root, symbol, granularity) / f"{day.isoformat()}.csv.gz"


async def find_history_start(feed: CandleFeed, symbol: str, seconds: int, today: dt.date) -> dt.date:
    """Earliest trading day with history (binary search on 6-hour probes).

    A probe that returns candles outside its window means "no history there".
    An empty probe (holiday) counts as available, which keeps the search
    monotonic.
    """
    days = [today - dt.timedelta(days=n) for n in range(LOOKBACK_DAYS, 0, -1)]
    days = [d for d in days if is_trading_day(d)]

    async def available(d: dt.date) -> bool:
        start = day_start(d) + 6 * 3600
        try:
            await feed.candles(symbol, seconds, start, start + 6 * 3600 - 1)
            return True
        except HistoryUnavailable:
            return False

    if await available(days[0]):
        return days[0]
    lo, hi = 0, len(days) - 1  # days[lo] unavailable, days[hi] available
    if not await available(days[hi]):
        raise HistoryUnavailable(f"{symbol}: no recent history")
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if await available(days[mid]):
            hi = mid
        else:
            lo = mid
    return days[hi]


def _batches(days: list[dt.date], seconds: int) -> list[list[dt.date]]:
    """Group consecutive pending days so each request window fits MAX_SLOTS."""
    batches: list[list[dt.date]] = []
    for d in days:
        if batches:
            first = batches[-1][0]
            contiguous = (d - batches[-1][-1]).days <= 3
            span = (day_start(d) + DAY - day_start(first)) // seconds
            if contiguous and span <= MAX_SLOTS:
                batches[-1].append(d)
                continue
        batches.append([d])
    return batches



async def collect_series(
    feed: CandleFeed,
    root: Path,
    symbol: str,
    granularity: str,
    today: dt.date,
    deadline: float,
    log=print,
    not_before: dt.date | None = None,
) -> SeriesResult:
    """Download every finished trading day that has no file yet.

    not_before: start the series on this day instead of searching for the oldest history Deriv
    has (used for pairs added later, whose research history comes from Dukascopy before the
    2026-04-28 holdout start; Deriv data is only needed from that day on)."""
    seconds = GRANULARITIES[granularity]
    result = SeriesResult(symbol, granularity)
    manifest = Manifest.load(series_dir(root, symbol, granularity) / "_manifest.json", symbol, granularity)

    if manifest.data["history_start"] is None:
        if not_before is not None:
            start = not_before
        else:
            if time.monotonic() >= deadline:
                result.pending = -1  # not started: history start still unknown
                return result
            start = await find_history_start(feed, symbol, seconds, today)
        manifest.data["history_start"] = start.isoformat()
        manifest.save()
        log(f"  {symbol} {granularity}: history starts {start}")
    first_day = dt.date.fromisoformat(manifest.data["history_start"])

    done = set(manifest.data["closed_days"]) | set(manifest.data["skipped_days"])
    pending = []
    d = first_day
    while d < today:
        if is_trading_day(d) and d.isoformat() not in done and not day_file(root, symbol, granularity, d).exists():
            pending.append(d)
        d += dt.timedelta(days=1)

    for batch in _batches(pending, seconds):
        if time.monotonic() >= deadline:
            break
        window_start = day_start(batch[0])
        window_end = day_start(batch[-1]) + session_end(batch[-1])
        fetched: list[Candle] = []
        t = window_start
        try:
            while t < window_end:
                chunk_end = min(t + MAX_SLOTS * seconds, window_end) - 1
                fetched.extend(await feed.candles(symbol, seconds, t, chunk_end))
                t = chunk_end + 1
        except HistoryUnavailable:
            # Deriv keeps a rolling window; these days dropped out before we got them.
            for day in batch:
                manifest.data["skipped_days"][day.isoformat()] = "no longer available at Deriv"
            manifest.save()
            log(f"  {symbol} {granularity}: {batch[0]}..{batch[-1]} no longer available, skipped")
            continue

        by_day: dict[dt.date, list[Candle]] = {day: [] for day in batch}
        for c in fetched:
            day = utc_date(c.epoch)
            if day in by_day:
                by_day[day].append(c)
        for day in batch:
            _finish_day(root, symbol, granularity, seconds, day, by_day[day], manifest, first_day, result)
        manifest.save()

    result.pending = len(pending) - result.written - result.closed - _skipped_in(pending, manifest)
    result.finished = result.pending == 0
    return result


def _skipped_in(pending: list[dt.date], manifest: Manifest) -> int:
    skipped = manifest.data["skipped_days"]
    return sum(1 for d in pending if d.isoformat() in skipped)


def _finish_day(
    root: Path,
    symbol: str,
    granularity: str,
    seconds: int,
    day: dt.date,
    raw: list[Candle],
    manifest: Manifest,
    first_day: dt.date,
    result: SeriesResult,
) -> None:
    key = day.isoformat()
    candles, stats = clean_candles(raw, seconds)
    if not candles:
        manifest.data["closed_days"].append(key)
        result.closed += 1
        return
    gaps, small_missing, outside = find_gaps((c.epoch for c in candles), day, seconds)
    expected = len(expected_epochs(day, seconds))
    coverage = len(candles) / expected
    if day == first_day and coverage < PARTIAL_DAY_COVERAGE:
        manifest.data["skipped_days"][key] = f"first day of history is partial ({coverage:.0%})"
        return
    write_day(day_file(root, symbol, granularity, day), candles, SOURCE)
    manifest.data["days"][key] = {
        "candles": len(candles),
        "expected": expected,
        "gaps": [g.describe(seconds) for g in gaps],
        "small_missing": small_missing,
        "outside_session": outside,
        "dropped_unaligned": stats.unaligned,
        "dropped_duplicates": stats.duplicates,
        "dropped_invalid": stats.invalid,
        "notes": stats.notes[:10],
    }
    result.written += 1
