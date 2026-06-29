"""trading/screener/filters.py — standalone, composable screener filter algorithms.

Pure functions over plain row-dicts / OHLC frames, so the `Screener` can compose
them and tests can call them directly with deterministic fixtures. Two families:

  • PAIRLIST-style filters ported from freqtrade's `plugins/pairlist/` (GPLv3 algos
    re-implemented, NOT imported — see research/crypto-filters-screeners.md §3):
    PercentChange (gainers/losers), Volume (rank + relative/unusual volume),
    Age (new listings), Volatility (stddev of returns), RangeStability (ROC band).

  • TECHNICAL filters computed on an OHLC frame via `pandas_ta_classic`
    (ATR%/Bollinger-width/ADX/RSI/Supertrend/RVOL/breakout/52w-range — the
    'volatile movement' / breakout / momentum filters of the NSE/MCX research).

Everything is CPU-only and OFFLINE-SAFE: the technical block lazy-imports pandas /
pandas_ta_classic inside try/except and degrades to {} so nothing ever raises.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable

Row = dict[str, Any]


# ── small helpers ─────────────────────────────────────────────────────────────
def _num(v: Any, default: float = 0.0) -> float:
    """Best-effort float — tolerant of None / strings / commas (NSE feeds)."""
    if v is None:
        return default
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return default


def _get(row: Row, *keys: str, default: float = 0.0) -> float:
    for k in keys:
        if k in row and row[k] not in (None, ""):
            return _num(row[k], default)
    return default


# ── freqtrade PercentChangePairList port → gainers / losers ───────────────────
def percent_change_filter(rows: Iterable[Row], *, key: str = "pct_change",
                          sort_direction: str = "desc",
                          min_value: float | None = None,
                          max_value: float | None = None) -> list[Row]:
    """Sort/clip rows by % change (24h or N-day). desc → top gainers, asc → losers.

    Mirrors freqtrade PercentChangePairList: filter by [min,max] then sort.
    """
    out = []
    for r in rows:
        v = _get(r, key, "percentage", "pChange", "pct_change")
        if min_value is not None and v < min_value:
            continue
        if max_value is not None and v > max_value:
            continue
        out.append(r)
    out.sort(key=lambda r: _get(r, key, "percentage", "pChange", "pct_change"),
             reverse=(sort_direction != "asc"))
    return out


# ── freqtrade VolumePairList port → liquidity rank + unusual volume ───────────
def volume_filter(rows: Iterable[Row], *, key: str = "quote_volume",
                  min_value: float | None = None,
                  sort_direction: str = "desc") -> list[Row]:
    """Rank rows by traded value (quoteVolume) — the primary liquidity screen."""
    out = [r for r in rows
           if min_value is None or _get(r, key, "quoteVolume", "volume") >= min_value]
    out.sort(key=lambda r: _get(r, key, "quoteVolume", "volume"),
             reverse=(sort_direction != "asc"))
    return out


def relative_volume(volumes: list[float], window: int = 20) -> float | None:
    """RVOL = latest volume ÷ trailing mean(window). >2 ≈ unusual participation.

    freqtrade VolumePairList 'lookback' (range) mode, reduced to a single ratio.
    """
    vals = [_num(v) for v in volumes if v is not None]
    if len(vals) < 2:
        return None
    base = vals[-(window + 1):-1] if len(vals) > window else vals[:-1]
    avg = sum(base) / len(base) if base else 0.0
    if avg <= 0:
        return None
    return vals[-1] / avg


# ── freqtrade AgeFilter port → new listings ───────────────────────────────────
def age_filter(rows: Iterable[Row], *, min_days: int | None = None,
               max_days: int | None = None, key: str = "age_days") -> list[Row]:
    """Keep rows whose listing age (days) is within [min_days, max_days]."""
    out = []
    for r in rows:
        age = _get(r, key, default=math.inf)
        if min_days is not None and age < min_days:
            continue
        if max_days is not None and age > max_days:
            continue
        out.append(r)
    return out


# ── freqtrade VolatilityFilter port → stddev of daily returns ─────────────────
def realized_volatility(closes: list[float]) -> float | None:
    """Annualised-ish stddev of log returns (freqtrade VolatilityFilter metric)."""
    vals = [_num(c) for c in closes if c is not None and _num(c) > 0]
    if len(vals) < 3:
        return None
    rets = [math.log(vals[i] / vals[i - 1]) for i in range(1, len(vals))]
    mean = sum(rets) / len(rets)
    var = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(var) * math.sqrt(len(rets))


def volatility_filter(rows: Iterable[Row], *, min_volatility: float | None = None,
                      max_volatility: float | None = None,
                      key: str = "volatility") -> list[Row]:
    """Keep rows whose volatility metric is within [min,max]."""
    out = []
    for r in rows:
        v = _get(r, key, default=None) if key in r else None
        if v is None:
            out.append(r)
            continue
        if min_volatility is not None and v < min_volatility:
            continue
        if max_volatility is not None and v > max_volatility:
            continue
        out.append(r)
    return out


# ── freqtrade RangeStabilityFilter port → rate-of-change band ─────────────────
def range_stability(highs: list[float], lows: list[float]) -> float | None:
    """ROC over the window = (max(high) − min(low)) / min(low)."""
    hs = [_num(h) for h in highs if h is not None]
    ls = [_num(l) for l in lows if l is not None and _num(l) > 0]
    if not hs or not ls:
        return None
    lo = min(ls)
    if lo <= 0:
        return None
    return (max(hs) - lo) / lo


# ── derivatives helpers (freqtrade has none — built per research) ─────────────
def oi_buildup(price_change: float, oi_change: float) -> str:
    """Classify F&O / perp positioning from ΔPrice vs ΔOI (research §2.3)."""
    p, o = _num(price_change), _num(oi_change)
    if o > 0 and p > 0:
        return "long_buildup"
    if o > 0 and p < 0:
        return "short_buildup"
    if o < 0 and p < 0:
        return "long_unwinding"
    if o < 0 and p > 0:
        return "short_covering"
    return "neutral"


# ── technical filters on an OHLC frame (pandas_ta_classic) ────────────────────
def apply_technical_filters(ohlc_df: Any, *, atr_len: int = 14, rsi_len: int = 14,
                            adx_len: int = 14, bb_len: int = 20,
                            breakout_len: int = 20) -> dict:
    """Compute the technical 'volatile-movement / breakout / momentum' filters.

    Accepts a pandas DataFrame (or list of OHLC dicts/rows with
    open/high/low/close/volume). Returns a flat metrics dict — OFFLINE-SAFE:
    if pandas / pandas_ta_classic is missing or the frame is too short, returns
    {} (never raises), so callers degrade gracefully.
    """
    try:
        import pandas as pd
    except Exception:
        return {}

    # normalise input → DataFrame with lowercase ohlcv columns
    try:
        if isinstance(ohlc_df, pd.DataFrame):
            df = ohlc_df.copy()
        else:
            df = pd.DataFrame(list(ohlc_df))
        df.columns = [str(c).lower() for c in df.columns]
        for col in ("open", "high", "low", "close"):
            if col not in df.columns:
                return {}
            df[col] = pd.to_numeric(df[col], errors="coerce")
        if "volume" in df.columns:
            df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
        df = df.dropna(subset=["high", "low", "close"])
    except Exception:
        return {}

    if len(df) < 2:
        return {}

    close = df["close"]
    out: dict = {"close": float(close.iloc[-1]), "bars": int(len(df))}

    # 52-week / N-bar range position + breakout (pure pandas, always works)
    try:
        hi, lo = float(df["high"].max()), float(df["low"].min())
        if hi > lo:
            out["range_pos"] = (float(close.iloc[-1]) - lo) / (hi - lo)
        out["period_high"], out["period_low"] = hi, lo
        if len(df) > breakout_len:
            prior_high = float(df["high"].iloc[-breakout_len - 1:-1].max())
            prior_low = float(df["low"].iloc[-breakout_len - 1:-1].min())
            out["breakout_up"] = bool(close.iloc[-1] >= prior_high)
            out["breakout_down"] = bool(close.iloc[-1] <= prior_low)
    except Exception:
        pass

    # RVOL
    if "volume" in df.columns:
        rv = relative_volume(df["volume"].tolist())
        if rv is not None:
            out["rvol"] = rv

    # realized vol (always-available pure fallback)
    rvol_ret = realized_volatility(close.tolist())
    if rvol_ret is not None:
        out["volatility"] = rvol_ret

    # pandas_ta_classic indicators (best-effort, each guarded)
    try:
        import pandas_ta_classic as ta
    except Exception:
        return out

    def _last(series) -> float | None:
        try:
            v = float(series.iloc[-1])
            return None if math.isnan(v) else v
        except Exception:
            return None

    try:
        atr = _last(ta.atr(df["high"], df["low"], df["close"], length=atr_len))
        if atr is not None:
            out["atr"] = atr
            if out["close"]:
                out["atr_pct"] = atr / out["close"] * 100.0
    except Exception:
        pass
    try:
        out["rsi"] = _last(ta.rsi(close, length=rsi_len))
    except Exception:
        pass
    try:
        adx = ta.adx(df["high"], df["low"], df["close"], length=adx_len)
        out["adx"] = _last(adx[f"ADX_{adx_len}"])
    except Exception:
        pass
    try:
        bb = ta.bbands(close, length=bb_len)
        if bb is not None:
            # BBB_* is the band-width %; column name carries the std (e.g. 2.0)
            wcol = [c for c in bb.columns if c.startswith("BBB_")]
            if wcol:
                out["bb_width"] = _last(bb[wcol[0]])
    except Exception:
        pass
    try:
        st = ta.supertrend(df["high"], df["low"], df["close"], length=7, multiplier=3.0)
        if st is not None:
            dcol = [c for c in st.columns if c.startswith("SUPERTd_")]
            if dcol:
                d = _last(st[dcol[0]])
                out["supertrend_dir"] = int(d) if d is not None else None
    except Exception:
        pass

    return {k: v for k, v in out.items() if v is not None}


# ── generic scoring used by the Screener to RANK candidates ───────────────────
def score_rows(rows: list[Row], score_fn: Callable[[Row], float],
               reason_fn: Callable[[Row], str] | None = None) -> list[Row]:
    """Attach a `score` (+ optional `reason`) to each row and sort best-first."""
    scored = []
    for r in rows:
        s = float(score_fn(r))
        r = {**r, "score": round(s, 6)}
        if reason_fn is not None and not r.get("reason"):
            r["reason"] = reason_fn(r)
        scored.append(r)
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored
