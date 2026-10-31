"""Live bot against a mocked Deriv: cost gate, rejected orders, disconnects, kill switch, /stop,
reconciliation after a restart, real-money refusals, dry run, Telegram commands."""

from __future__ import annotations

import asyncio
import shutil
from pathlib import Path

import pytest

from fxbot.backtest import fills
from fxbot.config import Settings
from fxbot.live import candidate as cand
from fxbot.live.broker import Broker
from fxbot.live.journal import Journal
from fxbot.live.main import ModeError, decide_mode, ledger_start
from fxbot.live.settings import load_live_settings
from fxbot.live.stop import stop_now
from fxbot.live.trader import Trader
from fxbot.risk.limits import Approval, OrderRequest, RiskLimits, RiskManager
from fxbot.risk.live import BuyTicket, LiveRisk, TicketError
from fxbot.telegram.commands import Commander
from live_fakes import BASE, MON_10, Clock, FakeDeriv, FakeNotifier, FakeStore, FakeTelegram, ScriptedStrategy

SETTINGS = Settings(deriv_app_id="app", deriv_pat="pat", deriv_account_id=None, deriv_mode="demo",
                    telegram_bot_token=None, telegram_chat_id=None, trading_enabled=True)
H10 = MON_10 - MON_10 % 3600          # candle closing at Monday 10:00


def make(tmp_path, entries=None, mode="demo", strategy=None, clock=None, fake=None, journal=None):
    clock = clock or Clock()
    fake = fake or FakeDeriv(clock)
    journal = journal or Journal(tmp_path / "journal.sqlite", 100.0, clock)
    notifier = FakeNotifier(journal)
    broker = Broker(SETTINGS, "demo", connect=fake.connect, rest_transport=fake.transport(), clock=clock)
    strat = strategy or ScriptedStrategy(entries)
    tr = Trader(candidate_id="cand_x", strategy=strat, broker=broker, store=FakeStore(fake), journal=journal,
                notifier=notifier, home=tmp_path, mode=mode, start_balance=100.0, clock=clock, sleep=clock.sleep,
                cost_sampling=False)
    tr.last_end = {s: H10 - 3600 for s in tr.symbols}   # the bot has seen candles up to 09:00
    return tr, fake, journal, notifier, clock


def run(coro):
    return asyncio.run(coro)


async def start_and_tick(tr, clock, minutes=1):
    await tr.connect()
    for _ in range(minutes):
        await tr.tick(clock())
        clock.t += 60


def skips(journal, reason=None):
    return [e for e in journal.events(kinds=("skip",)) if reason is None or e["detail"]["reason"] == reason]


