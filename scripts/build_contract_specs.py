"""Phase 2: summarise every proposal sample and demo trade into
config/contract_specs.yaml and research/phase2/cost_tables.md.

Re-run after new samples arrive; both files are rebuilt from scratch.
Hand-written findings (how Deriv closes contracts, overnight results, open
questions) live in FINDINGS below and in reports/costs.md.

Run: python scripts/build_contract_specs.py
"""

from __future__ import annotations

import csv
import gzip
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import _bootstrap  # noqa: F401
import yaml

from fxbot.contracts.multiplier import MIN_COMMISSION, commission, profit, stop_out_move

ROOT = Path(__file__).resolve().parents[1]
PHASE2 = ROOT / "research" / "phase2"
SPECS = ROOT / "config" / "contract_specs.yaml"
TABLES = PHASE2 / "cost_tables.md"
REAL_VS_DEMO = PHASE2 / "real_vs_demo.md"
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}
PIP_SIZE = {"frxEURUSD": 0.00001, "frxGBPUSD": 0.00001, "frxUSDJPY": 0.001}


def load_samples() -> list[dict]:
    samples = []
    for path in sorted(PHASE2.glob("proposals_*.jsonl.gz")):
        with gzip.open(path, "rt") as f:
            rows = [json.loads(line) for line in f]
        meta = rows[0]
        samples.append({
            "file": path.name,
            "connection": meta.get("connection") or "public",  # first files predate the field
            "time": meta["started_utc"][:16].replace("T", " ") + "Z",
            "meta": meta,
            "quotes": [r for r in rows if r.get("kind") in ("grid", "edge")],
        })
    return samples


def rate_of(quotes: list[dict], sym: str, mult: int) -> float | None:
    """Commission rate from the largest accepted quote (most digits)."""
    best = None
    for r in quotes:
        if r["kind"] == "grid" and r["accepted"] and r["symbol"] == sym and r["multiplier"] == mult:
            size = r["stake"] * mult
            if best is None or size > best[0]:
                best = (size, r["proposal"]["commission"] / size)
    return best[1] if best else None


def spot_of(quotes: list[dict], sym: str) -> float:
    return statistics.median(r["proposal"]["spot"] for r in quotes
                             if r["accepted"] and r["symbol"] == sym)


def closed_windows(samples: list[dict]) -> list[dict]:
    """Samples where Deriv refused every quote because trading was paused."""
    out = []
    for s in samples:
        quotes = s["quotes"]
        if quotes and not any(r["accepted"] for r in quotes):
            msgs = sorted({r.get("error", "") for r in quotes})
            out.append({"sample": s["time"], "connection": s["connection"], "messages": msgs})
    return out


def summarise(samples: list[dict]) -> dict:
    out: dict = {}
    # A sample taken while trading was paused has no prices: it is listed in
    # closed_windows instead of being averaged in.
    samples = [s for s in samples if any(r["accepted"] for r in s["quotes"])]
    for conn in ("real", "demo", "public"):
        group = [s for s in samples if s["connection"] == conn]
        if not group:
            continue
        c_out = {"samples": [s["time"] for s in group], "symbols": {}}
        for sym in SYMBOLS:
            grid = [r for s in group for r in s["quotes"] if r["kind"] == "grid" and r["symbol"] == sym]
            accepted = sorted({r["multiplier"] for r in grid if r["accepted"]})
            rejected = sorted({r["multiplier"] for r in grid if not r["accepted"]}
                              - set(accepted))
            stake_min = sorted({float(r["proposal"]["validation_params"]["stake"]["min"]) for r in grid if r["accepted"]})
            stake_max = sorted({float(r["proposal"]["validation_params"]["stake"]["max"]) for r in grid if r["accepted"]})
            tp_ratio = defaultdict(set)   # multiplier -> {tp max / stake}
            tp_min = set()
            sl_rule_ok = True
            for r in grid:
                if not r["accepted"]:
                    continue
                vp, p = r["proposal"]["validation_params"], r["proposal"]
                tp_ratio[r["multiplier"]].add(round(float(vp["take_profit"]["max"]) / r["stake"], 2))
                tp_min.add(float(vp["take_profit"]["min"]))
                expected_sl_min = max(0.10, round(p["commission"] + 0.01, 2))
                if abs(float(vp["stop_loss"]["min"]) - expected_sl_min) > 0.001 or \
                        abs(float(vp["stop_loss"]["max"]) - r["stake"]) > 0.001:
                    sl_rule_ok = False
            mults = {}
            for m in accepted:
                rates = [(s["time"], rate_of(s["quotes"], sym, m)) for s in group]
                rates = [(t, v) for t, v in rates if v is not None]
                vals = [v for _, v in rates]
                mults[m] = {
                    "commission_rate_pct": {
                        "median": round(statistics.median(vals) * 100, 5),
                        "min": round(min(vals) * 100, 5), "max": round(max(vals) * 100, 5),
                        "by_sample": {t: round(v * 100, 5) for t, v in rates},
                    },
                    "take_profit_max_per_usd_stake": sorted(tp_ratio[m]),
                }
            # did the edge probes agree with validation_params?
            edges = [r for s in group for r in s["quotes"] if r["kind"] == "edge" and r["symbol"] == sym]
            sl_at_min_rejected = sum(1 for r in edges if r["limit_order"] and "stop_loss" in r["limit_order"]
                                     and not r["accepted"] and "higher than" in r.get("error", "")
                                     and f"{r['limit_order']['stop_loss']:.2f}" in r.get("error", ""))
            c_out["symbols"][sym] = {
                "pip_size": PIP_SIZE[sym],
                "multipliers_accepted": accepted,
                "multipliers_rejected": rejected,
                "contracts_for_lists": sorted({m for s in group for m in s["meta"][sym]["contracts_for_multipliers"]}),
                "stake_min_usd": stake_min, "stake_max_usd": stake_max,
                "take_profit_min_usd": sorted(tp_min),
                "stop_loss_rule_holds": sl_rule_ok,
                "stop_loss_at_exact_min_rejected": sl_at_min_rejected,
                "multipliers": mults,
                "median_spot": round(statistics.median(spot_of(s["quotes"], sym) for s in group), 5),
            }
        out[conn] = c_out
    return out


