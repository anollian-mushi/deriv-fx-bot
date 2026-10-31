"""Fast screening simulator for the perfect-fit experiment (research only, needs numba).

Two pieces:
1. trade_outcomes(): for every candidate entry (pair, minute) and direction, the
   result of one Multiplier trade in stake units (profit / stake), using the same
   fill rules as fills.py: entry at the 1m open +0.5 pip, commission = rate for the
   opening UTC hour x multiplier, stop loss exits 1 pip past its level (or at a
   gapped open + 1 pip), stop out loses the stake, SL/stop out beat TP inside a
   candle, forced close at the deadline (20:30 before a weekend, 20:50 for x200),
   strategy time exit at the open of the minute the hold ends.
2. portfolio(): a quick account simulation of a list of chosen trades with the
   hard limits (3% stake compounding, max 2 open / 1 per pair, daily loss limit
   on closed balance, kill switch). It is only a screen: every finalist is re-run
   in the real event-driven engine (fxbot.backtest.engine), whose result is the
   one reported.
"""

from __future__ import annotations

import numpy as np
from numba import njit, prange


@njit(cache=True)
def _round(price, ps, mode):
    """mc.round_price: 0 nearest, 1 up, -1 down (with its float-noise guard)."""
    steps = np.round(price / ps, 6)
    if mode == 0:
        n = np.floor(steps + 0.5)
    elif mode == 1:
        n = np.ceil(steps)
    else:
        n = np.floor(steps)
    return n * ps


@njit(cache=True)
def _one(ep, op, hi, lo, j0, deadline, t_exit, up, mult, rate, pip, sl_pips, tp_pips):
    """Simulate one trade from 1m index j0. Returns (profit_in_stake_units, exit_epoch)."""
    sign = 1.0 if up else -1.0
    e = op[j0] + sign * 0.5 * pip
    c = mult * rate                                  # commission, stake units
    ps = pip / 10.0                                   # price step (0.00001 / 0.001)
    so = _round(e * (1.0 - sign * (1.0 - c) / mult), ps, -1 if up else 1)   # stop-out price
    has_sl = False
    slp = 0.0
    if sl_pips > 0:
        amt = mult * sl_pips * pip / e + c
        if amt < 1.0:
            has_sl = True
            slp = _round(e * (1.0 - sign * (amt - c) / mult), ps, 0)
    has_tp = False
    tpp = 0.0
    tpa = 0.0
    if tp_pips > 0:
        tpa = mult * tp_pips * pip / e - c
        if tpa < 0.001:
            tpa = 0.001
        has_tp = True
        tpp = _round(e * (1.0 + sign * (tpa + c) / mult), ps, 0)
    n = ep.shape[0]
    j = j0
    while j < n:
        t = ep[j]
        if j > j0:
            if t >= t_exit or t >= deadline:
                p = mult * sign * (op[j] - e) / e - c
                return max(p, -1.0), t
        o = e if j == j0 else op[j]
        worst = lo[j] if up else hi[j]
        best = hi[j] if up else lo[j]
        if has_sl and sign * (o - slp) <= 0:
            px = o - sign * pip
            return max(mult * sign * (px - e) / e - c, -1.0), t
        if sign * (o - so) <= 0:
            return -1.0, t
        if has_tp and sign * (o - tpp) >= 0:
            return tpa, t
        if has_sl and sign * (worst - slp) <= 0:
            px = slp - sign * pip
            return max(mult * sign * (px - e) / e - c, -1.0), t
        if sign * (worst - so) <= 0:
            return -1.0, t
        if has_tp and sign * (best - tpp) >= 0:
            return tpa, t
        j += 1
    p = mult * sign * (op[n - 1] - e) / e - c
    return max(p, -1.0), ep[n - 1] + 60


@njit(parallel=True, cache=True)
def trade_outcomes(ep, op, hi, lo, j0s, dl100, dl200, rates, pip, cfg):
    """cfg rows: (mult, sl_pips, tp_pips, hold_hours). Returns pnl[k, i, d], exit[k, i, d]."""
    K, N = cfg.shape[0], j0s.shape[0]
    pnl = np.zeros((K, N, 2))
    ext = np.zeros((K, N, 2), dtype=np.int64)
    for i in prange(N):
        j0 = j0s[i]
        if j0 < 0:
            continue
        t0 = ep[j0]
        for k in range(K):
            mult = cfg[k, 0]
            dl = dl100[i] if mult == 100 else dl200[i]
            t_exit = t0 + int(cfg[k, 3] * 3600) if cfg[k, 3] > 0 else 2 ** 62
            for d in range(2):
                p, x = _one(ep, op, hi, lo, j0, dl, t_exit, d == 0, mult, rates[i], pip,
                            cfg[k, 1], cfg[k, 2])
                pnl[k, i, d] = p
                ext[k, i, d] = x
    return pnl, ext


@njit(cache=True)
def portfolio(t_in, t_out, sym, pnl, start=100.0, risk=0.03, daily=0.10, kill=0.5):
    """Trades sorted by t_in. Returns (net_return, max_dd_fraction, n_taken, killed).

    Equity is tracked at trade closes (the engine also tracks it hourly with open
    profit, so its drawdown is a little larger)."""
    n = t_in.shape[0]
    bal = start
    peak = start
    dd = 0.0
    open_out = np.full(3, -1, dtype=np.int64)
    open_stake = np.zeros(3)
    open_pnl = np.zeros(3)
    day = -1
    day_start = start
    taken = 0
    for i in range(n):
        t = t_in[i]
        # close everything that ended by t, in exit order
        while True:
            best = -1
            for s in range(3):
                if open_out[s] >= 0 and open_out[s] <= t:
                    if best < 0 or open_out[s] < open_out[best]:
                        best = s
            if best < 0:
                break
            tx = open_out[best]
            if tx // 86400 != day:
                day = tx // 86400
                day_start = bal
            bal += open_stake[best] * open_pnl[best]
            open_out[best] = -1
            if bal > peak:
                peak = bal
            if (peak - bal) / peak > dd:
                dd = (peak - bal) / peak
            if bal <= kill * start:
                return bal / start - 1.0, max(dd, 0.5), taken, True
        if t // 86400 != day:
            day = t // 86400
            day_start = bal
        s = sym[i]
        if open_out[s] >= 0:
            continue
        nopen = 0
        for q in range(3):
            if open_out[q] >= 0:
                nopen += 1
        if nopen >= 2:
            continue
        if bal <= (1.0 - daily) * day_start:
            continue
        stake = min(np.floor(bal * risk * 100) / 100, 2000.0)
        if stake < 1.0:
            continue
        open_out[s] = t_out[i]
        open_stake[s] = stake
        open_pnl[s] = pnl[i]
        taken += 1
    for s in range(3):
        if open_out[s] >= 0:
            bal += open_stake[s] * open_pnl[s]
            if bal > peak:
                peak = bal
            if (peak - bal) / peak > dd:
                dd = (peak - bal) / peak
    return bal / start - 1.0, dd, taken, False
