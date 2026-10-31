"""A fake Deriv (REST + trading WebSocket), fake candles, clock and Telegram for live bot tests."""

from __future__ import annotations

import datetime as dt
import itertools
import json
import uuid

import httpx
import numpy as np

from fxbot.backtest.candles import Bars
from fxbot.contracts import multiplier as mc
from fxbot.deriv.api import DerivError
from fxbot.strategies.base import Enter, Strategy

BASE = {"frxEURUSD": 0.000239, "frxGBPUSD": 0.000203, "frxUSDJPY": 0.000275}
MON_10 = int(dt.datetime(2026, 11, 2, 10, 0, 3, tzinfo=dt.timezone.utc).timestamp())   # Monday 10:00:03 UTC


class Clock:
    def __init__(self, t: float = MON_10):
        self.t = float(t)

    def __call__(self) -> float:
        return self.t

    async def sleep(self, s: float) -> None:
        self.t += s


class FakeDeriv:
    def __init__(self, clock: Clock):
        self.clock = clock
        self.accounts = [{"account_id": "DOT123", "account_type": "demo", "balance": 10000.0, "currency": "USD",
                          "status": "active"},
                         {"account_id": "ROT123", "account_type": "real", "balance": 80.0, "currency": "USD",
                          "status": "active"}]
        self.prices = {"frxEURUSD": 1.10000, "frxGBPUSD": 1.30000, "frxUSDJPY": 150.000}
        self.rates = dict(BASE)
        self.proposals: dict[str, dict] = {}
        self.used_proposals: set[str] = set()
        self.contracts: dict[int, dict] = {}
        self.statement: list[dict] = []
        self.ids = itertools.count(1000)
        self.otps = 0
        self.connections: list["FakeConn"] = []
        self.requests: list[dict] = []
        self.fail: dict[str, str] = {}      # msg type -> "drop_before" | "drop_after" | "error:<code>"
        self.rest_down = 0                  # number of REST calls that fail

    # ------------------------------------------------------------------ REST
    def transport(self) -> httpx.MockTransport:
        def handler(req: httpx.Request) -> httpx.Response:
            if self.rest_down > 0:
                self.rest_down -= 1
                return httpx.Response(503, json={"errors": [{"code": "Unavailable", "message": "down"}]})
            assert req.headers.get("Deriv-App-ID") and req.headers.get("Authorization", "").startswith("Bearer ")
            if req.method == "GET" and req.url.path == "/trading/v1/options/accounts":
                return httpx.Response(200, json={"data": self.accounts})
            if req.method == "POST" and req.url.path.endswith("/otp"):
                acc = req.url.path.split("/")[-2]
                kind = next(a["account_type"] for a in self.accounts if a["account_id"] == acc)
                self.otps += 1
                return httpx.Response(200, json={"data": {
                    "url": f"wss://api.derivws.com/trading/v1/options/ws/{kind}?otp=secret{self.otps}"}})
            return httpx.Response(404, json={"errors": [{"code": "NotFound", "message": "?"}]})
        return httpx.MockTransport(handler)

    async def connect(self, url: str) -> "FakeConn":
        c = FakeConn(self, url)
        self.connections.append(c)
        return c

    def drop_all(self) -> None:
        for c in self.connections:
            c.closed = True

    # ------------------------------------------------------------------ contracts
    def profit(self, c: dict) -> float:
        if c["sold"]:
            return c["profit"]
        return round(mc.profit(c["type"], c["stake"], c["mult"], c["entry"], self.prices[c["symbol"]], c["comm"]), 2)

    def poc(self, cid: int) -> dict:
        c = self.contracts.get(cid)
        if not c:
            raise DerivError("InvalidContractId", "no such contract")
        return {"contract_id": cid, "is_sold": 1 if c["sold"] else 0, "profit": self.profit(c),
                "sell_price": c.get("sell_price"), "entry_spot": c["entry"], "commission": round(c["comm"], 2),
                "purchase_time": c["purchase_time"], "date_start": c["purchase_time"], "status": None if c["sold"] else "open",
                "exit_spot": c.get("exit"), "sell_time": c.get("sell_time"),
                "limit_order": {k: {"order_amount": v} for k, v in (("stop_loss", c["sl"]), ("take_profit", c["tp"])) if v}}

    def close(self, cid: int, price: float | None = None, profit: float | None = None) -> None:
        """Deriv closes a contract (TP / SL / stop out / manual)."""
        c = self.contracts[cid]
        price = self.prices[c["symbol"]] if price is None else price
        p = round(mc.profit(c["type"], c["stake"], c["mult"], c["entry"], price, c["comm"]), 2) if profit is None else profit
        c.update(sold=True, profit=p, sell_price=round(c["stake"] + p, 2), exit=price, sell_time=int(self.clock()))
        self.statement.insert(0, {"action_type": "sell", "contract_id": cid, "amount": c["sell_price"],
                                  "transaction_time": int(self.clock()), "shortcode": c["shortcode"]})

    def open_contract(self, symbol="frxEURUSD", type_="MULTUP", stake=1.0, mult=100, foreign=True) -> int:
        cid = next(self.ids)
        t = int(self.clock())
        comm = mc.commission(stake, mult, self.rates[symbol])
        self.contracts[cid] = {"symbol": symbol, "type": type_, "stake": stake, "mult": mult, "buy_price": stake,
                               "purchase_time": t, "entry": self.prices[symbol], "comm": comm, "sl": None, "tp": None,
                               "sold": False, "shortcode": f"{type_}_FRX{symbol[3:]}_{stake:.2f}_{mult}_{t}_4946820900_0_0.00_N1_0"}
        return cid

    # ------------------------------------------------------------------ WebSocket messages
    def handle(self, p: dict) -> dict:
        kind = next(iter(p))
        if kind == "balance":
            return {"balance": {"balance": 10000.0, "currency": "USD"}}
        if kind == "proposal":
            sym, stake, mult = p["underlying_symbol"], p["amount"], p["multiplier"]
            if mult not in (100, 200, 300, 500, 800):
                raise DerivError("ContractCreationFailure", "multiplier not offered")
            comm = round(max(self.rates[sym] * stake * mult, 0.02), 2)
            pid = uuid.uuid4().hex
            self.proposals[pid] = {**p, "spot": self.prices[sym], "comm_exact": max(self.rates[sym] * stake * mult, 0.02)}
            return {"proposal": {"id": pid, "ask_price": stake, "commission": comm, "spot": self.prices[sym],
                                 "multiplier": mult, "limit_order": p.get("limit_order", {})}}
        if kind == "buy":
            pid = p["buy"]
            if pid in self.used_proposals or pid not in self.proposals:
                raise DerivError("InvalidContractProposal", "proposal already used or unknown")
            self.used_proposals.add(pid)
            q = self.proposals[pid]
            cid = self.open_contract(q["underlying_symbol"], q["contract_type"], q["amount"], q["multiplier"])
            c = self.contracts[cid]
            lo = q.get("limit_order") or {}
            c.update(sl=lo.get("stop_loss"), tp=lo.get("take_profit"), comm=q["comm_exact"])
            self.statement.insert(0, {"action_type": "buy", "contract_id": cid, "amount": -q["amount"],
                                      "transaction_time": c["purchase_time"], "shortcode": c["shortcode"]})
            return {"buy": {"contract_id": cid, "buy_price": q["amount"], "purchase_time": c["purchase_time"],
                            "start_time": c["purchase_time"], "shortcode": c["shortcode"]}}
        if kind == "sell":
            c = self.contracts.get(p["sell"])
            if not c or c["sold"]:
                raise DerivError("InvalidSellContractProposal", "contract already sold")
            self.close(p["sell"])
            return {"sell": {"contract_id": p["sell"], "sold_for": c["sell_price"]}}
        if kind == "proposal_open_contract":
            return {"proposal_open_contract": self.poc(p["contract_id"])}
        if kind == "portfolio":
            return {"portfolio": {"contracts": [
                {"contract_id": cid, "contract_type": c["type"], "buy_price": c["buy_price"],
                 "purchase_time": c["purchase_time"], "shortcode": c["shortcode"], "underlying_symbol": c["symbol"]}
                for cid, c in self.contracts.items() if not c["sold"]]}}
        if kind == "statement":
            return {"statement": {"transactions": [t for t in self.statement
                                                   if t["transaction_time"] >= p["date_from"]]}}
        raise DerivError("UnrecognisedRequest", kind)


