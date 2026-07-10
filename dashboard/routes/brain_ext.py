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


def _state_json(name, default):
    """Cheap live-state read for the P4.x status routes (state-file-only rule: request
    threads never heavy-import or call LLMs — see memory dashboard-524-wedge)."""
    try:
        from trading import state as tstate
        return tstate.load_json(name, default)
    except Exception:
        return default


def handle_memory_status(h):
    """GET /api/brain/memory/status — P4.2 memory. LIVE-FIRST (2026-07-10): the brain's real
    persisted memory (associative notes + FinMem decision episodes + meta-articles); the old
    deterministic demo snapshot only when those stores are empty (labelled demo)."""
    try:
        notes = _state_json("associative_notes.json", {}) or {}
        eps = _state_json("decision_episodes.json", {}) or {}
        arts = _state_json("meta_articles.json", []) or []
        n_notes = len(notes.get("notes", notes) if isinstance(notes, dict) else notes)
        n_eps = len(eps.get("episodes", eps) if isinstance(eps, dict) else eps)
        n_arts = len(arts if isinstance(arts, list) else arts.get("articles", []))
        if n_notes or n_eps:
            body = json.dumps({
                "demo": False, "live": True,
                "tiers": {"associative_notes": n_notes,
                          "decision_episodes": n_eps,
                          "meta_articles": n_arts},
                "note": ("LIVE brain memory stores (trading/state): A-MEM associative "
                         "notes + FinMem decision episodes + learned meta-articles"),
            }, default=str).encode()
            return h._send(200, body, "application/json")
        from run_human_memory import build_demo_human_memory
        snap = build_demo_human_memory()
        snap["demo"] = True
        snap["note"] = ("live memory stores empty — offline deterministic demo "
                        "(run_human_memory.py); shows HumanMemory dynamics, not live memory")
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
        # LIVE-FIRST (2026-07-10): the fused view of the real stores + mind-event stream.
        me = _state_json("mind_events.json", []) or []
        events = me.get("events", me) if isinstance(me, dict) else me
        notes = _state_json("associative_notes.json", {}) or {}
        n_notes = len(notes.get("notes", notes) if isinstance(notes, dict) else notes)
        log = _state_json("learning_log.json", {}) or {}
        learned = log.get("learned") or []
        if n_notes or events:
            body = json.dumps({
                "demo": False, "live": True,
                "fusion": {"associative_notes": n_notes,
                           "mind_events": len(events),
                           "learned_topics": len(learned)},
                "latest_event": (events[-1] if events else None),
                "note": "LIVE hybrid view: A-MEM notes + mind-event stream + learn log",
            }, default=str).encode()
            return h._send(200, body, "application/json")
        from run_hybrid_memory import build_demo_hybrid_memory
        snap = build_demo_hybrid_memory()
        snap["demo"] = True
        snap["note"] = ("live stores empty — offline deterministic demo "
                        "(run_hybrid_memory.py); not live brain memory")
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
        # LIVE-FIRST (2026-07-10): the learn-loop IS the working librarian — real arXiv
        # papers + web articles ingested into the persistent KnowledgeBrain every cycle.
        ll = _state_json("learn_loop.json", {}) or {}
        arts = _state_json("meta_articles.json", []) or []
        done = ll.get("done") or []
        if done:
            body = json.dumps({
                "demo": False, "live": True,
                "cycles": ll.get("cycles"), "topics_ingested": len(done),
                "articles": len(arts if isinstance(arts, list) else []),
                "last_topic": ll.get("last"),
                "queue": ll.get("queue") or [],
                "note": ("LIVE librarian = continuous learn-loop (papers+articles → "
                         "KnowledgeBrain each cycle; trading/brain/learn_loop.py)"),
            }, default=str).encode()
            return h._send(200, body, "application/json")
        from run_librarian import build_demo_librarian
        snap = build_demo_librarian()
        snap["demo"] = True
        snap["note"] = ("learn-loop has no cycles yet — offline deterministic demo "
                        "(run_librarian.py); not live ingestion")
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
    # LIVE path inline (2026-07-10): cheap state-file read — must NOT queue behind the
    # serial snapshot warmer (a dashboard restart parked it "warming" for many minutes
    # behind the ultra producer). Only the heavy demo builder stays behind _bg_snapshot.
    ll = _state_json("learn_loop.json", {}) or {}
    ev = ll.get("last_eval") or {}
    if ev.get("final_retention") is not None:
        body = json.dumps({"demo": False, "live": True,
                           "retention": ev.get("final_retention"),
                           "rising": ev.get("rising"), "eval_ts": ev.get("ts"),
                           "cycles": ll.get("cycles"),
                           "topics_done": len(ll.get("done") or []),
                           "note": ("LIVE FSRS self-evaluation from the continuous "
                                    "learn-loop (retention over recently-learned "
                                    "topics)")}, default=str).encode()
        return h._send(200, body, "application/json")

    def _p_quiz():
        from run_self_quiz import build_demo_self_quiz
        snap = build_demo_self_quiz()
        snap["demo"] = True
        snap["note"] = ("no live FSRS eval yet — offline deterministic demo "
                        "(run_self_quiz.py); not live brain self-testing")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("quiz", _p_quiz), "application/json")


