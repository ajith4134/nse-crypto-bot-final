"""Extracted trading HTTP routes (dashboard/server.py split — Wave0-⑤ Group 2).

Same pattern + ``_srv(h)`` accessor as dashboard/routes/brain_ext.py: ``self.X`` → ``h.X`` and any
bare server module-level helper/global (``_trading_session``, ``_crypto_session``, ``_PRACTICE``,
``_bg_snapshot``, ``_cached_body``, ``_CT_CACHE``/``_CT_LOCK``, ``PREDICTION_COLUMNS``…) → ``_srv(h).X``
so a moved body reaches the SAME live singletons/caches/locks the inline code did (server runs as
``__main__``; a plain ``from dashboard.server import …`` would bind a duplicate module copy). Behavior
stays shape-identical — every moved route is diffed against a pre-move baseline.
"""
import json
import sys


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
    """GET /api/trading/options/status — honest T4 options-intelligence snapshot (forward/spot,
    ATM IV, max pain, PCR, GEX+zero-gamma, OI walls) off a labelled DEMO synthetic chain."""
    try:
        snap = _srv(h)._options_chain().status()
        snap["demo"] = True
        snap["note"] = ("offline demo chain (run_options_t4 synthetic chain); "
                        "no live options feed wired yet — real computed analytics only")
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


def handle_evolution_status(h):
    """GET /api/trading/evolution/status — honest T8.3 DEAP NSGA-II evolution snapshot (CRYPTO
    genomes evolved over a few generations on seeded synthetic OHLCV, guardrail-gated survivors
    promoted to StrategyNodes). Genetic evolution is GATED OFF; this is the offline demo."""
    def _p_evolution():
        from run_strategy_t8 import build_demo_evolution
        from trading.strategy.control import evolution_enabled
        snap = build_demo_evolution()
        return {
            "history": snap["history"],
            "n_evaluated": snap["n_evaluated"],
            "pareto_size": snap["pareto_size"],
            "n_promoted": snap["n_promoted"],
            "best": snap["best"],
            "registry": snap["registry"],
            "demo": True,
            "enabled": bool(evolution_enabled()),
            "gate_note": ("Strategy creation/mutation/evolution is GATED OFF for this "
                          "phase (trading.strategy.control). The Strategy Library is the "
                          "active feature (/api/trading/strategy/library). This snapshot "
                          "is the offline demo (force=True) kept for reference."),
            "note": ("offline demo evolution loop (run_strategy_t8 seeded synthetic "
                     "CRYPTO OHLCV, pop=16/gens=4); real μ+λ NSGA-II over the strategy "
                     "genome with OUT-OF-SAMPLE multi-objective fitness, T8.2 guardrail "
                     "gate, and survivors promoted to routable NodeProtocol "
                     "StrategyNodes — no live market loop wired yet"),
        }
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
