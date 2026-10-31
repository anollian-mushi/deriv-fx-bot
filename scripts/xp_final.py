"""Perfect-fit experiment, stage 5: save the winner and run it as a normal strategy.

1. Picks the finalist with the best engine score (research/experiment/verify.json).
2. Saves it to models/perfect_fit/ (spec.json + model file) for
   fxbot.strategies.perfect_fit.PerfectFit, the class the live bot would run.
3. Runs PerfectFit itself (not the replay table) in the engine over the whole
   pre-holdout period, at the measured commission and at 1.5x, and writes the
   standard report to reports/backtests/experiment_perfect_fit_preholdout/.
   Its trades must match the replay of the same variant.

Run: python scripts/xp_final.py [save|run]
"""

from __future__ import annotations

import json
import sys
import time

import numpy as np

import xp_lib as L
import xp_ml as M
import xp_verify as V

from fxbot.backtest.engine import Engine
from fxbot.backtest.report import write_run
from fxbot.backtest.research import DATA_END, DATA_START, market_data
from fxbot.strategies.perfect_fit import MODEL_DIR, PerfectFit
from fxbot.strategies.pf_features import FEATURE_NAMES, SYMBOLS

RUN_NAME = "experiment_perfect_fit_preholdout"


def winner() -> tuple[dict, dict]:
    ver = json.loads((L.RES / "verify.json").read_text())
    best = max(ver, key=lambda r: r["engine"]["score"])
    fins = {V.key_of(f): f for f in V.finalists()}
    return best, fins[best["key"]]


def save() -> dict:
    best, f = winner()
    b = L.build()
    m, sl, tp, hold = (int(x) for x in b["cfg"][f["k"]])
    spec = {"picked_from": best, "exit": {"mult": m, "sl": sl, "tp": tp, "hold": hold},
            "features": list(FEATURE_NAMES), "trained_on": f"{DATA_START} to {DATA_END} (Dukascopy 1m, pre-holdout)"}
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    for old in MODEL_DIR.iterdir():
        old.unlink()
    if f["source"] == "ml":
        mspec = M.MODELS[f["model"]]
        spec["threshold"] = f["thr"]
        y = b["pnl"][f["k"]].astype(np.float64)
        if mspec["kind"] == "knn":
            X = b["X"]
            mu, sd = X.mean(0), X.std(0) + 1e-12
            np.savez_compressed(MODEL_DIR / "knn.npz", X=X, y=y, mu=mu, sd=sd)
            spec["model"] = {"kind": "knn", "k": mspec["k"], "name": f["model"]}
        else:
            import lightgbm as lgb
            p = {k: v for k, v in mspec.items() if k != "kind"}
            for d, name in ((0, "up"), (1, "down")):
                mdl = lgb.LGBMRegressor(**p, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                                        random_state=7, n_jobs=4, verbose=-1, deterministic=True)
                mdl.fit(b["X"], y[:, d])
                mdl.booster_.save_model(str(MODEL_DIR / f"lgbm_{name}.txt"))
            spec["model"] = {"kind": "lgbm", "name": f["model"], **p}
    else:
        rule = f["rule"]
        if f["source"] == "r1":
            raise SystemExit("R1 winner: not supported by PerfectFit (add if it ever wins)")
        thr = [[float(np.quantile(b["X"][b["sym"] == s, fi], q)) for s in range(3)]
               for fi, q in zip(rule["f"], rule["q"])]
        spec["model"] = {"kind": "rule"}
        spec["rule"] = {"f": rule["f"], "thr": thr, "above": [q > 0.5 for q in rule["q"]],
                        "sign": rule["sign"], "cells": rule.get("cells"), "desc": f.get("desc")}
        spec["threshold"] = 0.0
    (MODEL_DIR / "spec.json").write_text(json.dumps(spec, indent=1, default=str))
    print("saved", spec["model"], spec["exit"], "threshold", spec["threshold"])
    return spec


def run() -> int:
    t0 = time.time()
    states = {}
    for label, stress in (("measured", 1.0), ("stress", 1.5)):
        eng = Engine(PerfectFit(), list(SYMBOLS), DATA_START, DATA_END, stress=stress,
                     data=market_data("1h", DATA_START, DATA_END), kill_switch="enforce")
        eng.run()
        states[label] = eng.state
        print(label, L.engine_score(eng.state), f"({time.time() - t0:.0f}s)", flush=True)
    s = PerfectFit()
    info = {"strategy": "fxbot.strategies.perfect_fit:PerfectFit", "timeframe": "1h", "label": s.label,
            "params": s.params, "symbols": list(SYMBOLS), "start": str(DATA_START), "end": str(DATA_END),
            "include_holdout": False, "starting_balance": 100.0, "kill_switch_mode": "enforce"}
    out = write_run(RUN_NAME, info, states["measured"], states["stress"])
    L.save_json(L.RES / "final_preholdout.json", {"measured": L.engine_score(states["measured"]),
                                                  "stress_1_5x": L.engine_score(states["stress"])})
    print("report:", out)
    return 0


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("save", "all"):
        save()
    if what in ("run", "all"):
        sys.exit(run())
