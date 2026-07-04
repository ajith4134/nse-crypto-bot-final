"""Technical-feature layer — thin pandas-ta-classic wrapper (CANON-24/25).

* add_indicators — RSI / EMA(fast, medium, slow) / SMA / Bollinger / MA-slope
  with tunable lengths (the videos' feature set) and warm-up NaN GATING:
  indicator columns are NaN only during their warm-up; `gate_warmup` drops
  those rows so no model ever trains on warm-up garbage (CANON-24).
* Williams fractals + the ~20-line monotonic S/R extension (PNP-10: a level is
  support if lows monotonically DECREASE into candle l for n1 bars and
  INCREASE after it for n2 bars; mirrored for resistance).
* Candle-pattern proximity combiner (PNP-11/12): bullish engulfing/star close
  to support -> 2, bearish close to resistance -> 1, else 0 — validated
  profitability is the admission criterion for the signal (CANON-25).
* admission_gate — lazy hook into trading.fitness.run_signals (built in B1 by
  another lane); returns a pending verdict until that engine lands.

Expects a chronological OHLC(V) DataFrame with columns open/high/low/close
(case-insensitive)."""
from __future__ import annotations

import numpy as np
import pandas as pd

INDICATOR_COLS = ["rsi", "ema_fast", "ema_mid", "ema_slow", "sma",
                  "bb_lower", "bb_mid", "bb_upper", "ma_slope"]


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    for c in df.columns:
        if c.lower() == name:
            return df[c]
    raise KeyError(f"missing OHLC column {name!r} in {list(df.columns)}")


# --------------------------------------------------------------------------- #
#  Indicators (CANON-24)
# --------------------------------------------------------------------------- #
def add_indicators(df: pd.DataFrame, rsi_len: int = 15,
                   ema_lens: tuple = (20, 100, 150), sma_len: int = 20,
                   bb_len: int = 20, slope_len: int = 10) -> pd.DataFrame:
    """Return a COPY with the indicator columns appended (NaN in warm-up)."""
    import pandas_ta_classic as ta
    close = _col(df, "close")
    out = df.copy()
    out["rsi"] = ta.rsi(close, length=rsi_len)
    out["ema_fast"] = ta.ema(close, length=ema_lens[0])
    out["ema_mid"] = ta.ema(close, length=ema_lens[1])
    out["ema_slow"] = ta.ema(close, length=ema_lens[2])
    out["sma"] = ta.sma(close, length=sma_len)
    bb = ta.bbands(close, length=bb_len)
    lower = [c for c in bb.columns if c.startswith("BBL")][0]
    mid = [c for c in bb.columns if c.startswith("BBM")][0]
    upper = [c for c in bb.columns if c.startswith("BBU")][0]
    out["bb_lower"], out["bb_mid"], out["bb_upper"] = \
        bb[lower], bb[mid], bb[upper]
    out["ma_slope"] = ta.slope(out["sma"], length=slope_len)
    return out


def gate_warmup(df: pd.DataFrame, cols=None) -> pd.DataFrame:
    """Drop the leading warm-up rows: everything before the first row where
    ALL indicator columns are finite. NaNs may only exist in the warm-up —
    any NaN after gating is a data bug and raises."""
    cols = [c for c in (cols or INDICATOR_COLS) if c in df.columns]
    if not cols:
        return df
    ok = df[cols].notna().all(axis=1)
    if not ok.any():
        raise ValueError("all rows are warm-up: series shorter than the "
                         "longest indicator length")
    gated = df.loc[ok.idxmax():].copy()
    assert not gated[cols].isna().any().any(), \
        "NaN found after warm-up gate — non-contiguous indicator NaNs"
    return gated


# --------------------------------------------------------------------------- #
#  Williams fractals + monotonic S/R extension (PNP-10, ~20 lines)
# --------------------------------------------------------------------------- #
def support(df1: pd.DataFrame, l: int, n1: int, n2: int) -> int:
    """1 if candle l is a support: lows monotonically decrease into l for n1
    bars and increase after it for n2 bars (video-faithful)."""
    low = _col(df1, "low").to_numpy()
    if l - n1 < 0 or l + n2 >= len(low):
        return 0
    for i in range(l - n1 + 1, l + 1):
        if low[i] > low[i - 1]:
            return 0
    for i in range(l + 1, l + n2 + 1):
        if low[i] < low[i - 1]:
            return 0
    return 1


