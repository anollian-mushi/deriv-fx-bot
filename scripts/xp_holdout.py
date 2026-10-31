"""Perfect-fit experiment, stage 6: the first unseen-data test. Runs ONCE.

Runs the saved PerfectFit strategy, unchanged, on the holdout: Deriv 1m data from
2026-04-28 to the last collected day. Candles before 2026-04-28 are loaded only to
warm up the indicators; no trade opens before the holdout starts. Kill switch
enforced, start balance 100 USD, measured commission (1.5x shown alongside, from
the same strategy, as every project report does).

Before running it writes research/experiment/holdout_once.json with a SHA-256
fingerprint of every model file; if that file already exists the script refuses
to run again. The result is reported exactly as it comes out.

Run: python scripts/xp_holdout.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
import time

import xp_lib as L

from fxbot.backtest.engine import Engine
from fxbot.backtest.report import write_run
from fxbot.data.split import HOLDOUT_START, HOLDOUT_START_EPOCH
from fxbot.strategies.perfect_fit import MODEL_DIR, PerfectFit
from fxbot.strategies.pf_features import SYMBOLS

RUN_NAME = "experiment_perfect_fit_first_unseen_test"
WARMUP_START = HOLDOUT_START - dt.timedelta(days=60)
GUARD = L.RES / "holdout_once.json"


def last_day() -> dt.date:
    days = [max(p.name for p in (L.ROOT / "data" / s / "1m").glob("2*.csv.gz")) for s in SYMBOLS]
    return dt.date.fromisoformat(min(days)[:10])


def main() -> int:
    if GUARD.exists():
        print(f"refused: the holdout test already ran ({GUARD.relative_to(L.ROOT)}). It runs once only.")
        return 1
    end = last_day()
    fp = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(MODEL_DIR.iterdir())}
    L.save_json(GUARD, {"started_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                        "holdout": f"{HOLDOUT_START} to {end}", "model_sha256": fp})
    t0 = time.time()
    states = {}
    for label, stress in (("measured", 1.0), ("stress", 1.5)):
        eng = Engine(PerfectFit(trade_from=HOLDOUT_START_EPOCH), list(SYMBOLS), WARMUP_START, end,
                     stress=stress, include_holdout=True, kill_switch="enforce")
        eng.run()
        assert all(t["entry_epoch"] >= HOLDOUT_START_EPOCH for t in eng.state.trades)
        states[label] = eng.state
        print(label, L.engine_score(eng.state), f"({time.time() - t0:.0f}s)", flush=True)
    s = PerfectFit()
    info = {"strategy": "fxbot.strategies.perfect_fit:PerfectFit", "timeframe": "1h", "label": s.label,
            "params": s.params, "symbols": list(SYMBOLS), "start": str(HOLDOUT_START), "end": str(end),
            "warmup_from": str(WARMUP_START), "include_holdout": True, "starting_balance": 100.0,
            "kill_switch_mode": "enforce", "test": "first unseen-data test (run once)"}
    out = write_run(RUN_NAME, info, states["measured"], states["stress"], include_holdout=True)
    g = json.loads(GUARD.read_text())
    g.update({"finished_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
              "measured": L.engine_score(states["measured"]), "stress_1_5x": L.engine_score(states["stress"]),
              "report": str(out.relative_to(L.ROOT))})
    L.save_json(GUARD, g)
    print("report:", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
