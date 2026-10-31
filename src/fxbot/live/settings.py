"""Live bot settings: environment variables first, then .env (same rule as fxbot.config).

Extra settings on top of fxbot.config.Settings:
- STRATEGY_ID        incubator candidate id, or "leader" (the incubator leaderboard's top
                     active/graduated candidate, resolved once at startup)
- LEADER_FALLBACK    candidate used when STRATEGY_ID=leader and no candidate is active yet
- CONFIRM_REAL       must be "yes" (with DERIV_MODE=real and a graduated candidate) for real money
- BOT_START_BALANCE  the bot's pretend ledger on demo (default 100, must be 50-100)
- BOT_HOME           folder for the journal, heartbeat, HALT file, local candles (default state/live)
- COST_SAMPLING      true: quote every pair once an hour and journal the commission rate
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from fxbot.config import DEFAULT_ENV_FILE, REPO_ROOT, ConfigError, Settings, _parse_bool, load_settings, parse_env_file


@dataclass(frozen=True)
class LiveSettings:
    base: Settings = field(repr=False)
    strategy_id: str
    leader_fallback: str
    confirm_real: bool
    start_balance: float
    home: Path
    cost_sampling: bool

    @property
    def journal_path(self) -> Path:
        return self.home / "journal.sqlite"

    @property
    def heartbeat_path(self) -> Path:
        return self.home / "heartbeat"

    @property
    def halt_path(self) -> Path:
        return self.home / "HALT"

    @property
    def status_path(self) -> Path:
        return self.home / "status.json"

    @property
    def data_dir(self) -> Path:
        return self.home / "data"

    @property
    def requests_dir(self) -> Path:
        return self.home / "requests"


def load_live_settings(environ: Mapping[str, str] | None = None,
                       env_file: Path | None = DEFAULT_ENV_FILE) -> LiveSettings:
    environ = os.environ if environ is None else environ
    file_values = parse_env_file(env_file) if env_file else {}

    def get(name: str, default: str | None = None) -> str | None:
        v = environ.get(name)
        if v is None or not v.strip():
            v = file_values.get(name)
        return v.strip() if v and v.strip() else default

    base = load_settings(environ, env_file)
    try:
        start = float(get("BOT_START_BALANCE", "100"))
    except ValueError:
        raise ConfigError("BOT_START_BALANCE must be a number") from None
    if not 50 <= start <= 100:
        raise ConfigError("BOT_START_BALANCE must be 50-100 USD (CLAUDE.md)")
    home = Path(get("BOT_HOME", str(REPO_ROOT / "state" / "live")))
    return LiveSettings(
        base=base,
        strategy_id=get("STRATEGY_ID", "") or "",
        leader_fallback=get("LEADER_FALLBACK", "f1_london_breakout_r5"),
        confirm_real=(get("CONFIRM_REAL", "") or "").lower() == "yes",
        start_balance=start,
        home=home,
        cost_sampling=_parse_bool("COST_SAMPLING", get("COST_SAMPLING", "true")),
    )
