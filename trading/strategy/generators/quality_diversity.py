"""trading/strategy/generators/quality_diversity.py — generator ④: Quality-Diversity (pyribs).

Research shortlist #4: plain NSGA-II returns a Pareto front that collapses toward a few similar
solutions. Quality-Diversity (MAP-Elites / CMA-ME) instead keeps an *illuminated archive* of
high-performers spread across a BEHAVIOR space — so we get a library of strategies that behave
differently (different activity / directional bias), which is exactly what a regime-switching
desk and a diverse skill library need.

Reuse: pyribs (ribs) GridArchive + EvolutionStrategyEmitter (CMA-ME) + Scheduler. The solution
vector is a continuous feature-weight vector → a linear factor `Σ wᵢ·featureᵢ` → a long/short
signal. QD SEARCH uses a cheap in-sample Sharpe proxy (fast, so we can afford many evaluations);
the archive elites then go through the SAME honest CPCV+DSR+PBO guardrail via evaluate_and_admit
before anything is trusted. Behavior descriptors: (activity = mean |signal|, bias = mean signal).
Each elite is emitted as an ExpressionStrategy(sympy) — a serialisable linear alpha.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.generators.base import StrategyGenerator
from trading.strategy.generators.expression import ExpressionStrategy


def _standardize(feats: pd.DataFrame, flist) -> np.ndarray:
    """Full-sample z-score of the feature matrix — used ONLY for the cheap QD search proxy
    (the final guardrail on elites is causal, so search-time leakage doesn't reach a verdict)."""
    X = feats[flist].to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    mu = X.mean(axis=0)
    sd = X.std(axis=0)
    sd[sd == 0] = 1.0
    return (X - mu) / sd


class QualityDiversityGenerator(StrategyGenerator):
    """pyribs CMA-ME illuminates an archive of behaviorally-diverse linear-alpha strategies."""

    name = "quality_diversity"

    def available(self) -> bool:
        try:
            import ribs  # noqa: F401
            return True
        except Exception:
            return False

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        feats = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        from trading.strategy.operators import market_features
        flist = [f for f in market_features(market) if f in feats.columns]
        if len(flist) < 2 or "close" not in feats.columns:
            return []
        Z = _standardize(feats, flist)                       # (T, d)
        fwd = feats["close"].pct_change().shift(-1).to_numpy(dtype=float)
        fwd = np.nan_to_num(fwd, nan=0.0, posinf=0.0, neginf=0.0)
        d = len(flist)

        def _sig(x):
            f = Z @ x                                        # linear factor value per bar
            s = np.std(f)
            fz = f / s if s > 0 else f
            sig = np.zeros_like(fz)
            sig[fz >= 0.5] = 1.0
            sig[fz <= -0.5] = -1.0
            return sig

        def _evaluate(x):
            sig = _sig(x)
            r = sig * fwd
            act = float(np.mean(np.abs(sig)))                # descriptor 1: activity [0,1]
            bias = float(np.clip(np.mean(sig), -1.0, 1.0))   # descriptor 2: directional bias
            sd = float(np.std(r))
            obj = float(np.mean(r) / sd * np.sqrt(252)) if sd > 0 and act > 0.02 else -10.0
            return obj, np.array([act, bias])

        try:
            from ribs.archives import GridArchive
            from ribs.emitters import EvolutionStrategyEmitter
            from ribs.schedulers import Scheduler
            archive = GridArchive(solution_dim=d, dims=[8, 8],
                                  ranges=[(0.0, 1.0), (-1.0, 1.0)], seed=int(seed))
            emitters = [EvolutionStrategyEmitter(
                archive, x0=np.zeros(d), sigma0=0.5, batch_size=16, seed=int(seed) + e)
                for e in range(2)]
            scheduler = Scheduler(archive, emitters)
            for _ in range(15):                              # cheap QD search
                sols = scheduler.ask()
                objs, meas = [], []
                for x in sols:
                    o, m = _evaluate(x)
                    objs.append(o)
                    meas.append(m)
                scheduler.tell(objs, np.array(meas))
        except Exception:
            return []

        # extract the best archive elites → ExpressionStrategy linear alphas
        try:
            data = archive.data(["solution", "objective"])
            sols, objs = data["solution"], data["objective"]
        except Exception:
            return []
        order = np.argsort(objs)[::-1]
        out = []
        for i, idx in enumerate(order[:max(4, min(int(budget), 12))]):
            w = sols[idx]
            if not np.any(np.abs(w) > 1e-6):
                continue
            terms = [f"({w_i:.4f}*{flist[j]})" for j, w_i in enumerate(w) if abs(w_i) > 1e-4]
            if not terms:
                continue
            expr = " + ".join(terms)
            out.append(ExpressionStrategy(
                market=market, features=list(flist), expr=expr, kind="sympy",
                long_thr=0.5, short_thr=-0.5, id=f"qd_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [], "mutations": ["quality_diversity"],
                            "qd_objective": round(float(objs[idx]), 4)}))
        return out
