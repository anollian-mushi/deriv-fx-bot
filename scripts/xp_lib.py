"""Shared helpers for the perfect-fit experiment scripts (research only)."""

from __future__ import annotations

import csv
import gzip
import json
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401

from fxbot.backtest import fastsim
from fxbot.backtest.metrics import max_drawdown
from fxbot.backtest.research import run_engine
from fxbot.strategies.base import Enter, ExitPosition, Strategy
from fxbot.strategies.pf_features import SYMBOLS

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / "cache" / "xp"
RES = ROOT / "research" / "experiment"
VARIANTS = RES / "variants.csv.gz"
FIELDS = ["id", "stage", "family", "desc", "config", "screen_trades", "screen_net_pct", "screen_dd_pct",
          "screen_score", "screen_killed"]


@lru_cache(maxsize=1)
def build() -> dict:
    z = np.load(CACHE / "build.npz")
    return {k: z[k] for k in z.files}


def cfg_str(row) -> str:
    m, sl, tp, h = (int(x) for x in row)
    return f"x{m} SL{sl or '-'} TP{tp or '-'} hold{h or 'max'}"


def screen(k: int, direction: np.ndarray) -> dict:
    """direction per candidate: +1 Up, -1 Down, 0 none. Fast portfolio screen."""
    b = build()
    sel = np.where(direction != 0)[0]
    if len(sel) == 0:
        return {"trades": 0, "net_pct": 0.0, "dd_pct": 0.0, "score": -1e9, "killed": False}
    d = (direction[sel] < 0).astype(int)
    t_in = b["t"][sel]
    order = np.argsort(t_in, kind="stable")
    sel, d, t_in = sel[order], d[order], t_in[order]
    pnl = b["pnl"][k, sel, d].astype(np.float64)
    t_out = b["ext"][k, sel, d]
    net, dd, n, killed = fastsim.portfolio(t_in, t_out, b["sym"][sel], pnl)
    score = (net * 100) / max(dd * 100, 0.5) if not killed else -1e9 + net
    return {"trades": int(n), "net_pct": float(net * 100), "dd_pct": float(dd * 100),
            "score": float(score), "killed": bool(killed)}


class VariantLog:
    """Logs every variant tried, one CSV per stage (research/experiment/variants/<stage>.csv).

    One file per stage, so stages can run at the same time without mixing their
    writes. Ids are "<stage>-<n>". xp_log.py merges the files into variants.csv.gz."""

    def __init__(self, stage: str):
        self.stage = stage
        self.path = RES / "variants" / f"{stage}.csv"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.n = 0
        if self.path.exists():
            with self.path.open() as f:
                self.n = sum(1 for _ in csv.DictReader(f))
        self.buf = []

    def add(self, stage, family, desc, k, res) -> str:
        self.n += 1
        vid = f"{self.stage}-{self.n}"
        b = build()
        self.buf.append([vid, stage, family, desc, cfg_str(b["cfg"][k]) if k is not None else "",
                         res["trades"], round(res["net_pct"], 2), round(res["dd_pct"], 2),
                         round(res["score"], 3), res["killed"]])
        return vid

    def flush(self):
        new = not self.path.exists()
        with self.path.open("a", newline="") as f:
            w = csv.writer(f)
            if new:
                w.writerow(FIELDS)
            w.writerows(self.buf)
        self.buf = []


def merge_variants() -> int:
    """Merge the per-stage files into research/experiment/variants.csv.gz (committed)."""
    n = 0
    with gzip.open(VARIANTS, "wt", newline="") as out:
        w = csv.writer(out)
        w.writerow(FIELDS)
        for p in sorted((RES / "variants").glob("*.csv")):
            with p.open() as f:
                r = csv.reader(f)
                next(r)
                for row in r:
                    w.writerow(row)
                    n += 1
    return n


# ----------------------------------------------------------------------------- engine verification
class SignalTable(Strategy):
    """Replays a precomputed table of signals in the real engine (verification only).

    signals: {(symbol, candle end epoch): direction}; one exit setup for all trades."""
    name = "xp_signal_table"
    timeframe = "1h"

    def __init__(self, signals: dict, mult: int, sl: float, tp: float, hold: int, trade_from: int = 0):
        self.signals, self.mult = signals, int(mult)
        self.sl, self.tp, self.hold = (sl or None), (tp or None), int(hold)
        self.trade_from = trade_from
        self.params = {"mult": mult, "sl": sl, "tp": tp, "hold": hold, "n_signals": len(signals)}

    def on_candle(self, symbol, candles, position, pending):
        t = int(candles.end[-1])
        if position is not None:
            if self.hold and t - position.entry_epoch >= self.hold * 3600:
                return [ExitPosition()]
            return []
        if pending or t < self.trade_from:
            return []
        d = self.signals.get((symbol, t))
        if d is None:
            return []
        return [Enter(d, multiplier=self.mult, stop_loss_pips=self.sl, take_profit_pips=self.tp)]


def engine_score(state) -> dict:
    eq = [e for _, e in state.equity]
    start = state.starting_balance
    net = state.balance - start
    dd = max_drawdown([start, *eq]) if eq else 0.0
    wins = sum(1 for t in state.trades if t["profit"] > 0)
    return {"trades": len(state.trades), "net_usd": round(net, 2), "net_pct": round(net / start * 100, 2),
            "dd_pct": round(dd * 100, 2), "score": round((net / start * 100) / max(dd * 100, 0.5), 3),
            "win_rate": round(wins / max(len(state.trades), 1) * 100, 1),
            "killed": bool(state.killed or state.kill_events)}


def run_signals(direction: np.ndarray, k: int, kill_switch: str = "enforce"):
    b = build()
    m, sl, tp, hold = b["cfg"][k]
    sig = {(SYMBOLS[int(b["sym"][i])], int(b["t"][i])): ("MULTUP" if direction[i] > 0 else "MULTDOWN")
           for i in np.where(direction != 0)[0]}
    s = SignalTable(sig, m, sl, tp, hold)
    from fxbot.backtest.engine import Engine
    from fxbot.backtest.research import DATA_END, DATA_START, market_data
    eng = Engine(s, list(SYMBOLS), DATA_START, DATA_END, data=market_data("1h", DATA_START, DATA_END),
                 kill_switch=kill_switch)
    eng.run()
    return eng


def save_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, default=str))
