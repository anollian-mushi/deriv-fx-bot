"""Telegram messages for the incubator (GitHub Secrets TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID).

Settings come from environment variables first, then .env (fxbot.config).
The token is never printed or logged.
"""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.parse
import urllib.request

from fxbot.config import load_settings

LIMIT = 4000        # Telegram allows 4096 characters per message


class NotifyError(RuntimeError):
    pass


def _chunks(text: str, limit: int = LIMIT) -> list[str]:
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > limit and cur:
            out.append(cur)
            cur = ""
        cur += line[:limit]
    if cur:
        out.append(cur)
    return out or [""]


def send(text: str, pre: bool = False, timeout: float = 20.0) -> None:
    """Send `text` (plain text; pre=True shows it in monospace). Raises NotifyError on failure."""
    s = load_settings()
    if not s.telegram_bot_token or not s.telegram_chat_id:
        raise NotifyError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are not set")
    url = f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage"
    for part in _chunks(text):
        body = f"<pre>{html.escape(part)}</pre>" if pre else html.escape(part)
        data = urllib.parse.urlencode({"chat_id": s.telegram_chat_id, "text": body, "parse_mode": "HTML",
                                       "disable_web_page_preview": "true"}).encode()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=timeout) as r:
                ok = json.loads(r.read().decode()).get("ok")
        except urllib.error.HTTPError as err:
            # The URL holds the token: report only the status and Telegram's description.
            try:
                desc = json.loads(err.read().decode()).get("description", "")
            except Exception:
                desc = ""
            raise NotifyError(f"Telegram refused the message: HTTP {err.code} {desc}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise NotifyError(f"Telegram unreachable: {type(err).__name__}") from None
        if not ok:
            raise NotifyError("Telegram did not accept the message")
