import asyncio
import datetime as dt
import json

import pytest

from fxbot.data import collector
from fxbot.data.calendar import day_start, expected_epochs, utc_date
from fxbot.data.candles import Candle, read_day
from fxbot.data.collector import HistoryUnavailable, collect_series, day_file

TODAY = dt.date(2026, 10, 28)       # Wednesday
HISTORY_START = dt.date(2026, 10, 12)  # Monday
HOLIDAY = dt.date(2026, 10, 20)     # pretend Tuesday holiday


class FakeFeed:
    """Serves a complete calendar of candles; can fail after N requests."""

    def __init__(self, fail_after=None, duplicate_edges=True):
        self.fail_after = fail_after
        self.duplicate_edges = duplicate_edges
        self.requests = []

    async def candles(self, symbol, seconds, start, end):
        self.requests.append((seconds, start, end))
        if self.fail_after is not None and len(self.requests) > self.fail_after:
            raise ConnectionError("network dropped")
        if utc_date(start) < HISTORY_START:
            raise HistoryUnavailable("too old")
        out = []
        d = utc_date(start)
        while day_start(d) <= end:
            if d != HOLIDAY:
                out += [Candle(e, 1.1, 1.2, 1.0, 1.15) for e in expected_epochs(d, seconds) if start <= e <= end]
            d += dt.timedelta(days=1)
        if self.duplicate_edges and out:
            out.append(out[-1])  # duplicate, must be removed
        return out


def run(feed, root, granularity="15m", deadline=float("inf")):
    return asyncio.run(collect_series(feed, root, "frxEURUSD", granularity, TODAY, deadline, log=lambda *_: None))


def test_full_collection_files_manifest_and_holiday(tmp_path):
    r = run(FakeFeed(), tmp_path)
    assert r.finished
    files = sorted(p.name for p in (tmp_path / "frxEURUSD" / "15m").glob("*.csv.gz"))
    # Mon 12th .. Tue 27th, weekdays only, minus the holiday
    assert files[0] == "2026-10-12.csv.gz" and files[-1] == "2026-10-27.csv.gz"
    assert "2026-10-20.csv.gz" not in files
    assert len(files) == 11
    manifest = json.loads((tmp_path / "frxEURUSD" / "15m" / "_manifest.json").read_text())
    assert manifest["history_start"] == "2026-10-12"
    assert manifest["closed_days"] == ["2026-10-20"]
    assert manifest["days"]["2026-10-16"]["candles"] == 84  # Friday early close
    assert manifest["days"]["2026-10-16"]["expected"] == 84
    assert manifest["days"]["2026-10-16"]["gaps"] == []
    candles, source = read_day(day_file(tmp_path, "frxEURUSD", "15m", dt.date(2026, 10, 14)))
    assert source == "deriv" and len(candles) == 96


def test_resume_after_failure_fetches_only_missing_days(tmp_path):
    with pytest.raises(ConnectionError):
        run(FakeFeed(fail_after=14), tmp_path, granularity="1m")  # 1m: 3 requests per day
    saved = {p.name for p in (tmp_path / "frxEURUSD" / "1m").glob("*.csv.gz")}
    assert 0 < len(saved) < 11

    feed = FakeFeed()
    r = run(feed, tmp_path, granularity="1m")
    assert r.finished
    after = {p.name for p in (tmp_path / "frxEURUSD" / "1m").glob("*.csv.gz")}
    assert saved < after and len(after) == 11
    fetched_days = {utc_date(start).isoformat() + ".csv.gz" for _, start, _ in feed.requests}
    assert not fetched_days & saved  # nothing already saved was downloaded again
    assert not list((tmp_path / "frxEURUSD" / "1m").glob("*.tmp"))


def test_existing_files_are_not_rewritten(tmp_path):
    run(FakeFeed(), tmp_path)
    path = day_file(tmp_path, "frxEURUSD", "15m", dt.date(2026, 10, 14))
    before = path.stat().st_mtime_ns
    feed = FakeFeed()
    r = run(feed, tmp_path)
    assert r.finished and r.written == 0
    assert feed.requests == []
    assert path.stat().st_mtime_ns == before


def test_deadline_stops_cleanly_and_reports_pending(tmp_path):
    folder = tmp_path / "frxEURUSD" / "1m"
    folder.mkdir(parents=True)
    (folder / "_manifest.json").write_text(json.dumps({"history_start": "2026-10-12"}))
    r = run(FakeFeed(), tmp_path, granularity="1m", deadline=0)
    assert not r.finished and r.pending > 0 and r.written == 0


def test_days_that_fell_out_of_history_are_skipped(tmp_path, monkeypatch):
    run(FakeFeed(), tmp_path, granularity="1h")
    manifest_path = tmp_path / "frxEURUSD" / "1h" / "_manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["history_start"] = "2026-10-08"  # older than the fake's history
    manifest_path.write_text(json.dumps(manifest))
    r = run(FakeFeed(), tmp_path, granularity="1h")
    manifest = json.loads(manifest_path.read_text())
    assert manifest["skipped_days"]["2026-10-08"] == "no longer available at Deriv"
    assert r.finished


def test_batches_fit_request_limit():
    days = [HISTORY_START + dt.timedelta(days=n) for n in range(14) if (HISTORY_START + dt.timedelta(days=n)).weekday() < 5]
    for seconds in (900, 3600):
        for batch in collector._batches(days, seconds):
            span = (day_start(batch[-1]) + 86400 - day_start(batch[0])) // seconds
            assert span <= collector.MAX_SLOTS


def test_deadline_before_history_search_does_not_fetch(tmp_path):
    feed = FakeFeed()
    r = run(feed, tmp_path, deadline=0)
    assert not r.finished and r.pending == -1
    assert feed.requests == []
