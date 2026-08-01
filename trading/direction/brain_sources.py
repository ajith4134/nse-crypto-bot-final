"""trading/direction/brain_sources.py — brain lenses → MEASURED directional sources.

Converts the brain's formerly *advisory* outputs into signals that actually open trades.
Each lens (hypothesis ledger, experience bank, news sentiment, world-model imagination,
concept-discovery) is consulted, turned into a ``p_up`` in [0,1] = P(LONG), returned as a
``(source, p_up)`` reading for :func:`trading.direction.learned_direction.decide`, and
recorded to the Truth Ledger.

Why this is safe to switch on
-----------------------------
``learned_direction`` fuses sources by their **Wilson-honest measured edge** (Hedge /
multiplicative-weights): a source with no scored history — or one measured near 50% — earns
**~0 weight** and cannot move a trade, while a source proven right earns weight in
proportion to its edge and a *reliably-wrong* one is inverted into a real signal. So adding
an unproven lens here does not risk trades: it starts weightless and *earns* the right to
drive as the ledger scores its calls. This is exactly the owner-approved "earn weight by
measured edge" model — advisory brain outputs become trade drivers only once they prove out.

Cost discipline
---------------
Cheap lenses (hypothesis, experience, news) run inline for every pick. Expensive lenses
(world-model MCTS, concept-discovery SSL encoder) run **only in the deep-verify lane**
(``fast=False``) and behind their own env flag — mirroring the debate-gate pattern — so a
50-coin breadth cycle never blows its deadline.

Env flags (all default ON except the two heavy ones):
  BRAIN_SOURCES=1            master switch
  BRAIN_SRC_HYPOTHESIS=1     confirmed-hypothesis directional support
  BRAIN_SRC_EXPERIENCE=1     CBR recall bias from analogous past trades
  BRAIN_SRC_NEWS=1           news-sentiment P(up)
  BRAIN_SRC_RIVER=1          River online learner P(up) (drift-aware; journal-bootstrapped)
  BRAIN_SRC_WORLDMODEL=1     world-model imagined-R (deep lane only, per-call MCTS fit)
  BRAIN_SRC_CONCEPT=1        concept-discovery live signal (deep lane, per-symbol warm engine)
"""
from __future__ import annotations

import os
import threading
import time

_LOCK = threading.RLock()
_CACHE: dict = {}
_TTL_S = 600.0                      # reload persisted producers every 10 min


# ── env / math helpers ──────────────────────────────────────────────────────────────
def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def _clamp01(x) -> float:
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.5


def _bias_to_p(bias) -> float | None:
    """Map a directional bias in [-1,1] to p_up in [0,1] (0 bias → 0.5 = no signal)."""
    try:
        b = max(-1.0, min(1.0, float(bias)))
    except (TypeError, ValueError):
        return None
    return round(0.5 + 0.5 * b, 4)


def _cached(key: str, build):
    """Lazily build + cache a producer singleton, rebuilt every _TTL_S. Thread-safe.
    A build failure is cached as None (retried after the TTL) so a missing optional
    dependency never repeatedly pays import cost on the hot path."""
    with _LOCK:
        ent = _CACHE.get(key)
        if ent is not None and (time.time() - ent[1]) < _TTL_S:
            return ent[0]
        try:
            obj = build()
        except Exception:
            obj = None
        _CACHE[key] = (obj, time.time())
        return obj


# ── producer accessors (cached) ─────────────────────────────────────────────────────
def _hypothesis_ledger():
    def _b():
        from trading.brain.hypothesis import HypothesisLedger
        return HypothesisLedger(persist=True)          # loads confirmed hypotheses from state
    return _cached("hypothesis", _b)


def _experience_bank():
    def _b():
        from trading.brain.experience import ExperienceBank
        bank = ExperienceBank()
        # best-effort: hydrate from the closed-trade journal so recall has cases to reason
        # over (fast, local, no network). If the bank exposes no backfill, an empty bank
        # simply recalls n=0 → contributes nothing (honest, never fabricated).
        for meth in ("rebuild_from_journal", "hydrate", "backfill"):
            fn = getattr(bank, meth, None)
            if callable(fn):
                try:
                    fn()
                    break
                except Exception:
                    pass
        return bank
    return _cached("experience", _b)


