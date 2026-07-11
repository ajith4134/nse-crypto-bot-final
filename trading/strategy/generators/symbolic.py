"""trading/strategy/generators/symbolic.py — generator ③: symbolic regression (BOTH engines).

Research shortlist #3: symbolic regression evolves the *expression tree itself* (strictly more
expressive than tuning a fixed genome template) — it can invent a factor like
`sub(mul(mom, rsi), atr)` we never templated. We ship BOTH engines the research named:

  • GplearnGenerator — gplearn.SymbolicTransformer (pure-Python, CPU, always available). Its
    programs export as function-call strings `sub(mul(X1,X2), X0)` → ExpressionStrategy(gplearn).
  • PysrGenerator    — PySR / SymbolicRegression.jl (Julia engine, faster + stronger). Its best
    equations export as sympy infix `x0 + x1*x2` → ExpressionStrategy(sympy).

Both fit factor = f(features) against next-bar return, then wrap the discovered formula as an
ExpressionStrategy and let the SHARED CPCV+DSR+PBO guardrail decide if it survives. The formula
value is causally z-scored + thresholded to a long/short signal inside ExpressionStrategy.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.generators.base import StrategyGenerator
from trading.strategy.generators.expression import ExpressionStrategy

# function set shared with expression._EXPR_FUNCS (so every gplearn program is evaluable)
_GPLEARN_FUNCS = ("add", "sub", "mul", "div", "sqrt", "log", "abs", "neg", "inv", "max", "min")


def _feature_matrix(feats: pd.DataFrame, market: str):
    """Ordered feature list (X0..Xn) + a clean numeric matrix + next-bar return target.

    Features come from market_features(market) ∩ available columns, so X{i} indexing lines up
    with what ExpressionStrategy will bind at signal time. Rows with no forward return dropped."""
    from trading.strategy.operators import market_features
    flist = [f for f in market_features(market) if f in feats.columns]
    if len(flist) < 2:
        return None, None, None, None
    X = feats[flist].to_numpy(dtype=float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    close = feats["close"] if "close" in feats.columns else None
    if close is None:
        return None, None, None, None
    fwd = close.pct_change().shift(-1).to_numpy(dtype=float)
    mask = np.isfinite(fwd)
    if mask.sum() < 60:
        return None, None, None, None
    y = np.nan_to_num(fwd[mask], nan=0.0, posinf=0.0, neginf=0.0)
    return flist, X[mask], y, flist


class GplearnGenerator(StrategyGenerator):
    """gplearn SymbolicTransformer → factor programs → ExpressionStrategy candidates."""

    name = "symbolic_gplearn"

    def available(self) -> bool:
        try:
            import gplearn  # noqa: F401
            return True
        except Exception:
            return False

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        feats = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        flist, X, y, _ = _feature_matrix(feats, market)
        if flist is None:
            return []
        try:
            from gplearn.genetic import SymbolicTransformer
            n = max(4, min(int(budget), 12))
            st = SymbolicTransformer(
                generations=6, population_size=max(200, 40 * n), hall_of_fame=max(20, 2 * n),
                n_components=n, function_set=_GPLEARN_FUNCS, parsimony_coefficient=0.001,
                max_samples=0.9, random_state=int(seed), n_jobs=1, verbose=0)
            st.fit(X, y)
            progs = list(getattr(st, "_best_programs", []) or [])
        except Exception:
            return []
        out = []
        for i, p in enumerate(progs[:budget]):
            expr = str(p)
            if not expr or expr in [str(feats.columns[0])]:
                continue
            out.append(ExpressionStrategy(
                market=market, features=list(flist), expr=expr, kind="gplearn",
                id=f"gp_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [], "mutations": ["gplearn"]}))
        return out


class PysrGenerator(StrategyGenerator):
    """PySR (SymbolicRegression.jl) → best equations → ExpressionStrategy candidates.

    PySR runs a Julia engine that installs on first fit. `available()` is a cheap import check;
    a Julia/engine failure at fit time simply yields no candidates (best-effort), never a crash.
    Set PYSR_GEN=0 to skip (Julia warm-up is slow on the first cycle)."""

    name = "symbolic_pysr"

    def available(self) -> bool:
        import os
        if os.environ.get("PYSR_GEN", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            import pysr  # noqa: F401
            return True
        except Exception:
            return False

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        feats = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        flist, X, y, _ = _feature_matrix(feats, market)
        if flist is None:
            return []
        try:
            from pysr import PySRRegressor
            n = max(3, min(int(budget), 10))
            model = PySRRegressor(
                niterations=8, populations=8, population_size=33,
                binary_operators=["+", "-", "*", "/"],
                unary_operators=["sqrt", "exp", "log", "sin", "cos"],
                model_selection="best", maxsize=18, progress=False, verbosity=0,
                deterministic=True, parallelism="serial", random_state=int(seed),
                temp_equation_file=True)
            # PySR names variables x0..xn by default → our evaluator binds x{i}
            model.fit(X, y)
            eqs = model.equations_
        except Exception:
            return []
        out = []
        try:
            rows = eqs if not isinstance(eqs, list) else (eqs[0] if eqs else None)
            if rows is None or len(rows) == 0:
                return []
            # take the best few equations by score (PySR sorts; take the top complexity-diverse)
            top = rows.sort_values("score", ascending=False).head(budget) \
                if "score" in rows.columns else rows.tail(budget)
            for i, (_, r) in enumerate(top.iterrows()):
                expr = str(r.get("sympy_format") or r.get("equation") or "").strip()
                if not expr:
                    continue
                out.append(ExpressionStrategy(
                    market=market, features=list(flist), expr=expr, kind="sympy",
                    id=f"pysr_{market.lower()}_{seed}_{i}",
                    provenance={"generation": 0, "parents": [], "mutations": ["pysr"]}))
        except Exception:
            return []
        return out


class OperonGenerator(StrategyGenerator):
    """Operon (pyoperon) — C++ genetic symbolic regression → ExpressionStrategy candidates.

    The direction-equation quest's named third engine (research/direction-equation-quest): Operon
    beats neural SR on NOISY real financial data and is CPU-native + fast (no Julia warm-up, unlike
    PySR). It fits factor = f(features) → next-bar return, then exports each Pareto-front expression
    (infix, Operon's 1-indexed `X1..Xn` remapped to our evaluator's 0-indexed `x0..xn`) as an
    ExpressionStrategy for the SHARED CPCV+DSR+PBO gate. Set OPERON_GEN=0 to skip."""

    name = "symbolic_operon"

    def available(self) -> bool:
        import os
        if os.environ.get("OPERON_GEN", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            import pyoperon  # noqa: F401
            return True
        except Exception:
            return False

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        import re
        feats = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        flist, X, y, _ = _feature_matrix(feats, market)
        if flist is None:
            return []
        try:
            from pyoperon.sklearn import SymbolicRegressor
            model = SymbolicRegressor(
                allowed_symbols="add,sub,mul,div,constant,variable",
                generations=max(5, min(int(budget), 20)), population_size=200,
                max_length=20, offspring_generator="basic", n_threads=2)
            model.fit(X, y)
            front = list(model.pareto_front_ or [])
        except Exception:
            return []

        def _mapvars(expr: str) -> str:               # Operon X1..Xn (1-indexed) → evaluator x0..xn
            return re.sub(r"\bX(\d+)\b", lambda m: f"x{int(m.group(1)) - 1}", expr)

        def _mse(el) -> float:
            try:
                return float(str(el.get("mean_squared_error")))
            except (TypeError, ValueError):
                return 1e18

        out = []
        try:
            for i, el in enumerate(sorted(front, key=_mse)[:budget]):   # best (lowest MSE) first
                expr = _mapvars(str(el.get("model") or "").strip())
                if not expr:
                    continue
                out.append(ExpressionStrategy(
                    market=market, features=list(flist), expr=expr, kind="sympy",
                    id=f"operon_{market.lower()}_{seed}_{i}",
                    provenance={"generation": 0, "parents": [], "mutations": ["operon"]}))
        except Exception:
            return []
        return out
