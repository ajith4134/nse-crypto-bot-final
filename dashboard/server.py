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
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:                      # so `from core.chat_brain import chat` resolves
    sys.path.insert(0, ROOT)
STATIC = os.path.join(ROOT, "dashboard", "static")
STATE = os.path.join(ROOT, "state.json")
PHASE3 = os.path.join(ROOT, "phase3.json")  # routing/DGMG comparison (Hellsemble L2/L3, DESlib, etc.)
NETWORK_STATE = os.path.join(ROOT, "network_state.json")  # CORTEX B7 unified feed (run_network.py)


# ── CORTEX B7: /api/network/* helpers (pure functions → unit-testable) ─────────
_NETWORK_REFRESH = {"proc": None, "last": 0.0}   # single in-flight run_network.py subprocess
_NETWORK_REFRESH_MIN_S = 60.0


def _network_state_payload(path: str = None, now: float = None) -> dict:
    """network_state.json + state_age_s (mtime), or a friendly note when absent."""
    path = path or NETWORK_STATE
    now = time.time() if now is None else now
    if not os.path.exists(path):
        return {"note": "no network state yet — run `python run_network.py` "
                        "or POST /api/network/refresh", "nodes": [], "edges": []}
    try:
        with open(path, encoding="utf-8") as f:
            state = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"note": f"network_state.json unreadable: {type(e).__name__}",
                "nodes": [], "edges": []}
    state["state_age_s"] = round(max(0.0, now - os.path.getmtime(path)), 1)
    return state


def _network_trust_payload(path: str = None) -> dict:
    """TrustLedger JSON file (MLNB_TRUST_PATH default brain_memory/node_trust.json)."""
    path = path or os.environ.get("MLNB_TRUST_PATH") or os.path.join(
        ROOT, "brain_memory", "node_trust.json")
    if not os.path.exists(path):
        return {"note": "no trust ledger yet — trust accrues as the brain records "
                        "node outcomes (core/trust.py)", "losses": {}, "counts": {}}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return {"note": f"trust ledger unreadable: {type(e).__name__}",
                "losses": {}, "counts": {}}


def _network_refresh_allowed(now: float, last: float, running: bool,
                             min_interval_s: float = _NETWORK_REFRESH_MIN_S
                             ) -> tuple[bool, str]:
    """Throttle rule for POST /api/network/refresh (pure, unit-tested)."""
    if running:
        return False, "refresh already running"
    if now - last < min_interval_s:
        return False, f"throttled — min interval {int(min_interval_s)}s"
    return True, "started"


def _network_refresh_start(now: float = None) -> dict:
    """Kick run_network.py as a niced SUBPROCESS — NEVER train in-process (524)."""
    now = time.time() if now is None else now
    proc = _NETWORK_REFRESH.get("proc")
    running = proc is not None and proc.poll() is None
    ok, note = _network_refresh_allowed(now, _NETWORK_REFRESH.get("last", 0.0), running)
    if not ok:
        return {"started": False, "note": note}
    import subprocess
    kw = {"cwd": ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    try:
        kw["preexec_fn"] = lambda: os.nice(15)
    except Exception:
        pass
    # interactive tier: the ⟳ Refresh button trains a BOUNDED pool (24 pairs,
    # ~15 min) so it stays responsive and can't clobber a deliberate full-run
    # (ML_COLUMNS_FULL all-pairs jobs are launched manually and take hours).
    env = {**os.environ, "ML_NETWORK_PAIRS": os.environ.get("ML_NETWORK_PAIRS_UI", "24")}
    _NETWORK_REFRESH["proc"] = subprocess.Popen(
        [sys.executable, os.path.join(ROOT, "run_network.py")], env=env, **kw)
    _NETWORK_REFRESH["last"] = now
    return {"started": True, "note": note}

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


_GUI_AGENT = None


def _gui_agent():
    """Lazily build ONE ComputerUseAgent (trading/brain/gui) shared across requests.

    Persisted (skills/lessons/targets survive restart) and PAPER-FIRST: default_dry_run=True and
    allow_live=False, so the dashboard can never make it fire a real-money action — arming live is
    a deliberate, separate step. Secrets-safe.
    """
    global _GUI_AGENT
    if _GUI_AGENT is None:
        from trading.brain.gui import ComputerUseAgent
        _GUI_AGENT = ComputerUseAgent(persist=True, allow_live=False, default_dry_run=True)
    return _GUI_AGENT


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
    "Symbol", "Trade Type", "Instrument Type", "Currency", "Direction",
    "Qty", "Lots", "Lot Size",
    "Capital", "Notional", "Leverage", "Fees",
    "Entry Price", "Current Price", "Unrealized P&L", "Unrealized P&L %", "Peak P/L", "Stop",
    "Trail Stop", "R-multiple", "Efficiency", "Strategy", "Exchange", "Exit Policy",
    "Liq Price", "Hold Time", "Confidence",
    # T-wire: the project node network's outcome call on THIS open trade (trade row → NN)
    "Win Prob", "NN Verdict", "Exp R",
    # order-book trader psychology at entry (trading/brain/psychology.py)
    "Psychology", "Psych Label",
    # Pillar 17 — calibrated uncertainty at entry (trading/uq/conformal.py)
    "p_up", "Interval ±", "Self-Unc",
]


def _ft_entry_meta(t: dict) -> dict:
    """Entry-time sidecar meta (psychology + UQ) for a Freqtrade open trade."""
    try:
        from trading.crypto.freqtrade import entry_meta
        seg = "spot" if (t.get("instrument_type") or "").upper() == "SPOT" else "futures"
        return entry_meta.lookup(t.get("symbol", ""), seg,
                                 str(t.get("entry_datetime") or "")) or {}
    except Exception:
        return {}


def _ft_entry_psych(t: dict):
    """Entry-time psychology for a Freqtrade open trade from the brain-loop sidecar store."""
    return _ft_entry_meta(t).get("psychology")


def _uq_cells(uq) -> dict:
    """Pillar-17 columns for a trade row from its entry UQ assessment (— when absent)."""
    if not isinstance(uq, dict) or uq.get("p_up") is None:
        return {"p_up": "—", "Interval ±": "—", "Self-Unc": "—"}
    iv = uq.get("interval") or [None, None]
    iv_txt = (f"[{iv[0]:+.1f}%, {iv[1]:+.1f}%]"
              if iv[0] is not None and iv[1] is not None else "—")
    su = uq.get("self_uncertainty")
    return {"p_up": f"{float(uq['p_up']) * 100:.1f}%", "Interval ±": iv_txt,
            "Self-Unc": f"{float(su):.2f}" if su is not None else "—"}


def _psych_cells(ps) -> dict:
    """Psychology columns for a trade row from its entry psych dict (— when absent)."""
    if not isinstance(ps, dict) or ps.get("trader_psychology") is None:
        return {"Psychology": "—", "Psych Label": "—"}
    return {"Psychology": f"{float(ps['trader_psychology']):+.2f}",
            "Psych Label": ps.get("psych_label") or "—"}


# Give request threads fair GIL slices while the outcome-net trains in the
# background (default 5ms starves the accept loop during pure-python training).
sys.setswitchinterval(0.001)

