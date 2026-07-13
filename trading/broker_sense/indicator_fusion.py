"""trading/broker_sense/indicator_fusion.py — ultra-advanced multi-timeframe indicator fusion.

The owner's ask: don't just *compute* MA/EMA/Bollinger/SAR/Supertrend/ADX/RSI — USE them to
open trades the way a professional desk does. Design doc: research/broker-sense-indicator-fusion.md.

The stack (each layer grounded in SOTA, see the research note):
  1. FULL indicator suite per timeframe from raw candles (SMA/EMA ribbon, MACD, Supertrend,
     Parabolic SAR, ADX/DMI, ATR, Bollinger, RSI, Stochastic-RSI).
  2. REGIME gate — ADX/DMI + Bollinger bandwidth decide trending vs ranging; in a trend we take
     trend-following confluence, in a range we require band-edge reversion or abstain.
  3. MULTI-TF CONFLUENCE — horizon-weighted vote across 1m/5m/15m/1h/4h/1d; the highest TF is a
     directional VETO (never long when the 1d trend is down).
  4. VISION fuse — the candlestick-pattern read (chart_vision/CNN) is an independent lens; the
     numeric confluence and the vision must broadly agree for high conviction.
  5. META-LABEL — the fusion proposes the SIDE; the project's conformal UQ gate (trading/uq)
     decides whether to ACT + how much to size (López de Prado meta-labeling).
  6. TRIPLE-BARRIER geometry — ATR-scaled entry/stop/target/time barriers → a concrete order plan
     that is also the label the meta-model learns from next time.

Pure-Python + offline-testable: the indicator math takes plain OHLCV lists and never touches the
network; only `fuse()` fetches candles (reusing data_failsafe/ccxt). Honest by construction —
every field derives from real candles + real vision; missing data yields 'unavailable', never a
fabricated number.
"""
from __future__ import annotations

import os

import math
import time

from trading.broker_sense import data_failsafe
from trading.broker_sense.fast_candles import _clamp, _ema, _rsi

# horizon weights — higher timeframes set the BIAS, lower ones the TIMING (research §3)
_TF_WEIGHT = {"1m": 0.6, "3m": 0.7, "5m": 0.8, "15m": 1.0, "30m": 1.2,
              "1h": 1.3, "2h": 1.45, "4h": 1.6, "6h": 1.7, "1d": 2.0}
_BIAS_TFS = ("1d", "4h")          # the veto timeframes (highest available acts as bias)
_TRIGGER_TFS = ("15m", "5m", "1h")  # first available is the entry-timing TF for ATR geometry
_BARS = 220                        # enough for EMA200 / ADX / Supertrend warm-up


# ── column helpers ──────────────────────────────────────────────────────────────────
def _ohlc(rows: list):
    """Split OHLCV rows [ts,o,h,l,c,v] into (opens, highs, lows, closes). Robust to short/None."""
    o = h = l = c = None
    try:
        o = [float(r[1]) for r in rows if r and len(r) >= 5]
        h = [float(r[2]) for r in rows if r and len(r) >= 5]
        l = [float(r[3]) for r in rows if r and len(r) >= 5]
        c = [float(r[4]) for r in rows if r and len(r) >= 5]
    except (TypeError, ValueError, IndexError):
        return [], [], [], []
    return o, h, l, c


def _sma(vals: list[float], n: int) -> float:
    if len(vals) < n or n <= 0:
        return sum(vals) / len(vals) if vals else 0.0
    return sum(vals[-n:]) / n


def _ema_series(vals: list[float], n: int) -> list[float]:
    """Full EMA series (needed by MACD/Supertrend), not just the last value."""
    if not vals:
        return []
    k = 2.0 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def _true_ranges(h, l, c) -> list[float]:
    tr = []
    for i in range(1, len(c)):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return tr


def _wilder(vals: list[float], n: int) -> float:
    """Wilder's smoothed average (used by ATR/ADX). Falls back to SMA when short."""
    if len(vals) < n or n <= 0:
        return sum(vals) / len(vals) if vals else 0.0
    a = sum(vals[:n]) / n
    for v in vals[n:]:
        a = (a * (n - 1) + v) / n
    return a


