import datetime as dt
import lzma
import struct

import httpx
import pytest

from fxbot.data.calendar import day_start
from fxbot.data.candles import read_day
from fxbot.data.dukascopy import Fetcher, collect, combine, decode_bi5, url

DAY = dt.date(2024, 1, 10)


def bi5(rows):
    return lzma.compress(b"".join(struct.pack(">5if", *r) for r in rows), format=lzma.FORMAT_ALONE)


def test_url_uses_zero_based_month():
    assert url("EURUSD", DAY, "BID").endswith("/EURUSD/2024/00/10/BID_candles_min_1.bi5")


def test_decode_and_combine_mid_and_spread():
    # offset, open, close, low, high, volume (points)
    bid = decode_bi5(bi5([(0, 109317, 109332, 109310, 109337, 5.0), (60, 1, 1, 1, 1, 0.0)]), DAY)
    ask = decode_bi5(bi5([(0, 109319, 109336, 109313, 109340, 4.0), (60, 1, 1, 1, 1, 0.0)]), DAY)
    candles = combine(bid, ask, 100_000, 6)
    assert len(candles) == 1  # zero-volume minute dropped
    c = candles[0]
    assert c.epoch == day_start(DAY)
    assert c.open == 1.09318 and c.close == 1.09334
    assert c.high == 1.093385 and c.low == 1.093115
    assert c.spread == 0.00003  # (2 + 4) / 2 points


def test_empty_file_means_no_data():
    assert decode_bi5(b"", DAY) == {}


def test_fetcher_backs_off_on_429_then_succeeds():
    replies = iter([429, 429, 200])
    sleeps = []
    transport = httpx.MockTransport(lambda r: httpx.Response(next(replies), content=b"ok"))
    f = Fetcher(min_interval=0, sleep=sleeps.append, transport=transport)
    assert f.get("https://example.test/x") == b"ok"
    assert f.throttled == 2 and sleeps == [5.0, 10.0]


def test_fetcher_gives_up_loudly():
    transport = httpx.MockTransport(lambda r: httpx.Response(429))
    f = Fetcher(min_interval=0, max_tries=3, sleep=lambda s: None, transport=transport)
    with pytest.raises(RuntimeError):
        f.get("https://example.test/x")


class FakeFetcher:
    def __init__(self, holiday=None):
        self.holiday = holiday
        self.urls = []

    def get(self, target):
        self.urls.append(target)
        parts = target.split("/")
        day = dt.date(int(parts[-4]), int(parts[-3]) + 1, int(parts[-2]))
        if day == self.holiday:
            return b""
        bid = "BID" in parts[-1]
        rows = [(m * 60, 109300, 109310, 109290, 109320 + (0 if bid else 3), 1.0) for m in range(1440)]
        if not bid:
            rows = [(o, a + 2, c + 2, lo + 2, hi, v) for o, a, c, lo, hi, v in rows]
        return bi5(rows)


def test_collect_newest_first_skips_weekends_and_resumes(tmp_path):
    first, last = dt.date(2024, 1, 8), dt.date(2024, 1, 14)  # Mon .. Sun
    fetcher = FakeFetcher(holiday=dt.date(2024, 1, 9))
    remaining, written = collect(fetcher, tmp_path, "frxEURUSD", first, last, float("inf"), log=lambda *_: None)
    assert (remaining, written) == (0, 4)
    days_requested = [u.split("/")[-2] for u in fetcher.urls[::2]]
    assert days_requested == ["12", "11", "10", "09", "08"]  # newest first, no weekend
    candles, source = read_day(tmp_path / "frxEURUSD" / "1m" / "2024-01-10.csv.gz")
    assert source == "dukascopy" and len(candles) == 1440
    assert candles[0].spread == 0.00002

    again = FakeFetcher()
    assert collect(again, tmp_path, "frxEURUSD", first, last, float("inf"), log=lambda *_: None) == (0, 0)
    assert again.urls == []  # holiday remembered, files skipped


def test_collect_stops_at_deadline(tmp_path):
    remaining, written = collect(FakeFetcher(), tmp_path, "frxEURUSD", dt.date(2024, 1, 8),
                                 dt.date(2024, 1, 12), deadline=0, log=lambda *_: None)
    assert remaining == 5 and written == 0
