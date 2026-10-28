"""WebSocket client that handles requests and subscriptions on one connection.

ws_request() in api.py is fine for one-off calls. A trading session also needs
live streams (ticks, proposal_open_contract) while it sends requests, so this
client runs a reader task that:
- hands each reply to the request that is waiting for its req_id, and
- keeps every tick and contract update in memory for later inspection.

Works on both the public and the trading (OTP) WebSocket. The OTP URL is a
password: this class never prints or stores it.
"""

from __future__ import annotations

import asyncio
import itertools
import json
import time
from typing import Any

from websockets.asyncio.client import connect

from fxbot.deriv.api import DerivError


class StreamClient:
    def __init__(self, url: str):
        self._url = url
        self._ws: Any = None
        self._reader: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._ids = itertools.count(1)
        self.ticks: dict[str, list[dict]] = {}       # symbol -> ticks (with local receive time)
        self.contracts: dict[int, list[dict]] = {}   # contract_id -> proposal_open_contract updates
        self.transactions: list[dict] = []

    async def __aenter__(self) -> "StreamClient":
        self._ws = await connect(self._url, open_timeout=20, ping_interval=30)
        self._reader = asyncio.create_task(self._read())
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._reader:
            self._reader.cancel()
        if self._ws:
            await self._ws.close()

    async def _read(self) -> None:
        try:
            async for raw in self._ws:
                msg = json.loads(raw)
                msg["_received"] = time.time()
                kind = msg.get("msg_type")
                if kind == "tick" and msg.get("tick"):
                    t = msg["tick"]
                    self.ticks.setdefault(t["symbol"] if "symbol" in t else t.get("underlying_symbol"), []).append(
                        {**t, "_received": msg["_received"]})
                elif kind == "proposal_open_contract" and msg.get("proposal_open_contract"):
                    poc = msg["proposal_open_contract"]
                    if poc.get("contract_id"):
                        self.contracts.setdefault(int(poc["contract_id"]), []).append(
                            {**poc, "_received": msg["_received"]})
                elif kind == "transaction" and msg.get("transaction"):
                    self.transactions.append({**msg["transaction"], "_received": msg["_received"]})
                fut = self._pending.pop(msg.get("req_id"), None)
                if fut and not fut.done():
                    fut.set_result(msg)
        except Exception as err:  # connection closed: fail everyone still waiting
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError(type(err).__name__))
            self._pending.clear()

    async def request(self, payload: dict[str, Any], timeout: float = 30) -> dict[str, Any]:
        """Send one request, return its first reply. Raises DerivError on an error reply."""
        req_id = next(self._ids)
        fut = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut
        await self._ws.send(json.dumps({**payload, "req_id": req_id}))
        msg = await asyncio.wait_for(fut, timeout)
        error = msg.get("error")
        if error:
            raise DerivError(error.get("code", "Unknown"), error.get("message", ""))
        return msg

    def last_tick(self, symbol: str) -> dict | None:
        ticks = self.ticks.get(symbol)
        return ticks[-1] if ticks else None

    def last_contract(self, contract_id: int) -> dict | None:
        updates = self.contracts.get(contract_id)
        return updates[-1] if updates else None
