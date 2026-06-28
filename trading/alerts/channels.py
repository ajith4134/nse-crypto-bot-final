"""trading/alerts/channels.py — TelegramChannel (T7 §1).

Sends an AlertEvent to Telegram via the Bot API `sendMessage` endpoint. The HTTP
transport is INJECTED (`transport(url, json) -> dict`), so tests run fully offline with
a fake transport and assert on the captured payloads. With no transport supplied it
lazily uses `requests`. When credentials are absent (config.telegram_enabled False) the
channel is in DRY-RUN: it formats the message and records it but performs no network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from trading.alerts.config import AlertConfig, alert_config
from trading.alerts.formatter import to_telegram_markdown


def _requests_transport(url: str, payload: dict) -> dict:
    import requests  # lazy: keeps the module importable without the dep at import time
    resp = requests.post(url, json=payload, timeout=10)
    try:
        data = resp.json()
    except Exception:
        data = {"ok": False, "status_code": resp.status_code, "text": resp.text[:200]}
    return data


@dataclass
class TelegramChannel:
    name: str = "telegram"
    config: AlertConfig = field(default_factory=lambda: alert_config)
    transport: Callable[[str, dict], dict] | None = None
    parse_mode: str = "Markdown"
    sent_log: list = field(default_factory=list, init=False)

    def enabled(self) -> bool:
        return self.config.telegram_enabled

    @property
    def _api_url(self) -> str:
        return f"https://api.telegram.org/bot{self.config.telegram_bot_token}/sendMessage"

    def send(self, event) -> dict:
        """Deliver one event. Returns {ok, dry_run, detail}. Never raises on transport."""
        text = to_telegram_markdown(event)
        record = {"dedup_key": getattr(event, "dedup_key", ""), "text": text}
        if not self.enabled():
            record.update(dry_run=True, ok=True, detail="dry-run: no Telegram credentials")
            self.sent_log.append(record)
            return record
        payload = {"chat_id": self.config.telegram_chat_id, "text": text,
                   "parse_mode": self.parse_mode, "disable_web_page_preview": True}
        send = self.transport or _requests_transport
        try:
            resp = send(self._api_url, payload)
            ok = bool(resp.get("ok")) if isinstance(resp, dict) else False
            record.update(dry_run=False, ok=ok, detail=resp if not ok else "sent")
        except Exception as exc:        # transport failure must not crash the engine
            record.update(dry_run=False, ok=False, detail=f"{type(exc).__name__}: {exc}")
        self.sent_log.append(record)
        return record

    def as_dict(self) -> dict:
        return {"name": self.name, "enabled": self.enabled(),
                "sent_count": len(self.sent_log)}
