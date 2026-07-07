"""trading/strategy/generators/expression.py — a candidate whose signal is a discovered
formula over features (used by the symbolic-regression, formulaic-alpha, and RD-Agent
generators). It satisfies the same tiny candidate contract as the DEAP genome (`.signal()`,
`.to_dict()`/`from_dict`), so it flows through the SAME CPCV+DSR+PBO guardrail and into the
SkillLibrary + brain pipeline unchanged.

The formula is stored as a STRING over the feature columns (plus a `kind` naming the dialect:
gplearn's function-call form `add(X0, mul(X1,X2))`, PySR/sympy infix `x0 + x1*x2`, or an
`alpha` expression over the operator library). `signal()` re-evaluates the formula on any new
OHLCV/features frame — so it is fully serialisable AND causal, and re-computes live, not frozen.

Evaluation is sandboxed: a fixed namespace of protected math ops (gplearn semantics) + the
feature Series bound to `X{i}` / `x{i}` / the feature name, and NO builtins. The raw formula
value is causally z-scored (expanding window — no look-ahead) then thresholded to +1/-1/0.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from trading.strategy.generators.base import register_candidate_type


# ── protected operator namespace (gplearn-compatible; safe on pandas Series) ──────
def _protected_div(a, b):
    b = np.where(np.abs(b) > 1e-6, b, 1.0) if not hasattr(b, "where") else b.where(np.abs(b) > 1e-6, 1.0)
    return a / b


def _protected_sqrt(a):
    return np.sqrt(np.abs(a))


def _protected_log(a):
    aa = np.abs(a)
    return np.where(aa > 1e-6, np.log(aa), 0.0) if not hasattr(a, "index") \
        else pd.Series(np.where(aa > 1e-6, np.log(aa), 0.0), index=a.index)


def _protected_inv(a):
    return _protected_div(1.0, a)


_EXPR_FUNCS = {
    "add": lambda a, b: a + b, "sub": lambda a, b: a - b, "mul": lambda a, b: a * b,
    "div": _protected_div, "sqrt": _protected_sqrt, "log": _protected_log,
    "abs": lambda a: np.abs(a), "neg": lambda a: -a, "inv": _protected_inv,
    "sin": lambda a: np.sin(a), "cos": lambda a: np.cos(a), "tan": lambda a: np.tan(a),
    "exp": lambda a: np.exp(np.clip(a, -50, 50)),
    "max": lambda a, b: np.maximum(a, b), "min": lambda a, b: np.minimum(a, b),
    "sign": lambda a: np.sign(a),
    # sympy-capitalised aliases (PySR exports sympy strings: Abs/Max/Min/sqrt/…)
    "Abs": lambda a: np.abs(a), "Max": lambda a, b: np.maximum(a, b),
    "Min": lambda a, b: np.minimum(a, b), "sqrt": _protected_sqrt, "log": _protected_log,
}


def _causal_z(s: pd.Series, *, min_periods: int = 20) -> pd.Series:
    """Expanding-window z-score (no look-ahead). Warm-up bars are neutral (0)."""
    s = pd.Series(np.asarray(s, dtype=float))
    mean = s.expanding(min_periods=min_periods).mean()
    std = s.expanding(min_periods=min_periods).std()
    return ((s - mean) / std.replace(0.0, np.nan)).fillna(0.0)


def eval_expression(expr: str, kind: str, df: pd.DataFrame, features: list) -> pd.Series:
    """Evaluate a discovered formula string over `features` of `df` → a raw value Series.

    Sandboxed: only the protected ops + the feature Series are in scope (no builtins). Feature i
    is bound to `X{i}`, `x{i}`, and its real name so any generator's dialect resolves. For
    kind='alpha' the scope is instead the formulaic-alpha operators over OHLCV fields."""
    if kind == "alpha":
        from trading.strategy.generators.alpha_ops import alpha_namespace
        ns = alpha_namespace(df)
        try:
            out = eval(expr, {"__builtins__": {}}, ns)  # noqa: S307 — sandboxed, generator-produced
        except Exception:
            return pd.Series(0.0, index=df.index)
        if np.isscalar(out):
            return pd.Series(float(out), index=df.index)
        return pd.Series(np.asarray(out, dtype=float), index=df.index).replace(
            [np.inf, -np.inf], np.nan).fillna(0.0)
    ns = dict(_EXPR_FUNCS)
    for i, f in enumerate(features):
        col = pd.Series(np.asarray(df[f], dtype=float), index=df.index) if f in df.columns \
            else pd.Series(0.0, index=df.index)
        ns[f"X{i}"] = col
        ns[f"x{i}"] = col
        ns[str(f)] = col
    try:
        out = eval(expr, {"__builtins__": {}}, ns)  # noqa: S307 — sandboxed, generator-produced
    except Exception:
        return pd.Series(0.0, index=df.index)
    if np.isscalar(out):
        return pd.Series(float(out), index=df.index)
    return pd.Series(np.asarray(out, dtype=float), index=df.index).fillna(0.0)


@register_candidate_type("expression")
@dataclass
class ExpressionStrategy:
    """A candidate whose long/short signal is a threshold on a discovered formula value."""

    market: str
    features: list
    expr: str
    kind: str = "sympy"                 # gplearn | sympy | alpha | rdagent
    long_thr: float = 0.5               # z-score thresholds (causal)
    short_thr: float = -0.5
    allow_short: bool = True
    id: str = ""
    provenance: dict = field(default_factory=lambda: {"generation": 0, "parents": [],
                                                      "mutations": []})

    def signal(self, df: pd.DataFrame) -> pd.Series:
        raw = eval_expression(self.expr, self.kind, df, self.features)
        z = _causal_z(raw)
        out = pd.Series(0, index=df.index, dtype=int)
        out[z >= self.long_thr] = 1
        if self.allow_short:
            out[z <= self.short_thr] = -1
        return out

    def to_dict(self) -> dict:
        return {"__type__": "expression", "market": self.market, "features": list(self.features),
                "expr": self.expr, "kind": self.kind, "long_thr": self.long_thr,
                "short_thr": self.short_thr, "allow_short": self.allow_short, "id": self.id,
                "provenance": self.provenance}

    @classmethod
    def from_dict(cls, d: dict) -> "ExpressionStrategy":
        return cls(market=d["market"], features=list(d["features"]), expr=d["expr"],
                   kind=d.get("kind", "sympy"), long_thr=d.get("long_thr", 0.5),
                   short_thr=d.get("short_thr", -0.5), allow_short=d.get("allow_short", True),
                   id=d.get("id", ""),
                   provenance=d.get("provenance", {"generation": 0, "parents": [], "mutations": []}))
