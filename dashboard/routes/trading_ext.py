"""Extracted trading HTTP routes (dashboard/server.py split — Wave0-⑤ Group 2).

Same pattern + ``_srv(h)`` accessor as dashboard/routes/brain_ext.py: ``self.X`` → ``h.X`` and any
bare server module-level helper/global (``_trading_session``, ``_crypto_session``, ``_PRACTICE``,
``_bg_snapshot``, ``_cached_body``, ``_CT_CACHE``/``_CT_LOCK``, ``PREDICTION_COLUMNS``…) → ``_srv(h).X``
so a moved body reaches the SAME live singletons/caches/locks the inline code did (server runs as
``__main__``; a plain ``from dashboard.server import …`` would bind a duplicate module copy). Behavior
stays shape-identical — every moved route is diffed against a pre-move baseline.
"""
import json
import os
import sys
import time


def _srv(h):
    """The live server module, resolved off the handler instance — see brain_ext._srv for why."""
    return sys.modules[h.__class__.__module__]


def handle_practice(h):
    """GET /api/trading/practice — practice mode: brain trades HISTORIC data (trading/practice.py)."""
    try:
        from data.downloads import list_nse_dump_symbols
        from trading.practice import list_runs
        proc = _srv(h)._PRACTICE.get("proc")
        body = json.dumps({
            "runs": list_runs(),
            "running": proc is not None and proc.poll() is None,
            "nse_symbols": list_nse_dump_symbols(),
        }).encode()
    except Exception as e:
        body = json.dumps({"note": f"practice unavailable: {e}",
                           "runs": [], "nse_symbols": []}).encode()
    return h._send(200, body, "application/json")


