"""Phase 6 weekend test (CLAUDE.md "No weekend holding until the Phase 6 weekend test").

One 1 USD demo contract, EUR/USD, x100, stop loss 0.20 USD, opened on a
Friday before 20:00 UTC and held over the weekend. On Monday we record:
  - any charge over the weekend (every statement entry since the buy),
  - what the Monday gap did to the stop loss (Friday's last price, Monday's
    first price, the stop-loss level, the fill, and whether it slipped past
    the level or reached the stop out).

    python scripts/weekend_test.py open [--direction MULTUP]   Friday, before 20:00 UTC
    python scripts/weekend_test.py snapshot                    any time: contract + balance + statement
    python scripts/weekend_test.py check [--close]             Monday: full record (--close sells if still open)

Demo only: refuses unless DERIV_MODE=demo, TRADING_ENABLED=true, the account
is a demo account and the URL is the demo gateway. Everything goes to
research/phase6/weekend_test/. The live bot sees this contract as "not its
own": it counts it toward its limits and never closes it.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401

from fxbot.config import REPO_ROOT, load_settings
from fxbot.deriv.api import WS_PUBLIC_URL, choose_demo_account, create_otp_url, is_demo_ws_url, list_accounts
from fxbot.deriv.stream import StreamClient

OUT = REPO_ROOT / "research" / "phase6" / "weekend_test"
SYMBOL, STAKE, MULT, STOP_LOSS = "frxEURUSD", 1.0, 100, 0.20


def utc(ts) -> str:
    return dt.datetime.fromtimestamp(int(ts), dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if ts else ""


def demo_url() -> str:
    s = load_settings()
    if s.deriv_mode != "demo" or not s.trading_enabled:
        raise SystemExit("Needs DERIV_MODE=demo and TRADING_ENABLED=true. Demo only.")
    acct = choose_demo_account(list_accounts(s), s.deriv_account_id)
    url = create_otp_url(s, acct["account_id"])
    if acct.get("account_type") != "demo" or not is_demo_ws_url(url):
        raise SystemExit("Not a demo account / gateway. Refusing.")
    return url


def save(name: str, data) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / name
    p.write_text(json.dumps(data, indent=1, sort_keys=True, default=str) + "\n")
    return p


def load_open() -> dict:
    p = OUT / "open.json"
    if not p.exists():
        raise SystemExit("No open.json: run 'open' first.")
    return json.loads(p.read_text())


async def state(c: StreamClient, cid: int, since: int) -> dict:
    poc = (await c.request({"proposal_open_contract": 1, "contract_id": cid}))["proposal_open_contract"]
    bal = (await c.request({"balance": 1}))["balance"]
    st = (await c.request({"statement": 1, "description": 1, "limit": 100, "date_from": since}))["statement"]
    return {"at": utc(dt.datetime.now(dt.timezone.utc).timestamp()), "contract": poc, "balance": bal,
            "statement": st.get("transactions", [])}       # all entries: any weekend charge shows up here


async def cmd_open(direction: str) -> None:
    now = dt.datetime.now(dt.timezone.utc)
    if now.weekday() != 4 or now.hour >= 20:
        raise SystemExit(f"Open only on a Friday before 20:00 UTC (now {now:%a %H:%M} UTC).")
    if (OUT / "open.json").exists():
        raise SystemExit("A weekend test contract was already opened (open.json exists).")
    async with StreamClient(demo_url()) as c:
        prop = (await c.request({"proposal": 1, "amount": STAKE, "basis": "stake", "contract_type": direction,
                                 "currency": "USD", "underlying_symbol": SYMBOL, "multiplier": MULT,
                                 "limit_order": {"stop_loss": STOP_LOSS}}))["proposal"]
        bought = (await c.request({"buy": prop["id"], "price": prop["ask_price"]}))["buy"]
        cid = int(bought["contract_id"])
        await asyncio.sleep(3)
        st = await state(c, cid, int(bought["purchase_time"]) - 60)
    lo = st["contract"].get("limit_order") or {}
    rec = {"contract_id": cid, "symbol": SYMBOL, "direction": direction, "stake": STAKE, "multiplier": MULT,
           "stop_loss_usd": STOP_LOSS, "opened": utc(bought["purchase_time"]), "purchase_time": bought["purchase_time"],
           "proposal": prop, "buy": bought, "entry_spot": st["contract"].get("entry_spot"),
           "stop_loss_price": (lo.get("stop_loss") or {}).get("value"),
           "stop_out_price": (lo.get("stop_out") or {}).get("value"),
           "commission": st["contract"].get("commission"), "state_after_open": st}
    p = save("open.json", rec)
    print(f"Opened contract {cid}: {direction} {SYMBOL} x{MULT} stake {STAKE}, entry {rec['entry_spot']}, "
          f"stop loss at {rec['stop_loss_price']}, stop out at {rec['stop_out_price']}. Saved {p}")


async def cmd_snapshot() -> None:
    o = load_open()
    async with StreamClient(demo_url()) as c:
        st = await state(c, o["contract_id"], int(o["purchase_time"]) - 60)
    name = f"snapshot_{dt.datetime.now(dt.timezone.utc):%Y%m%d_%H%M}.json"
    save(name, st)
    poc = st["contract"]
    print(f"{name}: sold={poc.get('is_sold')} profit={poc.get('profit')} bid={poc.get('bid_price')} "
          f"spot={poc.get('current_spot')} statement entries={len(st['statement'])}")


async def candles(start: int, end: int) -> list[dict]:
    async with StreamClient(WS_PUBLIC_URL) as c:
        r = await c.request({"ticks_history": SYMBOL, "style": "candles", "granularity": 60,
                             "start": start, "end": str(end)})
    return r.get("candles") or []


async def cmd_check(close: bool) -> None:
    o = load_open()
    cid = o["contract_id"]
    async with StreamClient(demo_url()) as c:
        st = await state(c, cid, int(o["purchase_time"]) - 60)
        if close and not st["contract"].get("is_sold"):
            sold = (await c.request({"sell": cid, "price": 0}))["sell"]
            await asyncio.sleep(2)
            st = await state(c, cid, int(o["purchase_time"]) - 60)
            st["sold_by_us"] = sold
    poc = st["contract"]
    # Friday's last minutes and Monday's first minutes on the public feed
    fri = dt.datetime.fromtimestamp(o["purchase_time"], dt.timezone.utc).replace(hour=20, minute=40, second=0)
    fri_t = int(fri.timestamp())
    mon_t = int((fri + dt.timedelta(days=2, hours=3, minutes=20)).timestamp())    # Monday 00:00
    before = await candles(fri_t, fri_t + 20 * 60)
    after = await candles(mon_t, mon_t + 30 * 60)
    fri_close = before[-1]["close"] if before else None
    mon_open = after[0]["open"] if after else None
    up = o["direction"] == "MULTUP"
    sl = float(o["stop_loss_price"]) if o.get("stop_loss_price") else None
    exit_spot = poc.get("exit_spot") or poc.get("sell_spot")
    gap = None if fri_close is None or mon_open is None else mon_open - fri_close
    txs = [t for t in st["statement"] if t.get("contract_id") == cid]
    other = [t for t in st["statement"] if t.get("contract_id") != cid]
    rec = {
        "contract_id": cid, "checked": st["at"], "direction": o["direction"], "entry_spot": o["entry_spot"],
        "stop_loss_usd": STOP_LOSS, "stop_loss_price": sl, "stop_out_price": o.get("stop_out_price"),
        "friday_last_close": fri_close, "monday_first_open": mon_open,
        "gap_pips": round(gap / 0.0001, 1) if gap is not None else None,
        "gap_through_stop": (sl is not None and mon_open is not None and fri_close is not None
                             and ((up and mon_open <= sl < fri_close) or (not up and mon_open >= sl > fri_close))),
        "is_sold": poc.get("is_sold"), "sell_time": utc(poc.get("sell_time")), "exit_spot": exit_spot,
        "sell_price": poc.get("sell_price"), "profit": poc.get("profit"), "status": poc.get("status"),
        "fill_past_stop_pips": (round(((sl - float(exit_spot)) if up else (float(exit_spot) - sl)) / 0.0001, 1)
                                if sl and exit_spot else None),
        "loss_over_stake": poc.get("profit") is not None and float(poc["profit"]) < -STAKE - 1e-9,
        "statement_this_contract": txs,
        "statement_other_entries": other,
        "charges_besides_buy_and_sell": [t for t in txs if t.get("action_type") not in ("buy", "sell")],
        "candles_friday": before, "candles_monday": after, "raw_contract": poc,
    }
    p = save("result.json", rec)
    print(json.dumps({k: v for k, v in rec.items() if not k.startswith(("candles", "raw", "statement"))}, indent=1))
    print("Saved", p)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    o = sub.add_parser("open")
    o.add_argument("--direction", default="MULTUP", choices=["MULTUP", "MULTDOWN"])
    sub.add_parser("snapshot")
    c = sub.add_parser("check")
    c.add_argument("--close", action="store_true")
    a = ap.parse_args()
    if a.cmd == "open":
        asyncio.run(cmd_open(a.direction))
    elif a.cmd == "snapshot":
        asyncio.run(cmd_snapshot())
    else:
        asyncio.run(cmd_check(a.close))
    return 0


if __name__ == "__main__":
    sys.exit(main())