def _atr(h, l, c, n: int = 14) -> float:
    tr = _true_ranges(h, l, c)
    return _wilder(tr, n) if tr else 0.0


def _adx(h, l, c, n: int = 14) -> tuple[float, float, float]:
    """Return (ADX, +DI, −DI). ADX is trend STRENGTH; the DIs give direction."""
    if len(c) < n + 2:
        return 0.0, 0.0, 0.0
    plus_dm, minus_dm, tr = [], [], []
    for i in range(1, len(c)):
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        plus_dm.append(up if (up > dn and up > 0) else 0.0)
        minus_dm.append(dn if (dn > up and dn > 0) else 0.0)
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    atr = _wilder(tr, n) or 1e-9
    pdi = 100.0 * _wilder(plus_dm, n) / atr
    mdi = 100.0 * _wilder(minus_dm, n) / atr
    denom = (pdi + mdi) or 1e-9
    dx = 100.0 * abs(pdi - mdi) / denom
    # ADX = smoothed DX; approximate with the DX of the smoothed DIs (one-pass, stable enough)
    return round(dx, 2), round(pdi, 2), round(mdi, 2)


def _supertrend(h, l, c, n: int = 10, mult: float = 3.0) -> tuple[int, float]:
    """Return (dir, band). dir=+1 uptrend (price above the line), −1 downtrend."""
    if len(c) < n + 2:
        return 0, 0.0
    tr = _true_ranges(h, l, c)
    atr = _wilder(tr, n)
    hl2 = (h[-1] + l[-1]) / 2.0
    upper, lower = hl2 + mult * atr, hl2 - mult * atr
    # simple final-band rule on the last bar (full recursion is overkill for a per-cycle read)
    if c[-1] > upper:
        return 1, lower
    if c[-1] < lower:
        return -1, upper
    # inside the bands → carry the sign of the faster EMA slope
    ef = _ema(c[-30:], 9)
    return (1, lower) if c[-1] >= ef else (-1, upper)


def _parabolic_sar(h, l, c, af0: float = 0.02, af_max: float = 0.2) -> tuple[int, float]:
    """Return (dir, sar). dir=+1 if price is above SAR (long), −1 below."""
    if len(c) < 5:
        return 0, 0.0
    up = c[1] >= c[0]
    sar = l[0] if up else h[0]
    ep = h[0] if up else l[0]
    af = af0
    for i in range(1, len(c)):
        sar = sar + af * (ep - sar)
        if up:
            if l[i] < sar:                      # flip to down
                up, sar, ep, af = False, ep, l[i], af0
            else:
                if h[i] > ep:
                    ep, af = h[i], min(af + af0, af_max)
        else:
            if h[i] > sar:                      # flip to up
                up, sar, ep, af = True, ep, h[i], af0
            else:
                if l[i] < ep:
                    ep, af = l[i], min(af + af0, af_max)
    return (1 if up else -1), round(sar, 8)


def _macd(c: list[float]) -> tuple[float, float, float]:
    """Return (macd_line, signal, hist)."""
    if len(c) < 35:
        return 0.0, 0.0, 0.0
    ef, es = _ema_series(c, 12), _ema_series(c, 26)
    line = [a - b for a, b in zip(ef, es)]
    sig = _ema_series(line, 9)
    return round(line[-1], 8), round(sig[-1], 8), round(line[-1] - sig[-1], 8)


def _bollinger(c: list[float], n: int = 20, k: float = 2.0) -> tuple[float, float, float]:
    """Return (%b in [0,1]+, bandwidth, mid). %b<0/>1 means outside the bands."""
    if len(c) < n:
        return 0.5, 0.0, (c[-1] if c else 0.0)
    window = c[-n:]
    mid = sum(window) / n
    var = sum((x - mid) ** 2 for x in window) / n
    sd = math.sqrt(var)
    upper, lower = mid + k * sd, mid - k * sd
    width = (upper - lower) / mid if mid else 0.0
    pctb = (c[-1] - lower) / (upper - lower) if upper != lower else 0.5
    return round(pctb, 4), round(width, 5), round(mid, 8)


