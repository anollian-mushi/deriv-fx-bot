"""EXPERIMENT ONLY (branch experiment/perfect-fit): the "perfect fit" strategy.

Built by the owner-approved perfect-fit experiment: the single variant with the
highest net profit / max drawdown on the whole pre-holdout period (2021-10-27 to
2026-04-27), with no walk-forward, luck check or parameter limit. It is fitted to
that period on purpose. Its first unseen-data result is in
reports/experiment_perfect_fit.md; read it before thinking about using this.

How it works (the plain-language rules are in the report):
- Called on every closed 1h candle; uses only closed candles (fxbot.strategies.pf_features).
- At the allowed signal hours, the saved model (models/perfect_fit/) scores an Up
  trade and a Down trade; the better one is taken if its score passes the
  saved threshold.
- Every trade uses the saved exit setup: multiplier, stop loss / take profit in
  pips, and a time exit after `hold` hours (0 = no time exit).
- Orders still go through the risk module (3% stake, daily limit, kill switch,
  max 2 positions / 1 per pair, cost gate, entry window, daily pause, Friday close).
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from fxbot.strategies.base import Enter, ExitPosition, Strategy
from fxbot.strategies.pf_features import SYMBOLS, features

ROOT = Path(__file__).resolve().parents[3]
MODEL_DIR = ROOT / "models" / "perfect_fit"


def allowed_hour(symbol: str, hour: int) -> bool:
    """Hours whose next minute can open at once (entry window, cost gate at 12:00 / 13:00 EUR)."""
    return 6 <= hour <= 17 and hour != 12 and not (symbol == "frxEURUSD" and hour == 13)


class PerfectFit(Strategy):
    name = "perfect_fit"
    label = "EXPERIMENT ONLY: fitted to the pre-holdout period on purpose"
    timeframe = "1h"
    needs_peers = True

    def __init__(self, model_dir: Path = MODEL_DIR, trade_from: int = 0):
        spec = json.loads((model_dir / "spec.json").read_text())
        self.spec = spec
        self.trade_from = trade_from
        self.mult, self.sl, self.tp, self.hold = (spec["exit"][k] for k in ("mult", "sl", "tp", "hold"))
        self.threshold = spec["threshold"]
        self.params = {"model": spec["model"], "exit": spec["exit"], "threshold": self.threshold}
        self._model = self._load(model_dir, spec)

    # ------------------------------------------------------------------ model
    @staticmethod
    def _load(model_dir: Path, spec: dict):
        kind = spec["model"]["kind"]
        if kind == "knn":
            from sklearn.neighbors import KNeighborsRegressor
            z = np.load(model_dir / "knn.npz")
            mu, sd = z["mu"], z["sd"]
            m = KNeighborsRegressor(n_neighbors=int(spec["model"]["k"])).fit((z["X"] - mu) / sd, z["y"])
            return lambda x: m.predict(((x - mu) / sd)[None, :])[0]
        if kind == "lgbm":
            import lightgbm as lgb
            boosters = [lgb.Booster(model_file=str(model_dir / f"lgbm_{d}.txt")) for d in ("up", "down")]
            return lambda x: np.array([b.predict(x[None, :])[0] for b in boosters])
        if kind == "rule":
            r = spec["rule"]

            def rule(x):
                s = int(x[0])
                ok = all((x[f] > thr[s]) if above else (x[f] < thr[s])
                         for f, thr, above in zip(r["f"], r["thr"], r["above"]))
                if ok and r.get("cells") is not None:
                    ok = [s, int(x[1])] in r["cells"]
                v = 1.0 if ok else -1.0
                return np.array([v, -1.0]) if r["sign"] > 0 else np.array([-1.0, v])
            return rule
        raise ValueError(f"unknown model kind {kind!r}")

    def score(self, symbol, candles) -> np.ndarray | None:
        """Predicted profit / stake for (Up, Down), or None if not enough history."""
        x = features(symbol, candles, self.peers)
        return None if x is None else np.asarray(self._model(x), dtype=float)

    # ------------------------------------------------------------------ signals
    def on_candle(self, symbol, candles, position, pending):
        t = int(candles.end[-1])
        if position is not None:
            if self.hold and t - position.entry_epoch >= self.hold * 3600:
                return [ExitPosition()]
            return []
        if pending or t < self.trade_from or not allowed_hour(symbol, (t % 86400) // 3600):
            return []
        p = self.score(symbol, candles)
        if p is None or max(p) <= self.threshold:
            return []
        d = "MULTUP" if p[0] >= p[1] else "MULTDOWN"
        return [Enter(d, multiplier=self.mult, stop_loss_pips=self.sl or None,
                      take_profit_pips=self.tp or None)]


assert set(SYMBOLS) == {"frxEURUSD", "frxGBPUSD", "frxUSDJPY"}
