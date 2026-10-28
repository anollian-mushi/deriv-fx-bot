import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import typical_moves  # noqa: E402

from fxbot.data.candles import Candle, write_day  # noqa: E402

TRAIN_DAY = 1777248000    # 2026-04-27 00:00 UTC (Monday)
HOLDOUT_DAY = 1777334400  # 2026-04-28 00:00 UTC


def test_load_skips_holdout_files_by_default(tmp_path):
    write_day(tmp_path / "2026-04-27.csv.gz", [Candle(TRAIN_DAY + 3600, 1, 1, 1, 1)], "deriv")
    write_day(tmp_path / "2026-04-28.csv.gz", [Candle(HOLDOUT_DAY + 3600, 1, 1, 1, 1)], "deriv")
    assert [c.epoch for c in typical_moves.load(tmp_path)] == [TRAIN_DAY + 3600]
    assert len(typical_moves.load(tmp_path, include_holdout=True)) == 2


def test_product_costs_refuses_mismatched_moves_file(tmp_path, monkeypatch):
    import product_costs
    from fxbot.data.split import HoldoutError

    (tmp_path / "research").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "contract_specs.yaml").write_text("connections: {}\n")
    (tmp_path / "research" / "typical_moves.json").write_text(json.dumps({"_meta": {"includes_holdout": True}}))
    monkeypatch.setattr(product_costs, "ROOT", tmp_path)
    monkeypatch.setattr(sys, "argv", ["product_costs.py"])
    with pytest.raises(HoldoutError):
        product_costs.main()
