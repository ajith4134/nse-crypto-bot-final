"""trading/direction/pullback.py — D3: pullback entries (goal Pillar 27).

Measured root cause this fixes: sub-15-minute holds were direction-correct only 34.9%
— the funnel enters AT the local extreme (the pump it just screened for) and the
immediate mean-reversion eats the trade. Instead of buying the spike, a verdict now
ARMS a pending entry; the executor only fires it once price has pulled back toward us
(k × ATR, or a percent fallback when no candles were in hand), so reversion becomes
the entry discount instead of the loss.

State machine per (segment|symbol), persisted cross-process in the state dir:
  arm(...)   → registers/refreshes an armed claim (idempotent; direction flip re-arms)
  sweep(...) → for every armed claim, one cheap cached quote decides:
                 triggered — price retraced ≥ the pullback distance → ENTER now
                 runaway   — price ran ≥ PULLBACK_RUNAWAY_ATR × dist in favor without
                             ever pulling back → the move is gone; drop honestly
                 expired   — older than PULLBACK_TTL_MIN → drop honestly
                 waiting   — stays armed
All drops/triggers are counted in the state file (the panel shows real funnel physics,
and "missed" runaways measure what patience costs — if they dominate, k self-tunes
down via review, not silently).

Levers: PULLBACK_ENTRY=0 disables (entries fire immediately as before),
PULLBACK_ATR (default 0.5 — fraction of ATR to wait for), PULLBACK_PCT (default 0.15
— percent fallback when the caller had no candles), PULLBACK_TTL_MIN (default 45),
PULLBACK_RUNAWAY_ATR (default 1.5).
"""
from __future__ import annotations

import os
import time

from trading import state

_FILE = "direction_pullback.json"              # {"armed": {key: row}, "stats": {...}}


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def enabled() -> bool:
    return os.environ.get("PULLBACK_ENTRY", "1") in ("1", "true", "TRUE", "yes", "on")


def _key(symbol: str, segment: str) -> str:
    return f"{(segment or 'futures').lower()}|{symbol}"


def live_price(symbol: str, segment: str = "futures", *,
               max_age_s: float = 1200.0) -> float | None:
    """Best live price available in ANY data mode: the quote path first (ui-capture
    in UI-only mode, ccxt/OpenAlgo otherwise), else the local 5m feather's last close
    when it is fresh enough (candle_updater keeps these current — zero network).
    None means no honest price → callers degrade, never guess."""
    try:
        from trading.broker_sense import data_failsafe as _df
        q = (_df.quote(symbol, "crypto") or {}).get("last")
        if q:
            return float(q)
    except Exception:
        pass
    try:
        from trading.direction.truth_ledger import _closes, _feather_for
        path, _ = _feather_for(symbol, segment)
        data = _closes(path) if path else None
        if data:
            ts, close = data
            if time.time() - float(ts[-1]) <= max_age_s:
                return float(close[-1])
    except Exception:
        pass
    return None


def atr_from_df(df) -> float | None:
    """ATR(14) from an OHLCV dataframe (open/high/low/close columns); None on bad data."""
    try:
        if df is None or len(df) < 15:
            return None
        h, l, c = df["high"].astype(float), df["low"].astype(float), df["close"].astype(float)
        pc = c.shift(1)
        tr = (h - l).combine((h - pc).abs(), max).combine((l - pc).abs(), max)
        val = float(tr.tail(14).mean())
        return val if val > 0 else None
    except Exception:
        return None


def atr_from_feather(symbol: str, segment: str = "futures",
                     tf: str = "5m") -> float | None:
    """ATR(14) from the LOCAL candle feather (zero network) — so the explore path
    can arm with a REAL volatility distance instead of the blind pct fallback.
    None when no feather / not enough bars; callers pass it straight to arm()."""
    try:
        import pandas as pd
        from trading.direction.truth_ledger import _feather_for
        p5, _ = _feather_for(symbol, segment)
        if p5 is None:
            return None
        p = p5 if tf == "5m" else p5.with_name(p5.name.replace("-5m-", f"-{tf}-"))
        if not p.exists():
            return None
        df = pd.read_feather(p, columns=["date", "open", "high", "low", "close"]).tail(60)
        return atr_from_df(df)
    except Exception:
        return None