def _stoch_rsi(c: list[float], n: int = 14) -> float:
    """Stochastic-RSI in [0,1] over the last `n` RSI values (momentum position)."""
    if len(c) < n + 15:
        return 0.5
    rsis = [_rsi(c[: i + 1], n) for i in range(len(c) - n, len(c))]
    lo, hi = min(rsis), max(rsis)
    return round((rsis[-1] - lo) / (hi - lo), 4) if hi != lo else 0.5


# ── per-timeframe indicator read + regime-gated vote ─────────────────────────────────
def indicators_from_ohlcv(rows: list) -> dict:
    """Full indicator suite + a regime-gated vote in [-1,1] for ONE timeframe.
    Returns {'available': False} when there aren't enough candles to be honest."""
    o, h, l, c = _ohlc(rows)
    if len(c) < 30:
        return {"available": False}
    close = c[-1]
    ema9, ema21, ema50 = _ema(c[-60:], 9), _ema(c[-60:], 21), _ema(c[-120:], 50)
    sma200 = _sma(c, 200) if len(c) >= 200 else None
    rsi = _rsi(c, 14)
    srsi = _stoch_rsi(c)
    macd_line, macd_sig, macd_hist = _macd(c)
    st_dir, st_band = _supertrend(h, l, c)
    sar_dir, sar = _parabolic_sar(h, l, c)
    adx, pdi, mdi = _adx(h, l, c)
    atr = _atr(h, l, c)
    pctb, bb_width, bb_mid = _bollinger(c)

    # regime: ADX>25 trend, <18 range, else transitional; Bollinger squeeze reinforces "range"
    squeeze = bb_width < 0.02
    if adx >= 25 and not squeeze:
        regime = "trend"
    elif adx < 18 or squeeze:
        regime = "range"
    else:
        regime = "transition"

    # per-indicator votes in {-1,0,1}
    ribbon = 1 if ema9 > ema21 > ema50 else -1 if ema9 < ema21 < ema50 else 0
    long_bias = 0 if sma200 is None else (1 if close > sma200 else -1)
    macd_v = 1 if macd_hist > 0 and macd_line > macd_sig else -1 if macd_hist < 0 and macd_line < macd_sig else 0
    di_v = 1 if pdi > mdi else -1 if mdi > pdi else 0
    rsi_v = 1 if 50 < rsi < 78 else -1 if 22 < rsi < 50 else 0
    revert_v = 1 if pctb < 0.05 else -1 if pctb > 0.95 else 0   # band-edge mean reversion

    trend_block = [ribbon, st_dir, sar_dir, macd_v, di_v, long_bias]
    if regime == "trend":
        num = sum(trend_block) + 0.5 * rsi_v
        vote = _clamp(num / (len(trend_block) + 0.5), -1.0, 1.0)
    elif regime == "range":
        # in a range, fade the extremes; trend indicators heavily discounted
        vote = _clamp(0.7 * revert_v + 0.15 * sum(trend_block) / len(trend_block), -1.0, 1.0)
    else:                                          # transition — half conviction, trend-leaning
        vote = _clamp(0.5 * sum(trend_block) / len(trend_block) + 0.2 * rsi_v, -1.0, 1.0)

    return {
        "available": True, "regime": regime, "vote": round(vote, 4), "close": close,
        "ema": {"e9": round(ema9, 8), "e21": round(ema21, 8), "e50": round(ema50, 8),
                "sma200": round(sma200, 8) if sma200 is not None else None},
        "supertrend": {"dir": st_dir, "band": st_band},
        "sar": {"dir": sar_dir, "value": sar},
        "macd": {"line": macd_line, "signal": macd_sig, "hist": macd_hist},
        "adx": {"adx": adx, "plus_di": pdi, "minus_di": mdi},
        "rsi": round(rsi, 2), "stoch_rsi": srsi,
        "bollinger": {"pct_b": pctb, "width": bb_width, "mid": bb_mid, "squeeze": squeeze},
        "atr": round(atr, 8),
    }


