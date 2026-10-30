"""Run metrics (CLAUDE.md list) and Monte Carlo drawdowns."""

from __future__ import annotations

import statistics

import numpy as np


def max_drawdown(curve: list[float]) -> float:
    """Largest fall from a peak, as a fraction of that peak."""
    peak, dd = -float("inf"), 0.0
    for v in curve:
        peak = max(peak, v)
        if peak > 0:
            dd = max(dd, (peak - v) / peak)
    return dd


def monte_carlo_drawdowns(profits: list[float], balances_before: list[float], start: float,
                          runs: int = 1000, seed: int = 7) -> dict:
    """Shuffle the order of trade returns (profit / balance before) 1,000 times."""
    if not profits:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0, "runs": 0}
    r = np.array(profits) / np.array(balances_before)
    rng = np.random.default_rng(seed)
    dds = []
    for _ in range(runs):
        curve = start * np.cumprod(1 + rng.permutation(r))
        dds.append(max_drawdown([start, *curve.tolist()]))
    return {"p50": float(np.percentile(dds, 50)), "p95": float(np.percentile(dds, 95)),
            "p99": float(np.percentile(dds, 99)), "runs": runs}


def summarise(trades: list[dict], start: float, equity: list[float] | None = None,
              profit_key: str = "profit") -> dict:
    profits = [t[profit_key] for t in trades]
    wins = [p for p in profits if p > 0]
    losses = [p for p in profits if p <= 0]
    balance, before, curve = start, [], [start]
    for t, p in zip(trades, profits):
        # With research restarts (kill switch observe mode) the real balance before a trade
        # can differ from the running sum; use it when the trade records it.
        if profit_key == "profit" and "balance_after" in t:
            balance = round(t["balance_after"] - p, 2)
        before.append(balance)
        balance = round(balance + p, 2)
        curve.append(balance)
    net = round(sum(profits), 2)
    commissions = [t["commission"] for t in trades] if trades and "commission" in trades[0] else []
    late = [t["delay_min"] for t in trades if t.get("delay_min", 0) > 0]
    avg_win = statistics.mean(wins) if wins else 0.0
    avg_comm = statistics.mean(commissions) if commissions else 0.0
    return {
        "trades": len(trades),
        "final_balance": balance,
        "net_profit": net,
        "net_return_pct": round(net / start * 100, 2),
        "max_drawdown_pct": round(max_drawdown(equity or curve) * 100, 2),
        "win_rate_pct": round(len(wins) / len(trades) * 100, 1) if trades else 0.0,
        "avg_win": round(avg_win, 3),
        "avg_loss": round(statistics.mean(losses), 3) if losses else 0.0,
        "profit_factor": round(sum(wins) / -sum(losses), 3) if losses and sum(losses) < 0 else None,
        "avg_commission": round(avg_comm, 4),
        "min_target_met": bool(trades) and bool(avg_win >= 3 * avg_comm),
        "late_fills": len(late),
        "avg_delay_min": round(statistics.mean(late), 1) if late else 0.0,
        "monte_carlo_drawdown_pct": {k: round(v * 100, 2) if k != "runs" else v
                                     for k, v in monte_carlo_drawdowns(profits, before, start).items()},
    }
