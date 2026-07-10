"""trading/broker_sense/account_watchlist.py — mirror OPEN trades into a dedicated
"Brain-Open" watchlist in the REAL Upstox account (add on open, remove on close).

Purpose (owner ask 2026-07-07): a live watchlist inside the Upstox app that always
equals the current open-trades set, so the owner can open Upstox and SEE the brain's
open positions there — visual proof the brain is wired to the real account.

Upstox has NO watchlist API (confirmed: community "Need API for Watchlist management"
is unanswered; watchlists are Pro-app UI only), so the WRITE path is DOM automation of
the logged-in Upstox Pro session (reusing trading/broker_sense/sessions + the safe-click
primitives). The DIFF/plan is pure + unit-tested; the apply is gated + honest:

  • Gated behind BROKER_WATCHLIST_WRITE=1 (a write to the app — never an order).
  • Targets ONE dedicated watchlist (WATCHLIST_NAME, default "Brain-Open") — never
    touches the owner's other watchlists.
  • add on open / remove on close, so the watchlist set == open-trades set.
  • Never fakes success: if the login is expired or a control isn't found, it reports
    the honest reason (the panel shows "login expired — re-login at Upstox").

State (which symbols we've synced) persists in trading/state so the diff is correct
across process restarts and the dashboard can show the last sync honestly.
"""
from __future__ import annotations

import os
import time
from typing import Any

from trading import state

_STATE_FILE = "account_watchlist_upstox.json"
WATCHLIST_NAME = os.environ.get("BRAIN_WATCHLIST_NAME", "Brain-Open")
# Upstox watchlists are equity/derivative symbols; crypto never belongs here.
_CRYPTO_MARKERS = ("/USDT", "/USD", "/INR", ":USDT")


