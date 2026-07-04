"""trading/online/controls.py — shared, persisted control surface (O5).

ONE source of truth for the live trading bot's controls, used by BOTH the dashboard
(`dashboard/server.py` POST /api/trading/online/control) AND Telegram (`/start_crypto`,
`/balance NSE 5000`, …). Every mutation goes through here, lands on a PERSISTED
`MarketRegistry` (per-market enable/mode/allow_live/trading_state → online_markets.json)
and a PERSISTED `PaperWalletBook` (editable paper money per market+portfolio), so a change
made from the dashboard is instantly visible to Telegram and survives a restart.

Controls map (NautilusTrader trading-state model + safe paper-first defaults):
    start  → enable + ACTIVE          stop  → disable (no new activity)
    pause  → REDUCING (graceful)      halt  → HALTED (kill-switch)
    mode   → PAPER | REAL  (REAL needs allow_live AND confirm=True — deliberate 2-step)
    set_balance / top_up / reset_wallet → editable virtual money
    panic  → halt ALL markets (best-effort note)
    status → JSON-able {markets, wallets} combining registry + walletbook

start/stop/pause/halt are MODE-INDEPENDENT (work the same in paper and real); switching
PAPER↔REAL is a separate, guarded action. Secrets-free, offline-safe (no network here).
"""
from __future__ import annotations

from trading.online.state import MarketRegistry, TradingState
from trading.online.wallet import PaperWalletBook

# ── module-level singletons (lazy) so dashboard + Telegram share ONE persisted state ──
_REGISTRY: MarketRegistry | None = None
_BOOK: PaperWalletBook | None = None
_NOTE: str = ""


def registry() -> MarketRegistry:
    """The shared, persisted per-market registry (lazy singleton)."""
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = MarketRegistry(persist=True)
    return _REGISTRY


def book() -> PaperWalletBook:
    """The shared, persisted paper-wallet book (lazy singleton)."""
    global _BOOK
    if _BOOK is None:
        _BOOK = PaperWalletBook(persist=True)
    return _BOOK


def reset_singletons(*, persist: bool = True) -> None:
    """Drop the cached singletons (used by tests / offline demos to start clean)."""
    global _REGISTRY, _BOOK
    _REGISTRY = MarketRegistry(persist=persist)
    _BOOK = PaperWalletBook(persist=persist)


def _ms_dict(market: str) -> dict:
    return registry().get(market).as_dict()


# ── per-market run controls (the Start/Stop/Pause/Halt buttons) ───────────────────────
def start(market: str) -> dict:
    """Start = enable + ACTIVE. Works in BOTH paper and real."""
    ms = registry().get(market)
    ms.enable().set_state(TradingState.ACTIVE)
    registry().save()
    return _ms_dict(market)


def stop(market: str) -> dict:
    """Stop = disable (no new activity)."""
    registry().get(market).disable()
    registry().save()
    return _ms_dict(market)


def pause(market: str) -> dict:
    """Pause = REDUCING (only position-reducing orders allowed — graceful de-risk)."""
    registry().get(market).set_state(TradingState.REDUCING)
    registry().save()
    return _ms_dict(market)


def halt(market: str) -> dict:
    """Halt = HALTED (kill-switch — deny everything except cancels)."""
    registry().get(market).set_state(TradingState.HALTED)
    registry().save()
    return _ms_dict(market)


# ── mode + live-trading guard ─────────────────────────────────────────────────────────
def set_mode(market: str, mode: str, *, confirm: bool = False) -> dict:
    """Switch PAPER↔REAL. REAL requires allow_live AND confirm=True (deliberate 2-step)."""
    res = registry().get(market).set_mode(mode, confirm=confirm)
    registry().save()
    res["state"] = _ms_dict(market)
    return res


def set_allow_live(market: str, allow: bool) -> dict:
    """Arm/disarm real trading for a market (must be armed before any REAL switch)."""
    registry().get(market).allow_live = bool(allow)
    registry().save()
    return _ms_dict(market)


# ── trade-type segment selection (only selected segments are traded) ─────────────────
def set_segments(market: str, segments: list) -> dict:
    """Set the selected trade-types for a market (NSE: intraday/mtf/fno/commodities;
    CRYPTO: spot/futures/options). Only selected segments get traded."""
    registry().get(market).set_segments(list(segments or []))
    registry().save()
    return _ms_dict(market)


def toggle_segment(market: str, segment: str) -> dict:
    """Toggle one trade-type on/off for a market."""
    registry().get(market).toggle_segment(str(segment))
    registry().save()
    return _ms_dict(market)


