"""Phase 2: a few real contracts on the DEMO account to measure costs.

Demo money only. The script refuses to run unless ALL of these hold:
- TRADING_ENABLED=true (set it for this one command only)
- DERIV_MODE is demo (the default)
- the chosen account is account_type "demo" and the OTP URL goes to /ws/demo
- fewer than MAX_TRADES contracts are already logged in
  research/demo_cost_trades.csv
- the stake is the 1 USD minimum

Commands (each opens at most one contract):
  cycle SYMBOL DIRECTION MULT      buy, set TP+SL, change them, remove SL, sell
  tight SYMBOL DIRECTION MULT --tp X | --sl X
                                   buy with a tight take profit or stop loss
                                   and wait up to --wait minutes for Deriv to close it
  hold SYMBOL DIRECTION MULT       buy and leave open (overnight test)
  try SYMBOL DIRECTION MULT        try to buy at a multiplier pricing rejects;
                                   if Deriv accepts it, the contract is sold at once
  settle                           check every logged contract that is still
                                   open or unsettled; with --close also sell
                                   held contracts; fetches statement entries

Every contract gets one row in research/demo_cost_trades.csv. The raw replies
go to research/phase2/demo_raw/<contract_id>.json (login ids removed).

Run: TRADING_ENABLED=true python scripts/demo_cost_trades.py cycle frxEURUSD MULTUP 50
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import _bootstrap  # noqa: F401

from fxbot.config import ConfigError, load_settings
from fxbot.contracts.multiplier import price_at_profit, profit, stop_out_price
from fxbot.deriv.api import (
    DerivError,
    choose_demo_account,
    create_otp_url,
    is_demo_ws_url,
    list_accounts,
)
from fxbot.deriv.stream import StreamClient

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "research" / "demo_cost_trades.csv"
RAW_DIR = ROOT / "research" / "phase2" / "demo_raw"
MAX_TRADES = 20
STAKE = 1.0
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}

COLUMNS = [
    "trade_no", "kind", "symbol", "direction", "multiplier", "stake",
    "proposal_time_utc", "proposal_spot", "proposal_ask_price", "proposal_commission",
    "proposal_stop_out", "tick_before_buy_bid", "tick_before_buy_quote", "tick_before_buy_ask",
    "buy_latency_s", "contract_id", "buy_price", "entry_spot", "entry_time_utc",
    "entry_vs_proposal_pips", "entry_vs_tick_quote_pips", "commission", "stop_out",
    "stop_out_formula", "tp_sl_updates", "close_requested_bid", "close_requested_quote",
    "sell_price", "exit_spot", "exit_time_utc", "status", "close_reason", "profit",
    "profit_formula", "profit_diff", "sell_vs_last_bid", "held_hours", "notes",
]


def _utc(epoch: float | int | None) -> str:
    if not epoch:
        return ""
    return datetime.fromtimestamp(float(epoch), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _scrub(obj: Any) -> Any:
    """Drop login ids from raw replies before saving them."""
    if isinstance(obj, dict):
        return {k: _scrub(v) for k, v in obj.items() if k not in ("loginid", "binary_user_id")}
    if isinstance(obj, list):
        return [_scrub(v) for v in obj]
    return obj


def read_rows() -> list[dict]:
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows: list[dict]) -> None:
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CSV_PATH.with_suffix(".tmp")
    with tmp.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLUMNS})
    tmp.replace(CSV_PATH)


def save_raw(contract_id: int, raw: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / f"{contract_id}.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(_scrub(raw))
    path.write_text(json.dumps(old, indent=1, sort_keys=True))


def _pips(symbol: str, diff: float) -> float:
    return round(diff / PIP[symbol], 2)


# ---------------------------------------------------------------- safety gate

def open_demo_url() -> str:
    settings = load_settings()
    if not settings.trading_enabled:
        raise SystemExit("TRADING_ENABLED is not true. Refusing to place orders.")
    if settings.deriv_mode != "demo":
        raise SystemExit("DERIV_MODE is not demo. This script only trades the demo account.")
    account = choose_demo_account(list_accounts(settings), settings.deriv_account_id)
    if account.get("account_type") != "demo":
        raise SystemExit("Chosen account is not a demo account. Refusing.")
    url = create_otp_url(settings, account["account_id"])
    if not is_demo_ws_url(url):
        raise SystemExit("One-time URL is not for the demo gateway. Refusing.")
    return url


def check_budget(rows: list[dict]) -> None:
    bought = [r for r in rows if r.get("contract_id")]
    if len(bought) >= MAX_TRADES:
        raise SystemExit(f"{len(bought)} demo contracts already logged (cap {MAX_TRADES}). Stopping.")


# ---------------------------------------------------------------- helpers

async def wait_for(cond, timeout: float, step: float = 0.2) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        await asyncio.sleep(step)
    return cond()


async def buy(c: StreamClient, symbol: str, direction: str, mult: int,
              limit_order: dict | None = None) -> tuple[dict, dict]:
    """Quote, then buy that exact quote. Returns (row, raw)."""
    await c.request({"ticks": symbol, "subscribe": 1})
    await wait_for(lambda: len(c.ticks.get(symbol, [])) >= 2, 15)
    req = {"proposal": 1, "amount": STAKE, "basis": "stake", "contract_type": direction,
           "currency": "USD", "underlying_symbol": symbol, "multiplier": mult}
    if limit_order:
        req["limit_order"] = limit_order
    prop = (await c.request(req))["proposal"]
    tick = c.last_tick(symbol) or {}
    t0 = time.time()
    bought = (await c.request({"buy": prop["id"], "price": prop["ask_price"]}))["buy"]
    latency = time.time() - t0
    cid = int(bought["contract_id"])
    await c.request({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1})
    await wait_for(lambda: (c.last_contract(cid) or {}).get("entry_spot") is not None, 20)
    poc = c.last_contract(cid) or {}
    entry = float(poc.get("entry_spot") or 0)
    comm = float(poc.get("commission") or prop["commission"])
    stop_out = (poc.get("limit_order") or {}).get("stop_out", {}).get("value")
    row = {
        "symbol": symbol, "direction": direction, "multiplier": mult, "stake": STAKE,
        "proposal_time_utc": _utc(prop.get("spot_time")), "proposal_spot": prop["spot"],
        "proposal_ask_price": prop["ask_price"], "proposal_commission": prop["commission"],
        "proposal_stop_out": prop["limit_order"]["stop_out"]["value"],
        "tick_before_buy_bid": tick.get("bid"), "tick_before_buy_quote": tick.get("quote"),
        "tick_before_buy_ask": tick.get("ask"), "buy_latency_s": round(latency, 3),
        "contract_id": cid, "buy_price": bought["buy_price"], "entry_spot": entry or "",
        "entry_time_utc": _utc(poc.get("entry_tick_time") or poc.get("date_start")),
        "commission": comm, "stop_out": stop_out or "",
    }
    if entry:
        sign = 1 if direction == "MULTUP" else -1
        # positive = we got a worse entry than we were quoted
        row["entry_vs_proposal_pips"] = _pips(symbol, sign * (entry - prop["spot"]))
        if tick.get("quote"):
            row["entry_vs_tick_quote_pips"] = _pips(symbol, sign * (entry - tick["quote"]))
        row["stop_out_formula"] = round(stop_out_price(direction, STAKE, mult, entry, comm), 6)
    raw = {"proposal": prop, "buy": bought, "tick_before_buy": tick,
           "ticks_around_buy": [t for t in c.ticks.get(symbol, []) if abs(t["epoch"] - t0) < 30]}
    print(f"Bought #{cid}: {direction} {symbol} x{mult} stake {STAKE}, buy price {bought['buy_price']}, "
          f"quoted spot {prop['spot']}, entry spot {entry}, commission {comm}")
    return row, raw


async def update(c: StreamClient, cid: int, limit_order: dict) -> dict:
    reply = (await c.request({"contract_update": 1, "contract_id": cid, "limit_order": limit_order}))
    return reply["contract_update"]


def finish_row(row: dict, poc: dict) -> None:
    """Fill the close columns from a final proposal_open_contract."""
    symbol, direction, mult = row["symbol"], row["direction"], int(row["multiplier"])
    row["sell_price"] = poc.get("sell_price", "")
    row["exit_spot"] = poc.get("exit_spot") or poc.get("exit_tick") or poc.get("sell_spot") or ""
    row["exit_time_utc"] = _utc(poc.get("exit_tick_time") or poc.get("sell_time"))
    row["status"] = poc.get("status", "")
    row["profit"] = poc.get("profit", "")
    entry, comm = float(row["entry_spot"]), float(row["commission"])
    if row["exit_spot"]:
        f = profit(direction, STAKE, mult, entry, float(row["exit_spot"]), comm)
        row["profit_formula"] = round(f, 4)
        if row["profit"] != "":
            row["profit_diff"] = round(float(row["profit"]) - f, 4)
    if poc.get("date_start") and poc.get("sell_time"):
        row["held_hours"] = round((poc["sell_time"] - poc["date_start"]) / 3600, 3)
    lo = poc.get("limit_order") or {}
    if not row.get("close_reason"):
        # Deriv does not say why a contract closed in one field; work it out.
        exit_spot = float(row["exit_spot"] or 0)
        reason = "unknown"
        for key in ("take_profit", "stop_loss", "stop_out"):
            if key in lo and exit_spot:
                level = float(lo[key]["value"])
                hit = (exit_spot >= level) if (direction == "MULTUP") == (key == "take_profit") else (exit_spot <= level)
                if hit:
                    reason = key
        row["close_reason"] = reason


async def sell_now(c: StreamClient, row: dict) -> None:
    cid = int(row["contract_id"])
    symbol = row["symbol"]
    before = c.last_contract(cid) or {}
    tick = c.last_tick(symbol) or {}
    row["close_requested_bid"] = before.get("bid_price", "")
    row["close_requested_quote"] = tick.get("quote", "")
    sold = (await c.request({"sell": cid, "price": 0}))["sell"]
    await wait_for(lambda: (c.last_contract(cid) or {}).get("is_sold"), 20)
    poc = c.last_contract(cid) or {}
    if not poc.get("is_sold"):
        poc = (await c.request({"proposal_open_contract": 1, "contract_id": cid}))["proposal_open_contract"]
    row["close_reason"] = "manual sell"
    finish_row(row, poc)
    if row["close_requested_bid"] != "":
        row["sell_vs_last_bid"] = round(float(sold["sold_for"]) - float(row["close_requested_bid"]), 4)
    save_raw(cid, {"sell": sold, "last_update_before_sell": before, "final": poc,
                   "updates": c.contracts.get(cid, [])[-50:]})
    print(f"Sold #{cid} for {sold['sold_for']} (last bid seen {row['close_requested_bid']}), "
          f"profit {row['profit']}, formula {row.get('profit_formula')}")


def _limit_summary(upd: dict) -> dict:
    return {k: (v.get("order_amount"), v.get("value")) for k, v in upd.items() if isinstance(v, dict)}


# ---------------------------------------------------------------- commands

async def cmd_cycle(c: StreamClient, row: dict) -> None:
    cid = int(row["contract_id"])
    entry, comm, d, m = float(row["entry_spot"]), float(row["commission"]), row["direction"], int(row["multiplier"])
    steps = []
    for label, lo in (("set TP 0.50 + SL 0.50", {"take_profit": 0.5, "stop_loss": 0.5}),
                      ("change TP 0.80 + SL 0.30", {"take_profit": 0.8, "stop_loss": 0.3}),
                      ("remove SL", {"stop_loss": None})):
        upd = await update(c, cid, lo)
        s = _limit_summary(upd)
        check = {}
        if "take_profit" in upd:
            check["tp_formula"] = round(price_at_profit(d, STAKE, m, entry, float(upd["take_profit"]["order_amount"]), comm), 6)
        if "stop_loss" in upd:
            check["sl_formula"] = round(price_at_profit(d, STAKE, m, entry, float(upd["stop_loss"]["order_amount"]), comm), 6)
        steps.append({"step": label, "deriv": s, **check})
        print(f"  {label}: {s} {check}")
        await asyncio.sleep(2)
    # Confirm the open contract shows the final state, and read the history.
    await asyncio.sleep(2)
    hist = (await c.request({"contract_update_history": 1, "contract_id": cid}))["contract_update_history"]
    row["tp_sl_updates"] = json.dumps(steps, separators=(",", ":"))
    save_raw(cid, {"contract_update_steps": steps, "contract_update_history": hist})
    await asyncio.sleep(20)
    await sell_now(c, row)


async def cmd_tight(c: StreamClient, row: dict, wait_min: float) -> None:
    cid = int(row["contract_id"])
    print(f"  waiting up to {wait_min} min for Deriv to close it ...")
    done = await wait_for(lambda: (c.last_contract(cid) or {}).get("is_sold"), wait_min * 60, step=1)
    if not done:
        row["notes"] = (row.get("notes", "") + " still open after wait; run settle later").strip()
        print("  not closed yet; it keeps its TP/SL. Run 'settle' later.")
        return
    poc = c.last_contract(cid)
    finish_row(row, poc)
    lo = poc.get("limit_order") or {}
    save_raw(cid, {"final": poc, "updates": c.contracts.get(cid, [])[-80:],
                   "ticks_at_close": [t for t in c.ticks.get(row["symbol"], [])
                                      if abs(t["epoch"] - (poc.get("sell_time") or 0)) < 20]})
    print(f"  closed by Deriv: status {row['status']}, reason {row['close_reason']}, sell price "
          f"{row['sell_price']}, exit spot {row['exit_spot']}, profit {row['profit']}, limits {_limit_summary(lo)}")


async def cmd_settle(c: StreamClient, rows: list[dict], close: bool) -> None:
    for row in rows:
        if not row.get("contract_id") or row.get("status") in ("sold", "won", "lost"):
            continue
        cid = int(row["contract_id"])
        poc = (await c.request({"proposal_open_contract": 1, "contract_id": cid, "subscribe": 1}))["proposal_open_contract"]
        if poc.get("is_sold"):
            finish_row(row, poc)
            save_raw(cid, {"final": poc})
            print(f"#{cid} was closed by Deriv: {row['status']} {row['close_reason']} profit {row['profit']}")
        elif close and row["kind"] == "hold":
            await c.request({"ticks": row["symbol"], "subscribe": 1})
            await wait_for(lambda: c.last_tick(row["symbol"]) and c.last_contract(cid), 15)
            await sell_now(c, row)
        else:
            print(f"#{cid} still open: bid {poc.get('bid_price')} profit {poc.get('profit')}")
    # Statement for the whole test window: shows every charge Deriv made.
    first = min((r["proposal_time_utc"] for r in rows if r.get("proposal_time_utc")), default=None)
    if first:
        start = int(datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()) - 60
        st = (await c.request({"statement": 1, "description": 1, "limit": 100, "date_from": start}))["statement"]
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        (RAW_DIR / "statement.json").write_text(json.dumps(_scrub(st), indent=1, sort_keys=True))
        actions = {}
        for t in st.get("transactions", []):
            actions[t.get("action_type")] = actions.get(t.get("action_type"), 0) + 1
        print(f"Statement since {first}: {actions}")


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["cycle", "tight", "hold", "try", "settle"])
    parser.add_argument("symbol", nargs="?")
    parser.add_argument("direction", nargs="?", choices=["MULTUP", "MULTDOWN"])
    parser.add_argument("multiplier", nargs="?", type=int)
    parser.add_argument("--tp", type=float)
    parser.add_argument("--sl", type=float)
    parser.add_argument("--wait", type=float, default=8, help="minutes to wait in 'tight'")
    parser.add_argument("--close", action="store_true", help="'settle': also sell held contracts")
    parser.add_argument("--note", default="")
    args = parser.parse_args()

    rows = read_rows()
    try:
        url = open_demo_url()
    except (ConfigError, DerivError) as err:
        print(f"Cannot open the demo account: {err}")
        return 1

    try:
        async with StreamClient(url) as c:
            if args.command == "settle":
                await cmd_settle(c, rows, args.close)
                write_rows(rows)
                return 0

            if not (args.symbol in PIP and args.direction and args.multiplier):
                print("Need SYMBOL DIRECTION MULTIPLIER")
                return 1
            check_budget(rows)
            if args.command == "try":
                try:
                    row, raw = await buy(c, args.symbol, args.direction, args.multiplier)
                except DerivError as err:
                    print(f"Deriv refused x{args.multiplier}: {err}")
                    rows.append({"trade_no": "", "kind": "try (refused)", "symbol": args.symbol,
                                 "direction": args.direction, "multiplier": args.multiplier,
                                 "stake": STAKE, "notes": str(err),
                                 "proposal_time_utc": _utc(time.time())})
                    write_rows(rows)
                    return 0
            else:
                lo = None
                if args.command == "tight":
                    if (args.tp is None) == (args.sl is None):
                        print("tight needs exactly one of --tp / --sl")
                        return 1
                    lo = {"take_profit": args.tp} if args.tp is not None else {"stop_loss": args.sl}
                row, raw = await buy(c, args.symbol, args.direction, args.multiplier, lo)

            row["trade_no"] = sum(1 for r in rows if r.get("contract_id")) + 1
            row["kind"] = args.command + (f" tp={args.tp}" if args.tp is not None else "") + (
                f" sl={args.sl}" if args.sl is not None else "")
            row["notes"] = args.note
            rows.append(row)
            write_rows(rows)          # log the buy at once, before anything else can fail
            save_raw(int(row["contract_id"]), raw)
            try:
                if args.command == "cycle":
                    await cmd_cycle(c, row)
                elif args.command == "tight":
                    await cmd_tight(c, row, args.wait)
                elif args.command == "try":
                    await asyncio.sleep(3)
                    await sell_now(c, row)
                elif args.command == "hold":
                    print("  left open on purpose. Close later with: settle --close")
            finally:
                write_rows(rows)
    except DerivError as err:
        print(f"Deriv error: {err}")
        write_rows(rows)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
