"""Extracted brain HTTP routes (dashboard/server.py split — Wave0-⑤, first verified seam).

Each handler takes the live HTTP handler ``h`` (the dashboard's BaseHTTPRequestHandler instance)
and responds via ``h._send(...)`` — exactly as when the body lived inline in ``_do_GET_impl``.
The low-risk pattern: the dispatch line (``if path == "…":``) stays in server.py; only the body
moves here, so the 3777-line god-module shrinks group-by-group without restructuring the router.

Some bodies reference module-level helpers/globals that live in server.py (``_bg_snapshot``,
``_brain_agent``, ``_cached_body``, ``_EMBODIMENT_CACHE``…). server.py runs as ``__main__``
(``python dashboard/server.py``), so a plain ``from dashboard.server import …`` would import a
SECOND copy of the module with its own singletons/caches. ``_srv(h)`` resolves the *live* running
module off the handler instance instead, so those calls hit the exact same state as when inline.
"""
import json
import os
import sys


def _srv(h):
    """The live server module (the one actually serving), resolved off the handler instance.

    Handlers moved out of server.py still need its module-level helpers/globals; this returns the
    running module (``__main__`` in prod) so ``_srv(h)._bg_snapshot(...)`` / ``_srv(h)._cached_body(...)``
    hit the same caches the inline code did — never a duplicate import.
    """
    return sys.modules[h.__class__.__module__]


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
        {"key": "boss", "label": "Boss directives + R&D", "path": "/api/brain/ops", "real": True},
        {"key": "mind", "label": "Mind event bus", "path": "/api/brain/mind/events", "real": True},
        {"key": "agent", "label": "Brain agent", "path": "/api/brain/agent/status", "real": False},
        {"key": "autonomy", "label": "Self-coding autonomy", "path": "/api/brain/autonomy/status", "real": False},
        {"key": "memory", "label": "Human memory", "path": "/api/brain/memory/status", "real": False},
        {"key": "hybrid", "label": "Hybrid memory", "path": "/api/brain/hybrid/status", "real": False},
        {"key": "librarian", "label": "Librarian", "path": "/api/brain/librarian/status", "real": False},
        {"key": "stream", "label": "Stream of mind", "path": "/api/brain/stream/status", "real": False},
    ]
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_mind_events(h):
    """GET /api/brain/mind/events?since=<id> — the ULTRA Stream-of-Mind typed event bus
    (trading/brain/mind_events.py): problems / discoveries / trade-credit / research / learning /
    invention events, polled incrementally. Real events only, cross-process.
    """
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain import mind_events as _me
        q = parse_qs(urlparse(h.path).query)
        since_id = int((q.get("since") or ["0"])[0])
        out = {"events": _me.since(since_id) if since_id else _me.peek(80)[::-1],
               **_me.status()}
    except Exception as e:
        out = {"events": [], "error": f"{type(e).__name__}: {e}"[:160]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_agent_status(h):
    """GET /api/brain/agent/status — P4.1 LangGraph BrainAgent status: engine, has_memory,
    active LLM (or null offline), recall_k. Background snapshot (agent init is slow on first hit).
    """
    def _p_agent():
        return _srv(h)._brain_agent().status()
    return h._send(200, _srv(h)._bg_snapshot("agent", _p_agent), "application/json")


def handle_memory_status(h):
    """GET /api/brain/memory/status — P4.2 human-like memory (importance + Ebbinghaus decay,
    Letta tiers, auto_dream). OFFLINE deterministic demo snapshot, labelled demo.
    """
    try:
        from run_human_memory import build_demo_human_memory
        snap = build_demo_human_memory()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_human_memory.py over a stub "
                        "brain, injected clock); shows real HumanMemory dynamics — "
                        "decay/tiers/dream — not live brain memory")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "P4.2 human-like memory not importable (see memory/human_memory.py, "
                    "run_human_memory.py and ml-network-brain-ultra-blueprint.md §4).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_hybrid_status(h):
    """GET /api/brain/hybrid/status — P4.2 hybrid memory fusing GA stream + Letta tiers + mem0 +
    Ebbinghaus decay/auto_dream. OFFLINE deterministic demo snapshot, labelled demo.
    """
    try:
        from run_hybrid_memory import build_demo_hybrid_memory
        snap = build_demo_hybrid_memory()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_hybrid_memory.py over a stub "
                        "brain + stub LLM, injected clock); shows real HybridMemory "
                        "fusion — GA stream + Letta tiers + Ebbinghaus decay/dream — "
                        "not live brain memory")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "P4.2 hybrid memory not importable (see memory/hybrid_memory.py, "
                    "run_hybrid_memory.py and ml-network-brain-ultra-blueprint.md §4).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_librarian_status(h):
    """GET /api/brain/librarian/status — P4.3 self-feeding internet Librarian (discover/extract/
    dedup/ingest). OFFLINE deterministic demo snapshot, labelled demo.
    """
    try:
        from run_librarian import build_demo_librarian
        snap = build_demo_librarian()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_librarian.py over a stub "
                        "brain, injected stub web/arxiv sources + extractor); shows "
                        "real Librarian discover/feed/dedup — not live ingestion")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "P4.3 self-feeding Librarian not importable (see memory/librarian.py, "
                    "run_librarian.py and ml-network-brain-ultra-blueprint.md §4).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_quiz_status(h):
    """GET /api/brain/quiz/status — P4.4 self-quiz mastery (cloze self-test + FSRS mastery/
    retention curve). OFFLINE deterministic demo snapshot, labelled demo.
    """
    def _p_quiz():
        from run_self_quiz import build_demo_self_quiz
        snap = build_demo_self_quiz()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_self_quiz.py over a stub "
                        "brain, injected clock); shows the real FSRS-driven mastery "
                        "curve rising for a learning brain vs a flat never-learning "
                        "control — not live brain self-testing")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("quiz", _p_quiz), "application/json")