def handle_practice_notebook(h):
    """GET /api/trading/practice_notebook — the brain's rough/calculating paper.

    STATE-FILE-READ-ONLY (hard rule): reads only the notebook's JSON state files that the
    run_practice_notebook daemon writes — never imports the WS mirror or a brain lens in this
    request thread. Returns rough page (pending), answer sheet, mistakes book, and report card.
    """
    try:
        from trading import state
        rough = state.load_json("practice_notebook_rough.json", {}) or {}
        answers = state.load_json("practice_notebook_answers.json", []) or []
        mistakes = state.load_json("practice_notebook_mistakes.json", []) or []
        report = state.load_json("practice_notebook_report.json", {}) or {}
        practice = state.load_json("practice_notebook_practice.json", {}) or {}
        confirmed = state.load_json("practice_notebook_confirmed.json", {}) or {}
        now = time.time()
        agg = practice.get("agg", {}) or {}
        reg = {k: (round(v["correct"] / v["n"], 4) if v.get("n") else None)
               for k, v in (practice.get("regime_agg", {}) or {}).items()}
        opened = int(report.get("confirmed", 0))
        rejected = int(report.get("rejected", 0))
        body = json.dumps({
            "enabled": os.environ.get("NOTEBOOK_ENABLED", "1") not in ("0", "false"),
            "long_only": os.environ.get("NOTEBOOK_LONG_ONLY", "1") not in ("0", "false"),
            "confirmations_required": int(float(os.environ.get("NOTEBOOK_CONFIRMATIONS_REQUIRED", "2"))),
            "abstain_below": float(os.environ.get("NOTEBOOK_ABSTAIN_BELOW", "0.52")),
            # rough page: live pending attempts being watched
            "rough": [
                {"symbol": a.get("symbol"), "side": a.get("side"), "p_up": a.get("p_up"),
                 "confirms": a.get("confirms", 0), "regime": a.get("regime"),
                 "age_s": round(now - a.get("created_ts", now), 1)}
                for a in rough.values() if a.get("status") == "pending"
            ],
            "answer_sheet": list(reversed(answers[-40:])),     # newest first
            "mistakes": list(reversed(mistakes[-40:])),
            "report": {
                "practice_n": int(agg.get("n", 0)),
                "practice_direction_hit_rate": (round(agg["correct"] / agg["n"], 4)
                                                if agg.get("n") else None),
                "per_regime": reg,
                "universe": practice.get("universe"),
                "opened": opened, "rejected": rejected,
                "confirm_rate": (round(opened / (opened + rejected), 4)
                                 if (opened + rejected) else None),
                "abstained": int(report.get("abstained", 0)),
                "reject_causes": report.get("reject_causes", {}),
                "confirmed_live": sum(1 for r in confirmed.values()
                                      if r.get("status") == "confirmed" and now <= r.get("expires", 0)),
                "updated_ts": practice.get("updated_ts") or report.get("updated_ts"),
            },
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({"note": f"practice_notebook unavailable: {e}",
                           "rough": [], "answer_sheet": [], "mistakes": [],
                           "report": {}}).encode()
    return h._send(200, body, "application/json")


def handle_venues(h):
    """GET /api/trading/venues — multi-venue market-DATA pool telemetry (ban-proofing): per-venue
    calls/errors/budget/ban-cooldown across binance/bybit/okx/kucoin. Read-only."""
    try:
        from trading.crypto.exchange_pool import all_pools_status
        blob = all_pools_status()
    except Exception as e:
        blob = {"enabled": None, "pools": [], "error": str(e)[:120]}
    return h._send(200, json.dumps(blob).encode(), "application/json")


def handle_brain_discovery(h):
    """GET /api/trading/brain/discovery — Concept Discovery Engine: last run's self-invented
    features + concept manifold (read-only; POST /run triggers a fresh discovery)."""
    try:
        from trading.brain.discovery import ConceptDiscoveryEngine
        blob = ConceptDiscoveryEngine.load()
    except Exception as e:
        blob = {"features": [], "manifold": {"points": [], "n_clusters": 0},
                "stats": {}, "error": str(e)[:120]}
    return h._send(200, json.dumps(blob).encode(), "application/json")


def handle_status(h):
    """GET /api/trading/status — honest trading status: real OpenAlgo connectivity + toggle/feed/
    watchlist. Lazy import so the dashboard still serves if the trading deps are absent."""
    try:
        body = json.dumps(_srv(h)._trading_session().status()).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T1 not configured — set OPENALGO_API_KEY in .env "
                    "and start the OpenAlgo server (see trading-execution-blueprint.md).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_crypto_status(h):
    """GET /api/trading/crypto/status — honest crypto status: one CryptoSession + the Freqtrade
    engine state alongside it. Degrades to an error payload (never crashes the dashboard)."""
    try:
        snap = _srv(h)._crypto_session().status()
    except Exception as e:
        snap = {
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Crypto T2 not ready — pip install ccxt; optionally set "
                    "CRYPTO_EXCHANGES in .env (see trading-execution-blueprint.md §7 T2).",
        }
    # Additive (T-split B): report the Freqtrade engine state alongside the legacy crypto session,
    # so the migration is honestly visible. Best-effort — never crashes.
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        snap["engine"] = CryptoEngineClient().as_status()
    except Exception as e:
        snap["engine"] = {
            "engine": "freqtrade", "connected": False,
            "detail": f"{type(e).__name__}: {e}",
            "hint": "Freqtrade not ready — pip install freqtrade freqtrade-client; "
                    "start a bot with api_server enabled (see research/trading-engine-split.md).",
        }
    body = json.dumps(snap, default=str).encode()
    return h._send(200, body, "application/json")


def handle_crypto_markets(h):
    """GET /api/trading/crypto/markets — Binance-style live markets/screener feed the brain picks
    from. Query: segment(perp|spot), sort(volume|movers|gainers|losers|volatility|funding|price),
    limit, q."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    g = lambda k, d="": (qs.get(k, [d])[0])
    try:
        from trading.crypto.markets import live_markets
        rows = live_markets(segment=g("segment", "perp"), sort=g("sort", "volume"),
                            limit=int(g("limit", "80") or 80), search=g("q", ""))
        out = {"rows": rows, "n": len(rows), "segment": g("segment", "perp"), "sort": g("sort", "volume")}
    except Exception as e:
        out = {"rows": [], "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_crypto_ingest(h):
    """GET /api/trading/crypto/ingest — Phase D: pull Freqtrade CLOSED crypto trades into the
    journal so the trade→NN bridge keeps learning. Idempotent (dedup by trade_id). Best-effort."""
    try:
        from trading.crypto.freqtrade_ingest import ingest_closed
        from trading.journal.journal import TradeJournal
        j = TradeJournal(state_file="journal.json", persist=True)
        res = ingest_closed(j)
        res["journal_trades"] = len(j.trades)
        body = json.dumps(res, default=str).encode()
    except Exception as e:
        body = json.dumps({"ingested": 0, "error": f"{type(e).__name__}: {e}",
                           "hint": "needs a running Freqtrade bot (see Phase D)."}).encode()
    return h._send(200, body, "application/json")


def handle_execution_status(h):
    """GET /api/trading/execution/status — honest T3 execution-engine status (orders/positions/
    circuit_breaker/kill_switch). Labelled demo until a live trade loop owns the engine."""
    try:
        snap = _srv(h)._execution_engine().status()
        snap["demo"] = True
        snap["note"] = ("offline demo engine (run_trading_t3.py sequence); "
                        "no live broker wired yet — real engine state only")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T3 execution engine not importable "
                    "(see trading/execution/ and trading-execution-blueprint.md §T3).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_options_status(h):
    """GET /api/trading/options/status — T4 options intelligence (forward/spot, ATM IV,
    max pain, PCR, GEX+zero-gamma, OI walls). LIVE-FIRST (2026-07-10): the REAL broker
    chain via OpenAlgo optionchain (?underlying=NIFTY|BANKNIFTY|…); cached last real
    chain when the broker/market is quiet; the synthetic demo only if never fetched."""
    try:
        from urllib.parse import parse_qs, urlparse
        und = (parse_qs(urlparse(h.path).query).get("underlying") or ["NIFTY"])[0]
        snap = None
        try:
            from trading.options import live_chain
            snap = live_chain.live_status(und)
        except Exception:
            snap = None
        # fall back not just when never fetched (None) but also when the cached real
        # chain is unusable ({"available": False, error}) — a single bad pre-open chain
        # otherwise pins a permanent error tile (2026-07-10 review fix); the real error
        # stays visible on the labeled fallback.
        if snap is None or not snap.get("available", True):
            err = (snap or {}).get("error")
            snap = _srv(h)._options_chain().status()
            snap["demo"] = True
            snap["note"] = ("no usable real chain (broker session down / bad cached "
                            "chain) — offline demo chain (run_options_t4); real "
                            "computed analytics only"
                            + (f" · last real-chain error: {err}" if err else ""))
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T4 options intelligence not importable "
                    "(see trading/options/ and trading-execution-blueprint.md §T4).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_journal_status(h):
    """GET /api/trading/journal/status — honest T5 trade-journal snapshot (n_trades, columns,
    analytics, per-symbol Brain confidence) off a labelled DEMO set of closed trades."""
    try:
        from run_journal_t5 import build_demo_journal
        snap = build_demo_journal().status()
        snap["demo"] = True
        snap["note"] = ("offline demo journal (run_journal_t5 synthetic trades); "
                        "no live trade loop wired yet — real computed analytics only")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T5 trade journal not importable "
                    "(see trading/journal/ and trading-execution-blueprint.md §T5).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_alerts_status(h):
    """GET /api/trading/alerts/status — honest T7 Telegram-alerts snapshot: secrets-safe
    AlertConfig status (token redacted) + the offline demo dispatcher's status."""
    try:
        from run_alerts_t7 import build_demo_dispatcher
        from trading.alerts import AlertConfig
        snap = AlertConfig.from_env().as_status()
        snap["dispatcher"] = build_demo_dispatcher().status()
        snap["demo"] = True
        snap["note"] = ("offline demo dispatcher (run_alerts_t7 fake transport); "
                        "no live Telegram delivery — token redacted, real "
                        "dedup/dispatch state only")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T7 alerts not importable "
                    "(see trading/alerts/ and trading-execution-blueprint.md §T7).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_strategy_status(h):
    """GET /api/trading/strategy/status — honest T8.1 strategy-evolution snapshot: a deterministic
    random population scored on a walk-forward OOS tail of seeded synthetic OHLCV. Heavy (GIL-bound
    pandas/backtest) → built in a niced SUBPROCESS via the background warmer (in-process wedged the
    server, 2026-07-03). Deterministic, so the subprocess result is identical."""
    def _p_strategy():
        import subprocess as _sp
        import sys as _sys
        code = (
            "import json;from run_strategy_t8 import build_demo_population as B;"
            "s=B();b=s['best'];pv=s.get('pbo',{}).get('pbo');"
            "P=[{'id':p['id'],'market':p['market'],'metrics':p['metrics'],"
            "'fitness_score':float(p['fitness_score']),"
            "'guardrail_passed':bool(p['guardrail']['passed'])} for p in s['population']];"
            "print(json.dumps({'population':P,'best':({'id':b['id'],'market':b['market'],"
            "'metrics':b['metrics'],'fitness_score':float(b['fitness_score']),"
            "'guardrail_passed':bool(b['guardrail']['passed'])} if b else None),"
            "'n':s['n'],'guardrails':{'pbo':(float(pv) if pv is not None else None)},"
            "'demo':True,'note':'offline demo population (subprocess-built, GIL-safe)'},default=str))"
        )
        try:
            kw = dict(cwd=_srv(h).ROOT, capture_output=True, text=True, timeout=180)
            try:
                kw["preexec_fn"] = lambda: __import__("os").nice(15)
            except Exception:
                pass
            r = _sp.run([_sys.executable, "-c", code], **kw)
            return json.loads(r.stdout.strip().splitlines()[-1])
        except Exception as e:
            return {"population": [], "best": None, "n": 0, "demo": True,
                    "error": f"{type(e).__name__}: {str(e)[:120]}"}
    return h._send(200, _srv(h)._bg_snapshot("strategy", _p_strategy), "application/json")


def handle_foundry(h):
    """GET /api/trading/foundry — Strategy Foundry: the brain's institutional strategy catalog
    (per segment, unique ID, tracked by real backtest/live perf, best promoted). Cached 8s."""
    def _p_foundry():
        try:
            from trading.strategy.foundry import StrategyFoundry
            return json.dumps(StrategyFoundry(persist=True).to_json(),
                              default=str).encode()
        except Exception as e:
            return json.dumps({"available": False,
                               "error": f"{type(e).__name__}: {e}",
                               "hint": "trading/strategy/foundry.py"}).encode()
    return h._send(200, _srv(h)._cached_body("trading/foundry", 8.0, _p_foundry),
                   "application/json")


def handle_credentials(h):
    """GET /api/trading/credentials — brain credential vault status: pending login requests +
    stored site NAMES only (never secret values; Fernet-encrypted at rest, gitignored)."""
    try:
        from trading.brain.credentials import get_vault
        body = json.dumps(get_vault().status(), default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_strategy_library(h):
    """GET /api/trading/strategy/library — curated institutional Strategy Library (the ACTIVE T8
    feature; evolution gated OFF). Real OOS backtest leaderboard + honest data-gated catalogue.
    Heavy (some strategies hit ccxt live) + polled hard → built ONCE by the background warmer."""
    def _p_library():
        from trading.strategy.library.run import build_library_snapshot
        snap = build_library_snapshot()
        cov = snap["coverage"]
        lb = [{"rank": r["rank"], "name": r["name"], "category": r["category"],
               "family": r["family"], "market_tested": r["market_tested"],
               "oss_source": r["oss_source"],
               "metrics": {k: r["metrics"].get(k) for k in
                           ("sharpe", "total_return", "max_drawdown", "n_trades",
                            "win_rate", "profit_factor")}}
              for r in snap["leaderboard"][:40]]
        gate_groups: dict = {}
        for s in snap["data_gated"]:
            key = ",".join(s["gating_reqs"]) or "n/a"
            gate_groups.setdefault(key, []).append(s["name"])
        return {
            "coverage": cov,
            "leaderboard": lb,
            "n_backtested": snap["n_backtested"],
            "data_gated": {"total": cov["n_data_gated"],
                           "by_gating_need": {k: len(v) for k, v in
                                              sorted(gate_groups.items(),
                                                     key=lambda kv: -len(kv[1]))},
                           "sample": {k: v[:8] for k, v in gate_groups.items()}},
            "evolution_status": snap["evolution"],
            "demo": True,
            "note": ("curated institutional Strategy Library — real OOS walk-forward "
                     "backtests of the executable strategies on seeded synthetic OHLCV; "
                     "data-gated families (MM/HFT/order-flow/options-greeks/stat-arb/"
                     "funding/OI) are catalogued with their data requirements, never "
                     "fabricated. Genetic creation/mutation/evolution is gated OFF."),
        }
    return h._send(200, _srv(h)._bg_snapshot("strategy_library", _p_library),
                   "application/json")


_EVO_DEMO_FILE = "evolution_demo.json"
_EVO_DEMO_TTL = 6 * 3600
_evo_building = False
_evo_lock = __import__("threading").Lock()


def _evo_demo_build():
    """Run the heavy DEAP demo evolution ONCE in its own thread and persist it. This must
    NEVER run in the request/warmer thread — the DEAP+pandas run holds the GIL for seconds
    and wedged every dashboard endpoint (000 across the whole server) post-restart."""
    global _evo_building
    import time as _t
    try:
        from run_strategy_t8 import build_demo_evolution
        from trading.strategy.control import evolution_enabled
        from trading import state as _state
        snap = build_demo_evolution()
        _state.save_json(_EVO_DEMO_FILE, {
            "history": snap["history"], "n_evaluated": snap["n_evaluated"],
            "pareto_size": snap["pareto_size"], "n_promoted": snap["n_promoted"],
            "best": snap["best"], "registry": snap["registry"], "demo": True,
            "enabled": bool(evolution_enabled()), "_built_at": _t.time(),
            "gate_note": ("Strategy creation/mutation/evolution is GATED OFF for this phase "
                          "(trading.strategy.control). The Strategy Library is the active "
                          "feature. This snapshot is the offline demo kept for reference."),
            "note": ("offline demo evolution loop (run_strategy_t8 seeded synthetic CRYPTO "
                     "OHLCV, pop=16/gens=4); real μ+λ NSGA-II with OUT-OF-SAMPLE fitness + "
                     "T8.2 guardrail gate, survivors promoted to StrategyNodes."),
        })
    except Exception:
        pass
    finally:
        _evo_building = False


def handle_upgrades_status(h):
    """GET /api/trading/upgrades/status — live status of the 2026-07-17 connect batch
    (E1 OPE replay, E2 exit-policy bandit, E4 lesson prior, E5 on-chain lane, E7 execution
    choice, E-video VP/market-state lenses, brain sources). State-file reads only — each
    module's status() is O(1); a failing subsystem reports its error, never fabricates."""
    out = {}
    for key, mod, fn in (
            ("ope", "trading.direction.ope", "status"),
            ("exit_policy", "trading.execution.exit_policy", "status"),
            ("exec_choice", "trading.execution.exec_choice", "status"),
            ("lesson_prior", "trading.direction.lesson_prior", "status"),
            ("onchain", "trading.direction.onchain_source", "status"),
            ("vp_events", "trading.direction.vp_events", "status"),
            ("market_state", "trading.direction.market_state", "status"),
            ("brain_sources", "trading.direction.brain_sources", "status"),
            # SELECTION overhaul 2026-07-17: gate refusals/retired lanes MUST be visible
            # — a kill/freshness gate that refuses entries with no surface would look
            # like "trading silently stopped" (honest-wiring review fix)
            ("lane_gate", "trading.execution.lane_gate", "status")):
        try:
            import importlib
            out[key] = getattr(importlib.import_module(mod), fn)()
        except Exception as e:
            out[key] = {"error": f"{type(e).__name__}: {e}"[:160]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_direction_xray(h):
    """GET /api/trading/direction/xray — per-decision direction rationale (owner ask): WHAT
    DATA drove each trade's direction. Reads the Direction Ledger (state-file only, cheap):
    recent decisions with each source's measured edge-weight + whether it was inverted + the
    winning side, plus a coverage summary. Optional ?symbol= for one symbol's latest."""
    import urllib.parse as _up
    q = _up.parse_qs(_up.urlparse(h.path).query)
    sym = (q.get("symbol") or [""])[0]
    try:
        from trading.brain import direction_ledger as _dl
        from trading.direction import direction_model as _dm
        if sym:
            out = {"symbol": sym, "latest": _dl.by_symbol(sym), "summary": _dl.summary()}
        else:
            out = {"summary": _dl.summary(), "recent": _dl.recent(60),
                   "model": _dm.status()}          # proposal B: direction-aware GBM status
    except Exception as e:
        out = {"error": f"{type(e).__name__}: {e}"[:200]}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_evolution_status(h):
    """GET /api/trading/evolution/status — honest T8.3 DEAP NSGA-II evolution snapshot.
    STATE-FILE-ONLY: the heavy demo build runs in a background thread and persists to
    evolution_demo.json; the request/warmer only READS the file (so the DEAP run can never
    hold the GIL in the warmer and wedge the server — 2026-07-13 fix)."""
    def _p_evolution():
        global _evo_building
        import time as _t
        from trading import state as _state
        cached = _state.load_json(_EVO_DEMO_FILE, None)
        stale = (not cached) or (_t.time() - float(cached.get("_built_at", 0)) > _EVO_DEMO_TTL)
        if stale and not _evo_building:
            with _evo_lock:
                if not _evo_building:
                    _evo_building = True
                    __import__("threading").Thread(
                        target=_evo_demo_build, daemon=True, name="evo-demo-build").start()
        if cached:
            return cached
        return {"warming": True, "demo": True,
                "note": "evolution demo precomputing in a background thread — refresh shortly."}
    return h._send(200, _srv(h)._bg_snapshot("evolution", _p_evolution), "application/json")


def handle_experience_status(h):
    """GET /api/trading/experience/status — honest T8.4 episodic-experience-bank snapshot: a
    Case-Based case base over the real closed-trade journal (numpy-kNN), a sample CBR recall, and
    semantic (mem0) text-memory status. LIVE when the journal is large enough, else demo."""
    try:
        import brain_live
        snap = brain_live.live_experience()
        body = json.dumps({
            "experience": snap["experience"],
            "sample_recall": snap["sample_recall"],
            "semantic": snap["semantic"],
            "demo": snap.get("demo", False),
            "n_trades": snap.get("n_trades"),
            "note": (f"LIVE experience bank — Case-Based Reasoning over the real closed-trade "
                     f"journal ({snap.get('n_trades')} trades); recall biases new decisions by "
                     f"analogous past outcomes" if not snap.get("demo") else
                     "offline demo experience bank (journal too small yet) (run_brain_t8: T5 demo journal "
                     "+ synthetic win/lose cluster, deterministic numpy-kNN over a "
                     "no-leakage trade-setup vector); CBR recall biases new "
                     "decisions by analogous past outcomes (expected win-rate / "
                     "P&L / confidence), with LanceDB-backed persistence available; "
                     "semantic text-memory via mem0 (real when MEM0_ENABLED + LLM "
                     "configured, dry-run otherwise) — no live trade loop wired yet"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.4 experience bank not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_selfeval_status(h):
    """GET /api/trading/selfeval/status — honest T8.5 continual-learning + self-eval snapshot: a
    prequential AutoQuiz accuracy-vs-trade-count curve, a River ADWIN drift count, a MAML warm-vs-
    cold few-shot result, and a Reflexion self-critique note. JSON-able only."""
    try:
        from run_brain_t8 import build_demo_selfeval
        snap = build_demo_selfeval()
        body = json.dumps({
            "autoquiz": snap["autoquiz"],
            "drift_events": snap["drift_events"],
            "meta": snap["meta"],
            "reflection": snap["reflection"],
            "demo": True,
            "note": ("offline demo self-eval (run_brain_t8: T8.5). AutoQuiz runs a "
                     "prequential test-then-train pass over a deterministic learnable "
                     "stream — the accuracy-vs-trade-count curve + positive slope are "
                     "the honest proof predictions improve with experience; River "
                     "OnlineNode flags concept drift (ADWIN) on a stream whose concept "
                     "flips halfway; MetaLearner shows warm-start few-shot gain over "
                     "cold-start; Reflexion writes a self-critique into the T8.4 "
                     "semantic memory — no live trade loop wired yet"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.5 continual-learning/self-eval not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_crypto_trades(h):
    """GET /api/trading/crypto/trades — Phase F+: open + closed Freqtrade trades with full columns
    (MFE/MAE, USDT P&L, capital, leverage). Cached 30s in the server-level _CT_CACHE behind a
    single-flight _CT_LOCK — the outcome-NN retrains as the journal grows (minutes over 1000+
    trades), so without the cache the poll times out and the Freqtrade panel renders empty.

    _srv(h) keeps _CT_CACHE/_CT_LOCK the SAME objects the inline code used, so the single-flight
    (one rebuild, others serve stale) still coordinates across ALL requests to this route.
    """
    srv = _srv(h)
    path = "/api/trading/crypto/trades"
    import time as _ct_t
    _hit = srv._CT_CACHE.get(path)
    if _hit and (_ct_t.time() - _hit[0]) < 30:
        return h._send(200, _hit[1], "application/json")
    # Single-flight: if a stale snapshot exists and another thread is already rebuilding,
    # serve the stale snapshot immediately instead of stacking another rebuild.
    if not srv._CT_LOCK.acquire(blocking=(_hit is None)):
        return h._send(200, _hit[1], "application/json")
    try:
        # Re-check after acquiring — the previous builder may have just refreshed it.
        _hit = srv._CT_CACHE.get(path)
        if _hit and (_ct_t.time() - _hit[0]) < 30:
            return h._send(200, _hit[1], "application/json")
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            from trading.crypto import freqtrade_ingest as _fi
            from trading.crypto.freqtrade_ingest import open_trades_view, closed_view
            from trading.crypto.freqtrade import control as _ctl
            cli = CryptoEngineClient()
            openrows = open_trades_view(cli)
            closed = closed_view(cli)
            # Enrich with strategy + brain + NN predictions. NN runs on all OPEN rows but
            # only the newest closed rows — predicting a 1000+-row history every poll is
            # what made this endpoint stall (open trades are the actionable ones).
            srv._enrich_predictions(openrows, closed[:80])
            for r in closed[80:]:
                r["strategy_label"] = (r.get("enter_tag") or r.get("strategy")
                                       or r.get("strategy_name") or "—")
                r["brain_pred"] = r.get("direction") or "—"
                r["nn_pred"] = "—"
            # FIXED column schemas (not data-derived) so the dashboard column count is
            # stable as trades open/close — same contract as the dark dashboard.
            out = {"open": openrows, "closed": closed,
                   "open_columns": _fi.OPEN_VIEW_COLUMNS + srv.PREDICTION_COLUMNS,
                   "closed_columns": _fi.CLOSED_VIEW_COLUMNS + srv.PREDICTION_COLUMNS,
                   "params": _ctl.status(), "n_open": len(openrows), "n_closed": len(closed)}
        except Exception as e:
            out = {"open": [], "closed": [], "error": f"{type(e).__name__}: {e}"}
        _body = json.dumps(out, default=str).encode()
        if not out.get("error"):
            srv._CT_CACHE[path] = (_ct_t.time(), _body)
    finally:
        srv._CT_LOCK.release()
    return h._send(200, _body, "application/json")


def handle_crypto_predictions(h):
    """GET /api/trading/crypto/predictions — LIGHTWEIGHT per-trade Strategy/Brain/NN map keyed by
    trade_id for overlaying onto the native FreqUI table cross-origin. Skips the slow peak-OHLCV
    enrichment (map_trade directly) + caches ~15s in the server-level _PRED_MAP_CACHE behind a
    single-flight _PRED_MAP_LOCK (same avalanche fix as /crypto/trades)."""
    srv = _srv(h)
    import time as _pt
    hit = srv._PRED_MAP_CACHE
    if hit and (_pt.time() - hit[0]) < 15:
        return h._send(200, hit[1], "application/json")
    # Single-flight: stale + rebuild-in-progress → serve stale now; only one thread pays the cost.
    if not srv._PRED_MAP_LOCK.acquire(blocking=(hit is None)):
        return h._send(200, hit[1], "application/json")
    try:
        hit = srv._PRED_MAP_CACHE
        if hit and (_pt.time() - hit[0]) < 15:
            return h._send(200, hit[1], "application/json")
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            from trading.crypto.freqtrade_ingest import open_trades_view, map_trade
            cli = CryptoEngineClient()
            openrows = open_trades_view(cli)
            try:
                # Only the most recent ~120 closed trades are visible in the native table's first
                # pages; enriching all 500 makes net.predict ~26s. Newest-first by trade_id.
                raw = [ft for ft in cli.closed_trades() if isinstance(ft, dict)]
                raw.sort(key=lambda ft: ft.get("trade_id") or 0, reverse=True)
                closed_light = [map_trade(ft, broker_ctx=False).to_dict() for ft in raw[:120]]
            except Exception:
                closed_light = []
            srv._enrich_predictions(openrows, closed_light)
            # TAILGATE overlay (owner 2026-07-07): per-trade LEARNED trail state — the
            # ratcheting locked floor + the trail distance the brain has learned (W2-railed
            # EMA from closed outcomes, trading/execution/profit_tailgate.learn) + peak.
            # Read from the live lock state the executor's tailgate pass maintains.
            try:
                from trading import state as _tstate
                _locks = _tstate.load_json("profit_tailgate_locks.json", {}) or {}
            except Exception:
                _locks = {}
            pmap = {}
            for r in [*openrows, *closed_light]:
                tid = str(r.get("trade_id", "")).replace("FT-", "")
                if tid:
                    _lk = _locks.get(tid) or {}
                    pmap[tid] = {"strategy_label": r.get("strategy_label"),
                                 "brain_pred": r.get("brain_pred"), "nn_pred": r.get("nn_pred"),
                                 "tg_locked_pct": _lk.get("locked"),
                                 "tg_trail_dist": _lk.get("dist"),
                                 "tg_peak_pct": _lk.get("peak")}
            body = json.dumps({"map": pmap, "n": len(pmap)}, default=str).encode()
        except Exception as e:
            body = json.dumps({"map": {}, "error": f"{type(e).__name__}: {e}"}).encode()
        srv._PRED_MAP_CACHE = (_pt.time(), body)
    finally:
        srv._PRED_MAP_LOCK.release()
    return h._send(200, body, "application/json")


def handle_patterns_status(h):
    """GET /api/trading/patterns/status — honest T8.6 pattern/regime + asset-picking + entry/exit
    snapshot (STUMPY matrix-profile + TA-Lib candles, hmmlearn GaussianHMM regime + RegimeGate,
    a learned vendored-gplearn symbolic factor, regime/anomaly-gated entry/exit). LIVE or demo."""
    try:
        import brain_live
        snap = brain_live.live_patterns()
        body = json.dumps({
            "patterns": snap["patterns"],
            "regime": snap["regime"],
            "picking": snap["picking"],
            "entryexit": snap["entryexit"],
            "demo": snap.get("demo", False),
            "symbol": snap.get("symbol"),
            "note": (f"LIVE pattern/regime layer on real {snap.get('symbol')} {snap.get('tf')} OHLCV "
                     f"(ccxt): STUMPY matrix-profile motifs/anomalies + hmmlearn GaussianHMM regime"
                     if not snap.get("demo") else
                     "offline demo pattern/regime layer (run_brain_t8: T8.6) on a "
                     "deterministic synthetic OHLCV with an injected anomaly + "
                     "bull/bear/neutral segments. PatternScanner = STUMPY matrix-"
                     "profile motif/anomaly discovery + TA-Lib candlesticks; "
                     "RegimeModel = hmmlearn GaussianHMM (bull/bear/neutral) with "
                     "RegimeGate strategy activation; asset-picking ranks a universe "
                     "by a LEARNED symbolic factor from VENDORED gplearn "
                     "(vendor/gplearn, factor_source='gplearn'); EntryExitPolicy is "
                     "regime/anomaly-gated — no live trade loop wired yet"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.6 pattern/regime layer not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_news_status(h):
    """GET /api/trading/news/status — honest T8.7 autonomous-news-research + sentiment snapshot
    (vendored-VADER finance-lexicon sentiment, per-symbol NewsResearcher, NewsSentimentNode
    compound→p(bullish), gated GPT-Researcher hook). LIVE (RSS) or demo."""
    try:
        import brain_live
        snap = brain_live.live_news()
        # persistent symbol-linked news memory (trading/brain/news_ingest, 2026-07-10):
        # the scheduled free-RSS ingest the learn loop drives — entry-time lookups read
        # this store instead of refetching feeds.
        try:
            from trading.brain import news_ingest
            ingest = news_ingest.status()
            ingest.pop("latest", None)
        except Exception as e:
            ingest = {"error": f"{type(e).__name__}: {e}"[:120]}
        body = json.dumps({
            "scorer_backend": snap["scorer_backend"],
            "research": snap["research"],
            "autonomous": snap["autonomous"],
            "node_p_bullish": snap["node_p_bullish"],
            "ingest": ingest,
            "demo": snap.get("demo", False),
            "n_items": snap.get("n_items"),
            "note": (f"LIVE news/sentiment — {snap.get('n_items')} real headlines via RSS "
                     f"(cointelegraph + coindesk, feedparser) scored with VADER per symbol "
                     f"(BTC/ETH/SOL); autonomous GPT-Researcher still gated (needs key)"
                     if not snap.get("demo") else
                     "offline demo news/sentiment layer (run_brain_t8: T8.7) over a "
                     "FIXED NewsItem feed (no RSS/network). Sentiment = VENDORED VADER "
                     "(vendor/vaderSentiment, finance-lexicon boosted), FinBERT optional "
                     "if transformers installed (backend='finbert'); NewsResearcher "
                     "aggregates per-symbol sentiment (feedparser RSS behind an injected "
                     "fetcher in live use); NewsSentimentNode maps compound→p(bullish); "
                     "autonomous_research is a gated GPT-Researcher hook (set "
                     "GPT_RESEARCHER_ENABLED=1 + an LLM key) — no live news loop wired yet"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.7 news/sentiment layer not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_skills_status(h):
    """GET /api/trading/skills/status — honest T8.8 skill-library + observability + self-improvement
    snapshot (Voyager quality-gated SkillLibrary, BrainTracer Stream-of-Mind spans, a CPU
    SelfImprover hill-climb, gated DSPy/GEPA optimiser). LIVE or demo."""
    try:
        import brain_live
        snap = brain_live.live_skills()
        body = json.dumps({
            "skills": snap["skills"],
            "skill_events": snap["skill_events"],
            "best": snap["best"],
            "stream_of_mind": snap["stream_of_mind"],
            "tracer": snap["tracer"],
            "self_improve": snap["self_improve"],
            "dspy": snap["dspy"],
            "demo": snap.get("demo", False),
            "n_skills": snap.get("n_skills"),
            "note": (f"LIVE Voyager skill library — {snap.get('n_skills')} validated skills from the "
                     f"real persisted store (skill_library.json); grows when the self-evolve loop "
                     f"is armed (Batch 3)" if not snap.get("demo") else
                     "offline demo skill-library + self-improvement layer "
                     "(run_brain_t8: T8.8). SkillLibrary is a Voyager-pattern "
                     "quality-gated, growing store of validated strategy skills "
                     "(persist=False here, so no disk state); BrainTracer records "
                     "reasoning spans → Stream-of-Mind (local; exports to Langfuse "
                     "when LANGFUSE_* keys set); SelfImprover is a REAL CPU "
                     "hill-climb optimising EntryExitPolicy params against a toy "
                     "T8.2-style fitness; DSPy/GEPA LLM-program optimiser is gated "
                     "(set DSPY_ENABLED=1 + an OpenAI-compatible key to activate)"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.8 skill-library layer not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def _filter_preset_of(d: dict) -> str:
    """The Binance-filter PRESET that surfaced a trade — its own column, separate from the strategy
    (owner 2026-07-13). From the 'filter:<preset>' enter_tag, else the entry snapshot's
    brain.filter.filter_preset, else '—'."""
    tag = str(d.get("enter_tag") or d.get("strategy") or d.get("strategy_name") or "")
    if tag.startswith("filter:"):
        return tag.split(":", 1)[1] or "—"
    ds = d.get("decision_snapshot")
    if isinstance(ds, dict):
        fp = ((ds.get("brain") or {}).get("filter") or {}).get("filter_preset")
        if fp:
            return str(fp)
    return "—"


def handle_brain_status(h):
    """GET /api/trading/brain/status — honest T8.9 FINALE end-to-end brain pipeline + safety review
    snapshot (BrainTradingPipeline drives CRYPTO + NSE off ONE path: features→regime→pattern/
    anomaly→news→evolved-signal→experience-recall→gated entry, traced, safety-gated to FLAT)."""
    try:
        import brain_live
        snap = brain_live.live_pipeline()
        body = json.dumps({
            "crypto": snap["crypto"],
            "nse": snap["nse"],
            "safety": snap["safety"],
            "stream_of_mind": snap["stream_of_mind"],
            "gate_demo": snap["gate_demo"],
            "strategy_seeds": snap["strategy_seeds"],
            "demo": snap.get("demo", False),
            "n_trades": snap.get("n_trades"),
            "note": (f"LIVE end-to-end brain pipeline on real {snap.get('n_trades')}-trade journal + "
                     f"real BTC OHLCV — features→regime→pattern/anomaly→experience-recall→gated "
                     f"decision, traced (Stream-of-Mind), safety-gated to FLAT (NSE leg reuses demo)"
                     if not snap.get("demo") else
                     "offline demo end-to-end brain pipeline (run_brain_t8: T8.9 "
                     "FINALE). BrainTradingPipeline stitches the full T8 stack "
                     "(features → regime → pattern/anomaly → news-sentiment → "
                     "evolved-strategy signal → experience-recall → regime/anomaly-"
                     "gated entry) into ONE traced decision per market, driving NSE "
                     "+ Crypto from the SAME code path; every step is recorded by the "
                     "BrainTracer → Stream-of-Mind, and the final action is SAFETY-"
                     "GATED to FLAT whenever the T3 kill-switch is engaged or the "
                     "DailyCircuitBreaker has tripped (paper-first; the gate_demo "
                     "shows the forced-FLAT). Deterministic synthetic OHLCV + a FIXED "
                     "offline news feed — no live market/news/order path wired"),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T8.9 end-to-end brain pipeline not importable "
                    "(see trading/brain/ and trading-execution-blueprint.md §T8).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_advintel_status(h):
    """GET /api/trading/advintel/status — honest T8-DEFERRED advanced-intelligence snapshot
    (PortfolioRisk VaR/CVaR/HRP/Kelly, StressTester, FII/DII + announcements, on-chain SOPR/MVRV
    + Fear&Greed, liquidation heatmap, cross-exchange arb + funding-farm, autonomous researcher,
    tabular-Q RL exit). All OFFLINE/deterministic via stub fetchers. Warmed snapshot."""
    def _p_advintel():
        from run_advintel import build_demo_advintel
        snap = build_demo_advintel()
        return {
            "portfolio_risk": snap["portfolio_risk"],
            "stress": snap["stress"],
            "fii_dii": snap["fii_dii"],
            "announcements": snap["announcements"],
            "onchain": snap["onchain"],
            "liquidations": snap["liquidations"],
            "arbitrage": snap["arbitrage"],
            "research": snap["research"],
            "rl_exit": snap["rl_exit"],
            "demo": True,
            "note": ("offline demo advanced-intelligence layer (run_advintel: T8 "
                     "DEFERRED). Group B: PortfolioRisk = Riskfolio-Lib/PyPortfolioOpt "
                     "VaR/CVaR/HRP/Kelly over a seeded returns panel (numpy fallbacks); "
                     "StressTester = first-order scenario analysis + a 'Nifty -5%' "
                     "what-if; FII/DII + NSE-announcement scrapers, crypto on-chain "
                     "SOPR/MVRV + Fear&Greed, and a Coinglass-style liquidation heatmap "
                     "all run through INJECTED stub fetchers (live use needs public NSE "
                     "endpoints / COINGLASS_API_KEY / BITCOINDATA_API_KEY); "
                     "ArbitrageScanner = cross-exchange spot arb + funding-farm over stub "
                     "price/funding sources. Group A: AutonomousResearcher (ddgs + "
                     "core.llm in live use) over a stub searcher+summarizer, and a "
                     "tabular Q-learning RL exit policy (CPU, no torch; deep-RL gated "
                     "hook) — no live market/news/order path wired yet"),
        }
    return h._send(200, _srv(h)._bg_snapshot("advintel", _p_advintel), "application/json")


def handle_tickers(h):
    """GET /api/trading/tickers — T6 Dark-Pro ticker tape: LIVE last prices from the running trade
    loop (real ccxt / OpenAlgo quotes). Falls back to demo constants if the loop has no ticks yet."""
    try:
        from trading.online.live_loop import get_loop
        snap = get_loop().ticks_snapshot()
        if snap:
            tickers = [{"symbol": v["symbol"], "last": round(float(v["last"]), 2),
                        "change": 0.0, "change_pct": 0.0, "market": v["market"]}
                       for v in snap.values()]
            body = json.dumps({"tickers": tickers, "demo": False, "live": True,
                               "note": "live last prices from the trade loop"},
                              default=str).encode()
        else:
            body = json.dumps({"tickers": _srv(h)._DEMO_TICKERS, "demo": True,
                               "note": "loop has no live ticks yet (warming up)"},
                              default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                           "hint": "live tickers via trading/online/live_loop.py"}).encode()
    return h._send(200, body, "application/json")


def handle_candles(h):
    """GET /api/trading/candles — REAL OHLC candles for the price chart: crypto via ccxt, NSE via
    OpenAlgo history. Query: symbol, market, tf."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    symbol = (qs.get("symbol", ["BTC/USDT"])[0])
    market = (qs.get("market", ["CRYPTO"])[0])
    tf = (qs.get("tf", ["5m"])[0])
    try:
        candles = _srv(h)._candles(symbol, market, tf=tf)
        body = json.dumps({"symbol": symbol, "market": market, "tf": tf,
                           "candles": candles, "demo": False, "live": True,
                           "count": len(candles)}, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "symbol": symbol, "market": market,
                           "error": f"{type(e).__name__}: {str(e)[:80]}",
                           "hint": "live candles via ccxt / OpenAlgo history"}).encode()
    return h._send(200, body, "application/json")


def handle_forecast(h):
    """GET /api/trading/forecast — CANON-54 predicted-path overlay from trading/heads.py. CPU-cheap
    + in-process-safe (numpy ridge in heads.RolloutHead does the k-step rollout; no torch — the
    524-wedge rule). Query: symbol, market, tf, k. Honest research-preview output."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    symbol = (qs.get("symbol", ["BTC/USDT"])[0])
    market = (qs.get("market", ["CRYPTO"])[0])
    tf = (qs.get("tf", ["15m"])[0])
    k = min(24, max(1, int((qs.get("k", ["8"])[0]) or 8)))
    try:
        candles = _srv(h)._candles(symbol, market, tf=tf)
        body = json.dumps(_srv(h)._forecast_payload(candles, k, symbol, tf),
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "symbol": symbol,
                           "error": f"{type(e).__name__}: {str(e)[:100]}"}).encode()
    return h._send(200, body, "application/json")


def handle_orderbook(h):
    """GET /api/trading/orderbook — LIVE L2 order book. CRYPTO → ccxt fetch_order_book (via the
    multi-venue pool); NSE → OpenAlgo depth. Degrades to a demo book on any error so the panel
    never crashes. 2.5s server-level _OB_CACHE collapses rapid polls (no thread pileup)."""
    srv = _srv(h)
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    symbol = (qs.get("symbol") or ["BTC/USDT"])[0]
    market = (qs.get("market") or ["CRYPTO"])[0].upper()
    _obhit = srv._OB_CACHE.get((symbol, market))
    if _obhit and (time.time() - _obhit[0]) < 2.5:    # collapse rapid polls → no thread pileup
        return h._send(200, _obhit[1], "application/json")
    try:
        def _norm(levels):
            out = []
            for lv in levels[:20]:
                if isinstance(lv, dict):
                    out.append([float(lv.get("price", 0)),
                                float(lv.get("quantity", lv.get("size", 0)))])
                else:
                    out.append([float(lv[0]), float(lv[1])])
            return out
        if market == "NSE":
            from trading.openalgo_client import OpenAlgoClient
            d = OpenAlgoClient()._client().depth(symbol=symbol, exchange="NSE")
            data = d.get("data", d) if isinstance(d, dict) else {}
            bids = _norm(data.get("bids", []))
            asks = _norm(data.get("asks", []))
        else:
            ob = srv._pool_order_book(symbol, 20)
            bids = _norm(ob.get("bids", []))
            asks = _norm(ob.get("asks", []))
        if not bids or not asks:
            raise ValueError("empty order book")
        best_bid = bids[0][0]
        best_ask = asks[0][0]
        body = json.dumps({
            "symbol": symbol, "market": market,
            "bids": bids, "asks": asks,
            "mid": (best_bid + best_ask) / 2.0,
            "spread": best_ask - best_bid,
            "demo": False, "live": True,
        }, default=str).encode()
        srv._OB_CACHE[(symbol, market)] = (time.time(), body)
    except Exception as e:
        # Honest demo book around a plausible mid so the UI degrades, never crashes.
        mid = 65000.0 if market != "NSE" else 1500.0
        step = mid * 0.0001
        bids = [[round(mid - step * (i + 1), 2), round(0.5 + i * 0.1, 3)] for i in range(20)]
        asks = [[round(mid + step * (i + 1), 2), round(0.5 + i * 0.1, 3)] for i in range(20)]
        body = json.dumps({
            "symbol": symbol, "market": market,
            "bids": bids, "asks": asks,
            "mid": mid, "spread": round(asks[0][0] - bids[0][0], 2),
            "demo": True,
            "note": f"live order book unavailable ({type(e).__name__}: {str(e)[:80]}) — demo book",
        }, default=str).encode()
    return h._send(200, body, "application/json")


def handle_scorecard(h):
    """GET /api/trading/scorecard — per-segment score card: realized + current P&L for every
    NSE / crypto / prediction segment, from the SAME sources as the unified open/closed tables."""
    try:
        body = json.dumps(_srv(h)._scorecard(), default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def _tg_cells(locked, dist):
    """Profit-tailgate display cells (unified open table, both venues). locked = the
    ratcheting locked-profit floor %, dist = the trail distance % in use. None → '—'."""
    def _pct(v, pre=""):
        try:
            return f"{pre}{float(v):.2f}%"
        except (TypeError, ValueError):
            return "—"
    return {"Tailgate Lock": _pct(locked), "Tailgate Trail": _pct(dist, "~")}


def handle_opentrades(h):
    """GET /api/trading/opentrades — T6 unified Open Trades table: LIVE open PAPER positions from
    the trade loop (marked at last price) + Freqtrade engine-owned crypto + OpenAlgo NSE sandbox,
    each enriched with the project node-network outcome call. Empty → rows:[] (honest)."""
    srv = _srv(h)
    try:
        from trading.online.live_loop import get_loop
        live = get_loop().open_positions()
        # train the project node network on the CLOSED journal, predict each OPEN trade
        net = srv._trade_outcome_net()
        preds = net.predict(live) if net else []
        # Symbol-Move Net (owner 2026-07-13): the NEW output net — signed price-move % + direction,
        # NOT win %. Surface it as its own columns so the table shows what we implemented. Module-
        # cached by closed-trade count (retrains only when a trade closes), mirroring the outcome net.
        # NON-BLOCKING: the server helper trains the move net in a background thread (never in this
        # request thread — that starves the GIL and 502s the tunnel); we only ever do cheap forward passes.
        mpreds, _mnet = [], None
        try:
            _mnet = srv._symbol_move_net()
            if _mnet is not None and _mnet.trained:
                mpreds = _mnet.predict(live)
            else:
                _mnet = None
        except Exception:
            mpreds, _mnet = [], None

        def _move_cells(trade_dict):
            """(move%_txt, direction) from the NEW output net for one trade dict; ('—','—') when
            the net is untrained. Shared by the loop-owned and Freqtrade-owned open-trade rows."""
            if _mnet is None:
                return "—", "—"
            try:
                _p = _mnet.predict_one(trade_dict)
                _v = _p.get("expected_move_pct")
                return (f"{_v:+.2f}%" if _v is not None else "—"), (_p.get("direction") or "—")
            except Exception:
                return "—", "—"
        # rows are DICTS keyed by OPEN_TRADE_COLUMNS (the frontend reads row[columnName]).
        rows = []
        nse_pnl = crypto_pnl = nse_cap = crypto_cap = 0.0
        import datetime as _dt

        def _money(v):
            return f"{sym}{float(v):,.4f}".rstrip("0").rstrip(".")
        for i, p in enumerate(live):
            cur, sym = srv.CCY.get(p["market"], ("INR", "₹"))
            is_crypto = p["market"] == "CRYPTO"
            notional = p.get("notional") or p.get("capital") or (p["entry_price"] * p["quantity"])
            lev = float(p.get("leverage", 1.0) or 1.0)
            margin = p.get("margin") or (notional / lev if lev else notional)
            fees = p.get("est_charges")
            upnl = p["unrealized_pnl"]
            pct = round(upnl / notional * 100, 3) if notional else 0.0
            pp, pl = float(p.get("peak_profit", 0.0)), float(p.get("peak_loss", 0.0))
            try:
                held = _dt.datetime.now() - _dt.datetime.fromisoformat(p.get("entry_dt", ""))
                hold = f"{int(held.total_seconds() // 60)}m"
            except Exception:
                hold = "—"
            # live stop/trail from the loop's ratcheting trailing engine (+ initial SL)
            stop_lv = p.get("stop_level", p.get("initial_sl"))
            stop_txt = _money(stop_lv) if stop_lv is not None else "—"
            # exit policy — intraday squares off at NSE close; everything else carries
            exit_policy = ("carry overnight" if p.get("holds_overnight", True)
                           else "square-off @ close")
            # R-multiple (live) = unrealized P&L / capital-at-risk
            risk = p.get("capital_at_risk")
            rmult_txt = f"{round(upnl / risk, 2):.2f}R" if risk else "—"
            # efficiency (live) = MFE capture share of the realised path
            denom = pp + abs(pl)
            eff_txt = f"{round(pp / denom * 100, 1)}%" if denom > 0 else "—"
            # liquidation price — only meaningful when leveraged (spot/eq → N/A, honest)
            liq_txt = "—"
            if is_crypto and lev > 1.0:
                try:
                    from trading.crypto.liquidation import liquidation_price
                    liq = liquidation_price(side=p["direction"].lower(),
                                            entry_price=float(p["entry_price"]), leverage=lev,
                                            margin_mode=p.get("margin_mode", "isolated"))
                    liq_txt = f"{sym}{liq:,.2f}"
                except Exception:
                    pass
            # node-network outcome call on THIS open trade (trade row → NN → output)
            pr = preds[i] if i < len(preds) else {}
            win_txt = (f"{round(pr['p_win'] * 100, 1)}%"
                       if pr.get("p_win") is not None else "—")
            # NEW output net: signed price-move % (primary) + its derived direction (owner 2026-07-13)
            mp = mpreds[i] if i < len(mpreds) else {}
            _mv = mp.get("expected_move_pct")
            move_txt = (f"{_mv:+.2f}%" if _mv is not None else "—")
            nn_dir_txt = mp.get("direction") or "—"
            expr = pr.get("expected_R")
            expr_txt = f"{expr:.2f}R" if expr is not None else "—"
            # confidence: brain entry confidence, else the NN p_win
            conf_val = p.get("brain_confidence_entry")
            if conf_val is None:
                conf_val = pr.get("p_win")
            conf_txt = f"{round(float(conf_val) * 100, 1)}%" if conf_val is not None else "—"
            # capital totals = cash actually committed (margin), matching the Capital column
            if p["market"] == "CRYPTO":
                crypto_pnl += upnl; crypto_cap += float(margin)
            else:
                nse_pnl += upnl; nse_cap += float(margin)
            rows.append({
                "Symbol": p["symbol"], "Trade Type": p.get("trade_type", "—"),
                "Instrument Type": p.get("instrument", "—"), "Currency": cur,
                "Direction": p["direction"], "Qty": p["quantity"],
                # lots: F&O/options/commodities trade in whole lots (qty = lots × lot size)
                "Lots": (p.get("num_lots") if p.get("num_lots") is not None else "—"),
                "Lot Size": p.get("lot_size", 1),
                # money values carry their currency symbol so $ (crypto) ≠ ₹ (NSE)
                # Capital = cash actually committed (= notional / leverage); Notional =
                # the leveraged position value (qty × price); Fees = est round-trip cost.
                "Capital": f"{sym}{float(margin):,.2f}",
                "Notional": f"{sym}{notional:,.2f}",
                "Leverage": f"{lev:g}×",
                "Fees": f"{sym}{float(fees):,.2f}" if fees is not None else "—",
                "Entry Price": _money(p["entry_price"]),
                "Current Price": _money(p["mark_price"]),
                "Unrealized P&L": f"{sym}{upnl:,.2f}", "Unrealized P&L %": pct,
                "Peak P/L": f"{sym}{pp:,.2f}/{sym}{pl:,.2f}",
                "Stop": stop_txt, "Trail Stop": stop_txt,
                **_tg_cells(p.get("tailgate_locked_profit_pct"),
                            p.get("tailgate_distance_pct")),
                "R-multiple": rmult_txt, "Efficiency": eff_txt,
                "Filter": _filter_preset_of(p), "Strategy": p.get("strategy", "momentum"),
                "Exchange": "binance" if p["market"] == "CRYPTO" else "NSE",
                "Exit Policy": exit_policy, "Liq Price": liq_txt, "Hold Time": hold,
                "Confidence": conf_txt,
                # NEW brain output net (SymbolMoveNet): predicted price-move % + direction — this is
                # the "what we implemented" the win% never showed. Win Prob kept for back-compat.
                "NN Move %": move_txt, "NN Direction": nn_dir_txt,
                "Win Prob": win_txt, "NN Verdict": pr.get("verdict", "—"),
                "Exp R": expr_txt, **srv._psych_cells(p.get("psych")),
                **srv._uq_cells(p.get("uq"))})
        # —— UNIFIED TABLE: Freqtrade OPEN trades (engine-owned crypto) ——
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            from trading.crypto.freqtrade_ingest import open_trades_view
            # live tailgate lock state (same store the FreqUI Tailgate column reads),
            # keyed by the bare Freqtrade trade id
            try:
                from trading import state as _tstate
                _tg_locks = _tstate.load_json("profit_tailgate_locks.json", {}) or {}
            except Exception:
                _tg_locks = {}
            for t in open_trades_view(CryptoEngineClient()):
                _lk = _tg_locks.get(
                    str(t.get("trade_id", "")).replace("FT-", "")) or {}
                upnl = float(t.get("unrealized_pnl_usdt") or 0.0)
                margin = float(t.get("capital_usdt") or 0.0)
                lev = float(t.get("leverage") or 1.0)
                stop = t.get("stop_loss")
                stop_txt = f"${float(stop):,.4f}".rstrip("0").rstrip(".") if stop else "—"
                try:
                    edt = _dt.datetime.fromisoformat(str(t.get("entry_datetime")).replace("Z", "+00:00"))
                    held = _dt.datetime.now(edt.tzinfo) - edt
                    hold = f"{int(held.total_seconds() // 60)}m"
                except Exception:
                    hold = "—"
                crypto_pnl += upnl; crypto_cap += margin
                _ftm = srv._ft_entry_meta(t)          # entry-meta sidecar (carries the filter preset)
                rows.append({
                    "Symbol": t.get("symbol"), "Trade Type": "crypto-freqtrade",
                    "Instrument Type": t.get("instrument_type", "SPOT"), "Currency": "USD",
                    "Direction": t.get("direction", "LONG"),
                    "Qty": float(t.get("quantity") or 0.0), "Lots": "—", "Lot Size": 1,
                    "Capital": f"${margin:,.2f}",
                    "Notional": f"${float(t.get('notional_usdt') or 0.0):,.2f}",
                    "Leverage": f"{lev:g}×",
                    "Fees": f"${float(t.get('funding_usdt') or 0.0):,.2f}",
                    "Entry Price": f"${float(t.get('entry_price') or 0.0):,.4f}".rstrip("0").rstrip("."),
                    "Current Price": f"${float(t.get('current_price') or 0.0):,.4f}".rstrip("0").rstrip("."),
                    "Unrealized P&L": f"${upnl:,.2f}",
                    "Unrealized P&L %": round(float(t.get("unrealized_pnl_pct") or 0.0), 3),
                    "Peak P/L": (f"${float(t.get('peak_profit_usdt') or 0.0):,.2f}/"
                                 f"${float(t.get('peak_loss_usdt') or 0.0):,.2f}"),
                    "Stop": stop_txt, "Trail Stop": stop_txt,
                    **_tg_cells(_lk.get("locked"), _lk.get("dist")),
                    "R-multiple": "—", "Efficiency": "—",
                    # filter preset lives in the entry-meta snapshot's brain.filter (enter_tag is the
                    # direction source e.g. 'learned_direction', not the filter) — read it from _ftm.
                    "Filter": (_filter_preset_of(t) if _filter_preset_of(t) != "—"
                               else _filter_preset_of(_ftm)),
                    "Strategy": t.get("enter_tag") or t.get("strategy") or "freqtrade",
                    "Exchange": t.get("exchange", "binance"),
                    "Exit Policy": "freqtrade-managed", "Liq Price": "—",
                    "Hold Time": hold, "Confidence": "—",
                    **(lambda mc: {"NN Move %": mc[0], "NN Direction": mc[1]})(_move_cells(t)),
                    "Win Prob": "—", "NN Verdict": "—", "Exp R": "—",
                    # entry-time psychology + UQ from the brain-loop sidecar store
                    **srv._psych_cells(_ftm.get("psychology")),
                    **srv._uq_cells(_ftm.get("uq"))})
        except Exception:
            pass
        # —— UNIFIED TABLE: OpenAlgo sandbox (NSE paper) open positions ——
        try:
            for p in srv._openalgo_positions():
                qty = float(p.get("quantity") or 0.0)
                if not qty:
                    continue        # flat rows belong to the CLOSED table
                avg = float(p.get("average_price") or 0.0)
                ltp = float(p.get("ltp") or avg)
                upnl = float(p.get("pnl") if p.get("pnl") is not None else (ltp - avg) * qty)
                notional = abs(qty) * avg
                nse_pnl += upnl; nse_cap += notional
                rows.append({
                    "Symbol": p.get("symbol"), "Trade Type": "nse-openalgo",
                    "Instrument Type": p.get("product", "—"), "Currency": "INR",
                    "Direction": "LONG" if qty > 0 else "SHORT", "Qty": abs(qty),
                    "Lots": "—", "Lot Size": p.get("lot_size", 1),
                    "Capital": f"₹{notional:,.2f}", "Notional": f"₹{notional:,.2f}",
                    "Leverage": "1×", "Fees": "—",
                    "Entry Price": f"₹{avg:,.2f}", "Current Price": f"₹{ltp:,.2f}",
                    "Unrealized P&L": f"₹{upnl:,.2f}",
                    "Unrealized P&L %": round(float(p.get("pnlpercent") or 0.0), 3),
                    "Peak P/L": "—", "Stop": "—", "Trail Stop": "—",
                    "Tailgate Lock": "—", "Tailgate Trail": "—",
                    "R-multiple": "—", "Efficiency": "—",
                    "Filter": _filter_preset_of(p), "Strategy": p.get("strategy") or "openalgo",
                    "Exchange": p.get("exchange", "NSE"),
                    "Exit Policy": "openalgo-managed", "Liq Price": "—",
                    "Hold Time": "—", "Confidence": "—",
                    "NN Move %": "—", "NN Direction": "—", "Win Prob": "—",
                    "NN Verdict": "—", "Exp R": "—",
                    "Psychology": "—", "Psych Label": "—",
                    "p_up": "—", "Interval ±": "—", "Self-Unc": "—"})
        except Exception:
            pass
        rate = srv._usdinr()
        total_inr = nse_pnl + crypto_pnl * rate     # convert $ → ₹ for the grand total
        body = json.dumps({"columns": srv.OPEN_TRADE_COLUMNS, "rows": rows,
                           "demo": False, "live": True,
                           "nn": (net.info() if net else None),
                           "totals": {"nse_pnl": round(nse_pnl, 2),          # ₹
                                      "binance_pnl": round(crypto_pnl, 2),   # $
                                      "total_inr": round(total_inr, 2),      # ₹ (converted)
                                      "nse_capital": round(nse_cap, 2),
                                      "binance_capital": round(crypto_cap, 2),
                                      "usdinr": round(rate, 2), "open": len(rows)},
                           "note": "live open paper positions — crypto in $ (USDT), NSE in ₹; "
                                   "Win Prob/NN Verdict/Exp R = project node network on the trade row"},
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                           "hint": "live open trades via trading/online/live_loop.py"}).encode()
    return h._send(200, body, "application/json")


def handle_brain_predict(h):
    """GET /api/trading/brain/predict — the trade-row → NEURAL-NETWORK bridge: the project node
    network (GatedMoENode over sklearn experts) trained on the closed-trade journal, run on every
    OPEN trade + a closed-trade replay (predicted vs actual). Memoized single-flight 8s (torch NN
    inference every hit otherwise stampeded the GIL under hub polling)."""
    def _produce_brain_predict():
        try:
            from trading.online.live_loop import get_loop
            net = _srv(h)._trade_outcome_net()
            if net is None:
                # net is None = the TradeOutcomeNet is still training in its background
                # thread (or the journal has <12 closed trades) — NOT an import failure.
                # Report that honestly so the panel shows "warming", not a broken feature.
                return json.dumps({
                    "available": False, "warming": True,
                    "note": ("TradeOutcomeNet is training in the background (rebuilds when "
                             "the closed-trade count changes; needs ≥12 closed trades) "
                             "— retry shortly."),
                }).encode()
            live = get_loop().open_positions()
            open_preds = net.predict(live)
            # replay recent closed trades (predicted p_win vs actual outcome)
            replay = []
            try:
                from trading.journal.journal import TradeJournal
                jr = TradeJournal(state_file="journal.json", persist=True)
                for t in jr._trades[-10:]:
                    d = t.to_dict()
                    pr = net.predict_one(d)
                    actual = "WIN" if float(d.get("net_pnl") or 0.0) > 0 else "LOSS"
                    replay.append({"symbol": d.get("symbol"), "p_win": pr.get("p_win"),
                                   "verdict": pr.get("verdict"), "actual": actual,
                                   "net_pnl": d.get("net_pnl")})
            except Exception:
                replay = []
            return json.dumps({
                "model": net.info(),
                "open_predictions": open_preds,
                "closed_replay": replay,
                "demo": False,
                "note": ("trade rows → project node network → outcome. The network is "
                         "trained on the live closed-trade journal and run on each open "
                         "trade; closed_replay shows predicted p_win vs the actual result. "
                         "engine 'gated_moe' = the real node MoE; 'numpy_logreg' = the "
                         "offline fallback; 'untrained' = need ≥12 closed trades."),
            }, default=str).encode()
        except Exception as e:
            return json.dumps({
                "available": False, "error": f"{type(e).__name__}: {e}",
                "hint": "trade→NN bridge via trading/brain/trade_features.py "
                        "(TradeOutcomeNet) + the closed journal.",
            }).encode()
    body = _srv(h)._cached_body("brain/predict", 8.0, _produce_brain_predict)
    return h._send(200, body, "application/json")


def handle_psychology(h):
    """GET /api/trading/psychology — Trader Psychology (order-book depth): LIVE crowd metrics per
    symbol (OBI, OFI, Stoikov microprice drift, depth-slope, whale walls, spread/λ/VPIN fear +
    composite). ?market&symbol&segment evaluates one on demand; default = every OPEN position."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain.psychology import get_engine
        qs = parse_qs(urlparse(h.path).query)
        eng = get_engine()
        out, errors = [], []
        sym = (qs.get("symbol", [""])[0] or "").strip()
        if sym:
            mkt = (qs.get("market", ["CRYPTO"])[0] or "CRYPTO").upper()
            seg = (qs.get("segment", [""])[0] or None)
            r = eng.evaluate(mkt, sym, segment=seg)
            if r:
                out.append(r)
            else:
                errors.append(f"no depth for {mkt}:{sym}")
        else:
            targets = []
            try:
                from trading.online.live_loop import get_loop
                targets += [(p["market"], p["symbol"], p.get("segment"))
                            for p in get_loop().open_positions()]
            except Exception:
                pass
            try:
                from trading.crypto.engine_client import CryptoEngineClient
                from trading.crypto.freqtrade_ingest import open_trades_view
                targets += [("CRYPTO", t.get("symbol"), "futures")
                            for t in open_trades_view(CryptoEngineClient())]
            except Exception:
                pass
            seen = set()
            for mkt, s, seg in targets[:12]:      # cap per request; engine caches 5s
                if not s or (mkt, s) in seen:
                    continue
                seen.add((mkt, s))
                r = eng.evaluate(mkt, s, segment=seg)
                if r:
                    out.append(r)
        body = json.dumps({"available": True, "rows": out, "errors": errors},
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_brain_ultra(h):
    """GET /api/trading/brain/ultra — Brain ultra-upgrade (Phases A–E): REAL statuses of associative
    memory (HippoRAG PPR + A-MEM), file memory, cloned micro-LLM, Docling perception, Avalanche
    continual, gpt-researcher. ?q=... runs a LIVE associative recall. status → _bg_snapshot (first
    run does LLM calls + file-memory init; not in the request thread)."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain import ultra
        qs = parse_qs(urlparse(h.path).query)

        def _p_ultra():
            st = ultra.status()
            return json.dumps({**st, "available": True}, default=str).encode()
        q = (qs.get("q", [""])[0] or "").strip()
        if q:
            body = json.dumps({"query": q, "hits": ultra.recall(q, k=6),
                               "available": True}, default=str).encode()
        else:
            body = _srv(h)._bg_snapshot("brain/ultra", _p_ultra, ttl=300.0)
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_brain_metacognition(h):
    """GET /api/trading/brain/metacognition — Pillar 17: REAL calibration state of the conformal UQ
    engine (crepes CPS coverage static vs ACI, ECE, adaptive width cap, reliability bins, abstention
    log). ?recalibrate=1 forces a refit. First fit reads the full journal + trains → _bg_snapshot."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.uq import get_uq
        uq = get_uq()
        qs = parse_qs(urlparse(h.path).query)
        if (qs.get("recalibrate", ["0"])[0] or "0") in ("1", "true"):
            uq.recalibrate()

        def _p_meta():
            st = uq.status()
            return json.dumps({"available": True, "status": st,
                               "reliability": st.get("reliability", []),
                               "abstentions": uq.abstentions(40)},
                              default=str).encode()
        body = _srv(h)._bg_snapshot("brain/metacognition", _p_meta, ttl=120.0)
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_brain_debate(h):
    """GET /api/trading/brain/debate — Pillar 18: adversarial bull/bear/risk debate + process-reward
    step verifier over a candidate trade. ?symbol&direction&p_up&sharpe&regime&psychology runs a
    live deliberation → auditable decision_snapshot. LLM failover → _bg_snapshot (off request thread)."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain.debate_gate import get_debate_gate
        qs = parse_qs(urlparse(h.path).query)

        def _g(k, d=None):
            v = qs.get(k, [d])[0]
            return v if v not in (None, "") else d
        symbol = _g("symbol", "BTC/USDT")
        direction = _g("direction", "LONG")
        feats = {}
        for k in ("p_up", "sharpe", "atr", "volatility"):
            v = _g(k)
            if v is not None:
                try:
                    feats[k] = float(v)
                except ValueError:
                    pass
        for k in ("regime", "psychology"):
            v = _g(k)
            if v is not None:
                feats[k] = v

        def _p_debate():
            gate = get_debate_gate()
            res = gate.assess(symbol, direction, features=feats or None)
            return json.dumps({"available": True, "symbol": symbol,
                               "direction": direction, "features": feats,
                               **res}, default=str).encode()
        body = _srv(h)._bg_snapshot(f"brain/debate/{symbol}/{direction}", _p_debate, ttl=45.0)
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_brain_decisions(h):
    """GET /api/trading/brain/decisions — Decision memory (FinMem layers + TradingAgents outcome-
    closure + SHAP attribution): REAL episodes only. ?symbol&q runs a live recall; default returns
    stats + newest episodes."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain.decision_memory import get_memory
        dm = get_memory()
        qs = parse_qs(urlparse(h.path).query)
        sym = (qs.get("symbol", [""])[0] or "").strip()
        q = (qs.get("q", [""])[0] or "").strip()

        def _trim(ep):
            out = {k: ep.get(k) for k in
                   ("episode_id", "trade_id", "engine", "ts", "symbol", "market",
                    "segment", "direction", "entry_price", "strategy", "outcome",
                    "reflection", "pending", "layer", "importance", "recency",
                    "_score")}
            out["attribution_top"] = (ep.get("attribution") or {}).get("top", [])
            return out
        if sym or q:
            eps = dm.recall(symbol=sym, query=q, k=12, resolved_only=False)
        else:
            eps = [dict(e) for e in dm.episodes[-40:]][::-1]
        body = json.dumps({"available": True, "stats": dm.stats(),
                           "episodes": [_trim(e) for e in eps]},
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_gui_status(h):
    """GET /api/trading/gui/status — Computer-use / GUI agent (trading/brain/gui): the brain SEEING
    dashboards, pressing buttons, experimenting, reflecting + growing a Voyager skill library.
    api+html read works today; DOM-click (playwright) + chart OCR (paddleocr) are install-gated.
    observe=1 reads our own dashboard live."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain.gui import register_computer_use_agent
        agent = _srv(h)._gui_agent()
        qs = parse_qs(urlparse(h.path).query)
        if qs.get("observe", ["0"])[0] == "1":
            # deep=True (Playwright DomReader) reads the REACT-RENDERED controls the stdlib parse
            # can't see (→ the old "CONTROLS FOUND 0"). BUT a headless-chromium read takes ~15-20s
            # and MUST NOT run on the request thread — that wedges the server (503). So kick it in
            # the BACKGROUND: this call returns the last cached perception immediately and the deep
            # control count lands on the next poll. A cheap stdlib read runs inline so a first-ever
            # call still returns a (shallow) perception rather than nothing.
            import threading as _th
            g = globals()
            if not g.get("_GUI_DEEP_OBSERVING"):
                g["_GUI_DEEP_OBSERVING"] = True

                def _bg_observe(_ag=agent):
                    try:
                        _ag.observe("own_dashboard", deep=True)
                    except Exception:
                        pass
                    finally:
                        g["_GUI_DEEP_OBSERVING"] = False
                _th.Thread(target=_bg_observe, daemon=True, name="gui-deep-observe").start()
            if getattr(agent, "_last_perception", None) is None:
                agent.observe("own_dashboard")        # cheap stdlib read so the first call is non-empty
        register_computer_use_agent(agent)        # dashboard-sync: node graph
        blob = agent.to_json()
        caps = blob["action_capabilities"]
        body = json.dumps({
            **blob, "available": True,
            "armed_for_live": caps.get("armed_for_live", False),
            "note": ("the brain's computer-use agent: it reads the same JSON the panels/"
                     "charts draw + enumerates pressable controls (stdlib, live today), "
                     "presses buttons via the SAME in-process control surface the UI uses "
                     "(paper-first, dry-run default), and compounds skills by practicing. "
                     "install playwright+paddleocr to add pixel-true DOM clicking + chart "
                     "OCR (vendored source in vendor/browser_use_src + vendor/omniparser)."),
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "computer-use agent via trading/brain/gui (ComputerUseAgent).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_closedtrades(h):
    """GET /api/trading/closedtrades — T6 Closed Trades journal: LIVE persisted journal.json (full
    110-column closed trades) unified with OpenAlgo sandbox round-trips. Falls back to the demo
    journal only while the live journal is empty."""
    srv = _srv(h)
    try:
        from trading.journal.journal import TradeJournal
        from trading.journal.schema import COLUMNS
        from trading.online.live_loop import trade_type as _ttype
        # surface the same friendly columns the open-trades table has, up front
        extra = ["Trade Type", "Currency", "Capital", "Notional", "Fees",
                 "Peak P/L", "Net P&L"]
        cols = extra + COLUMNS
        _CRYPTO_EX = ("binance", "bybit", "okx", "kucoin", "coinbase", "kraken")

        def _is_crypto(r):
            return (r.get("exchange") or "").lower() in _CRYPTO_EX

        def _augment(rws):
            for r in rws:
                sym = "$" if _is_crypto(r) else "₹"
                pp = float(r.get("mfe") or 0.0)         # peak profit (MFE)
                pl = -float(r.get("mae") or 0.0)        # peak loss (MAE, shown negative)
                notional = (r.get("entry_price") or 0) * (r.get("quantity") or 0)
                margin = r.get("margin_used") or notional
                fees = float(r.get("total_charges") or 0.0)  # statutory+broker charges
                net = float(r.get("net_pnl") or 0.0)
                r["Trade Type"] = _ttype("CRYPTO" if _is_crypto(r) else "NSE",
                                         r.get("instrument_type", ""), r.get("product_type", ""),
                                         r.get("exchange", ""))
                r["Currency"] = "USD" if _is_crypto(r) else "INR"
                r["Peak P/L"] = f"{sym}{pp:,.2f}/{sym}{pl:,.2f}"
                r["Capital"] = f"{sym}{float(margin):,.2f}"      # cash committed (margin)
                r["Notional"] = f"{sym}{float(notional):,.2f}"   # leveraged position value
                r["Fees"] = f"{sym}{fees:,.2f}"
                r["Net P&L"] = f"{sym}{net:,.2f}"
            return rws

        def _totals(rws):
            nse = binance = 0.0
            for r in rws:
                net = float(r.get("net_pnl") or 0.0)
                if _is_crypto(r):
                    binance += net          # $
                else:
                    nse += net              # ₹
            rate = srv._usdinr()
            return {"nse_pnl": round(nse, 2), "binance_pnl": round(binance, 2),
                    "total_inr": round(nse + binance * rate, 2),
                    "usdinr": round(rate, 2), "count": len(rws)}
        def _openalgo_closed_rows():
            # UNIFIED TABLE: OpenAlgo sandbox round-trips — flat (qty=0) positions
            # carry the realized P&L; fills come from the sandbox tradebook.
            out = []
            try:
                fills = {}
                for t in srv._openalgo_tradebook():
                    fills.setdefault(t.get("symbol"), []).append(t)
                for p in srv._openalgo_positions():
                    if float(p.get("quantity") or 0.0):
                        continue        # still open → belongs to the OPEN table
                    net = float(p.get("pnl") or 0.0)
                    fl = fills.get(p.get("symbol")) or []
                    last = fl[-1] if fl else {}
                    out.append({
                        "symbol": p.get("symbol"), "exchange": p.get("exchange", "NSE"),
                        "quantity": max((float(f.get("quantity") or 0) for f in fl), default=0),
                        "entry_price": (float(fl[0].get("average_price") or 0) if fl else None),
                        "exit_price": (float(last.get("average_price") or 0) if fl else None),
                        "exit_datetime": last.get("timestamp"),
                        "net_pnl": net, "pnl": net,
                        "strategy": p.get("strategy") or last.get("strategy") or "openalgo",
                        "product_type": p.get("product", ""),
                        "exit_reason": "openalgo-sandbox",
                        "Trade Type": "nse-openalgo", "Currency": "INR",
                        "Capital": "—", "Notional": "—", "Fees": "—",
                        "Peak P/L": "—", "Net P&L": f"₹{net:,.2f}"})
            except Exception:
                pass
            return out
        live = TradeJournal(state_file="journal.json", persist=True)
        oa_rows = _openalgo_closed_rows()
        if live._trades or oa_rows:
            rows = _augment([t.to_dict() for t in live._trades]) + oa_rows
            body = json.dumps({"columns": cols, "rows": rows, "demo": False,
                               "live": True, "count": len(rows), "totals": _totals(rows),
                               "note": "live journal.json + OpenAlgo sandbox — unified closed trades"},
                              default=str).encode()
        else:
            from run_journal_t5 import build_demo_journal
            rows = _augment([t.to_dict() for t in build_demo_journal().trades])
            body = json.dumps({"columns": cols, "rows": rows, "demo": True,
                               "totals": _totals(rows),
                               "note": "no live closed trades yet — showing demo journal"},
                              default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                           "hint": "live journal via trading/journal/journal.py"}).encode()
    return h._send(200, body, "application/json")


_CONF_CACHE: dict = {"ts": 0.0, "body": None}


def handle_confidence(h):
    """GET /api/trading/confidence — T6 per-symbol Brain confidence book: real Bayesian win-rate +
    Brier calibration off the LIVE journal.json, flattened to a list. Demo book while journal empty.

    TTL-cached 60s (brain-health 2026-07-17): the handler constructed TradeJournal() PER REQUEST
    — the measured 22s/request scar class (7k+ dataclass builds; see the _closed_tail lesson,
    commit 6f75790 family). 60s staleness is far fresher than the 5m bar the numbers describe."""
    import time as _t
    if _CONF_CACHE["body"] is not None and _t.time() - _CONF_CACHE["ts"] < 60.0:
        return h._send(200, _CONF_CACHE["body"], "application/json")
    def _flatten_book(book):
        return [
            {"symbol": s,
             "confidence": d.get("confidence"),
             "win_rate": d.get("win_rate"),
             "n": d.get("n"),
             "brier": d.get("brier")}
            for s, d in book.get("symbols", {}).items()
        ]
    try:
        from trading.journal.journal import TradeJournal
        jr = TradeJournal(state_file="journal.json", persist=True)
        book = jr.confidence.as_dict()
        symbols = _flatten_book(book)
        if symbols:
            body = json.dumps({
                "symbols": symbols,
                "demo": False, "live": True,
                # calibration truth (2026-07-10): overall Brier + ECE + reliability bins
                # over trades that carried a real (>0) brain forecast
                "overall_brier": book.get("overall_brier"),
                "ece": book.get("ece"),
                "reliability": book.get("reliability"),
                "calib_n": book.get("calib_n"),
                "note": "live journal.json confidence book — Bayesian win-rate + Brier + ECE",
            }, default=str).encode()
        else:
            from run_journal_t5 import build_demo_journal
            symbols = _flatten_book(build_demo_journal().confidence.as_dict())
            body = json.dumps({
                "symbols": symbols,
                "demo": True,
                "note": ("no live trades yet — offline demo confidence book "
                         "(run_journal_t5); real computed Bayesian win-rate + Brier"),
            }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T6 confidence not importable "
                    "(see trading/journal/confidence.py and blueprint §T5).",
        }).encode()
        return h._send(200, body, "application/json")   # errors are NOT cached
    _CONF_CACHE.update(ts=_t.time(), body=body)
    return h._send(200, body, "application/json")


def handle_dreams(h):
    """GET /api/trading/dreams — Counterfactual Dream-Trainer lessons (2026-07-10):
    per-(strategy, market) regret decomposition (exit-timing / direction / tailgate-capture)
    dreamed off real journal excursions each learn cycle. State-file-only read."""
    try:
        from trading.brain import dreamer
        body = json.dumps({**dreamer.status(), "live": True, "demo": False},
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_gate_tuning(h):
    """GET /api/trading/gate_tuning — counterfactual θ sweeps for the UQ / confidence
    gates off the explore-open-all journal (trading/brain/gate_tuner, 2026-07-10).
    Recommendation-only; state-file read."""
    try:
        from trading.brain import gate_tuner
        body = json.dumps({**gate_tuner.status(), "live": True, "demo": False},
                          default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_mirror_stream(h):
    """GET /api/trading/mirror/stream — LIVE MJPEG mirror of the brain's Xvfb display
    (ffmpeg x11grab, viewer-demand: capture runs only while someone watches). 503 with
    the honest reason when no headed display/ffmpeg is up — the panel then falls back
    to the existing per-action frame polling."""
    try:
        from trading.broker_sense import live_mirror
        gen = live_mirror.frames()
        first = next(gen)                          # surface start-up errors as 503
    except Exception as e:
        return h._send(503, json.dumps({"available": False,
                                        "error": str(e)[:200]}).encode(),
                       "application/json")
    try:
        h.send_response(200)
        h.send_header("Content-Type",
                      "multipart/x-mixed-replace; boundary=mlnbframe")
        h.send_header("Cache-Control", "no-cache")
        h.end_headers()
        for jpg in __import__("itertools").chain([first], gen):
            h.wfile.write(b"--mlnbframe\r\nContent-Type: image/jpeg\r\n"
                          b"Content-Length: " + str(len(jpg)).encode()
                          + b"\r\n\r\n" + jpg + b"\r\n")
            h.wfile.flush()
    except (BrokenPipeError, ConnectionResetError, OSError):
        pass                                       # viewer left → generator cleanup
    finally:
        try:
            gen.close()
        except Exception:
            pass
    return None


def handle_direction_truth(h):
    """GET /api/trading/direction/truth — D1 Direction Truth Ledger (goal Pillar 27).

    Real measured direction accuracy per source×regime×horizon with Wilson CIs, straight
    off direction_truth.json (state-file read, request-thread safe). ?min_n=N filters
    thin buckets; ?full=1 returns every bucket row for the drill-down table."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.broker_sense import watchlist_study
        from trading.direction import (meta_labeler, mirror_gate, pullback,
                                       truth_ledger)
        qs = parse_qs(urlparse(h.path).query)
        out = {**truth_ledger.status(), "live": True, "demo": False,
               "mirror": mirror_gate.status(), "meta": meta_labeler.status(),
               "pullback": pullback.status(), "study": watchlist_study.status()}
        if (qs.get("full") or ["0"])[0] in ("1", "true"):
            min_n = int((qs.get("min_n") or ["10"])[0])
            out["buckets"] = truth_ledger.hit_rates(min_n=min_n)
        body = json.dumps(out, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_postmortem(h):
    """GET /api/trading/postmortem — Trade Post-Mortem & Excursion Engine (owner ask 2026-07-13).

    Real mined winning/losing trade patterns + commonality + per-(symbol,regime) ideal-entry
    offsets, straight off postmortem_patterns.json / postmortem_excursion.json. STATE-FILE READ
    ONLY (postmortem.status() calls no pandas/pysubgroup) → request-thread safe; the mining that
    writes those files runs in the funnel-learn daemon, never here. ?market=CRYPTO|NSE filters."""
    try:
        from urllib.parse import parse_qs, urlparse
        from trading.brain import postmortem
        qs = parse_qs(urlparse(h.path).query)
        market = (qs.get("market") or [""])[0].strip().upper() or None
        out = {**postmortem.status(market), "live": True}
        body = json.dumps(out, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_learning_curve(h):
    """GET /api/trading/learning_curve — is the brain IMPROVING? (owner ask 2026-07-10).

    Real series straight off journal.json + learn_loop state, no synthesis:
      daily    — per-close-date trades / win-rate / Brier (forecast-carrying rows only);
      rolling  — last-100-trades win rate sampled every 25 closes (the graduation signal);
      knowledge— learn-loop cycles + latest FSRS retention eval + UQ calibration snapshot.
    Cached via the server-level SWR table (_HEAVY_TTL) — the journal parse is the cost."""
    try:
        from trading import state as tstate
        rows = [r for r in (tstate.load_json("journal.json", []) or [])
                if isinstance(r, dict)]
        daily: dict = {}
        for r in rows:
            d = str(r.get("exit_datetime") or "")[:10]
            if not d:
                continue
            b = daily.setdefault(d, {"n": 0, "wins": 0, "br_s": 0.0, "br_n": 0})
            won = 1 if (r.get("net_pnl") or 0) > 0 else 0
            b["n"] += 1
            b["wins"] += won
            p = r.get("brain_confidence_entry")
            try:
                p = float(p) if p is not None else None
            except (TypeError, ValueError):
                p = None
            if p is not None and p > 1.0:
                p /= 100.0
            if p is not None and 0.0 < p <= 1.0:      # <=0 = missing-value artifact
                b["br_s"] += (p - won) ** 2
                b["br_n"] += 1
        daily_series = [{"date": d, "trades": b["n"],
                         "win_rate": round(b["wins"] / b["n"], 4),
                         "brier": round(b["br_s"] / b["br_n"], 4) if b["br_n"] else None}
                        for d, b in sorted(daily.items())]
        closes = [1 if (r.get("net_pnl") or 0) > 0 else 0 for r in rows]
        rolling = [{"trade_i": i,
                    "win_rate_100": round(sum(closes[max(0, i - 100):i]) /
                                          len(closes[max(0, i - 100):i]), 4)}
                   for i in range(100, len(closes) + 1, 25)]
        ll = tstate.load_json("learn_loop.json", {}) or {}
        body = json.dumps({
            "daily": daily_series[-60:],
            "rolling": rolling[-80:],
            "knowledge": {"cycles": ll.get("cycles"), "topics_done": len(ll.get("done") or []),
                          "last_eval": ll.get("last_eval"), "last_uq": ll.get("last_uq")},
            "n_trades": len(rows), "live": True, "demo": False,
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_context(h):
    """GET /api/trading/context — T6 market-context strip. Crypto Fear & Greed LIVE (alternative.me,
    free); India VIX LIVE when OpenAlgo returns a real ltp, else honest demo; FII/DII stays
    available:false (no free live source). available:false ⇒ never live."""
    try:
        # ── crypto Fear & Greed (LIVE, free, no key) ──────────────────────
        fear_greed = {
            "value": 62, "available": False,
            "note": "live crypto Fear & Greed unavailable — illustrative demo value",
        }
        try:
            import urllib.request
            fng = json.load(urllib.request.urlopen(
                "https://api.alternative.me/fng/", timeout=8))["data"][0]
            fear_greed = {
                "value": int(fng["value"]),
                "classification": fng.get("value_classification"),
                "available": True,
                "source": "alternative.me",
            }
        except Exception:
            pass

        # ── India VIX (LIVE via OpenAlgo if a real ltp comes back) ─────────
        india_vix = {
            "value": 13.85, "available": False,
            "note": "no live NSE India VIX feed wired — illustrative demo value",
        }
        try:
            from trading.openalgo_client import OpenAlgoClient
            oc = OpenAlgoClient()
            ltp = None
            for sym, exch in (("INDIA VIX", "NSE_INDEX"),
                              ("INDIAVIX", "NSE_INDEX"),
                              ("INDIA VIX", "NSE")):
                try:
                    q = oc.quote(sym, exchange=exch)
                    data = q.get("data", q) if isinstance(q, dict) else {}
                    cand = data.get("ltp")
                    if cand is not None and float(cand) > 0:
                        ltp = float(cand)
                        break
                except Exception:
                    continue
            if ltp is not None:
                india_vix = {"value": ltp, "available": True, "source": "openalgo:NSE"}
        except Exception:
            pass

        live = fear_greed.get("available") or india_vix.get("available")
        body = json.dumps({
            "india_vix": india_vix,
            "fii_dii": {
                "available": False,
                "fii_net_cr": 1240.5, "dii_net_cr": -310.8,
                "note": "no free live FII/DII provisional feed — illustrative demo values",
            },
            "fear_greed": fear_greed,
            "demo": not live,
        }, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T6 context builder failed.",
        }).encode()
    return h._send(200, body, "application/json")


def handle_pnl_demos(h):
    """GET /api/trading/{screener,exits,sizing}/status — P2 screeners · P3 trailing exits · P4
    position sizing, offline demo snapshots. One handler for the three (kind from the path)."""
    path = h.path.split("?", 1)[0]
    kind = path.rsplit("/", 2)[1]
    _builders = {"screener": ("trading.screener", "build_demo_screener"),
                 "exits": ("trading.exits", "build_demo_trailing"),
                 "sizing": ("trading.sizing", "build_demo_sizing")}
    mod, fn = _builders[kind]
    try:
        import importlib
        res = getattr(importlib.import_module(mod), fn)()
        if kind == "screener":            # build_demo_screener returns a Screener
            snap = {"status": res.status(),
                    "nse_watchlist": res.watchlist("NSE", ["intraday", "fno", "commodities"],
                                                   per_segment=3),
                    "crypto_watchlist": res.watchlist("CRYPTO", ["spot", "futures", "options"],
                                                      per_segment=3)}
        else:
            snap = res
        snap["demo"] = True
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                           "hint": f"{kind} module (trading/{kind}/)"}).encode()
    return h._send(200, body, "application/json")


def handle_watchlist(h):
    """GET /api/trading/watchlist — live per-market watchlist (symbol+segment the loop trades) +
    fresh screener candidates for the SELECTED segments of each market."""
    try:
        from trading.online import controls
        from trading.online.live_loop import get_loop
        loop = get_loop()
        view = loop.watchlist_view()
        sc = loop.screener()
        filters = loop._screen_filters()
        candidates = {}
        if sc is not None:
            for m in ("NSE", "CRYPTO"):
                segs = list(getattr(controls.registry().get(m), "segments", []) or [])
                try:
                    candidates[m] = (sc.watchlist(m, segs, per_segment=6, filters=filters)
                                     if segs else [])
                except Exception:
                    candidates[m] = []
        body = json.dumps({"watchlist": view, "candidates": candidates,
                           "live": True}, default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_online_loop(h):
    """GET /api/trading/online/loop — live trade-loop telemetry: ticks, decisions, open/closed
    counts, last tick, errors."""
    try:
        from trading.online.live_loop import get_loop
        body = json.dumps(get_loop().status(), default=str).encode()
    except Exception as e:
        body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_onchain(h):
    """GET /api/trading/onchain — idea #11 on-chain + whale alt-data lane: live composite flow/risk
    signal from FREE keyless sources (Fear&Greed + blockchain.info avg-tx whale proxy + mempool.space).
    Pairs with /api/trading/news/status as the full alt-data feed. Cached 60s (external HTTP)."""
    def _p_onchain():
        from trading.altdata.onchain import OnChainAltData
        return json.dumps(OnChainAltData().snapshot(), default=str).encode()
    return h._send(200, _srv(h)._cached_body("trading/onchain", 60.0, _p_onchain), "application/json")


def handle_online_status(h):
    """GET /api/trading/online/status — honest O5 online-control snapshot: the SHARED persisted
    control surface (per-market enable/mode/allow_live/trading_state + editable paper wallets) +
    each market's live LIVE↔REPLAY session mode. Markets default OFF + PAPER (safe)."""
    try:
        from trading.online import controls
        from trading.online.session import MarketSession
        snap = controls.status()
        snap["sessions"] = {m: MarketSession(m).status()
                            for m in snap.get("markets", {})}
        snap.setdefault("note", "")
        body = json.dumps(snap, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading O5 online controls not importable "
                    "(see trading/online/ and trading-execution-blueprint.md ONLINE).",
        }).encode()
    return h._send(200, body, "application/json")


# ── Broker-Sense Funnel (trading/broker_sense) ────────────────────────────────────────
_BS_FUNNELS: dict = {}


def _bs_funnel(market: str):
    """Lazy per-market funnel singleton. Cheap to build: Playwright only starts when a
    cycle actually opens a page, never on a status poll."""
    if market not in _BS_FUNNELS:
        from trading.broker_sense.funnel import BrokerSenseFunnel
        _BS_FUNNELS[market] = BrokerSenseFunnel(market)
    return _BS_FUNNELS[market]


def handle_broker_sense(h):
    """GET /api/trading/broker_sense — the Broker-Sense Funnel: broker web-app screeners →
    candle-image CNN → screen-mirror book → paper exec via APIs. Shows the REAL funnel
    state (last cycle stages, hot watchlist, sessions/pending OTP asks, discovered
    learning columns, preset performance, execution role map). ?market=crypto|nse."""
    try:
        from urllib.parse import parse_qs, urlparse
        qs = parse_qs(urlparse(h.path).query)
        market = (qs.get("market", ["crypto"])[0] or "crypto").lower()
        f = _bs_funnel(market if market in ("crypto", "nse") else "crypto")
        payload = {"available": True, **f.status()}
        if market == "nse":
            # NSE DATA SOURCE (owner 2026-07-14): selection reads off the Zerodha Kite (KiteTicker)
            # in-RAM mirror — the owner's PAID feed. Surface its REAL freshness so the panel shows
            # "in-RAM (Zerodha Kite)" vs "api-fallback"/"cold" honestly, driven by live numbers
            # (connected + not stale + symbols streaming), never a hardcoded label.
            # CROSS-PROCESS: the mirror's RAM lives in the FUNNEL process — this dashboard runs
            # NO_LOOP=1 and never starts one, so its in-process status() is always "cold" (live-caught
            # 2026-07-16). Read the funnel's 10s snapshot instead, and age-gate it so a dead funnel
            # can never read as warm.
            try:
                from trading import state

                from trading.broker_sense import kite_stream
                snap = state.load_json(kite_stream._STATUS_FILE, {}) or {}
                ks = snap.get("status") or {}
                snap_age = time.time() - (snap.get("ts") or 0.0)
                warm = (bool(ks.get("connected")) and not ks.get("stale")
                        and (ks.get("symbols_ticker") or 0) > 0 and snap_age <= 60.0)
                payload["nse_data"] = {
                    "source": ("in-RAM (Zerodha Kite)" if warm else
                               ("cold" if ks.get("have_creds") else "api-fallback")),
                    "mirror": {**ks, "snapshot_age_s": round(snap_age, 1) if snap else None},
                }
            except Exception:
                pass
        body = json.dumps(payload, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "Broker-Sense funnel via trading/broker_sense (see "
                    "research/broker-sense-design.md).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_app_school(h):
    """GET /api/trading/app_school — what the brain has LEARNED about driving each broker app:
    the golden routes to each market-data kind (which control led there + the endpoint), goal
    coverage, and exploration stats. POST {op:'explore', broker} kicks off a learning run in the
    background (read-only; it only clicks to look, never trades)."""
    from trading.broker_sense.app_school import get_school
    school = get_school()
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            broker = str(data.get("broker", "binance")).lower()
            if data.get("op") == "explore":
                # SUBPROCESS (not a thread): Playwright's sync API is bound to its creating
                # thread — driving it from a dashboard daemon thread raises greenlet
                # "cannot switch to a different thread". A subprocess has its own main thread
                # + browser, so the crawl actually runs. Read-only; never places an order.
                import subprocess
                import sys as _sys
                subprocess.Popen(
                    [_sys.executable, "-m", "trading.broker_sense.run_app_school", broker,
                     "150", "60"],
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                body = json.dumps({"ok": True, "started": broker,
                                   "note": "learning run started in a subprocess (read-only); "
                                           "GET to watch pages/links/routes grow"}).encode()
            else:
                body = json.dumps({"ok": False, "error": "unknown op"}).encode()
        except Exception as e:
            body = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}).encode()
        return h._send(200, body, "application/json")
    body = json.dumps({"available": True, **school.status()}, default=str).encode()
    return h._send(200, body, "application/json")


def handle_memory_search(h):
    """GET /api/trading/memory_search — cross-session FULL-TEXT search over the brain's whole memory
    (associative notes, decision episodes, reflexion lessons, mind-stream, learning log, agent
    memory files, per-skill learnings). Query: q (required), k (default 10), sources (comma list).
    No q → the index status (honest: real counts per source)."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    g = lambda k, d="": (qs.get(k, [d])[0])
    try:
        from trading.brain.memory_search import get_search
        ms = get_search()
        q = g("q", "").strip()
        if not q:
            out = {"available": True, **ms.status()}
        else:
            srcs = [s for s in g("sources", "").split(",") if s] or None
            hits = ms.search(q, k=int(g("k", "10") or 10), sources=srcs)
            out = {"available": True, "query": q, "n": len(hits), "hits": hits,
                   "index": ms.status()}
    except Exception as e:
        out = {"available": False, "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")


def handle_connectivity(h):
    """GET /api/trading/connectivity — the self-healing wiring watchdog: NEW orphan modules / dead
    endpoints since the accepted baseline (a REGRESSION = something that was wired came unwired).
    Backlog counts shown for reference. POST {op:'rebaseline'} accepts the current wiring as OK."""
    from trading.brain import connectivity_monitor as cm
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            out = cm.rebaseline() if str(data.get("op")) == "rebaseline" else {"ok": False}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(out, default=str).encode(), "application/json")
    return h._send(200, json.dumps({"available": True, **cm.scan_async()}, default=str).encode(),
                   "application/json")


def handle_sandbox(h):
    """GET /api/trading/sandbox — the brain's FAST paper-trading sandbox: wallet, open positions
    (live PnL + tailgate lock), win-rate. POST {op:'enable'|'disable'|'reset'|'tick'}. Honest: a
    LEARNING sandbox (simple fast fills) — Freqtrade is the faithful bridge to real money."""
    from trading.sandbox.paper_sandbox import get_sandbox
    sb = get_sandbox()
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            op = str(data.get("op", "")).lower()
            if op == "enable":
                out = {"ok": True, **sb.set_enabled(True)}
            elif op == "disable":
                out = {"ok": True, **sb.set_enabled(False)}
            elif op == "reset":
                out = {"ok": True, **sb.reset()}
            elif op == "tick":
                out = {"ok": True, "tick": sb.tick()}
            elif op == "set_params":
                out = {"ok": True, **sb.set_params(
                    starting_balance=data.get("starting_balance"),
                    stake=data.get("stake"),
                    leverage=data.get("leverage"),
                )}
            elif op == "set_mode":
                out = {"ok": True, **sb.set_mode(data.get("mode"))}
            else:
                out = {"ok": False,
                       "error": "op must be enable|disable|reset|tick|set_params|set_mode"}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(out, default=str).encode(), "application/json")
    body = json.dumps({"available": True, **sb.status(), "open": sb.open_view()},
                      default=str).encode()
    return h._send(200, body, "application/json")


def handle_trade_columns(h):
    """GET /api/trading/trade_columns — the self-growing trade-table columns: genuine NEW columns
    the App Driving School discovered on the broker apps (distilled from noise, cross-checked vs
    the journal schema), plus which are already accepted. POST {op:'accept'|'reject', column}.
    Honest: proposals trace to the exact app label they were seen as."""
    from trading.broker_sense import trade_columns as tc
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            op = str(data.get("op", "")).lower()
            col = str(data.get("column", ""))
            if op == "accept":
                out = {"ok": True, **tc.accept(col)}
            elif op == "reject":
                out = {"ok": True, **tc.reject(col)}
            else:
                out = {"ok": False, "error": "op must be accept|reject"}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(out, default=str).encode(), "application/json")
    body = json.dumps({"available": True, "accepted": tc.accepted(), **tc.propose()},
                      default=str).encode()
    return h._send(200, body, "application/json")


def handle_segments(h):
    """GET /api/trading/segments — the GLOBAL segment-focus control. Per market (CRYPTO, NSE) it
    returns every segment + whether it is ACTIVE right now (boss.active_segments). This ONE switch
    gates the WHOLE brain — news, strategy research, feature-discovery, learning, the funnel all
    read boss.active_segments, so turning a segment off here makes the brain stop focusing on it
    everywhere. POST {market, segment, on:bool} toggles one; {market, all:bool} toggles all."""
    from trading.brain import boss
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            market = str(data.get("market", "CRYPTO")).upper()
            allv = data.get("all")
            if allv is not None:
                segs = list(boss.all_segments(market))
                boss.set_segments(market, enable=segs if allv else None,
                                  disable=None if allv else segs)
            else:
                seg = str(data.get("segment", "")).lower()
                on = bool(data.get("on"))
                boss.set_segments(market, enable=[seg] if on else None,
                                  disable=None if on else [seg])
            out = {"ok": True, **_segments_snapshot()}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(out, default=str).encode(), "application/json")
    return h._send(200, json.dumps({"available": True, **_segments_snapshot()},
                                   default=str).encode(), "application/json")


def _segments_snapshot() -> dict:
    from trading.brain import boss
    out = {"markets": {}}
    for mk in ("CRYPTO", "NSE"):
        active = set(boss.active_segments(mk))
        out["markets"][mk] = {"segments": [{"name": s, "active": s in active}
                                           for s in boss.all_segments(mk)],
                              "active": sorted(active), "paused": boss.is_paused(mk)}
    # which brain features honor the gate (HONEST wiring — only the ones that actually read
    # boss.active_segments; verified by toggling + checking each reads the gate)
    out["applies_to"] = ["crypto brain-loop (entries)", "Broker-Sense funnel (screen/execute)",
                         "broker built-in pickers (feature-discovery)", "strategy foundry (research)"]
    return out


def handle_broker_features(h):
    """GET /api/trading/broker_features — the broker apps' OWN built-in pickers: the catalog per
    broker, each picker's LEARNED weight (how its picks performed), invented presets, and a live
    cross-broker regime read. POST {op:'read', broker} reads every picker in parallel + fuses;
    {op:'invent', broker} composes a new screener preset; {op:'cross'} runs the cross-broker check.
    All read-only (never places an order)."""
    from trading.broker_sense import broker_features as bf
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            op = str(data.get("op", "")).lower()
            broker = str(data.get("broker", "binance")).lower()
            if op == "read":
                import subprocess
                import sys as _sys
                # subprocess: Playwright can't run in the dashboard's request thread (greenlet)
                subprocess.Popen(
                    [_sys.executable, "-m", "trading.broker_sense.run_broker_features", broker],
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                out = {"ok": True, "started": broker, "note": "reading all built-in pickers in "
                       "parallel (subprocess); GET to see fused picks + learned weights"}
            elif op == "invent":
                out = {"ok": True, "invented": bf.invent_preset(broker, int(data.get("cycle", 0)))}
            elif op == "cross":
                out = {"ok": True, "cross": bf.cross_broker_signals()}
            else:
                out = {"ok": False, "error": "op must be read|invent|cross"}
        except Exception as e:
            out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(out, default=str).encode(), "application/json")
    body = json.dumps({"available": True, **bf.status()}, default=str).encode()
    return h._send(200, body, "application/json")


def handle_broker_sources(h):
    """GET /api/trading/broker_sources — per-broker PUBLIC-vs-ACCOUNT data-source switch.
    POST {op:'set', broker, public:bool} flips it. When public=OFF the funnel screens from the
    LOGGED-IN account page instead of public screeners (owner's account-first idea)."""
    from trading.broker_sense import data_sources as ds
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            import json as _json
            data = _json.loads(h.rfile.read(length) or b"{}") if length else {}
            broker = str(data.get("broker", "")).lower()
            if data.get("op") == "set" and broker:
                ds.set_public(broker, bool(data.get("public", True)))
            body = _json.dumps({"ok": True, "sources": ds.status()}).encode()
        except Exception as e:
            body = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}).encode()
        return h._send(200, body, "application/json")
    body = json.dumps({"available": True, "sources": ds.status()}, default=str).encode()
    return h._send(200, body, "application/json")


def handle_remote_login(h):
    """GET /api/trading/remote_login?broker= — status of the remote-view login browser.
    POST {op:'start'|'stop', broker} — bring up / tear down the Xvfb+chromium+x11vnc+noVNC stack
    so the operator can solve the broker's CAPTCHA/OTP over VNC; 'stop' saves the session."""
    import subprocess
    from urllib.parse import parse_qs, urlparse
    script = "/home/karan18190164/tools/remote_login.sh"
    _PORT = {"binance": 6080, "angelone": 6081}

    def _run(op, broker):
        try:
            r = subprocess.run(["bash", script, op, broker], capture_output=True,
                               text=True, timeout=60)
            return (r.stdout or "") + (r.stderr or "")
        except Exception as e:
            return f"error: {type(e).__name__}: {e}"

    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            broker = str(data.get("broker", "binance")).lower()
            op = str(data.get("op", "status"))
            if op not in ("start", "stop", "status"):
                op = "status"
            out = _run(op, broker)
            missing = "MISSING x11vnc" in out or "MISSING Xvfb" in out
            body = json.dumps({
                "ok": not missing, "op": op, "broker": broker, "output": out.strip()[:1200],
                "novnc_path": f"/novnc/vnc.html?path=websockify&autoconnect=1&resize=scale",
                "needs_install": missing,
                "install_hint": ("sudo apt-get install -y xvfb xauth x11vnc && sudo "
                                 "/home/karan18190164/.venv/bin/python -m playwright "
                                 "install-deps chromium") if missing else "",
            }).encode()
        except Exception as e:
            body = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}).encode()
        return h._send(200, body, "application/json")

    qs = parse_qs(urlparse(h.path).query)
    broker = (qs.get("broker", ["binance"])[0] or "binance").lower()
    out = _run("status", broker)
    body = json.dumps({"available": True, "broker": broker, "status": out.strip()[:1200],
                       "web_port": _PORT.get(broker, 6082),
                       "novnc_path": "/novnc/vnc.html?path=websockify&autoconnect=1&resize=scale"},
                      default=str).encode()
    return h._send(200, body, "application/json")


def handle_mirror(h):
    """GET /api/trading/mirror[?broker=&limit=] — the Brain Screen Mirror status + action feed.

    Read-only view of the browsers the BRAIN drives (funnels / watchlist hand / app-school):
    per-broker frame age + LIVE/STALE, the page it's on, and the newest actions (opens,
    clicks with coordinates, reads, order-guard blocks). Pure state-file reads — safe in a
    request thread (no heavy imports, no browser calls)."""
    from urllib.parse import parse_qs, urlparse

    from trading.broker_sense import screen_mirror
    qs = parse_qs(urlparse(h.path).query)
    broker = (qs.get("broker", [""])[0] or "").lower()
    try:
        limit = int(qs.get("limit", ["60"])[0])
    except ValueError:
        limit = 60
    try:
        st = screen_mirror.status()
        if broker:
            st["actions"] = screen_mirror.actions(broker, limit=limit)
        body = json.dumps(st, default=str).encode()
    except Exception as e:
        body = json.dumps({"enabled": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_binance_edge(h):
    """GET /api/trading/binance — the Binance compute-offload edge (mirror status, top movers,
    funding extremes, liquidations, listing catalysts). STATE-FILE-ONLY read (hard rule: no mirror
    socket / heavy import in the request thread) — the funnel process writes the snapshot every ~10s."""
    import os as _os

    from trading import state
    p = _os.path.join(str(state.STATE_DIR), "binance_edge", "snapshot.json")
    try:
        if _os.path.exists(p):
            with open(p, "rb") as f:
                return h._send(200, f.read(), "application/json")
    except Exception as e:
        return h._send(200, json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode(),
                       "application/json")
    return h._send(200, json.dumps({"available": False,
                   "note": "mirror snapshot not written yet — start the crypto funnel (BINANCE_STREAM=1)"}
                   ).encode(), "application/json")


def handle_handoff(h):
    """GET /api/trading/handoff — human-CAPTCHA handoff state (which brokers are paused on a
    security challenge, VNC health, noVNC path). Pure state-file read; safe in a request thread.

    POST {op:'take_control'|'resume'|'stop', broker} — bring up the interactive noVNC on the
    brain's shared display / force-resume a broker / tear the VNC down. Never raises."""
    from trading.broker_sense import human_handoff
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            op = str(data.get("op", "")).lower()
            broker = str(data.get("broker", "")).lower()
            if op == "take_control":
                body = human_handoff.take_control(broker)
            elif op == "resume":
                body = human_handoff.request_resume(broker)
            elif op == "stop":
                body = human_handoff.stop_control()
            else:
                body = {"ok": False, "error": f"unknown op: {op!r}"}
            body = {**body, "status": human_handoff.status()}
        except Exception as e:
            body = {"ok": False, "error": f"{type(e).__name__}: {e}"}
        return h._send(200, json.dumps(body, default=str).encode(), "application/json")
    try:
        body = json.dumps(human_handoff.status(), default=str).encode()
    except Exception as e:
        body = json.dumps({"enabled": False, "any_active": False,
                           "error": f"{type(e).__name__}: {e}"}).encode()
    return h._send(200, body, "application/json")


def handle_mirror_frame(h):
    """GET /api/trading/mirror/frame?broker= — latest JPEG frame of the brain's browser."""
    from urllib.parse import parse_qs, urlparse

    from trading.broker_sense import screen_mirror
    qs = parse_qs(urlparse(h.path).query)
    broker = (qs.get("broker", ["binance"])[0] or "binance").lower()
    try:
        jpeg = screen_mirror.frame(broker)
    except Exception:
        jpeg = None
    if not jpeg:
        return h._send(204, b"", "image/jpeg")
    return h._send(200, jpeg, "image/jpeg")


def handle_live_browser_frame(h):
    """GET /api/trading/live_browser/frame?broker= — the current JPEG frame of the live browser."""
    from urllib.parse import parse_qs, urlparse

    from trading.broker_sense.live_browser import get_live_browser
    qs = parse_qs(urlparse(h.path).query)
    broker = (qs.get("broker", ["binance"])[0] or "binance").lower()
    jpeg = None
    try:
        jpeg = get_live_browser().frame(broker)
    except Exception:
        jpeg = None
    if not jpeg:
        return h._send(204, b"", "image/jpeg")
    return h._send(200, jpeg, "image/jpeg")


def handle_live_browser(h):
    """GET /api/trading/live_browser?broker= — status. POST {op, broker, ...} drives it:
    op=start|stop|click(x,y)|type(text)|key(key)|scroll(dy)|nav(url)|save. Lets the operator
    complete a broker login (CAPTCHA/OTP) from the dashboard; 'save' persists the session."""
    from trading.broker_sense.live_browser import get_live_browser
    lb = get_live_browser()
    _LOGIN_URL = {"binance": "https://accounts.binance.com/en/login",
                  "angelone": "https://www.angelone.in/login/",
                  "upstox": "https://login.upstox.com/",     # instant QR — scan with the app
                  "groww": "https://groww.in/login"}
    if h.command == "POST":
        try:
            length = int(h.headers.get("content-length", 0) or 0)
            data = json.loads(h.rfile.read(length) or b"{}") if length else {}
            broker = str(data.get("broker", "binance")).lower()
            op = str(data.get("op", "status"))
            if op == "start":
                out = lb.start(broker, data.get("url") or _LOGIN_URL.get(broker, ""))
            elif op == "stop":
                out = lb.stop(broker)
            elif op in ("click", "type", "key", "scroll", "nav", "save", "status"):
                out = lb.action(broker, op, x=data.get("x"), y=data.get("y"),
                                text=data.get("text"), key=data.get("key"),
                                dy=data.get("dy"), url=data.get("url"))
            else:
                out = {"error": f"unknown op {op}"}
            body = json.dumps({"broker": broker, "op": op, **(out or {})}, default=str).encode()
        except Exception as e:
            body = json.dumps({"ok": False, "error": f"{type(e).__name__}: {e}"}).encode()
        return h._send(200, body, "application/json")

    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    broker = (qs.get("broker", ["binance"])[0] or "binance").lower()
    try:
        st = lb.status(broker)
    except Exception as e:
        st = {"running": False, "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps({"available": True, **st}, default=str).encode(),
                   "application/json")


def handle_ocular(h):
    """GET /api/trading/ocular — the Ocular Cortex (the brain's eyes + visual memory).

    Shows REAL state: which free vision providers are online, how many frames perceived /
    novel / vision-read this session, the consolidated per-page LayoutMemory (golden paths +
    known data kinds), captured internal endpoints (interception registry) + live data kinds,
    and how many decisions have a linked visual frame. No fake tiles — every number is the
    live singleton's own count."""
    try:
        from trading.brain.vision.ocular_cortex import get_cortex
        from trading.broker_sense.interception import get_recorder
        cortex = get_cortex()
        rec = get_recorder()
        from core import llm
        payload = {
            "available": True,
            "vision_online": llm.vision_available(),
            "vision_providers": llm.vision_order(),
            "cortex": cortex.status(),
            "interception": rec.status(),
        }
        # Grounded eyes (invent-beyond #1): local OmniParser icon-grounding layer status —
        # status() never loads the model, so this stays dashboard-thread-cheap.
        try:
            from trading.brain.vision.grounded_eyes import status as _gstatus
            payload["grounded_eyes"] = _gstatus()
        except Exception:
            pass
        # fast_nav (ledger #10): learned-navigation inventory + per-target accuracy —
        # pure JSON reads, dashboard-thread-cheap.
        try:
            from trading.brain.vision import fast_nav
            payload["fast_nav"] = fast_nav.status()
        except Exception:
            pass
        body = json.dumps(payload, default=str).encode()
    except Exception as e:
        body = json.dumps({
            "available": False, "error": f"{type(e).__name__}: {e}",
            "hint": "Ocular Cortex via trading/brain/vision (see "
                    "research/broker-native-trader-spec.md).",
        }).encode()
    return h._send(200, body, "application/json")