# ── open-trades source (the mirror truth) ────────────────────────────────────
def open_nse_symbols() -> list[str]:
    """Distinct symbols of the currently-OPEN NSE trades (equity + options + futures),
    read from the OpenAlgo position book (qty != 0). This is where BOTH NSE drivers
    (the broker-sense funnel and the online live loop) book paper positions, so it is
    the single authoritative open-trades set the Upstox watchlist should mirror.

    Best-effort: returns [] (never raises) when OpenAlgo is down, so the sync degrades
    to 'no change' rather than wiping the watchlist on a transient outage.
    """
    try:
        from trading.openalgo_client import OpenAlgoClient
        res = OpenAlgoClient().positions()
    except Exception:
        return []
    rows = []
    if isinstance(res, dict):
        rows = res.get("data") or res.get("positions") or []
    elif isinstance(res, list):
        rows = res
    out: list[str] = []
    seen: set = set()
    for r in rows:
        if not isinstance(r, dict):
            continue
        sym = str(r.get("symbol") or r.get("tradingsymbol") or "").strip()
        if not sym or sym in seen:
            continue
        try:
            qty = float(r.get("quantity") or r.get("netqty") or r.get("net_quantity") or 0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty == 0:                      # flat leg → the trade is closed, drop it
            continue
        if any(m in sym for m in _CRYPTO_MARKERS):
            continue
        seen.add(sym)
        out.append(sym)
    return out


# ── pure diff / plan (unit-tested, no I/O) ───────────────────────────────────
def plan_sync(desired: list[str], already: list[str]) -> dict:
    """Compute the add/remove plan to make the 'Brain-Open' watchlist == `desired`.

    `desired`  = current open-trades symbols. `already` = what we last synced into the
    watchlist. Returns {add, remove, unchanged, target} — deterministic + order-stable.
    """
    d = list(dict.fromkeys(s for s in desired if s))       # de-dup, keep order
    a = list(dict.fromkeys(s for s in already if s))
    dset, aset = set(d), set(a)
    add = [s for s in d if s not in aset]                  # newly opened
    remove = [s for s in a if s not in dset]               # newly closed
    unchanged = [s for s in d if s in aset]
    return {"add": add, "remove": remove, "unchanged": unchanged, "target": d}


# ── persisted sync state ─────────────────────────────────────────────────────
def _load_state() -> dict:
    st = state.load_json(_STATE_FILE, {})
    return st if isinstance(st, dict) else {}


def _save_state(synced: list[str], report: dict) -> None:
    state.save_json(_STATE_FILE, {
        "watchlist": WATCHLIST_NAME,
        "synced": list(dict.fromkeys(synced)),
        "last_report": report,
        "ts": report.get("ts"),
    })


def status() -> dict:
    """Honest snapshot for the dashboard: what's in Brain-Open, vs open trades, last sync."""
    st = _load_state()
    synced = list(st.get("synced") or [])
    try:
        desired = open_nse_symbols()
    except Exception:
        desired = []
    plan = plan_sync(desired, synced)
    in_sync = not plan["add"] and not plan["remove"]
    return {
        "watchlist": WATCHLIST_NAME,
        "write_enabled": os.environ.get("BROKER_WATCHLIST_WRITE") in ("1", "true", "TRUE", "yes"),
        "open_trades": desired,
        "watchlist_synced": synced,
        "pending_add": plan["add"],
        "pending_remove": plan["remove"],
        "in_sync": in_sync,
        "last_report": st.get("last_report") or {},
    }


# ── HUMAN-LIKE writer (vision eyes→brain→hand — robust to the Upstox SPA) ─────
# Upstox Pro renders into a headless-detecting SPA (raw DOM selectors find nothing), so the
# watchlist is driven by the vision engine (trading/brain/vision/human_ui) the way a person
# would: LOOK, understand, move+click. Requires a HEADED browser — the session manager
# auto-runs Xvfb when BROKER_SENSE_HEADED=1. See [[human-ui-eyes-brain-hand]].
def _open_ui(sessions, broker: str = "upstox"):
    """Open the Upstox Pro app headed and return (HumanUI, page) — or (None, None) honestly."""
    from trading.broker_sense.brokers import REGISTRY
    from trading.brain.vision.human_ui import HumanUI
    app = REGISTRY.get(broker)
    home = getattr(app, "home_url", "https://pro.upstox.com") if app else "https://pro.upstox.com"
    try:
        pg = sessions.page(broker, home, timeout_ms=40000)
    except Exception:
        return None, None
    if pg is None:
        return None, None
    try:
        pg.wait_for_timeout(9000)              # let the SPA boot
    except Exception:
        pass
    return HumanUI(pg, name=broker), pg


def _logged_in(ui) -> bool:
    """Ask the eyes whether we're in the logged-in app (not the login/QR screen)."""
    try:
        ans = ui.read("Is this the logged-in Upstox trading app with a watchlist, or a "
                      "login/QR screen? Answer 'app' or 'login'.")
        return "login" not in (ans or "").lower()
    except Exception:
        return False


def apply_sync(*, sessions=None, broker: str = "upstox") -> dict:
    """Make the real Upstox 'Brain-Open' watchlist == current open trades.

    GATED behind BROKER_WATCHLIST_WRITE=1. Computes the add/remove plan, then drives the
    logged-in Upstox Pro DOM to add newly-opened symbols and remove newly-closed ones in
    the dedicated watchlist. Never raises; never fakes success — on expired login / missing
    control it records the honest reason and leaves the synced-state unchanged for those.
    """
    desired = open_nse_symbols()
    st = _load_state()
    already = list(st.get("synced") or [])
    plan = plan_sync(desired, already)
    report: dict = {"ts": time.time(), "target_n": len(plan["target"]),
                    "add": plan["add"], "remove": plan["remove"],
                    "added": [], "removed": [], "write_enabled": False, "login_ok": None,
                    "error": None}

    if os.environ.get("BROKER_WATCHLIST_WRITE") not in ("1", "true", "TRUE", "yes"):
        report["error"] = "gated — set BROKER_WATCHLIST_WRITE=1 to write to the real account"
        _save_state(already, report)                       # no change to synced set
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
        ui, pg = _open_ui(sessions, broker)
        if ui is None:
            report["error"] = "no Upstox browser session (headed open failed — need BROKER_SENSE_HEADED=1 + Xvfb)"
            _save_state(already, report)
            return report
        ui.dismiss_modals()                    # clear SEBI notice / onboarding tooltips first
        if not _logged_in(ui):
            report["login_ok"] = False
            report["error"] = "Upstox login expired — re-login at Upstox (daily QR login)"
            try:
                pg.close()
            except Exception:
                pass
            _save_state(already, report)
            return report
        report["login_ok"] = True
        report["watchlist_selected"] = _ensure_watchlist(ui)   # land on the Brain-Open tab
        synced = set(already)
        # BUDGETED (2026-07-07, same fix as the Binance mirror): this runs inside the
        # funnel loop — bound the vision work per pass so a big diff can never stall
        # trading cycles; the remainder converges over the next passes.
        try:
            max_actions = int(os.environ.get("BRAIN_MIRROR_MAX_ACTIONS", "4") or 4)
        except ValueError:
            max_actions = 4
        actions = 0
        deferred = 0
        # FAIR INTERLEAVE (same fix as the Binance mirror): alternating add/remove keeps
        # the remove queue from starving behind a churn of adds, so closed trades leave
        # the watchlist at the same pace new opens join it.
        queue: list[tuple[str, str]] = []
        for i in range(max(len(plan["add"]), len(plan["remove"]))):
            if i < len(plan["add"]):
                queue.append(("add", plan["add"][i]))
            if i < len(plan["remove"]):
                queue.append(("remove", plan["remove"][i]))
        for op, sym in queue:
            if actions >= max_actions:
                deferred += 1
                continue
            actions += 1
            if op == "add":
                if _add_symbol(ui, sym):
                    report["added"].append(sym)
                    synced.add(sym)
            elif _remove_symbol(ui, sym):
                report["removed"].append(sym)
                synced.discard(sym)
        report["deferred"] = deferred
        try:
            pg.close()
        except Exception:
            pass
        # persist only what the DOM actually confirmed, so a partial run stays truthful
        _save_state([s for s in desired if s in synced] +
                    [s for s in synced if s not in set(desired)], report)
        return report
    except Exception as e:                                  # a sync error never kills the loop
        report["error"] = f"{type(e).__name__}: {str(e)[:120]}"
        _save_state(already, report)
        return report


def _add_symbol(ui, sym: str) -> bool:
    """Add `sym` to the watchlist the human way. The Upstox add flow is multi-step and its
    exact controls (the 'Pin new symbols' menu → search → pin) shift with onboarding coach-
    marks, so we hand the GOAL to the autonomous vision loop (explore) which perceives and
    picks each next step itself — far more robust than a hard-coded selector chain. Then we
    CONFIRM by re-reading the watchlist (honest: only True when `sym` is actually visible).
    Skill-cached (#2): after the first success the recorded trajectory replays directly."""
    ui.dismiss_modals()
    ui.explore(
        f"Add the stock symbol {sym} to the current watchlist. To do this: open 'Pin new "
        f"symbols' (or the + add-symbol control), type {sym} into the search box, then click "
        f"the pin/+ button on the {sym} result row. Do NOT click any Buy/Sell/Trade button.",
        max_steps=6, skill_key="watchlist-add-symbol", params={"SYM": sym})
    ui.press("Escape")
    ans = ui.read(f"Is the symbol {sym} now listed in the left watchlist? Answer yes or no.")
    ok = "yes" in (ans or "").lower()
    try:
        ui.skill_feedback("watchlist-add-symbol", ok)   # eyes-confirmed outcome trains the hand
    except Exception:
        pass
    return ok


def _ensure_watchlist(ui) -> bool:
    """Select (or create) the dedicated WATCHLIST_NAME tab so adds/removes land there and
    never touch the owner's other watchlists. Best-effort via the vision loop."""
    ui.dismiss_modals()
    ans = ui.read(f"Is a watchlist tab named '{WATCHLIST_NAME}' currently selected at the top "
                  f"of the left watchlist panel? Answer yes or no.")
    if "yes" in (ans or "").lower():
        return True
    ui.explore(
        f"Select the watchlist tab named '{WATCHLIST_NAME}' at the top-left. If no tab named "
        f"'{WATCHLIST_NAME}' exists, create a new watchlist by clicking the + tab and name it "
        f"'{WATCHLIST_NAME}'. Do NOT click any Buy/Sell/Trade button.",
        max_steps=5, skill_key="watchlist-select-tab", params={"NAME": WATCHLIST_NAME})
    ans = ui.read(f"Is the '{WATCHLIST_NAME}' watchlist tab now selected? Answer yes or no.")
    return "yes" in (ans or "").lower()


def _remove_symbol(ui, sym: str) -> bool:
    """Remove `sym` from the watchlist the human way: open its row context menu, pick remove.
    Never touches Buy/Sell (order-guarded)."""
    if not ui.click(f"the watchlist row for the symbol {sym}"):
        return False
    ui.page.wait_for_timeout(400)
    # Upstox exposes remove via the row's context menu / 'Pin new symbols' toggle
    removed = (ui.click(f"the remove or unpin option for {sym} in the menu")
               or ui.click("the remove from watchlist option"))
    ui.press("Escape")
    return bool(removed)
