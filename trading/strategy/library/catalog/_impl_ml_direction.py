"""catalog/_impl_ml_direction.py — REAL sklearn/boosting ML-direction backtests (Wave 2).

The ml_*_direction family (random forest / xgboost / lightgbm / catboost) as REAL models: train on
the in-sample half of a real OHLCV feature frame, predict next-bar direction out-of-sample, backtest
the +1/-1/0 signal. Same models the brain uses live (ml_decider.py) — here as library backtests.
Offline-safe: a fetch/fit failure returns a zero-metrics dict tagged with the reason.
"""
from __future__ import annotations

import importlib
import warnings

import numpy as np
import pandas as pd

from trading.strategy.library import evaluators as ev

_MODELS = {
    "rf":  ("sklearn.ensemble", "RandomForestClassifier",
            {"n_estimators": 120, "max_depth": 6, "n_jobs": 1, "random_state": 0}),
    "xgb": ("xgboost", "XGBClassifier",
            {"n_estimators": 150, "max_depth": 4, "learning_rate": 0.05, "n_jobs": 1, "verbosity": 0}),
    "lgb": ("lightgbm", "LGBMClassifier",
            {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.05, "n_jobs": 1, "verbose": -1}),
    "catboost": ("catboost", "CatBoostClassifier",
                 {"iterations": 200, "depth": 5, "learning_rate": 0.05, "verbose": False}),
}


def _empty(reason: str) -> dict:
    m = ev.metrics_from_returns([]); m["note"] = reason; return m


def _ohlcv():
    import ccxt
    raw = ccxt.binance({"enableRateLimit": True}).fetch_ohlcv("BTC/USDT", "1h", limit=1000)
    return pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"]) if raw else None


def _ml_backtest(model_key: str, *, horizon: int = 1) -> dict:
    try:
        df = _ohlcv()
        if df is None or len(df) < 300:
            return _empty("no OHLCV")
        from trading.strategy.library.features_ext import compute_features_ext
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            feats = compute_features_ext(df[["open", "high", "low", "close", "volume"]])
        X = feats.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        close = df["close"].reset_index(drop=True).iloc[-len(X):].reset_index(drop=True)
        y = (close.shift(-horizon) > close).astype(int)
        n = len(X); split = int(n * 0.6)
        if y.iloc[:split].nunique() < 2:
            return _empty("degenerate labels")
        mod, cls, params = _MODELS[model_key]
        Model = getattr(importlib.import_module(mod), cls)
        try:
            m = Model(**params)
        except TypeError:
            m = Model()
        m.fit(X.iloc[:split], y.iloc[:split])
        proba = m.predict_proba(X.iloc[split:n - horizon])[:, 1]
        sig = pd.Series(np.where(proba > 0.55, 1, np.where(proba < 0.45, -1, 0)))
        oos = df.iloc[-(n - split):].iloc[:len(sig)].reset_index(drop=True)
        from trading.strategy.backtest import backtest_signal
        return backtest_signal(sig.reset_index(drop=True), oos).metrics
    except Exception as e:
        return _empty(f"{type(e).__name__}: {str(e)[:50]}")


def bt_rf(md=None) -> dict:        return _ml_backtest("rf")
def bt_xgb(md=None) -> dict:       return _ml_backtest("xgb")
def bt_lgb(md=None) -> dict:       return _ml_backtest("lgb")
def bt_catboost(md=None) -> dict:  return _ml_backtest("catboost")
