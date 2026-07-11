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
            FAST_CANDLES=0 — i.e. literally the app's chart), the FULL indicator
            fusion (every built-in indicator across every timeframe, with the chart
            read as its candlestick-vision lens), textbook candle patterns per
            timeframe, the D4 microstructure lanes (order depth via the psychology
            book read, funding, venue gap), and the D5 regime — fused into one
            StudyReport persisted with its evidence. The indicator and pattern reads
            also stake their own ledger claims ("app_indicators", "candle_pattern").
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


def _patterns_from_ohlc(o: list, h: list, l: list, c: list) -> tuple[list[str], int]:
    """Textbook candle patterns on the LAST bars of one timeframe (pure lists in →
    pattern names + net sign out; no I/O, symmetric long/short rules). The owner's
    'read the chart's candle patterns like a human' lens, kept honest and simple:
    engulfing, hammer / shooting star (after a slide/rise), three soldiers / crows."""
    names: list[str] = []
    n = len(c)
    if n < 4 or not (len(o) == len(h) == len(l) == n):
        return names, 0
    body = [c[i] - o[i] for i in range(n)]
    rng = [max(h[i] - l[i], 1e-12) for i in range(n)]
    i = n - 1
    if abs(body[i]) > abs(body[i - 1]):
        if body[i] > 0 > body[i - 1] and c[i] >= o[i - 1] and o[i] <= c[i - 1]:
            names.append("bullish_engulfing")
        if body[i] < 0 < body[i - 1] and c[i] <= o[i - 1] and o[i] >= c[i - 1]:
            names.append("bearish_engulfing")
    lower = min(o[i], c[i]) - l[i]
    upper = h[i] - max(o[i], c[i])
    small = abs(body[i]) <= 0.35 * rng[i]
    if small and lower >= 2 * abs(body[i]) and upper <= 0.25 * rng[i] and c[i - 1] < c[i - 2]:
        names.append("hammer")
    if small and upper >= 2 * abs(body[i]) and lower <= 0.25 * rng[i] and c[i - 1] > c[i - 2]:
        names.append("shooting_star")
    if all(body[j] > 0.5 * rng[j] for j in (i - 2, i - 1, i)) and c[i] > c[i - 1] > c[i - 2]:
        names.append("three_white_soldiers")
    if all(body[j] < -0.5 * rng[j] for j in (i - 2, i - 1, i)) and c[i] < c[i - 1] < c[i - 2]:
        names.append("three_black_crows")
    bull = {"bullish_engulfing", "hammer", "three_white_soldiers"}
    sign = sum(1 if x in bull else -1 for x in names)
    return names, (1 if sign > 0 else -1 if sign < 0 else 0)


def _candle_patterns(symbol: str, segment: str) -> dict:
    """Candle-pattern read across the app's timeframes (15m/1h/4h) from the LOCAL
    feathers — zero network. Votes only when every patterned frame agrees."""
    out: dict = {"frames": {}, "vote": None, "conf": None}
    try:
        import pandas as pd
        from trading.direction.truth_ledger import _feather_for
        p5, _ = _feather_for(symbol, segment)
        if p5 is None:
            return out
        signs = []
        for tf in _TFS:
            p = p5.with_name(p5.name.replace("-5m-", f"-{tf}-"))
            if not p.exists():
                continue
            df = pd.read_feather(
                p, columns=["date", "open", "high", "low", "close"]).tail(8)
            if len(df) < 4:
                continue
            names, sign = _patterns_from_ohlc(
                [float(x) for x in df["open"]], [float(x) for x in df["high"]],
                [float(x) for x in df["low"]], [float(x) for x in df["close"]])
            if names:
                out["frames"][tf] = names
            if sign:
                signs.append(sign)
        if signs and len(set(signs)) == 1:
            out["vote"] = "LONG" if signs[0] > 0 else "SHORT"
            out["conf"] = round(len(signs) / 3.0, 2)
    except Exception:
        pass
    return out


def _fuse(mtf: dict, micro: dict, fusion: dict | None = None,
          patterns: dict | None = None) -> tuple[str | None, float, dict]:
    """One verdict from the study evidence: multi-TF chart vote (2 votes — it is the
    owner's centerpiece) + the FULL indicator fusion (2 votes — every built-in
    indicator across every timeframe, the pro-desk read) + candle patterns (1 vote)
    + each micro lane (1 vote each). Majority wins; tie or no votes → None (an
    honest 'no edge seen')."""
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
    if (fusion or {}).get("available") and fusion.get("direction") in ("long", "short"):
        votes[fusion["direction"].upper()] += 2
        detail["indicator_fusion"] = {
            "direction": fusion["direction"], "p_up": fusion.get("p_up"),
            "confluence": fusion.get("confluence"), "regime": fusion.get("regime"),
            "veto": fusion.get("veto")}
    pv = (patterns or {}).get("vote")
    if pv in votes:
        votes[pv] += 1
        detail["candle_patterns"] = (patterns or {}).get("frames")
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
            # ALL the app's built-in indicators, every timeframe, fused like a desk
            # (owner 2026-07-11): the study's chart read doubles as fuse()'s
            # candlestick-vision lens; unavailable stays honest, never fabricated.
            try:
                from trading.broker_sense import indicator_fusion
                fusion = indicator_fusion.fuse(sym, market, vision=mtf)
            except Exception:
                fusion = {}
            patterns = _candle_patterns(sym, seg) if market == "crypto" else {}
            side, conf, detail = _fuse(mtf, micro, fusion, patterns)
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
            # D7 league: the indicator read and the pattern read ALSO stake their own
            # shadow claims — each lens earns its own measured hit-rate on the ledger.
            try:
                if (fusion or {}).get("available") and \
                        fusion.get("direction") in ("long", "short"):
                    if truth_ledger.record(
                            symbol=sym, market=market.upper(), segment=seg,
                            direction=fusion["direction"].upper(),
                            source="app_indicators",
                            confidence=fusion.get("p_up"), regime=regime):
                        rep["claims"] += 1
                if patterns.get("vote") and truth_ledger.record(
                        symbol=sym, market=market.upper(), segment=seg,
                        direction=patterns["vote"], source="candle_pattern",
                        confidence=patterns.get("conf"), regime=regime):
                    rep["claims"] += 1
            except Exception:
                pass

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
