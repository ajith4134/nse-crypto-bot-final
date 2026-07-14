"""dashboard/brain_live.py — LIVE brain snapshots from REAL data.

Mirrors run_brain_t8.build_demo_* but feeds the live trade journal (journal.json) and real ccxt
OHLCV instead of synthetic data, so the dashboard brain panels show REAL experience/pattern/regime/
pipeline activity. Each builder falls back to the deterministic demo builder on any error or when
there isn't enough real data yet (honest: never fabricates, and labels demo:true when it falls back).
"""
from __future__ import annotations

import threading
import time

_MIN_TRADES = 16

# Each builder is expensive (ccxt OHLCV fetch + HMM fit + kNN over the whole journal), and the
# panels poll every few seconds — cache results ~45s so polling stays cheap.
_CACHE: dict = {}
_TTL = 45.0
_CACHE_LOCKS: dict = {}
_CACHE_LOCKS_GUARD = threading.Lock()


def _cached(key, fn):
    """Single-flight TTL cache. When the entry expires, ONE caller recomputes while
    concurrent callers queue on the per-key lock and then serve the fresh value —
    without this, continuous hub polling made every poller recompute the HMM/OLS fit
    simultaneously and stampede the GIL (2026-07-02 audit fix)."""
    hit = _CACHE.get(key)
    now = time.monotonic()
    if hit and (now - hit[0]) < _TTL:
        return hit[1]
    with _CACHE_LOCKS_GUARD:
        lock = _CACHE_LOCKS.setdefault(key, threading.Lock())
    with lock:
        hit = _CACHE.get(key)                       # re-check after acquiring
        if hit and (time.monotonic() - hit[0]) < _TTL:
            return hit[1]
        val = fn()
        _CACHE[key] = (time.monotonic(), val)
        return val


_CCXT_CLIENT = None
_CCXT_GUARD = threading.Lock()


def _ccxt_client():
    """One reused ccxt spot client (thread-safe build). Creating a fresh ccxt.binance()
    per call re-ran load_markets() and leaked keep-alive sockets under hub polling."""
    global _CCXT_CLIENT
    if _CCXT_CLIENT is not None:
        return _CCXT_CLIENT
    with _CCXT_GUARD:
        if _CCXT_CLIENT is None:
            import ccxt
            _CCXT_CLIENT = ccxt.binance({"enableRateLimit": True, "timeout": 8000})
    return _CCXT_CLIENT


def _real_journal():
    from trading.journal.journal import TradeJournal
    return TradeJournal(state_file="journal.json", persist=True)


def _real_ohlcv(symbol: str = "BTC/USDT", tf: str = "5m", limit: int = 400):
    """Real OHLCV DataFrame (datetime-indexed open/high/low/close/volume) via ccxt spot."""
    import pandas as pd
    raw = _ccxt_client().fetch_ohlcv(symbol, timeframe=tf, limit=limit)
    df = pd.DataFrame(raw, columns=["ts", "open", "high", "low", "close", "volume"])
    df["date"] = pd.to_datetime(df["ts"], unit="ms")
    return df.set_index("date")[["open", "high", "low", "close", "volume"]]


def _experience() -> dict:
    """ExperienceBank CBR over the REAL closed-trade journal."""
    import run_brain_t8 as d
    jr = _real_journal()
    if len(jr.trades) < _MIN_TRADES:
        return {**d.build_demo_experience(), "demo": True}
    from trading.brain.experience import ExperienceBank
    from trading.brain.semantic import SemanticMemory
    bank = ExperienceBank(use_lancedb=False)
    bank.from_journal(jr)
    recall = bank.recall(d.SAMPLE_QUERY, k=8)
    sm = SemanticMemory(enabled=False)
    return {"experience": bank.status(), "sample_recall": recall.as_dict(),
            "semantic": sm.status(), "demo": False, "n_trades": len(jr.trades)}


def _patterns() -> dict:
    """PatternScanner motifs + hmmlearn RegimeModel on REAL BTC OHLCV. Picking/entry-exit are
    universe-level (need a multi-asset universe + the brain loop) — wired live in Batch 2."""
    import run_brain_t8 as d
    try:
        ohlcv = _real_ohlcv("BTC/USDT", "5m", 180)  # smaller series → fast STUMPY matrix-profile
    except Exception:
        return {**d.build_demo_brain_t86(), "demo": True}
    from trading.brain.patterns import PatternScanner
    from trading.brain.regime import RegimeModel
    scan = PatternScanner(window=20).scan(ohlcv, k=3)
    reg = RegimeModel(n_states=3, seed=0).fit(ohlcv)
    # `current` = the human-readable regime label the panel shows (bull/bear/neutral); the
    # status() detail (n_states/fitted/labels) rode alone before, so the UI stringified the whole
    # dict → "[object Object]". current_regime() is the same call the live pipeline uses.
    try:
        _cur = reg.current_regime(ohlcv)
    except Exception:
        _cur = "—"
    return {"patterns": scan.as_dict() if hasattr(scan, "as_dict") else scan,
            "regime": {"current": _cur,
                       **(reg.status() if hasattr(reg, "status") else {"regime": "—"})},
            "picking": {"note": "live universe ranking comes online with the brain loop (Batch 2)"},
            "entryexit": {"note": "live entry/exit gating comes online with the brain loop (Batch 2)"},
            "demo": False, "symbol": "BTC/USDT", "tf": "5m"}


