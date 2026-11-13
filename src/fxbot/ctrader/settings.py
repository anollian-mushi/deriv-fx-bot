"""cTrader settings: environment variables first, then the .env file (same rules as fxbot.config).

CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET: the Open API application's credentials.
CTRADER_ACCESS_TOKEN: an OAuth access token for the cTID that owns the account.
CTRADER_ACCOUNT_ID: the ctidTraderAccountId (not the login number shown in cTrader).
CTRADER_MODE: demo (default). real is refused in this version.

The secret and the token never appear in repr() or summary().
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from fxbot.config import DEFAULT_ENV_FILE, ConfigError, parse_env_file

DEMO_HOST = "demo.ctraderapi.com"
LIVE_HOST = "live.ctraderapi.com"     # never used in this version; listed so the refusal is explicit
PROTOBUF_PORT = 5035                  # 5036 is the JSON port; this client speaks Protobuf
NAMES = ("CTRADER_CLIENT_ID", "CTRADER_CLIENT_SECRET", "CTRADER_ACCESS_TOKEN", "CTRADER_ACCOUNT_ID",
         "CTRADER_MODE")


@dataclass(frozen=True)
class CTraderSettings:
    client_id: str | None
    client_secret: str | None = field(repr=False)
    access_token: str | None = field(repr=False)
    account_id: int | None
    mode: str = "demo"

    @property
    def host(self) -> str:
        if self.mode != "demo":
            raise ConfigError("CTRADER_MODE=real is not implemented; only demo accounts are supported")
        return DEMO_HOST

    @property
    def port(self) -> int:
        return PROTOBUF_PORT

    def missing(self) -> list[str]:
        """Names of the settings needed to log in that are not set (CTRADER_ACCOUNT_ID is optional:
        without it the first demo account of the token is used)."""
        out = []
        if not self.client_id:
            out.append("CTRADER_CLIENT_ID")
        if not self.client_secret:
            out.append("CTRADER_CLIENT_SECRET")
        if not self.access_token:
            out.append("CTRADER_ACCESS_TOKEN")
        return out

    def summary(self) -> dict[str, str]:
        def state(v) -> str:
            return "set" if v else "missing"
        return {
            "CTRADER_CLIENT_ID": state(self.client_id),
            "CTRADER_CLIENT_SECRET": state(self.client_secret),
            "CTRADER_ACCESS_TOKEN": state(self.access_token),
            "CTRADER_ACCOUNT_ID": mask_id(self.account_id) if self.account_id else "missing",
            "CTRADER_MODE": self.mode,
        }


def mask_id(value) -> str:
    """Account id for printing: only the last 3 digits shown."""
    text = str(value)
    return "*" * max(0, len(text) - 3) + text[-3:]


def load_ctrader_settings(environ: Mapping[str, str] | None = None,
                          env_file: Path | None = DEFAULT_ENV_FILE) -> CTraderSettings:
    environ = os.environ if environ is None else environ
    file_values = parse_env_file(env_file) if env_file else {}

    def get(name: str) -> str | None:
        value = environ.get(name)
        if value is None or value.strip() == "":
            value = file_values.get(name)
        if value is None or value.strip() == "":
            return None
        return value.strip()

    mode = (get("CTRADER_MODE") or "demo").lower()
    if mode == "real":
        raise ConfigError("CTRADER_MODE=real is not implemented in this version; use demo")
    if mode != "demo":
        raise ConfigError("CTRADER_MODE must be demo")
    raw_id = get("CTRADER_ACCOUNT_ID")
    account_id = None
    if raw_id is not None:
        if not raw_id.isdigit():
            raise ConfigError("CTRADER_ACCOUNT_ID must be the numeric ctidTraderAccountId")
        account_id = int(raw_id)
    return CTraderSettings(
        client_id=get("CTRADER_CLIENT_ID"),
        client_secret=get("CTRADER_CLIENT_SECRET"),
        access_token=get("CTRADER_ACCESS_TOKEN"),
        account_id=account_id,
        mode=mode,
    )
