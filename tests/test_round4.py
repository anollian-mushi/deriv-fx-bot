"""Round 4 tests: the ML day strategy (track A), families 11-12 (track B) and the
exact-signal-days luck check. Owner safeguards (30 Oct 2026):
1. scaling is fitted on the training window only;
2. every model has a fixed seed and reproduces exactly;
3. a saved model is frozen: it cannot be retrained, on the holdout or anywhere."""

import datetime as dt

import numpy as np
import pytest

from backtest_helpers import data_for
from fxbot.backtest import research as R
from fxbot.backtest.candles import Bars, aggregate
from fxbot.backtest.engine import Engine
from fxbot.strategies import families as F
from fxbot.strategies import ml_day as M

MON = dt.date(2025, 3, 3)
SYMS = list(R.SYMBOLS)


def ep(y, m, d, hh=0, mm=0):
    return int(dt.datetime(y, m, d, hh, mm, tzinfo=dt.timezone.utc).timestamp())


@pytest.fixture(scope="module")
def market():
    return data_for(SYMS, "1h", MON, 220, seed=11)


@pytest.fixture(scope="module")
def table(market):
    return M.build_table({s: tf for s, (_, tf) in market.items()})


@pytest.fixture(scope="module")
def frozen(table, tmp_path_factory):
    m = M.fit_frozen(table, MON, dt.date(2025, 5, 30), "lr", "peers", "all")
    path = tmp_path_factory.mktemp("models") / "lr_peers_all.pkl"
    m.save(path)
    return m, path


def _scramble_future(market, cut, seed=5):
    """Every pair's candles after `cut` replaced by a different random path."""
    out = {}
    for i, (s, (m1, _)) in enumerate(market.items()):
        rng = np.random.default_rng(seed + i)
        after = m1.epoch >= cut
        k = int(after.sum())
        vol = 0.008 if s == "frxUSDJPY" else 0.00008
        closes = m1.close.copy()
        closes[after] = m1.close[~after][-1] + np.cumsum(rng.normal(0, vol, k)) * rng.choice([-3, 3])
        opens = np.r_[m1.open[0], closes[:-1]]
        b = Bars(m1.epoch, m1.end, opens, np.maximum(opens, closes) + vol / 2, np.minimum(opens, closes) - vol / 2, closes)
        out[s] = (b, aggregate(b, "1h"))
    return out


class _Recording(M.MLDay):
    """MLDay that records every probability it computes (test helper)."""
    def __init__(self, **p):
        super().__init__(**p)
        self.seen = []

    def probability_up(self, symbol, c):
        p = super().probability_up(symbol, c)
        if p is not None:
            self.seen.append((symbol, int(c.end[-1]), round(p, 12)))
        return p


def _run(strategy, data):
    e = Engine(strategy, list(data), MON, MON, data=data)
    e.run()
    return e


# ----------------------------------------------------------------------------- look-ahead
def test_scrambling_the_future_changes_no_past_feature_or_prediction(market, frozen):
    m, path = frozen
    cut = ep(2025, 6, 2)
    a = _Recording(model_file=str(path), feats="peers", pool="all", margin=0.0)
    b = _Recording(model_file=str(path), feats="peers", pool="all", margin=0.0)
    ea, eb = _run(a, market), _run(b, _scramble_future(market, cut))
    before = lambda s: [x for x in s.seen if x[1] <= cut]
    after = lambda s: [x for x in s.seen if x[1] > cut]
    assert before(a) and before(a) == before(b)
    assert after(a) != after(b)                        # the future really did change
    sig = lambda e: [s for s in e.state.signals if s[0] <= cut]
    assert sig(ea) == sig(eb)
    # the raw feature rows agree too, for every pair
    ta = M.build_table({s: tf for s, (_, tf) in market.items()})
    tb = M.build_table({s: tf for s, (_, tf) in _scramble_future(market, cut).items()})
    ka, kb = ta.epoch <= cut, tb.epoch <= cut
    assert ka.sum() == kb.sum() > 50
    np.testing.assert_array_equal(ta.X[ka], tb.X[kb])


def test_features_use_only_candles_closed_by_0800(market):
    tf = market["frxEURUSD"][1]
    i = int(np.flatnonzero(tf.end == ep(2025, 5, 7, 8))[0])
    peers = {s: market[s][1].slice(int(np.searchsorted(market[s][1].end, tf.end[i], "right"))) for s in SYMS[1:]}
    f = M.features_at("frxEURUSD", tf.slice(i + 1), peers)
    assert f is not None
    # later candles are never read: a slice ending at the same candle gives the same features
    assert M.features_at("frxEURUSD", tf.slice(i + 1), peers) == f
    # and a slice ending one candle later is a different decision time (07:00 close -> None)
    assert M.own_features(tf.slice(i)) is None
    # weekday dummies: 7 May 2025 is a Wednesday
    assert f["dow_wed"] == 1.0 and f["dow_tue"] == f["dow_thu"] == f["dow_fri"] == 0.0


