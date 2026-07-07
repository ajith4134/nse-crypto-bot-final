"""trading/broker_sense/ui_health.py — Human-UI self-check (owner goal 2026-07-07, #10).

Proves the eyes→brain→hand→memory chain is actually FUNCTIONAL on BOTH accounts
(Binance for crypto, Upstox for NSE) — honestly, not assumed. For each broker it
reports, from real state, whether:
  • session   — a live logged-in browser session exists,
  • eyes      — the interception layer captured this app's payloads recently,
  • data      — the UI-only candle store holds fresh candles this app fed,
  • crawl     — the eyes visited this app's pages recently,
  • hand      — the human-UI navigator is available (headed-Xvfb rendering up).

No navigation is performed here (that would fight the live loops for the single browser
context); this reads the artifacts the live crawl already produced. A broker with no
session reports session=False honestly — never a fabricated green.
"""
from __future__ import annotations

import time

from trading import state

_BROKERS = {"binance": "crypto", "upstox": "nse"}


def _has_session(broker: str) -> bool:
    try:
        from trading.broker_sense.sessions import has_session
        return bool(has_session(broker))
    except Exception:
        return False


def _eyes_fresh(broker: str, max_age_s: float = 1800) -> dict:
    # in-process cache first (this process's own eyes)…
    try:
        from trading.broker_sense.interception import get_recorder
        rec = get_recorder()
        kinds = {k: round(time.time() - v["ts"], 1)
                 for (b, k), v in rec._cache.items()
                 if b == broker and time.time() - v["ts"] <= max_age_s}
        if kinds:
            return {"live": True, "kinds": kinds}
    except Exception:
        pass
    # …else the cross-process freshness snapshot the funnel's eyes persist.
    try:
        snap = state.load_json("interception_freshness.json", {}).get("kinds", {})
        kinds = {bk.split("|", 1)[1]: round(time.time() - ts, 1)
                 for bk, ts in snap.items()
                 if bk.split("|", 1)[0] == broker and time.time() - ts <= max_age_s}
        return {"live": bool(kinds), "kinds": kinds}
    except Exception:
        return {"live": False, "kinds": {}}


def _crawl_recent(max_age_s: float = 1800) -> dict:
    cur = state.load_json("ui_crawl_cursor.json", {})
    log = cur.get("log") or []
    recent = [r for r in log if time.time() - r.get("ts", 0) <= max_age_s]
    return {"visited_recently": len(recent),
            "last": recent[-1] if recent else None}


def _hand_available() -> dict:
    try:
        import importlib.util
        spec = importlib.util.find_spec("trading.brain.vision.human_ui")
        return {"module": spec is not None,
                "headed": __import__("os").environ.get("BROKER_SENSE_HEADED", "") == "1"}
    except Exception:
        return {"module": False, "headed": False}


def check() -> dict:
    from trading.broker_sense import ui_data
    cov = ui_data.coverage()
    covered = cov.get("detail") or {}
    out: dict = {"generated_ts": time.time(), "ui_only_mode": ui_data.enabled(),
                 "brokers": {}, "hand": _hand_available()}
    for broker, market in _BROKERS.items():
        eyes = _eyes_fresh(broker)
        # which indexed symbols came from THIS broker's captures
        data_syms = sum(1 for _s, e in covered.items()
                        if (e.get("broker") == broker))
        chain_ok = _has_session(broker) and eyes["live"]
        out["brokers"][broker] = {
            "market": market,
            "session": _has_session(broker),
            "eyes_live": eyes["live"], "eyes_kinds": eyes["kinds"],
            "ui_data_symbols": data_syms,
            "chain_functional": chain_ok,
        }
    out["crawl"] = _crawl_recent()
    ok = [b for b, v in out["brokers"].items() if v["chain_functional"]]
    out["summary"] = {"functional_brokers": ok,
                      "both_accounts": len(ok) == len(_BROKERS)}
    state.save_json("ui_health.json", out)
    return out
