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


_BRAIN_AGENT = None
_EMBODIMENT_CACHE = None    # P4.8 embodiment snapshot (computed once via subprocess, then cached)


def _brain_agent():
    """Lazily build ONE BrainAgent (P4.1) wired to the project's KnowledgeBrain.

    Reuses core.chat_brain's lazily-built, doc-ingested KnowledgeBrain so the agent
    grounds in the SAME memory the existing chat uses. The agent's LLM is the gated
    multi-provider core.llm (live when a key is in .env, else an honest offline
    memory-grounded fallback). Secrets-safe: no keys are read or echoed here.
    """
    global _BRAIN_AGENT
    if _BRAIN_AGENT is None:
        from core.brain_agent import BrainAgent
        from core.chat_brain import _brain
        _BRAIN_AGENT = BrainAgent(_brain())
    return _BRAIN_AGENT


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
    "Symbol", "Trade Type", "Instrument Type", "Currency", "Direction", "Qty", "Capital",
    "Entry Price", "Current Price", "Unrealized P&L", "Unrealized P&L %", "Peak P/L", "Stop",
    "Trail Stop", "R-multiple", "Efficiency", "Strategy", "Exchange", "Leverage",
    "Liq Price", "Hold Time", "Confidence",
]


_CANDLE_CACHE: dict = {}      # (symbol, market, tf) -> (ts, candles) — short TTL to avoid hammering
_FX_CACHE: dict = {}          # "USDINR" -> (ts, rate)

# currency per market: crypto settles in USDT ($), NSE in INR (₹). NEVER add them blindly.
CCY = {"CRYPTO": ("USD", "$"), "NSE": ("INR", "₹")}


def _usdinr() -> float:
    """Live USD→INR rate (open.er-api.com, no key, cached 1h). Fallback 86.0 if offline."""
    import time as _t
    hit = _FX_CACHE.get("USDINR")
    if hit and (_t.time() - hit[0]) < 3600:
        return hit[1]
    rate = 86.0
    try:
        import urllib.request
        r = json.load(urllib.request.urlopen("https://open.er-api.com/v6/latest/USD", timeout=6))
        rate = float(r["rates"]["INR"])
    except Exception:
        pass
    _FX_CACHE["USDINR"] = (_t.time(), rate)
    return rate


