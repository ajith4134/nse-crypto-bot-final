"""trading/alerts/bot.py — live Telegram command bot (T7 §1).

Wires a CommandRouter to python-telegram-bot so /positions /pnl /kill /status /help
work in the chat. This is the ONLY live-network piece; it is import-guarded so the rest
of trading.alerts stays usable without python-telegram-bot installed, and it is never
exercised by the offline tests (which drive CommandRouter directly).

Usage (live, requires TELEGRAM_BOT_TOKEN in .env):
    from trading.alerts.bot import run_bot
    run_bot(router, config)          # blocks, long-polling
"""
from __future__ import annotations

from trading.alerts.commands import CommandRouter
from trading.alerts.config import AlertConfig, alert_config


def build_application(router: CommandRouter, config: AlertConfig | None = None):
    """Build (but do not run) a python-telegram-bot Application with the handlers."""
    cfg = config or alert_config
    if not cfg.telegram_bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN absent — cannot start the Telegram bot.")
    try:
        from telegram.ext import Application, CommandHandler
    except ImportError as exc:  # pragma: no cover - env-dependent
        raise RuntimeError(
            "python-telegram-bot is not installed. Run:\n"
            "    .venv/bin/pip install python-telegram-bot"
        ) from exc

    app = Application.builder().token(cfg.telegram_bot_token).build()

    def _make_handler(cmd: str):
        async def _h(update, context):  # noqa: ANN001
            args = " ".join(context.args) if getattr(context, "args", None) else ""
            reply = router.handle(cmd, args)
            await update.message.reply_text(reply, parse_mode="Markdown")
        return _h

    for cmd in ("positions", "pnl", "kill", "status", "help"):
        app.add_handler(CommandHandler(cmd, _make_handler(f"/{cmd}")))
    return app


def run_bot(router: CommandRouter, config: AlertConfig | None = None) -> None:  # pragma: no cover
    """Blocking long-poll runner for live use."""
    app = build_application(router, config)
    app.run_polling()