def trade_summary() -> dict:
    path = ROOT / "research" / "demo_cost_trades.csv"
    trades = [t for t in csv.DictReader(path.open()) if t.get("contract_id")]
    entry = [float(t["entry_vs_proposal_pips"]) for t in trades if t.get("entry_vs_proposal_pips")]
    sells = [float(t["sell_vs_last_bid"]) for t in trades if t.get("sell_vs_last_bid")]
    return {
        "contracts": len(trades),
        "entry_vs_quote_pips": {"mean": round(statistics.mean(entry), 2), "worst": max(entry), "best": min(entry),
                                "n": len(entry)} if entry else None,
        "sell_vs_last_bid_usd": {"mean": round(statistics.mean(sells), 4), "worst": min(sells), "n": len(sells)} if sells else None,
    }


def cost_tables(summary: dict) -> str:
    lines = ["# Phase 2 cost tables (generated)", "",
             "Generated by `scripts/build_contract_specs.py`. Stake 1 USD (the minimum).",
             "Commission rate = median over all samples on that connection.", ""]
    for conn, c in summary.items():
        lines += [f"## {conn} connection", "",
                  "| Pair | Multiplier | Position size | Commission | Commission % of stake | "
                  "Break-even move | Stop-out distance | Stop-out distance as 1h medians |",
                  "|---|---|---|---|---|---|---|---|"]
        for sym, s in c["symbols"].items():
            spot = s["median_spot"]
            for m, info in s["multipliers"].items():
                rate = info["commission_rate_pct"]["median"] / 100
                comm = commission(1, m, rate)
                be_pips = comm / m * spot / PIP[sym]
                so_pips = stop_out_move(1, m, comm) * spot / PIP[sym]
                h1 = H1_MEDIAN_PIPS[sym]
                lines.append(f"| {sym} | x{m} | {m} USD | {comm:.4f} USD | {comm * 100:.1f}% | "
                             f"{be_pips:.1f} pips | {so_pips:.1f} pips | {so_pips / h1:.1f} |")
        lines.append("")
    return "\n".join(lines) + "\n"


