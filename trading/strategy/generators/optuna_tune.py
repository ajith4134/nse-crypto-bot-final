"""trading/strategy/generators/optuna_tune.py — generator ⑥ (part B): Optuna tuning.

Research shortlist #6 (tuning half): Optuna's multi-objective NSGA-II / CMA-ES samplers converge
faster + smarter than blind crossover for the continuous knobs of a strategy. Here Optuna tunes a
continuous feature-weight vector into a linear alpha, optimising a two-objective Pareto —
maximise rank-IC vs. next-bar return, minimise turnover — so it returns a spread of efficient
alphas rather than one point. The Pareto-front alphas are emitted as ExpressionStrategy(sympy)
and still face the SHARED CPCV+DSR+PBO + family-wise gate; Optuna only proposes, the gate judges.

Reuse: optuna (NSGAIISampler). Cheap IC/turnover objective (full-sample proxy) so many trials
are affordable; the honest verdict is the causal guardrail on the elites.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.generators.base import StrategyGenerator
from trading.strategy.generators.expression import ExpressionStrategy


class OptunaGenerator(StrategyGenerator):
    """Optuna NSGA-II tunes linear-alpha weights on an IC-vs-turnover Pareto front."""

    name = "optuna_tune"

    def available(self) -> bool:
        import os
        if os.environ.get("OPTUNA_GEN", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            import optuna  # noqa: F401
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
        X = np.nan_to_num(feats[flist].to_numpy(dtype=float), nan=0.0, posinf=0.0, neginf=0.0)
        mu, sd = X.mean(axis=0), X.std(axis=0)
        sd[sd == 0] = 1.0
        Z = (X - mu) / sd
        fwd = np.nan_to_num(feats["close"].pct_change().shift(-1).to_numpy(dtype=float),
                            nan=0.0, posinf=0.0, neginf=0.0)
        from scipy import stats as _st
        d = len(flist)

        def _obj(trial):
            w = np.array([trial.suggest_float(f"w{i}", -1.0, 1.0) for i in range(d)])
            f = Z @ w
            s = np.std(f)
            fz = f / s if s > 0 else f
            sig = np.where(fz >= 0.5, 1.0, np.where(fz <= -0.5, -1.0, 0.0))
            if np.mean(np.abs(sig)) < 0.02:
                return -1.0, 1.0
            ic, _ = _st.spearmanr(f, fwd)
            ic = abs(float(ic)) if np.isfinite(ic) else 0.0
            turnover = float(np.mean(np.abs(np.diff(sig)))) if len(sig) > 1 else 1.0
            return ic, turnover

        try:
            import optuna
            optuna.logging.set_verbosity(optuna.logging.WARNING)
            study = optuna.create_study(
                directions=["maximize", "minimize"],
                sampler=optuna.samplers.NSGAIISampler(seed=int(seed)))
            study.optimize(_obj, n_trials=max(30, budget * 4), show_progress_bar=False)
            best = study.best_trials
        except Exception:
            return []

        out = []
        # rank Pareto trials by IC (objective 0), keep the informative ones
        best = sorted(best, key=lambda t: t.values[0] if t.values else 0.0, reverse=True)
        for i, t in enumerate(best[:max(4, min(int(budget), 12))]):
            if not t.values or t.values[0] < 0.02:
                continue
            w = [t.params.get(f"w{j}", 0.0) for j in range(d)]
            terms = [f"({wj:.4f}*{flist[j]})" for j, wj in enumerate(w) if abs(wj) > 1e-3]
            if not terms:
                continue
            out.append(ExpressionStrategy(
                market=market, features=list(flist), expr=" + ".join(terms), kind="sympy",
                id=f"optuna_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [], "mutations": ["optuna"],
                            "ic": round(float(t.values[0]), 4),
                            "turnover": round(float(t.values[1]), 4)}))
        return out
