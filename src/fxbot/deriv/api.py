"""Small helpers for the Deriv API (see docs/deriv_api_notes.md).

Public market data: WebSocket at WS_PUBLIC_URL, no login.
Account data and trading: REST with a PAT + Deriv-App-ID to list accounts and
get a one-time WebSocket URL (OTP URL), then talk to that WebSocket.

The OTP URL contains a one-time password. Treat it like the PAT: never print
or log it.
"""

from __future__ import annotations

import itertools
import json
from typing import Any
from urllib.parse import urlparse

import httpx

from fxbot.config import Settings

REST_BASE = "https://api.derivws.com"
WS_PUBLIC_URL = "wss://api.derivws.com/trading/v1/options/ws/public"

_req_ids = itertools.count(1)


class DerivError(Exception):
    """An error returned by Deriv (REST or WebSocket)."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


async def ws_request(ws: Any, payload: dict[str, Any]) -> dict[str, Any]:
    """Send one request and return the reply with the matching req_id.

    Other messages on the connection (e.g. subscription updates) are skipped.
    Raises DerivError if the reply carries an error object.
    """
    req_id = next(_req_ids)
    await ws.send(json.dumps({**payload, "req_id": req_id}))
    while True:
        reply = json.loads(await ws.recv())
        if reply.get("req_id") != req_id:
            continue
        error = reply.get("error")
        if error:
            raise DerivError(error.get("code", "Unknown"), error.get("message", ""))
        return reply


def rest_headers(settings: Settings) -> dict[str, str]:
    if not settings.deriv_pat or not settings.deriv_app_id:
        raise DerivError("MissingSettings", "DERIV_PAT and DERIV_APP_ID are required")
    return {
        "Authorization": f"Bearer {settings.deriv_pat}",
        "Deriv-App-ID": settings.deriv_app_id,
    }


def _rest_data(response: httpx.Response) -> Any:
    try:
        body = response.json()
    except ValueError:
        body = {}
    if response.is_error:
        errors = body.get("errors") or [{}]
        first = errors[0]
        raise DerivError(
            str(first.get("code", f"HTTP{response.status_code}")),
            f"HTTP {response.status_code} {first.get('message', response.reason_phrase)}",
        )
    return body.get("data")


def _http(transport: httpx.BaseTransport | None) -> httpx.Client:
    return httpx.Client(base_url=REST_BASE, timeout=20, transport=transport)


def list_accounts(
    settings: Settings, transport: httpx.BaseTransport | None = None
) -> list[dict[str, Any]]:
    """GET /trading/v1/options/accounts -> list of Options trading accounts."""
    with _http(transport) as http:
        response = http.get("/trading/v1/options/accounts", headers=rest_headers(settings))
    return _rest_data(response) or []


def create_otp_url(
    settings: Settings, account_id: str, transport: httpx.BaseTransport | None = None
) -> str:
    """POST /trading/v1/options/accounts/{id}/otp -> one-time WebSocket URL. Secret."""
    with _http(transport) as http:
        response = http.post(
            f"/trading/v1/options/accounts/{account_id}/otp", headers=rest_headers(settings)
        )
    data = _rest_data(response) or {}
    url = data.get("url")
    if not url:
        raise DerivError("NoOtpUrl", "OTP response had no url")
    return url


def choose_demo_account(
    accounts: list[dict[str, Any]], preferred_id: str | None = None
) -> dict[str, Any]:
    """Pick the demo account to use. Never returns a real-money account.

    If preferred_id is given it must exist and be a demo account. Otherwise the
    first active demo account is used.
    """
    if preferred_id:
        match = [a for a in accounts if a.get("account_id") == preferred_id]
        if not match:
            raise DerivError("AccountNotFound", "DERIV_ACCOUNT_ID is not one of this token's accounts")
        if match[0].get("account_type") != "demo":
            raise DerivError("NotDemo", "DERIV_ACCOUNT_ID is not a demo account; refusing to use it")
        return match[0]
    demos = [
        a for a in accounts if a.get("account_type") == "demo" and a.get("status", "active") == "active"
    ]
    if not demos:
        raise DerivError("NoDemoAccount", "this token has no active demo account")
    return demos[0]


def is_demo_ws_url(url: str) -> bool:
    """True only for the demo trading gateway (…/ws/demo)."""
    parsed = urlparse(url)
    return parsed.scheme == "wss" and parsed.path.rstrip("/").endswith("/ws/demo")