def handle_thinking_status(h):
    """GET /api/brain/thinking/status — P4.5 deliberate reasoning over memory (ReAct/ToT + pymdp
    active inference + pyDatalog/DoWhy + conformal abstention + NeMo constitution). Demo snapshot.
    """
    # LIVE path inline (cheap state reads — never behind the serial warmer)
    hyp = _state_json("hypotheses.json", {}) or {}
    n_hyp = len(hyp.get("hypotheses", hyp) if isinstance(hyp, dict) else hyp)
    ab = _state_json("uq_abstentions.json", {}) or {}
    n_ab = len(ab.get("abstentions", ab) if isinstance(ab, dict) else ab)
    if n_hyp or n_ab:
        body = json.dumps({"demo": False, "live": True,
                           "hypotheses": n_hyp, "abstentions": n_ab,
                           "uq_calibration": _state_json("uq_calibration.json", {}) or {},
                           "note": ("LIVE deliberation: hypothesis ledger + conformal-UQ "
                                    "abstention log (answers when confident, abstains "
                                    "when not)")}, default=str).encode()
        return h._send(200, body, "application/json")

    def _p_thinking():
        from run_thinking_p45 import build_demo_thinking
        snap = build_demo_thinking()
        snap["demo"] = True
        snap["note"] = ("no live deliberation artifacts yet — offline deterministic demo "
                        "(run_thinking_p45.py); not live brain reasoning")
        return snap
    return h._send(200, _srv(h)._bg_snapshot("thinking", _p_thinking), "application/json")


def handle_stream_status(h):
    """GET /api/brain/stream/status — P4.6 Stream-of-Mind (think-cycle → thought stream → Global
    Workspace consolidation to long-term memory; Langfuse trace). Demo snapshot, labelled demo.
    """
    # LIVE path inline (cheap state read — never behind the serial warmer)
    me = _state_json("mind_events.json", []) or []
    events = me.get("events", me) if isinstance(me, dict) else me
    if events:
        kinds: dict = {}
        for e in events:
            k = (e.get("kind") or e.get("type") or "event") if isinstance(e, dict) else "event"
            kinds[k] = kinds.get(k, 0) + 1
        body = json.dumps({"demo": False, "live": True,
                           "n_events": len(events), "kinds": kinds,
                           "tail": events[-25:],
                           "note": ("LIVE stream of mind — the brain's mind-event bus "
                                    "(mind_events.json)")}, default=str).encode()
        return h._send(200, body, "application/json")

    def _p_stream():
        from run_stream_of_mind import build_demo_thinking
        snap = build_demo_thinking()
        snap["demo"] = True
        snap["note"] = ("mind-event bus empty — offline deterministic demo "
                        "(run_stream_of_mind.py); not live thoughts")
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
    # LIVE path inline (cheap state reads — never behind the serial warmer)
    se = _state_json("self_evolve.json", {}) or {}
    rv = _state_json("rule_versions.json", []) or []
    n_rules = len(rv if isinstance(rv, list) else rv.get("versions", []))
    if se or n_rules:
        body = json.dumps({"demo": False, "live": True,
                           "self_evolve": {k: se.get(k) for k in
                                           ("generations", "evaluated", "best", "ts")
                                           if isinstance(se, dict) and k in se} or se,
                           "rule_versions": n_rules,
                           "note": ("LIVE autonomy: self-evolve generation state + "
                                    "versioned rule changes "
                                    "(trading/state/rule_versions.json)")},
                          default=str).encode()
        return h._send(200, body, "application/json")

    def _p_autonomy():
        from run_self_coding_p47 import build_demo_self_coding
        snap = build_demo_self_coding()
        snap["demo"] = True
        snap["note"] = ("no live self-modification state yet — offline deterministic "
                        "demo (run_self_coding_p47.py)")
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


