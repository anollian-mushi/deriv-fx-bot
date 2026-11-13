"""cTrader DEMO lifecycle test: one trade at the minimum size, start to finish.

Steps: log in (refuses anything cTrader does not report as a demo account) -> quote at the
symbol's minimum size with a stop loss and take profit -> market order -> move both the
stop loss (closer) and the take profit -> close -> read the deals back and compare the
result with the balance change. The last step checks the commission assumptions written
in docs/ctrader_api_notes.md.

Needs the CTRADER_* settings and TRADING_ENABLED=true for this one command:
    TRADING_ENABLED=true python scripts/ctrader_lifecycle.py [frxEURUSD] [--sl 20] [--tp 40]

Risk: the stop loss caps the loss; the script refuses if the minimum size could lose more
than 3% of the demo balance. Demo money only; CTRADER_MODE=real is refused.
"""

import argparse
import asyncio
import sys
import time
import uuid

import _bootstrap  # noqa: F401

from fxbot.config import ConfigError, load_settings
from fxbot.ctrader.settings import load_ctrader_settings, mask_id

MAX_RISK = 0.03


def show(label, p):
    print(f"{label}: ref {p.ref} {p.direction} {p.size:g} units of {p.symbol} at {p.entry_price} "
          f"SL {p.stop_loss_price} TP {p.take_profit_price} open={p.is_open}"
          + (f" exit {p.exit_price} profit {p.profit_usd} reason {p.close_reason} costs {p.cost_usd}"
             if not p.is_open else f" open profit {p.open_profit_usd:.2f}"))


async def run(symbol: str, sl_pips: float, tp_pips: float) -> int:
    try:
        settings = load_ctrader_settings()
        trading_enabled = load_settings().trading_enabled
    except ConfigError as err:
        print(f"Settings problem: {err}")
        return 2
    missing = settings.missing()
    if missing:
        print("cTrader credentials are missing: " + ", ".join(missing)
              + ". See docs/ctrader_api_notes.md. Nothing was sent.")
        return 2
    if not trading_enabled:
        print("TRADING_ENABLED is not true. Refusing to place orders "
              "(set it for this one command: TRADING_ENABLED=true python scripts/ctrader_lifecycle.py).")
        return 2

    from fxbot.broker.ctrader import CTraderBroker
    from fxbot.broker.base import BrokerError, OrderIntent

    broker = CTraderBroker(settings)
    try:
        info = await broker.connect()
    except Exception as err:
        print(f"Login refused or failed: {type(err).__name__}: {err}")
        await broker.close()
        return 1
    if not info.is_demo:                      # connect() already refuses; belt and braces
        print("Not a demo account. Stopping.")
        await broker.close()
        return 1
    print(f"DEMO account {mask_id(info.account_id)}, balance {info.balance:.2f} {info.currency}"
          f" (account currency {getattr(broker, 'account_currency', info.currency)}; amounts shown in USD)")
    position = None
    try:
        inst = await broker.instrument(symbol)
        coid = "fxlc-" + uuid.uuid4().hex[:12]
        probe_q = await broker.quote(OrderIntent(symbol, "up", info.balance * MAX_RISK, sl_pips, tp_pips, None, coid))
        per_unit = probe_q.worst_case_loss_usd / probe_q.size
        allowed = per_unit * inst.min_size * 1.001 + 0.005
        if allowed > info.balance * MAX_RISK:
            print(f"The minimum size would risk {allowed:.2f} USD, more than 3% of the balance. Stopping.")
            return 1
        q = await broker.quote(OrderIntent(symbol, "up", allowed, sl_pips, tp_pips, None, coid))
        if q.size != inst.min_size:
            print(f"Sizing gave {q.size} units instead of the minimum {inst.min_size}. Stopping, no order sent.")
            return 1
        print(f"Quote: buy {q.size:g} units at about {q.price}, SL {q.stop_loss_price}, TP {q.take_profit_price}, "
              f"worst-case loss {q.worst_case_loss_usd:.2f} USD, cost {q.cost_usd:.4f} USD "
              f"({q.cost_pips:.2f} pips, spread {q.raw['spread_usd']:.4f} + commission "
              f"2 x {q.raw['commission_per_side_usd']:.4f})")
        balance_before = (await broker.account()).balance
        t_open = time.time()
        position = await broker.open(q)
        show("Opened", position)
        if position.stop_loss_price is None:
            print("WARNING: no stop loss on the position")
        pip = inst.pip
        new_sl = position.stop_loss_price + 5 * pip
        new_tp = position.take_profit_price + 5 * pip if position.take_profit_price else None
        position = await broker.modify(position.ref, stop_loss_price=new_sl, take_profit_price=new_tp)
        show("Amended", position)
        again = await broker.open(q) if time.time() < q.expires_epoch else position
        print(f"Repeat open with the same client order id returned ref {again.ref} "
              f"({'same position, idempotent' if again.ref == position.ref else 'DIFFERENT: investigate'})")
        closed = await broker.close_position(position.ref)
        show("Closed", closed)
        position = closed
        deals = await broker.client.deals_for_position(int(closed.ref))
        print(f"\n{len(deals)} deal(s) for position {closed.ref}:")
        for d in deals:
            line = (f"  deal {d.dealId} order {d.orderId} side {d.tradeSide} filled {d.filledVolume / 100:g} "
                    f"at {d.executionPrice} commission {d.commission} (moneyDigits {d.moneyDigits}) "
                    f"label {d.label!r}")
            if d.HasField("closePositionDetail"):
                c = d.closePositionDetail
                line += (f"\n    close detail: entry {c.entryPrice} gross {c.grossProfit} swap {c.swap} "
                         f"commission {c.commission} balance after {c.balance} conversion fee "
                         f"{c.pnlConversionFee if c.HasField('pnlConversionFee') else '-'}")
            print(line)
        balance_after = (await broker.account()).balance
        change = round(balance_after - balance_before, 2)
        print(f"\nBalance {balance_before:.2f} -> {balance_after:.2f} (change {change:+.2f}); "
              f"adapter's profit {closed.profit_usd:+.2f}")
        print("Commission check: " + ("MATCH" if abs(change - closed.profit_usd) < 0.015 else
                                      "MISMATCH: the commission reading in docs/ctrader_api_notes.md needs fixing"))
        hist = await broker.history(t_open - 60)
        print(f"history() since the open lists the position: {any(p.ref == closed.ref for p in hist)}")
        return 0
    except BrokerError as err:
        print(f"Broker refused: {err.code}: {err.message}")
        return 1
    finally:
        if position is not None and position.is_open:
            try:
                show("Safety close", await broker.close_position(position.ref))
            except Exception as err:
                print(f"COULD NOT CLOSE position {position.ref}: {err}. Close it in cTrader now.")
        await broker.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("symbol", nargs="?", default="frxEURUSD")
    parser.add_argument("--sl", type=float, default=20.0, help="stop loss in pips (default 20)")
    parser.add_argument("--tp", type=float, default=40.0, help="take profit in pips (default 40)")
    args = parser.parse_args()
    return asyncio.run(run(args.symbol, args.sl, args.tp))


if __name__ == "__main__":
    sys.exit(main())
