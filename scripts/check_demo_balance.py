"""Phase 0 check: log in to the DEMO account and print its balance.

Uses DERIV_APP_ID and DERIV_PAT. DERIV_ACCOUNT_ID is optional: if it is set it
must be a demo account; if not, the first active demo account is used.
Refuses to touch a real-money account. Read-only: places no orders.
Never prints the token or the one-time WebSocket URL.

Run: python scripts/check_demo_balance.py
"""

import asyncio
import sys

import _bootstrap  # noqa: F401
from websockets.asyncio.client import connect

from fxbot.config import ConfigError, load_settings
from fxbot.deriv.api import (
    DerivError,
    choose_demo_account,
    create_otp_url,
    is_demo_ws_url,
    list_accounts,
    ws_request,
)


async def main() -> int:
    try:
        settings = load_settings()
    except ConfigError as err:
        print(f"Settings problem: {err}")
        return 1
    print("Settings:", ", ".join(f"{k}={v}" for k, v in settings.summary().items()))
    if not settings.deriv_pat or not settings.deriv_app_id:
        print("DERIV_PAT and DERIV_APP_ID are both needed. Stopping.")
        return 1

    try:
        accounts = list_accounts(settings)
        print(f"\nOptions trading accounts for this token: {len(accounts)}")
        for a in accounts:
            print(f"  {a.get('account_id')}  {a.get('account_type'):<4}  {a.get('status'):<8}  "
                  f"{a.get('currency')}  group={a.get('group')}")

        account = choose_demo_account(accounts, settings.deriv_account_id)
        source = "from DERIV_ACCOUNT_ID" if settings.deriv_account_id else "picked automatically"
        print(f"\nUsing demo account {account['account_id']} ({source})")

        otp_url = create_otp_url(settings, account["account_id"])
        if not is_demo_ws_url(otp_url):
            print("The one-time URL is not for the demo gateway. Refusing to connect.")
            return 1
        print("Got a one-time demo WebSocket URL (not shown: it contains a password)")

        try:
            async with connect(otp_url, open_timeout=20) as ws:
                balance = (await ws_request(ws, {"balance": 1}))["balance"]
        except DerivError:
            raise
        except Exception as err:  # message could contain the OTP URL, so show the type only
            print(f"Could not connect to the demo WebSocket ({type(err).__name__})")
            return 1
        print(f"\nDemo balance: {balance['balance']:.2f} {balance['currency']} "
              f"(login id {balance['loginid']})")
        return 0
    except DerivError as err:
        print(f"Deriv error: {err}")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
