"""Perfect-fit experiment, stage 1: candidate entries, features and trade outcomes.

Pre-holdout data only (2021-10-27 to 2026-04-27). Candidates are 1h candle closes
whose next minute can open a trade at once: hours 06-17 UTC except 12:00 (cost gate
on every pair) and 13:00 on EUR/USD (cost gate). Saves cache/xp/build.npz.

Run: python scripts/xp_build.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

import _bootstrap  # noqa: F401

from fxbot import sessions
from fxbot.backtest import fastsim, fills
from fxbot.backtest.candles import aggregate
from fxbot.backtest.research import DATA_END, DATA_START, _m1
from fxbot.strategies.pf_features import FEATURE_NAMES, SYMBOLS, features

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "cache" / "xp"


def configs() -> np.ndarray:
    rows = []
    for sl in (0, 10, 15, 20, 30, 50):
        for tp in (0, 10, 15, 20, 30, 50, 80):
            for hold in (1, 2, 3, 4, 6, 8, 12, 24, 0):
                rows.append((100, sl, tp, hold))
    for sl in (0, 10, 15, 20, 30):
        for tp in (0, 10, 15, 20, 30, 50):
            for hold in (1, 2, 4, 8, 0):
                rows.append((200, sl, tp, hold))
    return np.array(rows, dtype=np.float64)


def allowed_hour(sym: str, h: int) -> bool:
    return 6 <= h <= 17 and h != 12 and not (sym == "frxEURUSD" and h == 13)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    table = fills.CommissionTable()
    cfg = configs()
    m1 = {s: _m1(s) for s in SYMBOLS}
    h1 = {s: aggregate(m1[s], "1h") for s in SYMBOLS}
    rows = {k: [] for k in ("sym", "t", "j0", "rate", "dl100", "dl200", "bar")}
    feats = []
    t0 = time.time()
    for si, s in enumerate(SYMBOLS):
        c = h1[s]
        ep = m1[s].epoch
        for i in range(len(c)):
            t = int(c.end[i])
            if not allowed_hour(s, (t % 86400) // 3600) or not sessions.entry_allowed_by_calendar(t)[0]:
                continue
            j0 = int(np.searchsorted(ep, t))
            if j0 >= len(ep) or ep[j0] != t:
                continue
            peers = {o: h1[o].slice(int(np.searchsorted(h1[o].end, t, "right"))) for o in SYMBOLS if o != s}
            f = features(s, c.slice(i + 1), peers)
            if f is None:
                continue
            rows["sym"].append(si); rows["t"].append(t); rows["j0"].append(j0); rows["bar"].append(i)
            rows["rate"].append(table.rate(s, t))
            rows["dl100"].append(sessions.exit_deadline(t, 100)); rows["dl200"].append(sessions.exit_deadline(t, 200))
            feats.append(f)
        print(f"{s}: {sum(1 for x in rows['sym'] if x == si)} candidates ({time.time() - t0:.0f}s)", flush=True)
    a = {k: np.array(v) for k, v in rows.items()}
    X = np.vstack(feats)
    K, N = len(cfg), len(a["t"])
    pnl = np.zeros((K, N, 2), dtype=np.float32)
    ext = np.zeros((K, N, 2), dtype=np.int64)
    for si, s in enumerate(SYMBOLS):
        idx = np.where(a["sym"] == si)[0]
        b = m1[s]
        p, x = fastsim.trade_outcomes(b.epoch, b.open, b.high, b.low, a["j0"][idx], a["dl100"][idx],
                                      a["dl200"][idx], a["rate"][idx].astype(np.float64),
                                      fills.PIP[s], cfg)
        pnl[:, idx, :] = p
        ext[:, idx, :] = x
        print(f"{s}: outcomes done ({time.time() - t0:.0f}s)", flush=True)
    np.savez(OUT / "build.npz", cfg=cfg, X=X, names=np.array(FEATURE_NAMES), pnl=pnl, ext=ext,
             start=str(DATA_START), end=str(DATA_END), **a)
    print(f"saved {N} candidates x {K} exit configs; {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
