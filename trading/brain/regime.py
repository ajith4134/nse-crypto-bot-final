"""trading/brain/regime.py — market-regime detection + regime-gated activation (T8.6).

Reuse-first: **hmmlearn** GaussianHMM infers hidden market regimes from observable
features (returns + volatility). States are auto-labelled by their mean return into
bull / bear / neutral (or N states), giving the brain a regime context node. `RegimeGate`
then turns strategies on/off by the current regime — "regime-gated strategy activation"
so a breakout strategy only fires in trending regimes, mean-reversion in ranging, etc.

Deterministic (GaussianHMM seeded via random_state). CPU.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from hmmlearn import hmm


def _observations(ohlcv: pd.DataFrame) -> np.ndarray:
    close = ohlcv["close"].astype(float)
    ret = close.pct_change().fillna(0.0)
    vol = ret.rolling(10).std().fillna(ret.std() or 1e-6)
    rng = ((ohlcv["high"] - ohlcv["low"]) / close).fillna(0.0)
    return np.column_stack([ret.to_numpy(), vol.to_numpy(), rng.to_numpy()])


class RegimeModel:
    """Gaussian-HMM regime detector; states labelled bull/bear/neutral by mean return."""

    def __init__(self, n_states: int = 3, *, seed: int = 0, n_iter: int = 50):
        self.n_states = n_states
        self.model = hmm.GaussianHMM(n_components=n_states, covariance_type="diag",
                                     n_iter=n_iter, random_state=seed)
        self.labels: dict[int, str] = {}
        self._fitted = False

    def _label_states(self, X: np.ndarray) -> None:
        states = self.model.predict(X)
        mean_ret = {}
        for s in range(self.n_states):
            mask = states == s
            mean_ret[s] = float(X[mask, 0].mean()) if mask.any() else 0.0
        order = sorted(mean_ret, key=mean_ret.get)            # low→high mean return
        if self.n_states == 3:
            names = ["bear", "neutral", "bull"]
        elif self.n_states == 2:
            names = ["bear", "bull"]
        else:
            names = [f"s{i}" for i in range(self.n_states)]
        self.labels = {state: names[rank] for rank, state in enumerate(order)}

    def fit(self, ohlcv: pd.DataFrame) -> "RegimeModel":
        X = _observations(ohlcv)
        self.model.fit(X)
        self._label_states(X)
        self._fitted = True
        return self

    def predict_states(self, ohlcv: pd.DataFrame) -> np.ndarray:
        return self.model.predict(_observations(ohlcv))

    def predict_labels(self, ohlcv: pd.DataFrame) -> list[str]:
        return [self.labels.get(int(s), str(s)) for s in self.predict_states(ohlcv)]

    def current_regime(self, ohlcv: pd.DataFrame) -> str:
        return self.predict_labels(ohlcv)[-1]

    def status(self) -> dict:
        return {"n_states": self.n_states, "fitted": self._fitted, "labels": self.labels}


@dataclass
class RegimeGate:
    """Enables strategies only in their allowed regimes (regime-gated activation)."""
    allowed: dict = field(default_factory=dict)     # strategy_id -> set/list of regimes
    default_allowed: tuple = ("bull", "bear", "neutral")

    def is_active(self, strategy_id: str, regime: str) -> bool:
        allow = self.allowed.get(strategy_id, self.default_allowed)
        return regime in allow

    def activate(self, strategy_ids: list[str], regime: str) -> list[str]:
        return [sid for sid in strategy_ids if self.is_active(sid, regime)]
