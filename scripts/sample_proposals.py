"""Phase 2: sample Multiplier price quotes (proposals) on the public WebSocket.

No login, never buys. For every pair, direction, multiplier (both the
contracts_for list and the list pricing accepted in Phase 0) and stake, asks
for a quote and records whether Deriv accepts it plus every cost and limit
field. Then probes the take-profit / stop-loss limits at and just past the
edges Deriv reports.

One run takes about two minutes and writes one file:
  research/phase2/proposals_<YYYYmmddTHHMM>Z_<label>.jsonl.gz
Run it at different times of day to see whether anything changes.

--demo asks the same questions through the DEMO account's own WebSocket
(needs DERIV_PAT and DERIV_APP_ID; still only quotes, never buys). This
matters: in Phase 2 the demo account was offered different multipliers than
the public connection.

Run: python scripts/sample_proposals.py [--label NAME] [--demo]
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401
from websockets.asyncio.client import connect

from fxbot.deriv.api import WS_PUBLIC_URL, DerivError, ws_request

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
DIRECTIONS = ("MULTUP", "MULTDOWN")
# contracts_for said 100, 200, 300, 500, 800; pricing accepted 50, 100, 150, 250, 500.
MULTIPLIERS = (50, 100, 150, 200, 250, 300, 500, 800)
STAKES = (1, 2, 3, 10, 100, 500)
OUT_DIR = Path(__file__).resolve().parents[1] / "research" / "phase2"
PAUSE = 0.3  # seconds between requests per pair; 3 pairs stay under 360/min


def _request(symbol: str, direction: str, multiplier: int, stake: float, limit_order: dict | None) -> dict:
    req = {
        "proposal": 1,
        "amount": stake,
        "basis": "stake",
        "contract_type": direction,
        "currency": "USD",
        "underlying_symbol": symbol,
        "multiplier": multiplier,
    }
    if limit_order:
        req["limit_order"] = limit_order
    return req


async def _quote(ws, kind: str, symbol: str, direction: str, multiplier: int, stake: float,
                 limit_order: dict | None = None) -> dict:
    row = {
        "kind": kind, "symbol": symbol, "direction": direction, "multiplier": multiplier,
        "stake": stake, "limit_order": limit_order, "requested_at": time.time(),
    }
    for attempt in range(3):
        try:
            reply = await ws_request(ws, _request(symbol, direction, multiplier, stake, limit_order))
            p = dict(reply["proposal"])
            p.pop("id", None)
            row.update(accepted=True, proposal=p)
            break
        except DerivError as err:
            if err.code == "RateLimit" and attempt < 2:
                await asyncio.sleep(30)
                continue
            row.update(accepted=False, error_code=err.code, error=err.message)
            break
    await asyncio.sleep(PAUSE)
    return row


def _demo_url() -> str:
    """A fresh one-time URL for the demo account. Refuses anything else."""
    from fxbot.config import load_settings
    from fxbot.deriv.api import choose_demo_account, create_otp_url, is_demo_ws_url, list_accounts

    settings = load_settings()
    account = choose_demo_account(list_accounts(settings), settings.deriv_account_id)
    url = create_otp_url(settings, account["account_id"])
    if not is_demo_ws_url(url):
        raise SystemExit("One-time URL is not for the demo gateway. Refusing.")
    return url


def _public_ws():
    return connect(WS_PUBLIC_URL, open_timeout=20, ping_interval=30)


def _demo_ws():
    return connect(_demo_url(), open_timeout=20, ping_interval=30)  # one OTP URL per connection


async def _sample_symbol(sym: str, open_ws) -> list[dict]:
    """All quotes for one pair, on its own connection (pairs run in parallel).

    open_ws() returns an async context manager yielding a WebSocket.
    """
    rows: list[dict] = []
    async with open_ws() as ws:
        # 0) if trading is paused (e.g. the daily 20:55-21:30 UTC pause), one
        #    refused quote says so; record it and stop instead of asking 300 times.
        probe = await _quote(ws, "grid", sym, DIRECTIONS[0], 100, STAKES[0])
        if not probe["accepted"] and "not available" in probe.get("error", "").lower():
            return [probe]

        # 1) every multiplier x stake, both directions
        for d in DIRECTIONS:
            for m in MULTIPLIERS:
                first = await _quote(ws, "grid", sym, d, m, STAKES[0])
                rows.append(first)
                if not first["accepted"] and "multiplier" in first.get("error", "").lower():
                    continue  # multiplier rejected; other stakes would say the same
                for stake in STAKES[1:]:
                    rows.append(await _quote(ws, "grid", sym, d, m, stake))

        # 2) stake edges and TP/SL edges, at the minimum stake and at 10 USD
        working = sorted({r["multiplier"] for r in rows if r["accepted"]})
        if not working:
            return rows
        rows.append(await _quote(ws, "edge", sym, "MULTUP", working[0], 0.99))
        rows.append(await _quote(ws, "edge", sym, "MULTUP", working[0], 500.01))
        for m in working:
            for stake in (1, 10):
                base = next((r for r in rows if r["kind"] == "grid" and r["accepted"]
                             and r["multiplier"] == m and r["stake"] == stake), None)
                if base is None:
                    continue
                vp = base["proposal"]["validation_params"]
                tp_min, tp_max = float(vp["take_profit"]["min"]), float(vp["take_profit"]["max"])
                sl_min, sl_max = float(vp["stop_loss"]["min"]), float(vp["stop_loss"]["max"])
                probes = [
                    {"take_profit": tp_min}, {"take_profit": round(tp_min - 0.01, 2)},
                    {"take_profit": tp_max}, {"take_profit": round(tp_max + 0.01, 2)},
                    {"stop_loss": sl_min}, {"stop_loss": round(sl_min - 0.01, 2)},
                    {"stop_loss": round(sl_min + 0.01, 2)},
                    {"stop_loss": sl_max}, {"stop_loss": round(sl_max + 0.01, 2)},
                ]
                for lo in probes:
                    rows.append(await _quote(ws, "edge", sym, "MULTUP", m, stake, lo))
    return rows


async def run(label: str | None, connection: str, open_ws) -> Path:
    started = datetime.now(timezone.utc)
    name = f"proposals_{started:%Y%m%dT%H%M}Z" + (f"_{label}" if label else "") + f"_{connection}"
    path = OUT_DIR / f"{name}.jsonl.gz"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    async with open_ws() as ws:
        server_time = (await ws_request(ws, {"time": 1}))["time"]
        symbols = {s["underlying_symbol"]: s for s in
                   (await ws_request(ws, {"active_symbols": "brief"}))["active_symbols"]}
        meta = {"kind": "meta", "started_utc": started.isoformat(), "server_time": server_time,
                "connection": connection}
        for sym in SYMBOLS:
            info = symbols.get(sym, {})
            avail = (await ws_request(ws, {"contracts_for": sym}))["contracts_for"]["available"]
            meta[sym] = {
                "pip_size": info.get("pip_size"),
                "exchange_is_open": info.get("exchange_is_open"),
                "is_trading_suspended": info.get("is_trading_suspended"),
                "contracts_for_multipliers": sorted({
                    m for a in avail if a["contract_category"] == "multiplier"
                    for m in a.get("multiplier_range", [])
                }),
            }
    per_symbol = await asyncio.gather(*(_sample_symbol(sym, open_ws) for sym in SYMBOLS))
    rows = [meta] + [r for rs in per_symbol for r in rs]

    with gzip.open(path, "wt", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    return path


def report(path: Path, t0: float) -> None:
    with gzip.open(path, "rt") as f:
        rows = [json.loads(line) for line in f]
    quotes = [r for r in rows if r["kind"] != "meta"]
    ok = sum(r["accepted"] for r in quotes)
    print(f"{len(quotes)} quotes ({ok} accepted) in {time.time() - t0:.0f}s -> {path.name}")
    grid = [r for r in quotes if r["kind"] == "grid"]
    for sym in SYMBOLS:
        works = sorted({r["multiplier"] for r in grid if r["symbol"] == sym and r["accepted"]})
        fails = sorted({r["multiplier"] for r in grid if r["symbol"] == sym and not r["accepted"]})
        print(f"  {sym}: accepted {works}, rejected {fails}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", help="optional tag added to the file name")
    parser.add_argument("--demo", action="store_true", help="quote through the demo account")
    args = parser.parse_args()
    t0 = time.time()
    path = asyncio.run(run(args.label, *(("demo", _demo_ws) if args.demo else ("public", _public_ws))))
    report(path, t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
