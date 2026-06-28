"""trading/alerts/ — Alerts + Automation (Phase T7, Telegram-only).

Pushes trading events to Telegram and exposes Telegram commands (/positions /pnl
/kill) back into the engine. Secrets-safe and offline-first: the core (events, dedup,
dispatch, formatting) is pure and unit-testable with an INJECTED transport, so tests
and the demo run with NO network and NO credentials. Real delivery turns on only when
TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID are present in `.env`; until then the channel
runs in dry-run and records what it WOULD have sent.

Minimal deps: sending is a plain Telegram Bot API HTTP POST (requests); only the live
command bot uses python-telegram-bot.

Pieces (blueprint §T7):
  events      — AlertEvent + builders (fill / daily P&L / signal / circuit-breaker / kill)
  dedup       — smart TTL + content-hash deduplication (no repeat alerts)
  config      — AlertConfig from env; honest enabled flag; secrets redacted
  channels    — TelegramChannel (injected transport, dry-run aware)
  formatter   — render an AlertEvent to Telegram markdown
  dispatcher  — route events to Telegram through the deduper; honest status()
  commands    — /positions /pnl /kill handlers wired to injected callables
  scheduler   — daily/weekly scheduled reports (deterministic, offline-testable)
  bot         — live python-telegram-bot runner (guarded import; live use only)
"""
from __future__ import annotations

from trading.alerts.channels import TelegramChannel
from trading.alerts.commands import CommandRouter
from trading.alerts.config import AlertConfig, alert_config
from trading.alerts.dedup import Deduplicator
from trading.alerts.dispatcher import AlertDispatcher
from trading.alerts.events import (
    AlertEvent,
    circuit_breaker_event,
    daily_pnl_event,
    fill_event,
    kill_event,
    signal_event,
)
from trading.alerts.formatter import to_telegram_markdown
from trading.alerts.scheduler import ReportScheduler

__all__ = [
    "AlertEvent", "fill_event", "daily_pnl_event", "signal_event",
    "circuit_breaker_event", "kill_event",
    "Deduplicator",
    "AlertConfig", "alert_config",
    "TelegramChannel",
    "to_telegram_markdown",
    "AlertDispatcher",
    "CommandRouter",
    "ReportScheduler",
]
