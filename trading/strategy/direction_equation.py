"""trading/strategy/direction_equation.py — P2 of the direction-equation quest: discover ONE
reliable direction equation and score it by horizon-conditioned Rank-IC (out-of-sample).

The quest (research/direction-equation-quest/): most naive signals are coin-flips because they
capture MAGNITUDE, not SIGN, and because the optimal signal SHIFTS with the forecast horizon.
This orchestrator answers both:

  1. DISCOVER — fan the feature bus (order-flow + Volume-Profile + indicators, via
     trading.strategy.features.compute_features) through the symbolic-regression generators
     (gplearn / Operon / PySR — each evolves the expression tree itself) on a TRAIN split.
  2. SCORE — evaluate every discovered equation's RAW factor on a held-out OOS split and measure
     **Rank-IC (Spearman)** against forward returns AT EACH HORIZON (1/4/12/24 bars). The best
     horizon and the SIGN are recorded — a strongly negative IC is an invertible edge, not noise
     (per the 40%-accuracy anti-signal finding, direction-accuracy-program).
  3. KEEP — rank by |OOS best-horizon IC|, keep top-K, persist per market for the P4 deploy.

Reuse-first: generators = trading.strategy.generators (already built), raw factor =
expression.eval_expression, Rank-IC = guardrails.information_coefficient (Spearman). Honest by
construction: too little data → empty result; a broken equation is skipped, never crashes the run.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading import state
from trading.strategy.generators.expression import eval_expression
from trading.strategy.guardrails import information_coefficient

DEFAULT_HORIZONS = (1, 4, 12, 24)          # bars ahead — the metric shifts with horizon (quest)
_EQ_FILE = "direction_equations.json"      # persisted top-K per market (for P4 deploy)


def _forward_return(close: pd.Series, h: int) -> np.ndarray:
    """h-bar forward return, aligned to the current bar (no look-ahead: value at t uses t→t+h)."""
    c = close.to_numpy(dtype=float)
    fwd = np.full(len(c), np.nan)
    if h < len(c):
        fwd[:-h] = c[h:] / np.where(c[:-h] == 0, np.nan, c[:-h]) - 1.0
    return fwd


def horizon_ic(raw: pd.Series, close: pd.Series, h: int) -> float:
    """Rank-IC (Spearman) of a raw factor vs the h-bar forward return."""
    return information_coefficient(np.asarray(raw, dtype=float), _forward_return(close, h))


def _equation_generators():
    """The symbolic-regression generators that produce interpretable EQUATIONS (the quest's goal).
    gplearn + Operon are fast/CPU-native; PySR is included when its Julia engine is present."""
    from trading.strategy.generators.symbolic import (GplearnGenerator, OperonGenerator,
                                                       PysrGenerator)
    gens = []
    for cls in (GplearnGenerator, OperonGenerator, PysrGenerator):
        try:
            g = cls()
            if g.available():
                gens.append(g)
        except Exception:
            continue
    return gens


def score_equation(cand, feats_oos: pd.DataFrame, close_oos: pd.Series,
                   horizons=DEFAULT_HORIZONS) -> dict | None:
    """OOS per-horizon Rank-IC for one candidate equation. Returns the score record, or None if
    the equation can't be evaluated / has no usable variance."""
    try:
        raw = eval_expression(cand.expr, cand.kind, feats_oos, cand.features)
    except Exception:
        return None
    raw = pd.Series(np.asarray(raw, dtype=float), index=feats_oos.index)
    if not np.isfinite(raw.to_numpy()).any() or float(np.nanstd(raw.to_numpy())) == 0.0:
        return None
    ics = {}
    for h in horizons:
        try:
            ics[h] = round(horizon_ic(raw, close_oos, h), 4)
        except Exception:
            ics[h] = 0.0
    if not ics:
        return None
    best_h = max(ics, key=lambda h: abs(ics[h]))
    best_ic = ics[best_h]
    return {
        "id": getattr(cand, "id", ""), "expr": cand.expr, "kind": cand.kind,
        "features": list(cand.features), "market": getattr(cand, "market", ""),
        "ic_by_horizon": ics, "best_horizon": best_h, "best_ic": best_ic,
        "invert": best_ic < 0,                       # negative IC = invertible anti-signal
        "abs_ic": round(abs(best_ic), 4),
        "mean_abs_ic": round(float(np.mean([abs(v) for v in ics.values()])), 4),
        "provenance": getattr(cand, "provenance", {}),
    }


def discover(ohlcv: pd.DataFrame, market: str = "crypto", *, horizons=DEFAULT_HORIZONS,
             budget: int = 10, seed: int = 0, top_k: int = 8, test_frac: float = 0.3,
             generators=None, min_abs_ic: float = 0.0) -> list[dict]:
    """Discover + OOS-Rank-IC-score direction equations; return the top-K (best |IC| first).

    Generators fit on the TRAIN split; every discovered equation is scored on the untouched OOS
    tail so the ranking is honest. `min_abs_ic` drops equations weaker than a floor (0 = keep all)."""
    from trading.strategy.features import compute_features
    feats = compute_features(ohlcv)
    n = len(feats)
    if n < 120:                                      # need enough for train + OOS + max horizon
        return []
    split = int(n * (1.0 - test_frac))
    if split < 60 or (n - split) < (max(horizons) + 30):
        return []
    train_ohlcv = ohlcv.iloc[:split]
    feats_oos = feats.iloc[split:]
    close_oos = feats_oos["close"] if "close" in feats_oos.columns else None
    if close_oos is None:
        return []

    cands = []
    for g in (generators if generators is not None else _equation_generators()):
        try:
            cands.extend(g.generate(train_ohlcv, market, budget=budget, seed=seed) or [])
        except Exception:
            continue

    scored = []
    seen_expr: set = set()
    for c in cands:
        key = (getattr(c, "kind", ""), str(getattr(c, "expr", "")))
        if key in seen_expr:                         # dedup identical equations across generators
            continue
        seen_expr.add(key)
        rec = score_equation(c, feats_oos, close_oos, horizons)
        if rec and rec["abs_ic"] >= min_abs_ic:
            scored.append(rec)
    scored.sort(key=lambda s: s["abs_ic"], reverse=True)
    return scored[:top_k]


def save_equations(market: str, ranked: list[dict]) -> None:
    """Persist the top-K equations for a market (P4 deploy reads these)."""
    store = state.load_json(_EQ_FILE, {}) or {}
    store[market] = {"ts": _now(), "equations": ranked}
    state.save_json(_EQ_FILE, store)


def load_equations(market: str) -> list[dict]:
    """The persisted top-K equations for a market (empty if none discovered yet)."""
    store = state.load_json(_EQ_FILE, {}) or {}
    return (store.get(market) or {}).get("equations", [])


def _now() -> float:
    import time
    return time.time()


def discover_and_save(ohlcv: pd.DataFrame, market: str = "crypto", **kw) -> list[dict]:
    """Convenience: discover → persist → return the top-K for `market`."""
    ranked = discover(ohlcv, market, **kw)
    if ranked:
        save_equations(market, ranked)
    return ranked


def _ohlcv_for(symbol: str, market: str, tf: str, bars: int) -> pd.DataFrame | None:
    """Fetch OHLCV → DataFrame via the shared data lane (reuses indicator_fusion._fetch)."""
    try:
        from trading.broker_sense import indicator_fusion
        rows = indicator_fusion._fetch(symbol, market, tf, bars=bars)
    except Exception:
        rows = None
    if not rows or len(rows) < 120:
        return None
    a = np.asarray(rows, dtype=float)
    return pd.DataFrame({"open": a[:, 1], "high": a[:, 2], "low": a[:, 3],
                         "close": a[:, 4], "volume": a[:, 5] if a.shape[1] > 5 else 0.0})


def run_for_market(symbol: str, market: str = "crypto", *, tf: str = "15m", bars: int = 800,
                   **kw) -> list[dict]:
    """Fetch real OHLCV for a representative symbol, discover + Rank-IC-score, persist top-K.
    Returns the ranked equations (empty on no data / no edge). Never raises."""
    try:
        df = _ohlcv_for(symbol, market, tf, bars)
        if df is None:
            return []
        return discover_and_save(df, market, **kw)
    except Exception:
        return []


if __name__ == "__main__":                 # ad-hoc run: discover equations for the majors
    for _sym, _mkt in (("BTC/USDT", "crypto"), ("ETH/USDT", "crypto")):
        _eqs = run_for_market(_sym, _mkt)
        print(f"{_sym}: {len(_eqs)} equations; "
              f"best |IC|={_eqs[0]['abs_ic'] if _eqs else 0} @ h={_eqs[0]['best_horizon'] if _eqs else '-'}")
