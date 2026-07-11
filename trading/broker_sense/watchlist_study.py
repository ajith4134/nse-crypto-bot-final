"""trading/broker_sense/watchlist_study.py — W: the watchlist study funnel (Pillar 27).

The owner's flow, verbatim: save promising symbols to the trading app's own
watchlist/favorites → open each saved symbol one by one → study EVERYTHING the app
shows for it (multi-timeframe candles + indicators, candle patterns, volume, order
depth) → decide the direction → trade via API only → remove the symbol from the
watchlist once its trade closes.

What each step maps to here (reuse-first — no new browsing machinery invented):
  SAVE    — a persistent STUDY SET (this module's state file); the existing Brain-Open
            mirrors (binance_watchlist ⭐ / account_watchlist) union it into the app
            watchlist they already write, gated by the same BROKER_WATCHLIST_WRITE.
  STUDY   — per symbol: the multi-timeframe chart read the funnel's LOOK stage uses
            (eyes' captured app data in UI-only mode, screenshot+CNN chart vision when
            FAST_CANDLES=0 — i.e. literally the app's chart), the D4 microstructure
            lanes (order depth via the psychology book read, funding, venue gap), and
            the D5 regime — fused into one StudyReport persisted with its evidence.
  DECIDE  — the fused verdict is recorded in the Truth Ledger as source "app_study":
            the study lane EARNS a measured hit-rate like every other source, and the
            executor's Mirror-Gate/meta-labeler treat it accordingly. Execution stays
            with the funnel executor — API-only, as the standing order requires.
  REMOVE  — a studied symbol leaves the set (and thus the app watchlist) when it is
            neither an open trade nor a current candidate any more.

Levers: WATCHLIST_STUDY=1 (default on), STUDY_MAX (default 6 concurrent),
STUDY_TTL_MIN (default 240), STUDY_BUDGET_S per round (default 45).
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "watchlist_study.json"       # {"set": {sym: {...}}, "reports": [...], "stats": {}}
_TFS = ("15m", "1h", "4h")


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def enabled() -> bool:
    return os.environ.get("WATCHLIST_STUDY", "1") in ("1", "true", "TRUE", "yes", "on")


def study_symbols(market: str = "crypto") -> list[str]:
    """The current study set for a market — the Brain-Open mirrors union this into
    the app watchlist they maintain."""
    try:
        data = state.load_json(_FILE, {})
        return [s for s, r in (data.get("set") or {}).items()
                if r.get("market") == market.lower()]
    except Exception:
        return []


def propose(candidates: list[str], *, market: str, segment: str) -> dict:
    """Refresh the study set from this cycle's funnel candidates: admit new symbols up
    to STUDY_MAX, expire stale ones, drop symbols that are no longer candidates AND
    already studied (their app-watchlist slot frees up). Never raises."""
    rep = {"added": [], "dropped": [], "kept": 0}
    if not enabled():
        return rep
    try:
        now = time.time()
        ttl_s = _env_f("STUDY_TTL_MIN", 240) * 60
        cap = int(_env_f("STUDY_MAX", 6))
        cands = [c for c in (candidates or []) if c]

        def _m(data: dict) -> dict:
            cur: dict = data.setdefault("set", {})
            for sym, row in list(cur.items()):
                if row.get("market") != market.lower():
                    continue
                stale = now - float(row.get("ts") or 0) > ttl_s
                done_and_gone = row.get("studied") and sym not in cands
                if stale or done_and_gone:
                    cur.pop(sym, None)
                    rep["dropped"].append(sym)
            room = cap - sum(1 for r in cur.values()
                             if r.get("market") == market.lower())
            for sym in cands:
                if room <= 0:
                    break
                if sym not in cur:
                    cur[sym] = {"market": market.lower(), "segment": segment,
                                "ts": now, "studied": False}
                    rep["added"].append(sym)
                    room -= 1
            rep["kept"] = sum(1 for r in cur.values()
                              if r.get("market") == market.lower())
            return data
        state.mutate_json(_FILE, _m, default={})
    except Exception:
        pass
    return rep


def _fuse(mtf: dict, micro: dict) -> tuple[str | None, float, dict]:
    """One verdict from the study evidence: multi-TF chart vote (2 votes — it is the
    owner's centerpiece) + each micro lane (1 vote each). Majority wins; tie or no
    votes → None (an honest 'no edge seen')."""
    votes: dict[str, float] = {"LONG": 0.0, "SHORT": 0.0}
    detail = {}
    ps = [c.get("p_up") for c in (mtf or {}).values()
          if isinstance(c, dict) and c.get("p_up") is not None
          and c.get("source") != "unavailable"]
    if ps:
        mean = sum(ps) / len(ps)
        detail["mtf_p_up"] = round(mean, 3)
        if mean >= 0.55:
            votes["LONG"] += 2
        elif mean <= 0.45:
            votes["SHORT"] += 2
    for lane in ("venue_leadlag", "psych_ofi", "funding_extreme", "mtf_agree"):
        v = ((micro or {}).get(lane) or {}).get("vote")
        if v in votes:
            votes[v] += 1
            detail[lane] = v
    if votes["LONG"] == votes["SHORT"]:
        return None, 0.0, detail
    side = "LONG" if votes["LONG"] > votes["SHORT"] else "SHORT"
    total = votes["LONG"] + votes["SHORT"]
    return side, round(votes[side] / total, 3), detail


def study_round(sessions=None, *, market: str = "crypto", vision=None,
                budget_s: float | None = None) -> dict:
    """Study up to the round budget of un-studied set members: multi-TF chart read
    (app chart via vision when configured, fast API candles otherwise) + D4 micro
    lanes + D5 regime → StudyReport persisted + an "app_study" Truth-Ledger claim.
    Returns {"studied": [...], "claims": n} for the loop log."""
    rep = {"studied": [], "claims": 0}
    if not enabled():
        return rep
    t0 = time.monotonic()
    budget = float(budget_s if budget_s is not None else _env_f("STUDY_BUDGET_S", 45))
    try:
        data = state.load_json(_FILE, {})
        todo = [(s, r) for s, r in (data.get("set") or {}).items()
                if r.get("market") == market.lower() and not r.get("studied")]
        if not todo:
            return rep
        from trading.broker_sense import fast_candles
        from trading.direction import micro_features, truth_ledger
        from trading.direction.regime import classify
        reports = []
        for sym, row in todo:
            if time.monotonic() - t0 > budget:
                break
            seg = row.get("segment") or "futures"
            reader = vision if vision is not None else fast_candles
            charts = reader.read([{"symbol": sym, "lane": "study"}], market,
                                 timeframes=_TFS,
                                 deadline=t0 + budget) or {}
            mtf = charts.get(sym) or {}
            micro = micro_features.snapshot(sym, seg) if market == "crypto" else {}
            regime = (classify(sym, seg).get("regime")
                      if market == "crypto" else None)
            side, conf, detail = _fuse(mtf, micro)
            report = {"symbol": sym, "market": market.lower(), "segment": seg,
                      "ts": time.time(), "regime": regime, "verdict": side,
                      "confidence": conf, "evidence": detail,
                      "frames_read": len([1 for c in mtf.values()
                                          if isinstance(c, dict)
                                          and c.get("source") != "unavailable"])}
            reports.append(report)
            rep["studied"].append(sym)
            if side and truth_ledger.record(
                    symbol=sym, market=market.upper(), segment=seg,
                    direction=side, source="app_study",
                    confidence=conf, regime=regime):
                rep["claims"] += 1

        def _m(d: dict) -> dict:
            cur = d.setdefault("set", {})
            for r in reports:
                if r["symbol"] in cur:
                    cur[r["symbol"]]["studied"] = True
                    cur[r["symbol"]]["verdict"] = r["verdict"]
            d["reports"] = (d.get("reports") or [])[-29:] + reports
            s = d.setdefault("stats", {})
            s["rounds"] = s.get("rounds", 0) + 1
            s["studied_total"] = s.get("studied_total", 0) + len(reports)
            return d
        if reports:
            state.mutate_json(_FILE, _m, default={})
    except Exception:
        pass
    return rep


def status() -> dict:
    """Panel/API snapshot: the live study set, latest reports, lifetime stats."""
    data = state.load_json(_FILE, {})
    return {"enabled": enabled(),
            "set": data.get("set") or {},
            "reports": (data.get("reports") or [])[-12:][::-1],
            "stats": data.get("stats") or {},
            "levers": {"STUDY_MAX": _env_f("STUDY_MAX", 6),
                       "STUDY_TTL_MIN": _env_f("STUDY_TTL_MIN", 240),
                       "STUDY_BUDGET_S": _env_f("STUDY_BUDGET_S", 45)}}
