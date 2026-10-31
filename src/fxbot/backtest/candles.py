"""1m price data and closed 1h / 4h / daily candles for the backtester.

Sources (CLAUDE.md research rules):
- before 2026-04-28: Dukascopy 1m mid prices (data_external/dukascopy/)
- from 2026-04-28 (the old, used-up holdout): Deriv 1m candles (data/), only
  with include_holdout=True. Without it, asking for any holdout date raises
  HoldoutError before a single holdout file is opened.
- from 2026-10-31 (the untouched period): Deriv 1m candles, only with
  forward=True, which only the strategy incubator uses. Otherwise
  UntouchedError is raised.

Minutes outside Deriv's trading hours (weekends, Friday after 20:55, closed
days, early closes) are dropped (fxbot.sessions). Bigger candles are built
from what is left, on UTC boundaries. Each candle carries its end time; the
engine hands a candle to a strategy only once that time has passed.

Built arrays are cached in cache/ (not committed) as .npz files.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fxbot import sessions
from fxbot.data.candles import read_day
from fxbot.data.split import HOLDOUT_START, UNTOUCHED_START, HoldoutError, UntouchedError

ROOT = Path(__file__).resolve().parents[3]
CACHE = ROOT / "cache"
TIMEFRAMES = {"1m": 60, "1h": 3600, "4h": 4 * 3600, "1d": 86400}


@dataclass
class Bars:
    """Candles as numpy arrays. epoch = start, end = when the candle is closed."""
    epoch: np.ndarray
    end: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    def __len__(self) -> int:
        return len(self.epoch)

    def slice(self, stop: int) -> "Bars":
        """Read-only view of the first `stop` candles."""
        out = Bars(*(a[:stop] for a in (self.epoch, self.end, self.open, self.high, self.low, self.close)))
        for a in (out.epoch, out.end, out.open, out.high, out.low, out.close):
            a.flags.writeable = False
        return out


def check_dates(start: dt.date, end: dt.date, include_holdout: bool, forward: bool = False) -> None:
    if end >= UNTOUCHED_START and not forward:
        raise UntouchedError(f"{end} is in the untouched period (from {UNTOUCHED_START}); "
                             "only the strategy incubator may read it (forward=True)")
    if end >= HOLDOUT_START and not include_holdout:
        raise HoldoutError(f"{end} is in the holdout (from {HOLDOUT_START}); "
                           "pass include_holdout=True only for the single final test")


def _source_file(symbol: str, day: dt.date) -> Path:
    name = f"{day:%Y-%m-%d}.csv.gz"
    if day < HOLDOUT_START:
        return ROOT / "data_external" / "dukascopy" / symbol / "1m" / name
    return ROOT / "data" / symbol / "1m" / name


def load_m1(symbol: str, start: dt.date, end: dt.date, include_holdout: bool = False,
            use_cache: bool = True, forward: bool = False) -> Bars:
    """1m mid-price candles for start..end (inclusive), trading hours only.

    forward=True is for the strategy incubator only: it may read the untouched period
    (fxbot.data.split.UNTOUCHED_START onward) and is never cached."""
    check_dates(start, end, include_holdout or forward, forward)
    use_cache = use_cache and not forward
    key = f"m1_{start:%Y%m%d}_{end:%Y%m%d}{'_holdout' if include_holdout else ''}.npz"
    path = CACHE / symbol / key
    if use_cache and path.exists():
        return _load(path)
    rows: list[tuple] = []
    day = start
    while day <= end:
        if sessions.is_trading_day(day):
            f = _source_file(symbol, day)
            if f.exists():
                candles, _ = read_day(f)
                rows.extend((c.epoch, c.open, c.high, c.low, c.close)
                            for c in candles if sessions.market_open(c.epoch))
        day += dt.timedelta(days=1)
    arr = np.array(rows, dtype=np.float64).reshape(-1, 5)
    epoch = arr[:, 0].astype(np.int64)
    bars = Bars(epoch, epoch + 60, arr[:, 1], arr[:, 2], arr[:, 3], arr[:, 4])
    if use_cache:
        _save(path, bars)
    return bars


def aggregate(m1: Bars, timeframe: str) -> Bars:
    """Build bigger candles on UTC boundaries from 1m candles."""
    seconds = TIMEFRAMES[timeframe]
    if seconds == 60:
        return m1
    bucket = m1.epoch - m1.epoch % seconds
    starts, idx = np.unique(bucket, return_index=True)
    return Bars(
        epoch=starts,
        end=starts + seconds,
        open=m1.open[idx],
        high=np.maximum.reduceat(m1.high, idx),
        low=np.minimum.reduceat(m1.low, idx),
        close=m1.close[np.r_[idx[1:] - 1, len(m1) - 1]],
    )


def load_candles(symbol: str, timeframe: str, start: dt.date, end: dt.date,
                 include_holdout: bool = False, use_cache: bool = True) -> tuple[Bars, Bars]:
    """(1m bars, timeframe bars) for one pair."""
    m1 = load_m1(symbol, start, end, include_holdout, use_cache)
    return m1, aggregate(m1, timeframe)


def _save(path: Path, b: Bars) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp.npz")
    np.savez(tmp, epoch=b.epoch, open=b.open, high=b.high, low=b.low, close=b.close)
    tmp.replace(path)


def _load(path: Path) -> Bars:
    z = np.load(path)
    return Bars(z["epoch"], z["epoch"] + 60, z["open"], z["high"], z["low"], z["close"])