def resistance(df1: pd.DataFrame, l: int, n1: int, n2: int) -> int:
    """Mirror of support() on highs."""
    high = _col(df1, "high").to_numpy()
    if l - n1 < 0 or l + n2 >= len(high):
        return 0
    for i in range(l - n1 + 1, l + 1):
        if high[i] < high[i - 1]:
            return 0
    for i in range(l + 1, l + n2 + 1):
        if high[i] > high[i - 1]:
            return 0
    return 1


def fractal_levels(df: pd.DataFrame, n1: int = 2, n2: int = 2) -> dict:
    """All S/R levels: {'support': [(idx, low)...], 'resistance': [(idx, high)...]}"""
    low, high = _col(df, "low").to_numpy(), _col(df, "high").to_numpy()
    ss = [(l, float(low[l])) for l in range(len(df)) if support(df, l, n1, n2)]
    rr = [(l, float(high[l])) for l in range(len(df))
          if resistance(df, l, n1, n2)]
    return {"support": ss, "resistance": rr}


# --------------------------------------------------------------------------- #
#  Candle patterns + proximity combiner (PNP-11/12, CANON-25)
# --------------------------------------------------------------------------- #
def _close_to_levels(price: float, levels, tol: float) -> bool:
    return any(abs(price - lv) <= tol for _, lv in levels)


def proximity_signal(df: pd.DataFrame, n1: int = 2, n2: int = 2,
                     tol: float | None = None,
                     patterns=("engulfing", "shootingstar")) -> pd.Series:
    """Per-bar signal: 2 = bullish pattern near support, 1 = bearish pattern
    near resistance, 0 = none (PNP-12 semantics; tol defaults to ~150 pips of
    the median price scale, the video's `150e-4`-style window scaled to the
    instrument)."""
    import pandas_ta_classic as ta
    o, h, low_s, c = (_col(df, k) for k in ("open", "high", "low", "close"))
    if tol is None:
        tol = float(c.median()) * 150e-4 / 1.0                # scale-relative
    bull = np.zeros(len(df), bool)
    bear = np.zeros(len(df), bool)
    for name in patterns:
        pat = ta.cdl_pattern(o, h, low_s, c, name=name)
        v = pat.iloc[:, 0].fillna(0).to_numpy()
        bull |= v > 0
        bear |= v < 0
    levels = fractal_levels(df, n1, n2)
    sig = np.zeros(len(df), int)
    closes = c.to_numpy()
    for i in range(len(df)):
        past_s = [(j, lv) for j, lv in levels["support"] if j < i]
        past_r = [(j, lv) for j, lv in levels["resistance"] if j < i]
        if bull[i] and _close_to_levels(float(closes[i]), past_s, tol):
            sig[i] = 2                                        # bullish @ supp
        elif bear[i] and _close_to_levels(float(closes[i]), past_r, tol):
            sig[i] = 1                                        # bearish @ res
    return pd.Series(sig, index=df.index, name="proximity_signal")


# --------------------------------------------------------------------------- #
#  Admission gate (CANON-25: profitability is the admission criterion)
# --------------------------------------------------------------------------- #
def admission_gate(df: pd.DataFrame, signal: pd.Series, **kwargs) -> dict:
    """Run the candidate signal through the mark-to-market fitness engine and
    return its verdict. trading.fitness is built in B1 by another lane, so the
    import is lazy and its absence is an honest 'pending', never a fake pass."""
    try:
        from trading.fitness import run_signals               # lazy (B1 lane)
    except Exception as exc:
        return {"status": "pending", "admitted": None,
                "reason": f"trading.fitness not available yet ({exc})"}
    try:
        result = run_signals(df, signal, **kwargs)
        return {"status": "ok", "admitted": bool(
            result.get("profitable", result.get("admitted", False))
            if isinstance(result, dict) else result), "result": result}
    except Exception as exc:                                  # honest failure
        return {"status": "error", "admitted": None, "reason": str(exc)}
