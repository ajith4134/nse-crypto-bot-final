"""trading/direction/micro_features.py — D4: microstructure direction features (Pillar 27).

The freshest direction information the box already pays for, packaged as (a) FEATURES
for the D6 meta-labeler and (b) independent shadow CLAIMS in the Truth Ledger — each
lane records its own vote per candidate per cycle under its own source name, so every
lane must EARN a measured hit-rate before the Mirror Gate or the meta-labeler leans on
it. This is the D7 shadow league's founding roster:

  venue_leadlag   — Binance (the documented price-discovery leader; SOTA notes §3)
                    printing above/below the other pooled venues' consensus predicts
                    the laggards' next move. Gap in bps from live pool tickers.
  psych_ofi       — order-flow/book-imbalance sign from the trader-psychology engine
                    (Cont-Kukanov-Stoikov linearity; SOTA notes §2). Cached engine read.
  funding_extreme — funding-rate z-score from the LOCAL 1h funding feathers; an
                    extreme means a crowded side → contrarian vote (SOTA notes §5).
  mtf_agree       — 15m/1h/4h close-vs-SMA20 agreement from LOCAL feathers (the
                    owner's multi-timeframe ask, measured instead of assumed).

Zero-cost rules: feathers first (no network); the ONLY network reads are pool tickers
(token-bucket budgeted per venue) and the psychology engine's cached book snapshot.
Levers: MICRO_FEATURES=0 disables claim recording; VENUE_GAP_BPS (default 5),
FUNDING_Z (default 1.0).
"""
from __future__ import annotations

import os
import time

_VENUE_TTL_S = 20.0
_venue_cache: dict = {}


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _enabled() -> bool:
    return os.environ.get("MICRO_FEATURES", "1") in ("1", "true", "TRUE", "yes", "on")


# ── venue lead-lag ────────────────────────────────────────────────────────────────