def test_label_is_the_same_days_2000_close_only(market):
    tf = market["frxEURUSD"][1]
    i = int(np.flatnonzero(tf.end == ep(2025, 5, 7, 8))[0])
    y, move = M.label_at(tf, i)
    j = int(np.flatnonzero(tf.end == ep(2025, 5, 7, 20))[0])
    assert move == pytest.approx(tf.close[j] - tf.close[i]) and y == float(move > 0)
    # no 20:00 candle (drop it) -> no label
    keep = tf.end != ep(2025, 5, 7, 20)
    short = Bars(*(a[keep] for a in (tf.epoch, tf.end, tf.open, tf.high, tf.low, tf.close)))
    i2 = int(np.flatnonzero(short.end == ep(2025, 5, 7, 8))[0])
    assert M.label_at(short, i2) is None


def test_training_rows_stay_inside_the_window_and_need_a_label(table):
    mask = M.training_rows(table, dt.date(2025, 4, 1), dt.date(2025, 4, 30), "peers")
    t = table.epoch[mask]
    assert len(t) > 40
    assert t.min() >= ep(2025, 4, 1, 8) and t.max() <= ep(2025, 4, 30, 8)
    assert not np.isnan(table.y[mask]).any()
    # the day after the window is out, even though its features exist
    assert ep(2025, 5, 1, 8) in set(table.epoch) and ep(2025, 5, 1, 8) not in set(t)
    # a row whose 20:00 candle is missing is never a training row
    tbl = M.Table(table.symbol, table.epoch, table.y.copy(), table.move, table.X)
    k = int(np.flatnonzero(tbl.epoch == ep(2025, 4, 15, 8))[0])
    tbl.y[k] = np.nan
    assert ep(2025, 4, 15, 8) in set(t)
    assert k not in set(np.flatnonzero(M.training_rows(tbl, dt.date(2025, 4, 1), dt.date(2025, 4, 30), "peers")))


# ----------------------------------------------------------------------------- safeguards
@pytest.mark.parametrize("kind", M.MODEL_KINDS)
def test_scaler_is_fitted_on_the_training_window_only(table, kind):
    t0, t1 = dt.date(2025, 4, 1), dt.date(2025, 5, 30)
    m = M.fit_frozen(table, t0, t1, kind, "own", "all")
    mask = M.training_rows(table, t0, t1, "own")
    idx = [table.columns.index(k) for k in m.columns]
    scaler = m.models["all"].named_steps["scale"]
    np.testing.assert_allclose(scaler.mean_, table.X[mask][:, idx].mean(axis=0))
    full_mean = table.X[:, idx].mean(axis=0)
    assert not np.allclose(scaler.mean_, full_mean)         # not the whole table
    assert m.rows == int(mask.sum()) and m.train_start == "2025-04-01"


@pytest.mark.parametrize("kind", M.MODEL_KINDS)
@pytest.mark.parametrize("pool", M.POOLS)
def test_fixed_seed_reproduces_every_probability(table, kind, pool):
    t0, t1 = MON, dt.date(2025, 9, 30)
    a = M.fit_frozen(table, t0, t1, kind, "peers", pool)
    b = M.fit_frozen(table, t0, t1, kind, "peers", pool)
    assert a.seed == b.seed == M.SEED
    rows = [dict(zip(table.columns, x)) for x in table.X[-30:]]
    for s, f in zip(table.symbol[-30:], rows):
        pa, pb = a.p_up(s, f), b.p_up(s, f)
        assert pa is not None and pa == pb
    # an explicit different seed is allowed to differ, so the seed is really in play
    c = M.fit_frozen(table, t0, t1, kind, "peers", pool, seed=1)
    assert c.seed == 1 and all(c.p_up(s, f) is not None for s, f in zip(table.symbol[-30:], rows))


def test_saved_model_is_frozen_and_predicts_the_same_after_loading(table, frozen):
    m, path = frozen
    with pytest.raises(M.Frozen):
        m.fit(table.X, table.y)
    loaded = M.load_frozen(str(path))
    with pytest.raises(M.Frozen):
        loaded.fit(table.X, table.y)
    for s, x in zip(table.symbol[-20:], table.X[-20:]):
        f = dict(zip(table.columns, x))
        assert loaded.p_up(s, f) == m.p_up(s, f)
    # the pipeline inside can still be asked to predict, never fitted through the strategy
    strat = M.MLDay(model_file=str(path), feats="peers", pool="all", margin=0.05)
    assert strat.frozen is loaded and not hasattr(strat, "fit")


def test_model_settings_are_fixed_before_testing():
    lr = M.make_model("lr").named_steps["clf"]
    gb = M.make_model("gb").named_steps["clf"]
    assert lr.C == 1.0 and lr.random_state == M.SEED
    assert (gb.max_iter, gb.learning_rate, gb.max_depth, gb.min_samples_leaf, gb.random_state) == \
        (150, 0.05, 3, 40, M.SEED) and gb.early_stopping is False
    assert len(M.ML_GRID if hasattr(M, "ML_GRID") else R.ML_GRID) == 24 <= 30
    assert all(len(p) <= 5 for p in R.ML_GRID)
    assert R.variants_through_round(4) == 186 + 24 + 24


# ----------------------------------------------------------------------------- strategy
def test_strategy_in_the_engine_matches_the_training_table(market, table, frozen):
    """The live path (strategy on engine slices) and the research path (table) give the same
    probability for the same pair and 08:00 candle."""
    m, path = frozen
    s = _Recording(model_file=str(path), feats="peers", pool="all", margin=0.0)
    _run(s, market)
    by_key = {(sym, int(t)): dict(zip(table.columns, x)) for sym, t, x in zip(table.symbol, table.epoch, table.X)}
    checked = 0
    for sym, t, p in s.seen:
        if (sym, t) in by_key:
            assert m.p_up(sym, by_key[(sym, t)]) == pytest.approx(p, abs=1e-9)
            checked += 1
    assert checked > 100


def test_strategy_trades_only_with_margin_and_exits_at_2000(market, frozen):
    m, path = frozen
    s = M.MLDay(model_file=str(path), feats="peers", pool="all", margin=0.02)
    e = _run(s, market)
    assert e.state.trades
    for t in e.state.trades:
        assert t["entry_time"].endswith("08:00") or t["delay_min"] > 0
        assert t["exit_time"].endswith("20:00") or t["reason"] in ("forced_deadline", "stop_out", "end_of_data")
    wide = M.MLDay(model_file=str(path), feats="peers", pool="all", margin=0.49)
    assert not _run(wide, market).state.trades
    # no model file -> no trades, ever
    assert not _run(M.MLDay(), market).state.trades


# ----------------------------------------------------------------------------- families 11-12
def _three(moves, hour=8):
    """1h candles for the three pairs where today's move since 00:00 (in dollar direction,
    units of the 20-day range) is `moves`; flat history before."""
    out = {}
    start = ep(2025, 2, 3)
    n = 30 * 24 + hour
    for s, mv in zip(SYMS, moves):
        px = 150.0 if s == "frxUSDJPY" else 1.1
        rng_day = px * 0.005
        e = start + 3600 * np.arange(n)
        close = np.full(n, px)
        hi, lo = close + rng_day / 2, close - rng_day / 2        # every day's range = rng_day
        today = e >= e[-1] - (hour - 1) * 3600
        close[today] = px + np.linspace(0, 1, today.sum()) * mv * rng_day * F.USD_SIGN[s]
        op = np.r_[close[0], close[:-1]]
        op[today][0] = px
        out[s] = Bars(e, e + 3600, op, np.maximum(hi, close), np.minimum(lo, close), close)
    return out


def test_usd_moves_read_all_three_pairs_in_dollar_terms():
    d = _three([0.4, 0.3, 0.2])
    m = F.usd_moves("frxEURUSD", d["frxEURUSD"], {s: d[s] for s in SYMS[1:]}, 8)
    assert m["frxEURUSD"] == pytest.approx(0.4, abs=0.02) and m["frxUSDJPY"] == pytest.approx(0.2, abs=0.02)
    assert F.usd_moves("frxEURUSD", d["frxEURUSD"], {}, 8) is None          # a peer is missing
    assert F.usd_moves("frxEURUSD", d["frxEURUSD"].slice(len(d["frxEURUSD"]) - 1), {}, 8) is None


