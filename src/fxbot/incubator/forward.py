"""Forward paper replay of a registered candidate on Deriv 1m data after its registration date.

Paper only: this module imports nothing that can reach Deriv or place an order.

Each daily run replays the candidate from scratch, from its first scored day
(the day after registration) to the newest day of complete Deriv data,
through the same engine the research used: measured commission by UTC hour
(research/phase2/cost_by_hour.json), slippage, every hard risk limit
(fxbot.risk) and the calendar rules, starting from 100 USD, kill switch
enforced. A second run charges 1.5x the commission.

Earlier candles are loaded only as indicator history (warm-up): the engine's
minute timeline starts on the first scored day, and the Forward wrapper
returns no action for any candle that closes before it. check_forward_only()
then rejects any signal or trade dated before that day.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from fxbot.backtest import fills
from fxbot.backtest.candles import Bars, aggregate, load_m1
from fxbot.backtest.engine import Engine
from fxbot.backtest.metrics import max_drawdown
from fxbot.data.split import UNTOUCHED_START
from fxbot.incubator.registry import ROOT, Candidate, load_strategy
from fxbot.risk.limits import RiskLimits
from fxbot.strategies.base import Strategy

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")      # the default; each candidate carries its own list
START_BALANCE = 100.0
STRESS = 1.5
DATA = ROOT / "data"
# Everything outside the frozen candidate that decides a forward result. Its hash is stored
# with every record, so a later change to the engine, limits or cost table is visible.
ENGINE_FILES = ("src/fxbot/backtest/engine.py", "src/fxbot/backtest/fills.py", "src/fxbot/backtest/candles.py",
                "src/fxbot/backtest/metrics.py", "src/fxbot/contracts/multiplier.py",
                "src/fxbot/risk/limits.py", "src/fxbot/sessions.py", "src/fxbot/strategies/base.py",
                "src/fxbot/data/candles.py", "src/fxbot/incubator/forward.py",
                "src/fxbot/incubator/exam.py", "research/phase2/cost_by_hour.json",
                "research/phase2/cost_by_hour_pairs2.json", "src/fxbot/symbols.py",
                "config/contract_specs.yaml")


class ForwardViolation(RuntimeError):
    """A signal or trade dated before the candidate's first scored day."""


def engine_fingerprint() -> str:
    h = hashlib.sha256()
    for rel in ENGINE_FILES:
        p = ROOT / rel
        h.update(rel.encode() + b"\0" + (p.read_bytes() if p.exists() else b"<missing>") + b"\0")
    return h.hexdigest()


def epoch_of(d: dt.date) -> int:
    return int(dt.datetime(d.year, d.month, d.day, tzinfo=dt.timezone.utc).timestamp())


