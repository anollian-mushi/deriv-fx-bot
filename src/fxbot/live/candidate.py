"""Pick and load the incubator candidate the live bot runs.

The bot runs the candidate's FROZEN copy from incubator/candidates/<id>/,
after registry.verify() has re-hashed every file against its registered
SHA-256 fingerprint. A changed file stops the bot from starting.

Real money needs a graduated candidate: its incubator state says "graduated"
AND exams.json (hash-chained) holds a passed exam result for it.
"""

from __future__ import annotations

import json
from pathlib import Path

from fxbot.incubator import leaderboard
from fxbot.incubator.registry import INCUBATOR, Candidate, candidates, exams_path, load_strategy, read_chain, verify

LEADER = "leader"


class CandidateError(RuntimeError):
    pass


def leader_id(root: Path = INCUBATOR) -> str | None:
    """Top of the incubator leaderboard among graduated/active candidates (None if none is active yet)."""
    path = root / "records" / "index.json"
    if not path.exists():
        return None
    index = json.loads(path.read_text())
    for cid, row in leaderboard._rows(index):
        if row.get("status") in ("graduated", "active"):
            return cid
    return None


def resolve_id(strategy_id: str, fallback: str, root: Path = INCUBATOR) -> tuple[str, str]:
    """(candidate id, how it was chosen)."""
    if not strategy_id:
        raise CandidateError("STRATEGY_ID is not set (an incubator candidate id, or 'leader')")
    if strategy_id != LEADER:
        return strategy_id, "STRATEGY_ID"
    lid = leader_id(root)
    if lid:
        return lid, "incubator leader"
    return fallback, "LEADER_FALLBACK (no candidate is active in the incubator yet)"


def find(cid: str, root: Path = INCUBATOR) -> Candidate:
    for c in candidates(root):
        if c.id == cid:
            return c
    raise CandidateError(f"{cid} is not a registered incubator candidate")


def load(cid: str, root: Path = INCUBATOR):
    """(Candidate, fresh strategy instance). Raises TamperedError if its fingerprint does not match."""
    c = find(cid, root)
    verify(c)
    return c, load_strategy(c)


def is_graduated(cid: str, root: Path = INCUBATOR) -> bool:
    state_path = root / "records" / cid / "state.json"
    if not state_path.exists():
        return False
    if json.loads(state_path.read_text()).get("status") != "graduated":
        return False
    results = [e for e in read_chain(exams_path(root)) if e.get("id") == cid and e.get("event") == "result"]
    return any(e.get("passed") is True for e in results)