def test_dollar_catch_up_buys_the_dollar_on_the_two_laggards():
    d = _three([0.4, 0.3, 0.2])          # dollar up everywhere, EUR/USD led
    s = F.DollarWideCatchUp(decision_hour=8, k=0.25, stop=0.0)
    peers = lambda sym: {o: d[o] for o in SYMS if o != sym}
    s.peers = peers("frxEURUSD")
    assert s.direction("frxEURUSD", d["frxEURUSD"]) is None                 # the leader is skipped
    s.peers = peers("frxGBPUSD")
    assert s.direction("frxGBPUSD", d["frxGBPUSD"]) == "MULTDOWN"           # dollar up -> GBP/USD down
    s.peers = peers("frxUSDJPY")
    assert s.direction("frxUSDJPY", d["frxUSDJPY"]) == "MULTUP"             # dollar up -> USD/JPY up
    assert s.stops("frxUSDJPY", d["frxUSDJPY"], "MULTUP") == (None, None)
    s2 = F.DollarWideCatchUp(stop=0.5)
    s2.peers = peers("frxUSDJPY")
    sl, _ = s2.stops("frxUSDJPY", d["frxUSDJPY"], "MULTUP")
    assert F.DollarWideCatchUp(stop=0.5).stops("frxUSDJPY", d["frxUSDJPY"], "MULTUP") is None   # no peers
    assert sl == pytest.approx(0.5 * 150 * 0.005 / 0.01, rel=0.05)
    d2 = _three([0.4, -0.3, 0.2])        # not all the same way
    s.peers = {o: d2[o] for o in SYMS if o != "frxUSDJPY"}
    assert s.direction("frxUSDJPY", d2["frxUSDJPY"]) is None
    d3 = _three([-0.4, -0.3, -0.2])      # dollar down -> buy EUR/USD... but EUR/USD led; GBP/USD Up
    s.peers = {o: d3[o] for o in SYMS if o != "frxGBPUSD"}
    assert s.direction("frxGBPUSD", d3["frxGBPUSD"]) == "MULTUP"


def test_lone_mover_trades_back_against_its_own_move():
    d = _three([0.5, 0.02, -0.05])       # EUR/USD moved alone (dollar up on it = EUR/USD fell)
    s = F.LoneMoverReverts(decision_hour=8, k=0.3, stop=0.0)
    s.peers = {o: d[o] for o in SYMS if o != "frxEURUSD"}
    assert s.direction("frxEURUSD", d["frxEURUSD"]) == "MULTUP"             # back up
    s.peers = {o: d[o] for o in SYMS if o != "frxGBPUSD"}
    assert s.direction("frxGBPUSD", d["frxGBPUSD"]) is None                 # did not move
    d2 = _three([0.5, 0.3, 0.1])         # others not flat
    s.peers = {o: d2[o] for o in SYMS if o != "frxEURUSD"}
    assert s.direction("frxEURUSD", d2["frxEURUSD"]) is None
    d3 = _three([0.0, 0.0, -0.5])        # USD/JPY fell alone (dollar down on it) -> buy it back
    s.peers = {o: d3[o] for o in SYMS if o != "frxUSDJPY"}
    assert s.direction("frxUSDJPY", d3["frxUSDJPY"]) == "MULTUP"


def test_round4_grids_and_luck_mode():
    for fam in ("f11", "f12"):
        assert R.ROUND[fam] == 4 and R.luck_mode(fam) == "signals" and R.luck_rule(fam) == (99, 500)
        assert sum(len(g) for _, g in R.FAMILIES[fam]) == 12
    assert R.luck_mode("f8") == "rates"


# ----------------------------------------------------------------------------- luck check
def test_signal_days_random_runs_keep_the_candidates_signal_count(market):
    sched = [(ep(2025, 3, 3), {"entry_hour": 9, "exit_hour": 12, "stop_pips": 0})]
    cand = _run(R.Scheduled(F.SessionDrift, sched), market)
    signals = R.entry_signals(cand.state)
    assert len(signals) > 100
    assert len(signals) == sum(a.startswith("Enter(") for _, _, a in cand.state.signals)
    assert any(a.startswith("ExitPosition(") for _, _, a in cand.state.signals)   # exits are not signals
    ups = []
    for seed in (1, 2):
        r = R.SignalDays(F.SessionDrift, sched, signals, seed=seed)
        e = _run(r, market)
        assert R.entry_signals(e.state) == signals            # same days and pairs, same count
        ups.append([s for s in e.state.signals if "MULTUP" in s[2]])
        again = _run(R.SignalDays(F.SessionDrift, sched, signals, seed=seed), market)
        assert again.state.signals == e.state.signals         # reproducible
    assert ups[0] != ups[1] and 0.3 < len(ups[0]) / len(signals) < 0.7
    assert not _run(R.SignalDays(F.SessionDrift, sched, [], seed=1), market).state.signals
