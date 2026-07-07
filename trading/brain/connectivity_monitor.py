"""trading/brain/connectivity_monitor.py — a light, always-on wiring watchdog.

The owner asked for a self-healing connectivity check so a module never silently disconnects again
(like the trade_columns orphan an audit just caught). This is a FAST stdlib scan (no grimp/vulture
needed) surfaced on the dashboard: it finds Python modules that nothing imports (orphans) and API
routes that no dashboard panel calls (dead endpoints). Report-only — it flags, it never edits.

Cheap enough to run each dashboard poll (cached ~60s) or from the learn loop."""
from __future__ import annotations

import os
import re
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_CACHE: dict = {}
_TTL_S = 60.0

# modules that are ENTRYPOINTS by design (run via `python -m`, cron, or CLI) — not orphans
_ENTRYPOINT_HINT = re.compile(r"run_|_loop|launch|^main|cli|monitor|snapshot|^tools", re.I)


def _py_files(sub: str) -> list:
    out = []
    for base, _dirs, files in os.walk(os.path.join(_ROOT, sub)):
        if any(skip in base for skip in ("__pycache__", "vendor", "node_modules", ".venv",
                                         "tests", "research")):
            continue
        for f in files:
            if f.endswith(".py") and f != "__init__.py":
                out.append(os.path.join(base, f))
    return out


def scan_async() -> dict:
    """NON-BLOCKING: return the cached report immediately; if stale/absent, kick a background
    thread to recompute. Used by the dashboard GET so the ~20s file walk NEVER blocks a request
    (which was causing 14s page loads). The learn loop also calls scan() periodically."""
    now = time.time()
    cached = _CACHE.get("report")
    fresh = _CACHE.get("ts") and now - _CACHE["ts"] < _TTL_S
    if not fresh and not _CACHE.get("_scanning"):
        _CACHE["_scanning"] = True
        import threading

        def _bg():
            try:
                scan(force=True)
            finally:
                _CACHE["_scanning"] = False
        threading.Thread(target=_bg, daemon=True, name="connectivity-scan").start()
    if cached:
        return cached
    return {"module_count": None, "backlog_orphans": None, "backlog_dead_endpoints": None,
            "new_orphans": [], "new_dead_endpoints": [], "orphans_sample": [],
            "healthy": True, "scanning": True, "checked_at": now}


def scan(*, force: bool = False) -> dict:
    """Return {orphans, dead_endpoints, module_count, healthy}. Cached ~60s. BLOCKING (~20s cold) —
    callers on a request thread must use scan_async() instead."""
    now = time.time()
    if not force and _CACHE.get("ts") and now - _CACHE["ts"] < _TTL_S:
        return _CACHE["report"]
    trading_files = _py_files("trading")
    # collect only the IMPORT lines across the whole tree (cheap + precise)
    import_lines = []
    for f in trading_files + _py_files("dashboard") + _py_files("core"):
        try:
            for ln in open(f, encoding="utf-8", errors="ignore"):
                s = ln.strip()
                if s.startswith(("import ", "from ")) or "import_module(" in s:
                    import_lines.append((f, s))
        except Exception:
            continue
    import_blob = "\n".join(s for _f, s in import_lines)
    orphans = []
    for f in trading_files:
        stem = os.path.splitext(os.path.basename(f))[0]
        if _ENTRYPOINT_HINT.search(stem):
            continue
        # CONSERVATIVE: orphan only if the module's stem appears in NO import line ANYWHERE except
        # its own file's imports (covers `from a.b import stem`, `from a.b.stem import`, `import
        # a.b.stem`, `import_module("a.b.stem")`). Heuristic — the grimp-based /independent-audit
        # is the source of truth; this is the always-on early-warning surfaced on the dashboard.
        ext = "\n".join(s for ff, s in import_lines if ff != f)
        if not re.search(rf"\b{re.escape(stem)}\b", ext):
            orphans.append(os.path.relpath(f, _ROOT))
    # API routes (server.py) that no panel calls
    dead_endpoints = []
    try:
        server = open(os.path.join(_ROOT, "dashboard", "server.py"),
                      encoding="utf-8", errors="ignore").read()
        routes = set(re.findall(r'path == "(/api/trading/[a-z_]+)"', server))
        web = ""
        webdir = os.path.join(_ROOT, "dashboard", "web", "src")
        for base, _d, files in os.walk(webdir):
            for f in files:
                if f.endswith((".jsx", ".js")):
                    web += open(os.path.join(base, f), encoding="utf-8",
                                errors="ignore").read() + "\n"
        for r in sorted(routes):
            if r not in web:
                dead_endpoints.append(r)
    except Exception:
        pass
    # BASELINE tracking (the self-healing value): the project has a known orphan backlog; what
    # matters is a module that WAS wired becoming unwired. Compare vs the recorded baseline and
    # surface only the NEW orphans/dead-endpoints as regressions.
    from trading import state
    base = state.load_json("connectivity_baseline.json", {})
    if not base.get("orphans") and not base.get("_set"):     # first run → record the current backlog
        base = {"orphans": sorted(orphans), "dead_endpoints": dead_endpoints, "_set": True,
                "ts": now}
        state.save_json("connectivity_baseline.json", base)
    base_orphans = set(base.get("orphans", []))
    base_dead = set(base.get("dead_endpoints", []))
    new_orphans = sorted(set(orphans) - base_orphans)
    new_dead = sorted(set(dead_endpoints) - base_dead)
    report = {"module_count": len(trading_files),
              "backlog_orphans": len(orphans), "backlog_dead_endpoints": len(dead_endpoints),
              "new_orphans": new_orphans, "new_dead_endpoints": new_dead,
              "orphans_sample": sorted(orphans)[:20],
              "healthy": not new_orphans and not new_dead,   # green unless something NEWLY broke
              "checked_at": now}
    _CACHE.update(ts=now, report=report, _full_orphans=sorted(orphans),
                  _full_dead=dead_endpoints)
    if new_orphans or new_dead:                              # only alert on a REGRESSION
        try:
            from trading.brain import mind_events
            mind_events.emit("problem",
                             f"Connectivity REGRESSION: {len(new_orphans)} newly-orphaned "
                             f"module(s), {len(new_dead)} newly-dead endpoint(s) — wire them",
                             salience=0.7, data={"new_orphans": new_orphans,
                                                 "new_dead_endpoints": new_dead})
        except Exception:
            pass
    return report


def rebaseline() -> dict:
    """Accept the current wiring as the new baseline (after intentionally removing a module)."""
    from trading import state
    scan(force=True)
    state.save_json("connectivity_baseline.json",
                    {"orphans": _CACHE.get("_full_orphans", []),
                     "dead_endpoints": _CACHE.get("_full_dead", []),
                     "_set": True, "ts": time.time()})
    return {"rebaselined": True, "orphans_baselined": len(_CACHE.get("_full_orphans", []))}


if __name__ == "__main__":
    import json
    print(json.dumps(scan(force=True), indent=2))