def arm(*, symbol: str, segment: str, direction: str, source: str,
        ref_price: float, atr: float | None = None,
        confidence: float | None = None, extra: dict | None = None) -> bool:
    """Register a directional claim as an ARMED pending entry. Re-arming the same
    symbol refreshes ref/ts; an opposite-direction claim REPLACES it (the newer
    verdict wins). Never raises."""
    try:
        d = (direction or "").upper()
        if d not in ("LONG", "SHORT") or not ref_price or ref_price <= 0:
            return False
        row = {"symbol": symbol, "segment": (segment or "futures").lower(),
               "direction": d, "source": str(source)[:80],
               "ref_price": float(ref_price),
               "atr": float(atr) if atr and atr > 0 else None,
               "confidence": confidence, "armed_ts": time.time(),
               "extra": extra or {}}

        def _m(data: dict) -> dict:
            data.setdefault("armed", {})[_key(symbol, segment)] = row
            s = data.setdefault("stats", {})
            s["armed_total"] = s.get("armed_total", 0) + 1
            return data
        state.mutate_json(_FILE, _m, default={})
        return True
    except Exception:
        return False


def _dist(row: dict) -> float:
    """The pullback distance in PRICE units for one armed row."""
    if row.get("atr"):
        return float(row["atr"]) * _env_f("PULLBACK_ATR", 0.5)
    return float(row["ref_price"]) * _env_f("PULLBACK_PCT", 0.15) / 100.0


def sweep(price_fn, *, segment: str | None = None, budget_s: float = 10.0) -> list[dict]:
    """Evaluate every armed claim (optionally one segment's) against a live price from
    `price_fn(symbol) -> float | None`. Returns the TRIGGERED rows (caller places the
    orders); mutates state to drop triggered/expired/runaway rows with honest counts.
    Cheap: one cached quote per armed symbol, hard time budget."""
    out: list[dict] = []
    if not enabled():
        return out
    t0 = time.monotonic()
    now = time.time()
    ttl_s = _env_f("PULLBACK_TTL_MIN", 45) * 60
    runaway_mult = _env_f("PULLBACK_RUNAWAY_ATR", 1.5)
    data = state.load_json(_FILE, {})
    armed: dict = data.get("armed") or {}
    if not armed:
        return out
    drops: dict[str, str] = {}                     # key → reason
    for key, row in armed.items():
        if segment and row.get("segment") != segment.lower():
            continue
        if time.monotonic() - t0 > budget_s:
            break
        age = now - float(row.get("armed_ts") or now)
        if age > ttl_s:
            drops[key] = "expired"
            continue
        try:
            px = price_fn(row["symbol"])
            px = float(px) if px else None
        except Exception:
            px = None
        if px is None or px <= 0:
            continue                               # no quote this pass → stays armed
        ref, d = float(row["ref_price"]), _dist(row)
        if row["direction"] == "LONG":
            if px <= ref - d:
                drops[key] = "triggered"
                out.append({**row, "entry_ref": px})
            elif px >= ref + runaway_mult * d:
                drops[key] = "runaway"
        else:
            if px >= ref + d:
                drops[key] = "triggered"
                out.append({**row, "entry_ref": px})
            elif px <= ref - runaway_mult * d:
                drops[key] = "runaway"
    if drops:
        def _m(dat: dict) -> dict:
            a = dat.setdefault("armed", {})
            s = dat.setdefault("stats", {})
            for k, reason in drops.items():
                if a.pop(k, None) is not None:
                    s[reason] = s.get(reason, 0) + 1
            return dat
        state.mutate_json(_FILE, _m, default={})
    return out


def status() -> dict:
    """Panel/API snapshot: armed rows + lifetime trigger/miss/expiry counts + levers."""
    data = state.load_json(_FILE, {})
    armed = sorted((data.get("armed") or {}).values(),
                   key=lambda r: -float(r.get("armed_ts") or 0))
    return {"enabled": enabled(), "n_armed": len(armed), "armed": armed[:40],
            "stats": data.get("stats") or {},
            "levers": {"PULLBACK_ATR": _env_f("PULLBACK_ATR", 0.5),
                       "PULLBACK_PCT": _env_f("PULLBACK_PCT", 0.15),
                       "PULLBACK_TTL_MIN": _env_f("PULLBACK_TTL_MIN", 45),
                       "PULLBACK_RUNAWAY_ATR": _env_f("PULLBACK_RUNAWAY_ATR", 1.5)}}