def _news_node():
    def _b():
        from trading.brain.news import NewsResearcher, NewsSentimentNode
        return NewsResearcher(), NewsSentimentNode()
    return _cached("news", _b)


def _world_planner():
    def _b():
        from trading.brain.worldmodel import ImaginationPlanner
        return ImaginationPlanner()
    return _cached("worldmodel", _b)


def _concept_engine():
    """A *warm, fitted* ConceptDiscoveryEngine published by the discovery loop, if any.
    We never fit the SSL encoder on the hot path — if no warm engine is registered we
    return None and the concept source simply abstains."""
    with _LOCK:
        eng = _CACHE.get("concept_warm")
        return eng[0] if eng else None


def register_concept_engine(engine) -> None:
    """Called by the concept-discovery loop after a fit so the direction path can read
    ``live_signal`` in O(1) without re-fitting. Keeps the SSL encoder off the hot path."""
    with _LOCK:
        _CACHE["concept_warm"] = (engine, time.time())


# ── individual lens → p_up ──────────────────────────────────────────────────────────
def _news_p(symbol: str) -> float | None:
    """P(up) from news sentiment. Reads the news-ingest daemon's already-fetched,
    already-scored ``news_memory.json`` (zero network — THE MOTTO: RAM/disk-first).

    Fix 2026-07-17: the old path built a NewsResearcher with **no fetcher**, so
    ``research()`` always returned n_articles=0 and the ``news_sentiment`` source was
    permanently dark. The ingest daemon writes scored items every cycle; we just needed a
    reader. Symbol-scoped (matches the coin root against each item's ``symbols``/title),
    recency-gated, and floored at LEARNED_DIR_NEWS_MIN_ARTICLES so one stray headline can't
    move a trade. §16-safe: emits a reading that earns weight only once outcomes prove it."""
    try:
        from trading import state
        mem = state.load_json("news_memory.json", {}) or {}
        items = mem.get("items") or []
        if not items:
            return None
        base = str(symbol or "").replace("/", "").split(":")[0].upper()   # BTCUSDT
        root = base
        for q in ("USDT", "USDC", "USD", "BUSD"):
            if base.endswith(q) and len(base) > len(q):
                root = base[: -len(q)]                                     # BTC
                break
        ttl = float(os.environ.get("LEARNED_DIR_NEWS_TTL_S", "21600"))     # 6h
        floor = int(os.environ.get("LEARNED_DIR_NEWS_MIN_ARTICLES", "2"))
        now = time.time()
        rel = []
        for it in items:
            try:
                if now - float(it.get("ts") or 0) > ttl:
                    continue
            except (TypeError, ValueError):
                continue
            syms = {str(s).replace("/", "").split(":")[0].upper() for s in (it.get("symbols") or [])}
            title = str(it.get("title") or "").upper()
            if base in syms or root in syms or (len(root) >= 3 and root in title):
                try:
                    rel.append(float(it.get("compound") or 0.0))
                except (TypeError, ValueError):
                    continue
        if len(rel) < floor:
            return None
        avg = max(-1.0, min(1.0, sum(rel) / len(rel)))
        # compound[-1,1] → modest band around 0.5 (news is a prior, not a forecast)
        return _clamp01(0.5 + 0.35 * avg)
    except Exception:
        return None


