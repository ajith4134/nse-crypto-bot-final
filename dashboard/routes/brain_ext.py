"""Extracted brain HTTP routes (dashboard/server.py split — Wave0-⑤, first verified seam).

Each handler takes the live HTTP handler ``h`` (the dashboard's BaseHTTPRequestHandler instance)
and responds via ``h._send(...)`` — exactly as when the body lived inline in ``_do_GET_impl``.
The low-risk pattern: the dispatch line (``if path == "…":``) stays in server.py; only the body
moves here, so the 3777-line god-module shrinks group-by-group without restructuring the router.
"""
import json


def handle_ops(h):
    """GET /api/brain/ops — Brain-Ops overview: real boss/R&D/mind-bus stats + an honest
    real/demo catalog of the heavier brain subsystems (each fetched per-tile). Never fabricated.
    """
    out = {"live": {}, "subsystems": []}
    try:
        from trading.brain import boss as _boss
        from trading.brain import rnd as _rnd
        from trading.brain import mind_events as _me
        d = _boss.directives()
        if isinstance(d, dict):
            d.pop("history", None)
        out["live"] = {"boss": d, "rnd": _rnd.status(), "mind_bus": _me.status()}
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"[:160]
    out["subsystems"] = [
        {"key": "boss", "label": "Boss directives + R&D", "path": "/api/brain/boss/status", "real": True},
        {"key": "mind", "label": "Mind event bus", "path": "/api/brain/mind/events", "real": True},
        {"key": "agent", "label": "Brain agent", "path": "/api/brain/agent/status", "real": False},
        {"key": "autonomy", "label": "Self-coding autonomy", "path": "/api/brain/autonomy/status", "real": False},
        {"key": "memory", "label": "Human memory", "path": "/api/brain/memory/status", "real": False},
        {"key": "hybrid", "label": "Hybrid memory", "path": "/api/brain/hybrid/status", "real": False},
        {"key": "librarian", "label": "Librarian", "path": "/api/brain/librarian/status", "real": False},
        {"key": "stream", "label": "Stream of mind", "path": "/api/brain/stream/status", "real": False},
    ]
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")
