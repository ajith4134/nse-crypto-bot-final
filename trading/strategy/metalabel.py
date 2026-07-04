"""trading/strategy/metalabel.py — meta-labeling gate (Pillar 20, López de Prado ch. 3).

The primary strategy decides DIRECTION (long/short). A secondary classifier decides
WHETHER TO ACT and HOW BIG — trained on triple-barrier outcomes of the primary signal.
This is the single most effective precision lever for a rule-based signal: it keeps the
signal's recall but learns, from features, to veto the low-precision firings.

Pipeline:
  1. triple_barrier_labels() — for every bar the primary signal fired, look forward and
     label 1 if the profit barrier was hit before the stop/time barrier (a "good" firing),
     else 0. Barriers are ATR-scaled so they adapt to volatility.
  2. MetaLabeler.fit() — train a LightGBM classifier (gradient-boosted trees, CPU, fast)
     on the entry-bar features → P(good firing). Falls back to a logistic-regression-style
     numpy model when LightGBM is unavailable, so the gate always works.
  3. MetaLabeler.gate() — at decision time: act only when P >= threshold; the returned
     probability multiplies position size (confidence-scaled sizing, capped by the caller).

Reuse-first: LightGBM for the model, numpy for labels and the fallback; the triple-barrier
+ meta-label wiring is the glue. `pip install lightgbm` already present.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

try:
    import lightgbm as lgb
    _HAS_LGB = True
except Exception:                                    # pragma: no cover - fallback path
    _HAS_LGB = False


def _atr(ohlcv: pd.DataFrame, n: int = 14) -> np.ndarray:
    high = ohlcv["high"].to_numpy(dtype=float)
    low = ohlcv["low"].to_numpy(dtype=float)
    close = ohlcv["close"].to_numpy(dtype=float)
    prev = np.concatenate([[close[0]], close[:-1]])
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    atr = pd.Series(tr).rolling(n, min_periods=1).mean().to_numpy()
    return atr


def triple_barrier_labels(ohlcv: pd.DataFrame, signal: pd.Series, *, pt: float = 2.0,
                          sl: float = 1.0, max_hold: int = 24, atr_n: int = 14) -> pd.DataFrame:
    """Label each bar where `signal` != 0 by which barrier the trade hits first.

    pt/sl are ATR multiples for the profit-take / stop barriers; max_hold is the vertical
    (time) barrier in bars. Returns a frame indexed by entry bar with columns
    {side, label, ret, bars_held, barrier}. label=1 → profit barrier hit first (a good firing).
    """
    close = ohlcv["close"].to_numpy(dtype=float)
    atr = _atr(ohlcv, atr_n)
    sig = np.asarray(signal, dtype=float)
    n = len(close)
    rows = []
    for i in range(n - 1):
        side = 1 if sig[i] > 0 else (-1 if sig[i] < 0 else 0)
        if side == 0:
            continue
        entry = close[i]
        a = atr[i] if atr[i] > 0 else entry * 0.01
        up = entry + pt * a
        dn = entry - sl * a
        end = min(i + max_hold, n - 1)
        label, ret, barrier, bars = 0, 0.0, "time", end - i
        for j in range(i + 1, end + 1):
            px = close[j]
            hit_up = px >= up
            hit_dn = px <= dn
            if side > 0 and hit_up or side < 0 and hit_dn:
                label, ret, barrier, bars = 1, side * (px - entry) / entry, "profit", j - i
                break
            if side > 0 and hit_dn or side < 0 and hit_up:
                label, ret, barrier, bars = 0, side * (px - entry) / entry, "stop", j - i
                break
        else:
            ret = side * (close[end] - entry) / entry
            label = 1 if ret > 0 else 0
        rows.append({"bar": i, "side": side, "label": label, "ret": float(ret),
                     "bars_held": bars, "barrier": barrier})
    return pd.DataFrame(rows).set_index("bar") if rows else pd.DataFrame(
        columns=["side", "label", "ret", "bars_held", "barrier"])


@dataclass
class MetaLabeler:
    """Secondary classifier: P(the primary signal's firing is a good trade)."""

    threshold: float = 0.5
    feature_cols: list = field(default_factory=list)
    _model: object = None
    _fallback: dict | None = None          # numpy logistic fallback params
    _fitted: bool = False
    _metrics: dict = field(default_factory=dict)

    def fit(self, features: pd.DataFrame, labels: pd.DataFrame) -> "MetaLabeler":
        """Train on entry-bar features aligned to triple-barrier labels."""
        if labels.empty:
            self._fitted = False
            return self
        idx = labels.index
        num = features.select_dtypes(include=[np.number])
        X = num.loc[idx].fillna(0.0)
        self.feature_cols = list(X.columns)
        y = labels["label"].to_numpy(dtype=int)
        Xv = X.to_numpy(dtype=float)
        if len(np.unique(y)) < 2:               # degenerate — constant meta-prob
            self._fallback = {"const": float(y.mean())}
            self._fitted = True
            self._metrics = {"n": int(len(y)), "pos_rate": float(y.mean()), "model": "const"}
            return self
        if _HAS_LGB:
            self._model = lgb.LGBMClassifier(
                n_estimators=200, num_leaves=15, learning_rate=0.05,
                min_child_samples=10, subsample=0.8, colsample_bytree=0.8,
                verbose=-1, n_jobs=1)
            self._model.fit(X, y)                 # fit on named frame; predict on named frame
            p = self._model.predict_proba(X)[:, 1]
            self._metrics = {"n": int(len(y)), "pos_rate": float(y.mean()),
                             "model": "lightgbm", "train_auc": _auc(y, p)}
        else:                                    # pragma: no cover
            self._fallback = _fit_logistic(Xv, y)
            p = _predict_logistic(self._fallback, Xv)
            self._metrics = {"n": int(len(y)), "pos_rate": float(y.mean()),
                             "model": "logistic", "train_auc": _auc(y, p)}
        self._fitted = True
        return self

    def predict_proba(self, feature_row: pd.Series | dict) -> float:
        """P(good firing) for one entry-bar feature vector."""
        if not self._fitted:
            return 0.5
        if self._fallback is not None and "const" in self._fallback:
            return float(self._fallback["const"])
        row = pd.Series(feature_row) if not isinstance(feature_row, pd.Series) else feature_row
        vals = {c: float(row.get(c, 0.0)) for c in self.feature_cols}
        if self._model is not None:              # named frame → matches training schema
            xdf = pd.DataFrame([vals], columns=self.feature_cols).fillna(0.0)
            return float(self._model.predict_proba(xdf)[0, 1])
        x = np.nan_to_num(np.array([[vals[c] for c in self.feature_cols]], dtype=float))
        return float(_predict_logistic(self._fallback, x)[0])

    def gate(self, feature_row: pd.Series | dict) -> dict:
        """Decision gate: {act, proba, size_mult}. size_mult scales position by confidence."""
        p = self.predict_proba(feature_row)
        act = p >= self.threshold
        # confidence-scaled size in (0,1]: rescale [threshold,1] → (0,1]
        span = max(1e-6, 1.0 - self.threshold)
        size_mult = max(0.0, min(1.0, (p - self.threshold) / span)) if act else 0.0
        return {"act": bool(act), "proba": float(p), "size_mult": float(size_mult)}

    def as_dict(self) -> dict:
        return {"fitted": self._fitted, "threshold": self.threshold,
                "n_features": len(self.feature_cols), "metrics": self._metrics}


# ── tiny numpy fallbacks (no sklearn dependency required) ────────────────────────
def _auc(y: np.ndarray, p: np.ndarray) -> float:
    pos = p[y == 1]
    neg = p[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    # Mann-Whitney U statistic → AUC
    order = np.argsort(p)
    ranks = np.empty(len(p), dtype=float)
    ranks[order] = np.arange(1, len(p) + 1)
    return float((ranks[y == 1].sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def _fit_logistic(X: np.ndarray, y: np.ndarray, *, lr: float = 0.1, iters: int = 400) -> dict:
    mu = X.mean(axis=0)
    sd = X.std(axis=0) + 1e-9
    Xn = (X - mu) / sd
    w = np.zeros(Xn.shape[1])
    b = 0.0
    for _ in range(iters):
        z = Xn @ w + b
        p = 1.0 / (1.0 + np.exp(-z))
        g = p - y
        w -= lr * (Xn.T @ g / len(y) + 1e-3 * w)
        b -= lr * g.mean()
    return {"w": w, "b": b, "mu": mu, "sd": sd}


def _predict_logistic(params: dict, X: np.ndarray) -> np.ndarray:
    if "const" in params:
        return np.full(len(X), params["const"])
    Xn = (X - params["mu"]) / params["sd"]
    z = Xn @ params["w"] + params["b"]
    return 1.0 / (1.0 + np.exp(-z))