def _mom_ts_p(symbol: str) -> float | None:
    """R1 (2026-07-17 direction-ceiling research): per-coin TIME-SERIES MOMENTUM — the one
    directional edge that actually replicates at a 15m–4h hold (trend factor Sharpe ~1.2 in the
    literature; what real systematic desks run at multi-hour holds, while OFI/book/CVD is
    execution-only and pure noise at this horizon — which is exactly why our microstructure fusion
    tops out at ~0.52). Vol-scaled trend t-stat → P(up); abstains when the trend is weak
    (underpowered ⇒ no side, per DIRECTION-MUST-BE-EARNED). Zero network — reads the in-RAM 5m
    mirror. §16-safe: emits a reading that earns weight only once the truth ledger proves it."""
    try:
        import math
        df = _mirror_ohlcv(symbol, tf_s=300, n=200)
        if df is None:
            return None
        close = [float(x) for x in (df["close"].tolist() if hasattr(df, "__getitem__") else df)]
        L = int(float(os.environ.get("MOM_TS_LOOKBACK_BARS", "48") or 48))   # 48×5m = 4h
        if len(close) < L + 5:
            return None
        seg = close[-(L + 1):]
        rets = [math.log(seg[i + 1] / seg[i]) for i in range(len(seg) - 1)
                if seg[i] > 0 and seg[i + 1] > 0]
        if len(rets) < L // 2 or seg[0] <= 0:
            return None
        mom = math.log(seg[-1] / seg[0])
        mu = sum(rets) / len(rets)
        vol = math.sqrt(sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1))
        if vol <= 0:
            return None
        t = mom / (vol * math.sqrt(len(rets)))                # trend t-stat
        # A random walk's t is ~N(0,1), so a low floor emits a spurious side on pure noise
        # (~62% of the time at floor 0.5). Require ≥1.5σ so we only call a side on a genuinely
        # clear trend and abstain on noise — the truth ledger then measures if it predicts.
        if abs(t) < float(os.environ.get("MOM_TS_MIN_T", "1.5") or 1.5):
            return None                                       # weak/ambiguous trend → abstain
        return _clamp01(0.5 + 0.4 * math.tanh(t))
    except Exception:
        return None


def _worldmodel_p(ohlcv) -> float | None:
    planner = _world_planner()
    if planner is None or ohlcv is None or len(ohlcv) < 30:
        return None
    plan = planner.plan(ohlcv)
    act = str(plan.get("action", "")).upper()
    er = float(plan.get("expected_R", 0.0) or 0.0)
    import math
    mag = 0.5 * math.tanh(abs(er))                      # |R| → conviction in [0,0.5)
    if any(t in act for t in ("LONG", "BUY")):
        return round(0.5 + mag, 4)
    if any(t in act for t in ("SHORT", "SELL")):
        return round(0.5 - mag, 4)
    return None                                          # HOLD / flat → no directional claim


def _mirror_ohlcv(symbol: str, *, tf_s: int = 300, n: int = 160):
    """5m OHLC DataFrame for the deep lenses from the in-RAM mirror (mark-price bars,
    volume=0 — the world-model's features are price-derived). None until the mirror holds
    ≥30 bars, so a fresh process abstains instead of hallucinating on a stub series."""
    try:
        import pandas as pd
        from trading.broker_sense.binance_stream import get_mirror
        flat = (symbol or "").replace("/", "").split(":")[0].upper()
        rows = get_mirror().candles(flat, tf_s, n) or []
        if len(rows) < 30:
            return None
        df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close"][:len(rows[0])])
        if "close" not in df.columns:
            return None
        df["volume"] = 0.0
        return df
    except Exception:
        return None


def _concept_p(symbol: str, series) -> float | None:
    """Concept-discovery directional signal via the live per-symbol registry
    (trading.brain.discovery.signal) — it keeps a fitted engine warm per symbol and refits in
    the background, so this is O(1) on the hot path. Only the proof-gated `validated` lane
    (never the shadow `experiment` lane) is allowed to size a trade."""
    try:
        from trading.brain.discovery import signal as _ds
    except Exception:
        _ds = None
    if _ds is not None:
        sig = _ds.signal(symbol, series)
        val = sig.get("validated", 0.0)
        if sig.get("n_val") and abs(val) > 1e-6:
            return _bias_to_p(val)
        return None
    # fallback: a warm engine explicitly registered by a loop (rare)
    eng = _concept_engine()
    if eng is None:
        return None
    sig = eng.live_signal(series)
    val = sig.get("validated", 0.0)
    if sig.get("n_val") and abs(val) > 1e-6:
        return _bias_to_p(val)
    return None


