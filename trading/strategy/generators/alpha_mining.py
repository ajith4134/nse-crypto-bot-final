"""trading/strategy/generators/alpha_mining.py — generator ⑤: formulaic-alpha mining.

Research shortlist #1 (highest impact): mine *formulaic alphas* (Alpha101/AlphaGen style) —
expressions over OHLCV built from the rolling operator vocabulary — instead of only tuning a
fixed genome. We reuse AlphaGen's operator set (vendor/alphagen, via alpha_ops.py) and mine
candidate alphas by grammar search, PRE-FILTER them by rank-IC (Spearman vs next-bar return,
`guardrails.information_coefficient`) so only informative factors reach the gate, then wrap the
survivors as ExpressionStrategy(kind="alpha") for the SHARED CPCV+DSR+PBO guardrail.

We reuse AlphaGen's grammar (the transferable part) rather than its RL/PPO training harness,
which needs Qlib China-stock data + torch training — not viable inside a per-cycle CPU breeding
loop. Seeded with a few classic Alpha101-style templates + random grammar samples.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.generators.base import StrategyGenerator
from trading.strategy.generators.expression import ExpressionStrategy, eval_expression

_FIELDS = ["close", "open", "high", "low", "volume", "vwap"]
_WINDOWS = [5, 10, 20, 30]
_UNARY_TS = ["Mean", "Std", "Delta", "Ref", "Max", "Min", "Rank", "WMA", "EMA", "Skew", "Mad"]
_BINARY = ["Sub", "Add", "Mul", "Div", "Greater", "Less"]
_PAIR_TS = ["Corr", "Cov"]
_UNARY = ["Abs", "Sign", "Log"]

# classic Alpha101-style seeds, adapted to single-asset OHLCV
_TEMPLATES = [
    "Div(Delta(close, 5), Ref(close, 5))",                                  # 5-bar momentum
    "Sub(close, Mean(close, 20))",                                          # deviation from MA
    "Corr(close, volume, 10)",                                              # price-volume corr
    "Div(Sub(close, Min(low, 10)), Sub(Max(high, 10), Min(low, 10)))",      # stochastic %K
    "Mul(Sign(Delta(close, 1)), Std(close, 10))",                          # signed volatility
    "Rank(Delta(close, 5), 20)",                                           # ranked momentum
    "Div(Sub(vwap, close), Mean(Abs(Sub(vwap, close)), 20))",             # vwap pressure
    "Mul(Delta(volume, 5), Sign(Delta(close, 5)))",                       # signed volume flow
]


def _rand_expr(rng, depth: int) -> str:
    if depth <= 0 or rng.random() < 0.25:
        return str(rng.choice(_FIELDS))
    r = rng.random()
    w = int(rng.choice(_WINDOWS))
    if r < 0.45:
        return f"{rng.choice(_UNARY_TS)}({_rand_expr(rng, depth - 1)}, {w})"
    if r < 0.75:
        return f"{rng.choice(_BINARY)}({_rand_expr(rng, depth - 1)}, {_rand_expr(rng, depth - 1)})"
    if r < 0.9:
        return f"{rng.choice(_PAIR_TS)}({_rand_expr(rng, depth - 1)}, {_rand_expr(rng, depth - 1)}, {w})"
    return f"{rng.choice(_UNARY)}({_rand_expr(rng, depth - 1)})"


class AlphaMiningGenerator(StrategyGenerator):
    """Mine + IC-filter formulaic alphas → ExpressionStrategy(alpha) candidates."""

    name = "alpha_mining"

    def available(self) -> bool:
        import os
        return os.environ.get("ALPHA_MINING", "1") in ("1", "true", "TRUE", "yes", "on")

    def generate(self, ohlcv, market, *, features=None, budget=12, seed=0, **kw):
        df = features if features is not None else __import__(
            "trading.strategy.features", fromlist=["compute_features"]).compute_features(ohlcv)
        if "close" not in df.columns:
            return []
        from trading.strategy.guardrails import information_coefficient
        fwd = df["close"].pct_change().shift(-1).to_numpy(dtype=float)
        rng = np.random.default_rng(int(seed))

        # candidate pool = templates + random grammar samples
        exprs = list(_TEMPLATES)
        for _ in range(max(24, budget * 4)):
            exprs.append(_rand_expr(rng, depth=3))

        scored = []
        seen = set()
        for expr in exprs:
            if expr in seen or "(" not in expr:      # require ≥1 operator (skip bare fields)
                continue
            seen.add(expr)
            try:
                vals = eval_expression(expr, "alpha", df, _FIELDS).to_numpy(dtype=float)
                ic = information_coefficient(vals, fwd)
            except Exception:
                continue
            if np.isfinite(ic) and abs(ic) > 0.02:
                scored.append((abs(ic), ic, expr))
        scored.sort(reverse=True)

        out = []
        for i, (aic, ic, expr) in enumerate(scored[:max(4, min(int(budget), 12))]):
            # negative-IC alphas trade the inverse: flip thresholds so the signal is aligned
            long_thr, short_thr = (0.5, -0.5) if ic >= 0 else (-0.5, 0.5)
            out.append(ExpressionStrategy(
                market=market, features=list(_FIELDS), expr=expr, kind="alpha",
                long_thr=long_thr, short_thr=short_thr, id=f"alpha_{market.lower()}_{seed}_{i}",
                provenance={"generation": 0, "parents": [], "mutations": ["alpha_mining"],
                            "ic": round(float(ic), 4)}))
        return out
