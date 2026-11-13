"""cTrader DEMO account: list open positions, and close the ones named on the command line.

    python scripts/ctrader_positions.py                  # list only
    python scripts/ctrader_positions.py --close 302958132 [...]   # close these (needs TRADING_ENABLED=true)

Demo only (the adapter refuses anything cTrader does not report as demo). Amounts in USD.
"""

import argparse
import asyncio
import sys

import _bootstrap  # noqa: F401

from fxbot.config import load_settings
from fxbot.ctrader.settings import load_ctrader_settings, mask_id


async def run(close: list[str]) -> int:
    from fxbot.broker.ctrader import CTraderBroker
    settings = load_ctrader_settings()
    if settings.missing():
        print("cTrader credentials are missing: " + ", ".join(settings.missing()))
        return 2
    if close and not load_settings().trading_enabled:
        print("TRADING_ENABLED is not true: listing only, nothing is closed.")
        close = []
    b = CTraderBroker(settings)
    try:
        info = await b.connect()
        print(f"DEMO account {mask_id(info.account_id)}, balance {info.balance:.2f} USD "
              f"(account currency {b.account_currency})")
        open_ = await b.positions()
        print(f"open positions: {len(open_)}")
        for p in open_:
            print(f"  ref {p.ref} {p.direction} {p.size:g} units {p.symbol} at {p.entry_price} "
                  f"SL {p.stop_loss_price} TP {p.take_profit_price} open profit {p.open_profit_usd:.2f}")
        for ref in close:
            r = await b.close_position(ref)
            print(f"close {ref}: open={r.is_open} exit {r.exit_price} profit {r.profit_usd} costs {r.cost_usd} "
                  f"reason {r.close_reason}")
        if close:
            left = [p.ref for p in await b.positions() if p.ref in close]
            print("still open:", left or "none")
            return 1 if left else 0
        return 0
    finally:
        await b.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--close", nargs="*", default=[])
    return asyncio.run(run(ap.parse_args().close))


if __name__ == "__main__":
    sys.exit(main())