_NET_LOCK = threading.Lock()
_NET_STATE: dict = {"net": None, "count": -1, "building": False, "built_at": 0.0}
_NET_REBUILD_SEC = 600          # retrain at most every 10 min — journal grows constantly


def _trade_outcome_net():
    """The project node network trained on the LIVE closed-trade journal.
    NON-BLOCKING: requests always get the last built net immediately; when the journal
    count changes, the retrain (minutes over 1000+ trades) runs in ONE background
    thread. Training inside the request thread starved every endpoint (GIL) and made
    the tunnel return 502s across the whole dashboard."""
    try:
        from trading.journal.journal import TradeJournal
        jr = TradeJournal(state_file="journal.json", persist=True)
        closed = [t.to_dict() for t in jr._trades]
    except Exception:
        return _NET_STATE["net"]
    n = len(closed)
    with _NET_LOCK:
        fresh = (time.time() - _NET_STATE["built_at"]) < _NET_REBUILD_SEC
        if n == _NET_STATE["count"] or _NET_STATE["building"] or (fresh and _NET_STATE["net"]):
            return _NET_STATE["net"]
        _NET_STATE["building"] = True

    def _build():
        net = None
        try:
            from trading.brain.trade_features import get_outcome_net
            net = get_outcome_net(closed)          # cached by trade-count inside
        except Exception:
            net = None
        with _NET_LOCK:
            if net is not None:
                _NET_STATE["net"] = net
                _NET_STATE["count"] = n
                _NET_STATE["built_at"] = time.time()
            _NET_STATE["building"] = False

    threading.Thread(target=_build, daemon=True, name="outcome-net-build").start()
    return _NET_STATE["net"]


def _confidence_book() -> dict:
    """Per-symbol Brain confidence (Bayesian win-rate calibration) from the live journal.
    {symbol: confidence_float}. Empty on failure — callers fall back to direction-only."""
    try:
        from trading.journal.journal import TradeJournal
        book = (TradeJournal(state_file="journal.json", persist=True).confidence.as_dict() or {})
        return {s: d.get("confidence") for s, d in (book.get("symbols") or {}).items()}
    except Exception:
        return {}


# Extra per-trade columns surfaced on EVERY crypto-trade surface (dark dashboard, FreqUI Brain tab,
# native FreqUI trade tables): the chosen strategy, the brain's direction+confidence call, and the
# node-network (TradeOutcomeNet) win probability. All REAL — strategy = enter_tag, brain = the live
# Bayesian confidence book, NN = the trained outcome net. No value is fabricated; missing → "—".
PREDICTION_COLUMNS = ["strategy_label", "brain_pred", "nn_pred"]
_PRED_MAP_CACHE = None  # (ts, body) cache for /api/trading/crypto/predictions

# ── Heavy-endpoint memoize (single-flight) ────────────────────────────────────
# ROOT-CAUSE FIX (2026-07-02 audit): the Control Hub polls ~30 tiles continuously.
# Several endpoints recompute torch NN inference / statsmodels OLS on EVERY hit with
# no cache, so concurrent polls stampede under the GIL, pile up handler threads
# (24k+ created, ~355 wedged), saturate the 120-slot request semaphore, and get
# dropped with connection-reset (HTTP 000) → the hub shows real features as "down".
# This collapses concurrent same-key polls to ONE computation; the rest serve cache.
_ENDPOINT_CACHE: dict = {}          # key -> (ts, body_bytes)
_ENDPOINT_LOCKS: dict = {}          # key -> threading.Lock
_ENDPOINT_CACHE_LOCK = threading.Lock()
_SWR_REFRESHING: set = set()        # paths with an in-flight background refresh
_SWR_PORT: int | None = None        # set in main() — loopback target for refreshes


def _swr_refresh_async(path: str) -> None:
    """Stale-while-revalidate: refresh `path` in ONE background daemon thread via a
    loopback request (X-SWR-Refresh header bypasses the cache read and re-stores).
    Callers keep serving the stale body instantly — nobody blocks on a 19s screener."""
    with _ENDPOINT_CACHE_LOCK:
        if path in _SWR_REFRESHING or _SWR_PORT is None:
            return
        _SWR_REFRESHING.add(path)

    def _run():
        try:
            import base64
            import urllib.request
            req = urllib.request.Request(f"http://127.0.0.1:{_SWR_PORT}{path}",
                                         headers={"X-SWR-Refresh": "1"})
            if AUTH_PASS:
                tok = base64.b64encode(f"{AUTH_USER}:{AUTH_PASS}".encode()).decode()
                req.add_header("Authorization", f"Basic {tok}")
            urllib.request.urlopen(req, timeout=120).read()
        except Exception:
            pass                                  # stale body keeps serving; retry next poll
        finally:
            with _ENDPOINT_CACHE_LOCK:
                _SWR_REFRESHING.discard(path)

    threading.Thread(target=_run, daemon=True, name=f"swr:{path}").start()


# Heavy read endpoints measured 3–19s each (2026-07-03 audit: watchlist 19s,
# opentrades 15s, scorecard 14s, psychology 10s, crypto/markets 3s) — they run live
# screeners / engine round-trips per hit and froze every panel. Each gets an explicit
# TTL and is refreshed in the BACKGROUND (stale-while-revalidate below), so requests
# always return in milliseconds once warm.
_HEAVY_TTL = {
    "/api/trading/watchlist": 30.0,
    "/api/trading/opentrades": 10.0,
    "/api/trading/scorecard": 30.0,
    "/api/trading/psychology": 15.0,
    "/api/trading/crypto/markets": 60.0,
    "/api/trading/orderbook": 8.0,
    "/api/trading/foundry": 30.0,
}


def _get_cache_ttl(path: str):
    """TTL (seconds) for a GET path's dispatch-level cache, or None to bypass.
    Covers all read-only '/status' tiles + the heavy brain/prediction endpoints; leaves
    file/state/stream/chat endpoints uncached (cheap or must stay live)."""
    if path.endswith("/status"):
        return 8.0
    if path in _HEAVY_TTL:
        return _HEAVY_TTL[path]
    if path in ("/api/brain/worldmodel", "/api/brain/hypotheses",
                "/api/trading/confidence", "/api/trading/crypto/predictions",
                "/api/trading/brain/predict"):
        return 8.0
    return None


def _cached_body(key: str, ttl: float, producer):
    """Short-TTL single-flight memoize for a heavy read endpoint.
    Returns cached bytes when fresh; otherwise the FIRST caller computes while
    concurrent callers for the same key queue on one lock and then serve the fresh
    result — bounding concurrent heavy compute to one per key (different keys still
    run concurrently). `producer` must return the response body as bytes."""
    hit = _ENDPOINT_CACHE.get(key)
    if hit and (time.time() - hit[0]) < ttl:
        return hit[1]
    with _ENDPOINT_CACHE_LOCK:
        lock = _ENDPOINT_LOCKS.setdefault(key, threading.Lock())
    with lock:
        hit = _ENDPOINT_CACHE.get(key)          # re-check: a prior holder may have refreshed
        if hit and (time.time() - hit[0]) < ttl:
            return hit[1]
        body = producer()
        _ENDPOINT_CACHE[key] = (time.time(), body)
        return body


