"""B3 LENS PAPER LANE — every orphaned directional lens trades under its own identity.

The Two-Path Reckoning (research/fable5/PROMPTS-BRAIN.md B3, owner-ordered 2026-07-16): the
brain's advisory/orphaned lenses — cortex, world-model imagination, concept discovery,
experience recall, news sentiment, the river online learner, the LLM debate room, the dir-exit
oracle, the hypothesis ledger — never had to survive entry timing, exits, fees, or slippage.
This lane gives each one real paper execution: per funnel cycle every lens may nominate its
single strongest conviction from a rotating slice of the universe, and the nomination is opened
as a REAL paper trade tagged ``enter_tag="lens:<name>"``.

Identity & feedback (the one hard requirement — every outcome logged and fed back):
  • ``enter_tag`` → journal ``strategy_name`` (freqtrade_ingest.map_trade) → per-lens realized
    P&L is directly attributable, and ``_learn_from_close`` grades every close back into the
    brain (champion bandit, neurons, river, truth-ledger exit labels).
  • Entry claim → truth ledger ``source="lens:<name>", taken=True`` so each lens accrues its
    own measured direction record from day one.

Honesty rules baked in:
  • A lens with no opinion (None / |p_up−0.5| < min edge) ABSTAINS — no forced nominations
    (direction-must-be-earned, CONVENTIONS §16).
  • Paper only by construction: nominations flow through the same engine_client used by every
    other lane (dry-run Freqtrade; ``allow_live`` stays False from the funnel).
  • Crypto executor only — the NSE/crypto isolation boundary is untouched.

Flags: LENS_LANE=1 (default ON — paper is the experiment, CONVENTIONS §15 forbids inert
wiring), LENS_LANE_SCAN_N (rotation slice per cycle, default 12), LENS_LANE_DEEP_N (symbols the
expensive LLM/MCTS lenses may inspect per cycle, default 2), LENS_LANE_MIN_EDGE (default 0.08),
LENS_LANE_MAX_PER_LENS (nominations per lens per cycle, default 1), LENS_LANE_DISABLE
(comma-list of lens names to switch off individually).
"""
from __future__ import annotations

import os
import threading

_LOCK = threading.Lock()
_CURSOR: dict[str, int] = {}                    # segment -> rotation cursor