class FakeConn:
    def __init__(self, fake: FakeDeriv, url: str):
        self.fake, self.url, self.closed = fake, url, False

    @property
    def alive(self) -> bool:
        return not self.closed

    async def request(self, payload: dict, timeout: float = 30) -> dict:
        if self.closed:
            raise ConnectionError("closed")
        kind = next(iter(payload))
        self.fake.requests.append(payload)
        mode = self.fake.fail.pop(kind, None)
        if mode == "drop_before":
            self.closed = True
            raise ConnectionError("dropped")
        if mode and mode.startswith("error:"):
            raise DerivError(mode[6:], "refused by fake Deriv")
        reply = self.fake.handle(payload)
        if mode == "drop_after":            # Deriv did it, but the reply never arrived
            self.closed = True
            raise ConnectionError("dropped after send")
        return json.loads(json.dumps(reply))

    async def __aexit__(self, *a):
        self.closed = True


# ---------------------------------------------------------------------------- candles and strategy
class FakeStore:
    """Hourly candles on a flat price, closed by `until`; 1m data is irrelevant to these tests."""

    def __init__(self, fake: FakeDeriv):
        self.fake = fake
        self.refreshes = 0
        self.fail = 0

    async def refresh(self, now):
        self.refreshes += 1
        if self.fail:
            self.fail -= 1
            raise ConnectionError("feed down")
        return {}

    def bars(self, symbol, timeframe, until):
        step = {"1h": 3600, "4h": 14400, "1d": 86400}[timeframe]
        end = until - until % step
        ends = np.arange(end - 50 * step, end + 1, step, dtype=np.int64)
        px = np.full(len(ends), self.fake.prices[symbol])
        return Bars(ends - step, ends, px, px, px, px)

    def last_price(self, symbol):
        return self.fake.prices[symbol]

    def prune(self, *a):
        pass


