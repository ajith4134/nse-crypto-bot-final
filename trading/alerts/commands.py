"""trading/alerts/commands.py — Telegram command router (T7 §1).

Implements /positions /pnl /kill (and /help, /status) as pure functions of INJECTED
callables, so the same router is unit-tested offline and driven live by bot.py:

    positions_fn() -> list[dict] | dict     (open positions snapshot)
    pnl_fn()       -> dict                   (e.g. journal analytics / daily P&L)
    kill_fn(reason)-> dict                   (engages the kill switch; returns report)

`handle(command, args)` returns the Telegram-ready Markdown reply string. No network.
"""
from __future__ import annotations

from typing import Callable


def _fmt_positions(positions) -> str:
    rows = positions.get("positions", positions) if isinstance(positions, dict) else positions
    rows = rows or []
    if not rows:
        return "*Positions*\nNo open positions."
    out = ["*Open Positions*"]
    for p in rows:
        sym = p.get("symbol", "?")
        side = p.get("side", p.get("direction", ""))
        qty = p.get("open_qty", p.get("size", p.get("quantity", "")))
        entry = p.get("entry_price", "")
        out.append(f"• {sym} {side} {qty} @ {entry}")
    return "\n".join(out)


def _fmt_pnl(pnl: dict) -> str:
    a = pnl.get("analytics", pnl) if isinstance(pnl, dict) else {}
    net = a.get("net_pnl")
    wr = a.get("win_rate")
    pf = a.get("profit_factor")
    n = a.get("total", a.get("n_trades"))
    return ("*P&L*\n"
            f"• net: {net if net is not None else '—'}\n"
            f"• trades: {n if n is not None else '—'}\n"
            f"• win rate: {wr if wr is not None else '—'}%\n"
            f"• profit factor: {pf if pf is not None else '—'}")


class CommandRouter:
    def __init__(self, *, positions_fn: Callable[[], object] | None = None,
                 pnl_fn: Callable[[], dict] | None = None,
                 kill_fn: Callable[[str], dict] | None = None):
        self.positions_fn = positions_fn
        self.pnl_fn = pnl_fn
        self.kill_fn = kill_fn

    COMMANDS = ("/positions", "/pnl", "/kill", "/status", "/help")

    def handle(self, command: str, args: str = "") -> str:
        cmd = command.strip().split("@", 1)[0].lower()   # strip @botname suffix
        try:
            if cmd == "/positions":
                if not self.positions_fn:
                    return "positions unavailable (not wired)"
                return _fmt_positions(self.positions_fn())
            if cmd == "/pnl":
                if not self.pnl_fn:
                    return "pnl unavailable (not wired)"
                return _fmt_pnl(self.pnl_fn())
            if cmd == "/kill":
                if not self.kill_fn:
                    return "kill switch unavailable (not wired)"
                rep = self.kill_fn(args or "telegram /kill")
                ok = rep.get("ok") if isinstance(rep, dict) else None
                return f"🛑 *KILL ENGAGED*\n• ok: {ok}\n• detail: {rep}"
            if cmd == "/help":
                return "*Commands*\n" + "\n".join(f"• {c}" for c in self.COMMANDS)
            if cmd == "/status":
                return "*Status*\nbot online · commands: " + ", ".join(self.COMMANDS)
        except Exception as exc:
            return f"command error: {type(exc).__name__}: {exc}"
        return f"unknown command {cmd} — try /help"