def enabled() -> bool:
    return os.environ.get("LENS_LANE", "1") in ("1", "true", "TRUE", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return float(default)


def _disabled() -> set:
    return {s.strip() for s in os.environ.get("LENS_LANE_DISABLE", "").split(",") if s.strip()}


def _p_clamp(p) -> float | None:
    try:
        p = float(p)
    except (TypeError, ValueError):
        return None
    if p != p:
        return None
    return max(0.0, min(1.0, p))


# ── lens adapters: ctx -> p_up | None ─────────────────────────────────────────────
# ctx carries: symbol, segment, regime, ohlcv_fn() (lazy, cached upstream), features (m_* dict).

def _lens_cortex(ctx) -> float | None:
    """CORTEX B8 self-wiring network — shadow-only since it shipped; now it trades."""
    from trading import cortex_signal as cx
    df = ctx["ohlcv_fn"]()
    if df is None:
        return None
    sig = cx.get_cortex_source().signal(ctx["symbol"], df)
    side, conf = sig.get("side"), sig.get("confidence") or 0.0
    if side == "long":
        return 0.5 + 0.5 * min(1.0, float(conf))
    if side == "short":
        return 0.5 - 0.5 * min(1.0, float(conf))
    return None


def _lens_world_model(ctx) -> float | None:
    """World-model imagination (MCTS rollouts) — deep lane, orphaned until now."""
    from trading.direction import brain_sources as bs
    df = ctx["ohlcv_fn"]()
    if df is None:
        return None
    return bs._worldmodel_p(df)


def _lens_concept(ctx) -> float | None:
    """Concept-discovery engine (SSL encoders → SAE probe) — needs a warm fitted engine."""
    from trading.direction import brain_sources as bs
    df = ctx["ohlcv_fn"]()
    if df is None:
        return None
    close = df["close"] if hasattr(df, "__getitem__") else df
    return bs._concept_p(ctx["symbol"], close)


def _lens_experience(ctx) -> float | None:
    """CBR experience bank — recall analogous trades BOTH ways; only a side-differential
    memory may vote (same rule as the hypothesis lens, B1 fix)."""
    from trading.direction import brain_sources as bs
    bank = bs._experience_bank()
    if bank is None:
        return None
    q = {"market": "CRYPTO", "symbol": ctx["symbol"]}
    rl = bank.recall({**q, "direction": "LONG"}, k=10)
    rs = bank.recall({**q, "direction": "SHORT"}, k=10)
    nl, ns = getattr(rl, "n", 0), getattr(rs, "n", 0)
    bl, bs_ = getattr(rl, "bias", 0.0), getattr(rs, "bias", 0.0)
    if max(nl, ns) < 3 or abs(bl - bs_) < 1e-6:
        return None
    # net memory lean: LONG-analogue profitability minus SHORT-analogue profitability
    return _p_clamp(0.5 + 0.25 * (bl - bs_))


def _lens_news(ctx) -> float | None:
    """News sentiment (vader) — measured dry in the B2 census; the lane gives it the chance
    to prove otherwise, and its zero-nomination count is the honest retire evidence."""
    from trading.direction import brain_sources as bs
    return bs._news_p(ctx["symbol"])


def _lens_river(ctx) -> float | None:
    """River online learner under its OWN identity (it also votes inside fusion — here its
    picks face entry/exit/fees alone)."""
    from trading.direction import river_source as rs
    feats = ctx.get("features") or {}
    if not feats:
        return None
    rs.ensure_trained()                # fresh process/reset pickle: bootstrap before predict
    return rs.predict(feats)


def _lens_hypothesis(ctx) -> float | None:
    """Confirmed-hypothesis ledger, side-differential (B1 fix semantics)."""
    from trading.direction import brain_sources as bs
    led = bs._hypothesis_ledger()
    if led is None:
        return None
    base = {"market": "CRYPTO", "symbol": ctx["symbol"],
            "market_regime_entry": ctx.get("regime") or ""}
    sl = led.support({**base, "direction": "LONG"})
    ss = led.support({**base, "direction": "SHORT"})
    if not (sl.get("n") or ss.get("n")):
        return None
    if sl.get("n") == ss.get("n") and abs(sl.get("bias", 0.0) - ss.get("bias", 0.0)) < 1e-6:
        return None                                   # direction-agnostic → abstain
    return _p_clamp(0.5 + 0.25 * (sl.get("bias", 0.0) - ss.get("bias", 0.0)))


def _lens_dir_exit(ctx) -> float | None:
    """The dir-exit oracle's read as an ENTRY opinion — it has 25k+ ledger claims and has
    never had to open a position on one. record=False: the lane's own lens: claim is the record."""
    from trading.direction import dir_exit
    r = dir_exit.read(ctx["symbol"], "CRYPTO", ctx["segment"], regime=ctx.get("regime"))
    s = r.get("strength") or 0.0
    if r.get("direction") not in ("LONG", "SHORT") or abs(s) < 1e-6:
        return None
    return _p_clamp(0.5 + 0.5 * s)


def _lens_debate(ctx) -> float | None:
    """LLM debate room (bull/bear/risk) — contests the naive momentum side; deep lane only."""
    from trading.brain import debate_gate
    feats = ctx.get("features") or {}
    prelim = "long" if float(feats.get("m_momentum", 0.5) or 0.5) >= 0.5 else "short"
    dc = debate_gate.get_debate_gate().contest(ctx["symbol"], prelim, features=feats)
    if dc.get("direction") in ("long", "short") and dc.get("p_up") is not None:
        return _p_clamp(dc["p_up"])
    return None


# cheap lenses look at the whole rotation slice; deep ones (LLM / MCTS / concept fit) at the
# first LENS_LANE_DEEP_N symbols of it.
LENSES: dict[str, tuple] = {
    "cortex": (_lens_cortex, "cheap"),
    "river_online": (_lens_river, "cheap"),
    "dir_exit_read": (_lens_dir_exit, "cheap"),
    "hypothesis": (_lens_hypothesis, "cheap"),
    "experience_recall": (_lens_experience, "cheap"),
    "news_sentiment": (_lens_news, "cheap"),
    "world_model": (_lens_world_model, "deep"),
    "concept_discovery": (_lens_concept, "deep"),
    "debate": (_lens_debate, "deep"),
}


def _rotation(symbols: list[str], segment: str, n: int) -> list[str]:
    """A deterministic rotating slice so coverage accumulates across cycles."""
    if not symbols:
        return []
    with _LOCK:
        cur = _CURSOR.get(segment, 0) % len(symbols)
        _CURSOR[segment] = (cur + n) % len(symbols)
    doubled = symbols + symbols
    return doubled[cur:cur + n]


def nominations(*, symbols: list[str], segment: str, ohlcv_fn, features_fn,
                regime_fn=None) -> list[dict]:
    """One funnel-cycle pass: every enabled lens inspects its slice and returns AT MOST
    LENS_LANE_MAX_PER_LENS nominations — its strongest |p_up − 0.5| edges past the min-edge
    bar. Returns [{lens, symbol, direction, p_up, edge}]. Never raises; a broken lens is
    skipped (and simply accrues no track record — honest absence, not fake neutrality)."""
    if not enabled():
        return []
    scan_n = max(1, int(_f("LENS_LANE_SCAN_N", 12)))
    deep_n = max(1, int(_f("LENS_LANE_DEEP_N", 2)))
    min_edge = _f("LENS_LANE_MIN_EDGE", 0.08)
    per_lens = max(1, int(_f("LENS_LANE_MAX_PER_LENS", 1)))
    off = _disabled()
    slice_ = _rotation(list(symbols or []), segment, scan_n)
    if not slice_:
        return []
    # lazy per-symbol context, built once and shared by all lenses
    ctxs: dict[str, dict] = {}

    def _ctx(sym: str) -> dict:
        if sym not in ctxs:
            cache: dict = {}

            def _ohlcv(s=sym):
                if "df" not in cache:
                    try:
                        cache["df"] = ohlcv_fn(s)
                    except Exception:
                        cache["df"] = None
                return cache["df"]

            def _feats(s=sym):
                if "feats" not in cache:
                    try:
                        cache["feats"] = features_fn(s) or {}
                    except Exception:
                        cache["feats"] = {}
                return cache["feats"]

            regime = None
            if regime_fn is not None:
                try:
                    regime = regime_fn(sym)
                except Exception:
                    regime = None
            ctxs[sym] = {"symbol": sym, "segment": segment, "regime": regime,
                         "ohlcv_fn": _ohlcv, "_feats_fn": _feats}
        c = ctxs[sym]
        c["features"] = c["_feats_fn"]()
        return c

    out: list[dict] = []
    for name, (fn, cost) in LENSES.items():
        if name in off:
            continue
        cands = slice_ if cost == "cheap" else slice_[:deep_n]
        best: list[tuple] = []
        for sym in cands:
            try:
                p = _p_clamp(fn(_ctx(sym)))
            except Exception:
                continue
            if p is None:
                continue
            edge = abs(p - 0.5)
            if edge >= min_edge:
                best.append((edge, sym, p))
        best.sort(reverse=True)
        for edge, sym, p in best[:per_lens]:
            out.append({"lens": name, "symbol": sym,
                        "direction": "LONG" if p >= 0.5 else "SHORT",
                        "p_up": round(p, 4), "edge": round(edge, 4)})
    return out