def handle_worldmodel(h):
    """GET /api/brain/worldmodel — World-Model + Imagination (MuZero MCTS): roll a LEARNED market
    dynamics model forward and plan entry/direction/stoploss/profit-trailing in imagined R BEFORE
    acting (reuse-first from vendor/muzero_general). Heavy → served via the background snapshot
    warmer. Live OHLCV when available, else a deterministic synthetic series so the panel renders.
    """
    def _p_worldmodel():
        import numpy as _np
        import pandas as _pd
        from trading.brain.worldmodel import build_planner, register_world_model
        ohlcv = None
        try:                                     # prefer a live recent series
            from trading.online.live_loop import get_loop
            ohlcv = get_loop().recent_ohlcv()    # may not exist on all builds
        except Exception:
            ohlcv = None
        if ohlcv is None or len(ohlcv) < 60:     # REAL ccxt BTC series (not synthetic)
            try:
                import brain_live
                ohlcv = brain_live._real_ohlcv("BTC/USDT", "5m", 260)
            except Exception:
                ohlcv = None
        demo = ohlcv is None or len(ohlcv) < 60
        if demo:                                 # deterministic synthetic uptrend+noise
            rng = _np.random.default_rng(7); n = 260
            ret = rng.normal(0.0004, 0.01, n) + 0.002 * _np.sin(_np.arange(n) / 15)
            close = 100 * _np.exp(_np.cumsum(ret))
            hi = close * (1 + _np.abs(rng.normal(0, 0.004, n)))
            lo = close * (1 - _np.abs(rng.normal(0, 0.004, n)))
            ohlcv = _pd.DataFrame({"open": close, "high": hi, "low": lo,
                                   "close": close, "volume": rng.uniform(1e3, 9e3, n)})
        node = register_world_model()            # dashboard-sync: appears in node graph
        planner = build_planner(ohlcv, num_simulations=64, horizon=12)
        entry_plan = planner.plan(ohlcv)
        manage_plan = planner.plan(ohlcv, position_side="LONG")
        return {
            "node": {"name": node.name, "kind": node.kind, "summary": node.summary},
            "backend": entry_plan["backend"],
            "actions": ["HOLD", "ENTER_LONG", "ENTER_SHORT", "EXIT",
                        "TIGHTEN_STOP", "SCALE_OUT"],
            "entry_decision": entry_plan,
            "manage_decision": manage_plan,
            "demo": demo,
            "note": ("learned market world-model (torch MuZero-FC, numpy-ridge "
                     "fallback) + MCTS imagination over trade actions. 'entry_decision' "
                     "plans entry/direction from a flat book; 'manage_decision' plans "
                     "exit/stop-tighten/scale-out for an open long. imagined_R is the "
                     "MCTS value (R-multiples) per action. demo=true → synthetic series."),
        }
    return h._send(200, _srv(h)._bg_snapshot("worldmodel", _p_worldmodel), "application/json")