def handle_thinking_status(h):
    """GET /api/brain/thinking/status — P4.5 deliberate reasoning over memory (ReAct/ToT + pymdp
    active inference + pyDatalog/DoWhy + conformal abstention + NeMo constitution). Demo snapshot.
    """
    def _p_thinking():
        from run_thinking_p45 import build_demo_thinking
        snap = build_demo_thinking()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_thinking_p45.py over a stub "
                        "brain): real ReAct/ToT reasoning + pymdp surprise/curiosity + "
                        "pyDatalog/DoWhy reasoning + conformal abstention + NeMo "
                        "constitution — answers when confident, abstains + escalates "
                        "when not; not live brain reasoning")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("thinking", _p_thinking), "application/json")


def handle_stream_status(h):
    """GET /api/brain/stream/status — P4.6 Stream-of-Mind (think-cycle → thought stream → Global
    Workspace consolidation to long-term memory; Langfuse trace). Demo snapshot, labelled demo.
    """
    def _p_stream():
        from run_stream_of_mind import build_demo_thinking
        snap = build_demo_thinking()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_stream_of_mind.py over a stub "
                        "brain): real Thinker think-cycle → thought stream → Global "
                        "Workspace consolidation to long-term memory; live panel streams "
                        "via AG-UI (POST /api/agui). Langfuse offline no-op unless keys set")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("stream", _p_stream), "application/json")


def handle_boss(h):
    """GET /api/brain/boss — Boss command engine: directives in force + R&D inventions. NOT named
    */status on purpose (that suffix hits the 8s dispatch cache; this must reflect a just-executed
    boss command immediately via a cheap state-file read).
    """
    try:
        from trading.brain import boss as _boss
        from trading.brain import rnd as _rnd
        out = {"ok": True, "directives": _boss.directives(), "rnd": _rnd.status()}
        out["directives"].pop("history", None)
    except Exception as e:
        out = {"ok": False, "error": f"{type(e).__name__}: {e}"[:160]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_autonomy_status(h):
    """GET /api/brain/autonomy/status — P4.7 autonomy + self-coding (propose→sandbox→benchmark-gate
    →admit; safety gate rejects malicious specs). OFFLINE deterministic demo snapshot.
    """
    def _p_autonomy():
        from run_self_coding_p47 import build_demo_self_coding
        snap = build_demo_self_coding()
        snap["demo"] = True
        snap["note"] = ("offline deterministic demo (run_self_coding_p47.py): real "
                        "propose→sandbox→benchmark-gate→admit loop over golden data; "
                        "shows the rising best-score curve + the safety gate rejecting a "
                        "malicious spec without running it. No network, no LLM")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("autonomy", _p_autonomy), "application/json")


def handle_embodiment_status(h):
    """GET /api/brain/embodiment/status — P4.8 multimodal + identity + society + affect (see/hear/
    speak + GoEmotions mood + internal debate + Letta identity). Computed in a SUBPROCESS (~4GB of
    real models load in a child that exits) and cached on the live server module. First call slow.
    """
    srv = _srv(h)
    try:
        if srv._EMBODIMENT_CACHE is None:
            import subprocess
            import sys as _sys
            proc = subprocess.run([_sys.executable, "run_embodiment_p48.py", "--json"],
                                  capture_output=True, text=True, timeout=300, cwd=os.getcwd())
            srv._EMBODIMENT_CACHE = json.loads(proc.stdout.strip().splitlines()[-1])
        snap = dict(srv._EMBODIMENT_CACHE)
        snap["demo"] = True
        snap["note"] = ("REAL models active (see/hear/speak + GoEmotions mood + internal "
                        "debate + persistent Letta identity), computed in a subprocess and "
                        "cached. run_embodiment_p48.py for the live CLI demo")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "P4.8 embodiment not importable (see cognition/embodiment.py, "
                    "cognition/{affect,identity,society,multimodal}.py, run_embodiment_p48.py).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_activity(h):
    """GET /api/brain/activity — ephemeral transparency feed (what the autonomous web agent did +
    learned). GET drains (marks viewed → disappears); ?peek=1 to look without clearing.
    """
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain import activity_feed as _af
        qs = parse_qs(urlparse(h.path).query)
        events = _af.peek() if qs.get("peek") else _af.drain()
        body = json.dumps({"events": events, "status": _af.status()}, default=str).encode()
    except Exception as e:
        body = json.dumps({"events": [], "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_learning(h):
    """GET /api/brain/learning — brain self-learning + web panel feed: knowledge stats + what it's
    learned + ephemeral web-activity + pending credential requests. Read-only aggregate (6s cache).
    """
    def _p_learning():
        out = {}
        try:
            from trading.brain.learner import get_learner
            out["learner"] = get_learner().status()
        except Exception as e:
            out["learner"] = {"error": f"{type(e).__name__}: {e}"[:120]}
        try:
            from trading.brain import activity_feed as _af
            out["activity"] = _af.peek(30)
        except Exception:
            out["activity"] = []
        try:
            from trading.brain.credentials import get_vault
            out["pending_logins"] = get_vault().pending()
        except Exception:
            out["pending_logins"] = []
        try:
            from trading.brain.learn_loop import get_learn_loop
            out["loop"] = get_learn_loop().status()
        except Exception:
            out["loop"] = {"enabled": False, "running": False}
        return json.dumps(out, default=str).encode()
    return h._send(200, _srv(h)._cached_body("brain/learning", 6.0, _p_learning),
                   "application/json")
