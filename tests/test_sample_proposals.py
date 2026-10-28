import asyncio
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import sample_proposals as sp  # noqa: E402


class FakeWS:
    """Accepts every proposal; drops the link after `fail_after` sends."""

    def __init__(self, log, fail_after=None):
        self.log, self.fail_after, self.pending = log, fail_after, []

    async def send(self, raw):
        if self.fail_after is not None and len(self.log) >= self.fail_after:
            raise ConnectionResetError("dropped")
        msg = json.loads(raw)
        self.log.append(msg)
        self.pending.append(msg)

    async def recv(self):
        msg = self.pending.pop(0)
        return json.dumps({"req_id": msg["req_id"], "proposal": {
            "spot": 1.0, "commission": 0.01, "validation_params": {
                "take_profit": {"min": "0.10", "max": "50.00"},
                "stop_loss": {"min": "0.10", "max": "1.00"}}}})


def test_dropped_connection_resumes_without_repeating(monkeypatch):
    monkeypatch.setattr(sp, "PAUSE", 0)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    log = []
    opened = []

    @asynccontextmanager
    async def open_ws():
        opened.append(1)
        yield FakeWS(log, fail_after=40 if len(opened) == 1 else None)

    rows = asyncio.run(sp._sample_symbol("frxEURUSD", open_ws))
    keys = [(r["kind"], r["direction"], r["multiplier"], r["stake"], json.dumps(r["limit_order"]))
            for r in rows if r["kind"] in ("grid", "edge")]
    assert len(opened) == 2                      # reconnected once
    assert len(keys) == len(set(keys))           # no quote stored twice
    assert not any(r["kind"] == "error" for r in rows)
    assert len(rows) > 40                        # finished after the drop


def test_gives_up_after_attempts_and_says_so(monkeypatch):
    monkeypatch.setattr(sp, "PAUSE", 0)
    monkeypatch.setattr(asyncio, "sleep", _no_sleep)

    @asynccontextmanager
    async def open_ws():
        yield FakeWS([], fail_after=0)

    rows = asyncio.run(sp._sample_symbol("frxEURUSD", open_ws))
    assert rows[-1]["kind"] == "error"


_real_sleep = asyncio.sleep


async def _no_sleep(_seconds):
    await _real_sleep(0)
