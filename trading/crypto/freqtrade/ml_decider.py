"""trading/crypto/freqtrade/ml_decider.py — real ML direction models → brain instruction (Phase G).

The library's ML-direction family (ml_random_forest_direction / ml_xgboost_direction /
ml_lightgbm_direction / ml_gbdt_* / ml_logreg_*) implemented as REAL sklearn/boosting models
trained on real ccxt OHLCV features, predicting the next-window direction. The prediction is read
as an entry/exit INSTRUCTION and driven onto Freqtrade by `BrainExecutor` (brain decides, Freqtrade
executes) — the robust path after FreqAI proved environment-incompatible (freqtrade↔datasieve).

Each `MLDirectionDecider(model=...)` is one library ML strategy. Trains per-pair on a rolling
window, caches the model, retrains every `retrain_every` calls. Offline-safe (FLAT on any failure).
"""
from __future__ import annotations

import time

import numpy as np
import pandas as pd

# model registry → the library's ML-direction variants (all deps already installed)
_MODELS = {
    "rf":     ("ml_random_forest_direction", "sklearn.ensemble", "RandomForestClassifier",
               {"n_estimators": 120, "max_depth": 6, "n_jobs": 1, "random_state": 0}),
    "xgb":    ("ml_xgboost_direction", "xgboost", "XGBClassifier",
               {"n_estimators": 150, "max_depth": 4, "learning_rate": 0.05, "n_jobs": 1,
                "verbosity": 0, "use_label_encoder": False}),
    "lgb":    ("ml_lightgbm_direction", "lightgbm", "LGBMClassifier",
               {"n_estimators": 150, "max_depth": 5, "learning_rate": 0.05, "n_jobs": 1,
                "verbose": -1}),
    "gbdt":   ("ml_gbdt_direction", "sklearn.ensemble", "GradientBoostingClassifier",
               {"n_estimators": 100, "max_depth": 3, "random_state": 0}),
    "logreg": ("ml_logreg_direction", "sklearn.linear_model", "LogisticRegression",
               {"max_iter": 500, "C": 1.0}),
}


class MLDirectionDecider:
    """Train a real classifier on live OHLCV features → next-window up/down → brain instruction."""

    def __init__(self, model: str = "rf", *, exchange: str = "binance", timeframe: str = "5m",
                 lookback: int = 600, horizon: int = 6, retrain_every: int = 120,
                 prob_threshold: float = 0.55):
        if model not in _MODELS:
            raise ValueError(f"model must be one of {tuple(_MODELS)}")
        self.model = model
        self.library_name = _MODELS[model][0]
        self._exchange, self._tf = exchange, timeframe
        self._lookback, self._horizon = lookback, horizon
        self._retrain_every, self._prob_threshold = retrain_every, prob_threshold
        self._ccxt = None
        self._fitted: dict = {}            # symbol -> (model, n_calls)

    def _client(self):
        if self._ccxt is None:
            from trading.crypto.exchange_client import ExchangeClient
            self._ccxt = ExchangeClient(self._exchange, market_type="spot")
        return self._ccxt

    def _new_model(self):
        _, mod, cls, params = _MODELS[self.model]
        import importlib
        Model = getattr(importlib.import_module(mod), cls)
        try:
            return Model(**params)
        except TypeError:                  # older/newer sklearn dropped some kwargs
            return Model()

    def _features_labels(self, symbol: str):
        raw = self._client()._client().fetch_ohlcv(symbol, self._tf, limit=self._lookback)
        if not raw or len(raw) < 120:
            return None
        df = pd.DataFrame(raw, columns=["time", "open", "high", "low", "close", "volume"])
        from trading.strategy.library.features_ext import compute_features_ext
        feats = compute_features_ext(df[["open", "high", "low", "close", "volume"]])
        # numeric feature matrix (drop obvious non-features)
        X = feats.select_dtypes(include=[np.number]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
        close = df["close"].reset_index(drop=True).iloc[-len(X):].reset_index(drop=True)
        fwd = close.shift(-self._horizon) / close - 1.0
        y = (fwd > 0).astype(int)
        return X.reset_index(drop=True), y, fwd

    def _model_for(self, symbol: str):
        cached = self._fitted.get(symbol)
        if cached and cached[1] % self._retrain_every != 0:
            self._fitted[symbol] = (cached[0], cached[1] + 1)
            return cached[0]
        fl = self._features_labels(symbol)
        if fl is None:
            return None
        X, y, _ = fl
        train = slice(0, len(X) - self._horizon)        # don't train on unlabeled tail
        if y.iloc[train].nunique() < 2:
            return None
        m = self._new_model()
        m.fit(X.iloc[train], y.iloc[train])
        self._fitted[symbol] = (m, 1)
        return m

    def decide(self, market: str, symbol: str, price, *, in_position: bool) -> dict:
        if str(market).upper() != "CRYPTO":
            return {"action": "FLAT"}
        try:
            m = self._model_for(symbol)
            if m is None:
                return {"action": "FLAT", "_brain": {"reason": "insufficient data", "model": self.model}}
            X, _, _ = self._features_labels(symbol)
            p_up = float(m.predict_proba(X.iloc[[-1]])[0][1])
        except Exception as e:
            return {"action": "FLAT", "_brain": {"reason": f"{type(e).__name__}", "model": self.model}}
        action = "FLAT"
        if in_position:
            action = "EXIT" if p_up < 0.5 else "FLAT"
        elif p_up >= self._prob_threshold:
            action = "LONG"
        elif p_up <= (1.0 - self._prob_threshold):
            action = "SHORT"
        return {"action": action, "size": 1.0,
                "_brain": {"source": f"ml:{self.model}", "library": self.library_name,
                           "p_up": round(p_up, 3), "confidence": round(abs(p_up - 0.5) * 2, 3),
                           "action": {"LONG": "UP", "SHORT": "DOWN"}.get(action, "NEUTRAL")}}


def all_ml_deciders(**kw) -> list:
    """One decider per library ML model (the ML-direction family, as real models)."""
    return [MLDirectionDecider(model=m, **kw) for m in _MODELS]
