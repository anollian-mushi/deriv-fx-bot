"""Emergency close for Telegram /stop, independent of the trading loop.

/stop must work even if the strategy loop is stuck, so this code never goes
through the Trader: it writes the HALT file first (no new order can pass the
live risk gate after that), then opens its OWN Deriv connection (fresh OTP
URL), and sells every contract the journal says the bot owns. A contract
already sold (by Deriv or by the trading loop) is recorded, never sold twice.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from fxbot.deriv.api import DerivError


def write_halt(path: Path, reason: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"{reason} ({time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())})\n")


async def close_all(broker, journal, reason: str = "telegram_stop") -> list[str]:
    """Sell every open bot contract. Returns one line per contract."""
    lines = []
    await broker.connect()
    try:
        for o in journal.orders(("open", "unknown")):
            cid = o["contract_id"]
            if not cid:
                lines.append(f"order {o['id']} ({o['symbol']}): buy unconfirmed; reconciliation settles it")
                continue
            poc = await broker.contract(cid)
            if not poc.get("is_sold"):
                try:
                    sold = await broker.sell(cid)
                    poc = await broker.contract(cid)
                    if not poc.get("is_sold"):
                        poc = {"sell_price": sold.get("sold_for"),
                               "profit": float(sold.get("sold_for", 0)) - float(o.get("buy_price") or o["stake"])}
                except DerivError as err:
                    poc = await broker.contract(cid)
                    if not poc.get("is_sold"):
                        lines.append(f"{o['symbol']} contract {cid}: Deriv refused to close: {err.message}")
                        continue
                why = reason
            else:
                why = "closed_by_deriv"
            profit = poc.get("profit")
            if profit is None and poc.get("sell_price") is not None:
                profit = float(poc["sell_price"]) - float(o.get("buy_price") or o["stake"])
            profit = round(float(profit or 0), 2)
            if journal.close_order(o["id"], why, profit, poc.get("sell_price"),
                                   poc.get("exit_spot") or poc.get("sell_spot"), poc.get("sell_time")):
                journal.event("close", o["symbol"], contract_id=cid, reason=why, profit=profit, by="stop")
            lines.append(f"{o['symbol']} contract {cid}: closed, {profit:+.2f} USD")
    finally:
        await broker.close()
    return lines


def stop_now(halt_path: Path, broker_factory, journal, timeout: float = 90.0) -> str:
    """Write HALT, then close everything on a fresh connection. Safe to call from any thread."""
    write_halt(halt_path, "stopped by Telegram /stop")
    journal.event("halt", reason="telegram /stop")
    try:
        lines = asyncio.run(asyncio.wait_for(close_all(broker_factory(), journal), timeout))
    except Exception as err:
        return (f"HALT written: no new trades. Closing failed ({type(err).__name__}: {err}); the bot keeps "
                "trying to close its trades every minute while halted. Check /open.")
    body = "\n".join(lines) if lines else "No open bot trades."
    return ("STOPPED. Trading is halted and stays halted after restarts until you clear it by hand "
            "(deploy/DEPLOY.md, 'Clear a halt').\n" + body)
