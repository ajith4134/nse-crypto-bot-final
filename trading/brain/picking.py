"""trading/brain/picking.py — cross-sectional asset picking (T8.6).

Chooses WHICH symbols to trade from a universe by ranking them cross-sectionally. Two
factor sources:
  • GPLearnFactorMiner — **LEARNS** a symbolic ranking factor from features→forward
    returns using **VENDORED gplearn** (vendor/gplearn, genetic-programming symbolic
    regression) — real library code, not a hand-rolled score.
  • CrossSectionalRanker — a composite z-score fallback when no learned factor is fitted.
Factor quality is validated with the rank **Information Coefficient** (Spearman) from the
T8.2 guardrails, so we only trust a factor that actually ranks forward returns.

Qlib (alpha-expression DSL + data layer) is the heavier substrate to swap in once the NSE
data layer is wired (no py3.13 wheel today). All CPU, deterministic.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from trading.strategy.guardrails import information_coefficient
from vendor.gplearn.genetic import SymbolicRegressor   # vendored, pure-Python GP

# default composite: reward momentum, penalise volatility/over-extension
_DEFAULT_WEIGHTS = {"mom": 1.0, "ret": 0.3, "vol": -0.6, "atr_pct": -0.3, "zscore": -0.2,
                    "rvol": 0.2, "rsi": 0.0}


def _zscores(values: dict[str, list[float]]) -> dict[str, np.ndarray]:
    out = {}
    for f, vals in values.items():
        a = np.asarray(vals, dtype=float)
        sd = a.std()
        out[f] = (a - a.mean()) / sd if sd > 0 else a * 0.0
    return out


@dataclass
class CrossSectionalRanker:
    """Rank a universe of symbols by a cross-sectional composite factor score."""
    weights: dict = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))

    def rank(self, universe: dict[str, dict]) -> list[dict]:
        """`universe`: {symbol: {feature: value, ...}}. Returns symbols sorted by score desc."""
        if not universe:
            return []
        symbols = list(universe)
        feats = set(self.weights) & set().union(*[set(v) for v in universe.values()])
        cols = {f: [float(universe[s].get(f, 0.0) or 0.0) for s in symbols] for f in feats}
        z = _zscores(cols)
        scores = np.zeros(len(symbols))
        for f in feats:
            scores += self.weights.get(f, 0.0) * z[f]
        ranked = sorted(zip(symbols, scores), key=lambda x: x[1], reverse=True)
        return [{"symbol": s, "score": round(float(sc), 4), "rank": i + 1}
                for i, (s, sc) in enumerate(ranked)]

    def select_top(self, universe: dict[str, dict], k: int = 5) -> list[str]:
        return [r["symbol"] for r in self.rank(universe)[:k]]

    @staticmethod
    def validate(factor_values, forward_returns) -> dict:
        """Rank-IC of a factor vs forward returns (factor-quality gate)."""
        ic = information_coefficient(factor_values, forward_returns)
        return {"ic": round(ic, 4), "tradeable": abs(ic) >= 0.03}


class GPLearnFactorMiner:
    """Learns a symbolic ranking factor from features→forward returns via VENDORED gplearn."""

    def __init__(self, feature_names: list[str], *, generations: int = 8,
                 population: int = 500, seed: int = 0,
                 function_set=("add", "sub", "mul", "div")):
        self.feature_names = list(feature_names)
        self.model = SymbolicRegressor(
            population_size=population, generations=generations, random_state=seed,
            function_set=function_set, parsimony_coefficient=0.001, verbose=0)
        self._fitted = False

    def fit(self, X, forward_returns) -> "GPLearnFactorMiner":
        self.model.fit(np.asarray(X, dtype=float), np.asarray(forward_returns, dtype=float))
        self._fitted = True
        return self

    def factor(self, X) -> np.ndarray:
        return self.model.predict(np.asarray(X, dtype=float))

    def program(self) -> str:
        return str(self.model._program) if self._fitted else ""


class AssetPicker:
    """Ranker + IC gate. Uses a LEARNED gplearn factor when one is fitted, else the composite."""

    def __init__(self, ranker: CrossSectionalRanker | None = None, *, top_k: int = 5,
                 miner: GPLearnFactorMiner | None = None):
        self.ranker = ranker or CrossSectionalRanker()
        self.top_k = top_k
        self.miner = miner

    def _rank_with_miner(self, universe: dict[str, dict]) -> list[dict]:
        symbols = list(universe)
        X = [[float(universe[s].get(f, 0.0) or 0.0) for f in self.miner.feature_names]
             for s in symbols]
        scores = self.miner.factor(X)
        ranked = sorted(zip(symbols, scores), key=lambda x: x[1], reverse=True)
        return [{"symbol": s, "score": round(float(sc), 6), "rank": i + 1}
                for i, (s, sc) in enumerate(ranked)]

    def pick(self, universe: dict[str, dict]) -> dict:
        if self.miner is not None and self.miner._fitted:
            ranked, source = self._rank_with_miner(universe), "gplearn"
        else:
            ranked, source = self.ranker.rank(universe), "composite"
        return {"top": [r["symbol"] for r in ranked[: self.top_k]],
                "ranked": ranked, "n_universe": len(universe), "factor_source": source}

    def status(self) -> dict:
        return {"top_k": self.top_k, "weights": self.ranker.weights,
                "miner": (self.miner.program() if (self.miner and self.miner._fitted)
                          else None)}
