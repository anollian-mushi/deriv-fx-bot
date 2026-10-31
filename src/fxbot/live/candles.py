"""Live candles for the bot: the same 1h / 4h / daily candles the incubator builds.

The incubator builds every candle from Deriv 1m candles, keeps only minutes
when the market is open (fxbot.sessions), and groups them on UTC boundaries
(fxbot.backtest.candles.aggregate). The live bot does exactly the same, so a
candidate sees the same candles live as in its forward record.

Sources, in order:
1. day files in BOT_HOME/data/<symbol>/1m/ (written by this bot),
2. day files in the repository's data/ (from the daily GitHub collector),
3. Deriv's public WebSocket (ticks_history, 1m) for missing days and today.
Finished days fetched from Deriv are saved to BOT_HOME/data, so a restart
does not download them again.

This is a live trading read (CLAUDE.md: allowed, not research). It does not
go through fxbot.backtest.candles.load_m1, whose research guard stays as it is.
"""

from __future__ import annotations

import datetime as dt
import logging
from pathlib import Path

import numpy as np

from fxbot import sessions
from fxbot.backtest.candles import Bars, aggregate
from fxbot.config import REPO_ROOT
from fxbot.data.candles import Candle, read_day, write_day

log = logging.getLogger(__name__)
CHUNK = 600 * 60          # seconds of 1m candles per ticks_history request


class CandleStore:
    def __init__(self, symbols, save_dir: Path, feed, read_dirs: list[Path] | None = None):
        self.symbols = list(symbols)
        self.save_dir = Path(save_dir)
        self.read_dirs = [self.save_dir] + list(read_dirs if read_dirs is not None else [REPO_ROOT / "data"])
        self.feed = feed                       # object with async candles(symbol, seconds, start, end)
        self.m1: dict[str, dict[int, tuple]] = {s: {} for s in self.symbols}
        self.saved_days: set[tuple[str, dt.date]] = set()

    # ------------------------------------------------------------------ loading
    def _day_file(self, symbol: str, day: dt.date) -> Path | None:
        for d in self.read_dirs:
            p = d / symbol / "1m" / f"{day:%Y-%m-%d}.csv.gz"
            if p.exists():
                return p
        return None

    def _add(self, symbol: str, candles) -> None:
        book = self.m1[symbol]
        for c in candles:
            book[int(c.epoch)] = (float(c.open), float(c.high), float(c.low), float(c.close))

    async def warm_up(self, days: int, now: float) -> dict:
        """Load `days` calendar days of 1m history up to now. Returns {symbol: days fetched from Deriv}."""
        today = sessions.utc_date(int(now))
        fetched = {s: 0 for s in self.symbols}
        for s in self.symbols:
            d = today - dt.timedelta(days=days)
            while d < today:
                if sessions.is_trading_day(d):
                    f = self._day_file(s, d)
                    if f is not None:
                        self._add(s, read_day(f)[0])
                    else:
                        await self._fetch_range(s, sessions.day_start(d), sessions.day_start(d) + 86400, now)
                        self._save_day(s, d)
                        fetched[s] += 1
                d += dt.timedelta(days=1)
            await self._fetch_range(s, sessions.day_start(today), int(now), now)
        return fetched

    async def _fetch_range(self, symbol: str, start: int, end: int, now: float) -> int:
        n = 0
        t = start
        while t < end:
            t1 = min(t + CHUNK, end)
            got = await self.feed.candles(symbol, 60, t, t1)
            closed = [c for c in got if start <= c.epoch and c.epoch + 60 <= min(t1, now)]
            self._add(symbol, closed)
            n += len(closed)
            t = t1
        return n

    def _save_day(self, symbol: str, day: dt.date) -> None:
        t0 = sessions.day_start(day)
        rows = [Candle(e, *v) for e, v in sorted(self.m1[symbol].items()) if t0 <= e < t0 + 86400]
        if rows:
            write_day(self.save_dir / symbol / "1m" / f"{day:%Y-%m-%d}.csv.gz", rows, "deriv")
        self.saved_days.add((symbol, day))

    async def refresh(self, now: float) -> dict[str, int | None]:
        """Fetch the newest closed 1m candles. Returns {symbol: newest closed minute epoch}."""
        out = {}
        for s in self.symbols:
            book = self.m1[s]
            last = max(book) if book else int(now) - 3 * 3600
            start = max(last - 120, int(now) - 6 * 3600)     # re-read 2 minutes in case the last one changed
            await self._fetch_range(s, start - start % 60, int(now), now)
            out[s] = max(book) if book else None
            # Save every finished day once (yesterday after midnight).
            yday = sessions.utc_date(int(now)) - dt.timedelta(days=1)
            if sessions.is_trading_day(yday) and (s, yday) not in self.saved_days and self._day_file(s, yday) is None:
                self._save_day(s, yday)
        return out

    def prune(self, keep_days: int, now: float) -> None:
        cut = int(now) - keep_days * 86400
        for s in self.symbols:
            for e in [e for e in self.m1[s] if e < cut]:
                del self.m1[s][e]

    # ------------------------------------------------------------------ candles
    def bars_1m(self, symbol: str, until: int | None = None) -> Bars:
        """1m candles while the market is open, closed by `until` (epoch), as the incubator uses them."""
        items = sorted((e, v) for e, v in self.m1[symbol].items()
                       if sessions.market_open(e) and (until is None or e + 60 <= until))
        if not items:
            z = np.zeros(0)
            return Bars(z.astype(np.int64), z.astype(np.int64), z, z, z, z)
        ep = np.array([e for e, _ in items], dtype=np.int64)
        v = np.array([x for _, x in items], dtype=np.float64)
        return Bars(ep, ep + 60, v[:, 0], v[:, 1], v[:, 2], v[:, 3])

    def bars(self, symbol: str, timeframe: str, until: int) -> Bars:
        """Strategy candles that have closed by `until` (end <= until)."""
        tf = aggregate(self.bars_1m(symbol, until), timeframe)
        k = int(np.searchsorted(tf.end, until, "right"))
        return Bars(*(a[:k] for a in (tf.epoch, tf.end, tf.open, tf.high, tf.low, tf.close)))

    def last_price(self, symbol: str) -> float | None:
        book = self.m1[symbol]
        return book[max(book)][3] if book else None