# ── public API ──────────────────────────────────────────────────────────────────────
def collect(symbol: str, *, market: str = "CRYPTO", segment: str = "futures",
            regime: str | None = None, direction_hint: str | None = None,
            ohlcv=None, features: dict | None = None,
            fast: bool = True, record: bool = True) -> list[tuple[str, float]]:
    """Consult every enabled brain lens → list of ``(source, p_up)`` readings.

    ``direction_hint`` (the fusion's preliminary lean) lets the direction-aware lenses
    (hypothesis / experience) score the candidate side. ``ohlcv`` (a DataFrame with a
    ``close`` column) enables the deep-lane lenses. Each emitted reading is also written to
    the Truth Ledger (unless ``record=False``) so it accrues a measured track record.
    Never raises — a failing lens is skipped, and the worst case is an empty list.
    """
    if not _flag("BRAIN_SOURCES"):
        return []
    reads: list[tuple[str, float]] = []
    seg = segment or "futures"
    dir_hint = (direction_hint or "").upper()

    def _emit(source: str, p_up: float | None) -> None:
        if p_up is None:
            return
        p = _clamp01(p_up)
        reads.append((source, p))
        if record:
            try:
                from trading.direction import truth_ledger as _tl
                _tl.record(symbol=symbol, market=market, segment=seg,
                           direction=("LONG" if p >= 0.5 else "SHORT"), source=source,
                           confidence=(p if p >= 0.5 else 1.0 - p), regime=regime)
            except Exception:
                pass

    # NB (B1 fix 2026-07-16): hypothesis.support() and experience.recall() score the HINTED
    # side (their bias means "the hinted direction is right"), while _emit records an ABSOLUTE
    # p_up. Recording the relative score directly made `hypothesis` vote LONG 100% of the time.
    def _rel_to_abs(p_rel: float | None, hint: str) -> float | None:
        if p_rel is None:
            return None
        return p_rel if hint != "SHORT" else round(1.0 - p_rel, 4)

    # 1) confirmed-hypothesis support — the AI-Scientist research loop endorses a direction.
    # Side-differential gate (B1 fix 2026-07-16): generic hypotheses whose conditions ignore
    # direction match BOTH sides with the same bias — that carried zero directional information
    # yet emitted a constant ~0.976 vote on every LONG-hinted candidate. Probe both sides; only
    # a hypothesis set that actually DISTINGUISHES the sides may vote.
    if _flag("BRAIN_SRC_HYPOTHESIS") and dir_hint in ("LONG", "SHORT"):
        try:
            led = _hypothesis_ledger()
            if led is not None:
                ctx = {"market": market, "symbol": symbol,
                       "market_regime_entry": regime or ""}
                other = "SHORT" if dir_hint == "LONG" else "LONG"
                sup = led.support({**ctx, "direction": dir_hint})
                sup_o = led.support({**ctx, "direction": other})
                differential = (sup.get("n", 0) != sup_o.get("n", 0)
                                or abs(sup.get("bias", 0.0) - sup_o.get("bias", 0.0)) > 1e-6)
                if sup.get("n") and differential:
                    _emit("hypothesis", _rel_to_abs(_bias_to_p(sup["bias"]), dir_hint))
        except Exception:
            pass

    # 2) experience bank — CBR recall bias from analogous past trades
    if _flag("BRAIN_SRC_EXPERIENCE"):
        try:
            bank = _experience_bank()
            if bank is not None:
                _xh = dir_hint if dir_hint in ("LONG", "SHORT") else "LONG"
                rc = bank.recall({"market": market, "symbol": symbol,
                                  "direction": _xh}, k=10)
                if getattr(rc, "n", 0) >= 3 and abs(getattr(rc, "bias", 0.0)) > 1e-6:
                    _emit("experience_recall", _rel_to_abs(_bias_to_p(rc.bias), _xh))
        except Exception:
            pass

    # 3) news sentiment — vader compound → P(up)
    if _flag("BRAIN_SRC_NEWS"):
        try:
            p = _news_p(symbol)
            if p is not None and abs(p - 0.5) > 1e-6:
                _emit("news_sentiment", p)
        except Exception:
            pass

    # 3b) time-series MOMENTUM (R1, 2026-07-17) — the replicated multi-hour direction edge.
    #     The only source here that is NOT microstructure (which is noise at our hold); it is the
    #     research's #1 ceiling-breaker. Earns weight via the truth ledger like every other lens.
    if _flag("BRAIN_SRC_MOM_TS"):
        try:
            p = _mom_ts_p(symbol)
            if p is not None and abs(p - 0.5) > 1e-6:
                _emit("mom_ts", p)
        except Exception:
            pass

    # 3c) NOTEBOOK universe read (2026-07-21) — the Practice Notebook's fast vol-scaled momentum
    #     direction read, the SAME signal it grades across ALL ~880 symbols every cycle. This lens
    #     therefore carries a track record measured on the whole universe (not just traded picks),
    #     closing the loop the owner asked for: universe practice → truth ledger → brain weight.
    #     Earns weight via the truth ledger like every other lens. Kill: BRAIN_SRC_NOTEBOOK=0.
    if _flag("BRAIN_SRC_NOTEBOOK"):
        try:
            from trading.brain.practice_notebook import cheap_direction as _cd
            _c = _cd(symbol)
            if _c and _c.get("p_up") is not None and abs(_c["p_up"] - 0.5) > 1e-6:
                _emit("notebook_scan", _c["p_up"])
        except Exception:
            pass

    # 4) River online learner — drift-aware P(up) from the live feature dict (cheap, O(1));
    #    bootstrapped from the journal so it is trained from process start
    if _flag("BRAIN_SRC_RIVER") and features:
        try:
            from trading.direction import river_source as _rs
            _rs.ensure_trained()
            p = _rs.predict(features)
            if p is not None and abs(p - 0.5) > 1e-6:
                _emit("river_online", p)
        except Exception:
            pass

    # 5) world-model imagination + concept-discovery — DEEP lane only. E3 (2026-07-17):
    # these were TRIPLE-gated dark — flags defaulted off, the sole production caller was
    # fast=True, and no caller ever passed `ohlcv`. The lane fix made the selective lane call
    # fast=False; the flags now default ON; and when the caller has no ohlcv we build it from
    # the in-RAM mirror's 5m bars (every perp, zero API — the ccxt fetch these lenses were
    # written against is anti-motto). Until the mirror has ≥30 bars (~2.5h after a restart)
    # they skip honestly.
    if not fast and (ohlcv is None) \
            and (_flag("BRAIN_SRC_WORLDMODEL") or _flag("BRAIN_SRC_CONCEPT")):
        ohlcv = _mirror_ohlcv(symbol)
    if not fast and _flag("BRAIN_SRC_WORLDMODEL") and ohlcv is not None:
        try:
            _emit("world_model", _worldmodel_p(ohlcv))
        except Exception:
            pass

    if not fast and _flag("BRAIN_SRC_CONCEPT") and ohlcv is not None:
        try:
            close = ohlcv["close"] if hasattr(ohlcv, "__getitem__") else ohlcv
            _emit("concept_discovery", _concept_p(symbol, close))
        except Exception:
            pass

    return reads


def status() -> dict:
    """Honest snapshot of which lenses are available right now (for the dashboard)."""
    return {
        "enabled": _flag("BRAIN_SOURCES"),
        "hypothesis": _flag("BRAIN_SRC_HYPOTHESIS") and _hypothesis_ledger() is not None,
        "experience": _flag("BRAIN_SRC_EXPERIENCE") and _experience_bank() is not None,
        "news": _flag("BRAIN_SRC_NEWS") and _news_node() is not None,
        "river_online": _flag("BRAIN_SRC_RIVER"),
        "world_model": _flag("BRAIN_SRC_WORLDMODEL"),
        "concept_discovery": _flag("BRAIN_SRC_CONCEPT"),
    }
