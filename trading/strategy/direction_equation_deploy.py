"""trading/strategy/direction_equation_deploy.py — P4 of the direction-equation quest: deploy the
CPCV-validated equation as the LIVE, horizon-conditioned direction driver, measured continuously.

Closes the loop the quest describes:
  • PREDICT — load the P3-validated survivor equations (direction_equation.load_equations), evaluate
    them on the latest features, causal-z each factor, apply its `invert` flag, and weight by CPCV
    OOS IC → one bounded direction score in [-1,1] (the discovered equation IS the driver).
  • MEASURE — record every directional call in the Truth Ledger under source "direction_equation"
    so its live per-regime/horizon accuracy is tracked against real forward price.
  • SELF-CORRECT — pass the call through the Mirror Gate: if the ledger shows this source has become
    an anti-signal in this regime, the gate INVERTS it (and tracks the flip on its own record).
  • RE-EVOLVE — reevolve_all() periodically re-runs discover→validate so the equation keeps up.

Reuse-first: equations from direction_equation (P2/P3), Mirror Gate + Truth Ledger from
trading.direction. Bounded by construction — it contributes a nudge to indicator_fusion, never a
hard override, and every call is honest (None when no validated equation exists). Never raises.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from trading.strategy.direction_equation import load_equations
from trading.strategy.generators.expression import _causal_z, eval_expression

_REC_BAR: dict = {}                        # symbol → last bar ts recorded (dedup ledger flooding)


def _rows_to_df(rows) -> pd.DataFrame | None:
    if not rows or len(rows) < 60:
        return None
    a = np.asarray(rows, dtype=float)
    return pd.DataFrame({"open": a[:, 1], "high": a[:, 2], "low": a[:, 3],
                         "close": a[:, 4], "volume": a[:, 5] if a.shape[1] > 5 else 0.0})


def _equation_score(feats: pd.DataFrame, eqs: list[dict], top_k: int = 5) -> float | None:
    """IC-weighted ensemble of the survivor equations' latest causal-z factor (invert-aware) →
    a bounded score in [-1,1]. None if nothing evaluated."""
    num = den = 0.0
    for eq in eqs[:top_k]:
        try:
            raw = eval_expression(eq["expr"], eq["kind"], feats, eq["features"])
            z = _causal_z(pd.Series(np.asarray(raw, dtype=float), index=feats.index))
            zt = float(z.iloc[-1]) if len(z) else 0.0
            if not np.isfinite(zt):
                continue
            s = -zt if eq.get("invert") else zt          # deploy the anti-signal inverted
            w = abs((eq.get("cpcv") or {}).get("cpcv_mean_ic") or eq.get("abs_ic") or 0.1)
            num += s * w
            den += w
        except Exception:
            continue
    if den <= 0:
        return None
    return float(np.tanh(num / den))                     # squash the z-ensemble to [-1,1]


def predict(rows, market: str = "crypto", *, symbol: str = "", segment: str = "futures",
            regime: str | None = None, record: bool = True) -> dict | None:
    """The discovered equation's live direction call for one symbol. Records to the Truth Ledger
    (deduped per bar) and applies the Mirror Gate. Returns {score, direction, gated, horizon,
    n_equations, source, gate} or None when no validated equation / insufficient data."""
    eqs = load_equations(market)
    if not eqs:
        return None
    df = _rows_to_df(rows)
    if df is None:
        return None
    try:
        from trading.strategy.direction_equation import features_bus
        feats = features_bus(df)
    except Exception:
        return None
    score = _equation_score(feats, eqs)
    if score is None:
        return None
    direction = "long" if score > 0.15 else "short" if score < -0.15 else "flat"
    horizon = eqs[0].get("best_horizon")

    if record and direction in ("long", "short") and symbol:
        try:
            bar = int(rows[-1][0])
            if _REC_BAR.get(symbol) != bar:              # one ledger record per symbol per bar
                _REC_BAR[symbol] = bar
                from trading.direction import truth_ledger
                truth_ledger.record(symbol=symbol, market=(market or "crypto").upper(),
                                    segment=segment, direction=direction.upper(),
                                    source="direction_equation", confidence=abs(score),
                                    regime=regime, ref_price=float(rows[-1][4]))
        except Exception:
            pass

    gated, gate_info = direction, {}
    if direction in ("long", "short"):
        try:
            from trading.direction import mirror_gate
            g, gate_info = mirror_gate.apply(direction.upper(), source="direction_equation",
                                             symbol=symbol, market=(market or "crypto").upper(),
                                             segment=segment, regime=regime, confidence=abs(score))
            gated = (g or direction).lower()
        except Exception:
            gated = direction
    return {"score": round(score, 4), "direction": direction, "gated": gated, "horizon": horizon,
            "n_equations": len(eqs), "source": "direction_equation", "gate": gate_info}


def equation_tilt(rows, market: str = "crypto", *, symbol: str = "", segment: str = "futures",
                  regime: str | None = None) -> dict | None:
    """Bounded direction-equation lens for indicator_fusion.fuse(): the Mirror-Gated equation score,
    signed by the gated direction. Returns {tilt∈[-1,1], ...} or None. The fusion applies a small
    fraction of `tilt` so the discovered equation informs — never overrides — the TA confluence."""
    p = predict(rows, market, symbol=symbol, segment=segment, regime=regime)
    if p is None:
        return None
    # honor the Mirror Gate: if it flipped the call, flip the sign; if it abstained, zero the tilt.
    sign = 1.0 if p["gated"] == "long" else -1.0 if p["gated"] == "short" else 0.0
    tilt = sign * abs(p["score"])
    return {"tilt": round(tilt, 4), "score": p["score"], "direction": p["direction"],
            "gated": p["gated"], "horizon": p["horizon"], "n_equations": p["n_equations"]}


def reevolve_all(symbols=(("BTC/USDT", "crypto"), ("ETH/USDT", "crypto")), *, tf: str = "15m",
                 bars: int = 800) -> dict:
    """Periodically re-discover + re-validate the equation per market (keep-the-best, mutate-the-rest).
    Returns {market: n_survivors}. Never raises."""
    from trading.strategy.direction_equation import run_for_market
    out: dict = {}
    for sym, market in symbols:
        try:
            survivors = run_for_market(sym, market, tf=tf, bars=bars)
            out[market] = len(survivors)
        except Exception:
            out[market] = 0
    return out


if __name__ == "__main__":                 # standalone re-evolution daemon
    import os
    import time
    while os.getenv("DIRECTION_EQ_REEVOLVE", "1").strip().lower() not in ("0", "false", "off"):
        res = reevolve_all()
        print("reevolve:", res)
        time.sleep(float(os.getenv("DIRECTION_EQ_REEVOLVE_INTERVAL", "3600")))
