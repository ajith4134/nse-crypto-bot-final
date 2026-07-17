"""trading/direction/vp_events.py — opening-range value-area events as MEASURED direction sources.

The owner's 2026-07-17 "first candle value" video (research/video/vp-first-candle-value/):
profile the first N minutes of a session, then play the two auction events at the value-area
edges — TRAP (close beyond VAH/VAL then back inside → fade, stop at the excursion extreme,
target the far edge) and ACCEPTANCE (holds beyond, pull back to the edge → continuation,
trail candle-by-candle). The engine primitives live in trading.broker_sense.volume_profile
(opening_range_profile + value_area_events); this module owns the CRYPTO wiring:

  • session anchors — crypto is 24/7, so "the open" is re-anchored to the session starts that
    actually structure its intraday volume: the UTC day open (00:00) and the US cash open
    (13:30 UTC). Each anchor is its own ledger source (vp_trap:utc / vp_trap:us / vp_accept:*)
    because their edges need not match and pooled stats would hide that.
  • level cache — the mirror keeps only 240 one-minute bars (~4h), so VAH/VAL are computed
    while the window is still in RAM/fetchable and CACHED per (symbol, anchor) in the state
    dir; late in the session the cached levels keep the grammar alive. No cache + no data →
    honest abstain, never a fabricated level.
  • volume-first, TPO degrade — profiles prefer real traded volume (the eyes' captured klines,
    else one ccxt 1m fetch when UI_ONLY allows); mark-price mirror bars degrade to a TPO
    profile with basis recorded.

Sources start UNPROVEN: learned_direction gives them ~0 weight until the truth ledger scores
n≥LEARNED_DIR_MIN_N of their calls (CONVENTIONS §16 — direction is earned, never assumed).
Never raises; every public function fail-opens to [] / None. VP_OR_SOURCE=0 disables.
"""
from __future__ import annotations

import os
import time

_LEVELS_FILE = "vp_or_levels.json"          # {"SYM|anchor_epoch": {vah,val,poc,basis,...}}
_LEVELS_MAX_AGE_S = 2 * 86_400              # prune cached sessions older than 2 days
_EVENT_TF_S = 300                           # the grammar walks 5m bars (the video's M5)


def _flag(name: str, default: str = "1") -> bool:
    return os.environ.get(name, default).strip().lower() in ("1", "true", "yes", "on")


def enabled() -> bool:
    return _flag("VP_OR_SOURCE")


def _minutes() -> int:
    try:
        return max(5, int(os.environ.get("VP_OR_MINUTES", "15")))
    except (TypeError, ValueError):
        return 15


def _flat(symbol: str) -> str:
    return (symbol or "").upper().split(":")[0].replace("/", "")


