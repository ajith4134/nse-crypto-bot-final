"""dashboard/server.py — zero-dependency dashboard server (stdlib http.server).

Serves the animated dashboard and a /api/state endpoint backed by state.json,
so every node/feature written there appears in the browser automatically
(dashboard-sync). No pip installs required.

Run:  python3 dashboard/server.py [port]   (or: make dash)
Open: http://localhost:8000
"""
from __future__ import annotations

import base64
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:                      # so `from core.chat_brain import chat` resolves
    sys.path.insert(0, ROOT)
STATIC = os.path.join(ROOT, "dashboard", "static")
STATE = os.path.join(ROOT, "state.json")

# Basic auth: active only when DASH_PASS is set (so local dev stays frictionless).
AUTH_USER = os.getenv("DASH_USER", "admin")
AUTH_PASS = os.getenv("DASH_PASS")
_EXPECTED = "Basic " + base64.b64encode(f"{AUTH_USER}:{AUTH_PASS}".encode()).decode() \
    if AUTH_PASS else None


_TRADING_SESSION = None


def _trading_session():
    """Lazily build ONE NSESession for the server's lifetime (avoids feed-thread leaks)."""
    global _TRADING_SESSION
    if _TRADING_SESSION is None:
        from trading.session import NSESession
        _TRADING_SESSION = NSESession()
    return _TRADING_SESSION


_CRYPTO_SESSION = None


def _crypto_session():
    """Lazily build ONE CryptoSession for the server's lifetime."""
    global _CRYPTO_SESSION
    if _CRYPTO_SESSION is None:
        from trading.crypto.session import CryptoSession
        _CRYPTO_SESSION = CryptoSession()
    return _CRYPTO_SESSION


_EXECUTION_ENGINE = None


def _execution_engine():
    """Lazily build ONE ExecutionEngine for the server's lifetime.

    There is no live broker/feed wired into the dashboard yet, so this is a labelled
    DEMO engine: it replays the same deterministic, offline sequence as
    run_trading_t3.py (one filled order, one managed long that books partials and
    trails out) so the dashboard surfaces REAL engine.status() state — never faked
    data. When a live trade loop exists it should register/own this same engine.
    """
    global _EXECUTION_ENGINE
    if _EXECUTION_ENGINE is None:
        from trading.execution import (
            ExecutionEngine, ExponentialTrailingStop, Order, ProfitLadder,
            Rung, TradeManager,
        )
        eng = ExecutionEngine(max_daily_loss=10_000.0)
        eng.on_fill(eng.register_order(Order(
            id="O-1", symbol="RELIANCE", exchange="NSE", side="BUY",
            quantity=100.0)).id, qty=100.0, price=100.0)
        mgr = TradeManager(
            symbol="RELIANCE", side="long", quantity=100.0, entry_price=100.0,
            trailing=ExponentialTrailingStop("long", 100.0, base_frac=0.03,
                                             floor_frac=0.004, k=8.0),
            ladder=ProfitLadder(
                side="long", entry_price=100.0, quantity=100.0, initial_stop=95.0,
                rungs=[Rung(target=1.0, fraction=0.50, as_r=True, label="+1R"),
                       Rung(target=2.0, fraction=0.25, as_r=True, label="+2R")]),
            initial_stop=95.0)
        eng.open_trade("RELIANCE", mgr)
        for px in (101.0, 103.0, 106.0, 108.0, 110.5, 113.0, 112.0, 110.0):
            eng.on_bar("RELIANCE", high=px, low=px, close=px)
        _EXECUTION_ENGINE = eng
    return _EXECUTION_ENGINE


_OPTIONS_CHAIN = None


def _options_chain():
    """Lazily build ONE labelled-DEMO OptionsChain for the server's lifetime.

    No live options feed is wired into the dashboard yet, so this replays the same
    deterministic synthetic single-expiry chain as run_options_t4.build_demo_chain().
    Every value chain.status() surfaces (Greeks-derived GEX, max pain, PCR, OI walls)
    is a REAL computed analytic on injected quotes — never faked or decorative.
    """
    global _OPTIONS_CHAIN
    if _OPTIONS_CHAIN is None:
        from run_options_t4 import build_demo_chain
        _OPTIONS_CHAIN = build_demo_chain()
    return _OPTIONS_CHAIN


