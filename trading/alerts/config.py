"""trading/alerts/config.py — Telegram alert configuration (T7).

Reads credentials from the environment (populated from the gitignored `.env` by the
project's dotenv loader). NEVER hard-codes secrets and NEVER exposes the raw token in
status — `as_status()` reports only presence + a redacted hint. When the token/chat-id
are absent the channel is `enabled=False` and the whole alert pipeline runs in dry-run.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _redact(secret: str | None) -> str:
    if not secret:
        return "—"
    if len(secret) <= 8:
        return "****"
    return f"{secret[:4]}…{secret[-4:]}"


@dataclass(frozen=True)
class AlertConfig:
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    @classmethod
    def from_env(cls, env: dict | None = None) -> "AlertConfig":
        e = env if env is not None else os.environ
        return cls(
            telegram_bot_token=(e.get("TELEGRAM_BOT_TOKEN") or None),
            telegram_chat_id=(e.get("TELEGRAM_CHAT_ID") or None),
        )

    @property
    def telegram_enabled(self) -> bool:
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    def as_status(self) -> dict:
        """Honest, secrets-safe status — never the raw token."""
        return {
            "telegram_enabled": self.telegram_enabled,
            "telegram_chat_id": self.telegram_chat_id or "—",
            "telegram_token": _redact(self.telegram_bot_token),
            "mode": "live" if self.telegram_enabled else "dry-run (no credentials)",
        }


# Module-level singleton (re-read with AlertConfig.from_env() after a dotenv load).
alert_config = AlertConfig.from_env()
