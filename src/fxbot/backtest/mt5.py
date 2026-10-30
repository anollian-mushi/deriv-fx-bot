"""Re-price backtest trades at Deriv MT5 micro costs. COMPARISON ONLY.

A pass is always judged on Multiplier costs (CLAUDE.md). This answers "would
the same trades do better on MT5?" using the figures in
reports/product_choice.md section 3 (deriv.com/en/trading-specifications,
read 2026-10-28):
- same entry and exit prices and the same position size (stake x multiplier)
- cost = the published minimum spread of the micro symbol, paid once
- swap for every 21:00 UTC rollover held, triple on Wednesdays (points per
  unit x point size; long or short rate by direction)
- MT5 has no stop out at the stake, so losses are not capped
"""

from __future__ import annotations

import datetime as dt

POINT = {"frxEURUSD": 0.00001, "frxGBPUSD": 0.00001, "frxUSDJPY": 0.001}
SPREAD_MICRO = {"frxEURUSD": 0.00007, "frxGBPUSD": 0.00007, "frxUSDJPY": 0.009}
SWAP_POINTS = {  # per unit per night: (long, short)
    "frxEURUSD": (-11.42, 2.66), "frxGBPUSD": (-5.43, -4.13), "frxUSDJPY": (9.95, -21.98)}
ROLLOVER_SOD = 21 * 3600


def rollovers(entry_epoch: int, exit_epoch: int) -> int:
    """Swap nights between entry and exit; a Wednesday rollover counts 3."""
    n = 0
    day = entry_epoch - entry_epoch % 86400
    while day + ROLLOVER_SOD < exit_epoch:
        r = day + ROLLOVER_SOD
        if r >= entry_epoch and dt.datetime.fromtimestamp(r, dt.timezone.utc).weekday() < 5:
            n += 3 if dt.datetime.fromtimestamp(r, dt.timezone.utc).weekday() == 2 else 1
        day += 86400
    return n


def mt5_profit(trade: dict) -> float:
    sym, up = trade["symbol"], trade["direction"] == "MULTUP"
    entry, exit_ = float(trade["entry"]), float(trade["exit"])
    notional = trade["stake"] * trade["multiplier"]          # USD
    units = notional if sym == "frxUSDJPY" else notional / entry
    move = (exit_ - entry) if up else (entry - exit_)
    swap_pts = SWAP_POINTS[sym][0 if up else 1]
    quote_pnl = units * (move - SPREAD_MICRO[sym]) + units * POINT[sym] * swap_pts * rollovers(
        trade["entry_epoch"], trade["exit_epoch"])
    return round(quote_pnl / exit_ if sym == "frxUSDJPY" else quote_pnl, 2)
