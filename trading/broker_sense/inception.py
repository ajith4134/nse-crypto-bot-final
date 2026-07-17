"""Inception ranker — attention by P(move STARTING), not P(move happened).

WHY (SELECTION-CRITIQUE 2026-07-17, measured on 5,495 closed trades): every attention
layer ranked symbols by the COMPLETED 24h move (filter-lane preset, watchlist heat,
LOOK_TOPK order), so the funnel examined exhausted movers while the pre-momentum universe
stayed structurally invisible. The measurement says fresh moves continue (1h run-up
+10%+ band: win 0.570, the only positive band) while STALE big movers (4h>5% with a flat
last hour) and counter-trend fades lose. This module scores the WHOLE universe every
cycle from the RAM mirror on *inception* features — is a move starting NOW — and exposes:

  features(symbol)          -> per-symbol feature dict (None when the mirror can't say)
  score(feats)              -> scalar inception score (documented weights below)
  rank(symbols=None, n=..)  -> [(symbol, score)] best-first over the given/whole universe
  order(symbols)            -> the same symbols re-ordered by inception score (funnel LOOK)
  phase(symbol)             -> lifecycle bucket for the truth-ledger conditioner:
                               quiet | fresh | mid | stale | extended
  fresh_ok(symbol, dir)     -> freshness gate: False ONLY for the measured toxic cohort —
                               a big 4h move in the trade's direction whose last hour has
                               already stalled (signed r240 ≥ 5% and signed r60 < 1%).

Data: RAM mirror only (5m/1m candles, taker aggTrade flow, liquidation feed) — zero API
calls, works for all ~877 mirrored perps. Everything is fail-open and never raises: a
symbol the mirror can't describe scores 0 / phases None / passes the gate — a
measurement gap must never veto or promote a trade by itself.

Env: INCEPTION_FRESH_R240 (5.0), INCEPTION_FRESH_R60 (1.0) — the stale-cohort bounds,
straight from the fine-grained band measurement in SELECTION-CRITIQUE.md §2.
"""
from __future__ import annotations

import math
import os
import threading
import time

_CACHE_TTL = 45.0                       # one funnel cycle ≈ 60s+; scores stay fresh enough
_score_cache: dict[str, tuple[float, dict | None]] = {}
_cache_lock = threading.Lock()


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except (TypeError, ValueError):
        return default


def _flat(symbol: str) -> str:
    return str(symbol or "").replace("/", "").split(":")[0].upper()


def _mirror():
    from trading.broker_sense.binance_stream import get_mirror
    return get_mirror()


# ── features ─────────────────────────────────────────────────────────────────────


