"""trading/alerts/formatter.py — render an AlertEvent to Telegram markdown (T7).

Telegram "MarkdownV2" is picky about escaping; we use the simpler legacy "Markdown"
parse mode and keep formatting conservative (bold title + key/value lines) so messages
never fail to parse. Pure string building — no I/O.
"""
from __future__ import annotations

_SEV_ICON = {"info": "ℹ️", "warn": "⚠️", "critical": "🛑"}


def _fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:,.2f}"
    if isinstance(v, bool):
        return "yes" if v else "no"
    return str(v)


def to_telegram_markdown(event) -> str:
    """A compact Telegram message: icon + bold title, body, then field lines."""
    icon = _SEV_ICON.get(getattr(event, "severity", "info"), "•")
    lines = [f"{icon} *{event.title}*"]
    if getattr(event, "body", ""):
        lines.append(event.body)
    fields = getattr(event, "fields", {}) or {}
    for k, v in fields.items():
        if v in (None, "", []):
            continue
        label = str(k).replace("_", " ")
        lines.append(f"• {label}: {_fmt_value(v)}")
    return "\n".join(lines)
