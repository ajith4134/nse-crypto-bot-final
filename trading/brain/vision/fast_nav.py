"""trading/brain/vision/fast_nav.py — FAST + ACCURATE navigation planner (2026-07-10).

Owner ask: "navigate Upstox and Binance very fast and accurately." The eyes/hand stack
already *learned* the apps (app_school_map.json: in-app links with seen-counts, visited
SPA pages, confirmed API routes; ui_skills.json: replayable action trajectories) — but
navigation still explores click-by-click. This planner turns that learned state into a
ranked plan BEFORE touching the browser:

    plan("upstox", "holdings")  →  [{method:"skill", key:...},          # replay, ~0 vision
                                    {method:"goto", url:..., trust:…},  # direct jump
                                    {method:"explore"}]                 # honest fallback

and `record()` closes the accuracy loop: every attempt's outcome (worked? how fast?) is
persisted to fast_nav_stats.json, and a (app, target, method) pair that failed twice in a
row is demoted below exploration — the same 2-strikes eviction convention as the hand's
skill cache. Self-contained on purpose (2026-07-10): human_ui.py / app_school.py carry
another session's in-flight edits; wiring is ONE call at the hand's navigate chokepoint —
`for step in fast_nav.plan(app, target): try step; fast_nav.record(...)`.
"""
from __future__ import annotations

import math
import re
import time

_STATS_FILE = "fast_nav_stats.json"
_SCHOOL_FILE = "app_school_map.json"
_SKILLS_FILE = "ui_skills.json"
_FAILS_TO_DEMOTE = 2


def _tokens(s: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", (s or "").lower()) if len(t) > 1}


def _state(name, default):
    try:
        from trading import state
        return state.load_json(name, default)
    except Exception:
        return default


def _score(target_toks: set[str], text: str, url: str, seen: int) -> float:
    """Similarity of a learned link to the target, weighted by how often the eyes saw it
    (a rail against one-off scraped links); 0 when nothing overlaps."""
    cand = _tokens(text) | _tokens(url.rsplit("/", 1)[-1]) | _tokens(url)
    overlap = len(target_toks & cand)
    if not overlap:
        return 0.0
    return overlap / max(1, len(target_toks)) * (1.0 + math.log1p(max(0, seen)) / 3.0)


def _method_fails(stats: dict, app: str, target: str, method: str, key: str) -> int:
    rec = ((stats.get(app) or {}).get(target.lower()) or {}).get(f"{method}:{key}") or {}
    return int(rec.get("consecutive_fails") or 0)


def plan(app: str, target: str, max_candidates: int = 3) -> list[dict]:
    """Ranked navigation plan for `target` (e.g. "holdings", "futures markets").

    Order: replayable hand SKILL (no per-step vision) → direct GOTO of the best learned
    URL(s) → EXPLORE (click-nav + vision, the honest fallback that also feeds the school).
    Entries that failed twice consecutively (per fast_nav_stats.json) are demoted."""
    app = (app or "").lower()
    tt = _tokens(target)
    school = _state(_SCHOOL_FILE, {}) or {}
    skills = _state(_SKILLS_FILE, {}) or {}
    stats = _state(_STATS_FILE, {}) or {}
    out: list[dict] = []
    # 1) hand skills — parameterized winning trajectories ({SYM} etc.)
    for key, sk in (skills.items() if isinstance(skills, dict) else []):
        if not isinstance(sk, dict):
            continue
        if _tokens(key) & tt and (sk.get("app") or app) == app:
            out.append({"method": "skill", "key": key, "app": app,
                        "score": 2.0 + _score(tt, key, "", int(sk.get("wins") or 0))})
    # 2) direct URL jumps from the school's learned links + visited pages
    seen_urls: set[str] = set()
    for section in ("links", "pages"):
        for url, meta in ((school.get(section) or {}).get(app) or {}).items():
            if url in seen_urls or not isinstance(meta, dict):
                continue
            seen_urls.add(url)
            s = _score(tt, meta.get("text") or "", url, int(meta.get("seen") or 1))
            if s > 0:
                out.append({"method": "goto", "url": url, "app": app, "score": s})
    # demote 2-strike failures below everything else (fresh exploration re-earns trust)
    for c in out:
        key = c.get("key") or c.get("url") or ""
        if _method_fails(stats, app, target, c["method"], key) >= _FAILS_TO_DEMOTE:
            c["score"] -= 100.0
            c["demoted"] = True
    out.sort(key=lambda c: -c["score"])
    out = out[:max_candidates]
    out.append({"method": "explore", "app": app,
                "note": "click-nav + vision fallback (feeds the school for next time)"})
    return out


def record(app: str, target: str, method: str, key: str, ok: bool,
           latency_ms: float | None = None) -> None:
    """Close the accuracy loop: persist the outcome of one navigation attempt."""
    try:
        from trading import state
        stats = state.load_json(_STATS_FILE, {}) or {}
        tgt = stats.setdefault((app or "").lower(), {}).setdefault(target.lower(), {})
        rec = tgt.setdefault(f"{method}:{key}", {
            "tries": 0, "wins": 0, "consecutive_fails": 0, "avg_ms": None})
        rec["tries"] += 1
        if ok:
            rec["wins"] += 1
            rec["consecutive_fails"] = 0
        else:
            rec["consecutive_fails"] += 1
        if latency_ms is not None:
            prev = rec["avg_ms"]
            rec["avg_ms"] = round(latency_ms if prev is None
                                  else 0.8 * prev + 0.2 * latency_ms, 1)
        rec["last_ts"] = time.time()
        state.save_json(_STATS_FILE, stats)
    except Exception:
        pass                                    # stats must never break navigation


def status() -> dict:
    """Live planner status for the dashboard: learned inventory + accuracy stats."""
    school = _state(_SCHOOL_FILE, {}) or {}
    stats = _state(_STATS_FILE, {}) or {}
    inv = {app: {"links": len((school.get("links") or {}).get(app) or {}),
                 "pages": len((school.get("pages") or {}).get(app) or {}),
                 "routes": len((school.get("routes") or {}).get(app) or {})}
           for app in set(list(school.get("links") or {}) + list(school.get("pages") or {}))}
    return {"inventory": inv, "nav_stats": stats, "live": True, "demo": False}
