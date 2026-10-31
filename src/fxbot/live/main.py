"""Start the live bot: settings, real-money checks, candidate, journal, Telegram, trading loop.

Modes:
- dry:  TRADING_ENABLED is not true (or --dry-run). Quotes, signals, gate checks
        and would-be orders are journalled; nothing is bought. Uses the demo account.
- demo: TRADING_ENABLED=true and DERIV_MODE=demo. Any registered candidate may run.
- real: refused unless ALL of: DERIV_MODE=real, TRADING_ENABLED=true, the candidate
        has GRADUATED in the incubator, and CONFIRM_REAL=yes.
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
import signal
import sys
import time

from fxbot.live import candidate as cand
from fxbot.live.settings import LiveSettings

log = logging.getLogger("fxbot.live")


class ModeError(RuntimeError):
    pass


def decide_mode(ls: LiveSettings, graduated: bool, dry_run: bool = False) -> str:
    s = ls.base
    if s.deriv_mode == "real":
        missing = []
        if not s.trading_enabled:
            missing.append("TRADING_ENABLED=true")
        if not graduated:
            missing.append("a candidate that has GRADUATED in the incubator")
        if not ls.confirm_real:
            missing.append("CONFIRM_REAL=yes")
        if dry_run:
            missing.append("no --dry-run")
        if missing:
            raise ModeError("Refusing real money. Missing: " + ", ".join(missing) + ".")
        return "real"
    if dry_run or not s.trading_enabled:
        return "dry"
    return "demo"


def setup_logging(ls: LiveSettings) -> None:
    (ls.home / "logs").mkdir(parents=True, exist_ok=True)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for h in (logging.StreamHandler(sys.stderr), logging.handlers.WatchedFileHandler(ls.home / "logs" / "bot.log")):
        h.setFormatter(fmt)
        root.addHandler(h)
    for noisy in ("httpx", "websockets"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def ledger_start(journal, mode: str, ls: LiveSettings, deriv_balance: float | None) -> float:
    """The pretend ledger's start, fixed at the first start of this journal. Mixing modes is refused."""
    if mode == "dry":
        rec = journal.get("ledger")
        return float(rec["start"]) if rec else ls.start_balance
    rec = journal.get("ledger")
    if rec:
        if rec["mode"] != mode:
            raise ModeError(f"This journal belongs to a {rec['mode']} ledger; use a fresh BOT_HOME for {mode}.")
        return float(rec["start"])
    start = ls.start_balance if mode == "demo" else float(deriv_balance or 0)
    if not 50 <= start <= 100:
        raise ModeError(f"Starting balance {start:.2f} USD is outside 50-100 USD (CLAUDE.md).")
    journal.set("ledger", {"mode": mode, "start": start, "since": time.time()})
    return start


async def amain(ls: LiveSettings, dry_run: bool = False, hours: float | None = None) -> int:
    from fxbot.data.collector import DerivCandleFeed
    from fxbot.live.broker import Broker
    from fxbot.live.candles import CandleStore
    from fxbot.live.journal import Journal
    from fxbot.live.stop import stop_now
    from fxbot.live.trader import SYMBOLS, Trader
    from fxbot.telegram.client import TelegramClient
    from fxbot.telegram.commands import Commander
    from fxbot.telegram.notifier import Notifier

    ls.home.mkdir(parents=True, exist_ok=True)
    journal = Journal(ls.journal_path)
    client = None
    if ls.base.telegram_bot_token and ls.base.telegram_chat_id:
        client = TelegramClient(ls.base.telegram_bot_token, ls.base.telegram_chat_id)
    notifier = Notifier(client, journal)
    try:
        cid, how = cand.resolve_id(ls.strategy_id, ls.leader_fallback)
        c, strategy = cand.load(cid)              # verifies the frozen files against the fingerprint
        mode = decide_mode(ls, cand.is_graduated(cid), dry_run)
        broker_mode = "real" if mode == "real" else "demo"
        deriv_balance = None
        if mode == "real":
            b = Broker(ls.base, "real")
            await b.connect()
            deriv_balance = float((await b.balance())["balance"])
            await b.close()
        journal.start_balance = ledger_start(journal, mode, ls, deriv_balance)
    except Exception as err:
        journal.event("start_refused", error=f"{type(err).__name__}: {err}")
        notifier.send(f"Bot did NOT start: {type(err).__name__}: {err}", "error")
        notifier.flush()
        log.error("start refused: %s", err)
        return 2

    feed = DerivCandleFeed(min_interval=0.5)
    await feed.__aenter__()
    store = CandleStore(SYMBOLS, ls.data_dir, feed)
    broker = Broker(ls.base, broker_mode)
    trader = Trader(candidate_id=cid, strategy=strategy, broker=broker, store=store, journal=journal,
                    notifier=notifier, home=ls.home, mode=mode, start_balance=journal.start_balance,
                    cost_sampling=ls.cost_sampling, halt_path=ls.halt_path)
    commander = None
    if client:
        commander = Commander(client, journal, ls.home,
                              lambda: stop_now(ls.halt_path, lambda: Broker(ls.base, broker_mode), journal),
                              notifier)
        commander.start()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, trader.stop)

    warm = int(getattr(strategy, "warmup_days", 120)) + 5
    fetched = await store.warm_up(warm, time.time())
    journal.event("start", candidate=cid, chosen_by=how, fingerprint=c.fingerprint, mode=mode,
                  start_balance=journal.start_balance, warmup_days=warm, fetched_days=fetched)
    halted = trader.halted()
    notifier.send(
        f"Bot started: {mode.upper()} mode, candidate {cid} ({how}), fingerprint {c.fingerprint[:12]} checked. "
        f"Bot balance {journal.balance():.2f} USD (ledger start {journal.start_balance:.2f}). "
        + ("Orders are NOT sent (dry run). " if mode == "dry" else "")
        + (f"HALTED: {halted}. No trading until the halt is cleared by hand." if halted else ""), "start")
    try:
        await trader.run(time.time() + hours * 3600 if hours else None)
    finally:
        journal.event("stop", balance=journal.balance())
        notifier.send(f"Bot stopped. Bot balance {journal.balance():.2f} USD, "
                      f"{len(journal.open_orders())} bot trade(s) still open at Deriv with their stop loss / take "
                      "profit; they are checked again at the next start.", "stop")
        notifier.flush()
        await broker.close()
        await feed.__aexit__(None, None, None)
        if commander:
            commander.running = False
    return 0


def run(dry_run: bool = False, hours: float | None = None) -> int:
    from fxbot.live.settings import load_live_settings
    ls = load_live_settings()
    setup_logging(ls)
    return asyncio.run(amain(ls, dry_run, hours))
