"""trading/direction/research_context.py — per-symbol web-research briefs as CONTEXT.

The ResearchLoop (trading/crypto/freqtrade/brain_learning.py) searches online and writes
per-symbol briefs to research_findings.json — but nothing read them (0 consumers; the 2026-07-17
review's S3). Those briefs are MARKET-WIDE link/title collections, NOT per-symbol directional
signals — turning them into a p_up would fabricate a side and violate "DIRECTION MUST BE EARNED".

So they are exposed here as CONTEXT, never as a vote: a reader the dashboard (and, later, the LLM
debate) can consult to SEE what the brain recently researched about a symbol. Cached by file
mtime; fail-open; no network.
"""
from __future__ import annotations

import time

from trading import state

_FILE = "research_findings.json"
_CACHE: dict = {"mtime": None, "by_symbol": {}, "briefs": []}


def _flat(sym) -> str:
    return str(sym or "").replace("/", "").split(":")[0].upper()


def _load() -> dict:
    import os
    try:
        p = os.path.join(str(state.STATE_DIR), _FILE)
        m = os.path.getmtime(p)
    except OSError:
        return _CACHE
    if _CACHE["mtime"] != m:
        d = state.load_json(_FILE, {}) or {}
        briefs = d.get("briefs") or []
        by_sym: dict = {}
        for b in briefs:
            sym = _flat(b.get("symbol"))
            if sym:
                by_sym.setdefault(sym, b)
        _CACHE.update(mtime=m, by_symbol=by_sym, briefs=briefs)
    return _CACHE


def brief(symbol: str) -> dict | None:
    """The most recent research brief for `symbol` (context, not a signal), or None.
    Shape: {symbol, n_sources, titles[:3], age_h, llm_used}."""
    b = _load()["by_symbol"].get(_flat(symbol))
    if not b:
        return None
    srcs = b.get("sources") or []
    ts = b.get("ts") or b.get("generated")
    age_h = round((time.time() - float(ts)) / 3600, 1) if ts else None
    return {"symbol": _flat(symbol), "n_sources": b.get("n_sources", len(srcs)),
            "titles": [str(s.get("title") or "")[:100] for s in srcs[:3]],
            "age_h": age_h, "llm_used": bool(b.get("llm_used"))}


def recent(limit: int = 20) -> list[dict]:
    briefs = _load()["briefs"]
    rows = [{"symbol": _flat(b.get("symbol")), "n_sources": b.get("n_sources"),
             "llm_used": bool(b.get("llm_used")),
             "error": b.get("error")} for b in briefs if b.get("symbol")]
    return rows[-limit:][::-1]


def status() -> dict:
    d = _load()
    briefs = d["briefs"]
    return {"n_briefs": len(briefs), "n_symbols": len(d["by_symbol"]),
            "with_sources": sum(1 for b in briefs if (b.get("n_sources") or 0) > 0),
            "recent": recent(15)}