def real_vs_demo(summary: dict) -> str:
    """Compare real and demo only on samples taken within 10 minutes of each other:
    the rate changes during the day, so samples hours apart are not comparable."""
    if not {"real", "demo"} <= summary.keys():
        return "# Real vs demo\n\nNo real-account sample yet.\n"
    def minutes(t: str) -> int:
        dt = datetime.strptime(t, "%Y-%m-%d %H:%MZ")
        return int(dt.timestamp() // 60)
    pairs = []
    for rt in summary["real"]["samples"]:
        near = [dt for dt in summary["demo"]["samples"] if abs(minutes(dt) - minutes(rt)) <= 10]
        if near:
            pairs.append((rt, near[0]))
    lines = ["# Real vs demo account: what Multipliers are offered (generated)", "",
             "Generated by `scripts/build_contract_specs.py`. Real-account data comes from",
             "`scripts/check_real_quotes.py` (price quotes only, no orders). Commission rates",
             "are compared only between samples taken within 10 minutes of each other,",
             "because the rate changes during the day.", ""]
    for sym in SYMBOLS:
        r, d = summary["real"]["symbols"][sym], summary["demo"]["symbols"][sym]
        lines.append(f"- {sym}: multipliers real {r['multipliers_accepted']} / demo {d['multipliers_accepted']}; "
                     f"stake real {r['stake_min_usd']}-{r['stake_max_usd']} / demo {d['stake_min_usd']}-{d['stake_max_usd']} USD")
    lines += ["", "| Real sample | Demo sample | Pair | Multiplier | Real rate | Demo rate | Real / demo |",
              "|---|---|---|---|---|---|---|"]
    for rt, dt in pairs:
        for sym in SYMBOLS:
            for m, info in summary["real"]["symbols"][sym]["multipliers"].items():
                rr = info["commission_rate_pct"]["by_sample"].get(rt)
                dd = summary["demo"]["symbols"][sym]["multipliers"].get(m, {}).get(
                    "commission_rate_pct", {}).get("by_sample", {}).get(dt)
                if rr and dd:
                    lines.append(f"| {rt} | {dt} | {sym} | x{m} | {rr}% | {dd}% | {rr / dd:.2f} |")
    if not pairs:
        lines.append("| - | - | no samples close enough in time | | | | |")
    return "\n".join(lines) + "\n"


# Median 1h candle high-low range on Deriv data 2025-10-29..2026-10-27, in pips
# (computed in Phase 2 from data/<symbol>/1h).
H1_MEDIAN_PIPS = {"frxEURUSD": 9.2, "frxGBPUSD": 12.3, "frxUSDJPY": 14.8}


def main() -> int:
    samples = load_samples()
    summary = summarise(samples)
    specs = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "measured": {s["file"]: s["time"] for s in samples},
        "notes": FINDINGS,
        "formulas": FORMULAS,
        "connections": summary,
        "closed_windows": closed_windows(samples),
        "demo_trades": trade_summary(),
    }
    SPECS.parent.mkdir(exist_ok=True)
    header = ("# Deriv Multiplier contract specs, measured in Phase 2.\n"
              "# GENERATED by scripts/build_contract_specs.py from research/phase2/ and\n"
              "# research/demo_cost_trades.csv. Do not edit by hand: re-run the script.\n"
              "# Plain-language explanation: reports/costs.md\n")
    SPECS.write_text(header + yaml.safe_dump(specs, sort_keys=False, width=100))
    TABLES.write_text(cost_tables(summary))
    REAL_VS_DEMO.write_text(real_vs_demo(summary))
    print(f"wrote {SPECS.relative_to(ROOT)} and {TABLES.relative_to(ROOT)} from {len(samples)} samples")
    print(TABLES.read_text())
    return 0


FORMULAS = {
    "position_size": "stake * multiplier",
    "commission": f"max({MIN_COMMISSION}, rate * stake * multiplier), unrounded; shown rounded to cents",
    "profit": "stake * multiplier * (+/-)(exit - entry) / entry - commission, rounded to the nearest cent, floor -stake",
    "stop_out_price": "entry * (1 -/+ (stake - commission) / (stake * multiplier)), rounded to pip size away from entry",
    "take_profit_price": "entry * (1 +/- (take_profit + commission) / (stake * multiplier))",
    "stop_loss_price": "entry * (1 -/+ (stop_loss - commission) / (stake * multiplier))",
    "sign": "first sign for MULTUP, second for MULTDOWN",
}

FINDINGS = {
    "multiplier_list_depends_on_connection": (
        "The public (no login) connection quotes 50/100/150/250/500. The demo account's own connection "
        "quotes and buys 100/200/300/500/800 (= contracts_for) and refuses 50/150/250 even on a direct buy. "
        "The real account (quotes only, 2026-10-28) offers the same list as demo."),
    "stop_loss_minimum": (
        "Deriv reports stop-loss min = commission + 0.01, but rejects exactly that value when the float sum "
        "is not exact (0.2 + 0.01 = 0.21000000000000002). Use stop loss >= commission + 0.02."),
    "real_commission": (
        "Real and demo quote the SAME commission rate at the same moment (checked side by side "
        "2026-10-28 20:07-20:09Z, all pairs, 3 rounds). An earlier '3x' reading compared samples taken "
        "90 minutes apart. The rate changes strongly during the day (EUR/USD 0.0239% at 16:35Z, "
        "0.0717% at 18:07Z, 0.0893% at 20:00Z). The public (no login) connection quotes a different, "
        "lower rate and must not be used for costs."),
    "entry_fill": "Entry spot is the tick mid price ('quote'), within 0.0-0.5 pip of the quoted spot.",
    "manual_sell": "sell with price 0 filled exactly at the last bid_price seen in proposal_open_contract.",
    "tp_sl_close": (
        "Deriv checks TP/SL against the mid price on each tick and closes at the first tick at or past the "
        "level, at that tick's mid. A jump past a stop loss costs the size of the jump (0.6 pip seen)."),
    "daily_pause": (
        "Every weekday Deriv refuses new Multiplier trades from 20:55:00 to 21:30:00 UTC "
        "('Trading is not available from 20:55:00 to 21:30:00.'), although active_symbols says the "
        "market is open and trading_times does not list the pause. Seen 2026-10-28 21:14Z."),
    "status_field": "Contracts Deriv closes itself (TP/SL/stop out) come back with status null and is_sold 1.",
}


if __name__ == "__main__":
    sys.exit(main())