# ============================================================================ normal order
def test_signal_buys_through_risk_and_gate(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(start_and_tick(tr, clock))
    orders = j.orders()
    assert len(orders) == 1 and orders[0]["state"] == "open"
    o = orders[0]
    assert o["stake"] == 3.0                               # 3% of the 100 USD ledger, not of 10,000 demo
    c = fake.contracts[o["contract_id"]]
    assert c["mult"] == 100 and c["sl"] and c["tp"]
    # every quote journalled with its exact rate; the probe gives the exact base rate
    q = j.quotes()
    probe = [x for x in q if x["purpose"] == "entry_probe"][0]
    assert probe["rate"] == pytest.approx(BASE["frxEURUSD"], rel=1e-4)
    assert any(x["purpose"] == "order" for x in q)
    assert any("Trade opened" in t for t in n.texts("trade"))
    assert fake.otps == 1


def test_sl_tp_amounts_match_backtest_fills(tmp_path):
    tr, *_ = make(tmp_path)
    sl, tp = tr.sl_tp_amounts("frxEURUSD", "MULTUP", 3.0, 100, 1.1, BASE["frxEURUSD"], 20, 40)
    p = fills.open_position("frxEURUSD", "MULTUP", 100, 3.0, 1.1 - 0.5 * 0.0001, 0, BASE["frxEURUSD"], 20, 40)
    assert sl == pytest.approx(p.sl_amount, abs=0.011) and tp == pytest.approx(p.tp_amount, abs=0.011)
    with pytest.raises(ValueError):
        tr.sl_tp_amounts("frxEURUSD", "MULTUP", 3.0, 100, 1.1, BASE["frxEURUSD"], 0.1, 40)


# ============================================================================ cost gate
def test_cost_gate_skips_and_logs_rate_then_buys_when_cheap(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    fake.rates["frxEURUSD"] = BASE["frxEURUSD"] * 1.6      # above 1.5x base
    run(start_and_tick(tr, clock, 2))
    assert j.orders() == []
    gs = skips(j, "cost_gate")
    assert gs and gs[0]["detail"]["rate_seen_pct"] == pytest.approx(BASE["frxEURUSD"] * 1.6 * 100, rel=1e-3)
    assert "frxEURUSD" in tr.pending                        # waits, like the backtester
    fake.rates["frxEURUSD"] = BASE["frxEURUSD"]
    run(tr.tick(clock()))
    assert len(j.orders(("open",))) == 1


def test_cost_gate_uses_order_quote_too(tmp_path):
    tr, *_ = make(tmp_path)
    ok, rate = tr.risk.quote_gate("frxGBPUSD", 0.10, 3.0, 100)    # 0.0333% > 1.5 x 0.0203%
    assert not ok and rate == pytest.approx(0.10 / 300)
    ok, _ = tr.risk.quote_gate("frxGBPUSD", 0.06, 3.0, 100)
    assert ok


def test_cost_gate_signal_expires_after_fixed_wait(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    fake.rates["frxEURUSD"] = BASE["frxEURUSD"] * 3
    run(tr.connect())
    for _ in range(62):
        run(tr.tick(clock()))
        clock.t += 60
    assert j.orders() == [] and "frxEURUSD" not in tr.pending
    assert skips(j, "expired")


# ============================================================================ rejected orders
def test_rejected_order_is_not_retried(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    fake.fail["buy"] = "error:InsufficientBalance"
    run(start_and_tick(tr, clock, 3))
    o = j.orders()
    assert len(o) == 1 and o[0]["state"] == "failed" and "InsufficientBalance" in o[0]["note"]
    assert fake.contracts == {}
    assert sum(1 for r in fake.requests if "buy" in r) == 1
    assert any("Order refused" in t for t in n.texts("error"))


def test_broker_buy_needs_a_ticket_from_the_risk_module(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    run(tr.connect())
    with pytest.raises(TicketError):
        run(tr.broker.buy({"proposal_id": "x"}))
    with pytest.raises(PermissionError):
        BuyTicket(object(), None, "p", 1, "frxEURUSD", "MULTUP", 1, 100, 0, 0, 0)
    with pytest.raises(PermissionError):
        Approval(object(), None, 1, 0, 0)


def test_ticket_is_single_use_and_expires():
    rm = RiskManager(RiskLimits(), BASE)
    clock = Clock()
    lr = LiveRisk(rm, lambda: None, clock)
    from fxbot.risk.limits import AccountState
    req = OrderRequest("frxEURUSD", "MULTUP", 100, 0.03)
    d = lr.check(req, AccountState(100, 100, 100, 100), MON_10, BASE["frxEURUSD"])
    t, g = lr.authorize(d, {"id": "p1", "ask_price": 3.0, "commission": 0.07}, BASE["frxEURUSD"])
    t.redeem(clock())
    with pytest.raises(TicketError):
        t.redeem(clock())
    t2, _ = lr.authorize(d, {"id": "p2", "ask_price": 3.0, "commission": 0.07}, BASE["frxEURUSD"])
    with pytest.raises(TicketError):
        t2.redeem(clock() + 30)
    # halted or paused: no ticket at all
    lr2 = LiveRisk(rm, lambda: "halted", clock)
    assert lr2.authorize(d, {"id": "p3", "ask_price": 3.0, "commission": 0.07}, BASE["frxEURUSD"])[0] is None


# ============================================================================ disconnects
def test_disconnect_after_buy_sent_no_duplicate(tmp_path):
    """Deriv filled the buy but the reply was lost: reconnect (fresh OTP), reconcile adopts it, no second buy."""
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(tr.connect())
    fake.fail["buy"] = "drop_after"

    async def go():
        tr.stopping = False
        await tr.run(until=clock() + 5 * 60)
    run(go())
    buys = [r for r in fake.requests if "buy" in r]
    assert len(buys) == 1 and len(fake.contracts) == 1
    o = j.orders()
    assert len(o) == 1 and o[0]["state"] == "open" and o[0]["contract_id"] in fake.contracts
    assert fake.otps >= 2                                    # a NEW one-time URL for the reconnect
    assert any(e["kind"] == "reconnect" for e in j.events())
    assert any("DID fill" in t for t in n.texts("reconcile"))


def test_disconnect_before_buy_reached_deriv(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(tr.connect())
    fake.fail["buy"] = "drop_before"
    run(tr.run(until=clock() + 5 * 60))
    assert fake.contracts == {}
    o = j.orders()
    assert len(o) == 1 and o[0]["state"] == "failed"       # proven never filled; signal dropped, not resent
    assert sum(1 for r in fake.requests if "buy" in r) == 1


def test_reconnect_backoff_survives_rest_outage(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    fake.rest_down = 4
    t0 = clock()
    run(tr.connect())
    assert tr.broker.alive
    assert clock() - t0 >= 1 + 2 + 4 + 8 - 0.1              # exponential backoff
    assert len([e for e in j.events() if e["kind"] == "connect_failed"]) == 4


def test_feed_failure_does_not_stop_position_management(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    run(tr.connect())
    cid = _bot_contract(tr, fake, j)
    tr.store.fail = 1
    fake.close(cid, profit=1.5)
    run(tr.tick(clock()))
    assert j.orders(("closed",))[0]["profit"] == 1.5
    assert any(e["kind"] == "feed_error" for e in j.events())


# ============================================================================ kill switch and limits
def _bot_contract(tr, fake, j, symbol="frxEURUSD", stake=3.0, deadline=None):
    cid = fake.open_contract(symbol, "MULTUP", stake, 100)
    oid = j.new_order(strategy="cand_x", symbol=symbol, direction="MULTUP", multiplier=100, stake=stake,
                      deadline=deadline or MON_10 + 86400)
    j.update_order(oid, state="open", contract_id=cid, buy_price=stake, purchase_time=int(tr.clock()),
                   entry_spot=fake.prices[symbol])
    return cid


def test_kill_switch_closes_all_halts_and_alerts(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxGBPUSD", H10 + 3600): "MULTUP"})
    run(tr.connect())
    oid = j.new_order(strategy="cand_x", symbol="frxUSDJPY", direction="MULTUP", multiplier=100, stake=48.0)
    j.update_order(oid, state="closed", profit=-48.0)          # ledger at 52 USD
    cid = _bot_contract(tr, fake, j)
    fake.prices["frxEURUSD"] = 1.0900                        # open loss pushes equity under 50
    run(tr.tick(clock()))
    assert fake.contracts[cid]["sold"]
    assert (tmp_path / "HALT").exists() and j.get("killed") is True
    assert any("KILL SWITCH" in t for t in n.texts("kill_switch"))
    # later signals never trade
    clock.t += 3600
    run(tr.tick(clock()))
    assert len(j.orders(("open",))) == 0 and len(fake.contracts) == 1


def test_daily_loss_limit_blocks_and_alerts_once(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(tr.connect())
    j.set("day_start", {"day": "2026-11-02", "balance": 100.0})
    oid = j.new_order(strategy="cand_x", symbol="frxGBPUSD", direction="MULTUP", multiplier=100, stake=3.0)
    j.update_order(oid, state="closed", profit=-10.5)
    run(tr.tick(clock()))
    clock.t += 60
    run(tr.tick(clock()))
    assert j.orders(("open",)) == []
    assert skips(j, "daily_loss_limit")
    assert len(n.texts("daily_limit")) == 1


def test_max_positions_count_foreign_contracts(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    fake.open_contract("frxEURUSD")                          # e.g. the weekend test
    run(start_and_tick(tr, clock))
    assert j.orders(("open",)) == []
    assert skips(j, "one_per_pair")
    assert len(tr.foreign) == 1


def test_forced_close_before_weekend(tmp_path):
    fri = MON_10 + 4 * 86400 + 10 * 3600 + 30 * 60           # Friday 20:30
    clock = Clock(fri - 60)
    tr, fake, j, n, _ = make(tmp_path, clock=clock)
    run(tr.connect())
    from fxbot import sessions
    cid = _bot_contract(tr, fake, j, deadline=sessions.exit_deadline(fri - 3600, 100))
    run(tr.tick(clock()))
    assert not fake.contracts[cid]["sold"]
    clock.t = fri + 3
    run(tr.tick(clock()))
    assert fake.contracts[cid]["sold"] and j.orders(("closed",))[0]["close_reason"] == "forced_deadline"


def test_strategy_exit(tmp_path):
    strat = ScriptedStrategy({("frxEURUSD", H10): "MULTUP"}, exits={("frxEURUSD", H10 + 3600)})
    tr, fake, j, n, clock = make(tmp_path, strategy=strat)
    run(start_and_tick(tr, clock))
    clock.t = H10 + 3600 + 3
    run(tr.tick(clock()))
    o = j.orders()[0]
    assert o["state"] == "closed" and o["close_reason"] == "strategy_exit"


# ============================================================================ /stop
def test_stop_works_while_trading_loop_is_stuck(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxGBPUSD", H10): "MULTUP"})
    run(tr.connect())
    cid = _bot_contract(tr, fake, j)
    # the trading loop is not running at all (stuck); /stop arrives on the command thread
    tg = FakeTelegram()
    factory = lambda: Broker(SETTINGS, "demo", connect=fake.connect, rest_transport=fake.transport(), clock=clock)
    cmd = Commander(tg, j, tmp_path, lambda: stop_now(tmp_path / "HALT", factory, j), clock=clock)
    tg.push("/stop")
    cmd.poll_once()
    assert fake.contracts[cid]["sold"]
    assert j.orders(("closed",))[0]["close_reason"] == "telegram_stop"
    assert (tmp_path / "HALT").exists()
    assert any("STOPPED" in s for s in tg.sent)
    # the loop wakes up later: it must not trade (halted), and the close is not recorded twice
    run(tr.tick(clock()))
    assert len(fake.contracts) == 1 and len(j.orders(("closed",))) == 1
    assert [e for e in j.events(kinds=("close",))].__len__() == 1


def test_halt_survives_restart_and_resume_does_not_clear_it(tmp_path):
    (tmp_path / "HALT").write_text("stopped by Telegram /stop")
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(start_and_tick(tr, clock, 2))
    assert j.orders() == []
    tg = FakeTelegram()
    cmd = Commander(tg, j, tmp_path, lambda: "", clock=clock)
    tg.push("/resume")
    cmd.poll_once()
    assert "HALTED" in tg.sent[-1] and (tmp_path / "HALT").exists()


def test_pause_blocks_new_trades_resume_allows(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    tg = FakeTelegram()
    cmd = Commander(tg, j, tmp_path, lambda: "", clock=clock)
    tg.push("/pause")
    cmd.poll_once()
    run(start_and_tick(tr, clock))
    assert j.orders() == [] and skips(j, "paused")
    tg.push("/resume")
    cmd.poll_once()
    run(tr.tick(clock()))
    assert len(j.orders(("open",))) == 1


# ============================================================================ reconciliation after restart
def test_reconciliation_after_restart(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    run(tr.connect())
    c_tp = _bot_contract(tr, fake, j, "frxEURUSD")
    c_open = _bot_contract(tr, fake, j, "frxGBPUSD")
    j.update_order(j.order_by_contract(c_tp)["id"], tp_amount=2.0)
    foreign = fake.open_contract("frxUSDJPY")
    # bot down; Deriv hits the take profit meanwhile
    fake.close(c_tp, profit=2.0)
    fake.drop_all()
    tr2, *_ = make(tmp_path, fake=fake, clock=clock, journal=j)
    run(tr2.connect())                                        # connect = fresh OTP + reconcile before anything else
    o = j.order_by_contract(c_tp)
    assert o["state"] == "closed" and o["profit"] == 2.0 and o["close_reason"] == "take_profit"
    assert j.order_by_contract(c_open)["state"] == "open"
    assert foreign in tr2.foreign
    assert j.balance() == 102.0
    # a third start does not alert the same foreign contract again
    n_before = len([t for t in tr2.notify.texts("reconcile") if "did not open" in t])
    tr3, *_ = make(tmp_path, fake=fake, clock=clock, journal=j)
    run(tr3.connect())
    assert n_before == 1 and not [t for t in tr3.notify.texts("reconcile") if "did not open" in t]


def test_restart_skips_candles_closed_while_down(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10 - 3600): "MULTUP"})
    tr.last_end = {s: H10 - 3 * 3600 for s in tr.symbols}
    run(start_and_tick(tr, clock))
    assert j.orders() == []                                   # 09:00 candle is an hour old: never traded late
    assert any(e["kind"] == "candles_skipped" for e in j.events())


# ============================================================================ modes
def _ls(tmp_path, **env):
    base = {"DERIV_MODE": "demo", "TRADING_ENABLED": "true", "STRATEGY_ID": "f1_london_breakout_r5",
            "BOT_HOME": str(tmp_path)}
    base.update(env)
    return load_live_settings(base, env_file=None)


def test_real_money_refused_unless_all_three(tmp_path):
    for env, grad in [({"DERIV_MODE": "real", "CONFIRM_REAL": "yes"}, False),
                      ({"DERIV_MODE": "real"}, True),
                      ({"DERIV_MODE": "real", "CONFIRM_REAL": "yes", "TRADING_ENABLED": "false"}, True)]:
        with pytest.raises(ModeError):
            decide_mode(_ls(tmp_path, **env), grad)
    assert decide_mode(_ls(tmp_path, DERIV_MODE="real", CONFIRM_REAL="yes"), True) == "real"
    assert decide_mode(_ls(tmp_path), False) == "demo"         # ungraduated: demo is fine
    assert decide_mode(_ls(tmp_path, TRADING_ENABLED="false"), False) == "dry"
    assert decide_mode(_ls(tmp_path), False, dry_run=True) == "dry"


def test_ledger_mode_cannot_be_mixed(tmp_path):
    j = Journal(tmp_path / "j.sqlite")
    ls = _ls(tmp_path)
    assert ledger_start(j, "demo", ls, None) == 100.0
    with pytest.raises(ModeError):
        ledger_start(j, "real", ls, 80.0)
    j2 = Journal(tmp_path / "j2.sqlite")
    with pytest.raises(ModeError):
        ledger_start(j2, "real", ls, 500.0)                     # real start must be 50-100 USD


def test_broker_refuses_real_account_and_gateway_in_demo(tmp_path):
    clock = Clock()
    fake = FakeDeriv(clock)
    s = Settings("app", "pat", "ROT123", "demo", None, None, True)
    b = Broker(s, "demo", connect=fake.connect, rest_transport=fake.transport())
    from fxbot.deriv.api import DerivError
    with pytest.raises(DerivError):
        run(b.connect())


def test_dry_run_never_buys(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"}, mode="dry")
    run(start_and_tick(tr, clock, 2))
    assert fake.contracts == {} and j.orders() == []
    assert not any("buy" in r for r in fake.requests)
    assert [e for e in j.events() if e["kind"] == "dry_run_order"]


def test_frozen_candidate_is_verified(tmp_path):
    c, s = cand.load("f1_london_breakout_r5")
    assert s.timeframe == "1h" and not cand.is_graduated(c.id)
    root = tmp_path / "incubator"
    shutil.copytree(Path(cand.INCUBATOR), root)
    f = root / "candidates" / "f1_london_breakout_r5" / "code" / "families.py"
    f.write_text(f.read_text() + "\n# edited\n")
    from fxbot.incubator.registry import TamperedError
    with pytest.raises(TamperedError):
        cand.load("f1_london_breakout_r5", root)


def test_leader_resolution(tmp_path):
    root = tmp_path
    (root / "records").mkdir()
    import json
    (root / "records" / "index.json").write_text(json.dumps({"candidates": {
        "a": {"status": "waiting"}, "b": {"status": "active", "measured": {"net_profit": 1.0}},
        "c": {"status": "active", "measured": {"net_profit": 3.0}}, "d": {"status": "dead"}}}))
    assert cand.resolve_id("leader", "fb", root) == ("c", "incubator leader")
    (root / "records" / "index.json").write_text(json.dumps({"candidates": {"a": {"status": "waiting"}}}))
    assert cand.resolve_id("leader", "fb", root)[0] == "fb"
    assert cand.resolve_id("x1", "fb", root) == ("x1", "STRATEGY_ID")


# ============================================================================ Telegram and journal
def test_commands_only_from_owner_chat(tmp_path):
    j = Journal(tmp_path / "j.sqlite")
    tg = FakeTelegram("42")
    called = []
    cmd = Commander(tg, j, tmp_path, lambda: called.append(1) or "stopped", clock=Clock())
    tg.push("/stop", chat="999")
    cmd.poll_once()
    assert called == [] and tg.sent == []
    assert any(e["kind"] == "command_ignored" for e in j.events())


def test_old_commands_are_not_replayed(tmp_path):
    j = Journal(tmp_path / "j.sqlite")
    tg = FakeTelegram()
    called = []
    cmd = Commander(tg, j, tmp_path, lambda: called.append(1) or "", clock=Clock())
    tg.push("/stop", date=MON_10 - 3600)
    cmd.poll_once()
    assert called == []


def test_status_open_report_export(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(start_and_tick(tr, clock))
    tr.write_status(clock())
    tr.heartbeat(clock())
    tg = FakeTelegram()
    cmd = Commander(tg, j, tmp_path, lambda: "", clock=clock)
    for c in ("/status", "/balance", "/open", "/report", "/export", "/nonsense"):
        tg.push(c)
    cmd.poll_once()
    text = "\n".join(tg.sent)
    assert "running" in text and "EUR/USD Up x100" in text and "Kill switch at 50.00" in text
    assert "Closed trades: 0" in text and "Unknown command" in text
    names = [d[0] for d in tg.docs]
    assert any(x.startswith("orders_") for x in names) and any(x.startswith("quotes_") for x in names)
    assert b"rate_pct" in dict(tg.docs)[[x for x in names if x.startswith("quotes_")][0]]


def test_hourly_cost_sampling(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    tr.cost_sampling = True
    clock.t = H10 + 5 * 60 + 3
    run(tr.connect())
    run(tr.sample_costs(clock()))
    run(tr.sample_costs(clock()))                            # once per hour only
    q = [x for x in j.quotes() if x["purpose"] == "hourly_sample"]
    assert len(q) == 6
    eur = [x for x in q if x["symbol"] == "frxEURUSD" and x["multiplier"] == 100][0]
    assert eur["rate"] == pytest.approx(BASE["frxEURUSD"], rel=1e-4)


def test_forced_test_trade_goes_through_risk(tmp_path):
    tr, fake, j, n, clock = make(tmp_path)
    (tmp_path / "requests").mkdir()
    import json
    (tmp_path / "requests" / "test_trade_1.json").write_text(json.dumps(
        {"symbol": "frxUSDJPY", "direction": "MULTDOWN", "hold_minutes": 5}))
    run(start_and_tick(tr, clock))
    o = j.orders()[0]
    assert o["test"] == 1 and o["state"] == "open" and o["stake"] == 3.0
    clock.t += 6 * 60
    run(tr.tick(clock()))
    assert j.orders()[0]["state"] == "closed" and j.orders()[0]["close_reason"] == "forced_deadline"


def test_every_message_is_journalled(tmp_path):
    tr, fake, j, n, clock = make(tmp_path, {("frxEURUSD", H10): "MULTUP"})
    run(start_and_tick(tr, clock))
    assert [e for e in j.events(kinds=("telegram",)) if "Trade opened" in e["detail"]["text"]]
