"""trading/strategy/generators/alpha_ops.py — formulaic-alpha operator library.

Reuses the operator VOCABULARY of AlphaGen (vendor/alphagen, KDD-2023) — Ref/Delta/Mean/Std/
Var/Skew/Kurt/Max/Min/Med/Mad/Rank/WMA/EMA/Cov/Corr + Abs/Sign/Log/Add/Sub/Mul/Div/Pow/Greater/
Less — but implemented over a SINGLE-asset pandas OHLCV series (rolling windows) instead of
AlphaGen's torch multi-stock tensor layout, so it runs CPU-only with no Qlib/torch dependency.
Semantics mirror AlphaGen's `alphagen/data/expression.py` `_apply` methods exactly (WMA/EMA
weights, Rank as the windowed rank of the last value, Corr denominator guard, etc.).

These power the formulaic-alpha MINING generator (⑤) and are the evaluation namespace for
ExpressionStrategy(kind="alpha").
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _s(x, index):
    return x if isinstance(x, pd.Series) else pd.Series(np.asarray(x, dtype=float), index=index)


# ── element-wise ──────────────────────────────────────────────────────────────────
def Abs(x): return x.abs() if isinstance(x, pd.Series) else np.abs(x)
def Sign(x): return np.sign(x)
def Log(x): return np.log(np.abs(x).clip(lower=1e-8)) if isinstance(x, pd.Series) else np.log(np.abs(x) + 1e-8)
def Add(a, b): return a + b
def Sub(a, b): return a - b
def Mul(a, b): return a * b


def Div(a, b):
    if isinstance(b, pd.Series):
        return a / b.where(b.abs() > 1e-8, np.nan)
    return a / b if abs(b) > 1e-8 else a * 0.0


def Pow(a, b): return np.sign(a) * (np.abs(a).clip(upper=1e6)) ** float(np.clip(b, -3, 3)) if np.isscalar(b) else a
def Greater(a, b): return np.maximum(a, b)
def Less(a, b): return np.minimum(a, b)


# ── time-series (rolling) — window/delta is the 2nd arg ────────────────────────────
def Ref(x, d): return x.shift(int(d))
def Delta(x, d): return x - x.shift(int(d))
def Mean(x, d): return x.rolling(int(d), min_periods=1).mean()
def Sum(x, d): return x.rolling(int(d), min_periods=1).sum()
def Std(x, d): return x.rolling(int(d), min_periods=2).std()
def Var(x, d): return x.rolling(int(d), min_periods=2).var()
def Skew(x, d): return x.rolling(int(d), min_periods=3).skew()
def Kurt(x, d): return x.rolling(int(d), min_periods=4).kurt()
def Max(x, d): return x.rolling(int(d), min_periods=1).max()
def Min(x, d): return x.rolling(int(d), min_periods=1).min()
def Med(x, d): return x.rolling(int(d), min_periods=1).median()
def Mad(x, d): return x.rolling(int(d), min_periods=1).apply(lambda w: np.abs(w - w.mean()).mean(), raw=True)


def Rank(x, d):
    """Windowed rank of the LAST value within the window (AlphaGen Rank semantics), in [0,1]."""
    n = int(d)
    return x.rolling(n, min_periods=2).apply(
        lambda w: ((w[-1] > w).sum() + (w[-1] >= w).sum() + ((w[-1] >= w).sum() > (w[-1] > w).sum()))
        / (2 * len(w)), raw=True)


def WMA(x, d):
    n = int(d)
    w = np.arange(n, dtype=float)
    sw = w.sum() or 1.0
    return x.rolling(n, min_periods=n).apply(lambda a: float((w * a).sum() / sw), raw=True)


def EMA(x, d):
    n = int(d)
    return x.ewm(span=max(2, n), min_periods=1, adjust=False).mean()


def Cov(a, b, d):
    return a.rolling(int(d), min_periods=2).cov(b)


def Corr(a, b, d):
    return a.rolling(int(d), min_periods=2).corr(b).replace([np.inf, -np.inf], np.nan)


# the callable namespace + the OHLCV fields a formulaic alpha may reference
ALPHA_FUNCS = {
    "Abs": Abs, "Sign": Sign, "Log": Log, "Add": Add, "Sub": Sub, "Mul": Mul, "Div": Div,
    "Pow": Pow, "Greater": Greater, "Less": Less, "Ref": Ref, "Delta": Delta, "Mean": Mean,
    "Sum": Sum, "Std": Std, "Var": Var, "Skew": Skew, "Kurt": Kurt, "Max": Max, "Min": Min,
    "Med": Med, "Mad": Mad, "Rank": Rank, "WMA": WMA, "EMA": EMA, "Cov": Cov, "Corr": Corr,
}
ALPHA_FIELDS = ("open", "high", "low", "close", "volume", "vwap")


def alpha_namespace(df: pd.DataFrame) -> dict:
    """Bind OHLCV fields (+ synthetic vwap) as Series and the operators — the eval scope."""
    ns = dict(ALPHA_FUNCS)
    idx = df.index
    for f in ("open", "high", "low", "close", "volume"):
        ns[f] = _s(df[f], idx) if f in df.columns else pd.Series(0.0, index=idx)
    if "vwap" in df.columns:
        ns["vwap"] = _s(df["vwap"], idx)
    else:
        ns["vwap"] = (ns["high"] + ns["low"] + ns["close"]) / 3.0
    return ns
