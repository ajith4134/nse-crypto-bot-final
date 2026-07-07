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
        # imports the portfolio module directly (also keeps it wired in the import graph)
        from trading.strategy.generators.portfolio import StrategyPortfolio  # noqa: F401
        from trading.strategy.evolved_link import _loop, status as _evo_status

        st = _evo_status()
        # group the live library by the generator that produced each skill
        by_gen: dict = {}
        try:
            skills = list(_loop().library._skills.values())
        except Exception:
            skills = []
        for sk in skills:
            src = (getattr(sk, "metrics", {}) or {}).get("source") or getattr(sk, "source", "") or "unknown"
            g = by_gen.setdefault(src, {"count": 0, "best_metric": None, "markets": {}, "sample": []})
            g["count"] += 1
            m = float(getattr(sk, "metric", 0.0) or 0.0)
            g["best_metric"] = m if g["best_metric"] is None else max(g["best_metric"], m)
            mk = getattr(sk, "market", "") or "?"
            g["markets"][mk] = g["markets"].get(mk, 0) + 1
            if len(g["sample"]) < 3:
                g["sample"].append({"id": getattr(sk, "name", "?"), "metric": round(m, 4),
                                    "market": mk})
        for g in by_gen.values():
            g["best_metric"] = round(g["best_metric"], 4) if g["best_metric"] is not None else None

        body = json.dumps({
            "available": True,
            "enabled": st.get("enabled"),
            "generators": st.get("generators", []),
            "n_generators": len(st.get("generators", []) or []),
            "best_by_market": st.get("best_by_market", {}),
            "library": st.get("library", {}),
            "by_generator": by_gen,
            "note": ("Strategy-Generator Portfolio (trading/strategy/generators): every generator "
                     "feeds ONE CPCV+Deflated-Sharpe+PBO + family-wise gate → the SkillLibrary → "
                     "the brain pipeline. `by_generator` groups the live library by which "
                     "generator bred each admitted strategy. enabled=false → evolution gated OFF."),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "strategy-generator portfolio via trading/strategy/generators/portfolio.py.",
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