# ── multi-timeframe confluence + vision fuse + meta-label + barriers ──────────────────
def _fetch(sym: str, market: str, tf: str, bars: int = _BARS) -> list | None:
    """Candles for indicators. UI_ONLY_DATA=1 (owner 2026-07-07): the eyes' captured
    app payloads are the ONLY source — an honest None + evidence-lane data-failure
    record when the eyes haven't seen this symbol/tf (never a silent API fallback).
    Flag off: ccxt direct (fast) with data_failsafe fallback, as before."""
    from trading.broker_sense import ui_data
    if ui_data.enabled():
        rows = ui_data.ui_ohlcv(sym, timeframe=tf, limit=bars)
        if rows is None:
            try:
                from trading import evidence
                evidence.record_data_failure("ui_data",
                                             f"no fresh UI candles for {sym} {tf}")
            except Exception:
                pass
        return rows
    if market == "crypto":
        try:
            from trading.broker_sense.app_school import _ccxt_exchange
            ex = _ccxt_exchange("futures" if ":" in sym else "spot")
            rows = ex.fetch_ohlcv(sym, timeframe=tf, limit=bars)
            if rows:
                return rows
        except Exception:
            pass
    try:
        return data_failsafe.ohlcv(sym, market, timeframe=tf, limit=bars)
    except Exception:
        return None


def _meta_label(confluence: float, direction: str, market: str, symbol: str) -> dict:
    """López de Prado meta-label: the fusion picks the side; the conformal UQ gate decides whether
    to ACT + size. Best-effort — a transparent fallback rule if the UQ model isn't fitted yet."""
    try:
        from trading.uq.conformal import get_uq
        a = get_uq().assess(confidence=abs(confluence), direction=direction.upper(),
                            market=(market or "crypto").upper(), symbol=symbol)
        return {"act": not a.get("abstain", False), "size_mult": round(a.get("size_scale", 1.0), 3),
                "p_up": a.get("p_up"), "reason": a.get("reason") or "uq gate", "source": "uq"}
    except Exception as e:
        act = abs(confluence) >= 0.34
        return {"act": act, "size_mult": round(min(1.0, abs(confluence) * 1.5), 3),
                "p_up": round((1 + confluence) / 2, 4),
                "reason": ("confluence ok" if act else "confluence too weak"),
                "source": f"fallback ({str(e)[:40]})"}


def _barriers(direction: str, price: float, atr: float,
              k_stop: float = 1.5, k_tp: float = 2.5, time_bars: int = 12) -> dict:
    """ATR-scaled triple-barrier order plan (entry/stop/target/time). The labels the meta-model
    learns from next cycle. Neutral direction → no plan."""
    if not price or not atr or direction == "neutral":
        return {"entry": price or None, "stop": None, "target": None, "rr": None,
                "atr": round(atr, 8), "time_bars": time_bars}
    sign = 1 if direction == "long" else -1
    stop = price - sign * k_stop * atr
    target = price + sign * k_tp * atr
    return {"entry": round(price, 8), "stop": round(stop, 8), "target": round(target, 8),
            "rr": round(k_tp / k_stop, 2), "atr": round(atr, 8), "time_bars": time_bars}


_ONCHAIN_CACHE: dict = {"ts": 0.0, "snap": None}


def _onchain_cached(ttl: float = 300.0) -> dict | None:
    """On-chain snapshot (altdata.onchain), cached ttl seconds — the fetch hits external free APIs,
    far too slow to run per fuse() call. Market-wide, so one snapshot serves every symbol."""
    if time.time() - _ONCHAIN_CACHE["ts"] > ttl:
        try:
            from trading.altdata.onchain import OnChainAltData
            _ONCHAIN_CACHE["snap"] = OnChainAltData().snapshot()
        except Exception:
            _ONCHAIN_CACHE["snap"] = None
        _ONCHAIN_CACHE["ts"] = time.time()
    return _ONCHAIN_CACHE["snap"]


_FUSE_CACHE: dict = {}      # (symbol, market, tfs, vision_sig) -> (bar_epoch, result)


def _vision_sig(vision) -> tuple:
    """Cheap fingerprint of the vision lens so a changed chart read misses the cache (correct)
    but a stable one within the bar hits it. None/empty → ()."""
    if not isinstance(vision, dict):
        return ()
    out = []
    for tf, v in sorted(vision.items()):
        if isinstance(v, dict):
            out.append((tf, round(float(v.get("p_up", 0.5) or 0.5), 3), v.get("direction")))
    return tuple(out)


