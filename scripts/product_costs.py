"""Cost of one trade as a share of a typical candle move, per product.

Compares Deriv Multipliers (real-account commission measured in Phase 2,
config/contract_specs.yaml) with Deriv MT5 forex CFDs (Standard and micro
symbols, figures from https://deriv.com/en/trading-specifications, read
2026-10-28). Typical moves come from research/typical_moves.json
(scripts/typical_moves.py). Writes research/product_costs.json and prints a
markdown table for reports/product_choice.md.

Assumptions (all in pips, round trip):
- Multipliers: commission = real commission rate x price; entry and exit
  fill at the mid price (Phase 2 demo trades), no swap (NOT yet confirmed:
  overnight demo test pending).
- MT5: cost = spread + expected swap. Spread at the published minimum, and
  a stress case of 2x the minimum (typical spreads are not published).
  Swap = average of long and short charge per night (credit counts as
  negative), times the expected rollovers crossed: 1h hold 0.06, 4h hold
  0.23, 1-day hold 1.4 (incl. the Wednesday triple swap).
- Slippage is left out for both: it is a separate backtest assumption.

Run: python scripts/product_costs.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import _bootstrap  # noqa: F401
import yaml

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
ROLLOVERS = {"1h": 0.06, "4h": 0.23, "1d": 1.4}


def main() -> int:
    specs = yaml.safe_load((ROOT / "config" / "contract_specs.yaml").read_text())
    real = specs["connections"]["real"]["symbols"]
    moves = json.loads((ROOT / "research" / "typical_moves.json").read_text())
    out: dict = {}
    print("| Pair | Candle | Typical range (Deriv 1y / Dukascopy 5y) | Multipliers (real) | "
          "MT5 Standard | MT5 Standard, 2x spread | MT5 micro |")
    print("|---|---|---|---|---|---|---|")
    for sym in SYMBOLS:
        price = real[sym]["median_spot"]
        rate = real[sym]["multipliers"][100]["commission_rate_pct"]["median"] / 100
        mult_cost = rate * price / PIP[sym]
        m = MT5[sym]
        swap_night = (-m["swap_long"] - m["swap_short"]) / 2 / 10  # average cost per night, pips
        for frame in ("1h", "4h", "1d"):
            d = moves[sym]["deriv_1y"][frame]["range_median"]
            k = moves[sym]["dukascopy_5y"][frame]["range_median"]
            swap = swap_night * ROLLOVERS[frame]
            costs = {
                "multipliers_real": mult_cost,
                "mt5_standard": m["spread"] / PIP[sym] + swap,
                "mt5_standard_2x": 2 * m["spread"] / PIP[sym] + swap,
                "mt5_micro": m["spread_micro"] / PIP[sym] + swap,
            }
            out.setdefault(sym, {})[frame] = {"range_deriv_1y": d, "range_dukascopy_5y": k,
                                              "costs_pips": {n: round(c, 2) for n, c in costs.items()},
                                              "share_of_range_deriv_1y": {n: round(c / d, 3) for n, c in costs.items()}}
            cells = " | ".join(f"{c:.1f} pips = {c / d:.0%}" for c in costs.values())
            print(f"| {sym} | {frame} | {d} / {k} pips | {cells} |")
    (ROOT / "research" / "product_costs.json").write_text(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
