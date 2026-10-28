import asyncio
import json

import httpx
import pytest

from fxbot.config import load_settings
from fxbot.deriv.api import (
    DerivError,
    choose_demo_account,
    create_otp_url,
    is_demo_ws_url,
    list_accounts,
    ws_request,
)

ACCOUNTS = [
    {"account_id": "ROT1", "account_type": "real", "status": "active"},
    {"account_id": "DOT1", "account_type": "demo", "status": "active"},
]
SETTINGS = load_settings(environ={"DERIV_APP_ID": "1", "DERIV_PAT": "pat-secret"}, env_file=None)


def test_choose_demo_account_picks_demo_automatically():
    assert choose_demo_account(ACCOUNTS)["account_id"] == "DOT1"


def test_choose_demo_account_refuses_real_account_id():
    with pytest.raises(DerivError) as err:
        choose_demo_account(ACCOUNTS, "ROT1")
    assert err.value.code == "NotDemo"


def test_choose_demo_account_unknown_id_and_no_demo():
    with pytest.raises(DerivError):
        choose_demo_account(ACCOUNTS, "DOT999")
    with pytest.raises(DerivError):
        choose_demo_account([ACCOUNTS[0]])


def test_is_demo_ws_url():
    assert is_demo_ws_url("wss://api.derivws.com/trading/v1/options/ws/demo?otp=x")
    assert not is_demo_ws_url("wss://api.derivws.com/trading/v1/options/ws/real?otp=x")
    assert not is_demo_ws_url("ws://api.derivws.com/trading/v1/options/ws/demo?otp=x")


def test_rest_calls_send_pat_and_app_id_headers():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if request.url.path.endswith("/otp"):
            return httpx.Response(200, json={"data": {"url": "wss://x/ws/demo?otp=1"}})
        return httpx.Response(200, json={"data": ACCOUNTS})

    transport = httpx.MockTransport(handler)
    assert list_accounts(SETTINGS, transport) == ACCOUNTS
    assert create_otp_url(SETTINGS, "DOT1", transport) == "wss://x/ws/demo?otp=1"
    assert seen[1].url.path == "/trading/v1/options/accounts/DOT1/otp"
    for request in seen:
        assert request.headers["Authorization"] == "Bearer pat-secret"
        assert request.headers["Deriv-App-ID"] == "1"


def test_rest_error_is_raised_without_token():
    transport = httpx.MockTransport(
        lambda r: httpx.Response(401, json={"errors": [{"code": "Unauthorized", "message": "bad"}]})
    )
    with pytest.raises(DerivError) as err:
        list_accounts(SETTINGS, transport)
    assert err.value.code == "Unauthorized"
    assert "pat-secret" not in str(err.value)


class FakeWS:
    def __init__(self, replies):
        self.sent = []
        self.replies = replies

    async def send(self, text):
        self.sent.append(json.loads(text))

    async def recv(self):
        req_id = self.sent[-1]["req_id"]
        reply = self.replies.pop(0)
        return json.dumps({**reply, "req_id": req_id} if reply.get("match") else reply)


def test_ws_request_skips_unrelated_messages():
    ws = FakeWS([{"msg_type": "tick"}, {"match": True, "balance": {"balance": 5}}])
    reply = asyncio.run(ws_request(ws, {"balance": 1}))
    assert reply["balance"]["balance"] == 5


def test_ws_request_raises_on_error():
    ws = FakeWS([{"match": True, "error": {"code": "InvalidToken", "message": "x"}}])
    with pytest.raises(DerivError) as err:
        asyncio.run(ws_request(ws, {"balance": 1}))
    assert err.value.code == "InvalidToken"
