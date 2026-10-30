"""Cost what-if: re-price recorded trades at a different cost per trade (research only).

NOT a strategy and NOT a candidate generator. It answers "at what cost per
trade would a Phase 4 result have passed?" by keeping each recorded trade's
price move and swapping its cost. Nothing here may be used to pick or tune a
strategy; the holdout is never read.

Model:
- A trade's before-cost move is its recorded profit with every modelled cost
  added back (audit.gross_of: commission, 0.5 pip entry slippage, 1 pip
  stop-loss slippage), as a fraction of the position size.
- New cost per trade, in pips of the entry price:
  * "total" model (Deriv-like, no swap): max(C, the trade's own slippage), so
    C is the total cost including slippage; the loss stays capped at the stake.
  * "broker" model: a fee (1.0 pip EUR/USD and GBP/USD, 1.3 USD/JPY) plus the
    same slippage rules plus overnight swap as in the MT5 comparison (mt5.py);
    no stake cap (a CFD has none).
- The account is rebuilt in time order from 100 USD: stake = 3% of the closed
  balance at entry (cents, min 1 USD), x100. Kill switch in research "observe"
  mode on the closed balance: at or below 50 USD the event is recorded and the
  balance restarts at 100 USD.

Approximations (stated in reports/cost_whatif.md): the same trades and exit
prices are kept at every cost (in a real run a different balance path can
change daily-loss pauses and which signal gets a position slot); the kill
switch looks at closed balance, not live equity; exits at Deriv's stop-out
level are kept as they were.
"""

from __future__ import annotations

import math

from fxbot.backtest import fills, mt5
from fxbot.backtest.audit import gross_of

PIP = fills.PIP
BROKER_FEE_PIPS = {"frxEURUSD": 1.0, "frxGBPUSD": 1.0, "frxUSDJPY": 1.3}


def slippage_pips(t: dict) -> float:
    return fills.ENTRY_SLIPPAGE_PIPS + (fills.SL_SLIPPAGE_PIPS if t["reason"] == "stop_loss" else 0.0)


def gross_move(t: dict) -> float:
    """Before-cost move as a fraction of position size (positive = in the trade's favour)."""
    return gross_of(t) / (t["stake"] * t["multiplier"])


def swap_fraction(t: dict) -> float:
    """MT5 overnight swap for this trade's nights, as a fraction of position size."""
    sym, up = t["symbol"], t["direction"] == "MULTUP"
    n = mt5.rollovers(t["entry_epoch"], t["exit_epoch"])
    if not n:
        return 0.0
    pts = mt5.SWAP_POINTS[sym][0 if up else 1]
    per_unit = mt5.POINT[sym] * pts * n                     # quote currency per unit of base
    # USD/JPY: units = notional (USD), quote JPY -> divide by price; others: units = notional / entry.
    return per_unit / t["exit"] if sym == "frxUSDJPY" else per_unit / t["entry"]


def cost_total(c_pips: float):
    """Deriv-like what-if: C pips total per trade, slippage included, no swap, loss capped at stake."""
    def fn(t):
        return max(c_pips, slippage_pips(t)) * PIP[t["symbol"]] / t["entry"], True
    return fn


def cost_broker(fee: dict = BROKER_FEE_PIPS):
    """Low-cost broker what-if: fee + the same slippage + swap, no stake cap."""
    def fn(t):
        c = (fee[t["symbol"]] + slippage_pips(t)) * PIP[t["symbol"]] / t["entry"]
        return c - swap_fraction(t), False
    return fn


def cost_recorded(t: dict) -> tuple[float, bool]:
    """The cost the trade actually paid (commission + slippage): re-pricing with it must
    reproduce the recorded result. Used as a self-check."""
    size = t["stake"] * t["multiplier"]
    return t["commission"] / size + slippage_pips(t) * PIP[t["symbol"]] / t["entry"], True


def reprice(trades: list[dict], cost_fn, start: float = 100.0, risk: float = 0.03,
            multiplier: int = 100, kill: float = 0.5) -> dict:
    """Rebuild the account in time order with a new cost per trade.

    Returns {"trades": [...re-priced copies with profit, balance_after, stake, cost_usd],
             "kill_events": [...], "net": ..., "skipped": n}.
    """
    events = []
    for i, t in enumerate(trades):
        events.append((int(t["entry_epoch"]), 1, i))
        events.append((int(t["exit_epoch"]), 0, i))           # exits before entries at the same minute
    events.sort()
    bal, open_stake, out, kills, skipped = start, {}, {}, [], 0
    for epoch, is_entry, i in events:
        t = trades[i]
        if is_entry:
            stake = math.floor(bal * risk * 100 + 1e-9) / 100
            if stake < 1.0:
                skipped += 1
                continue
            open_stake[i] = stake
            continue
        if i not in open_stake:
            continue
        stake = open_stake.pop(i)
        size = stake * multiplier
        cost, capped = cost_fn(t)
        profit = size * (gross_move(t) - cost)
        if capped:
            profit = max(profit, -stake)
        profit = round(profit, 2)
        bal = round(bal + profit, 2)
        out[i] = {**t, "stake": stake, "profit": profit, "balance_after": bal,
                  "cost_usd": size * cost, "multiplier": multiplier}
        if bal <= kill * start + 1e-9:
            kills.append({"epoch": epoch, "balance": bal})
            bal = start          # the trade keeps its real balance_after, as the engine records it
    ordered = [out[i] for i in sorted(out, key=lambda k: (int(trades[k]["exit_epoch"]), k))]
    return {"trades": ordered, "kill_events": kills, "net": round(sum(t["profit"] for t in ordered), 2),
            "skipped": skipped}
