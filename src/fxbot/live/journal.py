"""SQLite journal of everything the live bot does (on the VPS, never committed).

Tables:
- events: every signal, skip (with the reason and the rate seen), order, close,
  reconnect, alert, error, start/stop, and every Telegram message sent
- quotes: every price quote the bot asked for, with the exact commission rate
  (commission / (stake x multiplier)); hourly cost samples go here too
- orders: one row per buy attempt and its whole life:
    sending -> open -> closed      (normal)
    sending -> failed              (Deriv refused, or a lost reply that reconciliation proved never filled)
    sending -> unknown -> open/failed   (reply lost; resolved by reconciliation before any new order)
- kv: small bot state (start-of-day balance, paused, last candle seen, ...)

Every thread opens its own connection, so the Telegram thread can read and
write while the trading loop is busy (WAL mode).
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY, ts REAL NOT NULL, kind TEXT NOT NULL,
    symbol TEXT, detail TEXT);
CREATE INDEX IF NOT EXISTS events_ts ON events(ts);
CREATE TABLE IF NOT EXISTS quotes (id INTEGER PRIMARY KEY, ts REAL NOT NULL, symbol TEXT NOT NULL,
    contract_type TEXT, multiplier INTEGER, stake REAL, commission REAL, size REAL, rate REAL, spot REAL,
    purpose TEXT, account TEXT);
CREATE INDEX IF NOT EXISTS quotes_ts ON quotes(ts);
CREATE TABLE IF NOT EXISTS orders (id INTEGER PRIMARY KEY, created REAL NOT NULL, strategy TEXT,
    symbol TEXT NOT NULL, direction TEXT NOT NULL, multiplier INTEGER NOT NULL, stake REAL NOT NULL,
    sl_amount REAL, tp_amount REAL, signal_epoch INTEGER, deadline INTEGER, state TEXT NOT NULL,
    proposal_id TEXT, contract_id INTEGER UNIQUE, buy_price REAL, purchase_time INTEGER, entry_spot REAL,
    commission REAL, rate_probe REAL, rate_quote REAL, closed REAL, close_reason TEXT, sell_price REAL,
    exit_spot REAL, profit REAL, test INTEGER DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS kv (key TEXT PRIMARY KEY, value TEXT);
"""

ORDER_COLS = ("id", "created", "strategy", "symbol", "direction", "multiplier", "stake", "sl_amount", "tp_amount",
              "signal_epoch", "deadline", "state", "proposal_id", "contract_id", "buy_price", "purchase_time",
              "entry_spot", "commission", "rate_probe", "rate_quote", "closed", "close_reason", "sell_price",
              "exit_spot", "profit", "test", "note")


def _iso(ts: float | None) -> str:
    if not ts:
        return ""
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts))


