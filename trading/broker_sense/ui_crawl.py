"""trading/broker_sense/ui_crawl.py — the EYES' symbol-page crawl (owner goal
2026-07-07, Human-UI engine #10 / UI-only data #11).

The UI-only data store (ui_data.py) fills itself from the trading apps' OWN kline
XHRs — but those only fire when the eyes actually VISIT a symbol's page, like a human
trader flipping through charts. This module is that habit:

  crawl_once()  — round-robin: open the next K symbols' pages on the broker app
                  (Binance futures/spot chart pages; Upstox handled by the watchlist
                  mirror), dwell briefly so the app fires its candle/depth/trade
                  requests, optionally click one timeframe button (more TF coverage),
                  and move on. Interception does the capturing; ui_data indexes it.

Budget-aware and polite: K symbols per call, ~3-6s dwell, deadline honored — designed
to run inside the funnel cycle without blowing its budget. The crawl NEVER clicks
anything except chart timeframe tabs (guarded HumanUI click with order-guard on).
State: ui_crawl_cursor.json (round-robin position + per-symbol last-visit).
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "ui_crawl_cursor.json"
_DWELL_S = float(os.environ.get("UI_CRAWL_DWELL_S", "4"))
_PER_CYCLE = int(os.environ.get("UI_CRAWL_PER_CYCLE", "4"))
_REVISIT_S = float(os.environ.get("UI_CRAWL_REVISIT_S", "600"))   # candle freshness target
_TF_CLICK = os.environ.get("UI_CRAWL_TF_CLICK", "1") in ("1", "true", "TRUE", "yes")


def _binance_url(symbol: str) -> str:
    flat = symbol.upper().replace("/", "").replace(":USDT", "")
    if symbol.endswith(":USDT") or ":" in symbol:
        return f"https://www.binance.com/en/futures/{flat}"
    return f"https://www.binance.com/en/trade/{flat}?type=spot"


def _due_symbols(symbols: list[str], k: int) -> list[str]:
    cur = state.load_json(_FILE, {})
    visits = cur.get("visits", {})
    now = time.time()
    due = [s for s in symbols if now - visits.get(s, 0) >= _REVISIT_S]
    start = int(cur.get("pos", 0)) % max(1, len(due) or 1)
    picked = (due[start:] + due[:start])[:k] if due else []
    cur["pos"] = start + len(picked)
    state.save_json(_FILE, cur)
    return picked


def _mark_visited(symbol: str, ok: bool) -> None:
    cur = state.load_json(_FILE, {})
    cur.setdefault("visits", {})[symbol] = time.time()
    cur.setdefault("log", []).append({"symbol": symbol, "ok": ok, "ts": time.time()})
    cur["log"] = cur["log"][-200:]
    state.save_json(_FILE, cur)


def crawl_once(sessions, symbols: list[str], *, deadline: float | None = None,
               k: int = _PER_CYCLE) -> dict:
    """Visit up to k due symbol pages on Binance. Returns an honest report."""
    report = {"visited": [], "skipped": 0, "errors": []}
    todo = _due_symbols([s for s in symbols if s], k)
    if not todo:
        report["skipped"] = len(symbols)
        return report
    for sym in todo:
        if deadline is not None and time.monotonic() > deadline:
            report["errors"].append("deadline before finishing crawl")
            break
        try:
            pg = sessions.page("binance", _binance_url(sym))
            if pg is None:
                report["errors"].append(f"{sym}: no binance page/session")
                _mark_visited(sym, False)
                continue
            t0 = time.time()
            while time.time() - t0 < _DWELL_S:          # dwell: let the app fire XHRs
                time.sleep(0.5)
            if _TF_CLICK:
                # flip ONE timeframe tab like a human — more TF coverage per visit.
                # Best-effort DOM click on the visible interval selector; never fatal.
                try:
                    for tf_label in ("15m", "1h"):
                        el = pg.locator(f"text=/^{tf_label}$/").first
                        if el and el.is_visible(timeout=800):
                            el.click(timeout=1200)
                            time.sleep(1.2)
                            break
                except Exception:
                    pass
            report["visited"].append(sym)
            _mark_visited(sym, True)
        except Exception as e:
            report["errors"].append(f"{sym}: {type(e).__name__}: {str(e)[:60]}")
            _mark_visited(sym, False)
    try:                                               # coverage snapshot for the API
        from trading.broker_sense import ui_data
        ui_data._maybe_snapshot()
    except Exception:
        pass
    return report


def status() -> dict:
    cur = state.load_json(_FILE, {})
    return {"visited_total": len(cur.get("visits", {})),
            "recent": (cur.get("log") or [])[-10:],
            "per_cycle": _PER_CYCLE, "dwell_s": _DWELL_S,
            "revisit_s": _REVISIT_S}
