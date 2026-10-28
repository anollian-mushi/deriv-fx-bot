"""Phase 2: what the REAL account is offered on Multipliers. QUOTES ONLY.

Approved by the owner on 2026-10-28 for quotes only. This script:
- sends only read-only requests (price quotes, contract lists, symbol lists,
  server time). Every outgoing message passes through ReadOnlyWebSocket,
  which refuses anything else before it leaves the machine;
- contains no order, close or order-change requests at all
  (tests/test_check_real_quotes.py checks the source for them);
- refuses to run when DERIV_MODE=real, so it can never be mistaken for, or
  run alongside, a real-money bot setup;
- never prints the token or the one-time URL (the URL is a password).

It runs the same quote grid as scripts/sample_proposals.py through the real
account's own WebSocket and writes
  research/phase2/proposals_<YYYYmmddTHHMM>Z_<label>_real.jsonl.gz
which scripts/build_contract_specs.py compares with demo.

Run: python scripts/check_real_quotes.py [--label NAME]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from contextlib import asynccontextmanager
from typing import Any
from urllib.parse import urlparse

import _bootstrap  # noqa: F401
from websockets.asyncio.client import connect

from fxbot.config import load_settings
from fxbot.deriv.api import create_otp_url, list_accounts
from sample_proposals import report, run

# The only request types this script may send.
ALLOWED_REQUESTS = frozenset({"proposal", "contracts_for", "active_symbols", "time", "ping"})


class RefusedRequest(RuntimeError):
    pass


def check_request(raw: str) -> None:
    """Raise unless the outgoing message is one allowed read-only request."""
    msg = json.loads(raw)
    kinds = set(msg) - {"req_id", "passthrough"}
    request_type = next((k for k in msg if k in ALLOWED_REQUESTS), None)
    if request_type is None:
        raise RefusedRequest(f"request type not allowed: {sorted(kinds)[:3]}")
    if msg.get("subscribe"):
        raise RefusedRequest("subscriptions are not allowed")


class ReadOnlyWebSocket:
    """Wraps a WebSocket; send() refuses anything but ALLOWED_REQUESTS."""

    def __init__(self, ws: Any):
        self._ws = ws

    async def send(self, raw: str) -> None:
        check_request(raw)
        await self._ws.send(raw)

    async def recv(self) -> str:
        return await self._ws.recv()


def real_account_id() -> str:
    settings = load_settings()
    if settings.deriv_mode == "real":
        raise SystemExit("DERIV_MODE is real. This quotes-only check refuses to run in real mode.")
    real = [a for a in list_accounts(settings)
            if a.get("account_type") == "real" and a.get("status", "active") == "active"]
    if not real:
        raise SystemExit("This token has no active real account.")
    return real[0]["account_id"]


def is_real_ws_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "wss" and parsed.path.rstrip("/").endswith("/ws/real")


def make_opener(account_id: str):
    settings = load_settings()

    @asynccontextmanager
    async def open_ws():
        url = create_otp_url(settings, account_id)  # fresh one-time URL per connection
        if not is_real_ws_url(url):
            raise SystemExit("One-time URL is not for the real gateway. Stopping.")
        try:
            ws_cm = connect(url, open_timeout=20, ping_interval=30)
            ws = await ws_cm.__aenter__()
        except Exception as err:  # the message could contain the URL: show the type only
            raise SystemExit(f"Could not connect ({type(err).__name__})") from None
        try:
            yield ReadOnlyWebSocket(ws)
        finally:
            await ws_cm.__aexit__(None, None, None)

    return open_ws


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", default="quotes")
    args = parser.parse_args()
    account_id = real_account_id()
    print("Using the real account for QUOTES ONLY (no orders possible from this script).")
    t0 = time.time()
    path = asyncio.run(run(args.label, "real", make_opener(account_id)))
    report(path, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
