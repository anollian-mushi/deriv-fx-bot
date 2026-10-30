import datetime as dt

import numpy as np
import pytest

from fxbot.backtest import candles as bc
from fxbot.data.candles import Candle, write_day
from fxbot.data.split import HoldoutError


def test_holdout_guard_refuses_holdout_dates(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "ROOT", tmp_path)
    with pytest.raises(HoldoutError):
        bc.load_m1("frxEURUSD", dt.date(2026, 4, 1), dt.date(2026, 4, 28), use_cache=False)


def test_sources_by_date_and_trading_hours(tmp_path, monkeypatch):
    monkeypatch.setattr(bc, "ROOT", tmp_path)
    fri = dt.date(2026, 4, 24)       # Friday, Dukascopy side
    tue = dt.date(2026, 4, 28)       # holdout, Deriv side
    f0 = int(dt.datetime(2026, 4, 24, 20, 54, tzinfo=dt.timezone.utc).timestamp())
    write_day(tmp_path / "data_external/dukascopy/frxEURUSD/1m/2026-04-24.csv.gz",
              [Candle(f0, 1, 1, 1, 1, 0.1), Candle(f0 + 60, 2, 2, 2, 2, 0.1)], "dukascopy")
    t0 = int(dt.datetime(2026, 4, 28, 10, 0, tzinfo=dt.timezone.utc).timestamp())
    write_day(tmp_path / "data/frxEURUSD/1m/2026-04-28.csv.gz", [Candle(t0, 3, 3, 3, 3)], "deriv")
    bars = bc.load_m1("frxEURUSD", fri, tue, include_holdout=True, use_cache=False)
    # 20:55 Friday minute dropped (market closed); Deriv minute used for the 28th.
    assert list(bars.epoch) == [f0, t0]
    assert list(bars.close) == [1.0, 3.0]


def _m1(epochs, prices):
    e = np.array(epochs, dtype=np.int64)
    p = np.array(prices, dtype=float)
    return bc.Bars(e, e + 60, p, p + 0.5, p - 0.5, p)


def test_aggregate_hours_on_utc_boundaries():
    base = 1_700_000_000 - 1_700_000_000 % 3600
    m1 = _m1([base, base + 60, base + 3540, base + 3600], [1.0, 2.0, 3.0, 4.0])
    h = bc.aggregate(m1, "1h")
    assert list(h.epoch) == [base, base + 3600]
    assert list(h.end) == [base + 3600, base + 7200]
    assert (h.open[0], h.high[0], h.low[0], h.close[0]) == (1.0, 3.5, 0.5, 3.0)
    assert h.close[1] == 4.0
