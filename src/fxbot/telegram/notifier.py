"""Outgoing Telegram alerts, sent from a background thread so trading never waits on Telegram.

Every message is written to the journal (events, kind "telegram") with its
category, whether or not Telegram accepted it, so the record of alerts is
complete even when Telegram is down.
"""

from __future__ import annotations

import logging
import queue
import threading
import time

log = logging.getLogger(__name__)


class Notifier:
    def __init__(self, client, journal, prefix: str = "", retries: int = 3, retry_wait: float = 5.0):
        self.client, self.journal, self.prefix = client, journal, prefix
        self.retries, self.retry_wait = retries, retry_wait
        self.q: queue.Queue = queue.Queue()
        self._thread = threading.Thread(target=self._work, name="telegram-send", daemon=True)
        self._thread.start()

    def send(self, text: str, category: str = "info") -> None:
        text = f"{self.prefix}{text}" if self.prefix else text
        self.journal.event("telegram", category=category, text=text)
        self.q.put((text, category))

    def document(self, filename: str, content: bytes, caption: str = "") -> None:
        self.journal.event("telegram", category="document", text=f"{filename}: {caption}")
        self.q.put((("doc", filename, content, caption), "document"))

    def flush(self, timeout: float = 15.0) -> None:
        end = time.time() + timeout
        while not self.q.empty() and time.time() < end:
            time.sleep(0.1)
        time.sleep(0.2)

    def _work(self) -> None:
        while True:
            item, category = self.q.get()
            if self.client is None:
                continue
            for attempt in range(self.retries):
                try:
                    if isinstance(item, tuple):
                        _, name, content, caption = item
                        self.client.send_document(name, content, caption)
                    else:
                        self.client.send(item)
                    break
                except Exception as err:      # TelegramError, network
                    log.warning("Telegram send failed (%s), attempt %d", err, attempt + 1)
                    if attempt == self.retries - 1:
                        self.journal.event("telegram_failed", category=category, error=str(err))
                    else:
                        time.sleep(self.retry_wait)
