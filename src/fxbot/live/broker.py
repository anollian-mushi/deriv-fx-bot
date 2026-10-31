"""Deriv trading connection for the live bot (docs/deriv_api_notes.md).

Login: REST with the PAT + Deriv-App-ID lists the accounts and returns a
one-time WebSocket URL (OTP URL) for one account. Every connect, including
every reconnect, asks for a NEW OTP URL; an old one is never reused. The URL
is a password and is never printed, logged or journalled.

Demo by default: the account must be account_type "demo" and the URL must
end in /ws/demo. Real only when the caller passes mode="real" (which the
bot only does after its real-money checks), and then the URL must end in
/ws/real.

Buying: proposal first, then buy that exact proposal id at its ask price
(a proposal id cannot be bought twice). buy() needs a BuyTicket from
fxbot.risk.live. A lost buy reply is never resent: the bot marks the order
"unknown" and reconciliation checks the statement first.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

from fxbot.config import Settings
from fxbot.deriv import api
from fxbot.deriv.api import DerivError
from fxbot.risk.live import BuyTicket, TicketError

log = logging.getLogger(__name__)


class BrokerDisconnected(ConnectionError):
    """The trading connection dropped or a reply did not arrive. Reconnect and reconcile."""


async def _stream_connect(url: str):
    from fxbot.deriv.stream import StreamClient
    client = StreamClient(url)
    await client.__aenter__()
    return client


def choose_account(accounts: list[dict], mode: str, preferred_id: str | None = None) -> dict:
    if mode == "demo":
        return api.choose_demo_account(accounts, preferred_id)
    if mode != "real":
        raise DerivError("BadMode", "mode must be demo or real")
    if preferred_id:
        match = [a for a in accounts if a.get("account_id") == preferred_id]
        if not match or match[0].get("account_type") != "real":
            raise DerivError("NotReal", "DERIV_ACCOUNT_ID is not a real account of this token")
        return match[0]
    real = [a for a in accounts if a.get("account_type") == "real" and a.get("status", "active") == "active"]
    if not real:
        raise DerivError("NoRealAccount", "this token has no active real account")
    return real[0]


def url_matches_mode(url: str, mode: str) -> bool:
    p = urlparse(url)
    return p.scheme == "wss" and p.path.rstrip("/").endswith(f"/ws/{mode}")


def parse_shortcode(code: str) -> dict:
    """MULTUP_FRXEURUSD_1.00_100_1793205612_... -> type, symbol, stake, multiplier, purchase time."""
    parts = (code or "").split("_")
    try:
        sym = parts[1]
        return {"contract_type": parts[0], "symbol": "frx" + sym[3:] if sym.startswith("FRX") else sym,
                "stake": float(parts[2]), "multiplier": int(float(parts[3])), "purchase_time": int(parts[4])}
    except (IndexError, ValueError):
        return {}


class Broker:
    def __init__(self, settings: Settings, mode: str = "demo",
                 connect: Callable[[str], Awaitable[Any]] = _stream_connect,
                 rest_transport=None, clock=time.time, timeout: float = 30.0):
        if mode not in ("demo", "real"):
            raise ValueError("mode must be demo or real")
        self.settings, self.mode, self._connect = settings, mode, connect
        self.rest_transport, self.clock, self.timeout = rest_transport, clock, timeout
        self.conn: Any = None
        self.account_id: str | None = None
        self.currency = "USD"
        self.connects = 0

    # ------------------------------------------------------------------ connection
    async def connect(self) -> None:
        await self.close()
        accounts = await asyncio.to_thread(api.list_accounts, self.settings, self.rest_transport)
        acct = choose_account(accounts, self.mode, self.settings.deriv_account_id)
        if acct.get("account_type") != self.mode:
            raise DerivError("WrongAccount", f"chosen account is not a {self.mode} account; refusing")
        url = await asyncio.to_thread(api.create_otp_url, self.settings, acct["account_id"], self.rest_transport)
        if not url_matches_mode(url, self.mode):
            raise DerivError("WrongGateway", f"one-time URL is not for the {self.mode} gateway; refusing")
        self.conn = await self._connect(url)
        self.account_id = acct["account_id"]
        self.currency = acct.get("currency") or "USD"
        self.connects += 1

    @property
    def alive(self) -> bool:
        return self.conn is not None and getattr(self.conn, "alive", True)

    async def close(self) -> None:
        if self.conn is not None:
            try:
                await self.conn.__aexit__(None, None, None)
            except Exception:
                pass
            self.conn = None

    async def request(self, payload: dict, timeout: float | None = None) -> dict:
        if not self.alive:
            raise BrokerDisconnected("not connected")
        try:
            return await self.conn.request(payload, timeout or self.timeout)
        except DerivError:
            raise
        except (asyncio.TimeoutError, TimeoutError) as err:
            raise BrokerDisconnected(f"no reply to {next(iter(payload))}") from err
        except Exception as err:          # ConnectionClosed, OSError, ConnectionError from the reader
            raise BrokerDisconnected(f"{type(err).__name__} during {next(iter(payload))}") from err

    # ------------------------------------------------------------------ calls
    async def balance(self) -> dict:
        return (await self.request({"balance": 1}))["balance"]

    async def proposal(self, symbol: str, direction: str, stake: float, multiplier: int,
                       limit_order: dict | None = None) -> dict:
        req = {"proposal": 1, "amount": round(stake, 2), "basis": "stake", "contract_type": direction,
               "currency": self.currency, "underlying_symbol": symbol, "multiplier": multiplier}
        if limit_order:
            req["limit_order"] = limit_order
        return (await self.request(req))["proposal"]

    async def buy(self, ticket: BuyTicket) -> dict:
        if not isinstance(ticket, BuyTicket):
            raise TicketError("buy needs a BuyTicket from fxbot.risk.live")
        ticket.redeem(self.clock())
        return (await self.request({"buy": ticket.proposal_id, "price": ticket.ask_price}))["buy"]

    async def sell(self, contract_id: int) -> dict:
        return (await self.request({"sell": int(contract_id), "price": 0}))["sell"]

    async def contract(self, contract_id: int) -> dict:
        reply = await self.request({"proposal_open_contract": 1, "contract_id": int(contract_id)})
        return reply.get("proposal_open_contract") or {}

    async def portfolio(self) -> list[dict]:
        reply = await self.request({"portfolio": 1})
        return (reply.get("portfolio") or {}).get("contracts") or []

    async def statement(self, date_from: int, limit: int = 100) -> list[dict]:
        reply = await self.request({"statement": 1, "description": 1, "limit": limit, "date_from": int(date_from)})
        return (reply.get("statement") or {}).get("transactions") or []