def iso(epoch: int) -> str:
    return dt.datetime.fromtimestamp(epoch, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


# ----------------------------------------------------------------------------- data
def latest_complete_day(data_dir: Path = DATA, symbols=SYMBOLS) -> dt.date | None:
    """Newest day with a Deriv 1m file for every pair."""
    days = []
    for s in symbols:
        files = sorted((data_dir / s / "1m").glob("????-??-??.csv.gz"))
        if not files:
            return None
        days.append(dt.date.fromisoformat(files[-1].name[:10]))
    return min(days)


def slice_bars(b: Bars, t0: int, t1: int | None = None) -> Bars:
    i = int(np.searchsorted(b.epoch, t0))
    j = len(b) if t1 is None else int(np.searchsorted(b.epoch, t1))
    return Bars(*(a[i:j] for a in (b.epoch, b.end, b.open, b.high, b.low, b.close)))


def forward_data(c: Candidate, end: dt.date, m1_cache: dict | None = None) -> dict:
    """{symbol: (1m bars from the first scored day, timeframe bars incl. warm-up)}."""
    if c.first_day < UNTOUCHED_START:
        raise ForwardViolation(f"{c.id}: first scored day {c.first_day} is before the untouched period")
    warm = c.first_day - dt.timedelta(days=c.warmup_days)
    out = {}
    for s in c.symbols:
        key = (s, warm, end)
        if m1_cache is not None and key in m1_cache:
            m1 = m1_cache[key]
        else:
            m1 = load_m1(s, warm, end, forward=True)
            if m1_cache is not None:
                m1_cache[key] = m1
        tf = aggregate(m1, c.timeframe)
        # Only candles that close by the end of `end` (the last one may be cut by the data end).
        tf = slice_bars(tf, 0, epoch_of(end + dt.timedelta(days=1)))
        out[s] = (slice_bars(m1, c.start_epoch), tf)
    return out


# ----------------------------------------------------------------------------- strategy wrappers
class Forward(Strategy):
    """The frozen strategy, silent for every candle that closes before the first scored day."""

    def __init__(self, inner, start_epoch: int):
        self.inner, self.start_epoch = inner, start_epoch
        self.name, self.timeframe = inner.name, inner.timeframe
        self.needs_peers = getattr(inner, "needs_peers", False)
        self.params = dict(getattr(inner, "params", {}))

    def on_candle(self, symbol, candles, position, pending):
        if int(candles.end[-1]) < self.start_epoch:
            return []
        self.inner.peers = self.peers
        return self.inner.on_candle(symbol, candles, position, pending)


class CoinToss(Forward):
    """Luck check: the candidate's own forward signals (same pair, same candle), coin-toss
    direction, same stops, exits and limits. Two-leg strategies stay hedged: both legs share one
    draw per candle, so one leg goes Up and the other Down."""

    def __init__(self, inner, start_epoch: int, signals, seed: int, legs: dict | None = None,
                 symbols=SYMBOLS):
        super().__init__(inner, start_epoch)
        self.signals = {(str(s), int(t)) for s, t in signals}
        self.seed, self.legs, self.symbols = int(seed), legs, tuple(symbols)
        inner.entry = self._entry

    def _entry(self, symbol, c):
        t = int(c.end[-1])
        if (symbol, t) not in self.signals:
            return None
        if self.legs:
            if symbol not in self.legs:
                return None
            d = np.random.default_rng([self.seed, t]).random()
            return "MULTUP" if (d < 0.5) == (self.legs[symbol] > 0) else "MULTDOWN"
        d = np.random.default_rng([self.seed, t, self.symbols.index(symbol)]).random()
        return "MULTUP" if d < 0.5 else "MULTDOWN"


# ----------------------------------------------------------------------------- runs
def run(c: Candidate, data: dict, stress: float = 1.0, strategy: Strategy | None = None) -> Engine:
    s = strategy or Forward(load_strategy(c), c.start_epoch)
    eng = Engine(s, list(c.symbols), c.first_day, c.first_day, limits=RiskLimits(starting_balance=START_BALANCE),
                 stress=stress, data=data, kill_switch="enforce", table=fills.CommissionTable(ROOT / c.cost_table))
    eng.run()
    return eng


def entry_signals(eng: Engine) -> list[tuple[str, int]]:
    """(symbol, signal epoch) of every Enter action (filled or not)."""
    return [(sym, int(t)) for t, sym, a in eng.state.signals if a.startswith("Enter(")]


def check_forward_only(c: Candidate, eng: Engine) -> None:
    """Raise unless every signal and trade is dated on or after the first scored day."""
    t0 = c.start_epoch
    bad = [t for t, _, _ in eng.state.signals if t < t0]
    bad += [tr["entry_epoch"] for tr in eng.state.trades if tr["entry_epoch"] < t0]
    if bad:
        raise ForwardViolation(f"{c.id}: {len(bad)} signals/trades before {c.first_day} (first {iso(min(bad))})")


def net_profit(eng: Engine) -> float:
    """Closed trades plus trades still open, marked at the last price (end_of_data closes)."""
    return round(eng.state.balance - START_BALANCE, 2)


@dataclass
class Result:
    summary: dict
    trades: list[dict]
    equity_daily: list[tuple[str, float]]
    signals: list[tuple[str, int]]


def summarise(eng: Engine, symbols=SYMBOLS) -> dict:
    trades = eng.state.trades
    closed = [t for t in trades if t["reason"] != "end_of_data"]
    open_ = [t for t in trades if t["reason"] == "end_of_data"]
    wins = [t["profit"] for t in closed if t["profit"] > 0]
    losses = [t["profit"] for t in closed if t["profit"] <= 0]
    curve = [START_BALANCE] + [e for _, e in eng.state.equity]
    per_pair = {}
    for s in symbols:
        ts = [t for t in closed if t["symbol"] == s]
        per_pair[s] = {"trades": len(ts), "net": round(sum(t["profit"] for t in ts), 2),
                       "wins": sum(t["profit"] > 0 for t in ts)}
    return {
        "trades": len(closed),
        "open_trades": len(open_),
        "open_profit": round(sum(t["profit"] for t in open_), 2),
        "net_profit": net_profit(eng),
        "final_equity": round(eng.state.balance, 2),
        "max_drawdown_pct": round(max_drawdown(curve) * 100, 2),
        "win_rate_pct": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "avg_win": round(float(np.mean(wins)), 3) if wins else None,
        "avg_loss": round(float(np.mean(losses)), 3) if losses else None,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
        "avg_commission": round(float(np.mean([t["commission"] for t in closed])), 4) if closed else None,
        "kill_switch_fired": eng.kill_switch_fired,
        "per_pair": per_pair,
        "signals": len(entry_signals(eng)),
        "blocked_first_reason": dict(eng.state.blocked),
        "refused": dict(eng.state.refused),
        "cost_gate_skips": len(eng.state.gate_skips),
    }


def equity_by_day(eng: Engine) -> list[tuple[str, float]]:
    out: dict[str, float] = {}
    for t, e in eng.state.equity:
        out[iso(t)[:10]] = round(e, 2)
    return sorted(out.items())


def evaluate(c: Candidate, end: dt.date, m1_cache: dict | None = None) -> dict:
    """Forward replay to `end` at the measured commission and at 1.5x."""
    data = forward_data(c, end, m1_cache)
    measured = run(c, data)
    stressed = run(c, data, STRESS)
    for eng in (measured, stressed):
        check_forward_only(c, eng)
    days = (end - c.first_day).days + 1
    return {
        "id": c.id,
        "fingerprint": c.fingerprint,
        "registered": c.manifest["registered"],
        "first_scored_day": c.first_day.isoformat(),
        "data_end": end.isoformat(),
        "forward_days": max(days, 0),
        "measured": summarise(measured, c.symbols),
        "stress_1_5x": summarise(stressed, c.symbols),
        "symbols": list(c.symbols),
        "cost_table": c.cost_table,
        "engine_fingerprint": engine_fingerprint(),
        "_engines": (measured, stressed),
    }


def write_record(rec_dir: Path, result: dict) -> None:
    """records/<id>/: summary.json, trades.csv, equity.csv, signals.json (measured run)."""
    measured, _ = result["_engines"]
    rec_dir.mkdir(parents=True, exist_ok=True)
    summary = {k: v for k, v in result.items() if not k.startswith("_")}
    _write(rec_dir / "summary.json", json.dumps(summary, indent=1, sort_keys=True) + "\n")
    cols = ["symbol", "direction", "multiplier", "stake", "signal_time", "entry_time", "entry", "exit_time",
            "exit", "reason", "rate_pct", "commission", "profit", "balance_after"]
    lines = [",".join(cols)] + [",".join(str(t[k]) for k in cols) for t in measured.state.trades]
    _write(rec_dir / "trades.csv", "\n".join(lines) + "\n")
    _write(rec_dir / "equity.csv", "date,equity\n" + "".join(f"{d},{e}\n" for d, e in equity_by_day(measured)))
    _write(rec_dir / "signals.json", json.dumps(entry_signals(measured)) + "\n")


def _write(path: Path, text: str) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text)
    tmp.replace(path)