def handle_hypotheses(h):
    """GET /api/brain/hypotheses — HypothesisLedger (AI-Scientist loop): propose→experiment→
    Bayesian-credence→confirm/refute trading hypotheses over the REAL closed-trade journal.
    Falls back to a deterministic demo set of trades so the panel renders before the live journal
    has enough closed trades.
    """
    try:
        from trading.brain.hypothesis import (HypothesisLedger,
                                              register_hypothesis_ledger)
        trades = []
        try:
            from trading.journal.journal import TradeJournal
            jr = TradeJournal(state_file="journal.json", persist=True)
            trades = [t.to_dict() for t in jr.trades]
        except Exception:
            trades = []
        demo = len(trades) < 16
        if demo:                                 # deterministic synthetic journal
            import numpy as _np
            rng = _np.random.default_rng(3)
            trades = []
            for i in range(120):
                regime = "Trending" if i % 2 else "Ranging"
                direction = "LONG" if rng.random() < 0.6 else "SHORT"
                edge = 0.6 if (regime == "Trending" and direction == "LONG") else -0.05
                r = float(rng.normal(edge, 1.0))
                trades.append({"trade_id": str(i), "symbol": "BTC/USDT",
                               "market": "CRYPTO", "direction": direction,
                               "market_regime_entry": regime, "r_multiple": r,
                               "net_pnl": r * 100,
                               "brain_confidence_entry": float(rng.random()),
                               "strategy_name": "demo"})
        # persist=False on demo so a synthetic run never pollutes the live ledger
        led = HypothesisLedger(persist=not demo)
        summary = led.run_cycle(trades, seed=1)
        register_hypothesis_ledger(led)          # dashboard-sync: node graph
        body = json.dumps({
            "ledger": led.to_json(),
            "summary": {"n_hypotheses": summary["n_hypotheses"],
                        "confirmed": summary["confirmed"],
                        "refuted": summary["refuted"], "open": summary["open"],
                        "insights": summary["insights"]},
            "n_trades": len(trades), "demo": demo,
            "note": ("brain's research notebook: each hypothesis is split-tested on "
                     "the closed-trade journal (Bayesian Beta-Binomial A/B on win-rate "
                     "+ Welch t on R), confirmed→insight notes, refuted→failure DB. "
                     "demo=true → synthetic journal until ≥16 real closed trades."),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "hypothesis loop via trading/brain/hypothesis.py (HypothesisLedger).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_evolve(h):
    """GET /api/brain/evolve — self-evolving strategy loop: evolve → admit guardrail-passed winners
    into the growing SkillLibrary → compound. Genetic engine gated OFF this phase (library-first);
    runs a FORCED offline demo over a synthetic series + reports the real gate status honestly.

    _bg_snapshot, NOT inline: the demo runs DEAP GP evolution + dozens of vectorbt backtests
    (~minutes of GIL-bound compute). Inline, a UI polling burst after each restart put 10+ handler
    threads into backtests and 503-wedged the whole server for ~10 min (2026-07-03). The warmer
    builds it ONCE, serially.
    """
    try:
        def _p_evolve():
            import numpy as _np
            import pandas as _pd
            from trading.strategy.control import evolution_enabled
            from trading.strategy.self_evolve import (SelfEvolvingLoop,
                                                      register_self_evolve)
            rng = _np.random.default_rng(5); n = 360
            ret = rng.normal(0.0006, 0.012, n) + 0.003 * _np.sin(_np.arange(n) / 18)
            close = 100 * _np.exp(_np.cumsum(ret))
            ohlcv = _pd.DataFrame({"open": close,
                                   "high": close * (1 + _np.abs(rng.normal(0, 0.004, n))),
                                   "low": close * (1 - _np.abs(rng.normal(0, 0.004, n))),
                                   "close": close, "volume": rng.uniform(1e3, 9e3, n)})
            # persist=False so the demo never writes to the live library/history
            loop = SelfEvolvingLoop(persist=False)
            run = loop.run_generation(ohlcv, market="CRYPTO", generations=4,
                                      pop_size=14, seed=5, force=True)
            register_self_evolve(loop)           # dashboard-sync: node graph
            # LIVE state: the REAL persisted library the brain-loop breeds into + which bred
            # survivor is currently wired into the pipeline (honest — no demo numbers here).
            try:
                from trading.strategy.evolved_link import status as _evo_live
                live = _evo_live()
            except Exception as e:
                live = {"error": f"{type(e).__name__}: {e}"[:160]}
            return json.dumps({
                "gate_enabled": evolution_enabled(),  # real production gate status
                "demo_forced": True,
                "live": live,                         # armed engine + persisted library + best/market
                "run": {k: run.get(k) for k in ("ran", "evaluated", "promoted",
                                                "admitted", "best_score", "pbo",
                                                "gen_history", "admitted_skills")},
                "library": run.get("library"),
                "status": loop.status(),
                "note": ("lifelong loop (trading/strategy/self_evolve.py): DEAP NSGA-II "
                         "evolves a population → guardrail-passed survivors are admitted "
                         "into the persisted SkillLibrary (Voyager-style growth) → "
                         "reevaluate() retires stale skills. `live` shows the REAL armed "
                         "engine + persisted library the brain-loop breeds into and the "
                         "survivor now wired into the pipeline; `run`/`library` above are a "
                         "forced offline demo on synthetic data."),
            }, default=str).encode()
        body = _srv(h)._bg_snapshot("brain/evolve", _p_evolve)
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "self-evolving loop via trading/strategy/self_evolve.py.",
        }).encode()
    return h._send(200, body, "application/json")


