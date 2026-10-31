"""Research data split (CLAUDE.md, Research rules).

The final holdout is all data dated HOLDOUT_START or later, from any source.
That start date is fixed and never moves. Nothing in the holdout period may
be used for training, validation, parameter choices or strategy selection
until the single final test, so research code drops it by default.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

HOLDOUT_START = date(2026, 4, 28)
HOLDOUT_START_EPOCH = int(datetime(2026, 4, 28, tzinfo=timezone.utc).timestamp())


class HoldoutError(RuntimeError):
    """Raised when holdout-period data reaches code that must not see it."""


def in_holdout(epoch: int) -> bool:
    return epoch >= HOLDOUT_START_EPOCH


def day_in_holdout(day: date) -> bool:
    return day >= HOLDOUT_START


def before_holdout(items, epoch_of=lambda x: x.epoch):
    """Keep only items dated before HOLDOUT_START."""
    return [x for x in items if not in_holdout(epoch_of(x))]


# ----------------------------------------------------------------------------- the untouched period
# The 2026-04-28 holdout was used for the final Phase 4 checks and is used up (owner, 31 Oct 2026).
# Deriv data from UNTOUCHED_START onward is the new untouched period. Research, tuning and selection
# never see it. Only the strategy incubator (incubator/) reads it, and it scores each registered
# candidate only on days after that candidate's registration date.
UNTOUCHED_START = date(2026, 10, 31)
UNTOUCHED_START_EPOCH = int(datetime(2026, 10, 31, tzinfo=timezone.utc).timestamp())


class UntouchedError(HoldoutError):
    """Raised when data from the untouched period reaches code other than the incubator."""


def in_untouched(epoch: int) -> bool:
    return epoch >= UNTOUCHED_START_EPOCH