def fuse(symbol: str, market: str = "crypto",
         timeframes=("1m", "5m", "15m", "1h", "4h", "1d"),
         vision: dict | None = None) -> dict:
    """Per-5m-bar-memoized wrapper over the real fusion. fuse() reads bar-stable OHLCV across
    timeframes (the funnel VERIFY hog — measured ~6s/candidate live) so within a bar the result is
    deterministic for a given vision lens; consecutive funnel cycles (every ~1-2 min) reuse it
    instead of re-fetching every timeframe. Cache by (symbol, market, timeframes, vision-print) for
    the bar. FUSE_MEMO=0 disables; FUSE_MEMO_BAR_S sets the bar seconds (default 300). Unavailable
    results are never cached (so a transient data miss retries next cycle)."""
    if os.environ.get("FUSE_MEMO", "1") not in ("1", "true", "TRUE", "yes", "on"):
        return _fuse_uncached(symbol, market, timeframes, vision)
    try:
        bar = int(os.environ.get("FUSE_MEMO_BAR_S", "300"))
    except Exception:
        bar = 300
    epoch = int(time.time() // max(1, bar))
    key = (symbol, market, tuple(timeframes), _vision_sig(vision))
    hit = _FUSE_CACHE.get(key)
    if hit is not None and hit[0] == epoch:
        return hit[1]
    result = _fuse_uncached(symbol, market, timeframes, vision)
    if isinstance(result, dict) and result.get("available"):
        if len(_FUSE_CACHE) > 6000:               # bounded — clear rather than grow unbounded
            _FUSE_CACHE.clear()
        _FUSE_CACHE[key] = (epoch, result)
    return result


def _fuse_uncached(symbol: str, market: str = "crypto",
                   timeframes=("1m", "5m", "15m", "1h", "4h", "1d"),
                   vision: dict | None = None) -> dict:
    """THE decision object for one symbol (research §"Final decision object").

    vision: optional {tf: {p_up, direction}} from chart_vision/fast_candles — the independent
    candlestick-pattern lens. Fused with the numeric confluence.
    Returns a dict safe to drop into decision_snapshot['app_signals']['indicator_fusion'];
    direction='neutral' + p_up=0.5 when data is unavailable (never fabricated)."""
    from concurrent.futures import ThreadPoolExecutor
    per_tf: dict[str, dict] = {}

    def _one(tf):
        rows = _fetch(symbol, market, tf)          # I/O-bound → run the TFs in parallel
        return tf, (indicators_from_ohlcv(rows) if rows else {"available": False})

    with ThreadPoolExecutor(max_workers=min(6, len(timeframes) or 1)) as pool:
        for tf, ind in pool.map(_one, timeframes):
            per_tf[tf] = ind

    avail = {tf: d for tf, d in per_tf.items() if d.get("available")}
    if not avail:
        return {"symbol": symbol, "available": False, "direction": "neutral", "p_up": 0.5,
                "confluence": 0.0, "regime": "unknown", "source": "unavailable",
                "per_tf": {tf: {"available": False} for tf in timeframes}, "ts": time.time()}

    # 3 ── horizon-weighted confluence
    wsum = sum(_TF_WEIGHT.get(tf, 1.0) for tf in avail)
    confluence = sum(_TF_WEIGHT.get(tf, 1.0) * d["vote"] for tf, d in avail.items()) / (wsum or 1)

    # higher-TF VETO: if the bias TF's regime is a clear trend AGAINST the confluence, clamp it
    bias_tf = next((tf for tf in _BIAS_TFS if tf in avail), None)
    veto = None
    if bias_tf:
        bv = avail[bias_tf]["vote"]
        if bv * confluence < 0 and abs(bv) >= 0.4:      # bias opposes the crowd → cut conviction
            confluence *= 0.35
            veto = f"{bias_tf} bias {bv:+.2f} opposes"

    # regime = the bias TF's regime (falls back to the majority)
    regime = avail[bias_tf]["regime"] if bias_tf else max(
        ("trend", "range", "transition"),
        key=lambda r: sum(1 for d in avail.values() if d["regime"] == r))

    # 4 ── vision fuse (independent lens). vision p_up∈[0,1] → [-1,1]; blend 65% numeric / 35% vision
    if vision is None:                             # no live read passed → use the async deep VLM read
        try:                                       # (vision_worker: full qwen7b chart read, cached)
            from trading.broker_sense import vision_worker
            vision = vision_worker.deep_vision(symbol, timeframes=timeframes)
        except Exception:
            vision = None
    vision_dir = None
    if vision:
        vs = [(_TF_WEIGHT.get(tf, 1.0), (v.get("p_up", 0.5) - 0.5) * 2.0)
              for tf, v in vision.items() if isinstance(v, dict) and v.get("source") != "unavailable"]
        if vs:
            vw = sum(w for w, _ in vs) or 1
            vision_dir = sum(w * x for w, x in vs) / vw
    # Item 3 (adopt-plan, 2026-07-13): vision LLMs read charts at ~coin-flip for DIRECTION and
    # ~0 for patterns (independent 4-model benchmark incl. Opus 4.7, and our own truth ledger).
    # So a chart read NO LONGER casts a hardcoded direction vote by default — it stays a CONTEXT
    # lens (recorded for display + as a truth-ledger source that learned_direction weights ONLY
    # to its MEASURED reliability). Set VISION_PREDICTS_DIRECTION=1 to restore the old 35% blend.
    _vision_votes = os.getenv("VISION_PREDICTS_DIRECTION", "0") in ("1", "true", "TRUE", "yes", "on")
    if vision_dir is not None:
        vision_agree = (vision_dir * confluence) >= 0    # still surfaced (display/telemetry)
        if _vision_votes:
            blended = 0.65 * confluence + 0.35 * vision_dir
            if not vision_agree:
                blended *= 0.6                           # disagreement → shrink conviction
            confluence = _clamp(blended, -1.0, 1.0)
    else:
        vision_agree = None

    # 4b ── Binance order-flow tilt (compute-offload: positioning/flow COMPUTED BY BINANCE, read not
    # derived — long/short ratios, taker buy/sell, funding, liquidation skew). Crypto only; a BOUNDED
    # ±0.12 nudge so it informs the TA confluence without dominating it. Cheap: mirror=RAM,
    # /futures/data is TTL-cached, and only shortlisted symbols ever reach fuse(). Never raises.
    order_flow = None
    if market == "crypto":
        try:
            from trading.broker_sense import binance_orderflow as _of
            if _of.enabled():
                # WIDE/unlimited pass → mirror-only order-flow (no per-symbol /futures/data REST),
                # so a 600-symbol screen stays fast and never trips Binance's 1000/5min rate limit.
                _cheap = os.getenv("CRYPTO_UNLIMITED_OPENS", "1") not in ("0", "false", "off")
                order_flow = _of.signal(symbol, cheap=_cheap)
                t = order_flow.get("tilt")
                if t is not None:
                    confluence = _clamp(confluence + 0.12 * t, -1.0, 1.0)
                # accumulate the per-bar REAL order-flow HISTORY (orderflow_store) so the direction
                # equation trains on true order-flow, not just OHLCV proxies (COVERAGE-AUDIT gap B).
                if not _cheap:                        # only the deep (non-mirror) read has the fields
                    try:
                        from trading.broker_sense import orderflow_store
                        orderflow_store.snapshot(symbol, market)
                    except Exception:
                        pass
        except Exception:
            order_flow = None

    # 4c ── Binance-native event catalyst (new/upcoming listing). Informational — a listing is not
    # inherently long/short, so it does NOT nudge direction; it rides in the snapshot for the brain
    # to size/prioritise on, and the screener boosts discovery of fresh listings separately.
    catalyst = None
    if market == "crypto":
        try:
            from trading.broker_sense import binance_catalysts as _bc
            if _bc.enabled():
                catalyst = _bc.catalyst(symbol)
        except Exception:
            catalyst = None

    # 4d ── Binance sector rotation (Binance-classified sectors, mirror-pushed prices → sector momentum).
    # A small ±0.08 nudge: when the symbol's sector is broadly moving, lean with it. Crypto only, guarded.
    sectors = None
    if market == "crypto":
        try:
            from trading.broker_sense import binance_sectors as _sec
            if _sec.enabled():
                sectors = _sec.sector_signal(symbol)
                t = sectors.get("tilt")
                if t is not None:
                    confluence = _clamp(confluence + 0.08 * t, -1.0, 1.0)
        except Exception:
            sectors = None

    # 4e ── Binance's built-in AI Select (its own recommended-assets endpoint). Informational +
    # a tiny discovery lean: a top-ranked AI pick gets a small long tilt (Binance surfaces it as an
    # opportunity). Crypto only, guarded. Screener also boosts AI-picks into the candidate pool.
    ai_select = None
    if market == "crypto":
        try:
            from trading.broker_sense import binance_ai_select as _ai
            if _ai.enabled():
                ai_select = _ai.is_ai_selected(symbol)
                if ai_select.get("ai_selected") and (ai_select.get("ai_rank") or 99) <= 5:
                    confluence = _clamp(confluence + 0.05, -1.0, 1.0)
        except Exception:
            ai_select = None

    # 4f ── Volume Profile / Value Area lens (owner's champions-chart-strategy video, 2026-07-11).
    # EVERY segment (not crypto-only): daily-session value area + migration + failed-auction +
    # absorption → a bounded ±0.15 tilt (failed-auction reversion is a strong, evidence-based edge,
    # so it earns a slightly larger budget than sector/ai; still can't dominate the TA confluence).
    # One dedicated fetch on a stable TF (needs ~200 bars for daily sessions); guarded, never raises.
    vp_profile = None
    try:
        from trading.broker_sense import volume_profile as _vp
        vp_tf = next((t for t in ("15m", "1h", "5m") if t in timeframes), next(iter(avail)))
        vp_rows = _fetch(symbol, market, vp_tf, bars=240)
        if vp_rows:
            vp_profile = _vp.features(vp_rows, market)
            t = vp_profile.get("tilt") if vp_profile.get("available") else None
            if t is not None:
                confluence = _clamp(confluence + 0.15 * t, -1.0, 1.0)
    except Exception:
        vp_profile = None

    # 4g ── Lane C: YOLOv8 chart-pattern detection (vendor/ChartScanAI), cached from the eyes' REAL
    # app screenshot (chart_vision). A bounded ±0.10 tilt — an independent pattern lens, distinct
    # from the CNN (Lane A) + VLM (Lane B). Only contributes when a fresh real-screenshot read exists.
    yolo = None
    try:
        from trading.broker_sense import chart_yolo
        yolo = chart_yolo.cached(symbol)
        if yolo and yolo.get("score") is not None:
            confluence = _clamp(confluence + 0.10 * float(yolo["score"]), -1.0, 1.0)
    except Exception:
        yolo = None

    # 4h ── the DISCOVERED DIRECTION EQUATION (quest P4): the CPCV-validated symbolic-regression
    # equation, evaluated live, Mirror-Gated (self-inverts if the Truth Ledger says it's become an
    # anti-signal) → a bounded ±0.15 tilt. Only contributes once an equation has been discovered +
    # validated for this market (direction_equations.json); otherwise silent. Reuses the vp_rows fetch.
    direction_eq = None
    try:
        if vp_rows:
            from trading.strategy import direction_equation_deploy as _deq
            direction_eq = _deq.equation_tilt(vp_rows, market, symbol=symbol, regime=regime)
            if direction_eq and direction_eq.get("tilt") is not None:
                confluence = _clamp(confluence + 0.15 * float(direction_eq["tilt"]), -1.0, 1.0)
    except Exception:
        direction_eq = None

    # 4i ── ON-CHAIN sentiment/flow regime (fear&greed + network + whale, altdata.onchain). Market-
    # wide risk-on/off ∈[-1,1] → a small ±0.06 tilt; TTL-cached (external fetch). Crypto only. This is
    # the LIVE on-chain lens (COVERAGE-AUDIT gap C); per-bar on-chain HISTORY for the equation bus
    # remains a documented data-plumbing task.
    onchain = None
    if market == "crypto":
        try:
            onchain = _onchain_cached()
            c = onchain.get("composite") if onchain and onchain.get("available") else None
            if c is not None:
                confluence = _clamp(confluence + 0.06 * float(c), -1.0, 1.0)
        except Exception:
            onchain = None

    p_up = round(_clamp((1 + confluence) / 2, 0.02, 0.98), 4)
    direction = "long" if p_up > 0.56 else "short" if p_up < 0.44 else "neutral"

    # 4j ── NEURON MEMORY lens (Brain Ultra Upgrade R22): consult the web of neurons for
    # this symbol/regime — past episodes, lessons, strategy notes — record the USE, and
    # ride the ids + action facets in the snapshot. NO confluence tilt yet: recall must
    # EARN a tilt with close-graded evidence first (freqtrade_ingest grades these ids on
    # trade close, so the evidence accumulates from day one). Guarded, never raises.
    neurons = None
    try:
        from trading.brain import brain_os as _bos       # OS-4: one kernel-routed surface
        neurons = _bos.consult(
            f"{symbol} {direction} {regime} {market}", domain="trading", k=3)
        if not neurons["ids"]:
            neurons = None
    except Exception:
        neurons = None

    # 6 ── triple-barrier geometry off the trigger TF's ATR
    trig_tf = next((tf for tf in _TRIGGER_TFS if tf in avail), next(iter(avail)))
    trig = avail[trig_tf]
    barriers = _barriers(direction, trig.get("close"), trig.get("atr", 0.0))
    # 6b ── VP after-entry management (owner's video): when a failed-auction drove this side, define
    # risk by STRUCTURE — target the value-area edge, stop beyond the swing — instead of a fixed ATR
    # multiple. Keeps the ATR plan as fallback; rides in the snapshot either way.
    try:
        fa = (vp_profile or {}).get("failed_auction", {}) if vp_profile else {}
        if vp_rows and direction != "neutral" and fa.get("signal") == direction:
            plan = _vp.order_plan(vp_rows, direction, market)
            if plan and plan.get("rr") and plan["rr"] >= 1.0:
                barriers = {**barriers, **plan, "time_bars": barriers.get("time_bars")}
    except Exception:
        pass

    # 5 ── meta-label (act / size)
    meta = _meta_label(confluence, direction, market, symbol)

    # 5b ── options IV/skew market regime (Binance-computed; market-wide, direction-neutral). Rides in
    # the snapshot as context AND trims size in a risk-off (high-IV + put-skew) tape. Cached ~120s.
    options_regime = None
    if market == "crypto":
        try:
            from trading.broker_sense import binance_options as _opt
            if _opt.enabled():
                options_regime = _opt.regime()
                ro = options_regime.get("risk_off")
                if ro is not None and ro > 0.5:              # defensive sizing when vol/fear is bid up
                    meta = {**meta, "size_mult": round(meta.get("size_mult", 1.0) * (1 - 0.3 * (ro - 0.5) / 0.5), 3)}
        except Exception:
            options_regime = None

    return {
        "symbol": symbol, "available": True, "source": "indicator_fusion",
        "direction": direction, "p_up": p_up, "confluence": round(confluence, 4),
        "regime": regime, "veto": veto, "vision_agree": vision_agree,
        "vision_dir": round(vision_dir, 4) if vision_dir is not None else None,
        "trigger_tf": trig_tf, "bias_tf": bias_tf,
        "barriers": barriers, "meta": meta, "order_flow": order_flow, "catalyst": catalyst,
        "sectors": sectors, "options_regime": options_regime, "ai_select": ai_select,
        "volume_profile": vp_profile, "chart_yolo": yolo, "direction_equation": direction_eq,
        "neurons": neurons,
        "onchain": onchain,
        "per_tf": {tf: ({"available": False} if not d.get("available") else
                        {"available": True, "vote": d["vote"], "regime": d["regime"], "rsi": d["rsi"],
                         "adx": d["adx"]["adx"], "supertrend": d["supertrend"]["dir"],
                         "sar": d["sar"]["dir"], "macd_hist": d["macd"]["hist"],
                         "pct_b": d["bollinger"]["pct_b"]})
                   for tf, d in per_tf.items()},
        "ts": time.time(),
    }
