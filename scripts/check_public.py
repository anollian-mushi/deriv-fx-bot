"""Phase 0 check: public market data (no login needed).

Lists active forex symbols, then confirms the symbols, trading hours and
Multiplier details for EUR/USD, GBP/USD and USD/JPY. Read-only: it asks for
price quotes but never buys anything.

Run: python scripts/check_public.py
"""

import asyncio
import sys

import _bootstrap  # noqa: F401
from websockets.asyncio.client import connect

from fxbot.deriv.api import WS_PUBLIC_URL, DerivError, ws_request

TARGETS = ("EUR/USD", "GBP/USD", "USD/JPY")
QUOTE_STAKE = 10  # USD, only used to ask for a sample price quote


def find_trading_times(markets: list[dict], symbol: str) -> dict | None:
    for market in markets:
        for submarket in market.get("submarkets", []):
            for entry in submarket.get("symbols", []):
                if entry.get("underlying_symbol") == symbol:
                    return entry
    return None


async def main() -> int:
    async with connect(WS_PUBLIC_URL, open_timeout=20) as ws:
        print(f"Connected to {WS_PUBLIC_URL}\n")

        symbols = (await ws_request(ws, {"active_symbols": "brief"}))["active_symbols"]
        forex = sorted(
            (s for s in symbols if s["market"] == "forex"),
            key=lambda s: (s["submarket"], s["underlying_symbol"]),
        )
        print(f"Active forex symbols: {len(forex)} (of {len(symbols)} symbols in total)")
        print(f"  {'symbol':<12} {'name':<9} {'submarket':<12} open  suspended")
        for s in forex:
            print(
                f"  {s['underlying_symbol']:<12} {s['underlying_symbol_name']:<9} "
                f"{s['submarket']:<12} {'yes' if s['exchange_is_open'] else 'no ':<5} "
                f"{'YES' if s['is_trading_suspended'] else 'no'}"
            )

        by_name = {s["underlying_symbol_name"]: s for s in forex}
        times = (await ws_request(ws, {"trading_times": "today"}))["trading_times"]["markets"]

        ok = True
        for name in TARGETS:
            print(f"\n=== {name}")
            info = by_name.get(name)
            if not info:
                print("  NOT FOUND in active_symbols")
                ok = False
                continue
            symbol = info["underlying_symbol"]
            print(f"  symbol:      {symbol}  (pip size {info['pip_size']})")
            print(f"  market open: {'yes' if info['exchange_is_open'] else 'no'}, "
                  f"suspended: {'yes' if info['is_trading_suspended'] else 'no'}")

            tt = find_trading_times(times, symbol)
            if tt:
                hours = ", ".join(
                    f"{o}-{c}" for o, c in zip(tt["times"]["open"], tt["times"]["close"])
                )
                print(f"  hours (GMT): {hours} on {', '.join(tt.get('trading_days', []))}")
                for event in tt.get("events", []):
                    print(f"  note:        {event['descrip']} ({event['dates']})")
            else:
                print("  hours:       not listed in trading_times")

            available = (await ws_request(ws, {"contracts_for": symbol}))["contracts_for"]["available"]
            mult = {a["contract_type"]: a for a in available if a["contract_category"] == "multiplier"}
            if not {"MULTUP", "MULTDOWN"} <= mult.keys():
                print("  Multipliers: NOT offered")
                ok = False
                continue
            print(f"  Multipliers: up and down offered; contracts_for lists "
                  f"{mult['MULTUP'].get('multiplier_range')}")

            # Ask for a quote with an out-of-range multiplier on purpose: the
            # error message lists the multipliers the pricing engine accepts.
            accepted: list[int] = []
            try:
                await ws_request(ws, _quote(symbol, 1))
            except DerivError as err:
                tail = err.message.rsplit("Accepts", 1)
                if len(tail) == 2:
                    accepted = [int(x) for x in tail[1].strip(" .").split(",") if x.strip().isdigit()]
            print(f"  pricing accepts multipliers: {accepted or 'unknown'}")

            if not accepted:
                continue
            m = accepted[0]
            p = (await ws_request(ws, _quote(symbol, m)))["proposal"]
            stop_out = p["limit_order"]["stop_out"]
            vp = p["validation_params"]
            print(f"  sample quote (stake {QUOTE_STAKE} USD, Up, x{m}, spot {p['spot']}):")
            print(f"    commission {p['commission']} USD "
                  f"({p['commission'] / (QUOTE_STAKE * m):.4%} of position size {QUOTE_STAKE * m} USD)")
            print(f"    stop out at {stop_out['value']} (loss {stop_out['order_amount']} USD)")
            print(f"    stake range {vp['stake']['min']}-{vp['stake']['max']} USD, "
                  f"stop loss {vp['stop_loss']['min']}-{vp['stop_loss']['max']}, "
                  f"take profit {vp['take_profit']['min']}-{vp['take_profit']['max']}")

    print("\nAll three pairs confirmed." if ok else "\nSome pairs could not be confirmed.")
    return 0 if ok else 1


def _quote(symbol: str, multiplier: int) -> dict:
    return {
        "proposal": 1,
        "amount": QUOTE_STAKE,
        "basis": "stake",
        "contract_type": "MULTUP",
        "currency": "USD",
        "underlying_symbol": symbol,
        "multiplier": multiplier,
    }


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