def _candles(symbol: str, market: str, tf: str = "5m", limit: int = 200) -> list[dict]:
    """REAL OHLC candles: crypto via ccxt fetch_ohlcv, NSE via OpenAlgo history.

    Returns [{time, open, high, low, close, volume}] (lightweight-charts shape). Cached ~15s.
    """
    import time as _t
    key = (symbol, market.upper(), tf)
    hit = _CANDLE_CACHE.get(key)
    if hit and (_t.time() - hit[0]) < 15:
        return hit[1]
    out: list[dict] = []
    if market.upper() == "CRYPTO":
        from trading.crypto.exchange_client import ExchangeClient
        raw = ExchangeClient("binance")._client().fetch_ohlcv(symbol, timeframe=tf, limit=limit)
        out = [{"time": int(r[0] // 1000), "open": float(r[1]), "high": float(r[2]),
                "low": float(r[3]), "close": float(r[4]), "volume": float(r[5])} for r in raw]
    else:
        import datetime as _dt

        from trading.openalgo_client import OpenAlgoClient
        end = _dt.date.today()
        start = end - _dt.timedelta(days=5)
        df = OpenAlgoClient()._client().history(symbol=symbol, exchange="NSE", interval=tf,
                                                start_date=start.isoformat(), end_date=end.isoformat())
        for ts, row in df.tail(limit).iterrows():
            out.append({"time": int(ts.timestamp()), "open": float(row["open"]),
                        "high": float(row["high"]), "low": float(row["low"]),
                        "close": float(row["close"]), "volume": float(row.get("volume", 0))})
    _CANDLE_CACHE[key] = (_t.time(), out)
    return out


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


_COMPRESSIBLE = ("text/", "javascript", "json", "svg", "xml", "css")


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 keep-alive: reuse the TCP+TLS connection across the 8 poll endpoints
    # instead of a fresh handshake per request (huge over a tunnel). Requires a correct
    # Content-Length on every response (set in _send), which we always send.
    protocol_version = "HTTP/1.1"

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

    def _send(self, code: int, body: bytes, ctype: str, *, cache: str = "no-store") -> None:
        # gzip when the client accepts it and the payload is compressible + worth it.
        # 1.7MB bundle → ~490KB; JSON responses shrink ~70-80% — the single biggest win
        # over a slow tunnel (no language change needed; the backend was never the bottleneck).
        enc = None
        ae = (self.headers.get("Accept-Encoding") or "")
        if "gzip" in ae and len(body) > 512 and any(t in ctype for t in _COMPRESSIBLE):
            try:
                import gzip as _gz
                body = _gz.compress(body, 6)
                enc = "gzip"
            except Exception:
                enc = None
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))   # compressed length — required
        self.send_header("Cache-Control", cache)
        self.end_headers()
        if self.command != "HEAD":
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
        if path == "/api/brain/agent/status":
            # P4.1 LangGraph BrainAgent status: engine, has_memory, active LLM (or null
            # offline), recall_k. Degrades to an error payload (never crashes the server).
            try:
                body = json.dumps(_brain_agent().status(), default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "engine": "langgraph", "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "P4.1 brain agent not importable (see core/brain_agent.py "
                            "and ml-network-brain-ultra-blueprint.md §4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/brain/memory/status":
            # P4.2 human-like memory: importance + Ebbinghaus decay, Letta tiers, and an
            # auto_dream consolidation pass. Returns the OFFLINE deterministic demo snapshot
            # (a real KnowledgeBrain downloads an embedding model = network), labelled demo.
            # Degrades to an error payload (never crashes the server).
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
            return self._send(200, body, "application/json")
        if path == "/api/brain/hybrid/status":
            # P4.2 hybrid memory: fuses REAL reused projects — vendored Stanford
            # Generative-Agents memory stream (Apache-2.0; importance+recency+relevance
            # retrieval + reflection), real Letta tiered core-memory (pip), mem0 semantic
            # store (pip, gated) + our Ebbinghaus decay/auto_dream. Returns the OFFLINE
            # deterministic demo snapshot (real brain/LLM = network), labelled demo.
            # Degrades to an error payload (never crashes the server).
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
            return self._send(200, body, "application/json")
        if path == "/api/brain/librarian/status":
            # P4.3 self-feeding internet: the Librarian discovers (ddgs web / arxiv /
            # feedparser RSS), extracts (trafilatura), dedups (content+URL), and ingests
            # into KnowledgeBrain — on an APScheduler loop in live use. Returns the OFFLINE
            # deterministic demo snapshot (live mode needs network + an embedding model),
            # labelled demo. Degrades to an error payload (never crashes the server).
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
            return self._send(200, body, "application/json")
        if path == "/api/brain/quiz/status":
            # P4.4 self-quiz mastery: the brain quizzes ITSELF (cloze questions from
            # ingested memories → recall → grade) and tracks a FSRS-driven mastery/
            # retention curve — a RISING accuracy+retention curve is the honest "it gets
            # smarter" test (vs a never-learning control). Returns the OFFLINE
            # deterministic demo snapshot (a real KnowledgeBrain downloads an embedding
            # model = network), labelled demo. Degrades to an error payload (never crashes).
            try:
                from run_self_quiz import build_demo_self_quiz
                snap = build_demo_self_quiz()
                snap["demo"] = True
                snap["note"] = ("offline deterministic demo (run_self_quiz.py over a stub "
                                "brain, injected clock); shows the real FSRS-driven mastery "
                                "curve rising for a learning brain vs a flat never-learning "
                                "control — not live brain self-testing")
                body = json.dumps(snap, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "P4.4 self-quiz mastery not importable (see memory/self_quiz.py, "
                            "run_self_quiz.py and ml-network-brain-ultra-blueprint.md §4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/brain/thinking/status":
            # P4.5 thinking + knowing-what-it-knows: the brain REASONS deliberately over its
            # own memory (LangGraph ReAct/ToT), updates pymdp active-inference beliefs (surprise
            # + curiosity), reasons symbolically (pyDatalog traceable transitive logic) and
            # causally (DoWhy + causal-learn), then STAYS CALIBRATED — a conformal selective gate
            # (MAPIE/netcal) makes it ABSTAIN and escalate to the human when it isn't sure — and
            # passes a NeMo-Guardrails constitution. Returns the OFFLINE deterministic demo
            # snapshot, labelled demo. Degrades to an error payload (never crashes the server).
            try:
                from run_thinking_p45 import build_demo_thinking
                snap = build_demo_thinking()
                snap["demo"] = True
                snap["note"] = ("offline deterministic demo (run_thinking_p45.py over a stub "
                                "brain): real ReAct/ToT reasoning + pymdp surprise/curiosity + "
                                "pyDatalog/DoWhy reasoning + conformal abstention + NeMo "
                                "constitution — answers when confident, abstains + escalates "
                                "when not; not live brain reasoning")
                body = json.dumps(snap, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "P4.5 thinking layer not importable (see cognition/, "
                            "run_thinking_p45.py and ml-network-brain-ultra-blueprint.md §4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/brain/stream/status":
            # P4.6 Stream-of-Mind: the brain's live, EPHEMERAL state of mind — each think()
            # cycle becomes a stream of REAL thought-events (goal, ReAct steps, pymdp surprise/
            # curiosity, symbolic insight, calibrated verdict); a Global Workspace competition
            # broadcasts the most salient each tick and CONSOLIDATES winners to long-term memory
            # (visible working→long-term pipeline). Each cycle is a durable Langfuse trace
            # (no-op offline). Returns the OFFLINE deterministic demo snapshot, labelled demo.
            try:
                from run_stream_of_mind import build_demo_thinking
                snap = build_demo_thinking()
                snap["demo"] = True
                snap["note"] = ("offline deterministic demo (run_stream_of_mind.py over a stub "
                                "brain): real Thinker think-cycle → thought stream → Global "
                                "Workspace consolidation to long-term memory; live panel streams "
                                "via AG-UI (POST /api/agui). Langfuse offline no-op unless keys set")
                body = json.dumps(snap, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "P4.6 Stream-of-Mind not importable (see cognition/stream_of_mind.py, "
                            "core/observability.py, run_stream_of_mind.py and the blueprint §2/§4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/brain/autonomy/status":
            # P4.7 Autonomy + self-coding: the brain INVENTS new model-nodes, fits + scores each
            # in a SANDBOX (isolated subprocess · CPU/mem rlimits · wall-clock timeout · no
            # network), and admits only winners that BEAT the incumbent on golden data into its
            # own registry — bounded self-improvement on the safe substrate (P4.4 self-test +
            # P4.5 calibration/guardrails). Returns the OFFLINE deterministic demo snapshot.
            try:
                from run_self_coding_p47 import build_demo_self_coding
                snap = build_demo_self_coding()
                snap["demo"] = True
                snap["note"] = ("offline deterministic demo (run_self_coding_p47.py): real "
                                "propose→sandbox→benchmark-gate→admit loop over golden data; "
                                "shows the rising best-score curve + the safety gate rejecting a "
                                "malicious spec without running it. No network, no LLM")
                body = json.dumps(snap, default=str).encode()
            except Exception as e:
                body = json.dumps({
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "P4.7 self-coding not importable (see cognition/self_coding.py, "
                            "cognition/_sandbox_worker.py, run_self_coding_p47.py and blueprint §4).",
                }).encode()
            return self._send(200, body, "application/json")
        if path == "/api/brain/embodiment/status":
            # P4.8 Multimodal + identity + society + affect: the brain's personality with senses —
            # it SEES (Moondream2→BLIP), HEARS (faster-whisper), SPEAKS (kokoro-onnx), FEELS
            # (GoEmotions→NRCLex mood), holds an INTERNAL DEBATE (specialist roles → vote), and
            # keeps a persistent IDENTITY (Letta persona/human blocks). Computed in a SUBPROCESS so
            # the ~4GB of real models load in a child that exits (the dashboard server stays lean);
            # the JSON result is cached. First call is slow (model loads), then instant.
            try:
                global _EMBODIMENT_CACHE
                if _EMBODIMENT_CACHE is None:
                    import subprocess
                    import sys as _sys
                    proc = subprocess.run([_sys.executable, "run_embodiment_p48.py", "--json"],
                                          capture_output=True, text=True, timeout=300, cwd=os.getcwd())
                    _EMBODIMENT_CACHE = json.loads(proc.stdout.strip().splitlines()[-1])
                snap = dict(_EMBODIMENT_CACHE)
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
            return self._send(200, body, "application/json")
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
            # T6 Dark-Pro ticker tape: LIVE last prices from the running trade loop (real ccxt /
            # OpenAlgo quotes). Falls back to demo constants only if the loop has no ticks yet.
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
                    body = json.dumps({"tickers": _DEMO_TICKERS, "demo": True,
                                       "note": "loop has no live ticks yet (warming up)"},
                                      default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                                   "hint": "live tickers via trading/online/live_loop.py"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/candles":
            # REAL OHLC candles for the price chart: crypto via ccxt, NSE via OpenAlgo history.
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            symbol = (qs.get("symbol", ["BTC/USDT"])[0])
            market = (qs.get("market", ["CRYPTO"])[0])
            tf = (qs.get("tf", ["5m"])[0])
            try:
                candles = _candles(symbol, market, tf=tf)
                body = json.dumps({"symbol": symbol, "market": market, "tf": tf,
                                   "candles": candles, "demo": False, "live": True,
                                   "count": len(candles)}, default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "symbol": symbol, "market": market,
                                   "error": f"{type(e).__name__}: {str(e)[:80]}",
                                   "hint": "live candles via ccxt / OpenAlgo history"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/orderbook":
            # LIVE L2 order book. CRYPTO → ccxt fetch_order_book; NSE → OpenAlgo depth.
            # Degrades to a demo book on any error so the panel never crashes.
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            symbol = (qs.get("symbol") or ["BTC/USDT"])[0]
            market = (qs.get("market") or ["CRYPTO"])[0].upper()
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
                    from trading.crypto.exchange_client import ExchangeClient
                    ob = ExchangeClient("binance")._client().fetch_order_book(symbol, limit=20)
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/opentrades":
            # T6 Open Trades table: LIVE open PAPER positions from the running trade loop
            # (marked at last price). Empty → rows:[] (honest: no open positions right now).
            try:
                from trading.online.live_loop import get_loop
                live = get_loop().open_positions()
                # rows are DICTS keyed by OPEN_TRADE_COLUMNS (the frontend reads row[columnName]).
                rows = []
                nse_pnl = crypto_pnl = nse_cap = crypto_cap = 0.0
                import datetime as _dt
                for p in live:
                    cur, sym = CCY.get(p["market"], ("INR", "₹"))
                    notional = p.get("capital") or (p["entry_price"] * p["quantity"])
                    upnl = p["unrealized_pnl"]
                    pct = round(upnl / notional * 100, 3) if notional else 0.0
                    pp, pl = float(p.get("peak_profit", 0.0)), float(p.get("peak_loss", 0.0))
                    try:
                        held = _dt.datetime.now() - _dt.datetime.fromisoformat(p.get("entry_dt", ""))
                        hold = f"{int(held.total_seconds() // 60)}m"
                    except Exception:
                        hold = "—"
                    if p["market"] == "CRYPTO":
                        crypto_pnl += upnl; crypto_cap += notional
                    else:
                        nse_pnl += upnl; nse_cap += notional
                    rows.append({
                        "Symbol": p["symbol"], "Trade Type": p.get("trade_type", "—"),
                        "Instrument Type": p.get("instrument", "—"), "Currency": cur,
                        "Direction": p["direction"], "Qty": p["quantity"],
                        # money values carry their currency symbol so $ (crypto) ≠ ₹ (NSE)
                        "Capital": f"{sym}{notional:,.2f}",
                        "Entry Price": f"{sym}{p['entry_price']:,.4f}".rstrip("0").rstrip("."),
                        "Current Price": f"{sym}{p['mark_price']:,.4f}".rstrip("0").rstrip("."),
                        "Unrealized P&L": f"{sym}{upnl:,.2f}", "Unrealized P&L %": pct,
                        "Peak P/L": f"{sym}{pp:,.2f}/{sym}{pl:,.2f}",
                        "Stop": "—", "Trail Stop": "—", "R-multiple": "—", "Efficiency": "—",
                        "Strategy": p.get("strategy", "momentum"),
                        "Exchange": "binance" if p["market"] == "CRYPTO" else "NSE",
                        "Leverage": 1.0, "Liq Price": "—", "Hold Time": hold, "Confidence": "—"})
                rate = _usdinr()
                total_inr = nse_pnl + crypto_pnl * rate     # convert $ → ₹ for the grand total
                body = json.dumps({"columns": OPEN_TRADE_COLUMNS, "rows": rows,
                                   "demo": False, "live": True,
                                   "totals": {"nse_pnl": round(nse_pnl, 2),          # ₹
                                              "binance_pnl": round(crypto_pnl, 2),   # $
                                              "total_inr": round(total_inr, 2),      # ₹ (converted)
                                              "nse_capital": round(nse_cap, 2),
                                              "binance_capital": round(crypto_cap, 2),
                                              "usdinr": round(rate, 2), "open": len(rows)},
                                   "note": "live open paper positions — crypto in $ (USDT), NSE in ₹"},
                                  default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}",
                                   "hint": "live open trades via trading/online/live_loop.py"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/closedtrades":
            # T6 Closed Trades journal: LIVE persisted journal (journal.json) — the full
            # 110-column closed trades the trade loop actually saved. Falls back to the demo
            # journal only while the live journal is still empty (so the table isn't blank).
            try:
                from trading.journal.journal import TradeJournal
                from trading.journal.schema import COLUMNS
                from trading.online.live_loop import trade_type as _ttype
                # surface the same friendly columns the open-trades table has, up front
                extra = ["Trade Type", "Currency", "Peak P/L", "Capital", "Net P&L"]
                cols = extra + COLUMNS
                _CRYPTO_EX = ("binance", "bybit", "okx", "kucoin", "coinbase", "kraken")

                def _is_crypto(r):
                    return (r.get("exchange") or "").lower() in _CRYPTO_EX

                def _augment(rws):
                    for r in rws:
                        sym = "$" if _is_crypto(r) else "₹"
                        pp = float(r.get("mfe") or 0.0)         # peak profit (MFE)
                        pl = -float(r.get("mae") or 0.0)        # peak loss (MAE, shown negative)
                        cap = r.get("margin_used") or ((r.get("entry_price") or 0) * (r.get("quantity") or 0))
                        net = float(r.get("net_pnl") or 0.0)
                        r["Trade Type"] = _ttype("CRYPTO" if _is_crypto(r) else "NSE",
                                                 r.get("instrument_type", ""), r.get("product_type", ""),
                                                 r.get("exchange", ""))
                        r["Currency"] = "USD" if _is_crypto(r) else "INR"
                        r["Peak P/L"] = f"{sym}{pp:,.2f}/{sym}{pl:,.2f}"
                        r["Capital"] = f"{sym}{float(cap):,.2f}"
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
                    rate = _usdinr()
                    return {"nse_pnl": round(nse, 2), "binance_pnl": round(binance, 2),
                            "total_inr": round(nse + binance * rate, 2),
                            "usdinr": round(rate, 2), "count": len(rws)}
                live = TradeJournal(state_file="journal.json", persist=True)
                if live._trades:
                    rows = _augment([t.to_dict() for t in live._trades])
                    body = json.dumps({"columns": cols, "rows": rows, "demo": False,
                                       "live": True, "count": len(rows), "totals": _totals(rows),
                                       "note": "live journal.json — real closed paper trades"},
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/confidence":
            # T6 per-symbol Brain confidence book: real Bayesian win-rate + Brier
            # calibration off the LIVE journal (journal.json). Flattened to a list.
            # Falls back to the demo confidence book only while the live journal is empty.
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
                        "note": "live journal.json confidence book — Bayesian win-rate + Brier",
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/context":
            # T6 market-context strip. Crypto Fear & Greed is LIVE (alternative.me, free).
            # India VIX is LIVE when OpenAlgo returns a real ltp, else honest demo. FII/DII
            # stays available:false (no free live source). available:false ⇒ never live.
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
            return self._send(200, body, "application/json")
        if path in ("/api/trading/screener/status", "/api/trading/exits/status",
                    "/api/trading/sizing/status"):
            # P2 screeners · P3 trailing exits · P4 position sizing — offline demo snapshots.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/online/loop":
            # live trade-loop telemetry: ticks, decisions, open/closed counts, last tick, errors
            try:
                from trading.online.live_loop import get_loop
                body = json.dumps(get_loop().status(), default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/online/status":
            # Honest O5 online-control snapshot: the SHARED, persisted control surface
            # (per-market enable/mode/allow_live/trading_state + editable paper wallets)
            # plus each market's live LIVE↔REPLAY session mode. Same source of truth the
            # POST control endpoint + Telegram mutate. Markets default OFF + PAPER (safe).
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
            return self._send(200, body, "application/json")
        if path in ("/architecture", "/architecture.html"):
            with open(os.path.join(STATIC, "architecture.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/knowledge", "/knowledge.html"):
            with open(os.path.join(STATIC, "knowledge.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path in ("/hub", "/hub.html"):
            # all-in-one landing page: every rendered dashboard + live brain/trading
            # status panel as a clickable tile (opens in a new tab). Links are relative
            # so it works identically via the public tunnel, the server IP, or localhost.
            with open(os.path.join(STATIC, "hub.html"), "rb") as f:
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
            # Vite emits content-HASHED asset names → safe to cache forever (immutable):
            # a returning user re-uses the bundle from disk = ZERO tunnel transfer. index.html
            # must revalidate so new deploys are picked up.
            cache = ("public, max-age=31536000, immutable" if "/assets/" in path
                     else "no-cache" if fp.endswith(".html") else "public, max-age=3600")
            with open(fp, "rb") as f:
                return self._send(200, f.read(), ctype, cache=cache)
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
        if path == "/api/brain/agent":
            # P4.1 LangGraph BrainAgent: {message, history?} → recall→respond.
            # Mirrors /api/chat — lazy singleton agent, degrades to an error payload.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                out = _brain_agent().ask(data.get("message", ""),
                                         history=data.get("history"))
            except Exception as e:
                out = {"reply": "", "llm_used": False, "used_memory": False,
                       "recalled": [], "error": f"server error: {type(e).__name__}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
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
            self.send_header("Connection", "close")              # streamed (no Content-Length)
            self.close_connection = True
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
        if path == "/api/agui":
            # P4.6 Stream-of-Mind over the AG-UI protocol (the blueprint's named transport, the
            # exact lib CopilotKit is built on). The React panel's @ag-ui/client HttpAgent POSTs a
            # RunAgentInput here; we run ONE real think cycle and stream its thought-events as
            # AG-UI SSE: RUN_STARTED → per-thought TEXT_MESSAGE_START/CONTENT/END (+ a CUSTOM
            # event carrying kind/salience/consolidated) → RUN_FINISHED. Offline-safe.
            n = int(self.headers.get("Content-Length", 0) or 0)
            try:
                data = json.loads(self.rfile.read(n) or b"{}")
            except Exception:
                data = {}
            try:
                import uuid

                from ag_ui.core import (CustomEvent, EventType, RunFinishedEvent,
                                        RunStartedEvent, TextMessageContentEvent,
                                        TextMessageEndEvent, TextMessageStartEvent)
                from ag_ui.encoder import EventEncoder
            except Exception as e:
                return self._send(503, json.dumps(
                    {"error": f"AG-UI unavailable: {type(e).__name__}: {e}"}).encode(),
                    "application/json")
            enc = EventEncoder()
            self.send_response(200)
            self.send_header("Content-Type", enc.get_content_type())   # text/event-stream
            self.send_header("Cache-Control", "no-cache")
            self.send_header("X-Accel-Buffering", "no")
            self.send_header("Connection", "close")              # SSE stream (no Content-Length)
            self.close_connection = True
            self.end_headers()

            def _emit(ev):
                self.wfile.write(enc.encode(ev).encode())
                self.wfile.flush()

            thread_id = str(data.get("threadId") or uuid.uuid4())
            run_id = str(data.get("runId") or uuid.uuid4())
            # query: last user message from the AG-UI RunAgentInput, if any
            query = ""
            for m in (data.get("messages") or []):
                if m.get("role") == "user" and m.get("content"):
                    query = str(m["content"])
            try:
                _emit(RunStartedEvent(type=EventType.RUN_STARTED, thread_id=thread_id, run_id=run_id))
                from run_stream_of_mind import live_stream
                for ev in live_stream(query):
                    if ev.get("type") == "thought":
                        mid = str(uuid.uuid4())
                        _emit(TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START,
                                                    message_id=mid, role="assistant"))
                        _emit(TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT,
                                                      message_id=mid, delta=ev["text"]))
                        _emit(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=mid))
                        # non-chat signal: salience/kind/consolidated for the panel to style
                        _emit(CustomEvent(type=EventType.CUSTOM, name=ev.get("kind", "thought"),
                                          value={"salience": ev.get("salience"),
                                                 "consolidated": ev.get("consolidated")}))
                _emit(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=thread_id, run_id=run_id))
            except Exception as e:
                try:
                    from ag_ui.core import RunErrorEvent
                    _emit(RunErrorEvent(type=EventType.RUN_ERROR, message=f"{type(e).__name__}"))
                except Exception:
                    pass
            return
        if path == "/api/trading/online/control":
            # O5 control endpoint — the SAME persisted control surface Telegram uses.
            # JSON body {action, market, ...}; action ∈ {start,stop,pause,halt,mode,
            # allow_live,set_balance,top_up,reset_wallet,panic}. Secrets-safe; a
            # mode→REAL switch requires an explicit confirm:true (deliberate 2-step).
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.online import controls
                action = str(data.get("action", "")).lower()
                market = data.get("market", "")
                if action == "start":
                    controls.start(market)
                elif action == "stop":
                    controls.stop(market)
                elif action == "pause":
                    controls.pause(market)
                elif action == "halt":
                    controls.halt(market)
                elif action == "mode":
                    # accept either "mode" or the UI's "value" key (robust to both clients);
                    # surface set_mode's {ok, reason} so a REJECTED real-switch isn't shown green.
                    mode = str(data.get("mode") or data.get("value") or "PAPER").upper()
                    res = controls.set_mode(market, mode, confirm=bool(data.get("confirm", False)))
                    out = {"ok": bool(res.get("ok", True)), "action": action,
                           "reason": res.get("reason"), "status": controls.status()}
                    return self._send(200, json.dumps(out, default=str).encode(), "application/json")
                elif action == "allow_live":
                    allow = data.get("allow_live", data.get("value", False))
                    controls.set_allow_live(market, bool(allow))
                elif action == "segments":           # set the full selected-segment list
                    controls.set_segments(market, data.get("segments") or data.get("value") or [])
                elif action == "toggle_segment":      # flip one trade-type on/off
                    controls.toggle_segment(market, data.get("segment") or data.get("value") or "")
                elif action == "set_balance":
                    controls.set_balance(market, float(data.get("amount", 0.0)),
                                         data.get("portfolio_id", "default"))
                elif action == "top_up":
                    controls.top_up(market, float(data.get("amount", 0.0)),
                                    data.get("portfolio_id", "default"))
                elif action == "reset_wallet":
                    controls.reset_wallet(market, data.get("portfolio_id", "default"))
                elif action == "panic":
                    controls.panic()
                else:
                    out = {"ok": False, "error": f"unknown action {action!r}",
                           "status": controls.status()}
                    return self._send(200, json.dumps(out, default=str).encode(),
                                      "application/json")
                out = {"ok": True, "action": action, "status": controls.status()}
            except Exception as e:
                out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # quiet
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    srv = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    # P-trade: start the always-on LIVE trade loop (real-data PAPER trading + journaling).
    # Ticks the supervisor that controls.start()/Stop drive; PAPER-only (real orders blocked).
    # Start the live trade loop on a short DELAY (after the HTTP server is already serving),
    # off the main thread, so server startup is instant and the loop's first network calls
    # never block/destabilise boot. Gate with NO_LOOP=1 to run the dashboard without trading.
    if os.getenv("NO_LOOP") != "1":
        def _deferred_loop():
            import time as _t
            _t.sleep(3.0)
            try:
                from trading.online.live_loop import start_loop
                start_loop()
            except Exception:
                pass
        import threading as _th
        _th.Thread(target=_deferred_loop, daemon=True).start()
    print(f"Dashboard on http://localhost:{port}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
