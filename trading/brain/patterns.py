"""trading/brain/patterns.py — pattern + anomaly discovery (T8.6, reuse-first).

Reuse-first engines:
  • **STUMPY** matrix profile → unsupervised motif (recurring setup) and discord
    (anomaly) discovery on a price series, with no labels.
  • **TA-Lib** 61 candlestick-pattern recognizers for deterministic price-action features.

`PatternScanner.scan(ohlcv)` returns the recurring motifs, the biggest anomalies, a
"how-unusual-is-right-now" anomaly score, and which candlestick patterns fired on the
last bar — features the regime/entry layers and the brain consume. All CPU.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:
    import stumpy
    _HAVE_STUMPY = True
except Exception:  # pragma: no cover
    _HAVE_STUMPY = False

try:
    import talib
    _HAVE_TALIB = True
except Exception:  # pragma: no cover
    _HAVE_TALIB = False

# A compact, high-signal subset of TA-Lib candlestick recognizers.
_CDL = ["CDLENGULFING", "CDLHAMMER", "CDLSHOOTINGSTAR", "CDLDOJI", "CDLMORNINGSTAR",
        "CDLEVENINGSTAR", "CDLHARAMI", "CDL3WHITESOLDIERS", "CDL3BLACKCROWS",
        "CDLMARUBOZU"]


def matrix_profile(series, m: int = 20):
    """1-D matrix profile (distance to each window's nearest neighbour) via STUMPY."""
    x = np.asarray(series, dtype="float64")
    if not _HAVE_STUMPY or len(x) < 2 * m:
        return np.array([])
    mp = stumpy.stump(x, m)
    return mp[:, 0].astype(float)            # column 0 = profile distances


def find_anomalies(series, m: int = 20, k: int = 3) -> list[dict]:
    """Top-k discords (windows least similar to anything else = anomalies)."""
    P = matrix_profile(series, m)
    if P.size == 0:
        return []
    order = np.argsort(P)[::-1][:k]          # largest distance = most anomalous
    return [{"index": int(i), "distance": float(P[i])} for i in order]


def find_motifs(series, m: int = 20, k: int = 3) -> list[dict]:
    """Top-k motifs (most recurring window patterns) via STUMPY."""
    x = np.asarray(series, dtype="float64")
    P = matrix_profile(series, m)
    if P.size == 0:
        return []
    try:
        dists, idxs = stumpy.motifs(x, P, max_motifs=k)
        out = []
        for d_row, i_row in zip(dists, idxs):
            valid = [int(i) for i in i_row if i >= 0]
            if valid:
                out.append({"indices": valid, "distance": float(d_row[0])})
        return out
    except Exception:                         # fall back to smallest-distance windows
        order = np.argsort(P)[:k]
        return [{"indices": [int(i)], "distance": float(P[i])} for i in order]


def anomaly_score(series, m: int = 20) -> float:
    """How unusual is the most-recent window vs history (0 = typical, higher = rarer)."""
    P = matrix_profile(series, m)
    if P.size == 0:
        return 0.0
    last = float(P[-1])
    pos = P[P > 0]                             # ignore exact-duplicate (zero-distance) windows
    scale = float(np.median(pos)) if pos.size else 0.0
    if scale <= 0:                            # near-constant series → no meaningful anomaly
        return 0.0
    return round(min(last / scale, 50.0), 4)  # capped ratio vs typical distance (no blow-ups)


def candlestick_patterns(ohlcv: pd.DataFrame, names: list[str] | None = None) -> dict:
    """Per-bar candlestick signals (+100 bullish / -100 bearish / 0) via TA-Lib."""
    if not _HAVE_TALIB:
        return {}
    o, h, l, c = (ohlcv["open"].to_numpy("float64"), ohlcv["high"].to_numpy("float64"),
                  ohlcv["low"].to_numpy("float64"), ohlcv["close"].to_numpy("float64"))
    out = {}
    for nm in (names or _CDL):
        fn = getattr(talib, nm, None)
        if fn is not None:
            out[nm] = fn(o, h, l, c)
    return out


def candles_firing(ohlcv: pd.DataFrame) -> dict:
    """Which candlestick patterns fired on the LAST bar (name → +1/-1)."""
    pats = candlestick_patterns(ohlcv)
    firing = {}
    for nm, sig in pats.items():
        if len(sig) and sig[-1] != 0:
            firing[nm] = int(np.sign(sig[-1]))
    return firing


class PatternScanner:
    """One-call pattern/anomaly scan over an OHLCV frame."""

    def __init__(self, window: int = 20):
        self.window = window

    def scan(self, ohlcv: pd.DataFrame, *, k: int = 3) -> dict:
        close = ohlcv["close"]
        return {
            "window": self.window,
            "motifs": find_motifs(close, self.window, k),
            "anomalies": find_anomalies(close, self.window, k),
            "anomaly_score": anomaly_score(close, self.window),
            "candles_firing": candles_firing(ohlcv),
            "engine": "stumpy" if _HAVE_STUMPY else "unavailable",
        }