# ── editable paper money ──────────────────────────────────────────────────────────────
def _flush_loop_positions(market: str) -> None:
    """Keep the live loop's in-memory open map in sync with a wallet wipe — without this the
    loop still sees the cleared positions as open (in_position=True) and never re-opens
    anything (observed 2026-07-02)."""
    try:
        from trading.online.live_loop import get_loop
        get_loop().flush_market(market)
    except Exception:
        pass


def set_balance(market: str, amount: float, portfolio_id: str = "default") -> dict:
    """Clean-reset the paper wallet to a NEW starting capital (clears positions/PnL)."""
    out = book().wallet(market, portfolio_id).set_starting_capital(float(amount)).summary()
    _flush_loop_positions(market)
    return out


def top_up(market: str, amount: float, portfolio_id: str = "default") -> dict:
    """Add paper cash (deposit), keeping positions and PnL."""
    return book().wallet(market, portfolio_id).top_up(float(amount)).summary()


def reset_wallet(market: str, portfolio_id: str = "default") -> dict:
    """Reset the paper wallet back to its starting capital, flat."""
    out = book().wallet(market, portfolio_id).reset().summary()
    _flush_loop_positions(market)
    return out


# ── panic + status ────────────────────────────────────────────────────────────────────
def panic(note: str = "panic: halt all markets") -> dict:
    """Halt EVERY market at once (the big red button) + record a best-effort note."""
    global _NOTE
    registry().halt_all()
    _NOTE = note
    return status()


def status() -> dict:
    """JSON-able snapshot combining the persisted registry + walletbook (+ note)."""
    return {**registry().status(), **book().status(), "note": _NOTE}


# ══════════════════════════════════════════════════════════════════════════════════════
# Telegram command surface — the SAME controls, exposed as chat commands.
# ══════════════════════════════════════════════════════════════════════════════════════
_KNOWN_MARKETS = ("CRYPTO", "NSE")


def _fmt_state(d: dict) -> str:
    return (f"{d['market']}: enabled={d['enabled']} mode={d['mode']} "
            f"state={d['trading_state']} allow_live={d['allow_live']}")


def _fmt_status() -> str:
    st = status()
    lines = ["*Online status*"]
    for m, d in st["markets"].items():
        lines.append("• " + _fmt_state(d))
    for w in st["wallets"]:
        lines.append(f"• {w['market']} wallet [{w['portfolio_id']}]: "
                     f"cash={w['cash']:.2f} {w['currency']} equity={w['equity']:.2f}")
    if st.get("note"):
        lines.append(f"_note: {st['note']}_")
    return "\n".join(lines)


def _cmd_balance(args: str) -> str:
    """/balance <market> <amount> — set paper starting capital."""
    parts = (args or "").split()
    if len(parts) < 2:
        return "usage: /balance <market> <amount>"
    market, amount = parts[0], parts[1]
    try:
        w = set_balance(market, float(amount))
    except ValueError:
        return f"bad amount {amount!r}"
    return f"{w['market']} paper balance set → {w['cash']:.2f} {w['currency']}"


def build_online_command_router() -> dict:
    """Return a {command: callable(args)->str} map the T7 bot can register.

    Per-market verbs are pre-bound (`/start_crypto`, `/stop_nse`, `/pause_crypto`,
    `/halt_nse`) alongside the global `/halt` (panic), `/balance <m> <amt>` and
    `/online_status`. Each callable returns a Telegram-ready text summary. Offline-safe.
    """
    cmds: dict = {}

    def _bind(fn, market):
        return lambda args="": _fmt_state(fn(market))

    for m in _KNOWN_MARKETS:
        low = m.lower()
        cmds[f"/start_{low}"] = _bind(start, m)
        cmds[f"/stop_{low}"] = _bind(stop, m)
        cmds[f"/pause_{low}"] = _bind(pause, m)
        cmds[f"/halt_{low}"] = _bind(halt, m)
    def _panic(args=""):
        panic()
        return f"PANIC — all markets halted.\n{_fmt_status()}"

    cmds["/halt"] = _panic
    cmds["/balance"] = _cmd_balance
    cmds["/online_status"] = lambda args="": _fmt_status()
    return cmds


def handle_command(command: str, args: str = "") -> str:
    """Dispatch one Telegram command string through the shared control surface."""
    cmd = command.strip().split("@", 1)[0].lower()
    router = build_online_command_router()
    fn = router.get(cmd)
    if fn is None:
        return f"unknown command {cmd} — try /online_status"
    try:
        return fn(args)
    except Exception as exc:  # offline-safe: never raise into the bot loop
        return f"command error: {type(exc).__name__}: {exc}"
