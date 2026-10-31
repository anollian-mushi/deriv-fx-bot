"""Live candle store: same candles as the incubator, closed candles only, local files first."""

from __future__ import annotations

import asyncio
import datetime as dt

import numpy as np

from fxbot import sessions
from fxbot.backtest.candles import aggregate
from fxbot.data.candles import Candle, read_day, write_day
from fxbot.live.candles import CandleStore

SYM = "frxEURUSD"


class FakeFeed:
    def __init__(self):
        self.calls = []

    async def candles(self, symbol, seconds, start, end):
        self.calls.append((symbol, start, end))
        # Deriv also returns the minute still forming (epoch <= end)
        return [Candle(e, 1 + e % 7 * 1e-5, 1 + e % 7 * 1e-5 + 2e-5, 1 + e % 7 * 1e-5 - 2e-5, 1 + e % 5 * 1e-5)
                for e in range(start - start % 60, end + 1, 60)]


def test_bars_match_incubator_build_and_are_closed_only(tmp_path):
    feed = FakeFeed()
    now = int(dt.datetime(2026, 11, 3, 10, 7, 4, tzinfo=dt.timezone.utc).timestamp())
    st = CandleStore([SYM], tmp_path / "live", feed, read_dirs=[tmp_path / "repo"])
    fetched = asyncio.run(st.warm_up(3, now))
    assert fetched[SYM] == 1                                  # 31 Oct Sat and 1 Nov Sun skipped; Mon 2 Nov fetched
    m1 = st.bars_1m(SYM, now)
    assert m1.epoch[-1] + 60 <= now                           # the forming minute is not used
    h = st.bars(SYM, "1h", now - now % 60)
    assert int(h.end[-1]) == now - now % 3600                 # last closed 1h candle ends at 10:00
    ref = aggregate(m1, "1h")
    k = len(h)
    assert np.allclose(h.close, ref.close[:k]) and np.array_equal(h.epoch, ref.epoch[:k])
    assert all(sessions.market_open(int(e)) for e in m1.epoch)


def test_local_files_first_and_finished_days_saved(tmp_path):
    feed = FakeFeed()
    mon = dt.date(2026, 11, 2)
    repo = tmp_path / "repo"
    t0 = sessions.day_start(mon)
    write_day(repo / SYM / "1m" / f"{mon}.csv.gz", [Candle(t0 + 60 * i, 1.1, 1.1, 1.1, 1.1) for i in range(1440)],
              "deriv")
    now = sessions.day_start(dt.date(2026, 11, 3)) + 3600 + 4
    st = CandleStore([SYM], tmp_path / "live", feed, read_dirs=[repo])
    asyncio.run(st.warm_up(2, now))
    assert all(c[1] >= sessions.day_start(dt.date(2026, 11, 3)) for c in feed.calls)   # Monday came from the file
    # next day: refresh saves the finished Tuesday into BOT_HOME/data
    later = sessions.day_start(dt.date(2026, 11, 4)) + 120 + 4
    asyncio.run(st.refresh(later))
    f = tmp_path / "live" / SYM / "1m" / "2026-11-03.csv.gz"
    assert f.exists() and len(read_day(f)[0]) > 60