def handle_generators(h):
    """GET /api/trading/generators — the live Strategy-Generator Portfolio.

    Honest view of trading/strategy/generators: the DEAP evolver + the SOTA generators
    (LLM-mutation, gplearn+PySR symbolic regression, pyribs quality-diversity, formulaic-alpha
    mining, Optuna, RD-Agent), whether evolution is armed, and the REAL persisted SkillLibrary
    grouped BY the generator that bred each admitted strategy (skill.source). No demo numbers —
    everything here is read from the shared library the brain-loop breeds into and the brain
    trades from (via trading.strategy.evolved_link)."""
    try:
        # STATE-FILE-ONLY (2026-07-07, py-spy-proven): building the portfolio here imported
        # DEAP/pyribs inside a request thread → threadpoolctl .so scan under the import lock
        # → whole server wedged (524 pattern). The BREEDER process (autoresearch daemon /
        # any evolved_link.breed caller) persists this payload via persist_dashboard_status.
        from trading import state as _state
        st = _state.load_json("generators_status.json", {})
        if st:
            body = json.dumps({
                "available": True, **st,
                "note": ("Strategy-Generator Portfolio (trading/strategy/generators): every "
                         "generator feeds ONE CPCV+Deflated-Sharpe+PBO + family-wise gate → "
                         "the SkillLibrary → the brain pipeline. Snapshot persisted by the "
                         "breeder process each research cycle."),
            }, default=str).encode()
        else:
            from trading.strategy.control import evolution_enabled
            body = json.dumps({
                "available": True, "enabled": bool(evolution_enabled()),
                "generators": [], "n_generators": 0, "best_by_market": {},
                "library": {}, "by_generator": {},
                "note": ("No research cycle has persisted a snapshot yet — the autoresearch "
                         "daemon (python -m trading.strategy.run_autoresearch) writes it "
                         "each cycle."),
            }).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "strategy-generator portfolio via trading/strategy/generators/portfolio.py.",
        }).encode()
    return h._send(200, body, "application/json")