def venue_gap(symbol: str) -> dict:
    """Binance last vs the other pooled venues' median last, in bps (+ = Binance
    higher → laggards expected to follow UP). {'gap_bps', 'n_venues', 'vote', 'conf'};
    honest None-vote when fewer than 2 venues answer."""
    out = {"gap_bps": None, "n_venues": 0, "vote": None, "conf": None}
    key = symbol
    now = time.monotonic()
    hit = _venue_cache.get(key)
    if hit and now - hit[0] < _VENUE_TTL_S:
        return hit[1]
    try:
        from trading.crypto.exchange_pool import get_pool, pool_enabled
        if not pool_enabled():
            return out
        pool = get_pool("swap")
        leader = None
        others = []
        for v in pool.venues:
            if v.cooling() or not v.bucket.take():
                continue
            try:
                sym = pool._norm(symbol)
                if not pool._has_symbol(v, sym):
                    continue
                last = (v.client().fetch_ticker(sym) or {}).get("last")
                if not last:
                    continue
                v.reward()
                if v.name == "binance":
                    leader = float(last)
                else:
                    others.append(float(last))
            except Exception as exc:
                try:
                    v.punish(exc)
                except Exception:
                    pass
        if leader and others:
            others.sort()
            med = others[len(others) // 2]
            gap = (leader - med) / med * 1e4
            thr = _env_f("VENUE_GAP_BPS", 5.0)
            out = {"gap_bps": round(gap, 2), "n_venues": 1 + len(others),
                   "vote": ("LONG" if gap > thr else
                            "SHORT" if gap < -thr else None),
                   "conf": round(min(1.0, abs(gap) / (4 * thr)), 3)
                   if abs(gap) > thr else None}
    except Exception:
        pass
    _venue_cache[key] = (now, out)
    if len(_venue_cache) > 200:
        _venue_cache.pop(next(iter(_venue_cache)))
    return out


# ── funding extreme (local feathers) ──────────────────────────────────────────────


def funding_extreme(symbol: str) -> dict:
    """z-score of the latest 1h funding rate vs its trailing 30 readings, from the
    local funding feather. Extreme positive funding = crowded longs → SHORT vote."""
    out = {"funding_z": None, "vote": None, "conf": None}
    try:
        import pandas as pd
        from trading.direction.truth_ledger import _candle_dir
        base = symbol.split("/")[0]
        p = (_candle_dir() / "futures"
             / f"{base}_USDT_USDT-1h-funding_rate.feather")
        if not p.exists():
            return out
        df = pd.read_feather(p, columns=["date", "open"])   # funding rate in 'open'
        rates = df["open"].astype(float).tail(31)
        if len(rates) < 12:
            return out
        hist, last = rates.iloc[:-1], float(rates.iloc[-1])
        std = float(hist.std())
        if std <= 0:
            return out
        z = (last - float(hist.mean())) / std
        thr = _env_f("FUNDING_Z", 1.0)
        out = {"funding_z": round(z, 3),
               "vote": ("SHORT" if z > thr else "LONG" if z < -thr else None),
               "conf": round(min(1.0, abs(z) / (3 * thr)), 3)
               if abs(z) > thr else None}
    except Exception:
        pass
    return out


# ── multi-timeframe agreement (local feathers) ────────────────────────────────────


def mtf_agree(symbol: str, segment: str = "futures") -> dict:
    """Close vs SMA20 on the 15m / 1h / 4h local feathers; a vote only when ALL
    available frames agree (a human doesn't trade a chart that disagrees with itself)."""
    out = {"frames": {}, "vote": None, "conf": None}
    try:
        import pandas as pd
        from trading.direction.truth_ledger import _feather_for
        p5, _ = _feather_for(symbol, segment)
        if p5 is None:
            return out
        signs = {}
        for tf in ("15m", "1h", "4h"):
            p = p5.with_name(p5.name.replace("-5m-", f"-{tf}-"))
            if not p.exists():
                continue
            df = pd.read_feather(p, columns=["date", "close"])
            closes = df["close"].astype(float).tail(40)
            if len(closes) < 21:
                continue
            sma = float(closes.tail(20).mean())
            signs[tf] = 1 if float(closes.iloc[-1]) > sma else -1
        out["frames"] = signs
        if len(signs) >= 2 and len(set(signs.values())) == 1:
            out["vote"] = "LONG" if next(iter(signs.values())) > 0 else "SHORT"
            out["conf"] = round(len(signs) / 3.0, 2)
    except Exception:
        pass
    return out


# ── order-flow (psychology engine, cached) ────────────────────────────────────────


def psych_ofi(symbol: str, segment: str = "futures") -> dict:
    """OBI/OFI-composite sign from the trader-psychology engine's cached book read."""
    out = {"obi": None, "ofi_z": None, "vote": None, "conf": None}
    try:
        from trading.brain.psychology import get_engine
        r = get_engine().evaluate("CRYPTO", symbol, segment=segment)
        if not r:
            return out
        obi = r.get("psych_obi")
        ofi_z = r.get("psych_ofi_z")
        out["obi"], out["ofi_z"] = obi, ofi_z
        score = 0.6 * float(obi or 0) + 0.4 * (float(ofi_z or 0) / 2.0)
        if abs(score) > 0.2:
            out["vote"] = "LONG" if score > 0 else "SHORT"
            out["conf"] = round(min(1.0, abs(score)), 3)
    except Exception:
        pass
    return out


# ── the packaged snapshot + shadow-claim recording ────────────────────────────────

LANES = ("venue_leadlag", "psych_ofi", "funding_extreme", "mtf_agree")


def snapshot(symbol: str, segment: str = "futures", *,
             include_network: bool = True) -> dict:
    """All D4 features for one symbol — the meta-labeler's feature block. Feather
    lanes always run; network lanes (pool tickers, book read) only when asked."""
    snap = {"symbol": symbol, "segment": segment, "ts": time.time(),
            "funding_extreme": funding_extreme(symbol),
            "mtf_agree": mtf_agree(symbol, segment)}
    if include_network:
        snap["venue_leadlag"] = venue_gap(symbol)
        snap["psych_ofi"] = psych_ofi(symbol, segment)
    else:
        snap["venue_leadlag"] = {"vote": None}
        snap["psych_ofi"] = {"vote": None}
    return snap


def record_claims(symbols: list[str], segment: str = "futures",
                  budget_s: float = 20.0, *, include_network: bool = True) -> dict:
    """Shadow league round: compute each lane's vote for each candidate and record
    every non-None vote as a Truth-Ledger claim under the lane's own source name.
    Returns {"symbols": n, "claims": n, "by_lane": {...}} for the loop log."""
    rep = {"symbols": 0, "claims": 0, "by_lane": {}}
    if not _enabled() or not symbols:
        return rep
    t0 = time.monotonic()
    try:
        from trading.direction import truth_ledger
        from trading.direction.regime import classify
        for sym in symbols:
            if time.monotonic() - t0 > budget_s:
                break
            rep["symbols"] += 1
            snap = snapshot(sym, segment, include_network=include_network)
            regime = classify(sym, segment).get("regime")
            for lane in LANES:
                vote = (snap.get(lane) or {}).get("vote")
                if vote not in ("LONG", "SHORT"):
                    continue
                if truth_ledger.record(symbol=sym, market="CRYPTO",
                                       segment=segment, direction=vote,
                                       source=lane, regime=regime,
                                       confidence=(snap.get(lane) or {}).get("conf")):
                    rep["claims"] += 1
                    rep["by_lane"][lane] = rep["by_lane"].get(lane, 0) + 1
    except Exception:
        pass
    return rep
