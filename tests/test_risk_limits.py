import datetime as dt

import pytest

from fxbot.risk.limits import AccountState, Approval, OrderRequest, RiskLimits, RiskManager

BASE = {"frxEURUSD": 0.000239, "frxGBPUSD": 0.000203, "frxUSDJPY": 0.000275}
RM = RiskManager(RiskLimits(), BASE)
T = int(dt.datetime(2025, 3, 4, 10, 0, tzinfo=dt.timezone.utc).timestamp())   # Tuesday 10:00


def acct(**kw):
    a = dict(balance=100.0, equity=100.0, day_start_balance=100.0, starting_balance=100.0)
    a.update(kw)
    return AccountState(**a)


def req(**kw):
    r = dict(symbol="frxEURUSD", direction="MULTUP")
    r.update(kw)
    return OrderRequest(**r)


def check(r=None, a=None, epoch=T, rate=0.000239):
    return RM.check_entry(r or req(), a or acct(), epoch, rate)


def test_approves_and_sizes_stake_at_3pct_rounded_down():
    d = check(a=acct(balance=87.77, equity=87.77, day_start_balance=87.77))
    assert d.allowed and d.approval.stake == 2.63


def test_risk_fraction_capped_and_minimum_stake():
    assert check(r=req(risk_fraction=0.05)).reason == "bad_risk_fraction"
    assert check(r=req(risk_fraction=0.01)).approval.stake == 1.0
    d = check(a=acct(balance=60, equity=60, day_start_balance=60), r=req(risk_fraction=0.015))
    assert d.reason == "stake_below_minimum" and d.wait


def test_only_x100_and_x200():
    assert check(r=req(multiplier=200)).allowed
    for m in (300, 500, 800, 50):
        d = check(r=req(multiplier=m))
        assert d.reason == "multiplier_not_allowed" and not d.wait


def test_cost_gate_at_1_5x_base():
    assert check(rate=0.000239 * 1.5).allowed
    d = check(rate=0.000239 * 1.51)
    assert d.reason == "cost_gate" and d.rate_seen == pytest.approx(0.000239 * 1.51) and d.wait
    assert check(rate=None).reason == "no_price"


def test_daily_loss_limit():
    assert check(a=acct(equity=90.0, balance=90.0)).reason == "daily_loss_limit"
    assert check(a=acct(equity=90.5, balance=90.5)).allowed


def test_kill_switch():
    d = check(a=acct(equity=50.0, balance=50.0, day_start_balance=50.0))
    assert d.reason == "kill_switch" and not d.wait
    assert RM.kill_switch_hit(acct(equity=49.99))
    assert check(a=acct(killed=True)).reason == "kill_switch"


def test_max_two_positions_and_one_per_pair():
    assert check(a=acct(open_symbols=["frxEURUSD"])).reason == "one_per_pair"
    assert check(r=req(symbol="frxGBPUSD", direction="MULTUP"),
                 a=acct(open_symbols=["frxEURUSD"]), rate=0.000203).allowed
    assert check(r=req(symbol="frxUSDJPY"), a=acct(open_symbols=["frxEURUSD", "frxGBPUSD"]),
                 rate=0.000275).reason == "max_positions"


def test_calendar_rules():
    assert check(epoch=T - 5 * 3600).reason == "outside_entry_window"     # 05:00
    assert check(epoch=T + 11 * 3600).reason == "daily_pause"             # 21:00
    assert check(epoch=T + 4 * 86400).reason == "market_closed"           # Saturday


def test_approval_cannot_be_forged():
    with pytest.raises(PermissionError):
        Approval(object(), req(), 3.0, T, 0.000239)


def test_limits_cannot_be_loosened():
    for kw in (dict(max_risk_fraction=0.05), dict(daily_loss_fraction=0.2), dict(kill_switch_fraction=0.3),
               dict(allowed_multipliers=(100, 500)), dict(max_positions=3), dict(gate_factor=2.0),
               dict(starting_balance=500)):
        with pytest.raises(ValueError):
            RiskLimits(**kw)


def test_x200_deadline_20_50_and_x100_until_friday():
    assert RM.exit_deadline(T, 200) == T + 10 * 3600 + 50 * 60
    assert RM.exit_deadline(T, 100) == T + 3 * 86400 + 10 * 3600 + 30 * 60
