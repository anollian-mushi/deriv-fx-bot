"""Round 4, track A: a machine-learning day strategy (approved by the owner, 30 Oct 2026).

One decision per pair per day at 08:00 UTC (the close of the 07:00-08:00
candle, so the first London hour is known), exit at 20:00 UTC. The model
gives the probability that the pair is higher at 20:00 than at 08:00; the
strategy trades Up when it is at least 0.5 + margin, Down when at most
0.5 - margin, otherwise nothing. No stop or target: the time exit and
Deriv's stop out are the only exits, as in family 5.

Fixed before testing (plan approved 30 Oct 2026):
- Horizon 08:00 -> 20:00 UTC. Features use only candles closed by 08:00.
- Every price move is divided by the pair's average daily range over the
  last 20 completed days, so features mean the same in calm and wild months.
- Features: own moves since midnight, last hour, 1/3/5/20 trading days;
  yesterday's range vs normal; 5-day vs 20-day ranges; position in the last
  20 days' range; where yesterday closed in its range; day of the week.
  "peers" adds the three pairs' moves (since midnight, 1 day, 5 days) in the
  dollar's direction. "all" (pooled) adds which pair the row is.
- Models: logistic regression (L2, C=1) or gradient boosting (150 shallow
  trees, depth 3, learning rate 0.05, at least 40 rows per leaf), each behind
  a StandardScaler. The scaler and the model are fitted inside one sklearn
  Pipeline, so both see the training rows only (owner safeguard 1).
- Every model gets SEED (owner safeguard 2).
- A fitted model is saved as a FrozenModel: it can predict but any attempt to
  fit it raises (owner safeguard 3: the holdout test uses the pre-holdout
  model exactly as it is).

The strategy sees closed candles only and keeps no state, so the live bot
runs the same code with the same model file.
"""

from __future__ import annotations

import datetime as dt
import pickle
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np

from fxbot.backtest.candles import Bars
from .families import DAY, HOUR, FamilyStrategy, PositionView, hour_of

SYMBOLS = ("frxEURUSD", "frxGBPUSD", "frxUSDJPY")
USD_SIGN = {"frxEURUSD": -1.0, "frxGBPUSD": -1.0, "frxUSDJPY": 1.0}   # pair up = dollar down / up
DECISION_HOUR = 8
EXIT_HOUR = 20
LOOKBACK_DAYS = 20
SEED = 20261030
OWN = ["r_on", "r_l1", "r_1d", "r_3d", "r_5d", "r_20d", "range_y", "vol_ratio", "pos_20d", "loc_y",
       "dow_tue", "dow_wed", "dow_thu", "dow_fri"]
PEER = [f"usd_{s[3:]}_{h}" for s in SYMBOLS for h in ("on", "1d", "5d")]
PAIR = [f"pair_{s[3:]}" for s in SYMBOLS]
FEATURE_SETS = {"own": OWN, "peers": OWN + PEER}
ALL_COLUMNS = OWN + PEER + PAIR
MODEL_KINDS = ("lr", "gb")
POOLS = ("all", "pair")

PLAIN = {
    "r_on": "move since midnight (Asian session + first London hour)",
    "r_l1": "move in the last hour (07:00-08:00 UTC)",
    "r_1d": "move over the last trading day", "r_3d": "move over the last 3 trading days",
    "r_5d": "move over the last week", "r_20d": "move over the last month",
    "range_y": "yesterday's range vs the monthly normal",
    "vol_ratio": "this week's ranges vs this month's",
    "pos_20d": "where price sits in the last month's high-low range (0 = at the low, 1 = at the high)",
    "loc_y": "where yesterday closed within its own range",
    "dow_tue": "it is Tuesday", "dow_wed": "it is Wednesday", "dow_thu": "it is Thursday",
    "dow_fri": "it is Friday",
    **{f"usd_{s[3:]}_{h}": f"dollar move on {s[3:6]}/{s[6:]} {lab}" for s in SYMBOLS
       for h, lab in (("on", "since midnight"), ("1d", "over 1 day"), ("5d", "over 5 days"))},
    **{f"pair_{s[3:]}": f"the row is {s[3:6]}/{s[6:]}" for s in SYMBOLS},
}