# ── T6 Dark-Pro UI read-only data helpers ───────────────────────────────────────
# Deterministic, offline, secrets-safe. No network calls anywhere in this section.

# Hardcoded demo ticker tape (NO live feed wired — labelled demo, honest constants).
_DEMO_TICKERS = [
    {"symbol": "NIFTY",     "last": 24187.45, "change":  112.30, "change_pct":  0.47, "market": "NSE"},
    {"symbol": "BANKNIFTY", "last": 51842.10, "change": -238.65, "change_pct": -0.46, "market": "NSE"},
    {"symbol": "BTCUSDT",   "last": 64210.00, "change":  815.50, "change_pct":  1.29, "market": "CRYPTO"},
    {"symbol": "ETHUSDT",   "last":  3142.80, "change":  -27.40, "change_pct": -0.86, "market": "CRYPTO"},
]

# Canonical 22-column Open Trades table (blueprint §4). Single source of truth so the
# frontend hook and this builder agree. Some cells are honestly "—" when the offline
# TradeManager.status() does not carry that field (no live broker/feed wired yet).
OPEN_TRADE_COLUMNS = [
    "Symbol", "Instrument Type", "Direction", "Qty", "Open Qty", "Entry Price",
    "Current Price", "Unrealized P&L", "Unrealized P&L %", "Stop", "Trail Stop",
    "MAE", "MFE", "R-multiple", "Efficiency", "Strategy", "Exchange", "Leverage",
    "Margin", "Liq Price", "Hold Time", "Confidence",
]


def _open_trades_rows() -> list[dict]:
    """Map real ExecutionEngine.status()['positions'] to OPEN_TRADE_COLUMNS rows.

    Only OPEN (not-closed) managers become rows; if none are open returns [] (never
    fabricates a position). Cells absent from TradeManager.status() are honest "—".
    """
    rows: list[dict] = []
    for p in _execution_engine().status().get("positions", []):
        if p.get("closed"):
            continue
        mm = p.get("mae_mfe") or {}
        entry = p.get("entry_price")
        qty = p.get("quantity")
        upnl = mm.get("current_pnl")
        upnl_pct = None
        if upnl is not None and entry and qty:
            upnl_pct = round(upnl / (abs(entry) * abs(qty)) * 100.0, 4)
        rows.append({
            "Symbol": p.get("symbol", "—"),
            "Instrument Type": "—",                 # not carried by TradeManager.status()
            "Direction": (p.get("side") or "").upper() or "—",
            "Qty": qty,
            "Open Qty": p.get("open_qty"),
            "Entry Price": entry,
            "Current Price": entry,                 # entry used as proxy (no live mark)
            "Unrealized P&L": upnl,
            "Unrealized P&L %": upnl_pct,
            "Stop": p.get("stop"),
            "Trail Stop": p.get("stop"),            # trailing stop IS the live stop here
            "MAE": mm.get("mae"),
            "MFE": mm.get("mfe"),
            "R-multiple": mm.get("current_r"),
            "Efficiency": mm.get("efficiency"),
            "Strategy": "—",                        # not carried by TradeManager.status()
            "Exchange": "—",
            "Leverage": "—",
            "Margin": "—",
            "Liq Price": "—",                       # no liquidation engine wired
            "Hold Time": mm.get("ticks"),           # bars processed (proxy for hold time)
            "Confidence": "—",
        })
    return rows