def handle_researcher(h):
    """GET /api/trading/researcher — the LIVE Trading-Researcher view (invent-beyond #5).

    Real state only: autoresearch driver cycles/totals/liveness (autoresearch.json),
    W5 champion/challenger lineage per market (champion_lineage.json), the look-ahead
    leak-tripwire rejection log, and the shared SkillLibrary size. driver.live=false is
    an honest 'the daemon is not running' — never a demo number."""
    try:
        from trading.strategy.autoresearch import status as _rstatus
        body = json.dumps({"available": True, **_rstatus()}, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "live autoresearch via trading/strategy/autoresearch.py "
                    "(daemon: python -m trading.strategy.run_autoresearch).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_goal_score(h):
    """GET /api/trading/goal — W1 goal scoreboard (owner goal 2026-07-07): every configured
    market/segment scored over the trailing 30 days against trading/goal.yaml (return vs
    target, drawdown vs limit, Sharpe vs bar, failure line) with an honest verdict.
    ?refresh=1 recomputes from the journal; default serves the persisted snapshot."""
    import json as _json
    from urllib.parse import parse_qs, urlparse

    from trading import goal
    try:
        q = parse_qs(urlparse(h.path).query)
        if q.get("refresh", ["0"])[0] in ("1", "true"):
            snap = goal.scoreboard()
        else:
            snap = goal.last_scoreboard() or goal.scoreboard()
        body = _json.dumps(snap).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_surface(h):
    """GET /api/trading/surface — W2 scientific-method rails: parameter-ownership map,
    optimizer modes (read_only|live), one-variable-only window, versioned rule changes
    (old→new + evidence + reason) and refused writes. POST via ops to flip modes."""
    import json as _json

    from trading.brain import surface
    try:
        body = _json.dumps(surface.status()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_evidence(h):
    """GET /api/trading/evidence — W3 evidence lane: blind-baseline vs brain, skip
    counterfactuals (good-skip / missed-winner), per-segment autonomy gates (earn-live
    checklist) and blow-up watchdogs (fee bleed, frozen activity)."""
    import json as _json

    from trading import evidence
    try:
        body = _json.dumps(evidence.status()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_ui_data(h):
    """GET /api/trading/ui_data — UI-only data mode: the eyes' per-symbol candle
    coverage (symbols, timeframes, freshness, hit-rate) + whether the mode is enabled.
    The owner flips UI_ONLY_DATA=1 once this shows warm coverage."""
    import json as _json

    from trading import state
    from trading.broker_sense import ui_data
    try:
        cov = ui_data.coverage()
        if cov.get("keys", 0) == 0:                    # this process may not host the eyes
            snap = state.load_json("ui_data_coverage.json", {})
            if snap:
                snap["note"] = "cross-process snapshot (eyes live in the funnel process)"
                cov = snap
        body = _json.dumps(cov).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_scouts(h):
    """GET /api/trading/scouts — W4 smart-money scout swarm: per-scout signal counts in
    the Delphi window, recent consensus events (Sophie fires only on multi-scout
    agreement), min-agree/window config. Ross dispatches alerts; never trades."""
    import json as _json

    from trading import scouts
    try:
        body = _json.dumps(scouts.status()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_track_record(h):
    """GET /api/trading/track_record — W7 report card: per-actor (strategy/scout/
    optimizer/node) runs, win-rate, supervised successes, rule-of-three status, trust
    weight and cost — trust follows the accumulated record, not the code."""
    import json as _json

    from trading.brain import track_record
    try:
        body = _json.dumps(track_record.report_card()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_briefing(h):
    """GET /api/trading/briefing — W8 daily morning brief (regime gate → watchdogs →
    open positions → smart-money setups → stance + sizing math from goal.yaml), every
    number with provenance. ?generate=1 rebuilds now; default serves today's."""
    import json as _json
    from urllib.parse import parse_qs, urlparse

    from trading.brain import briefing
    try:
        q = parse_qs(urlparse(h.path).query)
        if q.get("generate", ["0"])[0] in ("1", "true"):
            body = _json.dumps(briefing.generate(deliver=False)).encode()
        else:
            body = _json.dumps(briefing.latest() or
                               {"note": "no brief yet today — ?generate=1"}).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_connectivity(h):
    """GET /api/trading/connectivity — #13: per-feature PRESENT/MISSING proof over the
    newest real entries + closed rows (does every capability actually fire on trades?).
    ?refresh=1 recomputes."""
    import json as _json
    from urllib.parse import parse_qs, urlparse

    from trading import state
    from trading.connectivity_check import check
    try:
        q = parse_qs(urlparse(h.path).query)
        if q.get("refresh", ["0"])[0] in ("1", "true"):
            body = _json.dumps(check()).encode()
        else:
            body = _json.dumps(state.load_json("connectivity_check.json", {})
                               or check()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_curiosity(h):
    """GET /api/trading/curiosity — invent-beyond #1: data fields the eyes discovered on
    broker pages, ranked by curiosity (novelty × cross-symbol informativeness), and the
    last auto-harvest into trade columns."""
    import json as _json

    from trading.broker_sense import curiosity
    try:
        body = _json.dumps(curiosity.status()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_ui_health(h):
    """GET /api/trading/ui_health — #10: proves the eyes→brain→hand→memory chain is
    functional on BOTH accounts (Binance for crypto, Upstox for NSE) from real state:
    session, eyes-live (interception freshness), UI-data symbols, crawl recency, hand."""
    import json as _json

    from trading.broker_sense.ui_health import check
    try:
        body = _json.dumps(check()).encode()
    except Exception as e:
        body = _json.dumps({"available": False,
                            "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")
