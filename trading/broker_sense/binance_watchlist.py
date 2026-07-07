"""trading/broker_sense/binance_watchlist.py — mirror OPEN crypto trades into the REAL
Binance web app's ⭐ Favorites (add on open, remove on close).

Owner ask 2026-07-07: "same as Upstox has the Brain-Open watchlist, Binance has the
Favorites feature — when the brain opens a trade add the symbol to Favorites, when it
closes remove it, for all segments that are selected." The crypto twin of
[[account_watchlist]] (Upstox): open Binance and SEE the brain's open positions starred.

Scope (honest): Binance Favorites can only hold Binance-listed symbols, so the mirror
covers the futures + spot segments (options = Deribit, prediction = Polymarket — their
symbols don't exist on Binance and are skipped with a note). Segment selection obeys
boss.active_segments("CRYPTO") — the owner's Segment-Focus switches gate this mirror
exactly like they gate entries.

Write path = the human-UI eyes→hand (HumanUI) on the logged-in Binance web session: the
⭐ star toggle on each symbol's own futures/spot page. Idempotent — the eyes READ the
star state first and only click when it differs (a favorites star is an organize-only
control; the order-guard still forbids Buy/Sell clicks). Same gates + honesty rules as
the Upstox mirror:

  • Gated behind BROKER_WATCHLIST_WRITE=1 (writes to the real account UI — never orders).
  • Never fakes success: star state is re-read after the click; only a confirmed toggle
    updates the synced set, so a partial run stays truthful.

State persists in trading/state (account_watchlist_binance.json) so the diff survives
restarts and the dashboard shows the last sync honestly.
"""
from __future__ import annotations

import os
import re
import time

from trading import state
from trading.broker_sense.account_watchlist import plan_sync  # pure diff — reuse, don't copy

_STATE_FILE = "account_watchlist_binance.json"
# Binance-app-mirrorable segments; options (Deribit) / prediction (Polymarket) symbols
# don't exist on Binance and are skipped honestly.
_BINANCE_SEGMENTS = ("futures", "spot")


# ── open-trades source (the mirror truth) ────────────────────────────────────
def _flat(pair: str) -> str:
    """Freqtrade pair → the Binance app token: 'BEL/USDT:USDT' → 'BELUSDT'."""
    base = (pair or "").split(":", 1)[0]
    return re.sub(r"[^A-Z0-9]", "", base.upper())


def open_crypto_symbols() -> dict:
    """{binance_symbol: {pair, segment}} for currently-OPEN crypto trades across the
    ACTIVE Binance-mirrorable segments (boss Segment-Focus gate). Best-effort per
    segment: a down engine degrades to 'no change', never a watchlist wipe."""
    try:
        from trading.brain import boss
        active = [s for s in (boss.active_segments("CRYPTO") or []) if s in _BINANCE_SEGMENTS]
    except Exception:
        active = list(_BINANCE_SEGMENTS)
    out: dict = {}
    if not active:
        return out
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        cli = CryptoEngineClient()
    except Exception:
        return out
    for seg in active:
        try:
            for pair in (cli.open_pairs(segment=seg) or []):
                sym = _flat(pair)
                if sym and sym not in out:
                    out[sym] = {"pair": pair, "segment": seg}
        except Exception:
            continue                       # one segment down ≠ the mirror is wrong
    return out


# ── persisted sync state ─────────────────────────────────────────────────────
def _load_state() -> dict:
    st = state.load_json(_STATE_FILE, {})
    return st if isinstance(st, dict) else {}


def _save_state(synced: list[str], report: dict) -> None:
    state.save_json(_STATE_FILE, {
        "watchlist": "Binance Favorites",
        "synced": list(dict.fromkeys(synced)),
        "last_report": report,
        "ts": report.get("ts"),
    })


def status() -> dict:
    """Honest snapshot for the dashboard: Favorites vs open trades, last sync."""
    st = _load_state()
    synced = list(st.get("synced") or [])
    desired_map = open_crypto_symbols()
    plan = plan_sync(list(desired_map), synced)
    return {
        "watchlist": "Binance Favorites",
        "write_enabled": os.environ.get("BROKER_WATCHLIST_WRITE") in
                         ("1", "true", "TRUE", "yes"),
        "segments_mirrored": list(_BINANCE_SEGMENTS),
        "open_trades": list(desired_map),
        "watchlist_synced": synced,
        "pending_add": plan["add"],
        "pending_remove": plan["remove"],
        "in_sync": not plan["add"] and not plan["remove"],
        "last_report": st.get("last_report") or {},
    }