def features(symbol: str) -> dict | None:
    """Inception features for one symbol from RAM 5m bars (+taker/liquidation extras).

    Returns None when the mirror has fewer than ~75m of history for the symbol — an
    honest miss; callers treat it as "cannot rank", never as a zero-quality signal."""
    try:
        m = _mirror()
        s = _flat(symbol)
        bars = m.candles(s, 300, 49) or []          # 49×5m ≈ 4h+1 bar
        if len(bars) < 15:                          # need ≥75m to say anything
            return None
        closes = [float(b[4]) for b in bars]
        highs = [float(b[2]) for b in bars]
        lows = [float(b[3]) for b in bars]
        cur = closes[-1]
        if cur <= 0:
            return None

        def _ret(nbars: int) -> float | None:
            if len(closes) <= nbars:
                return None
            past = closes[-1 - nbars]
            return (cur / past - 1.0) * 100.0 if past > 0 else None

        r15, r60, r240 = _ret(3), _ret(12), _ret(48)
        if r15 is None or r60 is None:
            return None
        # acceleration: is the last 15m moving faster than the hour's average pace?
        accel = r15 * 4.0 - r60
        # squeeze percentile: current 30m range width vs the trailing 30m-window widths.
        # A LOW percentile = coiled range — the classic pre-move state.
        widths = []
        for i in range(6, len(bars) + 1):
            w_hi, w_lo = max(highs[i - 6:i]), min(lows[i - 6:i])
            if w_lo > 0:
                widths.append((w_hi - w_lo) / w_lo)
        squeeze_pct = None
        if len(widths) >= 8:
            curw = widths[-1]
            squeeze_pct = sum(1 for w in widths[:-1] if w <= curw) / (len(widths) - 1)
        # breakout freshness: did the LAST bar make a new 60m high/low that the previous
        # bars had not — the first visible footprint of an inception.
        # STRICT inequality: a new high must be ABOVE every prior one — with >= a
        # perfectly flat tape "breaks out" every bar (caught by the unit tests)
        brk_up = highs[-1] > max(highs[-13:-1]) if len(highs) >= 13 else False
        brk_dn = lows[-1] < min(lows[-13:-1]) if len(lows) >= 13 else False
        # move age: consecutive closing bars in the current direction (staleness proxy).
        # A zero delta is a PAUSE — it neither extends nor breaks the move, so a dead-flat
        # tape reads age 0 instead of "48-bar-old move" (caught by the unit tests).
        age, sign = 0, 0
        for i in range(len(closes) - 1, 0, -1):
            d = closes[i] - closes[i - 1]
            if d == 0:
                continue
            s = 1 if d > 0 else -1
            if sign == 0:
                sign = s
            if s != sign:
                break
            age += 1
        out = {"r15": r15, "r60": r60, "r240": r240, "accel": accel,
               "squeeze_pct": squeeze_pct, "brk_up": brk_up, "brk_dn": brk_dn,
               "move_age_bars": age}
        try:                                        # taker flow (5m rolling) when streamed
            tk = m.taker(s)
            out["taker_imbalance"] = tk.get("imbalance") if tk else None
        except Exception:
            out["taker_imbalance"] = None
        try:                                        # liquidation burst = forced-move onset
            liqs = m.recent_liquidations(s, 50) or []
            cutoff = time.time() - 600
            out["liq_10m"] = sum(1 for x in liqs if (x.get("ts") or 0) >= cutoff)
        except Exception:
            out["liq_10m"] = 0
        return out
    except Exception:
        return None


def score(feats: dict | None) -> float:
    """Scalar inception score. Transparent weighted sum — each term is a measured or
    literature-standard inception marker, and the weights are deliberately simple (this
    ranks ATTENTION, it never picks a side — direction still must be earned, §16):
      +2.0 · fresh 60m breakout (either side)         — the move's first footprint
      +1.5 · |accel| capped 5                          — pace is INCREASING now
      +1.0 · (1 − squeeze_pct)                         — coiled range = pre-move state
      +1.0 · |taker imbalance|                         — one-sided aggression right now
      +0.5 · min(liq_10m, 4)/4                         — forced-flow cascade starting
      −1.0 · stale shape (|r240|≥5 & |r60|<1)          — the measured toxic cohort
      −0.5 · move_age > 12 bars                        — hour-old one-way move, late
    """
    if not feats:
        return 0.0
    sc = 0.0
    if feats.get("brk_up") or feats.get("brk_dn"):
        sc += 2.0
    sc += 1.5 * min(5.0, abs(feats.get("accel") or 0.0)) / 5.0
    sq = feats.get("squeeze_pct")
    if sq is not None:
        sc += 1.0 * (1.0 - float(sq))
    ti = feats.get("taker_imbalance")
    if ti is not None:
        sc += 1.0 * min(1.0, abs(float(ti)))
    sc += 0.5 * min(int(feats.get("liq_10m") or 0), 4) / 4.0
    r60, r240 = feats.get("r60"), feats.get("r240")
    if _is_stale(abs(r60 or 0.0), abs(r240) if r240 is not None else None):
        sc -= 1.0
    if int(feats.get("move_age_bars") or 0) > 12:
        sc -= 0.5
    return round(sc, 4)


