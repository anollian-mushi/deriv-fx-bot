"""Cost of one trade as a share of a typical candle move, per product.

Compares Deriv Multipliers (real-account commission measured in Phase 2,
config/contract_specs.yaml) with Deriv MT5 forex CFDs (Standard and micro
symbols, figures from https://deriv.com/en/trading-specifications, read
2026-10-28). Typical moves come from research/typical_moves.json
(scripts/typical_moves.py). Writes research/product_costs.json and prints a
markdown table for reports/product_choice.md and reports/costs.md.

Holdout: by default only data dated before 2026-04-28 is used, as CLAUDE.md
requires. The moves file must say it excludes the holdout, or the script
stops. --include-holdout uses research/typical_moves_with_holdout.json and
writes research/product_costs_with_holdout.json instead.

Assumptions (all in pips, round trip):
- Multipliers: commission = commission rate x price, at the base rate
  (06:00-17:59 UTC outside news) and at 3x base (seen at news times and
  18:00-19:59 UTC), from research/phase2/cost_by_hour.json (real and demo
  are equal at the same moment).
  Price = median close before 2026-04-28. Entry and exit fill at the mid
  price (Phase 2 demo trades), no swap (NOT yet confirmed: overnight demo
  test pending).
- MT5: cost = spread + expected swap. Spread at the published minimum, and
  a stress case of 2x the minimum (typical spreads are not published).
  Swap = average of long and short charge per night (credit counts as
  negative), times the expected rollovers crossed: 1h hold 0.06, 4h hold
  0.23, 1-day hold 1.4 (incl. the Wednesday triple swap).
- Slippage is left out for both: it is a separate backtest assumption.

Run: python scripts/product_costs.py
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
from fxbot.data.split import HoldoutError

ROOT = Path(__file__).resolve().parents[1]
SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
PIP = {"frxEURUSD": 0.0001, "frxGBPUSD": 0.0001, "frxUSDJPY": 0.01}

# deriv.com/en/trading-specifications, 2026-10-28 (min spread in price units;
# swap in points per lot per night; 10 points = 1 pip for all three pairs)
MT5 = {
    "frxEURUSD": {"spread": 0.00011, "spread_micro": 0.00007, "swap_long": -11.42, "swap_short": 2.66},
    "frxGBPUSD": {"spread": 0.0001, "spread_micro": 0.00007, "swap_long": -5.43, "swap_short": -4.13},
    "frxUSDJPY": {"spread": 0.014, "spread_micro": 0.009, "swap_long": 9.95, "swap_short": -21.98},
}
ROLLOVERS = {"15m": 0.015, "1h": 0.06, "4h": 0.23, "1d": 1.4}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-holdout", action="store_true",
                        help="use moves that include data dated 2026-04-28 or later (final test only)")
    args = parser.parse_args()
    suffix = "_with_holdout" if args.include_holdout else ""
    by_hour = json.loads((ROOT / "research" / "phase2" / "cost_by_hour.json").read_text())
    moves = json.loads((ROOT / "research" / f"typical_moves{suffix}.json").read_text())
    if moves.get("_meta", {}).get("includes_holdout") is not args.include_holdout:
        raise HoldoutError("typical_moves file does not match the holdout setting; re-run "
                           "scripts/typical_moves.py first")
    out: dict = {"_meta": {**moves["_meta"], "base_rate_pct": by_hour["base_rate_pct"]}}
    print("| Pair | Candle | Typical range (Deriv / Dukascopy) | Multipliers, base rate | "
          "Multipliers, 3x base | MT5 Standard | MT5 Standard, 2x spread | MT5 micro |")
    print("|---|---|---|---|---|---|---|---|")
    for sym in SYMBOLS:
        price = moves[sym]["deriv"]["1h"]["price_median"]
        base = by_hour["base_rate_pct"][sym] / 100
        m = MT5[sym]
        swap_night = (-m["swap_long"] - m["swap_short"]) / 2 / 10  # average cost per night, pips
        for frame in ("15m", "1h", "4h", "1d"):
            d = moves[sym]["deriv"][frame]["range_median"]
            k = moves[sym]["dukascopy"][frame]["range_median"]
            swap = swap_night * ROLLOVERS[frame]
            costs = {
                "multipliers_base": base * price / PIP[sym],
                "multipliers_3x": 3 * base * price / PIP[sym],
                "mt5_standard": m["spread"] / PIP[sym] + swap,
                "mt5_standard_2x": 2 * m["spread"] / PIP[sym] + swap,
                "mt5_micro": m["spread_micro"] / PIP[sym] + swap,
            }
            out.setdefault(sym, {})[frame] = {"range_deriv": d, "range_dukascopy": k,
                                              "costs_pips": {n: round(c, 2) for n, c in costs.items()},
                                              "share_of_range_deriv": {n: round(c / d, 3) for n, c in costs.items()}}
            cells = " | ".join(f"{c:.1f} pips = {c / d:.0%}" for c in costs.values())
            print(f"| {sym} | {frame} | {d} / {k} pips | {cells} |")
    (ROOT / "research" / f"product_costs{suffix}.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
