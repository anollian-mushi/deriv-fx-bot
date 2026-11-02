"""TJR method (owner's course notes), as fixed in docs/tjr_rules.md and approved on 2 Nov 2026.

One strategy class per execution timeframe. Each one is fed its *confirmation* candles
(the engine's timeframe) and builds every bigger timeframe itself, candle by candle, from
closed candles only:

- TJR5m: fed 1m candles; execution 5m; confirmation inside the zone on 1m.
- TJR15m: fed 5m candles; execution 15m; confirmation inside the zone on 5m.
- Both: liquidity sweeps on 30m, bias on 4h and daily (UTC candles).

The chain for a short (a long is the mirror image):
1. Bias: the last 4h break of structure and the last daily break of structure are both
   bearish (section 6, C12).
2. A 30m candle inside the London or New York session window trades above an untaken
   prominent high and closes back below it (sections 3-4).
3. Within `n` execution candles, an execution candle closes below the last execution swing
   low that formed before the candle that made the sweep high (section 5, C10).
4. Entry (section 9, by `model`):
   1: at the close of the break-of-structure candle.
   2/3/4: price comes back up into the order block (2), a displacement FVG (3), or either
      one lying wholly in premium (4), within `n` execution candles of the break. Then
      (confirm="ltf", owner's C18) a fresh confirmation-timeframe sweep inside the zone
      and a confirmation-timeframe break of structure; entry at that candle's close. The
      labelled alternative confirm="touch" enters at the close of the first execution
      candle that reached into the zone and closed with the zone holding. The entry price
      must be in premium (above the 50% of the sweep high to the low since the sweep).
5. Stop: 1 pip beyond the 30m sweep wick, never at an execution swing (section 10, owner's
   point 4). Target: the nearest untaken opposing prominent level at least 1R away, else
   5R (C24). Optional (breakeven=True, owner's C23 variant): the stop moves to Deriv's
   smallest stop once price reaches 1R. Every trade is closed at 17:55 UTC.
6. Skipped by the engine at fill time: stop under 4x the cost per trade (owner's rule), stop
   beyond Deriv's stop out. Multiplier x200, or x100 if the stop is too wide for x200.

Settings (at most 5): model, n, breakeven, confirm. Everything else is fixed by the rules.
The strategy only proposes trades; the CLAUDE.md risk module decides (engine / live bot).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

import numpy as np

from fxbot import symbols as symbols_mod
from fxbot.strategies import tjr_calendar as cal
from fxbot.strategies.base import Enter, ExitPosition, Strategy

PIP = symbols_mod.PIP
SL_BUFFER_PIPS = 1.0               # C21
ENTRY_SLIPPAGE_PIPS = 0.5          # the engine's standard fill (fills.ENTRY_SLIPPAGE_PIPS)
MIN_STOP_COST_MULTIPLE = 4.0       # owner's cost rule (Step 2)
TP_MIN_R, TP_MAX_R = 1.0, 5.0      # C24
SWING_30M_LIFE = 24 * 3600         # C7: 30m swings from the last 24 hours
STOP_OUT_MARGIN = 0.8              # the stop must lie inside 80% of the stop-out move (C22)
CATCH_UP_DAYS = 60                 # a fresh instance replays at most this much history
MAX_KEEP = 4000                    # closed candles kept per timeframe (older ones are dropped)


# ----------------------------------------------------------------------------- building blocks
class _Series:
    """Closed candles of one timeframe, built from smaller closed candles, with absolute indexes."""

    def __init__(self, seconds: int):
        self.sec = seconds
        self.off = 0                       # absolute index of the first kept candle
        self.s: list[int] = []             # start epochs
        self.o: list[float] = []
        self.h: list[float] = []
        self.l: list[float] = []
        self.c: list[float] = []
        self.cur: list | None = None       # [start, o, h, l, c] of the forming candle

    def __len__(self) -> int:
        return self.off + len(self.s)

    def _close(self) -> int:
        b, o, h, lo, c = self.cur
        self.s.append(b)
        self.o.append(o)
        self.h.append(h)
        self.l.append(lo)
        self.c.append(c)
        self.cur = None
        if len(self.s) > MAX_KEEP:
            k = MAX_KEEP // 2
            for a in (self.s, self.o, self.h, self.l, self.c):
                del a[:k]
            self.off += k
        return len(self) - 1

    def add(self, start: int, o: float, h: float, lo: float, c: float, end: int) -> list[int]:
        """Add one smaller closed candle; return the absolute indexes of candles it closed."""
        closed = []
        b = start - start % self.sec
        if self.cur is not None and self.cur[0] != b:
            closed.append(self._close())          # the bucket ended with missing minutes
        if self.cur is None:
            self.cur = [b, o, h, lo, c]
        else:
            cur = self.cur
            if h > cur[2]:
                cur[2] = h
            if lo < cur[3]:
                cur[3] = lo
            cur[4] = c
        if end >= b + self.sec:
            closed.append(self._close())
        return closed

    def get(self, i: int) -> tuple[int, float, float, float, float]:
        j = i - self.off
        return self.s[j], self.o[j], self.h[j], self.l[j], self.c[j]

    def has(self, i: int) -> bool:
        return self.off <= i < len(self)


class _Swings:
    """Swing highs/lows of strength k (section 2): higher than the k candles after it, at least as
    high as the k candles before it (a tie on the left goes to the later candle). Known only when
    the k-th candle after it has closed."""

    def __init__(self, k: int, keep: int = 60):
        self.k, self.keep = k, keep
        self.highs: list[tuple[int, float, int]] = []    # (candle index, price, confirmed at index)
        self.lows: list[tuple[int, float, int]] = []

    def update(self, ser: _Series, i: int) -> tuple[tuple | None, tuple | None]:
        k = self.k
        j = i - k
        if j - k < ser.off:
            return None, None
        hs = [ser.h[x - ser.off] for x in range(j - k, i + 1)]
        ls = [ser.l[x - ser.off] for x in range(j - k, i + 1)]
        hj, lj = hs[k], ls[k]
        new_h = new_l = None
        if all(hj >= x for x in hs[:k]) and all(hj > x for x in hs[k + 1:]):
            new_h = (j, hj, i)
            self.highs.append(new_h)
            if len(self.highs) > self.keep:
                del self.highs[0]
        if all(lj <= x for x in ls[:k]) and all(lj < x for x in ls[k + 1:]):
            new_l = (j, lj, i)
            self.lows.append(new_l)
            if len(self.lows) > self.keep:
                del self.lows[0]
        return new_h, new_l


class _Bias:
    """Direction of the most recent break of structure on one timeframe (section 6)."""

    def __init__(self):
        self.sw = _Swings(2)
        self.ref_high: float | None = None
        self.ref_low: float | None = None
        self.bias = 0

    def update(self, ser: _Series, i: int) -> None:
        close = ser.c[i - ser.off]
        if self.ref_high is not None and close > self.ref_high:
            self.bias, self.ref_high = 1, None
        elif self.ref_low is not None and close < self.ref_low:
            self.bias, self.ref_low = -1, None
        new_h, new_l = self.sw.update(ser, i)
        if new_h:
            self.ref_high = new_h[1]
        if new_l:
            self.ref_low = new_l[1]


@dataclass
class _Level:
    price: float
    side: int            # +1 = a high (buy-side liquidity), -1 = a low (sell-side liquidity)
    avail: int           # epoch from which it exists
    expires: float
    source: str
    taken: bool = False


@dataclass
class _Zone:
    near: float          # edge price reaches first on the way back
    far: float           # edge beyond which a close invalidates it
    kind: str            # "ob" / "fvg"


@dataclass
class _Setup:
    d: int                       # +1 long, -1 short
    extreme: float               # sweep wick tip (stop goes beyond it)
    sweep_end: int
    ext_idx: int                 # execution candle that made the extreme
    ref: float                   # execution swing that must break
    bos_deadline: int            # last allowed close time of the break
    session_end: int
    session_key: tuple
    ob: _Zone | None
    leg_ext: float               # most favourable price since the sweep (dealing range)
    phase: str = "bos"           # bos -> retrace -> (entry)
    bos_idx: int = -1
    bos_time: int = 0
    touch_deadline: int = 0
    zones: list = field(default_factory=list)
    armed: _Zone | None = None
    draw: float | None = None    # nearest opposing liquidity when the break happened
    ltf: dict | None = None      # pending confirmation-timeframe sweep
    ltf_taken: set = field(default_factory=set)   # confirmation swings already traded through


class _Sym:
    def __init__(self, base_sec: int, exec_sec: int):
        self.base = _Series(base_sec)          # confirmation timeframe (as fed)
        self.ex = _Series(exec_sec)
        self.m30 = _Series(1800)
        self.h4 = _Series(4 * 3600)
        self.d1 = _Series(86400)
        self.ex_sw = _Swings(1)
        self.m30_sw = _Swings(2, keep=10)
        self.base_sw = _Swings(1)
        self.bias4, self.bias1 = _Bias(), _Bias()
        self.levels: list[_Level] = []
        self.ranges: dict = {}                 # name -> [ny day, end epoch, hi, lo]
        self.setup: _Setup | None = None
        self.used_sessions: set = set()
        self.n = 0                             # candles processed
        self.last_end = 0


class TJRBase(Strategy):
    name = "tjr"
    timeframe = "1m"
    exec_tf = "5m"
    multiplier = 200
    risk_fraction = 0.03
    warmup_days = 70
    defaults = {"model": 1, "n": 12, "breakeven": False, "confirm": "ltf"}

    def __init__(self, **params):
        self.params = {**self.defaults, **params}
        p = self.params
        if p["model"] not in (1, 2, 3, 4) or p["confirm"] not in ("ltf", "touch") or int(p["n"]) < 1:
            raise ValueError(f"bad TJR settings {p}")
        self.model, self.n = int(p["model"]), int(p["n"])
        self.breakeven, self.confirm = bool(p["breakeven"]), p["confirm"]
        self.base_sec = {"1m": 60, "5m": 300}[self.timeframe]
        self.exec_sec = {"5m": 300, "15m": 900}[self.exec_tf]
        self.state: dict[str, _Sym] = {}
        self.stats: Counter = Counter()          # setups and the rule that ended each (diagnostics)
        self._live = True
        self._hour_cache: dict[int, list] = {}

    def _c(self, key: str) -> None:
        if self._live:                            # not while a fresh instance replays history
            self.stats[key] += 1

    # ------------------------------------------------------------- hooks the luck check may replace
    def entry(self, symbol, candles):           # not used: the TJR luck check replays signals
        return None

    def stops(self, symbol, candles, direction):
        return None

    # ------------------------------------------------------------- main entry point
    def on_candle(self, symbol, candles, position, pending):
        st = self.state.get(symbol)
        if st is None:
            st = self.state[symbol] = _Sym(self.base_sec, self.exec_sec)
        n = len(candles)
        start = st.n
        if start == 0 and n > 1:
            # A fresh instance (e.g. the walk-forward switched settings): replay recent history only.
            cut = int(candles.end[-1]) - CATCH_UP_DAYS * 86400
            start = int(np.searchsorted(candles.end, cut))
        signal = None
        for i in range(start, n):
            self._live = i == n - 1 or start == st.n
            e = int(candles.end[i])
            sig = self._step(symbol, st, int(candles.epoch[i]), float(candles.open[i]), float(candles.high[i]),
                             float(candles.low[i]), float(candles.close[i]), e, live=(i == n - 1))
            if i == n - 1:
                signal = sig
        st.n = n
        t = int(candles.end[-1])
        acts = []
        if position is not None and t % 86400 >= cal.FLAT_SECOND_OF_DAY:
            acts.append(ExitPosition())                       # C25: flat at 17:55 UTC
        if signal is not None:
            if position is not None or pending:
                self._c("skip_busy")
            else:
                acts.append(signal)
        return acts

    # ------------------------------------------------------------- one confirmation candle
    def _step(self, symbol, st: _Sym, s, o, h, lo, c, e, live: bool):
        pip = PIP[symbol]
        self._ranges(symbol, st, s, h, lo)
        bi = st.base.add(s, o, h, lo, c, e)
        ex_closed = st.ex.add(s, o, h, lo, c, e)
        m30_closed = st.m30.add(s, o, h, lo, c, e)
        for i in st.h4.add(s, o, h, lo, c, e):
            st.bias4.update(st.h4, i)
        for i in st.d1.add(s, o, h, lo, c, e):
            st.bias1.update(st.d1, i)
            ds, _, dh, dl, _ = st.d1.get(i)
            st.levels = [lv for lv in st.levels if lv.source != "pd"]
            day_end = ds + 86400
            st.levels += [_Level(dh, 1, day_end, float("inf"), "pd"), _Level(dl, -1, day_end, float("inf"), "pd")]
        for i in ex_closed:
            st.ex_sw.update(st.ex, i)
        for i in bi:
            nh, nl = st.base_sw.update(st.base, i)
        for i in m30_closed:
            self._on_30m(symbol, st, i)
        signal = None
        for i in ex_closed:
            sig = self._on_exec(symbol, st, i, pip)
            signal = signal or sig
        if self.model != 1 and self.confirm == "ltf" and bi:
            sig = self._on_ltf(symbol, st, bi[-1], pip)
            signal = signal or sig
        st.last_end = e
        return signal if live else None

    # ------------------------------------------------------------- session ranges (Asia, London)
    def _range_names(self, s: int) -> list:
        key = s // 3600
        r = self._hour_cache.get(key)
        if r is None:
            r = []
            d = cal.ny_date(s)
            for day in (d, d + cal.dt.timedelta(days=1)):
                w = cal.day_windows(day)
                for name in ("asia_range", "london_range"):
                    a, b = w[name]
                    if a <= s < b:
                        r.append((name, day, b))
            if len(self._hour_cache) > 5000:
                self._hour_cache.clear()
            self._hour_cache[key] = r
        return r

    def _ranges(self, symbol, st: _Sym, s, h, lo):
        for name, acc in list(st.ranges.items()):
            if s >= acc[1]:
                day, end, hi, low = acc
                flat = int(cal.dt.datetime(day.year, day.month, day.day, tzinfo=cal.UTC).timestamp()) \
                    + cal.FLAT_SECOND_OF_DAY
                st.levels += [_Level(hi, 1, end, flat, name), _Level(low, -1, end, flat, name)]
                del st.ranges[name]
        for name, day, end in self._range_names(s):
            acc = st.ranges.get(name)
            if acc is None or acc[0] != day:
                st.ranges[name] = [day, end, h, lo]
            else:
                acc[2] = max(acc[2], h)
                acc[3] = min(acc[3], lo)

    # ------------------------------------------------------------- 30m: liquidity and sweeps
    def _on_30m(self, symbol, st: _Sym, i: int):
        s, _, h, lo, c = st.m30.get(i)
        e = s + 1800
        swept = {1: [], -1: []}
        keep = []
        for lv in st.levels:
            if lv.expires <= s or lv.taken:
                continue
            if lv.avail <= s:
                if lv.side == 1 and h > lv.price:
                    lv.taken = True
                    if c < lv.price:
                        swept[1].append(lv)
                elif lv.side == -1 and lo < lv.price:
                    lv.taken = True
                    if c > lv.price:
                        swept[-1].append(lv)
            if not lv.taken:
                keep.append(lv)
        st.levels = keep
        nh, nl = st.m30_sw.update(st.m30, i)
        if nh:
            st.levels.append(_Level(nh[1], 1, e, st.m30.get(nh[0])[0] + SWING_30M_LIFE, "m30"))
        if nl:
            st.levels.append(_Level(nl[1], -1, e, st.m30.get(nl[0])[0] + SWING_30M_LIFE, "m30"))
        if not (swept[1] or swept[-1]):
            return
        self._c("sweeps")
        if swept[1] and swept[-1]:
            self._c("sweep_both_sides")
            return
        if st.setup is not None:
            su = st.setup
            if su.d * ((h if su.d == -1 else lo) - su.extreme) < 0:
                self._cancel(st, "stop_level_traded")      # price went through its stop level
            else:
                self._c("sweep_while_active")
                return
        side = 1 if swept[1] else -1
        d = -side                                   # a swept high sets up a short
        name, day, win = cal.session_at(s)
        if name is None or e > win[1]:
            self._c("sweep_outside_session")
            return
        bias = st.bias4.bias if st.bias4.bias == st.bias1.bias else 0
        if bias != d:
            self._c("sweep_against_bias")
            return
        key = (day, name)
        if key in st.used_sessions:
            self._c("sweep_session_used")
            return
        extreme = h if d == -1 else lo
        # Execution candle that made the extreme (first one), then the reference swing before it.
        ext_idx = None
        j = len(st.ex) - 1
        while j >= st.ex.off:
            es, _, eh, el, _ = st.ex.get(j)
            if es < s:
                break
            if (eh if d == -1 else el) == extreme:
                ext_idx = j
            j -= 1
        if ext_idx is None:
            self._c("sweep_no_exec_candle")
            return
        swings = st.ex_sw.lows if d == -1 else st.ex_sw.highs
        ref = next((p for (k, p, _) in reversed(swings) if k < ext_idx), None)
        if ref is None or d * (extreme - ref) >= 0:
            self._c("sweep_no_reference_swing")
            return
        leg_ext = min(st.ex.get(j)[3] for j in range(ext_idx, len(st.ex))) if d == -1 else \
            max(st.ex.get(j)[2] for j in range(ext_idx, len(st.ex)))
        ob = None
        for j in range(ext_idx, max(st.ex.off, ext_idx - 20) - 1, -1):
            _, eo, eh, el, ec = st.ex.get(j)
            if (ec > eo) if d == -1 else (ec < eo):
                ob = _Zone(el, eh, "ob") if d == -1 else _Zone(eh, el, "ob")
                break
        st.setup = _Setup(d=d, extreme=extreme, sweep_end=e, ext_idx=ext_idx, ref=ref,
                          bos_deadline=e + self.n * self.exec_sec, session_end=win[1], session_key=key,
                          ob=ob, leg_ext=leg_ext)
        self._c("setups")

    # ------------------------------------------------------------- execution timeframe
    def _cancel(self, st: _Sym, why: str):
        self._c(f"cancel_{why}")
        st.setup = None

    def _on_exec(self, symbol, st: _Sym, i: int, pip: float):
        su = st.setup
        if su is None:
            return None
        s, _, h, lo, c = st.ex.get(i)
        e = s + self.exec_sec
        if e < su.sweep_end:
            return None
        d = su.d
        adv, fav = (h, lo) if d == -1 else (lo, h)
        if d * (adv - su.extreme) < 0:
            return self._cancel(st, "stop_level_traded")
        if d * (fav - su.leg_ext) > 0:
            su.leg_ext = fav
        if su.phase == "bos":
            if d * (c - su.ref) > 0:
                su.phase, su.bos_idx, su.bos_time = "retrace", i, e
                self._c("bos")
                if self.model == 1:
                    return self._signal(symbol, st, c, e, pip)
                self._start_retrace(symbol, st, e)
                return None
            if e >= su.bos_deadline:
                return self._cancel(st, "no_bos_in_time")
            return None
        # retrace phase (models 2-4)
        if su.draw is not None and d * (fav - su.draw) >= 0:
            return self._cancel(st, "draw_reached_before_entry")
        su.zones = [z for z in su.zones if d * (c - z.far) >= 0]
        if su.armed is not None and su.armed not in su.zones:
            su.armed, su.ltf = None, None
        if self.confirm == "touch" and e > su.bos_time:
            touched = [z for z in su.zones if d * (adv - z.near) <= 0]
            if touched and s < su.touch_deadline:
                z = max(touched, key=lambda z: d * z.near)
                if self.model == 4 and not self._in_premium(su, z):
                    su.zones.remove(z)
                elif d * (c - z.far) >= 0:
                    return self._entry_if_premium(symbol, st, c, e, pip)
        if not su.zones:
            return self._cancel(st, "zones_invalidated")
        if su.armed is None and e >= su.touch_deadline:
            return self._cancel(st, "no_retrace_in_time")
        if e >= su.session_end:
            return self._cancel(st, "session_ended")
        return None

    def _start_retrace(self, symbol, st: _Sym, e: int):
        su, d = st.setup, st.setup.d
        zones = []
        if self.model in (2, 4) and su.ob is not None:
            zones.append(su.ob)
        if self.model in (3, 4):
            for a in range(max(su.ext_idx, st.ex.off), su.bos_idx - 1):
                _, _, ah, al, _ = st.ex.get(a)
                _, bo, _, _, bc = st.ex.get(a + 1)
                _, _, ch, cl, _ = st.ex.get(a + 2)
                if d == -1 and bc < bo and ch < al:
                    zones.append(_Zone(ch, al, "fvg"))
                elif d == 1 and bc > bo and cl > ah:
                    zones.append(_Zone(cl, ah, "fvg"))
        if not zones:
            return self._cancel(st, "no_zone")
        su.zones = zones
        su.touch_deadline = e + self.n * self.exec_sec
        draws = self._target_levels(st, su.d, su.leg_ext, e)
        su.draw = draws[0] if draws else None

    @staticmethod
    def _in_premium(su: _Setup, z: _Zone) -> bool:
        eq = (su.extreme + su.leg_ext) / 2
        return su.d * (z.near - eq) < 0 and su.d * (z.far - eq) < 0

    def _entry_if_premium(self, symbol, st, price, e, pip):
        su = st.setup
        eq = (su.extreme + su.leg_ext) / 2
        if su.d * (price - eq) >= 0:
            return self._cancel(st, "entry_not_in_premium_discount")
        return self._signal(symbol, st, price, e, pip)

    # ------------------------------------------------------------- confirmation timeframe (C18)
    def _on_ltf(self, symbol, st: _Sym, i: int, pip: float):
        su = st.setup
        if su is None or su.phase != "retrace":
            return None
        s, _, h, lo, c = st.base.get(i)
        e = s + self.base_sec
        if e <= su.bos_time:
            return None
        d = su.d
        adv = h if d == -1 else lo
        if d * (adv - su.extreme) < 0:
            return self._cancel(st, "stop_level_traded")
        if su.armed is None:
            touched = [z for z in su.zones if d * (adv - z.near) <= 0]
            if not touched or s >= su.touch_deadline:
                return None
            z = max(touched, key=lambda z: d * z.near)
            if self.model == 4 and not self._in_premium(su, z):
                su.zones.remove(z)
                if not su.zones:
                    return self._cancel(st, "zones_invalidated")
                return None
            su.armed = z
            self._c("zone_touched")
        z = su.armed
        # pending confirmation sweep: cancelled if price trades beyond its wick before the break
        if su.ltf is not None and i > su.ltf["idx"] and d * (adv - su.ltf["extreme"]) < 0:
            su.ltf = None
        # A fresh confirmation sweep inside the zone: the wick goes through a confirmation-timeframe
        # swing that formed after the break (each such swing is used once), and the candle closes
        # back on the trade side.
        swept = False
        pool = st.base_sw.highs if d == -1 else st.base_sw.lows
        for k, p, conf in reversed(pool):
            if not st.base.has(k) or st.base.s[k - st.base.off] < su.bos_time:
                break                                   # older swings: formed before the break
            if conf >= i or (k, p) in su.ltf_taken:
                continue
            if d * (adv - p) < 0:
                su.ltf_taken.add((k, p))
                swept = swept or d * (c - p) > 0
        if swept and d * (adv - z.near) <= 0:
            refs = st.base_sw.lows if d == -1 else st.base_sw.highs
            ref = next((q for (kk, q, _) in reversed(refs) if kk < i), None)
            if ref is not None and d * (adv - ref) < 0 and (su.ltf is None or d * (adv - su.ltf["extreme"]) < 0):
                su.ltf = {"idx": i, "extreme": adv, "ref": ref, "deadline": i + self.n}
                self._c("ltf_sweeps")
        if su.ltf is not None:
            if d * (c - su.ltf["ref"]) > 0:
                self._c("ltf_bos")
                return self._entry_if_premium(symbol, st, c, e, pip)
            if i >= su.ltf["deadline"]:
                su.ltf = None
        if e >= su.session_end:
            return self._cancel(st, "session_ended")
        return None

    # ------------------------------------------------------------- the order proposal
    def _target_levels(self, st: _Sym, d: int, price: float, t: int) -> list[float]:
        """Untaken opposing levels beyond `price`, nearest first. A short aims at lows below it, a
        long at highs above it. Callers pass the most favourable price since the sweep, so levels
        the displacement already traded through do not count."""
        out = [lv.price for lv in st.levels
               if lv.side == d and not lv.taken and lv.avail <= t and lv.expires > t
               and d * (lv.price - price) > 0]
        return sorted(out, key=lambda p: abs(p - price))

    def _signal(self, symbol, st: _Sym, close: float, t: int, pip: float):
        su = st.setup
        st.setup = None                                        # one trade per sweep (C19)
        d = su.d
        ok, why = cal.entry_allowed(symbol, t)
        if not ok:
            self._c(f"skip_{why}")
            return None
        if su.session_key in st.used_sessions:
            self._c("skip_session_used")
            return None
        if (st.bias4.bias if st.bias4.bias == st.bias1.bias else 0) != d:
            self._c("skip_bias_changed")
            return None
        entry = close + d * ENTRY_SLIPPAGE_PIPS * pip
        sl_level = su.extreme - d * SL_BUFFER_PIPS * pip
        risk = abs(entry - sl_level)
        if d * (entry - sl_level) <= 0:
            self._c("skip_stop_passed")
            return None
        frac = risk / entry
        if frac < STOP_OUT_MARGIN / 200:
            mult = 200
        elif frac < STOP_OUT_MARGIN / 100:
            mult = 100
        else:
            self._c("skip_stop_too_wide")
            return None
        beyond = su.leg_ext if d * (su.leg_ext - entry) > 0 else entry
        dist = next((abs(p - entry) for p in self._target_levels(st, d, beyond, t)
                     if abs(p - entry) >= TP_MIN_R * risk), None)
        if dist is None or dist > TP_MAX_R * risk:
            dist = TP_MAX_R * risk
        st.used_sessions.add(su.session_key)
        if len(st.used_sessions) > 50:
            st.used_sessions = set(sorted(st.used_sessions)[-10:])
        self._c("signals")
        return Enter("MULTUP" if d == 1 else "MULTDOWN", multiplier=mult,
                     stop_loss_pips=round(risk / pip, 2), take_profit_pips=round(dist / pip, 2),
                     risk_fraction=self.risk_fraction, min_stop_cost_multiple=MIN_STOP_COST_MULTIPLE,
                     require_stop=True, move_stop_at_r=1.0 if self.breakeven else None)


class TJR5m(TJRBase):
    name = "tjr_5m"
    timeframe = "1m"
    exec_tf = "5m"


class TJR15m(TJRBase):
    name = "tjr_15m"
    timeframe = "5m"
    exec_tf = "15m"


class TJRReplay(Strategy):
    """Luck check: the candidate's own signals (same pairs, minutes, stops, targets, multiplier and
    stop rule), with a coin toss for each direction; every trade still closes at 17:55 UTC.

    signals: {(symbol, signal epoch): Enter}. The coin toss is keyed by seed, time and pair, so a
    run always draws the same directions whatever order the engine calls the pairs in."""

    name = "tjr_replay"

    def __init__(self, timeframe: str, signals: dict, seed: int, symbols: tuple):
        self.timeframe = timeframe
        self.signals, self.seed, self.symbols = signals, seed, tuple(symbols)

    def on_candle(self, symbol, candles, position, pending):
        t = int(candles.end[-1])
        acts = []
        if position is not None and t % 86400 >= cal.FLAT_SECOND_OF_DAY:
            acts.append(ExitPosition())
        a = self.signals.get((symbol, t))
        if a is not None and position is None and not pending:
            u = np.random.default_rng([self.seed, t, self.symbols.index(symbol)]).random()
            acts.append(Enter("MULTUP" if u < 0.5 else "MULTDOWN", multiplier=a.multiplier,
                              stop_loss_pips=a.stop_loss_pips, take_profit_pips=a.take_profit_pips,
                              risk_fraction=a.risk_fraction, min_stop_cost_multiple=a.min_stop_cost_multiple,
                              require_stop=a.require_stop, move_stop_at_r=a.move_stop_at_r))
        return acts


REGISTRY = {cls.name: cls for cls in (TJR5m, TJR15m)}