class Journal:
    def __init__(self, path: Path, start_balance: float = 100.0, clock=time.time):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.start_balance = start_balance
        self.clock = clock
        with self._db() as db:
            db.executescript(SCHEMA)

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute("PRAGMA journal_mode=WAL")
            yield db
        finally:
            db.close()

    # ------------------------------------------------------------------ events and quotes
    def event(self, kind: str, symbol: str | None = None, **detail) -> None:
        with self._db() as db:
            db.execute("INSERT INTO events (ts, kind, symbol, detail) VALUES (?,?,?,?)",
                       (self.clock(), kind, symbol, json.dumps(detail, default=str, sort_keys=True)))

    def events(self, since: float = 0, kinds: tuple[str, ...] | None = None) -> list[dict]:
        q, args = "SELECT * FROM events WHERE ts >= ?", [since]
        if kinds:
            q += f" AND kind IN ({','.join('?' * len(kinds))})"
            args += list(kinds)
        with self._db() as db:
            rows = db.execute(q + " ORDER BY id", args).fetchall()
        return [{**dict(r), "detail": json.loads(r["detail"] or "{}")} for r in rows]

    def quote(self, symbol: str, contract_type: str, multiplier: int, stake: float, commission: float,
              spot: float | None, purpose: str, account: str = "") -> float:
        """Journal one quote; returns its exact commission rate (fraction of stake x multiplier)."""
        size = stake * multiplier
        rate = commission / size if size else None
        with self._db() as db:
            db.execute("INSERT INTO quotes (ts, symbol, contract_type, multiplier, stake, commission, size, rate, "
                       "spot, purpose, account) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                       (self.clock(), symbol, contract_type, multiplier, stake, commission, size, rate, spot,
                        purpose, account))
        return rate

    def quotes(self, since: float = 0) -> list[dict]:
        with self._db() as db:
            return [dict(r) for r in db.execute("SELECT * FROM quotes WHERE ts >= ? ORDER BY id", (since,))]

    # ------------------------------------------------------------------ orders
    def new_order(self, **fields) -> int:
        fields = {"created": self.clock(), "state": "sending", **fields}
        cols = ",".join(fields)
        with self._db() as db:
            cur = db.execute(f"INSERT INTO orders ({cols}) VALUES ({','.join('?' * len(fields))})",
                             tuple(fields.values()))
            return int(cur.lastrowid)

    def update_order(self, oid: int, **fields) -> None:
        if not fields:
            return
        sets = ",".join(f"{k}=?" for k in fields)
        with self._db() as db:
            db.execute(f"UPDATE orders SET {sets} WHERE id=?", (*fields.values(), oid))

    def close_order(self, oid: int, reason: str, profit: float, sell_price=None, exit_spot=None,
                    closed: float | None = None) -> bool:
        """Mark an open order closed. Idempotent: returns False if it was already closed."""
        with self._db() as db:
            cur = db.execute("UPDATE orders SET state='closed', close_reason=?, profit=?, sell_price=?, exit_spot=?, "
                             "closed=? WHERE id=? AND state IN ('open','unknown')",
                             (reason, round(float(profit), 2), sell_price, exit_spot, closed or self.clock(), oid))
            return cur.rowcount == 1

    def orders(self, states: tuple[str, ...] | None = None, since: float = 0) -> list[dict]:
        q, args = "SELECT * FROM orders WHERE created >= ?", [since]
        if states:
            q += f" AND state IN ({','.join('?' * len(states))})"
            args += list(states)
        with self._db() as db:
            return [dict(r) for r in db.execute(q + " ORDER BY id", args)]

    def order_by_contract(self, contract_id: int) -> dict | None:
        with self._db() as db:
            r = db.execute("SELECT * FROM orders WHERE contract_id=?", (int(contract_id),)).fetchone()
        return dict(r) if r else None

    def open_orders(self) -> list[dict]:
        return self.orders(("open",))

    def unresolved_orders(self) -> list[dict]:
        return self.orders(("sending", "unknown"))

    # ------------------------------------------------------------------ ledger
    def balance(self) -> float:
        """Pretend ledger: start balance + every closed trade's profit."""
        with self._db() as db:
            s = db.execute("SELECT COALESCE(SUM(profit),0) FROM orders WHERE state='closed'").fetchone()[0]
        return round(self.start_balance + float(s), 2)

    def get(self, key: str, default=None):
        with self._db() as db:
            r = db.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default

    def set(self, key: str, value) -> None:
        with self._db() as db:
            db.execute("INSERT INTO kv (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (key, json.dumps(value)))

    # ------------------------------------------------------------------ exports
    def orders_csv(self, since: float = 0) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow([*ORDER_COLS, "created_utc", "closed_utc"])
        for o in self.orders(since=since):
            w.writerow([*(o[c] for c in ORDER_COLS), _iso(o["created"]), _iso(o["closed"])])
        return buf.getvalue()

    def events_csv(self, since: float = 0) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["utc", "kind", "symbol", "detail"])
        for e in self.events(since):
            w.writerow([_iso(e["ts"]), e["kind"], e["symbol"] or "", json.dumps(e["detail"], sort_keys=True)])
        return buf.getvalue()
