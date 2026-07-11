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


_NON_FEATURE = {"open", "high", "low", "close", "volume", "ts", "time", "date", "timestamp"}


def _feature_matrix(feats: pd.DataFrame, market: str):
    """Ordered feature list (X0..Xn) + a clean numeric matrix + next-bar return target.

    The variable set = the numeric NON-OHLCV columns of the PASSED feature frame (so a caller that
    hands a rich frame — order-flow + Volume-Profile + extended TA, e.g. the direction-equation
    orchestrator — gets those variables, while the base foundry frame yields the base set). X{i}
    indexing lines up with what ExpressionStrategy binds at signal time. No-forward-return rows dropped."""
    import pandas as _pd
    flist = [c for c in feats.columns
             if c not in _NON_FEATURE and _pd.api.types.is_numeric_dtype(feats[c])]
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


class SindyGenerator(StrategyGenerator):
    """SINDy (pysindy) — sparse identification: sparse polynomial regression of next-bar return on
    the feature bus → a compact interpretable equation (COVERAGE-AUDIT gap D; a named quest engine).

    Uses pysindy's PolynomialLibrary(degree 2) + STLSQ sparse optimizer directly (the supervised
    y=f(X) path, not the ODE wrapper), at a few sparsity thresholds → complexity-diverse equations,
    each exported as an ExpressionStrategy(sympy). Set SINDY_GEN=0 to skip."""

    name = "symbolic_sindy"

    def available(self) -> bool:
        import os
        if os.environ.get("SINDY_GEN", "1") not in ("1", "true", "TRUE", "yes", "on"):
            return False
        try:
            import pysindy  # noqa: F401
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
            import pysindy as ps
            # degree 2 only when the variable set is small (else the polynomial library explodes);
            # linear sparse regression over the rich bus otherwise.
            degree = 2 if len(flist) <= 12 else 1
            lib = ps.PolynomialLibrary(degree=degree, include_bias=False)
            theta = np.asarray(lib.fit_transform(X), dtype=float)
            names = lib.get_feature_names(input_features=[f"x{i}" for i in range(len(flist))])
            # standardize columns + target so STLSQ thresholds are SCALE-FREE (forward return is
            # ~1e-2 → absolute thresholds would zero everything); map coefs back to raw space after.
            col_std = theta.std(axis=0)
            col_std[col_std == 0] = 1.0
            y_arr = np.asarray(y, dtype=float)
            y_std = float(y_arr.std()) or 1.0
            theta_n = theta / col_std
        except Exception:
            return []
        out = []
        thresholds = [0.03, 0.06, 0.12, 0.2][:max(1, min(int(budget), 4))]
        for ti, thr in enumerate(thresholds):
            try:
                opt = ps.STLSQ(threshold=thr)
                opt.fit(theta_n, (y_arr / y_std).reshape(-1, 1))
                coef = np.asarray(opt.coef_, dtype=float).ravel() * y_std / col_std   # → raw space
            except Exception:
                continue
            terms = []
            for j in range(min(len(coef), len(names))):
                if abs(coef[j]) > 1e-9:
                    term = names[j].replace("^", "**").replace(" ", "*")   # "x0 x1"→x0*x1, "x0^2"→x0**2
                    terms.append(f"({coef[j]:.6g})*{term}")
            if not terms:
                continue
            out.append(ExpressionStrategy(
                market=market, features=list(flist), expr=" + ".join(terms), kind="sympy",
                id=f"sindy_{market.lower()}_{seed}_{ti}",
                provenance={"generation": 0, "parents": [], "mutations": ["sindy"]}))
        return out