def _pipeline() -> dict:
    """BrainTradingPipeline-style snapshot built on REAL journal + REAL OHLCV."""
    import run_brain_t8 as d
    jr = _real_journal()
    if len(jr.trades) < _MIN_TRADES:
        return {**d.build_demo_pipeline(), "demo": True}
    try:
        ohlcv = _real_ohlcv("BTC/USDT", "5m", 400)
    except Exception:
        return {**d.build_demo_pipeline(), "demo": True}
    from trading.brain.regime import RegimeModel
    from trading.brain.experience import ExperienceBank
    from trading.brain.pipeline import BrainTradingPipeline
    reg = RegimeModel(n_states=3, seed=0).fit(ohlcv)
    exp = ExperienceBank(use_lancedb=False)
    exp.from_journal(jr)
    pipe = BrainTradingPipeline(market="CRYPTO", regime_model=reg, experience=exp)
    decision = pipe.decide("BTC/USDT", ohlcv)
    decision = decision.as_dict() if hasattr(decision, "as_dict") else decision
    status = pipe.status() if hasattr(pipe, "status") else {}
    demo = d.build_demo_pipeline()  # NSE needs OpenAlgo; reuse demo shape for nse/gate/seeds
    return {
        "crypto": decision,
        "nse": demo.get("nse"),
        "safety": status.get("safety", demo.get("safety")),
        "stream_of_mind": status.get("stream_of_mind", demo.get("stream_of_mind")),
        "gate_demo": demo.get("gate_demo"),
        "strategy_seeds": demo.get("strategy_seeds"),
        "demo": False, "n_trades": len(jr.trades),
    }


_RSS_FEEDS = [
    "https://cointelegraph.com/rss",
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
]


def _news() -> dict:
    """REAL crypto news sentiment — live RSS (feedparser) → VADER per-symbol aggregate."""
    import run_brain_t8 as d
    from trading.brain.news import NewsResearcher, fetch_rss, NewsSentimentNode
    from trading.brain.sentiment import SentimentScorer
    items = []
    for url in _RSS_FEEDS:
        try:
            items += fetch_rss(url, limit=25)
        except Exception:
            pass
    if not items:
        return {**d.build_demo_news(), "demo": True}
    researcher = NewsResearcher(scorer=SentimentScorer(backend="vader"))
    research, node_p_bullish = {}, {}
    node = NewsSentimentNode()
    for sym in ("BTC", "ETH", "SOL"):
        res = researcher.research(sym, items=items)
        research[sym] = res
        try:
            comp = res.get("avg_compound", 0.0) if isinstance(res, dict) else 0.0
            node_p_bullish[sym] = node.p_bullish(comp) if hasattr(node, "p_bullish") else round((float(comp) + 1) / 2, 4)
        except Exception:
            node_p_bullish[sym] = None
    return {"scorer_backend": researcher.scorer.active_backend, "research": research,
            "autonomous": {"enabled": False,
                           "note": "GPT-Researcher gated (set GPT_RESEARCHER_ENABLED=1 + an LLM key)"},
            "node_p_bullish": node_p_bullish, "demo": False, "n_items": len(items)}


def live_news() -> dict:
    return _cached("news", _news)


def _skills() -> dict:
    """The REAL persisted Voyager skill library (skill_library.json). Filled by the self-evolve
    loop (Batch 3) — shows the real store now (often empty until evolution is armed)."""
    from trading.brain.skills import SkillLibrary
    lib = SkillLibrary()
    st = lib.status()
    skills = st.get("skills", st) if isinstance(st, dict) else st
    n = len(skills) if hasattr(skills, "__len__") else (st.get("n_skills", 0) if isinstance(st, dict) else 0)
    return {"skills": st, "skill_events": [], "best": None, "tracer": {},
            "stream_of_mind": [],
            "self_improve": {"note": "SelfImprover hill-climb runs inside the self-evolve loop (Batch 3)"},
            "dspy": {"enabled": False, "note": "DSPy/GEPA gated (set DSPY_ENABLED=1 + an LLM key)"},
            "demo": False, "n_skills": n}


def live_skills() -> dict:
    return _cached("skills", _skills)


# patterns + pipeline run PatternScanner (STUMPY/numba) whose first call JIT-compiles for ~40s.
# Warm it ONCE in a background thread (populating the cache) and serve a "warming…" placeholder
# until ready, so the first panel poll never blocks/times out.
import threading

_WARM_DONE = threading.Event()
_warm_started = False
_warm_lock = threading.Lock()


def _ensure_warm():
    global _warm_started
    with _warm_lock:
        if _warm_started:
            return
        _warm_started = True

    def _run():
        for key, fn in (("patterns", _patterns), ("pipeline", _pipeline), ("experience", _experience)):
            try:
                _CACHE[key] = (time.monotonic(), fn())
            except Exception:
                pass
        _WARM_DONE.set()

    threading.Thread(target=_run, daemon=True).start()


def _warming(extra: dict) -> dict:
    return {**extra, "demo": False, "warming": True,
            "note": "warming STUMPY/numba JIT (~40s, first run only)…"}


def live_experience() -> dict:
    return _cached("experience", _experience)  # fast (no numba)


def live_patterns() -> dict:
    _ensure_warm()
    hit = _CACHE.get("patterns")
    if hit and (time.monotonic() - hit[0]) < _TTL:
        return hit[1]
    if not _WARM_DONE.is_set():
        return _warming({"patterns": {}, "regime": {"regime": "warming…"}, "picking": {}, "entryexit": {}})
    return _cached("patterns", _patterns)


def live_pipeline() -> dict:
    _ensure_warm()
    hit = _CACHE.get("pipeline")
    if hit and (time.monotonic() - hit[0]) < _TTL:
        return hit[1]
    if not _WARM_DONE.is_set():
        return _warming({"crypto": {}, "nse": {}, "safety": {}, "stream_of_mind": ["warming…"],
                         "gate_demo": {}, "strategy_seeds": []})
    return _cached("pipeline", _pipeline)