# ── Background-computed snapshot cache (for endpoints too slow for a request) ──
# Some Brain-Ultra tiles (P4.5 thinking, P4.6 stream, P4.1 agent, P4.7 autonomy) and
# heavy trading builders take >25s on first hit — mostly one-time import/init of heavy
# cognition libs (pymdp/pyDatalog/DoWhy/…) or GP evolution — which blows the 25s socket
# timeout, so the request-level cache never populates. Generalizes the existing
# _EMBODIMENT_CACHE pattern: run the producer in a daemon thread (no socket timeout),
# cache the result, and serve a "warming" placeholder until it's ready (2026-07-02 fix).
_SNAPSHOT_CACHE: dict = {}          # key -> (ts, body_bytes)
_SNAPSHOT_STATE: dict = {}          # key -> {"lock": Lock}
_SNAPSHOT_PENDING: set = set()      # keys requested but not yet warmed
_SNAPSHOT_PRODUCERS: dict = {}      # key -> producer callable (registered on first request)
_SNAPSHOT_LOCK = threading.Lock()
_SNAPSHOT_TTL = 1800.0              # deterministic demo snapshots — refresh at most every 30 min
# Serialize heavy builds: each loads GBs of C-extension state (torch / pymdp / DoWhy /
# DEAP / model weights). Firing all snapshot builds at once spikes memory and crashed the
# process (OOM / concurrent native-init). One build at a time keeps the server alive.
_SNAPSHOT_BUILD_SEM = threading.Semaphore(1)


def _bg_snapshot(key: str, producer, ttl: float = _SNAPSHOT_TTL) -> bytes:
    """Serve a heavy snapshot WITHOUT ever building in the request path. Returns the cached
    bytes when present, else registers the producer for the background warmer
    (_warm_snapshots) and returns an honest 'warming' placeholder. Request handlers stay
    fast and the server can't be destabilised by a polling storm triggering GBs of
    concurrent C-extension init; the warmer computes each tile serially, off-band."""
    hit = _SNAPSHOT_CACHE.get(key)
    if hit:
        return hit[1]
    _SNAPSHOT_PENDING.add(key)
    _SNAPSHOT_PRODUCERS[key] = producer
    return json.dumps({"status": "warming", "warming": True, "demo": True,
                       "note": (f"{key} snapshot is precomputing (heavy cognition/model "
                                "init runs serially in the background); refresh shortly.")
                       }).encode()


