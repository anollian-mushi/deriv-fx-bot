"""Owner's cost rule for the multi-pair test of i13 (31 Oct 2026): keep a pair only if the
rule's expected move per trade is at least 3x the cost per trade at that pair's base commission.

    python scripts/pairs2_cost_rule.py [--table research/phase2/cost_by_hour_pairs2.json]

The expected move is the average |exit - entry| in pips of the unchanged i13 rule's trades on
that pair in the pre-screen period (data before 2026-10-31), measured with the engine. The cost
is the base-rate commission in pips (rate x price / pip, from the table) plus the 0.5 pip entry
slippage. Writes research/incubator_prescreen/pairs2_cost_rule.json. The pair list is fixed
(fxbot.symbols.PAIRS2); nothing here looks at profit.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401

from fxbot import symbols as S
from fxbot.backtest import fills
from fxbot.backtest import prescreen as P
from fxbot.strategies.families import REGISTRY

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "research" / "incubator_prescreen" / "pairs2_cost_rule.json"
MIN_RATIO = 3.0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--table", default="research/phase2/cost_by_hour_pairs2.json")
    a = ap.parse_args()
    idea = P.IDEAS["morning_overnight_pairs2"]
    table = json.loads((ROOT / a.table).read_text())
    strat = REGISTRY[idea.name](**idea.grid[0])
    v0, v1 = P.oos_span()
    eng = P.run_engine(strat, v0 - P.dt.timedelta(days=P.WARMUP_DAYS), v1, symbols=idea.symbols, table=a.table)
    out = {"table": a.table, "oos_span": [v0.isoformat(), v1.isoformat()], "min_ratio": MIN_RATIO, "pairs": {}}
    for s in idea.symbols:
        tr = [t for t in eng.state.trades if t["symbol"] == s]
        pip = S.PIP[s]
        move = float(np.mean([abs(t["exit"] - t["entry"]) / pip for t in tr])) if tr else None
        rate = table["base_rate_pct"][s] / 100
        price = table["price_used"][s]
        comm_pips = rate * price / pip
        cost = comm_pips + fills.ENTRY_SLIPPAGE_PIPS
        ratio = move / cost if move else None
        out["pairs"][s] = {"trades": len(tr), "avg_abs_move_pips": round(move, 2) if move else None,
                           "base_rate_pct": table["base_rate_pct"][s], "price": price,
                           "commission_pips": round(comm_pips, 2), "cost_pips": round(cost, 2),
                           "ratio": round(ratio, 2) if ratio else None,
                           "keep": bool(ratio is not None and ratio >= MIN_RATIO)}
    out["kept"] = [s for s, v in out["pairs"].items() if v["keep"]]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=1) + "\n")
    for s, v in out["pairs"].items():
        print(f"{S.display(s)}: {v['trades']} trades, avg move {v['avg_abs_move_pips']} pips, cost {v['cost_pips']} pips "
              f"(base {v['base_rate_pct']}% at {v['price']}), ratio {v['ratio']} -> {'KEEP' if v['keep'] else 'DROP'}")
    print("kept:", out["kept"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
