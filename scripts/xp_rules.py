"""Perfect-fit experiment, stage 2: rule-based search (fast screen, every variant logged).

Families (all on closed 1h candles, entries only at allowed hours):
  R1 time-of-day: fixed direction per pair and hour cell, cells chosen in-sample
  R2 one indicator: feature above / below its in-sample per-pair quantile -> Up or Down
  R3 two indicators: the best R2 rules AND a second feature condition
  R4 cell filter: the best R2/R3 rules, keeping only the pair x hour cells that made money
Each family x exit setup (528 setups) is one variant. Results: research/experiment/rules_top.json.

Run: python scripts/xp_rules.py [r1|r2|r3|r4]   (each stage resumes from saved files)
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np

import xp_lib as L

QS = (0.1, 0.2, 0.3, 0.7, 0.8, 0.9)


def per_pair_quantile(x: np.ndarray, sym: np.ndarray, q: float) -> np.ndarray:
    thr = np.zeros(3)
    for s in range(3):
        thr[s] = np.quantile(x[sym == s], q)
    return thr[sym]


def cond(b, f: int, q: float) -> np.ndarray:
    """Boolean: feature f beyond its per-pair quantile q (above if q > 0.5, below otherwise)."""
    x = b["X"][:, f]
    thr = per_pair_quantile(x, b["sym"], q)
    return x > thr if q > 0.5 else x < thr


def top_save(name, items, n=200):
    items = sorted(items, key=lambda r: -r["score"])[:n]
    L.save_json(L.RES / f"rules_{name}.json", items)
    return items


def r1(b, log):
    """Best direction per pair x hour cell, chosen per exit setup (pure in-sample)."""
    out = []
    hour = b["X"][:, 1].astype(int)
    for k in range(len(b["cfg"])):
        d = np.zeros(len(hour), dtype=int)
        for s in range(3):
            for h in range(24):
                m = (b["sym"] == s) & (hour == h)
                if not m.any():
                    continue
                up, dn = b["pnl"][k, m, 0].mean(), b["pnl"][k, m, 1].mean()
                if max(up, dn) > 0:
                    d[m] = 1 if up > dn else -1
        res = L.screen(k, d)
        vid = log.add("rules", "R1 time-of-day cells", "best direction per pair x hour cell (in-sample)", k, res)
        out.append({"id": vid, "family": "R1", "k": k, "rule": {"type": "cells"}, **res})
    return out


def r2(b, log):
    out = []
    names = b["names"]
    nf = b["X"].shape[1]
    t0 = time.time()
    conds = {(f, q): cond(b, f, q) for f in range(nf) for q in QS if names[f] != "sym"}
    for (f, q), c in conds.items():
        for sign in (1, -1):
            d = np.where(c, sign, 0)
            for k in range(len(b["cfg"])):
                res = L.screen(k, d)
                desc = f"{names[f]} {'>' if q > 0.5 else '<'} q{int(q * 100)} -> {'Up' if sign > 0 else 'Down'}"
                vid = log.add("rules", "R2 one indicator", desc, k, res)
                out.append({"id": vid, "family": "R2", "k": k, "rule": {"f": [int(f)], "q": [q], "sign": sign},
                            "desc": desc, **res})
        if len(log.buf) > 50000:
            log.flush()
    print(f"r2: {len(out)} variants in {time.time() - t0:.0f}s", flush=True)
    return out


def r3(b, log, base):
    out = []
    names = b["names"]
    nf = b["X"].shape[1]
    seen = set()
    for r in base[:60]:
        f1, q1, sign, k = r["rule"]["f"][0], r["rule"]["q"][0], r["rule"]["sign"], r["k"]
        c1 = cond(b, f1, q1)
        ks = sorted({k, *[x["k"] for x in base[:20]]})
        for f2 in range(nf):
            if f2 == f1 or names[f2] == "sym":
                continue
            for q2 in (0.2, 0.3, 0.5, 0.501, 0.7, 0.8):
                c = c1 & cond(b, f2, q2)
                d = np.where(c, sign, 0)
                for kk in ks:
                    key = (f1, q1, sign, f2, q2, kk)
                    if key in seen:
                        continue
                    seen.add(key)
                    res = L.screen(kk, d)
                    desc = (f"{r['desc']} AND {names[f2]} {'>' if q2 > 0.5 else '<'} q{int(round(q2 * 100))}")
                    vid = log.add("rules", "R3 two indicators", desc, kk, res)
                    out.append({"id": vid, "family": "R3", "k": kk,
                                "rule": {"f": [int(f1), int(f2)], "q": [q1, q2], "sign": sign}, "desc": desc, **res})
        if len(log.buf) > 50000:
            log.flush()
    return out


def rule_dir(b, rule) -> np.ndarray:
    c = np.ones(len(b["t"]), dtype=bool)
    for f, q in zip(rule["f"], rule["q"]):
        c &= cond(b, f, q)
    return np.where(c, rule["sign"], 0)


def r4(b, log, base):
    out = []
    hour = b["X"][:, 1].astype(int)
    for r in base[:100]:
        d0 = rule_dir(b, r["rule"])
        k = r["k"]
        sgn = (d0 < 0).astype(int)
        p = b["pnl"][k, np.arange(len(d0)), sgn]
        keep = np.zeros(len(d0), dtype=bool)
        cells = []
        for s in range(3):
            for h in range(24):
                m = (b["sym"] == s) & (hour == h) & (d0 != 0)
                if m.any() and p[m].sum() > 0:
                    keep |= m
                    cells.append([s, h])
        res = L.screen(k, np.where(keep, d0, 0))
        desc = r["desc"] + f" | only profitable pair x hour cells ({len(cells)})"
        vid = log.add("rules", "R4 cell filter", desc, k, res)
        out.append({"id": vid, "family": "R4", "k": k, "rule": {**r["rule"], "cells": cells}, "desc": desc, **res})
    return out


def main() -> int:
    stage = sys.argv[1] if len(sys.argv) > 1 else "all"
    b = L.build()
    if stage in ("r1", "all"):
        log = L.VariantLog("r1")
        top_save("r1", r1(b, log)); log.flush()
    if stage in ("r2", "all"):
        log = L.VariantLog("r2")
        top_save("r2", r2(b, log)); log.flush()
    if stage in ("r3", "all"):
        log = L.VariantLog("r3")
        base = json.loads((L.RES / "rules_r2.json").read_text())
        top_save("r3", r3(b, log, base)); log.flush()
    if stage in ("r4", "all"):
        log = L.VariantLog("r4")
        base = sorted(json.loads((L.RES / "rules_r2.json").read_text())
                      + json.loads((L.RES / "rules_r3.json").read_text()), key=lambda r: -r["score"])
        top_save("r4", r4(b, log, base)); log.flush()
    for name in ("r1", "r2", "r3", "r4"):
        p = L.RES / f"rules_{name}.json"
        if p.exists():
            best = json.loads(p.read_text())[0]
            print(name, best.get("desc", ""), L.cfg_str(b["cfg"][best["k"]]),
                  {k: best[k] for k in ("trades", "net_pct", "dd_pct", "score")})
    return 0


if __name__ == "__main__":
    sys.exit(main())
