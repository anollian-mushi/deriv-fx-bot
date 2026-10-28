import pytest

from fxbot.contracts.multiplier import (
    commission,
    position_size,
    price_at_profit,
    profit,
    round_price,
    stop_loss_price,
    stop_out_move,
    stop_out_price,
    take_profit_price,
)

# Real quote, 2026-10-28: frxEURUSD, MULTDOWN, stake 1, x100, spot 1.11448,
# commission 0.02, take profit 1 -> 1.10311, stop loss 0.5 -> 1.11983.
SPOT = 1.11448


def test_position_size_and_commission():
    assert position_size(10, 100) == 1000
    assert commission(10, 100, 0.0002) == pytest.approx(0.20)
    assert commission(1, 100, 0.0002) == pytest.approx(0.02)


def test_take_profit_and_stop_loss_match_real_quote():
    tp = take_profit_price("MULTDOWN", 1, 100, SPOT, 1, 0.02)
    sl = stop_loss_price("MULTDOWN", 1, 100, SPOT, 0.5, 0.02)
    assert round_price(tp, 0.00001) == 1.10311
    assert round_price(sl, 0.00001) == 1.11983


def test_up_and_down_are_mirror_images():
    up = stop_out_price("MULTUP", 10, 100, 1.0, 0.2)
    down = stop_out_price("MULTDOWN", 10, 100, 1.0, 0.2)
    assert up == pytest.approx(1 - 0.0098)
    assert down == pytest.approx(1 + 0.0098)


def test_stop_out_move_shrinks_with_multiplier():
    assert stop_out_move(10, 100, 0.2) == pytest.approx(0.0098)
    assert stop_out_move(10, 500, 1.0) == pytest.approx(0.0018)


def test_profit_round_trip_and_floor_at_minus_stake():
    for direction in ("MULTUP", "MULTDOWN"):
        price = price_at_profit(direction, 2, 150, 1.25, 0.8, 0.06)
        assert profit(direction, 2, 150, 1.25, price, 0.06) == pytest.approx(0.8)
        so = stop_out_price(direction, 2, 150, 1.25, 0.06)
        assert profit(direction, 2, 150, 1.25, so, 0.06) == pytest.approx(-2)
    # A gap far past stop out still loses only the stake.
    assert profit("MULTUP", 2, 150, 1.25, 1.0, 0.06) == -2


def test_profit_at_entry_is_minus_commission():
    assert profit("MULTUP", 1, 50, 150.0, 150.0, 0.014) == pytest.approx(-0.014)


def test_round_price_modes_and_jpy_pip():
    assert round_price(1.1254019, 0.00001) == 1.12540
    assert round_price(1.1254019, 0.00001, "up") == 1.12541
    assert round_price(1.1254099, 0.00001, "down") == 1.12540
    assert round_price(152.3456, 0.001) == 152.346
    # Float noise must not push an exact value up a step.
    assert round_price(1.12540 + 1e-15, 0.00001, "up") == 1.12540


def test_unknown_direction_rejected():
    with pytest.raises(ValueError):
        profit("UP", 1, 100, 1.0, 1.1, 0.0)