class ScriptedStrategy(Strategy):
    """Enters on chosen (symbol, candle end) pairs."""
    name = "scripted"
    timeframe = "1h"

    def __init__(self, entries=None, sl_pips=20.0, tp_pips=40.0, exits=None):
        self.entries = dict(entries or {})          # (symbol, end) -> direction
        self.exits = set(exits or ())
        self.sl, self.tp = sl_pips, tp_pips
        self.calls = []

    def on_candle(self, symbol, candles, position, pending):
        end = int(candles.end[-1])
        self.calls.append((symbol, end, position is not None, pending))
        if position is not None:
            from fxbot.strategies.base import ExitPosition
            return [ExitPosition()] if (symbol, end) in self.exits else []
        d = self.entries.get((symbol, end))
        return [Enter(d, 100, self.sl, self.tp, 0.03)] if d and not pending else []


class FakeNotifier:
    def __init__(self, journal=None):
        self.journal = journal
        self.messages: list[tuple[str, str]] = []

    def send(self, text, category="info"):
        self.messages.append((category, text))
        if self.journal:
            self.journal.event("telegram", category=category, text=text)

    def flush(self, *a):
        pass

    def texts(self, category=None):
        return [t for c, t in self.messages if category is None or c == category]


class FakeTelegram:
    def __init__(self, chat_id="42"):
        self.chat_id = chat_id
        self.sent: list[str] = []
        self.docs: list[tuple[str, bytes]] = []
        self.inbox: list[dict] = []
        self.next_id = 1

    def push(self, text, chat=None, date=None):
        self.inbox.append({"update_id": self.next_id, "message": {"chat": {"id": int(chat or self.chat_id)},
                                                                  "text": text, "date": date or MON_10}})
        self.next_id += 1

    def updates(self, offset, timeout=0):
        out = [u for u in self.inbox if offset is None or u["update_id"] >= offset]
        self.inbox = []
        return out

    def send(self, text):
        self.sent.append(text)

    def send_document(self, name, content, caption=""):
        self.docs.append((name, content))
