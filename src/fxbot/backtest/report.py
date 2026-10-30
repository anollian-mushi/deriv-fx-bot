"""Write a run's outputs: trades.csv, equity.png, metrics.json, gate_skips.csv, report.md."""

from __future__ import annotations

import csv
import datetime as dt
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from fxbot.backtest import metrics, mt5  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "reports" / "backtests"


def write_run(name: str, info: dict, measured, stress, include_holdout: bool = False) -> Path:
    """measured / stress: finished EngineState objects."""
    out = OUT / (name + ("_HOLDOUT" if include_holdout else ""))
    out.mkdir(parents=True, exist_ok=True)
    start = measured.starting_balance
    trades = [dict(t, mt5_profit=mt5.mt5_profit(t)) for t in measured.trades]

    res = {
        "run": name, "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        **info,
        "measured": metrics.summarise(trades, start, [e for _, e in measured.equity] or None),
        "stress_1_5x": metrics.summarise(stress.trades, start, [e for _, e in stress.equity] or None),
        "mt5_micro_comparison_only": metrics.summarise(trades, start, profit_key="mt5_profit"),
        "signals_blocked_first_reason": dict(measured.blocked),
        "signals_dropped": dict(measured.refused),
        "gate_blocked_signals": measured.blocked.get("cost_gate", 0),
        "kill_switch": measured.killed or bool(measured.kill_events),
        "kill_switch_stress": stress.killed or bool(stress.kill_events),
        "kill_events": measured.kill_events, "kill_events_stress": stress.kill_events,
        "exit_reasons": _count(trades, "reason"),
    }
    res["mt5_micro_comparison_only"]["min_target_met"] = None   # not meaningful without commission
    (out / "metrics.json").write_text(json.dumps(res, indent=1))

    if trades:
        with (out / "trades.csv").open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(trades[0]))
            w.writeheader()
            w.writerows(trades)
    with (out / "gate_skips.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time_utc", "symbol", "rate_pct_seen"])
        w.writerows(measured.gate_skips)

    _plot(out / "equity.png", name, start, trades, stress.trades)
    (out / "report.md").write_text(_markdown(name, res))
    return out


def _count(trades, key):
    out: dict = {}
    for t in trades:
        out[t[key]] = out.get(t[key], 0) + 1
    return out


def _curve(trades, start, key="profit"):
    xs, ys, b = [], [], start
    for t in trades:
        b += t[key]
        xs.append(dt.datetime.fromtimestamp(t["exit_epoch"], dt.timezone.utc))
        ys.append(b)
    return xs, ys


def _plot(path, name, start, trades, stress_trades):
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=110)
    for tr, key, label, style in ((trades, "profit", "Multipliers, measured cost", "-"),
                                  (stress_trades, "profit", "Multipliers, 1.5x cost", "--"),
                                  (trades, "mt5_profit", "MT5 micro (comparison only)", ":")):
        xs, ys = _curve(tr, start, key)
        if xs:
            ax.plot(xs, ys, style, label=label, linewidth=1.3)
    ax.axhline(start, color="grey", linewidth=0.8)
    ax.axhline(start * 0.5, color="red", linewidth=0.8, linestyle="-.", label="kill switch (50%)")
    ax.set_title(f"{name}: balance after each trade (USD)")
    ax.legend(loc="best", fontsize=8)
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def _markdown(name, r) -> str:
    def row(label, m):
        pf = m["profit_factor"] if m["profit_factor"] is not None else "-"
        mc = m["monte_carlo_drawdown_pct"]
        return (f"| {label} | {m['trades']} | {m['net_return_pct']}% | {m['max_drawdown_pct']}% | "
                f"{m['win_rate_pct']}% | {m['avg_win']} | {m['avg_loss']} | {pf} | "
                f"{mc['p50']}% / {mc['p95']}% / {mc['p99']}% |")
    m = r["measured"]
    lines = [
        f"# Backtest: {name}", "",
        f"Generated {r['generated_utc']} by `scripts/run_backtest.py`.", "",
        f"- Strategy: `{r.get('strategy')}` ({r.get('timeframe')}) {r.get('label', '')}",
        f"- Pairs: {', '.join(r.get('symbols', []))}",
        f"- Period: {r.get('start')} to {r.get('end')} "
        f"({'INCLUDES THE HOLDOUT' if r.get('include_holdout') else 'pre-holdout data only'})",
        f"- Starting balance: {r.get('starting_balance')} USD; all CLAUDE.md risk limits on.", "",
        "| Cost model | Trades | Net return | Max drawdown | Win rate | Avg win (USD) | Avg loss (USD) "
        "| Profit factor | Monte Carlo drawdown p50 / p95 / p99 |",
        "|---|---|---|---|---|---|---|---|---|",
        row("Multipliers, measured cost", m),
        row("Multipliers, 1.5x cost (stress)", r["stress_1_5x"]),
        row("MT5 micro (comparison only)", r["mt5_micro_comparison_only"]), "",
        "In plain language:",
        f"- **{m['trades']} trades**, net result **{m['net_profit']} USD** on a start of "
        f"{r.get('starting_balance')} ({m['net_return_pct']}%). The worst fall from a high point was "
        f"{m['max_drawdown_pct']}%.",
        f"- Average commission per trade: {m['avg_commission']} USD. Minimum target (average win at "
        f"least 3x that): **{'met' if m['min_target_met'] else 'NOT met'}**.",
        f"- **{m['late_fills']} trades filled late** (the signal had to wait), on average "
        f"{m['avg_delay_min']} minutes after the signal.",
        f"- Signals that could not fill at once, by first reason: {r['signals_blocked_first_reason']}. "
        f"The live cost gate blocked **{r['gate_blocked_signals']}** signals (`gate_skips.csv`).",
        f"- Signals dropped: {r['signals_dropped']}.",
        f"- How trades ended: {r['exit_reasons']}.",
        f"- Kill switch hit: {r['kill_switch']} (stress run: {r['kill_switch_stress']}). "
        f"Research restarts after a kill: {len(r['kill_events'])} (stress run: {len(r['kill_events_stress'])}); "
        "any restart counts as a FAIL.",
        "- Monte Carlo: the same trades in 1,000 random orders. The p95 drawdown is the fall that only "
        "5% of orderings beat; it is a better guide to risk than the single historical drawdown.",
        "- MT5 micro re-prices the same trades with spread + swap and no stake cap. It is for "
        "comparison only; a pass is judged on Multiplier costs.", "",
        "Files: `trades.csv`, `equity.png`, `metrics.json`, `gate_skips.csv`.",
    ]
    return "\n".join(lines) + "\n"
