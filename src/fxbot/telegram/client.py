"""Minimal Telegram Bot API client (standard library only).

The token is part of every URL, so errors report only the HTTP status and
Telegram's description, never the URL.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
import uuid

LIMIT = 4000


class TelegramError(RuntimeError):
    pass


def chunks(text: str, limit: int = LIMIT) -> list[str]:
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > limit and cur:
            out.append(cur)
            cur = ""
        cur += line[:limit]
    if cur:
        out.append(cur)
    return out or [""]


class TelegramClient:
    def __init__(self, token: str, chat_id: str):
        if not token or not chat_id:
            raise TelegramError("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID are required")
        self._token = token
        self.chat_id = str(chat_id)

    def _call(self, method: str, data: bytes | None = None, headers: dict | None = None,
              timeout: float = 20.0) -> dict:
        url = f"https://api.telegram.org/bot{self._token}/{method}"
        req = urllib.request.Request(url, data=data, headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                body = json.loads(r.read().decode())
        except urllib.error.HTTPError as err:
            try:
                desc = json.loads(err.read().decode()).get("description", "")
            except Exception:
                desc = ""
            raise TelegramError(f"HTTP {err.code} {desc}") from None
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            raise TelegramError(f"unreachable: {type(err).__name__}") from None
        if not body.get("ok"):
            raise TelegramError(body.get("description", "not ok"))
        return body

    def send(self, text: str) -> None:
        for part in chunks(text):
            data = urllib.parse.urlencode({"chat_id": self.chat_id, "text": part,
                                           "disable_web_page_preview": "true"}).encode()
            self._call("sendMessage", data)

    def send_document(self, filename: str, content: bytes, caption: str = "") -> None:
        boundary = uuid.uuid4().hex
        parts = []
        for k, v in (("chat_id", self.chat_id), ("caption", caption)):
            parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
        parts.append((f'--{boundary}\r\nContent-Disposition: form-data; name="document"; filename="{filename}"\r\n'
                      f"Content-Type: text/csv\r\n\r\n").encode() + content + b"\r\n")
        parts.append(f"--{boundary}--\r\n".encode())
        self._call("sendDocument", b"".join(parts),
                   {"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=60)

    def updates(self, offset: int | None, timeout: int = 25) -> list[dict]:
        q = {"timeout": timeout, "allowed_updates": json.dumps(["message"])}
        if offset is not None:
            q["offset"] = offset
        return self._call("getUpdates?" + urllib.parse.urlencode(q), timeout=timeout + 10)["result"]