def _warm_snapshots():
    """Populate heavy snapshot tiles OUT of the request path, in ONE background thread,
    serially (never concurrently — that spikes memory). Producers register themselves on
    first request; this loop then builds each pending key once and refreshes on TTL. A
    build that raises is cached as an error payload — the server never dies for a tile."""
    import time as _t
    _t.sleep(20)                                    # let the server settle + first polls register
    while True:
        for key in list(_SNAPSHOT_PENDING):
            hit = _SNAPSHOT_CACHE.get(key)
            if hit and (_t.time() - hit[0]) < _SNAPSHOT_TTL:
                continue
            producer = _SNAPSHOT_PRODUCERS.get(key)
            if producer is None:
                continue
            try:
                with _SNAPSHOT_BUILD_SEM:
                    out = producer()
                # Producers may return a dict OR pre-encoded JSON bytes/str — encoding
                # bytes with json.dumps stringified the whole payload ("b'{...}'") and
                # broke the Brain-Ultra/Evolve panels (observed 2026-07-03).
                if isinstance(out, (bytes, bytearray)):
                    body = bytes(out)
                elif isinstance(out, str):
                    body = out.encode()
                else:
                    body = json.dumps(out, default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            _SNAPSHOT_CACHE[key] = (_t.time(), body)
            _t.sleep(2)                             # breathe between heavy builds
        _t.sleep(30)


def _enrich_predictions(*row_lists) -> None:
    """In-place: add strategy_label / brain_pred / nn_pred to each crypto trade row."""
    book = _confidence_book()
    net = _trade_outcome_net()

    def _conf(sym: str):
        d = book.get(sym)
        if d is None:
            d = book.get((sym or "").split(":")[0])          # BTC/USDT:USDT → BTC/USDT fallback
        try:
            return float(d) if d is not None else None
        except (TypeError, ValueError):
            return None

    for rows in row_lists:
        if not rows:
            continue
        try:
            preds = net.predict(rows) if net else []
        except Exception:
            preds = []
        for i, r in enumerate(rows):
            direction = r.get("direction", "") or ""
            r["strategy_label"] = (r.get("enter_tag") or r.get("strategy")
                                   or r.get("strategy_name") or "—")
            conf = _conf(r.get("symbol", ""))
            r["brain_pred"] = f"{direction} {conf:.2f}" if conf is not None else (direction or "—")
            pw = preds[i].get("p_win") if (i < len(preds) and isinstance(preds[i], dict)) else None
            r["nn_pred"] = f"win {round(pw * 100)}%" if pw is not None else "—"


_CANDLE_CACHE: dict = {}      # (symbol, market, tf) -> (ts, candles) — short TTL to avoid hammering
_OB_CACHE: dict = {}          # (symbol, market) -> (ts, payload) — orderbook short cache
_SYSMAP_CACHE: tuple | None = None   # (ts, body) — /api/network/system 20s cache
_PRACTICE: dict = {"proc": None}     # single in-flight practice replay subprocess
_SHARED_CCXT = {}             # one reused ccxt client per (exchange) — avoids per-request load_markets


def _ccxt_spot():
    """One shared, market-loaded ccxt binance client reused across requests (avoids the slow
    per-call construct + load_markets that was wedging the thread pool)."""
    cli = _SHARED_CCXT.get("binance")
    if cli is None:
        import ccxt
        cli = ccxt.binance({"enableRateLimit": True, "timeout": 8000})
        cli.load_markets()
        _SHARED_CCXT["binance"] = cli
    return cli


def _pool_ohlcv(symbol: str, tf: str, limit: int) -> list:
    """Recent OHLCV via the ban-proof multi-venue pool (binance/bybit/okx/kucoin round-robin
    with per-venue budgets + failover) so dashboard reads never pile onto Binance and wedge
    the thread pool when the trading bot has the IP rate-limited. Falls back to the shared
    binance client only if the pool is disabled (MULTI_VENUE_POOL=0) or errors."""
    try:
        from trading.crypto.exchange_pool import get_pool, pool_enabled
        if pool_enabled():
            return get_pool("spot").ohlcv(symbol, timeframe=tf, limit=limit)
    except Exception:
        pass
    return _ccxt_spot().fetch_ohlcv(symbol, timeframe=tf, limit=limit)


def _pool_order_book(symbol: str, limit: int = 20) -> dict:
    """Order book via the multi-venue pool (same rationale as _pool_ohlcv)."""
    try:
        from trading.crypto.exchange_pool import get_pool, pool_enabled
        if pool_enabled():
            return get_pool("spot").order_book(symbol, limit)
    except Exception:
        pass
    return _ccxt_spot().fetch_order_book(symbol, limit=limit)
_FX_CACHE: dict = {}          # "USDINR" -> (ts, rate)
_CT_CACHE: dict = {}          # "/api/trading/crypto/trades" body -> (ts, bytes); NN retrains on
                              # journal growth are minutes-long, so the 8s poll must reuse bodies
# Single-flight: only ONE thread may rebuild an expired heavy cache; concurrent polls get the
# stale snapshot instantly. Without this, every poll that hits an expired cache started its own
# ~20s+ rebuild (OHLCV per open trade + NN predict/retrain) — with 40+ no-limit open trades the
# rebuilds outlasted the poll interval, handler threads avalanched (390+) and the server wedged.
_CT_LOCK = threading.Lock()
_PRED_MAP_LOCK = threading.Lock()

# currency per market: crypto settles in USDT ($), NSE in INR (₹). NEVER add them blindly.
CCY = {"CRYPTO": ("USD", "$"), "NSE": ("INR", "₹")}


def _openalgo_positions() -> list:
    """OpenAlgo positionbook rows (sandbox book when Analyze Mode is ON).
    Unified-tables source: open rows have quantity != 0; flat rows carry realized pnl.
    Best-effort: [] on any failure so the tables never break when OpenAlgo is down."""
    try:
        from trading.openalgo_client import OpenAlgoClient
        res = OpenAlgoClient()._client().positionbook()
        if isinstance(res, dict) and res.get("status") == "success":
            data = res.get("data")
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


def _openalgo_tradebook() -> list:
    """OpenAlgo executed fills (sandbox tradebook when Analyze Mode is ON). [] on failure."""
    try:
        from trading.openalgo_client import OpenAlgoClient
        res = OpenAlgoClient()._client().tradebook()
        if isinstance(res, dict) and res.get("status") == "success":
            data = res.get("data")
            return data if isinstance(data, list) else []
    except Exception:
        pass
    return []


_CRYPTO_EXCHANGES = ("binance", "bybit", "okx", "kucoin", "coinbase", "kraken",
                     "deribit", "predictionpaper")


def _trade_segment(r: dict) -> tuple[str, str]:
    """(market, segment) for a journal/OpenAlgo trade row — the scorecard's grouping key.
    Crypto rows land in the journal without an explicit segment, so derive it from
    exchange + instrument_type + symbol shape; NSE rows likewise from instrument/exchange.
    Prediction is its own market group (operator wants it scored separately)."""
    ex = (r.get("exchange") or "").lower()
    it = (r.get("instrument_type") or "").upper()
    sym = str(r.get("symbol") or "")
    if ex in _CRYPTO_EXCHANGES:
        if ex == "predictionpaper" or it == "PRED" or sym.startswith(("PRED:", "WILL-")):
            return ("PREDICTION", "prediction")
        if ex == "deribit" or it == "OPT" or (sym.count("-") >= 2 and sym[-2:] in ("-C", "-P")):
            return ("CRYPTO", "options")
        if it == "SPOT" or ":" not in sym:
            return ("CRYPTO", "spot")
        return ("CRYPTO", "futures")
    if ex == "mcx" or "COM" in it:
        return ("NSE", "commodities")
    if it in ("CE", "PE") or it.startswith("OPT"):
        return ("NSE", "options")
    if it.startswith("FUT"):
        return ("NSE", "futures")
    if it == "MTF" or (r.get("product_type") or "").upper() == "MTF":
        return ("NSE", "mtf")
    return ("NSE", "intraday")


def _scorecard() -> dict:
    """Per-segment score: realized (closed journal + OpenAlgo round-trips) and current
    (open positions across loop + Freqtrade + OpenAlgo), grouped NSE / CRYPTO / PREDICTION.
    Same sources as the unified open/closed tables so the numbers always reconcile."""
    groups = {
        "NSE": {"currency": "₹", "segments": ["intraday", "mtf", "futures", "options",
                                              "commodities"]},
        "CRYPTO": {"currency": "$", "segments": ["futures", "spot", "options"]},
        "PREDICTION": {"currency": "$", "segments": ["prediction"]},
    }
    cards: dict[tuple, dict] = {}
    for mkt, g in groups.items():
        for seg in g["segments"]:
            cards[(mkt, seg)] = {"market": mkt, "segment": seg, "currency": g["currency"],
                                 "realized": 0.0, "unrealized": 0.0, "total": 0.0,
                                 "open_count": 0, "closed_count": 0}

    def bump(key, field, pnl):
        c = cards.get(key)
        if c is None:      # unexpected segment name — still count it, honestly
            mkt, seg = key
            ccy = groups.get(mkt, {}).get("currency", "$")
            c = cards[key] = {"market": mkt, "segment": seg, "currency": ccy,
                              "realized": 0.0, "unrealized": 0.0, "total": 0.0,
                              "open_count": 0, "closed_count": 0}
        c[field] += float(pnl or 0.0)
        c["open_count" if field == "unrealized" else "closed_count"] += 1

    # realized — the persisted journal is the single closed-trades source (it already
    # ingests Freqtrade closures, so summing Freqtrade again would double count)
    try:
        from trading.journal.journal import TradeJournal
        for t in TradeJournal(state_file="journal.json", persist=True)._trades:
            r = t.to_dict()
            bump(_trade_segment(r), "realized", r.get("net_pnl"))
    except Exception:
        pass
    # realized — OpenAlgo sandbox round-trips (flat rows carry pnl); NSE-side only
    try:
        for p in _openalgo_positions():
            if float(p.get("quantity") or 0.0):
                continue
            bump(_trade_segment({"exchange": p.get("exchange", "NSE"),
                                 "instrument_type": p.get("product", ""),
                                 "symbol": p.get("symbol")}), "realized", p.get("pnl"))
    except Exception:
        pass
    # current — live paper loop open positions (rows carry market + segment natively)
    try:
        from trading.online.live_loop import get_loop
        for p in get_loop().open_positions():
            mkt = "CRYPTO" if p.get("market") == "CRYPTO" else "NSE"
            seg = p.get("segment") or ("futures" if mkt == "CRYPTO" else "intraday")
            if seg == "prediction":
                mkt = "PREDICTION"
            bump((mkt, seg), "unrealized", p.get("unrealized_pnl"))
    except Exception:
        pass
    # current — Freqtrade engine open trades (bot_segment from the multi-segment fork)
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        from trading.crypto.freqtrade_ingest import open_trades_view
        for t in open_trades_view(CryptoEngineClient()):
            seg = t.get("segment") or "futures"
            bump(("PREDICTION" if seg == "prediction" else "CRYPTO", seg),
                 "unrealized", t.get("unrealized_pnl_usdt"))
    except Exception:
        pass
    # current — OpenAlgo open positions (qty != 0)
    try:
        for p in _openalgo_positions():
            qty = float(p.get("quantity") or 0.0)
            if not qty:
                continue
            avg = float(p.get("average_price") or 0.0)
            ltp = float(p.get("ltp") or avg)
            upnl = float(p.get("pnl") if p.get("pnl") is not None else (ltp - avg) * qty)
            bump(_trade_segment({"exchange": p.get("exchange", "NSE"),
                                 "instrument_type": p.get("product", ""),
                                 "symbol": p.get("symbol")}), "unrealized", upnl)
    except Exception:
        pass

    rate = _usdinr()
    out_groups = []
    for mkt, g in groups.items():
        segs = [cards[k] for k in cards if k[0] == mkt]
        segs.sort(key=lambda c: g["segments"].index(c["segment"])
                  if c["segment"] in g["segments"] else 99)
        for c in segs:
            c["realized"] = round(c["realized"], 2)
            c["unrealized"] = round(c["unrealized"], 2)
            c["total"] = round(c["realized"] + c["unrealized"], 2)
        out_groups.append({"market": mkt, "currency": g["currency"], "cards": segs,
                           "realized": round(sum(c["realized"] for c in segs), 2),
                           "unrealized": round(sum(c["unrealized"] for c in segs), 2),
                           "total": round(sum(c["total"] for c in segs), 2)})
    inr_total = 0.0
    for og in out_groups:
        inr_total += og["total"] * (1.0 if og["currency"] == "₹" else rate)
    return {"groups": out_groups, "usdinr": round(rate, 2),
            "grand_total_inr": round(inr_total, 2), "live": True,
            "note": "realized = closed journal + OpenAlgo round-trips; current = open "
                    "positions across loop + Freqtrade + OpenAlgo (same sources as the "
                    "unified tables)"}


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
        raw = _pool_ohlcv(symbol, tf, limit)
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


def _forecast_payload(candles: list, k: int, symbol: str, tf: str) -> dict:
    """CANON-54 predicted-path payload. Fits a numpy ridge auto-regressor on the
    recent close window and rolls it forward k steps via heads.RolloutHead — the
    real CANON-47 rollout engine, but CPU-trivial and in-process-safe. Returns
    the future path (unix-timed to the right of the last candle), an in-sample
    predicted line, the train/test split time, and an honest preview flag."""
    import numpy as np
    from trading.heads import RolloutHead

    closes = np.array([c["close"] for c in candles], float)
    times = [int(c["time"]) for c in candles]
    if len(closes) < 40:
        return {"available": False, "symbol": symbol, "tf": tf,
                "reason": "not enough candles for a forecast (need ≥40)"}
    lb = 16
    step = int(np.median(np.diff(times))) if len(times) > 2 else 900

    # returns-space ridge on a lookback window (chronological, no shuffle)
    rets = np.diff(np.log(closes))
    X, y = [], []
    for i in range(lb, len(rets)):
        X.append(rets[i - lb:i]); y.append(rets[i])
    X, y = np.asarray(X), np.asarray(y)
    lam = 1e-2
    w = np.linalg.solve(X.T @ X + lam * np.eye(lb), X.T @ y)

    class _Ridge:                       # heads.RolloutHead forecaster protocol
        def predict(self, win):
            r = np.diff(np.log(np.asarray(win, float).ravel()))
            r = r[-lb:] if len(r) >= lb else np.pad(r, (lb - len(r), 0))
            return float(win.ravel()[-1] * np.exp(r @ w))

    head = RolloutHead(_Ridge(), name="ridge_ar", direct=False, col=0)
    window = closes[-(lb + 1):].reshape(-1, 1)
    try:
        path = head.rollout(window, k)
    except Exception:                   # fall back to the raw rollout engine
        from trading.rollout import autoregressive_rollout
        path = autoregressive_rollout(_Ridge(), window, k)
    path = np.asarray(path, float).ravel()[:k]

    forecast = [{"time": times[-1] + step * (i + 1), "value": round(float(v), 8)}
                for i, v in enumerate(path)]
    # in-sample predicted line (one-step) over the visible tail, for CANON-55 overlay
    predicted = []
    for i in range(lb, len(closes) - 1):
        r = rets[i - lb:i]
        predicted.append({"time": times[i + 1],
                          "value": round(float(closes[i] * np.exp(r @ w)), 8)})
    split_idx = int(len(closes) * 0.7)
    return {"available": True, "symbol": symbol, "tf": tf, "k": k,
            "forecast": forecast, "predicted": predicted[-60:],
            "train_split_time": times[split_idx],
            "model": "ridge-AR (research preview)", "preview": True}


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
        # Capture the RAW (pre-gzip) body for the dispatch-level cache when do_GET asked
        # for it — re-sends re-compress per client Accept-Encoding.
        if getattr(self, "_capture_want", False):
            self._captured = (code, body, ctype)
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
        # CORS: let the custom FreqUI (served on Freqtrade :8080) call our control endpoints.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        """CORS preflight — let the forked FreqUI POST to our control endpoints cross-origin."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        if not self._authed():
            return
        path = self.path.split("?", 1)[0]
        # Dispatch-level single-flight cache for heavy read endpoints (2026-07-02 audit
        # fix): the Control Hub polls ~30 tiles continuously, and several recompute
        # torch/statsmodels/HMM per hit. Without this, concurrent polls stampede the GIL,
        # pile up handler threads (24k+ created, ~355 wedged), exhaust the 120-slot
        # semaphore and get dropped as HTTP 000 → false "down" dots. Here, concurrent
        # polls for the same path collapse to ONE computation; the rest serve cache.
        ttl = _get_cache_ttl(path)
        if ttl is None:
            return self._do_GET_impl(path)
        is_refresh = bool(self.headers.get("X-SWR-Refresh"))
        hit = _ENDPOINT_CACHE.get(path)
        if hit and not is_refresh:
            # STALE-WHILE-REVALIDATE (2026-07-03): once a body exists it is ALWAYS served
            # instantly; if past TTL, one background thread recomputes it via loopback.
            # Panels went from 3–19s blocking waits to constant-millisecond responses.
            if (time.time() - hit[0]) >= ttl:
                _swr_refresh_async(path)
            c = hit[1]
            return self._send(c[0], c[1], c[2])
        with _ENDPOINT_CACHE_LOCK:
            lock = _ENDPOINT_LOCKS.setdefault(path, threading.Lock())
        with lock:
            hit = _ENDPOINT_CACHE.get(path)                 # re-check after acquiring
            if hit and not is_refresh and (time.time() - hit[0]) < ttl:
                c = hit[1]
                return self._send(c[0], c[1], c[2])
            self._capture_want = True
            try:
                self._do_GET_impl(path)
            finally:
                self._capture_want = False
            cap = getattr(self, "_captured", None)
            if cap is not None:
                _ENDPOINT_CACHE[path] = (time.time(), cap)

    def _do_GET_impl(self, path: str) -> None:
        if path in ("/", "/index.html"):
            with open(os.path.join(STATIC, "index.html"), "rb") as f:
                return self._send(200, f.read(), "text/html; charset=utf-8")
        if path == "/api/state":                              # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_state(self)
        if path == "/api/state/routing":                      # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_state_routing(self)
        if path == "/api/network/state":                      # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_network_state(self)
        if path == "/api/network/trust":                      # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_network_trust(self)
        if path == "/api/trading/practice":                   # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_practice(self)
        if path == "/api/network/system":                     # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_network_system(self)
        if path == "/api/network/antioverfit":                # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_network_antioverfit(self)
        if path == "/api/network/autoload":                   # node auto-loader recovery (idea #1)
            from dashboard.routes import network_ext
            return network_ext.handle_network_autoload(self)
        if path == "/api/knowledge":                          # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_knowledge(self)
        if path == "/api/llm/telemetry":                      # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_llm_telemetry(self)
        if path == "/api/trading/venues":                     # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_venues(self)
        if path == "/api/trading/brain/discovery":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_discovery(self)
        if path == "/api/trading/goal":                       # body → dashboard/routes/brain_ext.py (W1 goal scoreboard)
            from dashboard.routes import brain_ext
            return brain_ext.handle_goal_score(self)
        if path == "/api/trading/surface":                    # body → dashboard/routes/brain_ext.py (W2 rails)
            from dashboard.routes import brain_ext
            return brain_ext.handle_surface(self)
        if path == "/api/trading/evidence":                   # body → dashboard/routes/brain_ext.py (W3 evidence lane)
            from dashboard.routes import brain_ext
            return brain_ext.handle_evidence(self)
        if path == "/api/trading/ui_data":                    # body → dashboard/routes/brain_ext.py (UI-only data coverage)
            from dashboard.routes import brain_ext
            return brain_ext.handle_ui_data(self)
        if path == "/api/trading/scouts":                     # body → dashboard/routes/brain_ext.py (W4 consensus)
            from dashboard.routes import brain_ext
            return brain_ext.handle_scouts(self)
        if path == "/api/trading/track_record":               # body → dashboard/routes/brain_ext.py (W7 report card)
            from dashboard.routes import brain_ext
            return brain_ext.handle_track_record(self)
        if path == "/api/trading/briefing":                   # body → dashboard/routes/brain_ext.py (W8 morning brief)
            from dashboard.routes import brain_ext
            return brain_ext.handle_briefing(self)
        if path == "/api/trading/connectivity":               # body → dashboard/routes/brain_ext.py (#13 feature-usage proof)
            from dashboard.routes import brain_ext
            return brain_ext.handle_connectivity(self)
        if path == "/api/brain/agent/status":                 # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_agent_status(self)
        if path == "/api/brain/memory/status":                # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_memory_status(self)
        if path == "/api/brain/hybrid/status":                # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_hybrid_status(self)
        if path == "/api/brain/librarian/status":             # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_librarian_status(self)
        if path == "/api/brain/quiz/status":                  # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_quiz_status(self)
        if path == "/api/brain/thinking/status":              # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_thinking_status(self)
        if path == "/api/brain/stream/status":                # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_stream_status(self)
        if path == "/api/brain/mind/events":                  # body extracted → dashboard/routes/brain_ext.py (Wave0-⑤)
            from dashboard.routes import brain_ext
            return brain_ext.handle_mind_events(self)
        if path == "/api/brain/ops":                          # body extracted → dashboard/routes/brain_ext.py (Wave0-⑤ seam)
            from dashboard.routes import brain_ext
            return brain_ext.handle_ops(self)
        if path == "/api/brain/boss":                         # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_boss(self)
        if path == "/api/brain/autonomy/status":              # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_autonomy_status(self)
        if path == "/api/brain/embodiment/status":            # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_embodiment_status(self)
        if path == "/api/trading/status":                     # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_status(self)
        if path == "/api/trading/crypto/status":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_crypto_status(self)
        if path == "/api/trading/crypto/trades":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_crypto_trades(self)
        if path == "/api/trading/crypto/predictions":         # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_crypto_predictions(self)
        if path == "/api/trading/crypto/markets":             # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_crypto_markets(self)
        if path == "/api/trading/crypto/ingest":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_crypto_ingest(self)
        if path == "/api/trading/execution/status":           # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_execution_status(self)
        if path == "/api/trading/options/status":             # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_options_status(self)
        if path == "/api/trading/journal/status":             # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_journal_status(self)
        if path == "/api/trading/alerts/status":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_alerts_status(self)
        if path == "/api/trading/strategy/status":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_strategy_status(self)
        if path == "/api/trading/foundry":                    # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_foundry(self)
        if path == "/api/brain/activity":                     # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_activity(self)
        if path == "/api/brain/learning":                     # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_learning(self)
        if path == "/api/trading/credentials":                # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_credentials(self)
        if path == "/api/trading/strategy/library":           # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_strategy_library(self)
        if path == "/api/trading/evolution/status":           # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_evolution_status(self)
        if path == "/api/trading/experience/status":          # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_experience_status(self)
        if path == "/api/trading/selfeval/status":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_selfeval_status(self)
        if path == "/api/trading/patterns/status":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_patterns_status(self)
        if path == "/api/trading/news/status":                # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_news_status(self)
        if path == "/api/trading/skills/status":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_skills_status(self)
        if path == "/api/trading/brain/status":               # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_status(self)
        if path == "/api/trading/advintel/status":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_advintel_status(self)
        if path == "/api/trading/tickers":                    # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_tickers(self)
        if path == "/api/trading/candles":                    # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_candles(self)
        if path == "/api/trading/forecast":                   # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_forecast(self)
        if path == "/api/trading/orderbook":                  # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_orderbook(self)
        if path == "/api/trading/scorecard":                  # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_scorecard(self)
        if path == "/api/trading/opentrades":                 # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_opentrades(self)
        if path == "/api/trading/brain/predict":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_predict(self)
        if path == "/api/brain/worldmodel":                   # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_worldmodel(self)
        if path == "/api/brain/hypotheses":                   # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_hypotheses(self)
        if path == "/api/trading/psychology":                 # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_psychology(self)
        if path == "/api/trading/brain/ultra":                # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_ultra(self)
        if path == "/api/trading/brain/metacognition":        # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_metacognition(self)
        if path == "/api/trading/brain/debate":               # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_debate(self)
        if path == "/api/trading/brain/decisions":            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_brain_decisions(self)
        if path == "/api/trading/gui/status":                 # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_gui_status(self)
        if path.startswith("/api/trading/broker_sense"):      # body → dashboard/routes/trading_ext.py
            from dashboard.routes import trading_ext
            return trading_ext.handle_broker_sense(self)
        if path == "/api/trading/ocular":                     # Ocular Cortex eyes+memory status
            from dashboard.routes import trading_ext
            return trading_ext.handle_ocular(self)
        if path == "/api/trading/broker_sources":             # public-vs-account data switch
            from dashboard.routes import trading_ext
            return trading_ext.handle_broker_sources(self)
        if path == "/api/trading/app_school":                 # learned app-driving routes
            from dashboard.routes import trading_ext
            return trading_ext.handle_app_school(self)
        if path == "/api/trading/memory_search":              # cross-session full-text memory search
            from dashboard.routes import trading_ext
            return trading_ext.handle_memory_search(self)
        if path == "/api/trading/broker_features":            # built-in broker pickers + fusion
            from dashboard.routes import trading_ext
            return trading_ext.handle_broker_features(self)
        if path == "/api/trading/segments":                   # GLOBAL segment-focus (whole brain)
            from dashboard.routes import trading_ext
            return trading_ext.handle_segments(self)
        if path == "/api/trading/trade_columns":              # self-growing discovered columns
            from dashboard.routes import trading_ext
            return trading_ext.handle_trade_columns(self)
        if path == "/api/trading/sandbox":                    # brain's fast paper sandbox
            from dashboard.routes import trading_ext
            return trading_ext.handle_sandbox(self)
        if path == "/api/trading/connectivity":               # self-healing wiring watchdog
            from dashboard.routes import trading_ext
            return trading_ext.handle_connectivity(self)
        if path == "/api/trading/remote_login":               # remote-view login (VNC) status
            from dashboard.routes import trading_ext
            return trading_ext.handle_remote_login(self)
        if path == "/api/trading/live_browser/frame":         # live browser JPEG frame
            from dashboard.routes import trading_ext
            return trading_ext.handle_live_browser_frame(self)
        if path == "/api/trading/live_browser":               # live browser status
            from dashboard.routes import trading_ext
            return trading_ext.handle_live_browser(self)
        if path == "/api/brain/evolve":                       # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_evolve(self)
        if path == "/api/trading/generators":                 # Strategy-Generator Portfolio → brain_ext.py
            from dashboard.routes import brain_ext
            return brain_ext.handle_generators(self)
        if path == "/api/trading/closedtrades":               # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_closedtrades(self)
        if path == "/api/trading/confidence":                 # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_confidence(self)
        if path == "/api/trading/context":                    # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_context(self)
        if path in ("/api/trading/screener/status", "/api/trading/exits/status",
                    "/api/trading/sizing/status"):            # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_pnl_demos(self)
        if path == "/api/trading/watchlist":                  # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_watchlist(self)
        if path == "/api/trading/onchain":                    # on-chain + whale alt-data lane (idea #11)
            from dashboard.routes import trading_ext
            return trading_ext.handle_onchain(self)
        if path == "/api/trading/online/loop":                # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_online_loop(self)
        if path == "/api/trading/online/status":              # body → dashboard/routes/trading_ext.py (Wave0-⑤ G2)
            from dashboard.routes import trading_ext
            return trading_ext.handle_online_status(self)
        if path == "/api/trading/xray":                       # Upstox Stock X-Ray (fused snapshot)
            try:
                from urllib.parse import urlparse, parse_qs
                from trading.broker_sense import stock_xray as _sx
                qs = parse_qs(urlparse(self.path).query)
                sym = (qs.get("symbol") or [""])[0].strip().upper()
                if sym:
                    exch = (qs.get("exchange") or ["NSE"])[0]
                    seg = (qs.get("segment") or ["intraday"])[0]
                    fresh = (qs.get("refresh") or ["0"])[0] in ("1", "true")
                    data = _sx.capture(sym, exch, seg) if fresh else (_sx.get_xray(sym) or _sx.capture(sym, exch, seg))
                else:
                    data = {"recent": _sx.latest(20)}
                return self._send(200, json.dumps(data).encode(), "application/json")
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)[:200]}).encode(), "application/json")
        if path == "/api/trading/account_watchlist":          # Brain-Open Upstox watchlist mirror
            try:
                from trading.broker_sense.account_watchlist import status as _aw_status
                return self._send(200, json.dumps(_aw_status()).encode(), "application/json")
            except Exception as e:
                return self._send(200, json.dumps({"error": str(e)[:200]}).encode(),
                                  "application/json")
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
            cache = ("public, max-age=31536000, immutable"
                     if ("/assets/" in path or "/dash-assets/" in path)
                     else "no-cache" if fp.endswith(".html") else "public, max-age=3600")
            with open(fp, "rb") as f:
                return self._send(200, f.read(), ctype, cache=cache)
        self._send(404, b"not found", "text/plain")

    def do_POST(self) -> None:
        if not self._authed():
            return
        path = self.path.split("?", 1)[0]
        # Any POST can change trading/brain state → mark the read-cache STALE (ts=0),
        # not deleted: the next poll still serves instantly from the old body while a
        # background SWR refresh recomputes it. Deleting instead forced the next reader
        # into a synchronous 10–19s rebuild — every stray POST (chat, GUI-agent, FreqUI
        # overlay) silently re-froze the panels (observed 2026-07-03).
        with _ENDPOINT_CACHE_LOCK:
            for k, v in list(_ENDPOINT_CACHE.items()):
                _ENDPOINT_CACHE[k] = (0.0, v[1])
        if path == "/api/network/refresh":                    # body → dashboard/routes/network_ext.py (Wave0-⑤ G3)
            from dashboard.routes import network_ext
            return network_ext.handle_network_refresh(self)
        if path == "/api/trading/practice/start":             # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_practice_start(self)
        if path == "/api/trading/brain/discovery/run":        # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_brain_discovery_run(self)
        if path == "/api/trading/credentials":                # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_credentials_post(self)
        if path == "/api/brain/learn":                        # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_brain_learn(self)
        if path == "/api/brain/web":                          # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_brain_web(self)
        if path == "/api/chat":                               # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_chat(self)
        if path == "/api/brain/agent":                        # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_brain_agent(self)
        if path == "/api/chat/stream":                        # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_chat_stream(self)
        if path == "/api/agui":                               # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_agui(self)
        if path == "/api/trading/crypto/params":              # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_crypto_params(self)
        if path == "/api/trading/closedtrades/reset":         # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_closedtrades_reset(self)
        if path == "/api/trading/crypto/mode":                # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_crypto_mode(self)
        if path == "/api/trading/online/control":             # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_online_control(self)
        if path == "/api/trading/brain/ultra/remember":       # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_brain_ultra_remember(self)
        if path == "/api/trading/gui/action":                 # body → dashboard/routes/post_ext.py (Wave0-⑤ G4)
            from dashboard.routes import post_ext
            return post_ext.handle_gui_action(self)
        if path == "/api/trading/broker_sense":               # body → dashboard/routes/post_ext.py
            from dashboard.routes import post_ext
            return post_ext.handle_broker_sense_post(self)
        if path == "/api/trading/broker_sources":             # POST flip public/account source
            from dashboard.routes import trading_ext
            return trading_ext.handle_broker_sources(self)
        if path == "/api/trading/app_school":                 # POST start a learning run
            from dashboard.routes import trading_ext
            return trading_ext.handle_app_school(self)
        if path == "/api/trading/broker_features":            # POST read/invent/cross pickers
            from dashboard.routes import trading_ext
            return trading_ext.handle_broker_features(self)
        if path == "/api/trading/segments":                   # POST toggle segment focus (whole brain)
            from dashboard.routes import trading_ext
            return trading_ext.handle_segments(self)
        if path == "/api/trading/sandbox":                    # POST enable/disable/reset sandbox
            from dashboard.routes import trading_ext
            return trading_ext.handle_sandbox(self)
        if path == "/api/trading/trade_columns":              # POST accept/reject discovered column
            from dashboard.routes import trading_ext
            return trading_ext.handle_trade_columns(self)
        if path == "/api/trading/connectivity":               # POST rebaseline wiring watchdog
            from dashboard.routes import trading_ext
            return trading_ext.handle_connectivity(self)
        if path == "/api/trading/remote_login":               # POST start/stop remote-view login
            from dashboard.routes import trading_ext
            return trading_ext.handle_remote_login(self)
        if path == "/api/trading/live_browser":               # POST drive the live browser
            from dashboard.routes import trading_ext
            return trading_ext.handle_live_browser(self)
        self._send(404, b"not found", "text/plain")

    def log_message(self, *a):  # quiet
        pass


