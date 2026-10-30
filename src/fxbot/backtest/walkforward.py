"""Rolling train/validation windows on pre-holdout data (walk-forward).

The holdout (2026-04-28 onward) is never part of any window: asking for a
window that reaches it raises HoldoutError.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

from fxbot.data.split import HOLDOUT_START, HoldoutError


@dataclass(frozen=True)
class Window:
    train_start: dt.date
    train_end: dt.date          # inclusive
    valid_start: dt.date
    valid_end: dt.date          # inclusive


def _add_months(d: dt.date, months: int) -> dt.date:
    m = d.month - 1 + months
    y = d.year + m // 12
    m = m % 12 + 1
    day = min(d.day, [31, 29 if y % 4 == 0 and (y % 100 or y % 400 == 0) else 28, 31, 30, 31, 30,
                      31, 31, 30, 31, 30, 31][m - 1])
    return dt.date(y, m, day)


def rolling_windows(start: dt.date, end: dt.date, train_months: int, valid_months: int,
                    step_months: int | None = None, anchored: bool = False) -> list[Window]:
    """Walk-forward windows: train, then validate on the next period, then step on.

    anchored=True keeps every training window starting at `start`.
    """
    if end >= HOLDOUT_START:
        raise HoldoutError(f"walk-forward windows must end before {HOLDOUT_START}")
    step = step_months or valid_months
    out, k = [], 0
    while True:
        t0 = start if anchored else _add_months(start, k * step)
        t1 = _add_months(start, k * step + train_months) - dt.timedelta(days=1)
        v0 = t1 + dt.timedelta(days=1)
        v1 = _add_months(v0, valid_months) - dt.timedelta(days=1)
        if v1 > end:
            break
        out.append(Window(t0, t1, v0, v1))
        k += 1
    return out