def cached_features(symbol: str) -> dict | None:
    """features() behind the 45s TTL cache. EVERY consumer goes through here (review
    fix 2026-07-17: phase()/fresh_ok() originally called features() directly, so each
    truth-ledger claim record re-read 49 bars + taker + liquidations from the mirror —
    3× per symbol per cycle on the funnel hot path, exactly what the cache exists to
    bound)."""
    now = time.monotonic()
    s = _flat(symbol)
    with _cache_lock:
        hit = _score_cache.get(s)
        if hit and now - hit[0] < _CACHE_TTL:
            return hit[1]
    feats = features(s)
    with _cache_lock:
        _score_cache[s] = (now, feats)
        if len(_score_cache) > 2000:                # bound the cache
            for k in list(_score_cache)[:500]:
                _score_cache.pop(k, None)
    return feats


def _scored(symbol: str) -> float:
    return score(cached_features(symbol))


def _is_stale(r60: float | None, r240: float | None) -> bool:
    """THE stale-cohort predicate (one definition — score, phase and the gate must
    never disagree): a ≥INCEPTION_FRESH_R240 4h move whose last hour has stalled below
    INCEPTION_FRESH_R60. Signed inputs give the direction-aware answer; absolute inputs
    give the symbol-level one."""
    if r240 is None:
        return False
    return (r240 >= _f("INCEPTION_FRESH_R240", 5.0)
            and (r60 or 0.0) < _f("INCEPTION_FRESH_R60", 1.0))


def rank(symbols=None, n: int | None = None) -> list[tuple[str, float]]:
    """Best-first (symbol, score) over `symbols`, or the whole mirrored universe."""
    try:
        if symbols is None:
            m = _mirror()
            symbols = [r["symbol"] for r in m.futures_rows(min_quote_volume=0.0)] or []
        pairs = [(s, _scored(s)) for s in symbols]
        pairs.sort(key=lambda p: p[1], reverse=True)
        return pairs[:n] if n else pairs
    except Exception:
        return []


def order(symbols: list[str]) -> list[str]:
    """The same symbols re-ordered by inception score (stable for ties — preserves the
    caller's original order as the tiebreak so a cold mirror degrades to the old order)."""
    try:
        if not symbols:
            return []
        idx = {s: i for i, s in enumerate(symbols)}
        scored = [(s, _scored(s)) for s in symbols]
        scored.sort(key=lambda p: (-p[1], idx[p[0]]))
        return [s for s, _ in scored]
    except Exception:
        return list(symbols)


# ── lifecycle phase (truth-ledger conditioner) ───────────────────────────────────


def phase(symbol: str) -> str | None:
    """Direction-agnostic momentum-lifecycle bucket, thresholds from the 2026-07-17
    band measurement: quiet (nothing moving) | fresh (last hour moving) | stale (big 4h
    move, last hour flat — the toxic cohort) | extended (big and still running) | mid."""
    f = cached_features(symbol)
    if f is None:
        return None
    r60, r240 = abs(f.get("r60") or 0.0), abs(f.get("r240") or 0.0)
    if r240 >= 10.0 and r60 >= 2.0:
        return "extended"
    if _is_stale(r60, r240):
        return "stale"
    if r60 >= 2.0:
        return "fresh"
    if r240 < 2.0 and r60 < 1.0:
        return "quiet"
    return "mid"


def fresh_ok(symbol: str, direction: str) -> tuple[bool, str]:
    """Freshness gate for momentum-family entries: refuse ONLY the measured toxic
    cohort — a ≥5% 4h move in the TRADE's direction whose last hour has stalled (<1%).
    (win 0.488/−1.21% stale vs 0.529/−0.92% fresh; filter:* entered at +4.6% 4h with a
    +0.8% hour and ran 0.425/−1.43%.) Missing data → (True, ...): fail-open, a blind
    gate must never block trades."""
    f = cached_features(symbol)
    if f is None:
        return True, "no-data (fail-open)"
    sign = -1.0 if (direction or "LONG").upper() == "SHORT" else 1.0
    sr60 = sign * float(f.get("r60") or 0.0)
    sr240 = sign * float(f.get("r240") or 0.0)
    if _is_stale(sr60, sr240):
        return False, (f"stale momentum: 4h {sr240:+.1f}% but last hour {sr60:+.1f}% "
                       f"— move already stalled")
    return True, f"fresh enough (4h {sr240:+.1f}%, 1h {sr60:+.1f}%)"


def clear_cache() -> None:
    with _cache_lock:
        _score_cache.clear()
