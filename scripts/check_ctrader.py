"""Read-only cTrader check: log in to the DEMO account, print what the bot needs to know.

Needs CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, CTRADER_ACCESS_TOKEN (CTRADER_ACCOUNT_ID is
optional: without it the token's first demo account is used). Places no orders.
Prints: account type (demo / live as cTrader reports it), balance, the account id with all
but the last 3 digits hidden, the three majors' contract specs, a few closed 1h candles and
one live price. Never prints the secret or the token.

    python scripts/check_ctrader.py            # full check (needs credentials)
    python scripts/check_ctrader.py --probe    # no credentials: TLS + framing + an auth request
                                               # with dummy credentials, which must be refused
"""

import argparse
import asyncio
import datetime as dt
import sys

import _bootstrap  # noqa: F401

from fxbot.config import ConfigError
from fxbot.ctrader.client import CTraderClient
from fxbot.ctrader.errors import CTraderDisconnected, CTraderError, CTraderTimeout
from fxbot.ctrader.settings import CTraderSettings, load_ctrader_settings, mask_id
from fxbot.symbols import MAJORS


async def probe() -> int:
    """Without credentials: does the demo endpoint answer our Protobuf frames as documented?"""
    dummy = CTraderSettings(client_id="fxbot-probe-invalid-id", client_secret="fxbot-probe-invalid-secret",
                            access_token=None, account_id=None)
    client = CTraderClient(dummy, auto_reconnect=False, request_timeout=15)
    print(f"Connecting to {client.host}:{client.port} (TLS, Protobuf)"
          + (" through the HTTPS proxy" if client._proxy else "") + " ...")
    try:
        await client.open()
    except CTraderDisconnected as err:
        print(f"FAILED: {err}")
        return 1
    print("TLS connection: OK")
    ok = True
    try:
        version = await client.version()
        print(f"ProtoOAVersionReq -> server version {version}")
    except CTraderError as err:
        print(f"ProtoOAVersionReq -> error reply {err.code} ({err.description})")
    except (CTraderTimeout, CTraderDisconnected) as err:
        print(f"ProtoOAVersionReq -> {type(err).__name__}: {err}")
    try:
        await client.application_auth()
        print("UNEXPECTED: dummy credentials were accepted")
        ok = False
    except CTraderError as err:
        print(f"ProtoOAApplicationAuthReq (dummy credentials) -> {err.code}: {err.description}")
        expected = err.code in ("CH_CLIENT_AUTH_FAILURE", "CH_OA_CLIENT_NOT_FOUND")
        print("Documented refusal received: " + ("YES" if expected else "NO (unexpected code)"))
        ok = ok and expected
    except (CTraderTimeout, CTraderDisconnected) as err:
        print(f"ProtoOAApplicationAuthReq -> {type(err).__name__}: {err}")
        ok = False
    await client.close()
    return 0 if ok else 1


async def check() -> int:
    try:
        settings = load_ctrader_settings()
    except ConfigError as err:
        print(f"Settings problem: {err}")
        return 2
    print("Settings:", ", ".join(f"{k}={v}" for k, v in settings.summary().items()))
    missing = settings.missing()
    if missing:
        print("cTrader credentials are missing: " + ", ".join(missing) + ".")
        print("See docs/ctrader_api_notes.md (section 'Getting credentials'). "
              "Run with --probe to test the connection without them.")
        return 2
    from fxbot.broker.ctrader import CTraderBroker
    broker = CTraderBroker(settings)
    try:
        info = await broker.connect()
    except Exception as err:  # BrokerError / BrokerDisconnected
        print(f"Login refused or failed: {type(err).__name__}: {err}")
        await broker.close()
        return 1
    try:
        trader = await broker.client.trader()
        print(f"Account {mask_id(info.account_id)}: {'DEMO' if info.is_demo else 'LIVE'} "
              f"(cTrader isLive=False checked), broker {trader.brokerName or '?'}, "
              f"currency {info.currency}, balance {info.balance:.2f}, equity {info.equity:.2f}, "
              f"leverage 1:{trader.leverageInCents / 100:g}")
        for symbol in MAJORS:
            spec = await broker.symbol_spec(symbol)
            print(f"\n{symbol} -> cTrader {spec['broker_symbol']} (id {spec['symbol_id']})")
            for key in ("digits", "pip_position", "pip", "min_units", "step_units", "max_units", "lot_units",
                        "commission_type", "commission_rate", "min_commission", "swap_long", "swap_short",
                        "swap_calculation_type", "swap_triple_day", "sl_distance", "trading_mode",
                        "pnl_conversion_fee_rate"):
                print(f"  {key}: {spec[key]}")
            bars = await broker.candles(symbol, "1h", 3)
            for i in range(len(bars)):
                t = dt.datetime.fromtimestamp(int(bars.epoch[i]), dt.timezone.utc)
                print(f"  1h {t:%Y-%m-%d %H:%M} O {bars.open[i]} H {bars.high[i]} L {bars.low[i]} "
                      f"C {bars.close[i]}")
            bid, ask, epoch = await broker.price(symbol)
            t = dt.datetime.fromtimestamp(epoch, dt.timezone.utc)
            print(f"  price {t:%H:%M:%S} bid {bid} ask {ask} spread {(ask - bid) / spec['pip']:.1f} pips")
    finally:
        await broker.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--probe", action="store_true", help="no credentials: transport and encoding check")
    args = parser.parse_args()
    return asyncio.run(probe() if args.probe else check())


if __name__ == "__main__":
    sys.exit(main())
