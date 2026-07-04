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
        if path == "/api/state":
            if os.path.exists(STATE):
                with open(STATE, "rb") as f:
                    return self._send(200, f.read(), "application/json")
            return self._send(200, json.dumps(
                {"project": "no state yet — run `make phase1`",
                 "nodes": [], "edges": [], "history": []}).encode(),
                "application/json")
        if path == "/api/state/routing":
            # The learned-routing / DGMG comparison (Hellsemble circles-of-difficulty + L2/L3 deep
            # routers, DESlib KNORA/META-DES, conformal-gated, Caruana, deep-cascade, dynamic-bus,
            # structure-search) — computed by run_phase3.py into phase3.json but previously unserved.
            if os.path.exists(PHASE3):
                with open(PHASE3, "rb") as f:
                    return self._send(200, f.read(), "application/json")
            return self._send(200, json.dumps(
                {"note": "no routing snapshot — run `python -m run_phase3` (writes phase3.json)",
                 "results": []}).encode(), "application/json")
        if path == "/api/network/state":
            # CORTEX B7 unified feed: network_state.json (run_network.py) + freshness.
            return self._send(200, json.dumps(_network_state_payload()).encode(),
                              "application/json")
        if path == "/api/network/trust":
            # Raw TrustLedger file (real per-node losses/counts — never fabricated).
            return self._send(200, json.dumps(_network_trust_payload()).encode(),
                              "application/json")
        if path == "/api/trading/practice":
            # Practice mode: brain trades HISTORIC data (trading/practice.py).
            try:
                from data.downloads import list_nse_dump_symbols
                from trading.practice import list_runs
                proc = _PRACTICE.get("proc")
                body = json.dumps({
                    "runs": list_runs(),
                    "running": proc is not None and proc.poll() is None,
                    "nse_symbols": list_nse_dump_symbols(),
                }).encode()
            except Exception as e:
                body = json.dumps({"note": f"practice unavailable: {e}",
                                   "runs": [], "nse_symbols": []}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/network/system":
            # Whole-brain system map: every subsystem with working/standby status
            # from real evidence + wired edges (core/system_map.py). 20s cache —
            # the probes/stats are cheap but not free.
            global _SYSMAP_CACHE
            try:
                hit = _SYSMAP_CACHE
                if hit and (time.time() - hit[0]) < 20:
                    return self._send(200, hit[1], "application/json")
                from core.system_map import system_map
                body = json.dumps(system_map()).encode()
                _SYSMAP_CACHE = (time.time(), body)
                return self._send(200, body, "application/json")
            except Exception as e:
                return self._send(200, json.dumps(
                    {"note": f"system map unavailable: {type(e).__name__}: {e}"}).encode(),
                    "application/json")
        if path == "/api/network/antioverfit":
            # CANON-43: anti-overfit telemetry (backtests / free-params / research age).
            try:
                from trading.antioverfit import telemetry as _ao_tel
                payload = _ao_tel()
            except Exception as e:
                payload = {"note": f"antioverfit telemetry unavailable: {type(e).__name__}: {e}"}
            return self._send(200, json.dumps(payload).encode(), "application/json")
        if path == "/api/knowledge":
            kp = os.path.join(ROOT, "knowledge_state.json")
            if os.path.exists(kp):
                with open(kp, "rb") as f:
                    return self._send(200, f.read(), "application/json")
            return self._send(200, b'{"nodes":[],"edges":[],"stats":{}}', "application/json")
        if path == "/api/llm/telemetry":
            # Real per-provider cloud-LLM call stats (hit-rate / free calls used / cooldown),
            # recorded inside core.llm.chat's failover loop. Never fabricated.
            try:
                from core import llm, llm_telemetry
                try:
                    order = llm.configured_order()
                except Exception:
                    order = None
                snap = llm_telemetry.snapshot(order)
            except Exception as e:
                snap = {"providers": [], "totals": {}, "error": str(e)[:120]}
            return self._send(200, json.dumps(snap).encode(), "application/json")
        if path == "/api/trading/venues":
            # Multi-venue market-DATA pool telemetry (ban-proofing): per-venue calls, errors,
            # budget, and ban cooldown across binance/bybit/okx/kucoin — so you can SEE the pool
            # spreading load and backing off banned venues. Read-only; never constructs a pool.
            try:
                from trading.crypto.exchange_pool import all_pools_status
                blob = all_pools_status()
            except Exception as e:
                blob = {"enabled": None, "pools": [], "error": str(e)[:120]}
            return self._send(200, json.dumps(blob).encode(), "application/json")
        if path == "/api/trading/brain/discovery":
            # Concept Discovery Engine: last run's self-invented features + concept manifold.
            # Read-only (returns the persisted result); POST /run triggers a fresh discovery.
            try:
                from trading.brain.discovery import ConceptDiscoveryEngine
                blob = ConceptDiscoveryEngine.load()
            except Exception as e:
                blob = {"features": [], "manifold": {"points": [], "n_clusters": 0},
                        "stats": {}, "error": str(e)[:120]}
            return self._send(200, json.dumps(blob).encode(), "application/json")
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
                snap = _crypto_session().status()
            except Exception as e:
                snap = {
                    "available": False,
                    "error": f"{type(e).__name__}: {e}",
                    "hint": "Crypto T2 not ready — pip install ccxt; optionally set "
                            "CRYPTO_EXCHANGES in .env (see trading-execution-blueprint.md §7 T2).",
                }
            # Additive (T-split B): report the Freqtrade engine state alongside the legacy
            # crypto session, so the migration is honestly visible. Best-effort — never crashes.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/crypto/trades":
            # Phase F+: open + closed Freqtrade trades with full columns (MFE/MAE, USDT P&L,
            # capital placed, leverage). Open via map_open_trade; closed via the 85-col schema.
            # Cached 30s: the outcome-NN retrains whenever the journal count grows, which is
            # minutes over 1000+ trades — without the cache the panel poll times out and the
            # Freqtrade panel renders empty.
            import time as _ct_t
            _hit = _CT_CACHE.get(path)
            if _hit and (_ct_t.time() - _hit[0]) < 30:
                return self._send(200, _hit[1], "application/json")
            # Single-flight: if a stale snapshot exists and another thread is already rebuilding,
            # serve the stale snapshot immediately instead of stacking another rebuild.
            if not _CT_LOCK.acquire(blocking=(_hit is None)):
                return self._send(200, _hit[1], "application/json")
            try:
                # Re-check after acquiring — the previous builder may have just refreshed it.
                _hit = _CT_CACHE.get(path)
                if _hit and (_ct_t.time() - _hit[0]) < 30:
                    return self._send(200, _hit[1], "application/json")
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
                    _enrich_predictions(openrows, closed[:80])
                    for r in closed[80:]:
                        r["strategy_label"] = (r.get("enter_tag") or r.get("strategy")
                                               or r.get("strategy_name") or "—")
                        r["brain_pred"] = r.get("direction") or "—"
                        r["nn_pred"] = "—"
                    # FIXED column schemas (not data-derived) so the dashboard column count is
                    # stable as trades open/close — same contract as the dark dashboard.
                    out = {"open": openrows, "closed": closed,
                           "open_columns": _fi.OPEN_VIEW_COLUMNS + PREDICTION_COLUMNS,
                           "closed_columns": _fi.CLOSED_VIEW_COLUMNS + PREDICTION_COLUMNS,
                           "params": _ctl.status(), "n_open": len(openrows), "n_closed": len(closed)}
                except Exception as e:
                    out = {"open": [], "closed": [], "error": f"{type(e).__name__}: {e}"}
                _body = json.dumps(out, default=str).encode()
                if not out.get("error"):
                    _CT_CACHE[path] = (_ct_t.time(), _body)
            finally:
                _CT_LOCK.release()
            return self._send(200, _body, "application/json")
        if path == "/api/trading/crypto/predictions":
            # LIGHTWEIGHT per-trade Strategy/Brain/NN map keyed by trade_id, for overlaying onto the
            # native FreqUI table cross-origin. Skips closed_view's slow peak-OHLCV enrichment (uses
            # map_trade directly) and caches ~15s so the 8s frontend poll stays cheap (the full
            # /crypto/trades enrichment is ~20s+ and was starving this overlay → columns showed "–").
            import time as _pt
            global _PRED_MAP_CACHE
            hit = _PRED_MAP_CACHE
            if hit and (_pt.time() - hit[0]) < 15:
                return self._send(200, hit[1], "application/json")
            # Single-flight (same avalanche fix as /crypto/trades): stale + rebuild-in-progress
            # → serve stale now; only one thread pays the enrichment cost.
            if not _PRED_MAP_LOCK.acquire(blocking=(hit is None)):
                return self._send(200, hit[1], "application/json")
            try:
                hit = _PRED_MAP_CACHE
                if hit and (_pt.time() - hit[0]) < 15:
                    return self._send(200, hit[1], "application/json")
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
                    _enrich_predictions(openrows, closed_light)
                    pmap = {}
                    for r in [*openrows, *closed_light]:
                        tid = str(r.get("trade_id", "")).replace("FT-", "")
                        if tid:
                            pmap[tid] = {"strategy_label": r.get("strategy_label"),
                                         "brain_pred": r.get("brain_pred"), "nn_pred": r.get("nn_pred")}
                    body = json.dumps({"map": pmap, "n": len(pmap)}, default=str).encode()
                except Exception as e:
                    body = json.dumps({"map": {}, "error": f"{type(e).__name__}: {e}"}).encode()
                _PRED_MAP_CACHE = (_pt.time(), body)
            finally:
                _PRED_MAP_LOCK.release()
            return self._send(200, body, "application/json")
        if path == "/api/trading/crypto/markets":
            # Binance-style live markets/screener feed the brain picks from. Query: segment
            # (perp|spot), sort (volume|movers|gainers|losers|volatility|funding|price), limit, q.
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            g = lambda k, d="": (qs.get(k, [d])[0])
            try:
                from trading.crypto.markets import live_markets
                rows = live_markets(segment=g("segment", "perp"), sort=g("sort", "volume"),
                                    limit=int(g("limit", "80") or 80), search=g("q", ""))
                out = {"rows": rows, "n": len(rows), "segment": g("segment", "perp"), "sort": g("sort", "volume")}
            except Exception as e:
                out = {"rows": [], "error": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
        if path == "/api/trading/crypto/ingest":
            # Phase D: pull Freqtrade CLOSED crypto trades into the journal so the trade→NN
            # bridge keeps learning from crypto. Idempotent (dedup by trade_id). Best-effort.
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
            def _p_strategy():
                # build_demo_population() is a HEAVY, GIL-holding pandas/backtest computation.
                # Run it in a niced SUBPROCESS (its own GIL) so it never starves the dashboard's
                # HTTP handler threads — running it in-process wedged the whole server (all 32
                # handlers GIL-starved → Cloudflare 524, 2026-07-03; py-spy caught it in the
                # snapshot-warmer). It's deterministic, so a subprocess result is identical.
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
                    kw = dict(cwd=ROOT, capture_output=True, text=True, timeout=180)
                    try:
                        kw["preexec_fn"] = lambda: __import__("os").nice(15)
                    except Exception:
                        pass
                    r = _sp.run([_sys.executable, "-c", code], **kw)
                    return json.loads(r.stdout.strip().splitlines()[-1])
                except Exception as e:
                    return {"population": [], "best": None, "n": 0, "demo": True,
                            "error": f"{type(e).__name__}: {str(e)[:120]}"}
            return self._send(200, _bg_snapshot("strategy", _p_strategy), "application/json")
        if path == "/api/trading/foundry":
            # Strategy Foundry: the brain's institutional strategy catalog — discovered/created
            # per segment, each with a UNIQUE ID, tracked by real backtest/live performance, best
            # promoted (trading/strategy/foundry.py). Real data only (state ledger). Cached 8s.
            def _p_foundry():
                try:
                    from trading.strategy.foundry import StrategyFoundry
                    return json.dumps(StrategyFoundry(persist=True).to_json(),
                                      default=str).encode()
                except Exception as e:
                    return json.dumps({"available": False,
                                       "error": f"{type(e).__name__}: {e}",
                                       "hint": "trading/strategy/foundry.py"}).encode()
            return self._send(200, _cached_body("trading/foundry", 8.0, _p_foundry),
                              "application/json")
        if path == "/api/brain/activity":                     # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_activity(self)
        if path == "/api/brain/learning":                     # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1)
            from dashboard.routes import brain_ext
            return brain_ext.handle_learning(self)
        if path == "/api/trading/credentials":
            # Brain credential vault status — pending login requests + stored site NAMES only
            # (never secret values; Fernet-encrypted at rest, gitignored). The chat surfaces
            # pending requests so the operator can answer them. trading/brain/credentials.py.
            try:
                from trading.brain.credentials import get_vault
                body = json.dumps(get_vault().status(), default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/strategy/library":
            # Curated institutional Strategy Library (the ACTIVE T8 feature; evolution is
            # gated OFF). Real OOS backtest leaderboard of the executable strategies on
            # seeded synthetic OHLCV + honest data-gated catalogue. JSON-light: coverage,
            # top-40 leaderboard, and data-gated families grouped by their gating data need.
            # Built via _bg_snapshot: run_library() is HEAVY (some strategies hit ccxt live)
            # and this route is polled hard — building it in the request path let a startup
            # poll-burst stampede build it concurrently, saturating every request thread and
            # wedging the whole server (empty responses → "Unexpected end of JSON input" in
            # the UI). The warmer builds it ONCE serially, off-band; requests stay instant.
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
            return self._send(200, _bg_snapshot("strategy_library", _p_library),
                              "application/json")
        if path == "/api/trading/evolution/status":
            # Honest T8.3 DEAP NSGA-II evolution snapshot: a modest population of CRYPTO
            # strategy genomes evolved over a few generations on seeded synthetic OHLCV
            # (real OOS fitness + NSGA-II Pareto selection), guardrail-gated survivors
            # promoted to NodeProtocol StrategyNodes. JSON-able EvolutionResult.as_dict()
            # only (per-gen history, pareto size, promoted-node registry) — no genome trees.
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
            return self._send(200, _bg_snapshot("evolution", _p_evolution), "application/json")
        if path == "/api/trading/experience/status":
            # Honest T8.4 episodic-experience-bank snapshot: a deterministic Case-Based
            # case base built from the T5 demo journal + a synthetic win/lose cluster
            # (numpy-kNN store), a sample CBR recall biasing a new decision by analogous
            # precedents, and the semantic (mem0) text-memory status. JSON-able only.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/news/status":
            # Honest T8.7 autonomous-news-research + sentiment snapshot on a FIXED offline
            # NewsItem feed (no RSS/network): vendored-VADER (finance-lexicon boosted) CPU
            # sentiment, per-symbol NewsResearcher aggregation, a NewsSentimentNode
            # compound→p(bullish), and the gated GPT-Researcher autonomous-web-research hook
            # status. JSON-able only.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/skills/status":
            # Honest T8.8 skill-library + observability + self-improvement snapshot. A
            # Voyager-pattern quality-gated SkillLibrary (admit/reject/improve), a
            # BrainTracer Stream-of-Mind span feed, a CPU SelfImprover hill-climb over
            # EntryExitPolicy params against a T8.2-style fitness (real, offline), and the
            # gated DSPy/GEPA LLM-program optimiser status. JSON-able only.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/status":
            # Honest T8.9 FINALE end-to-end brain pipeline + safety review snapshot. A
            # fully-wired BrainTradingPipeline drives a CRYPTO and an NSE symbol off ONE
            # code path: features → regime → pattern/anomaly → news-sentiment →
            # evolved-strategy signal → experience-recall bias → regime/anomaly-gated entry,
            # every step traced (BrainTracer → Stream-of-Mind); the final action is
            # SAFETY-GATED to FLAT on a T3 kill-switch/circuit-breaker. JSON-able only.
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/advintel/status":
            # Honest T8-DEFERRED advanced-intelligence snapshot (Group B + Group A engines),
            # all OFFLINE/deterministic via injected stub fetchers + seeded data: PortfolioRisk
            # (Riskfolio/PyPortfolioOpt VaR/CVaR/HRP/Kelly), StressTester scenario/what-if,
            # FII/DII + NSE-announcement scrapers, crypto on-chain SOPR/MVRV + Fear&Greed,
            # liquidation heatmap, cross-exchange arb + funding-farm, a lightweight autonomous
            # web researcher, and a tabular Q-learning RL exit policy. JSON-able only.
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
            return self._send(200, _bg_snapshot("advintel", _p_advintel), "application/json")
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
        if path == "/api/trading/forecast":
            # CANON-54: predicted-path overlay from trading/heads.py. CPU-cheap and
            # in-process-safe (no foundation/torch models — the 524-wedge rule): a
            # numpy ridge forecaster wrapped in heads.RolloutHead does the k-step
            # autoregressive rollout. Honest research-preview output.
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            symbol = (qs.get("symbol", ["BTC/USDT"])[0])
            market = (qs.get("market", ["CRYPTO"])[0])
            tf = (qs.get("tf", ["15m"])[0])
            k = min(24, max(1, int((qs.get("k", ["8"])[0]) or 8)))
            try:
                candles = _candles(symbol, market, tf=tf)
                body = json.dumps(_forecast_payload(candles, k, symbol, tf),
                                  default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False, "symbol": symbol,
                                   "error": f"{type(e).__name__}: {str(e)[:100]}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/orderbook":
            # LIVE L2 order book. CRYPTO → ccxt fetch_order_book; NSE → OpenAlgo depth.
            # Degrades to a demo book on any error so the panel never crashes.
            from urllib.parse import parse_qs, urlparse
            qs = parse_qs(urlparse(self.path).query)
            symbol = (qs.get("symbol") or ["BTC/USDT"])[0]
            market = (qs.get("market") or ["CRYPTO"])[0].upper()
            _obhit = _OB_CACHE.get((symbol, market))
            if _obhit and (time.time() - _obhit[0]) < 2.5:    # collapse rapid polls → no thread pileup
                return self._send(200, _obhit[1], "application/json")
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
                    ob = _pool_order_book(symbol, 20)
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
                _OB_CACHE[(symbol, market)] = (time.time(), body)
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
        if path == "/api/trading/scorecard":
            # Per-segment score card: realized + current P&L for every NSE / crypto /
            # prediction segment, from the SAME sources as the unified open/closed tables.
            try:
                body = json.dumps(_scorecard(), default=str).encode()
            except Exception as e:
                body = json.dumps({"available": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/opentrades":
            # T6 Open Trades table: LIVE open PAPER positions from the running trade loop
            # (marked at last price). Empty → rows:[] (honest: no open positions right now).
            try:
                from trading.online.live_loop import get_loop
                live = get_loop().open_positions()
                # train the project node network on the CLOSED journal, predict each OPEN trade
                net = _trade_outcome_net()
                preds = net.predict(live) if net else []
                # rows are DICTS keyed by OPEN_TRADE_COLUMNS (the frontend reads row[columnName]).
                rows = []
                nse_pnl = crypto_pnl = nse_cap = crypto_cap = 0.0
                import datetime as _dt

                def _money(v):
                    return f"{sym}{float(v):,.4f}".rstrip("0").rstrip(".")
                for i, p in enumerate(live):
                    cur, sym = CCY.get(p["market"], ("INR", "₹"))
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
                        "Exp R": expr_txt, **_psych_cells(p.get("psych")),
                        **_uq_cells(p.get("uq"))})
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
                            **_psych_cells((_ftm := _ft_entry_meta(t)).get("psychology")),
                            **_uq_cells(_ftm.get("uq"))})
                except Exception:
                    pass
                # —— UNIFIED TABLE: OpenAlgo sandbox (NSE paper) open positions ——
                try:
                    for p in _openalgo_positions():
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
                rate = _usdinr()
                total_inr = nse_pnl + crypto_pnl * rate     # convert $ → ₹ for the grand total
                body = json.dumps({"columns": OPEN_TRADE_COLUMNS, "rows": rows,
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/predict":
            # The trade-row → NEURAL-NETWORK bridge (operator's first ask): the project
            # node network (GatedMoENode over real sklearn experts) is TRAINED on the
            # closed-trade journal and run on every OPEN trade. We also replay the last
            # few CLOSED trades through it (predicted vs actual) so the panel shows the
            # network's output even with zero open positions. Honest: untrained until the
            # journal has ≥12 closed trades with both outcomes.
            # Memoized (single-flight, 8s): torch NN inference on every hit otherwise
            # stampeded the GIL under continuous hub polling (2026-07-02 audit fix).
            def _produce_brain_predict():
                try:
                    from trading.online.live_loop import get_loop
                    net = _trade_outcome_net()
                    if net is None:
                        raise RuntimeError("trading stack not importable")
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
            body = _cached_body("brain/predict", 8.0, _produce_brain_predict)
            return self._send(200, body, "application/json")
        if path == "/api/brain/worldmodel":                   # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_worldmodel(self)
        if path == "/api/brain/hypotheses":                   # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_hypotheses(self)
        if path == "/api/trading/psychology":
            # Trader Psychology (order-book depth): LIVE crowd metrics per symbol — OBI, OFI,
            # Stoikov microprice drift, depth-slope, whale walls, spread/λ/VPIN fear and the
            # composite score/label (trading/brain/psychology.py, stitched from vendored
            # lob-regime-scanner + microprice + crypto-whale-watching + lob-deep-learning).
            # ?market=CRYPTO|NSE&symbol=X&segment=Y evaluates ONE symbol on demand; default =
            # every currently OPEN position (loop + Freqtrade) — real books only, no demo rows.
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.brain.psychology import get_engine
                qs = parse_qs(urlparse(self.path).query)
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/ultra":
            # Brain ultra-upgrade (Phases A–E, 2026-07-02): REAL statuses of the new stack —
            # associative memory (HippoRAG PPR + A-MEM evolution over the knowledge graph),
            # Claude-style file memory (brain_memory/), the cloned micro-LLM (nanoGPT node +
            # llama2.c C kernel), Docling/Surya perception, Avalanche continual learning and
            # the gpt-researcher deep-research engine. ?q=... also runs a LIVE associative
            # recall so the panel shows actual multi-hop hits, never canned JSON.
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.brain import ultra
                qs = parse_qs(urlparse(self.path).query)

                def _p_ultra():
                    st = ultra.status()
                    return json.dumps({**st, "available": True}, default=str).encode()
                q = (qs.get("q", [""])[0] or "").strip()
                if q:
                    body = json.dumps({"query": q, "hits": ultra.recall(q, k=6),
                                       "available": True}, default=str).encode()
                else:
                    # _bg_snapshot, NOT _cached_body: ultra.status() first-run does LLM
                    # calls + file-memory init IN the request thread — 6+ pollers stuck
                    # there was half of the post-restart 503 wedge (2026-07-03).
                    body = _bg_snapshot("brain/ultra", _p_ultra, ttl=300.0)
            except Exception as e:
                body = json.dumps({"available": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/metacognition":
            # Pillar 17 (trading/uq/conformal.py): REAL calibration state of the conformal
            # UQ engine — crepes CPS coverage (static vs ACI-adapted), ECE, adaptive width
            # cap, the reliability diagram bins (predicted p_up vs realized win-rate on the
            # chronological holdout) and the first-class abstention log. ?recalibrate=1
            # forces a refit (otherwise the learn-loop refits every 6h).
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.uq import get_uq
                uq = get_uq()
                qs = parse_qs(urlparse(self.path).query)
                if (qs.get("recalibrate", ["0"])[0] or "0") in ("1", "true"):
                    uq.recalibrate()

                def _p_meta():
                    st = uq.status()
                    return json.dumps({"available": True, "status": st,
                                       "reliability": st.get("reliability", []),
                                       "abstentions": uq.abstentions(40)},
                                      default=str).encode()
                # background snapshot: the first fit reads the full journal + trains —
                # never in the request thread (same wedge as brain/ultra)
                body = _bg_snapshot("brain/metacognition", _p_meta, ttl=120.0)
            except Exception as e:
                body = json.dumps({"available": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/debate":
            # Pillar 18 (trading/brain/debate_gate.py): adversarial bull/bear/risk debate +
            # process-reward step verifier over a candidate trade. ?symbol=&direction=&p_up=&
            # sharpe=&regime=&psychology= runs a live deliberation; returns the auditable
            # decision_snapshot (votes, arguments, per-step verifier scores) + gate decision.
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.brain.debate_gate import get_debate_gate
                qs = parse_qs(urlparse(self.path).query)

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
                # deliberation calls the LLM failover → run off the request thread
                body = _bg_snapshot(f"brain/debate/{symbol}/{direction}", _p_debate, ttl=45.0)
            except Exception as e:
                body = json.dumps({"available": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/brain/decisions":
            # Decision memory (trading/brain/decision_memory.py — FinMem layers +
            # TradingAgents outcome-closure + SHAP attribution): REAL episodes only.
            # ?symbol=X&q=... runs a live recall; default returns stats + newest episodes.
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.brain.decision_memory import get_memory
                dm = get_memory()
                qs = parse_qs(urlparse(self.path).query)
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
            return self._send(200, body, "application/json")
        if path == "/api/trading/gui/status":
            # Computer-use / GUI agent (trading/brain/gui): the brain SEEING dashboards (own +
            # Freqtrade/FreqUI), pressing their buttons, experimenting, reflecting (Reflexion)
            # and growing a Voyager-style skill library. Honest capability flags: api+html read
            # works today (stdlib); DOM-click (playwright) + chart-pixel OCR (paddleocr) are
            # activate-on-install upgrade layers. observe=1 in the query also reads our own
            # dashboard live so the panel shows what the agent currently sees.
            try:
                from urllib.parse import parse_qs, urlparse
                from trading.brain.gui import register_computer_use_agent
                agent = _gui_agent()
                qs = parse_qs(urlparse(self.path).query)
                if qs.get("observe", ["0"])[0] == "1":
                    agent.observe("own_dashboard")        # live read (reachable + controls + chart)
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
            return self._send(200, body, "application/json")
        if path == "/api/brain/evolve":                       # body → dashboard/routes/brain_ext.py (Wave0-⑤ G1b)
            from dashboard.routes import brain_ext
            return brain_ext.handle_evolve(self)
        if path == "/api/trading/closedtrades":
            # T6 Closed Trades journal: LIVE persisted journal (journal.json) — the full
            # 110-column closed trades the trade loop actually saved. Falls back to the demo
            # journal only while the live journal is still empty (so the table isn't blank).
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
                    rate = _usdinr()
                    return {"nse_pnl": round(nse, 2), "binance_pnl": round(binance, 2),
                            "total_inr": round(nse + binance * rate, 2),
                            "usdinr": round(rate, 2), "count": len(rws)}
                def _openalgo_closed_rows():
                    # UNIFIED TABLE: OpenAlgo sandbox round-trips — flat (qty=0) positions
                    # carry the realized P&L; fills come from the sandbox tradebook.
                    out = []
                    try:
                        fills = {}
                        for t in _openalgo_tradebook():
                            fills.setdefault(t.get("symbol"), []).append(t)
                        for p in _openalgo_positions():
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
        if path == "/api/trading/watchlist":
            # live per-market watchlist (symbol+segment the loop trades) + fresh screener
            # candidates for the SELECTED segments of each market.
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
        if path == "/api/network/refresh":
            # CORTEX B7: rebuild network_state.json via a niced run_network.py
            # SUBPROCESS (throttled; never trains in the dashboard process — 524).
            return self._send(200, json.dumps(_network_refresh_start()).encode(),
                              "application/json")
        if path == "/api/trading/practice/start":
            # Start a practice replay (brain trades historic data) as a niced
            # SUBPROCESS — one in-flight run at a time, honest busy answer.
            try:
                body_in = json.loads(self.rfile.read(
                    int(self.headers.get("Content-Length", 0)) or 0) or b"{}")
            except Exception:
                body_in = {}
            proc = _PRACTICE.get("proc")
            if proc is not None and proc.poll() is None:
                return self._send(200, json.dumps(
                    {"started": False, "note": "a practice run is already in flight"}).encode(),
                    "application/json")
            sym = str(body_in.get("symbol") or "RELIANCE").upper()
            interval = str(body_in.get("interval") or "15m")
            bars = min(5000, max(300, int(body_in.get("bars") or 1200)))
            explore = bool(body_in.get("explore", True))
            code = (
                "from data.downloads import download_nse_history;"
                "from trading.practice import replay;"
                f"df = download_nse_history({sym!r}, {interval!r});"
                f"r = replay(df.tail({bars}).reset_index(drop=True), 'NSE:'+{sym!r},"
                f" warmup_frac=0.6, explore={explore});"
                "print(r['run_id'], r['n_trades'])")
            import subprocess
            kw = {"cwd": ROOT, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
            try:
                kw["preexec_fn"] = lambda: os.nice(15)
            except Exception:
                pass
            _PRACTICE["proc"] = subprocess.Popen([sys.executable, "-c", code], **kw)
            return self._send(200, json.dumps(
                {"started": True, "symbol": sym, "interval": interval, "bars": bars,
                 "explore": explore,
                 "note": "practice run started — results appear in the runs list"}).encode(),
                "application/json")
        if path == "/api/trading/brain/discovery/run":
            # Trigger a fresh concept-discovery run on REAL recent market data (public Binance
            # klines). Body {symbol?, interval?, use_llm?}. Returns the discovered features +
            # manifold and persists them for the panel. Never fabricates — needs real candles.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                symbol = str(data.get("symbol", "BTCUSDT")).upper().replace("/", "")
                interval = str(data.get("interval", "1h"))
                use_llm = bool(data.get("use_llm", False))
                from data.binance import fetch_klines, load_klines
                fetch_klines(symbol=symbol, interval=interval, total=800)
                rows = load_klines(symbol=symbol, interval=interval)   # (date, close, volume)
                import numpy as np
                if len(rows) < 60:
                    raise ValueError("not enough candles")
                rows = rows[-400:]                                     # bound work for latency
                closes = np.array([float(r[1]) for r in rows], float)
                cv = np.array([[float(r[1]), float(r[2])] for r in rows], float)

                def _run_discovery():
                    try:
                        from trading.brain.discovery import ConceptDiscoveryEngine
                        eng = ConceptDiscoveryEngine(use_llm=use_llm)
                        res = eng.discover(series=closes, ohlcv=cv)
                        res["symbol"] = symbol
                        res["interval"] = interval
                        eng.save()
                    except Exception:
                        pass

                # discovery (encoder+SAE+UMAP) is too heavy for a sync HTTP request — run it in
                # the background and let the panel's GET poll pick up the saved result.
                threading.Thread(target=_run_discovery, daemon=True).start()
                return self._send(200, json.dumps(
                    {"ok": True, "started": True, "symbol": symbol,
                     "note": "discovery running — results appear in a few seconds"}).encode(),
                    "application/json")
            except Exception as e:
                return self._send(200, json.dumps({"ok": False, "error": str(e)[:160]}).encode(),
                                  "application/json")
        if path == "/api/trading/credentials":
            # Credential vault control. Body {op, site, ...}: op=submit {site, values{}} stores
            # (encrypted) the operator's answer to a brain login request; op=request {site,
            # fields[]} raises a pending request; op=forget {site} deletes. Secret values are
            # accepted here but NEVER echoed back (receipt = field names only) or logged.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.brain.credentials import get_vault
                v = get_vault(); op = str(data.get("op", "")).lower()
                if op == "submit":
                    out = v.submit(str(data.get("site", "")), data.get("values") or {})
                elif op == "request":
                    out = v.request_login(str(data.get("site", "")),
                                          data.get("fields") or ("username", "password"),
                                          str(data.get("note", "")))
                elif op == "forget":
                    out = {"site": data.get("site"), "forgotten": v.forget(str(data.get("site", "")))}
                else:
                    out = {"error": "op must be submit|request|forget"}
            except Exception as e:
                out = {"error": f"server error: {type(e).__name__}"}
            return self._send(200, json.dumps(out).encode(), "application/json")
        if path == "/api/brain/learn":
            # Brain self-learning control. Body {op, ...}: op=topic {topic} learns a topic
            # (arXiv+web → KnowledgeBrain); op=pdf {url} ingests a PDF; op=self_eval {topics[]}
            # quizzes itself (incl. non-trading) for a mastery curve. Runs in a bg thread so the
            # request never blocks (learning is slow); returns accepted + current status.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.brain.learner import get_learner
                L = get_learner(); op = str(data.get("op", "")).lower()
                if op in ("loop_on", "loop_off", "queue", "loop_status"):
                    # CONTINUOUS learning loop control (trading/brain/learn_loop.py):
                    # loop_on/off toggles autonomous interval learning; queue adds a topic
                    # the loop studies next; state persists across restarts.
                    from trading.brain.learn_loop import get_learn_loop
                    lp = get_learn_loop()
                    if op == "loop_on":
                        out = lp.enable(True)
                    elif op == "loop_off":
                        out = lp.enable(False)
                    elif op == "queue":
                        out = lp.queue_topic(str(data.get("topic", "")))
                    else:
                        out = lp.status()
                elif op == "self_eval":
                    out = L.self_evaluate(data.get("topics"))
                else:
                    import threading as _th
                    if op == "topic":
                        tgt = str(data.get("topic", ""))
                        _th.Thread(target=lambda: L.learn_topic(tgt), daemon=True).start()
                    elif op == "pdf":
                        url = str(data.get("url", ""))
                        _th.Thread(target=lambda: L.ingest_pdf(url), daemon=True).start()
                    out = {"accepted": op, "note": "learning in background — watch the activity feed",
                           "status": L.status()}
            except Exception as e:
                out = {"error": f"server error: {type(e).__name__}: {e}"[:200]}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
        if path == "/api/brain/web":
            # Autonomous READ-ONLY web screener. Body {op, url|query, site?}: op=screen opens a
            # URL read-only (screenshot+OCR+DOM text+controls, login via vault if walled);
            # op=google browses a knowledge-gap query. Emits ephemeral feed events. Never places
            # orders (execution is API-only). trading/brain/gui/web_screener.py.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.brain.gui.web_screener import get_screener
                sc = get_screener(); op = str(data.get("op", "screen")).lower()
                if op == "google":
                    out = sc.google_gap(str(data.get("query", "")),
                                        max_sites=int(data.get("max_sites", 1)))
                else:
                    out = sc.screen(str(data.get("url", "")), site=data.get("site"),
                                    want_ocr=bool(data.get("ocr", True)))
                # never echo secrets; trim big fields
                if isinstance(out, dict):
                    out.pop("text", None)
            except Exception as e:
                out = {"available": False, "error": f"server error: {type(e).__name__}: {e}"[:200]}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
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
        if path == "/api/trading/crypto/params":
            # Phase F+: adjustable Freqtrade params (paper balance / max trades / stake / leverage)
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.crypto.freqtrade import control as _ctl
                out = _ctl.set_params(paper_balance=data.get("paper_balance"),
                                      max_open_trades=data.get("max_open_trades"),
                                      stake_amount=data.get("stake_amount"),
                                      leverage=data.get("leverage"))
            except Exception as e:
                out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
        if path == "/api/trading/closedtrades/reset":
            # Permanently wipe CLOSED-trade data (brain journal + Freqtrade closed paper trades) so
            # the brain stops learning on contaminated history. Type-to-confirm: body {confirm:"RESET"}.
            # Backs up both stores to trading/state/backups/ first. OPEN trades untouched.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.journal.reset import reset_closed_trades
                out = reset_closed_trades(confirm=data.get("confirm", ""))
            except Exception as e:
                out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
        if path == "/api/trading/crypto/mode":
            # Phase F: guarded crypto paper↔live / spot↔futures switch (FreqUI can't flip these).
            # Body {mode?, segment?, paper_balance?, confirm?}. LIVE needs confirm + real API keys.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.crypto.freqtrade import control as _ctl
                res = _ctl.switch(mode=data.get("mode"), segment=data.get("segment"),
                                  paper_balance=data.get("paper_balance"),
                                  confirm=bool(data.get("confirm", False)))
                out = {"ok": True, **res, "status": _ctl.status()}
            except (PermissionError, ValueError) as e:     # refused (real-money guard / bad arg)
                out = {"ok": False, "reason": str(e)}
            except Exception as e:
                out = {"ok": False, "reason": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
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
                # Phase F: CRYPTO start/stop drives the Freqtrade bot (FreqUI's native action),
                # alongside the shared registry flag. Best-effort — engine may be down.
                if str(market).upper() == "CRYPTO" and action in ("start", "stop"):
                    try:
                        from trading.crypto.engine_client import CryptoEngineClient
                        getattr(CryptoEngineClient(), action)()
                    except Exception:
                        pass
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
                # CRYPTO segment changes also reconfigure the multi-segment Freqtrade engine
                # (vendor/freqtrade fork): persist CRYPTO_SEGMENTS + rewrite config + restart.
                if str(market).upper() == "CRYPTO" and action in ("segments", "toggle_segment"):
                    try:
                        sel = ((controls.status().get("markets") or {})
                               .get("CRYPTO") or {}).get("segments") or []
                        from trading.crypto.freqtrade import control as _ctl
                        _ctl.set_segments_enabled(sel)
                    except Exception as e:
                        out = {"ok": True, "action": action, "engine_sync": f"failed: {e}",
                               "status": controls.status()}
                        return self._send(200, json.dumps(out, default=str).encode(),
                                          "application/json")
                elif action == "set_balance":
                    controls.set_balance(market, float(data.get("amount", 0.0)),
                                         data.get("portfolio_id", "default"))
                elif action == "top_up":
                    controls.top_up(market, float(data.get("amount", 0.0)),
                                    data.get("portfolio_id", "default"))
                elif action == "reset_wallet":
                    controls.reset_wallet(market, data.get("portfolio_id", "default"))
                elif action == "set_strategy":        # trailing ATR mult · sizing method/risk/caps
                    from trading.online.live_loop import get_loop
                    cfg = get_loop().set_config(
                        trail_atr_mult=data.get("trail_atr_mult"),
                        sizing_method=data.get("sizing_method"),
                        max_risk_pct=data.get("max_risk_pct"),
                        max_position_pct=data.get("max_position_pct"),
                        kelly_fraction=data.get("kelly_fraction"),
                        trail_mode=data.get("trail_mode"),
                        trail_pct=data.get("trail_pct"),
                        take_profit_pct=data.get("take_profit_pct"),
                        # auto-open basket + brain-handoff + screener filters
                        enter_all=data.get("enter_all"),
                        top_n_per_segment=data.get("top_n_per_segment"),
                        min_open_per_segment=data.get("min_open_per_segment"),
                        min_open_by_segment=data.get("min_open_by_segment"),
                        leverage_by_segment=data.get("leverage_by_segment"),
                        lot_size_by_segment=data.get("lot_size_by_segment"),
                        min_total_open=data.get("min_total_open"),
                        min_capital_per_trade=data.get("min_capital_per_trade"),
                        brain_handoff_trades=data.get("brain_handoff_trades"),
                        brain_unlimited=data.get("brain_unlimited"),
                        screen_min_pct=data.get("screen_min_pct"),
                        screen_min_quote_volume=data.get("screen_min_quote_volume"))
                    out = {"ok": True, "action": action, "config": cfg}
                    return self._send(200, json.dumps(out, default=str).encode(), "application/json")
                elif action == "close_all":           # flatten every open position now
                    # ALL engines, best-effort: (1) the loop's own paper book, (2) every
                    # Freqtrade-owned crypto trade (forceexit per open pair), (3) every
                    # OpenAlgo sandbox position (covers trades opened outside the loop).
                    from trading.online.live_loop import get_loop
                    res = get_loop().close_all()
                    ft_closed, ft_err = 0, ""
                    try:
                        from trading.crypto.engine_client import CryptoEngineClient
                        eng = CryptoEngineClient()
                        if eng.ping().connected:
                            for pair in list(eng.open_pairs() or []):
                                try:
                                    eng.close_pair(pair)
                                    ft_closed += 1
                                except Exception as e:
                                    ft_err = f"{type(e).__name__}: {e}"[:80]
                    except Exception as e:
                        ft_err = f"{type(e).__name__}: {e}"[:80]
                    oa_res, oa_err = {}, ""
                    try:
                        from trading.openalgo_client import OpenAlgoClient
                        oa = OpenAlgoClient()
                        if not oa.config.is_live:      # paper only — never flatten a live book here
                            oa_res = oa._check(oa._client().closeposition(
                                strategy="dashboard-close-all"), "closeposition")
                    except Exception as e:
                        oa_err = f"{type(e).__name__}: {e}"[:80]
                    out = {"ok": True, "action": action, "result": res,
                           "freqtrade": {"closed_pairs": ft_closed, "error": ft_err},
                           "openalgo": {**oa_res, "error": oa_err},
                           "detail": (f"loop closed {res.get('closed', 0)} · Freqtrade closed "
                                      f"{ft_closed} pairs · OpenAlgo "
                                      f"{oa_res.get('closed_positions', 0)} positions")}
                    return self._send(200, json.dumps(out, default=str).encode(), "application/json")
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
        if path == "/api/trading/brain/ultra/remember":
            # Write a durable Claude-style memory note (one fact per file in brain_memory/,
            # indexed + associatively linked). Body {name, description, body, type}.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.brain import ultra
                out = ultra.remember(str(data.get("name", "note")),
                                     str(data.get("description", "")),
                                     str(data.get("body", "")),
                                     type=str(data.get("type", "lesson")))
                body = json.dumps({"ok": True, **out}).encode()
            except Exception as e:
                body = json.dumps({"ok": False,
                                   "error": f"{type(e).__name__}: {e}"}).encode()
            return self._send(200, body, "application/json")
        if path == "/api/trading/gui/action":
            # Drive the computer-use / GUI agent. JSON body {op, ...}:
            #   op=observe   {target}                      → SEE a dashboard (live read)
            #   op=step      {goal,target,market,dry_run,use_http}  → one perceive→act→learn cycle
            #   op=practice  {goals,rounds}                → compound skills over many dry cycles
            #   op=experiment{}                            → feed observations into HypothesisLedger
            #   op=add_target{name,kind,web_url,api_base}  → register a new operable dashboard
            #   op=arm_live  {armed,confirm}               → arm/disarm real-money actions (2-step)
            # PAPER-FIRST: dry_run defaults TRUE; a real action needs op=arm_live(confirm) first.
            try:
                n = int(self.headers.get("Content-Length", 0) or 0)
                data = json.loads(self.rfile.read(n) or b"{}")
                from trading.brain.gui import register_computer_use_agent
                from trading.brain.gui.targets import DashboardTarget
                agent = _gui_agent()
                op = str(data.get("op", "")).lower()
                if op == "observe":
                    # deep:true opens the live page (Playwright) + OCRs the chart (PaddleOCR);
                    # default shallow read (api+html) stays cheap for routine polling.
                    out = {"ok": True, "op": op,
                           "perception": agent.observe(data.get("target", "own_dashboard"),
                                                        deep=bool(data.get("deep", False)))}
                elif op == "step":
                    dry = data.get("dry_run", True)
                    out = {"ok": True, "op": op, "result": agent.step(
                        str(data.get("goal", "")), data.get("target", "own_dashboard"),
                        data.get("market", "CRYPTO"),
                        dry_run=bool(dry), use_http=bool(data.get("use_http", False)))}
                elif op == "practice":
                    out = {"ok": True, "op": op, "result": agent.practice(
                        data.get("goals"), int(data.get("rounds", 1)),
                        data.get("target", "own_dashboard"))}
                elif op == "experiment":
                    out = {"ok": True, "op": op, "result": agent.experiment()}
                elif op == "add_target":
                    t = agent.targets.add(DashboardTarget(
                        name=str(data["name"]), kind=str(data.get("kind", "external")),
                        web_url=str(data.get("web_url", "")),
                        api_base=str(data.get("api_base", data.get("web_url", ""))),
                        note=str(data.get("note", ""))))
                    out = {"ok": True, "op": op, "target": t.to_dict()}
                elif op == "arm_live":
                    # deliberate 2-step: arming real-money actions requires confirm:true
                    armed = bool(data.get("armed", False))
                    if armed and not bool(data.get("confirm", False)):
                        out = {"ok": False, "op": op,
                               "reason": "arming live requires confirm:true (deliberate 2-step)"}
                    else:
                        agent.actions.allow_live = armed
                        out = {"ok": True, "op": op, "armed_for_live": armed}
                else:
                    out = {"ok": False, "op": op, "error": f"unknown op {op!r}"}
                register_computer_use_agent(agent)        # keep node graph in sync
            except Exception as e:
                out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
            return self._send(200, json.dumps(out, default=str).encode(), "application/json")
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
