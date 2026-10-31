"""Perfect-fit experiment, stage 4: re-run the screen's finalists in the real engine.

Finalists: the best 3 variants of each rule family (R1-R4) and the best 4 of each
ML model, by screen score. Each is replayed in the event-driven engine with every
hard limit (kill switch enforced, as the live bot would). The engine's net profit /
max drawdown decides the winner. Results: research/experiment/verify.json (resumable).

Run: python scripts/xp_verify.py [--max-minutes 9]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np

import xp_lib as L
import xp_rules as R


def finalists() -> list[dict]:
    out = []
    for fam in ("r1", "r2", "r3", "r4"):
        p = L.RES / f"rules_{fam}.json"
        if p.exists():
            out += [dict(x, source=fam) for x in json.loads(p.read_text())[:3]]
    ml = json.loads((L.RES / "ml_results.json").read_text())
    for m in sorted({r["model"] for r in ml}):
        rs = sorted((r for r in ml if r["model"] == m), key=lambda r: -r["score"])[:4]
        out += [dict(x, source="ml") for x in rs]
    # Round 2: the screen's drawdown (closed trades only) is near zero for every high-capacity
    # model, so it cannot rank them. Re-run the 5 exit setups with the best engine scores
    # from round 1 with the three highest-capacity models at every threshold.
    vp = L.RES / "verify.json"
    if vp.exists():
        ver = [r for r in json.loads(vp.read_text()) if r["source"] == "ml" and r.get("round", 1) == 1]
        cfg = L.build()["cfg"]
        top_cfg = []
        for r in sorted(ver, key=lambda r: -r["engine"]["score"]):
            k = int(r["key"].split(":")[2])
            if k not in top_cfg:
                top_cfg.append(k)
        have = {(r["model"], r["k"], r["thr"]) for r in out if r["source"] == "ml"}
        for r in ml:
            if r["model"] in ("knn_1", "lgbm_l", "lgbm_m") and r["k"] in top_cfg[:5] \
                    and (r["model"], r["k"], r["thr"]) not in have and r["trades"] > 0:
                out.append(dict(r, source="ml", round=2))
    return out


def direction_of(f: dict) -> np.ndarray:
    b = L.build()
    if f["source"] == "ml":
        pr = np.load(L.CACHE / "ml_pred" / f"{f['model']}_{f['k']}.npy")
        best = pr.max(1)
        return np.where(best > f["thr"], np.where(pr[:, 0] >= pr[:, 1], 1, -1), 0)
    if f["source"] == "r1":
        hour = b["X"][:, 1].astype(int)
        k = f["k"]
        d = np.zeros(len(hour), dtype=int)
        for s in range(3):
            for h in range(24):
                m = (b["sym"] == s) & (hour == h)
                if m.any():
                    up, dn = b["pnl"][k, m, 0].mean(), b["pnl"][k, m, 1].mean()
                    if max(up, dn) > 0:
                        d[m] = 1 if up > dn else -1
        return d
    d = R.rule_dir(b, f["rule"])
    cells = f["rule"].get("cells")
    if cells is not None:
        hour = b["X"][:, 1].astype(int)
        keep = np.zeros(len(d), dtype=bool)
        for s, h in cells:
            keep |= (b["sym"] == s) & (hour == h)
        d = np.where(keep, d, 0)
    return d


def key_of(f: dict) -> str:
    if f["source"] == "ml":
        return f"ml:{f['model']}:{f['k']}:{f['thr']}"
    return f"{f['source']}:{f['id']}"


def _run(f: dict) -> dict:
    eng = L.run_signals(direction_of(f), f["k"])
    return {"key": key_of(f), "round": f.get("round", 1), "source": f["source"], "desc": f.get("desc") or f.get("model"),
            "config": L.cfg_str(L.build()["cfg"][f["k"]]), "screen": {k: f[k] for k in ("trades", "net_pct", "dd_pct", "score")},
            "engine": L.engine_score(eng.state)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=9.0)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    t0 = time.time()
    path = L.RES / "verify.json"
    done = json.loads(path.read_text()) if path.exists() else []
    have = {d["key"] for d in done}
    todo = [f for f in finalists() if key_of(f) not in have]
    print(f"{len(todo)} finalists to run in the engine", flush=True)
    with ProcessPoolExecutor(a.workers) as ex:
        for r in ex.map(_run, todo):
            done.append(r)
            L.save_json(path, done)
            print(r["key"], r["config"], r["engine"], f"({time.time() - t0:.0f}s)", flush=True)
            if time.time() - t0 > a.max_minutes * 60:
                print("time budget used; run again to continue")
                ex.shutdown(cancel_futures=True)
                return 2
    best = max(done, key=lambda r: r["engine"]["score"])
    print("BEST:", best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