# ----------------------------------------------------------------------------- features
def _completed_days(c: Bars, n: int):
    """(high, low, close) of the last n completed UTC days, from intraday candles."""
    m = min(len(c), (n + 2) * 24)
    end, hi, lo, cl = c.end[-m:], c.high[-m:], c.low[-m:], c.close[-m:]
    day = (end - 1) // DAY
    starts = np.r_[0, np.flatnonzero(day[1:] != day[:-1]) + 1]
    h = np.maximum.reduceat(hi, starts)
    low = np.minimum.reduceat(lo, starts)
    cc = cl[np.r_[starts[1:] - 1, len(cl) - 1]]
    if int(c.end[-1]) % DAY != 0:               # today is not finished
        h, low, cc = h[:-1], low[:-1], cc[:-1]
    return h[-n:], low[-n:], cc[-n:]


def own_features(c: Bars) -> dict | None:
    """The pair's own features at a 08:00 UTC candle close, or None if the history is short."""
    t = int(c.end[-1])
    if t % DAY != DECISION_HOUR * HOUR or len(c) < 2 or int(c.end[-2]) != t - HOUR:
        return None
    h, low, cc = _completed_days(c, LOOKBACK_DAYS)
    if len(h) < LOOKBACK_DAYS:
        return None
    rngs = h - low
    r20, r5 = float(rngs.mean()), float(rngs[-5:].mean())
    if r20 <= 0:
        return None
    m = min(len(c), (LOOKBACK_DAYS + 3) * 24)    # only the tail is needed (speed; same values)
    tail_end, tail_close, tail_epoch, tail_open = c.end[-m:], c.close[-m:], c.epoch[-m:], c.open[-m:]
    c8 = tail_close[tail_end % DAY == DECISION_HOUR * HOUR]      # closes at 08:00, today last
    if len(c8) < LOOKBACK_DAYS + 1:
        return None
    d0 = t - DECISION_HOUR * HOUR
    today = tail_epoch >= d0
    if today.sum() < 6:                          # most of the overnight candles must exist
        return None
    close = float(c.close[-1])
    open_today = float(tail_open[today][0])
    ry = float(rngs[-1])
    wd = ((t // DAY) + 3) % 7                    # 0 = Monday
    span = float(h.max() - low.min())
    return {
        "r_on": (close - open_today) / r20,
        "r_l1": (close - float(c.close[-2])) / r20,
        "r_1d": (close - float(c8[-2])) / r20,
        "r_3d": (close - float(c8[-4])) / r20,
        "r_5d": (close - float(c8[-6])) / r20,
        "r_20d": (close - float(c8[-21])) / r20,
        "range_y": ry / r20,
        "vol_ratio": r5 / r20,
        "pos_20d": (close - float(low.min())) / span if span > 0 else 0.5,
        "loc_y": (float(cc[-1]) - float(low[-1])) / ry if ry > 0 else 0.5,
        "dow_tue": float(wd == 1), "dow_wed": float(wd == 2), "dow_thu": float(wd == 3),
        "dow_fri": float(wd == 4),
    }


def features_at(symbol: str, c: Bars, peers: dict) -> dict | None:
    """All feature columns for `symbol` at the 08:00 close of c (peers: other pairs' closed candles).

    Peer columns are NaN when a peer's 08:00 candle or history is missing; models
    that use them then make no prediction for the day.
    """
    own = own_features(c)
    if own is None:
        return None
    out = dict(own)
    for s in SYMBOLS:
        out[f"pair_{s[3:]}"] = float(s == symbol)
        if s == symbol:
            f = own
        else:
            p = peers.get(s)
            f = own_features(p) if p is not None and len(p) and int(p.end[-1]) == int(c.end[-1]) else None
        for h in ("on", "1d", "5d"):
            out[f"usd_{s[3:]}_{h}"] = USD_SIGN[s] * f[f"r_{h}"] if f is not None else float("nan")
    return out


def label_at(c: Bars, i: int) -> tuple[float, float] | None:
    """(y, move) for the 08:00 candle at index i: y = 1 if the close of the candle ending 20:00
    the same day is above this close. None when that candle is missing (early close)."""
    t = int(c.end[i])
    j = np.searchsorted(c.end, t + (EXIT_HOUR - DECISION_HOUR) * HOUR)
    if j >= len(c) or int(c.end[j]) != t + (EXIT_HOUR - DECISION_HOUR) * HOUR:
        return None
    move = float(c.close[j] - c.close[i])
    return float(move > 0), move


@dataclass
class Table:
    """Feature rows at every 08:00 close of the pre-holdout history (research only)."""
    symbol: np.ndarray
    epoch: np.ndarray                   # the 08:00 candle's end (= decision time)
    y: np.ndarray                       # 1 / 0, NaN when the 20:00 candle is missing
    move: np.ndarray                    # price move 08:00 -> 20:00 (NaN as above)
    X: np.ndarray                       # rows x ALL_COLUMNS
    columns: list = field(default_factory=lambda: list(ALL_COLUMNS))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(path, symbol=self.symbol, epoch=self.epoch, y=self.y, move=self.move, X=self.X,
                            columns=np.array(self.columns))

    @classmethod
    def load(cls, path: Path) -> "Table":
        z = np.load(path, allow_pickle=False)
        return cls(z["symbol"], z["epoch"], z["y"], z["move"], z["X"], [str(x) for x in z["columns"]])


def build_table(bars: dict[str, Bars]) -> Table:
    """bars: {symbol: 1h candles}. Features at each 08:00 close through the same code the
    strategy uses live (features_at on a closed-candle slice), labels from the same day's 20:00."""
    sym, ep, ys, mv, rows = [], [], [], [], []
    for s in SYMBOLS:
        c = bars[s]
        for i in np.flatnonzero(c.end % DAY == DECISION_HOUR * HOUR):
            t = int(c.end[i])
            peers = {o: bars[o].slice(int(np.searchsorted(bars[o].end, t, "right")))
                     for o in SYMBOLS if o != s}
            f = features_at(s, c.slice(i + 1), peers)
            if f is None:
                continue
            lab = label_at(c, i)
            sym.append(s)
            ep.append(t)
            ys.append(lab[0] if lab else np.nan)
            mv.append(lab[1] if lab else np.nan)
            rows.append([f[k] for k in ALL_COLUMNS])
    return Table(np.array(sym), np.array(ep, dtype=np.int64), np.array(ys), np.array(mv),
                 np.array(rows, dtype=float).reshape(-1, len(ALL_COLUMNS)))


# ----------------------------------------------------------------------------- models
def make_model(kind: str, seed: int = SEED):
    """An unfitted sklearn pipeline: scaler + classifier, settings fixed before testing."""
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import StandardScaler
    if kind == "lr":
        clf = LogisticRegression(C=1.0, max_iter=2000, random_state=seed)
    elif kind == "gb":
        clf = HistGradientBoostingClassifier(max_iter=150, learning_rate=0.05, max_depth=3,
                                             min_samples_leaf=40, l2_regularization=1.0,
                                             early_stopping=False, random_state=seed)
    else:
        raise ValueError(kind)
    return Pipeline([("scale", StandardScaler()), ("clf", clf)])


def training_rows(table: Table, train_start: dt.date, train_end: dt.date, feats: str) -> np.ndarray:
    """Row mask: decision inside [train_start, train_end], label day inside it too (the 20:00
    close is the same day, so no label reaches past the window), label present, and every
    feature column of this set present."""
    t0 = int(dt.datetime(train_start.year, train_start.month, train_start.day, tzinfo=dt.timezone.utc).timestamp())
    t1 = int(dt.datetime(train_end.year, train_end.month, train_end.day, tzinfo=dt.timezone.utc).timestamp()) + DAY
    cols = [table.columns.index(k) for k in FEATURE_SETS[feats]]
    label_time = table.epoch + (EXIT_HOUR - DECISION_HOUR) * HOUR
    return ((table.epoch >= t0) & (label_time < t1) & ~np.isnan(table.y)
            & ~np.isnan(table.X[:, cols]).any(axis=1))


class Frozen(RuntimeError):
    """Raised when something tries to refit a saved model."""


@dataclass
class FrozenModel:
    """A fitted model that can only predict. fit() raises (owner safeguard 3)."""
    kind: str
    feats: str
    pool: str
    models: dict                        # {"all": pipeline} or {symbol: pipeline}
    columns: list                       # feature columns each pipeline was fitted on, in order
    train_start: str
    train_end: str
    rows: int
    seed: int = SEED

    def fit(self, *a, **k):
        raise Frozen(f"model trained on {self.train_start}..{self.train_end} (pre-holdout) is frozen; "
                     "it is never retrained, not on the holdout either")

    def _pipe(self, symbol: str):
        return self.models["all"] if self.pool == "all" else self.models.get(symbol)

    def p_up(self, symbol: str, f: dict) -> float | None:
        pipe = self._pipe(symbol)
        if pipe is None:
            return None
        x = np.array([[f[k] for k in self.columns]], dtype=float)
        if np.isnan(x).any():
            return None
        return float(pipe.predict_proba(x)[0, 1])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(pickle.dumps(self))
        tmp.replace(path)


def fit_frozen(table: Table, train_start: dt.date, train_end: dt.date, kind: str, feats: str,
               pool: str, seed: int = SEED) -> FrozenModel:
    """Fit on the rows of [train_start, train_end] only (scaler included), then freeze."""
    mask = training_rows(table, train_start, train_end, feats)
    cols = list(FEATURE_SETS[feats]) + (list(PAIR) if pool == "all" else [])
    idx = [table.columns.index(k) for k in cols]
    models = {}
    if pool == "all":
        m = make_model(kind, seed)
        m.fit(table.X[mask][:, idx], table.y[mask])
        models["all"] = m
    else:
        for s in SYMBOLS:
            sel = mask & (table.symbol == s)
            if sel.sum() < 100 or len(set(table.y[sel])) < 2:
                continue
            m = make_model(kind, seed)
            m.fit(table.X[sel][:, idx], table.y[sel])
            models[s] = m
    return FrozenModel(kind, feats, pool, models, cols, train_start.isoformat(), train_end.isoformat(),
                       int(mask.sum()), seed)


@lru_cache(maxsize=64)
def load_frozen(path: str) -> FrozenModel:
    m = pickle.loads(Path(path).read_bytes())
    if not isinstance(m, FrozenModel):
        raise TypeError(f"{path} is not a FrozenModel")
    return m


# ----------------------------------------------------------------------------- the strategy
class MLDay(FamilyStrategy):
    """Track A strategy. Params: model (lr/gb), feats (own/peers), pool (all/pair), margin,
    model_file (a saved FrozenModel; the research script sets one per walk-forward window)."""
    name = "a1_ml_day"
    family = "a1"
    timeframe = "1h"
    needs_peers = True
    warmup_days = 60
    defaults = {"model": "lr", "feats": "own", "pool": "all", "margin": 0.05, "model_file": ""}

    def __init__(self, **params):
        super().__init__(**params)
        self._frozen = load_frozen(self.params["model_file"]) if self.params["model_file"] else None

    @property
    def frozen(self) -> FrozenModel | None:
        return self._frozen

    def _features(self, symbol: str, c: Bars) -> dict | None:
        if int(c.end[-1]) % DAY != DECISION_HOUR * HOUR:
            return None
        return features_at(symbol, c, self.peers)

    def probability_up(self, symbol: str, c: Bars) -> float | None:
        f = self._features(symbol, c)
        if f is None or self._frozen is None:
            return None
        return self._frozen.p_up(symbol, f)

    def direction(self, symbol, c):
        p = self.probability_up(symbol, c)
        if p is None:
            return None
        m = self.params["margin"]
        if p >= 0.5 + m:
            return "MULTUP"
        if p <= 0.5 - m:
            return "MULTDOWN"
        return None

    def stops(self, symbol, c, direction):
        return None if self._features(symbol, c) is None else (None, None)

    def exit_now(self, symbol, c, position: PositionView):
        e = position.entry_epoch
        return int(c.end[-1]) >= e - e % DAY + EXIT_HOUR * HOUR
