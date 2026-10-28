from fxbot.data.candles import Candle, clean_candles, encode_day, read_day, resample, write_day


def c(epoch, o=1.1, h=1.2, l=1.0, cl=1.15, spread=None):
    return Candle(epoch, o, h, l, cl, spread)


def test_clean_sorts_and_drops_unaligned_duplicates_invalid():
    raw = [
        c(120), c(60), c(60),            # out of order + identical duplicate
        c(90),                            # not on a minute boundary
        c(180, h=1.1, cl=1.15),           # high below close
        c(240, l=1.12),                   # low above open
        c(300, o=0),                      # zero price
        c(360, o=-1),                     # negative price
        c(420),
    ]
    out, stats = clean_candles(raw, 60)
    assert [x.epoch for x in out] == [60, 120, 420]
    assert stats.unaligned == 1
    assert stats.duplicates == 1
    assert stats.invalid == 4
    assert stats.received == 9 and stats.kept == 3


def test_conflicting_duplicate_keeps_first_and_notes_it():
    out, stats = clean_candles([c(60, cl=1.15), c(60, cl=1.11)], 60)
    assert out[0].close == 1.15
    assert stats.duplicates == 1
    assert "conflicting duplicate" in stats.notes[0]


def test_negative_spread_is_invalid():
    out, stats = clean_candles([c(60, spread=-0.1)], 60)
    assert out == [] and stats.invalid == 1


def test_resample_1m_to_15m():
    minutes = [Candle(900 + 60 * i, 1.0 + i, 2.0 + i, 0.5 + i, 1.5 + i, 0.1 * (i + 1)) for i in range(15)]
    minutes.append(Candle(1800, 9, 9, 9, 9, 0.2))
    out = resample(minutes, 900)
    assert len(out) == 2
    first = out[0]
    assert first.epoch == 900
    assert first.open == 1.0 and first.close == 15.5
    assert first.high == 16.0 and first.low == 0.5
    assert abs(first.spread - 0.8) < 1e-9
    assert out[1] == Candle(1800, 9, 9, 9, 9, 0.2)


def test_day_file_roundtrip_is_deterministic(tmp_path):
    candles = [c(60), c(120, spread=0.00012)]
    assert encode_day(candles, "deriv") == encode_day(candles, "deriv")
    path = tmp_path / "2026-01-05.csv.gz"
    write_day(path, candles, "dukascopy")
    back, source = read_day(path)
    assert source == "dukascopy"
    assert back[1].spread == 0.00012 and back[0].spread is None
    assert not list(tmp_path.glob("*.tmp"))


def test_read_day_rejects_mixed_sources(tmp_path):
    import gzip

    import pytest

    path = tmp_path / "mixed.csv.gz"
    path.write_bytes(gzip.compress(b"epoch,open,high,low,close,source\n60,1,1,1,1,deriv\n120,1,1,1,1,other\n"))
    with pytest.raises(ValueError):
        read_day(path)
