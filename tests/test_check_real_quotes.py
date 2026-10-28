import json
import re
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_real_quotes as crq  # noqa: E402

# The real-account script and the sampler it reuses must never contain
# order, close or order-change requests.
FORBIDDEN = re.compile(r"\b(buy|sell|contract_update|cancel|transfer)\b", re.IGNORECASE)


@pytest.mark.parametrize("name", ["check_real_quotes.py", "sample_proposals.py"])
def test_source_has_no_trading_calls(name):
    source = (SCRIPTS / name).read_text()
    # Ignore the docstring/comment lines that describe what is NOT done.
    code = "\n".join(l for l in source.splitlines() if not l.strip().startswith("#"))
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    assert not FORBIDDEN.search(code)


@pytest.mark.parametrize("payload", [
    {"buy": "abc", "price": 1}, {"sell": 123, "price": 0},
    {"contract_update": 1, "contract_id": 1, "limit_order": {}},
    {"cancel": 1}, {"portfolio": 1}, {"ticks": "frxEURUSD", "subscribe": 1},
    {"proposal": 1, "subscribe": 1},
])
def test_guard_refuses_everything_else(payload):
    with pytest.raises(crq.RefusedRequest):
        crq.check_request(json.dumps({**payload, "req_id": 1}))


@pytest.mark.parametrize("payload", [
    {"proposal": 1, "amount": 1, "multiplier": 100}, {"contracts_for": "frxEURUSD"},
    {"active_symbols": "brief"}, {"time": 1},
])
def test_guard_allows_quotes(payload):
    crq.check_request(json.dumps({**payload, "req_id": 1}))


def test_refuses_real_mode(monkeypatch):
    monkeypatch.setenv("DERIV_MODE", "real")
    with pytest.raises(SystemExit, match="real mode"):
        crq.real_account_id()


def test_real_url_check():
    assert crq.is_real_ws_url("wss://api.derivws.com/trading/v1/options/ws/real?otp=x")
    assert not crq.is_real_ws_url("wss://api.derivws.com/trading/v1/options/ws/demo?otp=x")
