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
                closed_light = [map_trade(ft).to_dict() for ft in raw[:120]]
            except Exception:
                closed_light = []
            srv._enrich_predictions(openrows, closed_light)
            pmap = {}
            for r in [*openrows, *closed_light]:
                tid = str(r.get("trade_id", "")).replace("FT-", "")
                if tid:
                    pmap[tid] = {"strategy_label": r.get("strategy_label"),
                                 "brain_pred": r.get("brain_pred"), "nn_pred": r.get("nn_pred")}
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
        body = json.dumps({
            "scorer_backend": snap["scorer_backend"],
            "research": snap["research"],
            "autonomous": snap["autonomous"],
            "node_p_bullish": snap["node_p_bullish"],
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
                "R-multiple": rmult_txt, "Efficiency": eff_txt,
                "Strategy": p.get("strategy", "momentum"),
                "Exchange": "binance" if p["market"] == "CRYPTO" else "NSE",
                "Exit Policy": exit_policy, "Liq Price": liq_txt, "Hold Time": hold,
                "Confidence": conf_txt,
                "Win Prob": win_txt, "NN Verdict": pr.get("verdict", "—"),
                "Exp R": expr_txt, **srv._psych_cells(p.get("psych")),
                **srv._uq_cells(p.get("uq"))})
        # —— UNIFIED TABLE: Freqtrade OPEN trades (engine-owned crypto) ——
        try:
            from trading.crypto.engine_client import CryptoEngineClient
            from trading.crypto.freqtrade_ingest import open_trades_view
            for t in open_trades_view(CryptoEngineClient()):
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
                    "R-multiple": "—", "Efficiency": "—",
                    "Strategy": t.get("enter_tag") or t.get("strategy") or "freqtrade",
                    "Exchange": t.get("exchange", "binance"),
                    "Exit Policy": "freqtrade-managed", "Liq Price": "—",
                    "Hold Time": hold, "Confidence": "—", "Win Prob": "—",
                    "NN Verdict": "—", "Exp R": "—",
                    # entry-time psychology + UQ from the brain-loop sidecar store
                    **srv._psych_cells((_ftm := srv._ft_entry_meta(t)).get("psychology")),
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
                    "R-multiple": "—", "Efficiency": "—",
                    "Strategy": p.get("strategy") or "openalgo",
                    "Exchange": p.get("exchange", "NSE"),
                    "Exit Policy": "openalgo-managed", "Liq Price": "—",
                    "Hold Time": "—", "Confidence": "—", "Win Prob": "—",
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