class Handler(BaseHTTPRequestHandler):
    def _authed(self) -> bool:
        if _EXPECTED is None:
            return True
        if self.headers.get("Authorization") == _EXPECTED:
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="ML Network Brain"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._authed():
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(STATIC, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/state":
            if os.path.exists(STATE):
                with open(STATE, "rb") as f:
                    return self._send(200, f.read(), "application/json")
            return self._send(200, json.dumps(
                {"project": "no state yet — run `make phase1`",
                 "nodes": [], "edges": [], "history": []}).encode(),
                "application/json")
        if path == "/api/knowledge":
            kp = os.path.join(ROOT, "knowledge_state.json")
            if os.path.exists(kp):
                with open(kp, "rb") as f:
                    return self._send(200, f.read(), "application/json")
            return self._send(200, b'{"nodes":[],"edges":[],"stats":{}}', "application/json")
        if path == "/api/trading/status":
            # Honest trading status: real OpenAlgo connectivity + toggle/feed/watchlist.
            # Lazy import so the dashboard still serves if the trading deps are absent.
            try:
                body = json.dumps(_trading_session().status()).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T1 not configured — set OPENALGO_API_KEY in .env "
                            "and start the OpenAlgo server (see trading-execution-blueprint.md).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/crypto/status":
            # Honest crypto status: reuses a single CryptoSession. Degrades to an
            # error payload (never crashes the dashboard) if ccxt/config absent.
            try:
                body = json.dumps(_crypto_session().status()).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Crypto T2 not ready — pip install ccxt; optionally set "
                            "CRYPTO_EXCHANGES in .env (see trading-execution-blueprint.md §7 T2).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/execution/status":
            # Honest T3 execution-engine status: real ExecutionEngine.status()
            # (orders/positions/circuit_breaker/kill_switch). Labelled demo until a
            # live trade loop owns the engine — state is computed, never decorative.
            try:
                snap = _execution_engine().status()
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/options/status":
            # Honest T4 options-intelligence snapshot: real OptionsChain.status()
            # (forward/spot, ATM IV, max pain, PCR, GEX+zero-gamma, OI walls) computed
            # off a labelled DEMO synthetic chain. No live options feed wired yet.
            try:
                snap = _options_chain().status()
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/journal/status":
            # Honest T5 trade-journal snapshot: real TradeJournal.status()
            # (n_trades, columns, analytics, per-symbol Brain confidence) computed off
            # a labelled DEMO set of closed trades. No live trade loop wired yet.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/alerts/status":
            # Honest T7 Telegram-alerts snapshot: secrets-safe AlertConfig status
            # (token redacted by as_status — raw token NEVER exposed) PLUS the offline
            # demo dispatcher's status (channels / dedup / dispatch counts).
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/strategy/status":
            # Honest T8.1 strategy-evolution snapshot: a deterministic random strategy
            # population scored on a walk-forward OOS tail of seeded synthetic OHLCV
            # (real genome/operators/backtest output). Metrics dicts only — NO equity
            # curves or full genome trees in the population list (kept JSON-light).
            try:
                from run_strategy_t8 import build_demo_population
                snap = build_demo_population()
                pop = [{"id": p["id"], "market": p["market"], "metrics": p["metrics"],
                        "fitness_score": float(p["fitness_score"]),
                        "guardrail_passed": bool(p["guardrail"]["passed"])}
                       for p in snap["population"]]
                best = snap["best"]
                pbo_v = snap.get("pbo", {}).get("pbo")
                body = json.dumps({
                    "population": pop,
                    "best": ({"id": best["id"], "market": best["market"],
                              "metrics": best["metrics"],
                              "fitness_score": float(best["fitness_score"]),
                              "guardrail_passed": bool(best["guardrail"]["passed"])}
                             if best else None),
                    "n": snap["n"],
                    "guardrails": {"pbo": (float(pbo_v) if pbo_v is not None else None)},
                    "demo": True,
                    "note": ("offline demo population (run_strategy_t8 seeded synthetic "
                             "OHLCV); no live evolution loop wired yet — real walk-forward "
                             "OOS-scored genome metrics + T8.2 multi-objective fitness, "
                             "deflated-Sharpe/min-trades/max-DD guardrail pass-flags, and "
                             "population PBO (CSCV) only"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T8.1 strategy engine not importable "
                            "(see trading/strategy/ and trading-execution-blueprint.md §T8).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/evolution/status":
            # Honest T8.3 DEAP NSGA-II evolution snapshot: a modest population of CRYPTO
            # strategy genomes evolved over a few generations on seeded synthetic OHLCV
            # (real OOS fitness + NSGA-II Pareto selection), guardrail-gated survivors
            # promoted to NodeProtocol StrategyNodes. JSON-able EvolutionResult.as_dict()
            # only (per-gen history, pareto size, promoted-node registry) — no genome trees.
            try:
                from run_strategy_t8 import build_demo_evolution
                snap = build_demo_evolution()
                body = json.dumps({
                    "history": snap["history"],
                    "n_evaluated": snap["n_evaluated"],
                    "pareto_size": snap["pareto_size"],
                    "n_promoted": snap["n_promoted"],
                    "best": snap["best"],
                    "registry": snap["registry"],
                    "demo": True,
                    "note": ("offline demo evolution loop (run_strategy_t8 seeded synthetic "
                             "CRYPTO OHLCV, pop=16/gens=4); real μ+λ NSGA-II over the strategy "
                             "genome with OUT-OF-SAMPLE multi-objective fitness, T8.2 guardrail "
                             "gate, and survivors promoted to routable NodeProtocol "
                             "StrategyNodes — no live market loop wired yet"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T8.3 evolution loop not importable "
                            "(see trading/strategy/evolve.py and trading-execution-blueprint.md §T8).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/experience/status":
            # Honest T8.4 episodic-experience-bank snapshot: a deterministic Case-Based
            # case base built from the T5 demo journal + a synthetic win/lose cluster
            # (numpy-kNN store), a sample CBR recall biasing a new decision by analogous
            # precedents, and the semantic (mem0) text-memory status. JSON-able only.
            try:
                from run_brain_t8 import build_demo_experience
                snap = build_demo_experience()
                body = json.dumps({
                    "experience": snap["experience"],
                    "sample_recall": snap["sample_recall"],
                    "semantic": snap["semantic"],
                    "demo": True,
                    "note": ("offline demo experience bank (run_brain_t8: T5 demo journal "
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/selfeval/status":
            # Honest T8.5 continual-learning + self-eval snapshot: a prequential AutoQuiz
            # accuracy-vs-trade-count curve (test-then-train, proving accuracy rises with
            # experience on a learnable stream), a River OnlineNode's ADWIN concept-drift
            # event count on a concept-flipping stream, a MAML-style MetaLearner warm-vs-cold
            # few-shot adapt result, and a Reflexion self-critique note. JSON-able only.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/patterns/status":
            # Honest T8.6 pattern/regime + asset-picking + entry/exit snapshot on a
            # deterministic synthetic OHLCV (bull/bear/neutral segments + injected anomaly):
            # STUMPY matrix-profile motifs/anomalies + TA-Lib candles, hmmlearn GaussianHMM
            # regime + RegimeGate strategy activation, a LEARNED VENDORED-gplearn symbolic
            # factor ranking a universe, and regime/anomaly-gated entry/exit. JSON-able only.
            try:
                from run_brain_t8 import build_demo_brain_t86
                snap = build_demo_brain_t86()
                body = json.dumps({
                    "patterns": snap["patterns"],
                    "regime": snap["regime"],
                    "picking": snap["picking"],
                    "entryexit": snap["entryexit"],
                    "demo": True,
                    "note": ("offline demo pattern/regime layer (run_brain_t8: T8.6) on a "
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/news/status":
            # Honest T8.7 autonomous-news-research + sentiment snapshot on a FIXED offline
            # NewsItem feed (no RSS/network): vendored-VADER (finance-lexicon boosted) CPU
            # sentiment, per-symbol NewsResearcher aggregation, a NewsSentimentNode
            # compound→p(bullish), and the gated GPT-Researcher autonomous-web-research hook
            # status. JSON-able only.
            try:
                from run_brain_t8 import build_demo_news
                snap = build_demo_news()
                body = json.dumps({
                    "scorer_backend": snap["scorer_backend"],
                    "research": snap["research"],
                    "autonomous": snap["autonomous"],
                    "node_p_bullish": snap["node_p_bullish"],
                    "demo": True,
                    "note": ("offline demo news/sentiment layer (run_brain_t8: T8.7) over a "
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/skills/status":
            # Honest T8.8 skill-library + observability + self-improvement snapshot. A
            # Voyager-pattern quality-gated SkillLibrary (admit/reject/improve), a
            # BrainTracer Stream-of-Mind span feed, a CPU SelfImprover hill-climb over
            # EntryExitPolicy params against a T8.2-style fitness (real, offline), and the
            # gated DSPy/GEPA LLM-program optimiser status. JSON-able only.
            try:
                from run_brain_t8 import build_demo_skills
                snap = build_demo_skills()
                body = json.dumps({
                    "skills": snap["skills"],
                    "skill_events": snap["skill_events"],
                    "best": snap["best"],
                    "stream_of_mind": snap["stream_of_mind"],
                    "tracer": snap["tracer"],
                    "self_improve": snap["self_improve"],
                    "dspy": snap["dspy"],
                    "demo": True,
                    "note": ("offline demo skill-library + self-improvement layer "
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/status":
            # Honest T8.9 FINALE end-to-end brain pipeline + safety review snapshot. A
            # fully-wired BrainTradingPipeline drives a CRYPTO and an NSE symbol off ONE
            # code path: features → regime → pattern/anomaly → news-sentiment →
            # evolved-strategy signal → experience-recall bias → regime/anomaly-gated entry,
            # every step traced (BrainTracer → Stream-of-Mind); the final action is
            # SAFETY-GATED to FLAT on a T3 kill-switch/circuit-breaker. JSON-able only.
            try:
                from run_brain_t8 import build_demo_pipeline
                snap = build_demo_pipeline()
                body = json.dumps({
                    "crypto": snap["crypto"],
                    "nse": snap["nse"],
                    "safety": snap["safety"],
                    "stream_of_mind": snap["stream_of_mind"],
                    "gate_demo": snap["gate_demo"],
                    "strategy_seeds": snap["strategy_seeds"],
                    "demo": True,
                    "note": ("offline demo end-to-end brain pipeline (run_brain_t8: T8.9 "
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/advintel/status":
            # Honest T8-DEFERRED advanced-intelligence snapshot (Group B + Group A engines),
            # all OFFLINE/deterministic via injected stub fetchers + seeded data: PortfolioRisk
            # (Riskfolio/PyPortfolioOpt VaR/CVaR/HRP/Kelly), StressTester scenario/what-if,
            # FII/DII + NSE-announcement scrapers, crypto on-chain SOPR/MVRV + Fear&Greed,
            # liquidation heatmap, cross-exchange arb + funding-farm, a lightweight autonomous
            # web researcher, and a tabular Q-learning RL exit policy. JSON-able only.
            try:
                from run_advintel import build_demo_advintel
                snap = build_demo_advintel()
                body = json.dumps({
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
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T8 advanced-intelligence layer not importable "
                            "(see trading/advintel/, trading/brain/ and "
                            "trading-execution-blueprint.md §T8).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/tickers":
            # T6 Dark-Pro ticker tape: deterministic offline demo constants (no live
            # feed wired) — honest hardcoded values, never a fabricated live quote.
            try:
                body = json.dumps({
                    "tickers": _DEMO_TICKERS,
                    "demo": True,
                    "note": ("offline demo ticker tape (hardcoded constants); no live "
                             "NSE/crypto feed wired yet — values are illustrative only"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T6 tickers builder failed.",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/opentrades":
            # T6 Open Trades table: rows derived from REAL ExecutionEngine.status()
            # positions (run_trading_t3 demo sequence). Empty positions → rows:[].
            try:
                body = json.dumps({
                    "columns": OPEN_TRADE_COLUMNS,
                    "rows": _open_trades_rows(),
                    "demo": True,
                    "note": ("rows from real offline ExecutionEngine.status() positions "
                             "(run_trading_t3 sequence); no live broker wired — some "
                             "cells honestly '—' when not carried by the engine"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T6 open-trades builder failed "
                            "(see trading/execution/ and blueprint §T3/§4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/closedtrades":
            # T6 Closed Trades journal: full 85+ column schema, real to_dict() rows
            # off the labelled DEMO journal (run_journal_t5 synthetic closed trades).
            try:
                from run_journal_t5 import build_demo_journal
                from trading.journal.schema import COLUMNS
                rows = [t.to_dict() for t in build_demo_journal().trades]
                body = json.dumps({
                    "columns": COLUMNS,
                    "rows": rows,
                    "demo": True,
                    "note": ("offline demo journal (run_journal_t5 synthetic trades); no "
                             "live trade loop wired yet — real computed analytics only"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T6 closed-trades not importable "
                            "(see trading/journal/ and blueprint §T5/§5).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/confidence":
            # T6 per-symbol Brain confidence book: real Bayesian win-rate + Brier
            # calibration off the labelled DEMO journal. Flattened to a list.
            try:
                from run_journal_t5 import build_demo_journal
                book = build_demo_journal().confidence.as_dict()
                symbols = [
                    {"symbol": s,
                     "confidence": d.get("confidence"),
                     "win_rate": d.get("win_rate"),
                     "n": d.get("n"),
                     "brier": d.get("brier")}
                    for s, d in book.get("symbols", {}).items()
                ]
                body = json.dumps({
                    "symbols": symbols,
                    "demo": True,
                    "note": ("offline demo confidence book (run_journal_t5 synthetic "
                             "trades); real computed Bayesian win-rate + Brier only"),
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T6 confidence not importable "
                            "(see trading/journal/confidence.py and blueprint §T5).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/context":
            # T6 market-context strip. HONEST: no live NSE/macro feed is wired, so VIX,
            # FII/DII and fear-greed carry available:false. Demo numbers are illustrative
            # only and MUST never be read as live (their available flag says so).
            try:
                body = json.dumps({
                    "india_vix": {
                        "value": 13.85, "available": False,
                        "note": "no live NSE India VIX feed wired — illustrative demo value",
                    },
                    "fii_dii": {
                        "available": False,
                        "fii_net_cr": 1240.5, "dii_net_cr": -310.8,
                        "note": "no live FII/DII provisional feed wired — illustrative demo values",
                    },
                    "fear_greed": {
                        "value": 62, "available": False,
                        "note": "no live crypto Fear & Greed feed wired — illustrative demo value",
                    },
                    "demo": True,
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Trading T6 context builder failed.",
                }).encode()
            return self._send(200, body, "application/json")
        if path in ("/architecture", "/architecture.html"):
            with open(os.path.join(STATIC, "architecture.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/knowledge", "/knowledge.html"):
            with open(os.path.join(STATIC, "knowledge.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        # static passthrough — resolves under STATIC so the built React app's
        # /assets/*.js|css and other bundled files are served (and path-safe).
        safe = os.path.normpath(path).lstrip("/")
        fp = os.path.join(STATIC, safe)
        if os.path.commonpath([STATIC, os.path.abspath(fp)]) == STATIC and os.path.isfile(fp):
            ctype = {".html": "text/html; charset=utf-8", ".svg": "image/svg+xml",
                     ".css": "text/css", ".js": "text/javascript",
                     ".mjs": "text/javascript", ".json": "application/json",
                     ".map": "application/json", ".png": "image/png",
                     ".jpg": "image/jpeg", ".woff2": "font/woff2",
                     ".woff": "font/woff", ".ico": "image/x-icon"}.get(
                         os.path.splitext(fp)[1], "application/octet-stream")
            with open(fp, "rb") as f:
                return self._send(200, f.read(), ctype)
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if not self._authed():
            return
        path = self.path.split("?", 1)[0]
        if path == "/api/chat":
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from core.chat_brain import chat as brain_chat       # lazy: server starts without it
                out = brain_chat(data.get("message", ""), data.get("history"))
            except Exception as e:
                out = {"reply": "", "sources": [], "thoughts": [],
                       "error": f"server error: {type(e).__name__}"}
            return self._send(200, json.dumps(out).encode(), "application/json")
        if path == "/api/chat/stream":
            n = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                data = {}
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")          # disable proxy buffering
            self.end_headers()
            try:
                from core.chat_brain import chat_stream
                for ev in chat_stream(data.get("message", ""), data.get("history")):
                    self.wfile.write((json.dumps(ev) + "\n").encode())
                    self.wfile.flush()                            # push each event immediately
            except Exception as e:
                try:
                    self.wfile.write((json.dumps(
                        {"type": "error", "error": f"server error: {type(e).__name__}"}) + "\n").encode())
                except Exception:
                    pass
            return
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # quiet
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Dashboard on http://localhost:{port}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
