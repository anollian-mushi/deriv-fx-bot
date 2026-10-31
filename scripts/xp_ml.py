"""Perfect-fit experiment, stage 3: machine learning, fitted on the whole pre-holdout period.

For an exit setup k, two models predict the trade result (profit / stake) of an Up
trade and of a Down trade from the features (fxbot.strategies.pf_features). The
strategy takes the better direction when its prediction is above a threshold.
Models are trained and scored on the same data (the owner's perfect-fit rules),
so more capacity always looks better in-sample.

Models: LightGBM at three sizes; k-nearest-neighbours (k = 1, 5, 25) on z-scored
features. Each (model, exit setup, threshold) is one logged variant. Predictions are
cached per (model, setup), so the script resumes where it stopped.

Run: python scripts/xp_ml.py [--max-minutes 9]
"""

from __future__ import annotations

import argparse
import json
import sys
import time

import numpy as np

import xp_lib as L

MODELS = {
    "lgbm_s": {"kind": "lgbm", "num_leaves": 15, "n_estimators": 200, "learning_rate": 0.05, "min_child_samples": 100},
    "lgbm_m": {"kind": "lgbm", "num_leaves": 63, "n_estimators": 600, "learning_rate": 0.05, "min_child_samples": 20},
    "lgbm_l": {"kind": "lgbm", "num_leaves": 255, "n_estimators": 1500, "learning_rate": 0.05, "min_child_samples": 3},
    "knn_25": {"kind": "knn", "k": 25},
    "knn_5": {"kind": "knn", "k": 5},
    "knn_1": {"kind": "knn", "k": 1},
}
THRESHOLDS = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5)


def setups(b) -> list[int]:
    """Exit setups for ML: the oracle's best 8 plus a fixed spread of 8 common ones."""
    cfg = b["cfg"]
    oracle = []
    for k in range(len(cfg)):
        p = b["pnl"][k]
        best = p.max(1)
        d = np.where(best > 0, np.where(p[:, 0] >= p[:, 1], 1, -1), 0)
        oracle.append((L.screen(k, d)["score"], k))
    oracle.sort(reverse=True)
    fixed = [(100, 20, 30, 4), (100, 30, 50, 8), (100, 0, 0, 24), (100, 0, 0, 4), (100, 15, 30, 0),
             (200, 15, 30, 0), (200, 0, 0, 4), (100, 50, 80, 0)]
    ks = [k for _, k in oracle[:8]]
    for f in fixed:
        k = int(np.where((cfg == f).all(1))[0][0])
        if k not in ks:
            ks.append(k)
    return ks, oracle


def fit_predict(spec: dict, X: np.ndarray, y: np.ndarray, seed: int = 7) -> np.ndarray:
    if spec["kind"] == "lgbm":
        import lightgbm as lgb
        p = {k: v for k, v in spec.items() if k != "kind"}
        m = lgb.LGBMRegressor(**p, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                              random_state=seed, n_jobs=4, verbose=-1, deterministic=True)
        m.fit(X, y)
        return m.predict(X)
    from sklearn.neighbors import KNeighborsRegressor
    mu, sd = X.mean(0), X.std(0) + 1e-12
    m = KNeighborsRegressor(n_neighbors=spec["k"], n_jobs=4).fit((X - mu) / sd, y)
    return m.predict((X - mu) / sd)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=9.0)
    a = ap.parse_args()
    t0 = time.time()
    b = L.build()
    pred_dir = L.CACHE / "ml_pred"
    pred_dir.mkdir(parents=True, exist_ok=True)
    ks_path = L.RES / "ml_setups.json"
    if ks_path.exists():
        ks = json.loads(ks_path.read_text())["setups"]
    else:
        ks, oracle = setups(b)
        L.save_json(ks_path, {"setups": ks, "oracle_top": [{"k": k, "cfg": L.cfg_str(b["cfg"][k]), "score": s}
                                                          for s, k in oracle[:20]]})
    res_path = L.RES / "ml_results.json"
    results = json.loads(res_path.read_text()) if res_path.exists() else []
    done = {(r["model"], r["k"]) for r in results}
    log = L.VariantLog("ml")
    X = b["X"]
    for name, spec in MODELS.items():
        for k in ks:
            if (name, k) in done:
                continue
            if time.time() - t0 > a.max_minutes * 60:
                print("time budget used; run again to continue")
                return 2
            f = pred_dir / f"{name}_{k}.npy"
            if f.exists():
                pr = np.load(f)
            else:
                pr = np.stack([fit_predict(spec, X, b["pnl"][k, :, d].astype(np.float64)) for d in (0, 1)], 1)
                np.save(f, pr)
            best = pr.max(1)
            up = pr[:, 0] >= pr[:, 1]
            for thr in THRESHOLDS:
                d = np.where(best > thr, np.where(up, 1, -1), 0)
                res = L.screen(k, d)
                vid = log.add("ml", f"ML {name}", f"{name}, predicted profit/stake > {thr}", k, res)
                results.append({"id": vid, "model": name, "k": k, "thr": thr, **res})
            log.flush()
            L.save_json(res_path, results)
            bestr = max((r for r in results if r["model"] == name and r["k"] == k), key=lambda r: r["score"])
            print(f"{name} {L.cfg_str(b['cfg'][k])}: best thr {bestr['thr']} trades {bestr['trades']} "
                  f"net {bestr['net_pct']:.0f}% dd {bestr['dd_pct']:.1f}% score {bestr['score']:.1f} "
                  f"({time.time() - t0:.0f}s)", flush=True)
    print("ml stage complete")
    return 0


if __name__ == "__main__":
    sys.exit(main())
