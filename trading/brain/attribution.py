"""Per-trade feature attribution — WHICH data led to this decision and HOW MUCH.

Engine: SHAP (github.com/shap/shap, pip 0.48) KernelExplainer over TradeOutcomeNet's
vector-level probability (`_proba`), the same net that predicts trade outcomes from the
42 pre-trade features in trading/brain/trade_features.py. Falls back to a deterministic
occlusion attribution (feature → background mean, Δp_win) when shap is unavailable or
the net is untrained — the journal column is never silently empty for a trained net.

The result is qlib-recorder-style "attribution record" JSON stored per trade
(feature_attribution column + episode.attribution in decision_memory).
"""
from __future__ import annotations

from trading.brain.trade_features import FEATURE_NAMES, get_outcome_net, trade_feature_row

_TOP_K = 8          # keep the strongest drivers only — the full 42-vector is noise in a cell
_NSAMPLES = 128     # SHAP sampling budget per explanation (CPU: ~100ms class)
_BG_ROWS = 40       # background sample size for the explainers


def _background(closed_rows: list[dict]) -> list[list[float]]:
    rows = closed_rows[-_BG_ROWS:] if closed_rows else []
    return [trade_feature_row(r) for r in rows] or [[0.0] * len(FEATURE_NAMES)]


def explain_trade(trade: dict, closed_rows: list[dict], *, fast: bool = False) -> dict:
    """Attribution record for one (open or closed) trade row.

    Returns {"engine", "p_win", "top": [{"feature", "value", "impact"}...]} where impact
    is the signed contribution of that feature to p_win vs the background baseline.

    fast=True (live entry hot paths — loop tick / brain-executor cycle): NEVER trains the
    outcome net inline (a 1000+-row retrain takes minutes and starves the shared server);
    reuses the cached net when warm, else records an honest "cold-skip".
    """
    if fast:
        from trading.brain import trade_features as _tf
        net = _tf._CACHE.get("net")
        if net is None or not net.trained:
            return {"engine": "cold-skip", "p_win": None, "top": []}
    else:
        net = get_outcome_net(closed_rows)
    x = trade_feature_row(trade)
    if not net.trained:
        return {"engine": "untrained", "p_win": None, "top": []}
    bg = _background(closed_rows)
    try:
        if fast:
            raise RuntimeError("fast path → occlusion (42 net calls, no SHAP sampling)")
        import numpy as np
        import shap

        f = lambda X: np.asarray([net._proba(list(row)) for row in X])
        expl = shap.KernelExplainer(f, np.asarray(bg))
        sv = expl.shap_values(np.asarray([x]), nsamples=_NSAMPLES, silent=True)
        impacts = list(map(float, np.asarray(sv).reshape(-1)))
        engine = "shap-kernel"
    except Exception:
        # occlusion fallback: replace each feature with the background mean, measure Δp
        base = [sum(col) / len(bg) for col in zip(*bg)]
        p0 = net._proba(x)
        impacts = []
        for i in range(len(x)):
            xi = list(x)
            xi[i] = base[i]
            impacts.append(p0 - net._proba(xi))
        engine = "occlusion"
    pairs = sorted(zip(FEATURE_NAMES, x, impacts), key=lambda t: -abs(t[2]))[:_TOP_K]
    return {"engine": engine,
            "p_win": round(float(net._proba(x)), 4),
            "top": [{"feature": n, "value": round(float(v), 6),
                     "impact": round(float(im), 6)} for n, v, im in pairs if im]}