# ── HUMAN-LIKE writer (eyes→brain→hand on the Binance web app) ───────────────
def _symbol_url(sym: str, segment: str) -> str:
    if segment == "futures":
        return f"https://www.binance.com/en/futures/{sym}"
    return f"https://www.binance.com/en/trade/{sym}?type=spot"


def _open_symbol_ui(sessions, sym: str, segment: str):
    """(HumanUI, page) on the symbol's own Binance page — or (None, None) honestly."""
    from trading.brain.vision.human_ui import HumanUI
    try:
        pg = sessions.page("binance", _symbol_url(sym, segment), timeout_ms=40000)
    except Exception:
        return None, None
    if pg is None:
        return None, None
    try:
        pg.wait_for_timeout(6000)              # let the app hydrate the header/star
    except Exception:
        pass
    return HumanUI(pg, name="binance"), pg


def _star_state(ui, sym: str) -> bool | None:
    """Eyes-read of the ⭐ toggle next to the symbol name. True=favorited, None=unreadable."""
    try:
        ans = ui.read(f"Look at the star/favorite icon next to the symbol name {sym} near "
                      f"the top of the page. Is it FILLED/highlighted (already a favorite) "
                      f"or EMPTY/outline (not a favorite)? Answer 'filled' or 'empty'.")
    except Exception:
        return None
    a = (ans or "").lower()
    if "filled" in a or "highlight" in a:
        return True
    if "empty" in a or "outline" in a:
        return False
    return None


def _set_star(ui, sym: str, want: bool) -> bool:
    """Make the ⭐ state == want, idempotently; True only when the eyes CONFIRM it."""
    ui.dismiss_modals()
    cur = _star_state(ui, sym)
    if cur is want:
        return True
    if not ui.click(f"the star / add-to-favorites icon next to the symbol name {sym} at "
                    f"the top of the page (NOT any Buy/Sell/Trade button)"):
        return False
    try:
        ui.page.wait_for_timeout(1200)
    except Exception:
        pass
    return _star_state(ui, sym) is want


def apply_sync(*, sessions=None) -> dict:
    """Make Binance ⭐ Favorites == current open crypto trades (active segments).

    GATED behind BROKER_WATCHLIST_WRITE=1. Add newly-opened, un-star newly-closed;
    each toggle is confirmed by the eyes before the synced set records it. Never raises."""
    desired_map = open_crypto_symbols()
    desired = list(desired_map)
    st = _load_state()
    already = list(st.get("synced") or [])
    plan = plan_sync(desired, already)
    report: dict = {"ts": time.time(), "target_n": len(plan["target"]),
                    "add": plan["add"], "remove": plan["remove"],
                    "added": [], "removed": [], "write_enabled": False,
                    "login_ok": None, "error": None}

    if os.environ.get("BROKER_WATCHLIST_WRITE") not in ("1", "true", "TRUE", "yes"):
        report["error"] = "gated — set BROKER_WATCHLIST_WRITE=1 to write to the real account"
        _save_state(already, report)
        return report
    report["write_enabled"] = True
    if not plan["add"] and not plan["remove"]:
        report["note"] = "already in sync"
        _save_state(already, report)
        return report

    try:
        if sessions is None:
            from trading.broker_sense.sessions import get_sessions
            sessions = get_sessions()
        synced = set(already)
        seg_of = {s: (desired_map.get(s) or {}).get("segment", "futures") for s in desired}
        for sym in plan["add"]:
            ui, pg = _open_symbol_ui(sessions, sym, seg_of.get(sym, "futures"))
            if ui is None:
                report["error"] = "no Binance browser session (login expired or page failed)"
                continue
            report["login_ok"] = True
            if _set_star(ui, sym, True):
                report["added"].append(sym)
                synced.add(sym)
            _close(pg)
        for sym in plan["remove"]:
            # a closed trade's segment came from the last sync; default futures page
            seg = ((st.get("last_report") or {}).get("segments") or {}).get(sym, "futures")
            ui, pg = _open_symbol_ui(sessions, sym, seg)
            if ui is None:
                report["error"] = "no Binance browser session (login expired or page failed)"
                continue
            report["login_ok"] = True
            if _set_star(ui, sym, False):
                report["removed"].append(sym)
                synced.discard(sym)
            _close(pg)
        report["segments"] = seg_of
        _save_state([s for s in desired if s in synced] +
                    [s for s in synced if s not in set(desired)], report)
        return report
    except Exception as e:                                  # a sync error never kills the loop
        report["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        _save_state(already, report)
        return report


def _close(pg) -> None:
    try:
        pg.close()
    except Exception:
        pass