# ── session anchors ──────────────────────────────────────────────────────────────────
def anchors(now: float | None = None) -> list[tuple[str, int]]:
    """[(kind, anchor_epoch)] for the CURRENT session of each anchor family, newest first.
    kind ∈ {utc, us}: the UTC day open and the US cash open (13:30 UTC) — the two session
    starts with documented intraday-volume structure for crypto."""
    t = time.time() if now is None else float(now)
    day0 = int(t // 86_400) * 86_400
    out = [("utc", day0)]
    us = day0 + 13 * 3600 + 1800                      # 13:30 UTC today
    if t >= us:
        out.append(("us", us))
    else:                                             # before today's US open → yesterday's
        out.append(("us", us - 86_400))
    out.sort(key=lambda kv: kv[1], reverse=True)
    return out


# ── candles (volume-first, honest degrade) ───────────────────────────────────────────
def _volume_candles_1m(symbol: str, since_epoch: int, minutes: int) -> list | None:
    """1m bars WITH real volume covering [since, since+minutes): the eyes' captured klines
    first (zero network), else one ccxt fetch when UI_ONLY_DATA allows. None on miss."""
    try:
        from trading.broker_sense import ui_data
        rows = ui_data.ui_ohlcv(symbol, timeframe="1m", limit=1500)
        if rows:
            win = [r for r in rows
                   if since_epoch * 1000 <= int(r[0]) < (since_epoch + minutes * 60) * 1000]
            if len(win) >= minutes - 2:
                return win
        if ui_data.enabled():
            return None                               # UI-only: no API fallback (honest miss)
    except Exception:
        pass
    try:                                              # one bounded ccxt request per cache miss
        from trading.broker_sense.app_school import _ccxt_exchange
        flat = _flat(symbol)
        ccxt_sym = symbol if "/" in str(symbol) else (
            f"{flat[:-4]}/USDT:USDT" if flat.endswith("USDT") else flat)
        ex = _ccxt_exchange("futures")
        return ex.fetch_ohlcv(ccxt_sym, timeframe="1m",
                              since=since_epoch * 1000, limit=minutes + 2)
    except Exception:
        return None


def _mirror_candles(symbol: str, tf_s: int, n: int) -> list:
    try:
        from trading.broker_sense.binance_stream import get_mirror
        return get_mirror().candles(_flat(symbol), tf_s, n) or []
    except Exception:
        return []


# ── level cache ──────────────────────────────────────────────────────────────────────
def _levels(symbol: str, kind: str, anchor_epoch: int) -> dict | None:
    """Cached-or-computed opening-range VAH/VAL for (symbol, anchor). Computes from volume
    candles when possible, TPO mirror bars otherwise; caches good levels for the session."""
    from trading import state
    key = f"{_flat(symbol)}|{anchor_epoch}"
    cached = (state.load_json(_LEVELS_FILE, {}) or {}).get(key)
    if isinstance(cached, dict) and cached.get("available"):
        return cached
    minutes = _minutes()
    from trading.broker_sense import volume_profile as _vp
    rows = _volume_candles_1m(symbol, anchor_epoch, minutes)
    if not rows:                                       # TPO degrade off the in-RAM mirror
        rows = _mirror_candles(symbol, 60, 240)
    prof = _vp.opening_range_profile(rows or [], anchor_epoch, minutes)
    if not prof.get("available"):
        return None
    prof = {k: v for k, v in prof.items() if k != "hist"}    # keep the cache row small
    prof["kind"] = kind

    def _upd(d: dict) -> dict:
        d = d or {}
        d[key] = prof
        cutoff = time.time() - _LEVELS_MAX_AGE_S
        return {k: v for k, v in d.items()
                if (v or {}).get("anchor_ts", 0) >= cutoff}
    try:
        state.mutate_json(_LEVELS_FILE, _upd, default={})
    except Exception:
        pass
    return prof


# ── the readings ─────────────────────────────────────────────────────────────────────
def readings(symbol: str, *, segment: str = "futures", regime: str | None = None,
             record: bool = True) -> list[tuple[str, float]]:
    """Consult the OR value-area grammar for every anchor → [(source, p_up)] readings, each
    recorded to the Truth Ledger. Also stashes the event's structure plan (stop/target/trail)
    on `readings.last_plans[source]` for callers that want structure-based risk. Never raises."""
    readings.last_plans = {}
    if not enabled():
        return []
    out: list[tuple[str, float]] = []
    try:
        from trading.broker_sense import volume_profile as _vp
        for kind, anchor in anchors():
            va = _levels(symbol, kind, anchor)
            if not va:
                continue
            end_ts = va.get("end_ts") or (anchor + _minutes() * 60)
            bars = [b for b in _mirror_candles(symbol, _EVENT_TF_S, 240)
                    if int(b[0]) >= int(end_ts)]
            if len(bars) < 2:
                continue
            ev = _vp.value_area_events(bars, va)
            if not ev.get("event"):
                continue
            src = f"vp_{'trap' if ev['event'] == 'trap' else 'accept'}:{kind}"
            p = 0.5 + (0.5 * ev.get("strength", 0.55)) * (1 if ev["side"] == "long" else -1)
            p = min(0.98, max(0.02, round(p, 4)))
            out.append((src, p))
            readings.last_plans[src] = {
                "side": ev["side"], "level": ev.get("level"), "stop": ev.get("stop"),
                "target": ev.get("target"), "trail": ev.get("trail"),
                "basis": va.get("basis"), "anchor": kind, "detail": ev.get("detail")}
            if record:
                try:
                    from trading.direction import truth_ledger as _tl
                    _tl.record(symbol=symbol, market="CRYPTO", segment=segment or "futures",
                               direction=("LONG" if ev["side"] == "long" else "SHORT"),
                               source=src, confidence=abs(p - 0.5) + 0.5, regime=regime)
                except Exception:
                    pass
    except Exception:
        return out
    return out


readings.last_plans = {}


def status() -> dict:
    """Honest snapshot for the dashboard/verify: cache size + anchors currently live."""
    try:
        from trading import state
        cache = state.load_json(_LEVELS_FILE, {}) or {}
    except Exception:
        cache = {}
    return {"enabled": enabled(), "minutes": _minutes(),
            "anchors": [k for k, _ in anchors()], "cached_levels": len(cache)}
