"""Settings loader.

Reads each setting from the environment first, then from a .env file if one
exists, so the same code works in cloud sessions (environment variables) and
on the VPS (.env file). Secrets are never shown in repr() or summaries.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = REPO_ROOT / ".env"

VALID_MODES = ("demo", "real")
_TRUE = {"true", "1", "yes", "on"}
_FALSE = {"false", "0", "no", "off", ""}


class ConfigError(ValueError):
    """A setting has a value the bot does not accept."""


@dataclass(frozen=True)
class Settings:
    deriv_app_id: str | None
    deriv_pat: str | None = field(repr=False)
    deriv_account_id: str | None
    deriv_mode: str
    telegram_bot_token: str | None = field(repr=False)
    telegram_chat_id: str | None
    trading_enabled: bool

    def summary(self) -> dict[str, str]:
        """Safe-to-print view: secrets only show as set or missing."""

        def state(value: str | None) -> str:
            return "set" if value else "missing"

        return {
            "DERIV_APP_ID": state(self.deriv_app_id),
            "DERIV_PAT": state(self.deriv_pat),
            "DERIV_ACCOUNT_ID": state(self.deriv_account_id),
            "DERIV_MODE": self.deriv_mode,
            "TELEGRAM_BOT_TOKEN": state(self.telegram_bot_token),
            "TELEGRAM_CHAT_ID": state(self.telegram_chat_id),
            "TRADING_ENABLED": str(self.trading_enabled).lower(),
        }


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse KEY=VALUE lines. Blank lines and # comments are skipped."""
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key] = value
    return values


def _parse_bool(name: str, value: str | None) -> bool:
    text = (value or "").strip().lower()
    if text in _TRUE:
        return True
    if text in _FALSE:
        return False
    raise ConfigError(f"{name} must be true or false")


def load_settings(
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = DEFAULT_ENV_FILE,
) -> Settings:
    """Load settings. Environment variables win over the .env file.

    An empty environment variable counts as unset, so the .env value is used.
    Missing DERIV_MODE means demo; missing TRADING_ENABLED means false.
    """
    environ = os.environ if environ is None else environ
    file_values = parse_env_file(env_file) if env_file else {}

    def get(name: str) -> str | None:
        value = environ.get(name)
        if value is None or value.strip() == "":
            value = file_values.get(name)
        if value is None or value.strip() == "":
            return None
        return value.strip()

    mode = (get("DERIV_MODE") or "demo").lower()
    if mode not in VALID_MODES:
        raise ConfigError("DERIV_MODE must be demo or real")

    return Settings(
        deriv_app_id=get("DERIV_APP_ID"),
        deriv_pat=get("DERIV_PAT"),
        deriv_account_id=get("DERIV_ACCOUNT_ID"),
        deriv_mode=mode,
        telegram_bot_token=get("TELEGRAM_BOT_TOKEN"),
        telegram_chat_id=get("TELEGRAM_CHAT_ID"),
        trading_enabled=_parse_bool("TRADING_ENABLED", get("TRADING_ENABLED")),
    )