class BoundedHTTPServer(ThreadingHTTPServer):
    """ThreadingHTTPServer that CAPS concurrent request threads so slow upstream calls (ccxt /
    OpenAlgo) can't accumulate threads and wedge the server (the recurring thread-leak fix).
    Excess requests QUEUE (bounded) instead of being reset: the old drop-on-full close() made
    Caddy report 'connection reset by peer' → 502, so the UI's once-a-minute polling burst
    (~30 parallel GETs) randomly killed control POSTs (toggle segment / set sizing limits).
    Waiting threads are blocked on a semaphore — no GIL cost — so queuing is cheap; only past
    the hard backlog cap do we shed load, and then with a real 503, never a silent reset."""
    daemon_threads = True
    # 32, not 120: handlers are GIL-bound Python; 120 concurrent heavy handlers each get ~1/120
    # of one core and ALL time out. With the single-flight caches most requests are cheap
    # cache-serves, so 32 concurrent is ample and keeps the box responsive under storm.
    _sem = __import__("threading").Semaphore(32)
    # Hard cap on QUEUED requests beyond the 32 running (thread pile-up backstop).
    _backlog = __import__("threading").Semaphore(224)
    # Accept-queue: the BaseHTTPServer default is 5 — a browser reconnect storm overflows it and
    # new TCP connections are dropped before Python ever sees them (curl → 000 while LISTENing).
    request_queue_size = 128

    @staticmethod
    def _refuse(request):
        try:
            request.sendall(b"HTTP/1.1 503 Service Unavailable\r\nRetry-After: 2\r\n"
                            b"Content-Length: 0\r\nConnection: close\r\n\r\n")
        except Exception:
            pass
        try:
            request.close()
        except Exception:
            pass

    def process_request(self, request, client_address):
        # Never block the accept loop: only the cheap backlog check happens here; the
        # potentially-slow handler-slot wait happens inside the per-request thread.
        if not self._backlog.acquire(blocking=False):
            self._refuse(request)
            return
        super().process_request(request, client_address)

    def process_request_thread(self, request, client_address):
        try:
            # Wait for a handler slot instead of resetting the connection. 20s < the 25s
            # per-request socket timeout and well under the tunnel's upstream timeout.
            if not self._sem.acquire(timeout=20):
                self._refuse(request)
                return
            try:
                super().process_request_thread(request, client_address)
            finally:
                self._sem.release()
        finally:
            self._backlog.release()


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    # Warm heavy imports SYNCHRONOUSLY here (once, single-threaded) BEFORE any warmer thread or
    # request can touch them. The trading.brain package eagerly imports ~20 numpy/statsmodels
    # modules (~10s); importing it from TWO threads at once deadlocks on Python's per-module
    # import locks (import-warmer stuck in pipeline.py while a request imports learner) →
    # /api/brain/learning hung at 000. Doing it up-front populates sys.modules so all later
    # imports are instant no-ops with no lock contention (2026-07-02 fix). ~10s added to boot.
    for _m in ("trading.brain.learner", "trading.brain.credentials",
               "trading.brain.activity_feed", "trading.strategy.foundry"):
        try:
            __import__(_m)
        except Exception:
            pass
    Handler.timeout = 25                       # per-request socket timeout → hung reads release
    srv = BoundedHTTPServer(("0.0.0.0", port), Handler)
    # SWR: loopback port for background refreshes + prewarm the measured-heavy endpoints
    # (staggered, one at a time) so the FIRST page load after boot already hits warm cache.
    global _SWR_PORT
    _SWR_PORT = port

    def _prewarm():
        import time as _t
        _t.sleep(3)                            # let serve_forever start
        for p in (*_HEAVY_TTL, "/api/trading/crypto/status", "/api/trading/strategy/status",
                  "/api/trading/online/status", "/api/trading/execution/status"):
            _swr_refresh_async(p)
            _t.sleep(1.5)                      # stagger: don't stampede the GIL at boot
        # warm the PERSISTENT KnowledgeBrain (loads the embedding model + rehydrates the
        # on-disk collection) so the Brain Learning panel shows the surviving documents
        # right after a restart instead of 0/warming until the first learn.
        try:
            from memory.brain import get_brain
            from trading.brain.learner import get_learner
            get_learner()._brain = get_brain()
        except Exception:
            pass
        try:
            from trading.brain.learn_loop import ensure_started
            ensure_started()               # resume continuous learning across restarts
        except Exception:
            pass
    threading.Thread(target=_prewarm, daemon=True, name="swr-prewarm").start()

    # Write live markets to a JSON file inside Freqtrade's served UI dir so the forked FreqUI
    # pairlist reads it SAME-ORIGIN (no CORS / no dashboard-URL config — bulletproof overlay).
    def _markets_writer():
        import time as _t
        try:
            import freqtrade as _ft
            uidir = os.path.join(os.path.dirname(_ft.__file__), "rpc", "api_server", "ui", "installed")
        except Exception:
            return
        from trading.crypto.markets import live_markets

        def _dash_url():
            # dashboard's own public tunnel URL → FreqUI POSTs control changes back here (CORS
            # fallback; same-origin via the Caddy gateway is the primary path). Truth order:
            # public_link.txt (written by start_all.sh, always the LIVE link) → the live
            # logs/cloudflared.log → legacy root cloudflared.log. The old code read only the
            # stale root log → dead trycloudflare URL → every FreqUI control POST "failed".
            import re
            try:
                with open(os.path.join(ROOT, "public_link.txt")) as f:
                    u = f.read().strip()
                if u.startswith("https://"):
                    return u.rstrip("/")
            except Exception:
                pass
            for lf in ("logs/cloudflared.log", "cloudflared.log"):
                try:
                    with open(os.path.join(ROOT, lf)) as f:
                        urls = re.findall(r"https://[a-z0-9-]+\.trycloudflare\.com", f.read())
                    if urls:
                        return urls[-1]
                except Exception:
                    continue
            return ""
        while True:
            try:
                rows = live_markets(segment="perp", sort="volume", limit=300)
                if rows:
                    with open(os.path.join(uidir, "mlnb_markets.json"), "w") as f:
                        json.dump({"rows": rows}, f)
            except Exception:
                pass
            try:
                from trading.crypto.freqtrade import control as _ctl
                # Selected trade-type segments (Futures/Spot/Options/Prediction buttons in the
                # FreqUI overlay) — same persisted registry the dashboard panel uses.
                try:
                    from trading.online import controls as _oc
                    _cs = _oc.registry().get("CRYPTO")
                    seg = {"selected": list(_cs.segments),
                           "available": list(__import__("trading.online.state", fromlist=["SEGMENTS"]).SEGMENTS.get("CRYPTO", []))}
                except Exception:
                    seg = {}
                # 🤖 AI-Brain unlimited flag for the FreqUI toggle (loop cfg is the truth).
                try:
                    from trading.online.live_loop import get_loop
                    brain_unl = bool(get_loop().cfg.get("brain_unlimited"))
                except Exception:
                    brain_unl = False
                with open(os.path.join(uidir, "mlnb_status.json"), "w") as f:
                    json.dump({"params": _ctl.status(), "dashboard_url": _dash_url(),
                               "segments": seg, "brain_unlimited": brain_unl}, f)
            except Exception:
                pass
            _t.sleep(10)
    import threading as _thmw
    _thmw.Thread(target=_markets_writer, daemon=True).start()

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
    # Warm heavy snapshot tiles (P4.x cognition, world-model, strategy/evolution/advintel)
    # serially in the background so they populate without ever building in the request path.
    threading.Thread(target=_warm_snapshots, daemon=True, name="snapshot-warmer").start()
    print(f"Dashboard on http://localhost:{port}  (Ctrl+C to stop)")
    srv.serve_forever()


if __name__ == "__main__":
    main()
