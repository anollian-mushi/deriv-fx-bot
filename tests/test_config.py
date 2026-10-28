from pathlib import Path

import pytest

from fxbot.config import ConfigError, load_settings, parse_env_file


def write_env(tmp_path: Path, text: str) -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_are_safe_when_nothing_is_set(tmp_path):
    s = load_settings(environ={}, env_file=tmp_path / "missing.env")
    assert s.deriv_mode == "demo"
    assert s.trading_enabled is False
    assert s.deriv_pat is None
    assert s.deriv_account_id is None


def test_environment_wins_over_env_file(tmp_path):
    env_file = write_env(tmp_path, "DERIV_APP_ID=from_file\nDERIV_PAT=file_pat\n")
    s = load_settings(environ={"DERIV_APP_ID": "from_env"}, env_file=env_file)
    assert s.deriv_app_id == "from_env"
    assert s.deriv_pat == "file_pat"


def test_empty_environment_value_falls_back_to_env_file(tmp_path):
    env_file = write_env(tmp_path, "DERIV_APP_ID=from_file\n")
    s = load_settings(environ={"DERIV_APP_ID": "  "}, env_file=env_file)
    assert s.deriv_app_id == "from_file"


def test_env_file_parsing(tmp_path):
    env_file = write_env(
        tmp_path,
        "# comment\n\nexport DERIV_MODE=demo\nTELEGRAM_CHAT_ID=\"123\"\nBAD LINE\nX='a=b'\n",
    )
    assert parse_env_file(env_file) == {"DERIV_MODE": "demo", "TELEGRAM_CHAT_ID": "123", "X": "a=b"}


@pytest.mark.parametrize("value,expected", [("true", True), ("TRUE", True), ("1", True),
                                            ("false", False), ("0", False), ("", False)])
def test_trading_enabled_parsing(value, expected):
    s = load_settings(environ={"TRADING_ENABLED": value}, env_file=None)
    assert s.trading_enabled is expected


def test_trading_enabled_rejects_unclear_values():
    with pytest.raises(ConfigError):
        load_settings(environ={"TRADING_ENABLED": "maybe"}, env_file=None)


def test_mode_must_be_demo_or_real():
    assert load_settings(environ={"DERIV_MODE": "REAL"}, env_file=None).deriv_mode == "real"
    with pytest.raises(ConfigError):
        load_settings(environ={"DERIV_MODE": "live"}, env_file=None)


def test_secrets_never_appear_in_repr_or_summary():
    s = load_settings(
        environ={"DERIV_PAT": "pat-secret-value", "TELEGRAM_BOT_TOKEN": "tg-secret-value"},
        env_file=None,
    )
    text = repr(s) + str(s.summary())
    assert "pat-secret-value" not in text
    assert "tg-secret-value" not in text
    assert s.summary()["DERIV_PAT"] == "set"
