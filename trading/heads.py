"""CORTEX B6 — forecast heads: direct + autoregressive rollout on foundation nodes.

Design §1 T5 (CANON-44/48/36): every head produces a k-step forecast either DIRECTLY
(one multi-horizon call, CANON-48) or AUTOREGRESSIVELY (feed prediction back, CANON-47),
and must beat the persistence floor AND a DLinear floor (Diebold–Mariano, CANON-36) before
the trust ledger will weight it. This module is the thin adapter that turns the existing
zero-shot foundation nodes (nodes/foundation_nodes.py — TinyTimeMixer, Chronos, TimesFM,
Moirai; nodes/dl_nodes.py — TabPFN) into rollout heads over trading/rollout.py's engine,
and the gate that scores a head against the floors.

Foundation nodes are classifier-framed (their public .fit rejects a continuous target), so
heads drive their pure forecasting internals `_fit_forecaster(y)` + `_forecast(h)` directly.
Any plain callable `(y, k) -> array` or object with `.predict` also works, so tests need no
network / model weights.
"""
from __future__ import annotations

import numpy as np

from trading.rollout import autoregressive_rollout, compare_to_floors

__all__ = ["RolloutHead", "evaluate_head", "build_foundation_heads"]


class RolloutHead:
    """Wrap a forecaster as a direct-or-AR k-step rollout head.

    forecaster may be:
      * a foundation node exposing `_fit_forecaster(y)` + `_forecast(h)` (fit-per-window,
        zero-shot models cost ~nothing to "fit"), or
      * a callable `(y, k) -> array-like` (length >= k), or
      * an object with `.predict(y)` returning the next value.
    col : the target column when a window is 2-D (price by convention = 0).
    direct : True -> one multi-horizon call; False -> autoregressive feedback rollout.
    """

    def __init__(self, forecaster, *, name: str, direct: bool = True, col: int = 0):
        self.f = forecaster
        self.name = str(name)
        self.direct = bool(direct)
        self.col = int(col)
        self.fell_back = False

    # -- series extraction ---------------------------------------------------
    def _series(self, window) -> np.ndarray:
        w = np.asarray(window, dtype=float)
        return (w if w.ndim == 1 else w[:, self.col]).astype(float)

    # -- one direct multi-horizon forecast -----------------------------------
    def forecast(self, window, k: int) -> np.ndarray:
        y = self._series(window)
        k = int(k)
        node = self.f
        try:
            if hasattr(node, "_fit_forecaster") and hasattr(node, "_forecast"):
                node._fit_forecaster(y)                       # zero-shot: cheap
                out = np.asarray(node._forecast(k), dtype=float).reshape(-1)
            elif callable(node):
                out = np.asarray(node(y, k), dtype=float).reshape(-1)
            elif hasattr(node, "predict"):
                out = np.asarray(node.predict(y), dtype=float).reshape(-1)
            else:                                             # pragma: no cover
                raise TypeError(f"unsupported forecaster {type(node)!r}")
            self.fell_back = bool(getattr(node, "fell_back", False))
        except Exception:                                     # honest floor, never crash
            self.fell_back = True
            out = np.full(k, y[-1])                           # persistence fallback
        if out.size < k:                                      # pad short direct heads
            out = np.concatenate([out, np.full(k - out.size, out[-1] if out.size else y[-1])])
        return out[:k].astype(float)

    # -- rollout.py hooks ----------------------------------------------------
    def rollout_step(self, window) -> np.ndarray:
        """One-step forecast — lets rollout.autoregressive_rollout drive AR mode."""
        return self.forecast(window, 1)[:1]

    def rollout(self, window, k: int) -> np.ndarray:
        """k-step rollout in this head's configured mode."""
        if self.direct:
            return self.forecast(window, k)
        return autoregressive_rollout(self, window, k)


def evaluate_head(head: RolloutHead, windows, y_true_matrix, k: int,
                  floor_model=None, p_max: float = 0.10) -> dict:
    """Score a head against the persistence + DLinear floors + a DM significance gate.

    Reuses rollout.compare_to_floors for the per-horizon error comparison and
    trading.fitness.persistence_gate for the Diebold–Mariano significance test on the
    first-horizon path. `trusted` requires beating persistence AND (if a floor_model is
    given) DLinear AND passing the DM gate — the minimum bar for trust (CANON-36).
    """
    windows = [np.asarray(w, dtype=float) for w in windows]
    T = np.asarray(y_true_matrix, dtype=float)
    if T.ndim == 1:
        T = T.reshape(len(windows), -1)

    cmp = compare_to_floors(lambda w: head.rollout(w, k), windows, T, k,
                            floor_model=floor_model)

    # DM significance on the first-horizon forecasts vs realized (directional-honest)
    preds1 = np.array([head.rollout(w, k)[0] for w in windows], dtype=float)
    truth1 = T[:, 0]
    dm_ok, dm_detail = False, {"skipped": "no persistence_gate"}
    try:
        from trading.fitness import persistence_gate
        dm_ok, dm_detail = persistence_gate(truth1, preds1, p_max=p_max)
    except Exception:                                         # pragma: no cover
        pass

    beats_pers = bool(cmp.get("beats_persistence", False))
    beats_dl = bool(cmp.get("beats_dlinear", True))          # True when no floor_model
    trusted = beats_pers and beats_dl and (dm_ok or "skipped" in dm_detail)
    return {
        "head": head.name,
        "beats_persistence": beats_pers,
        "beats_dlinear": beats_dl,
        "dm_gate": dm_ok,
        "dm_detail": dm_detail,
        "per_horizon": {kk: {m: np.asarray(v).tolist() for m, v in vv.items()}
                        for kk, vv in cmp.items() if isinstance(vv, dict)},
        "fell_back": head.fell_back,
        "trusted": bool(trusted),
    }


def build_foundation_heads(*, direct: bool = True, col: int = 0) -> dict:
    """Build the TTM / Chronos / TabPFN rollout heads, lazily and crash-free.

    Each head wraps its foundation node; a node whose weights can't be fetched degrades
    to the head's own persistence floor at call time (never a crash), so the registry is
    always complete. Returns {name: RolloutHead}.
    """
    heads: dict[str, RolloutHead] = {}
    specs = [
        ("ttm", "nodes.foundation_nodes", "TinyTimeMixerNode"),
        ("chronos", "nodes.foundation_nodes", "ChronosNode"),
        ("timesfm", "nodes.foundation_nodes", "TimesFMNode"),
    ]
    import importlib
    for name, mod, cls in specs:
        try:
            node = getattr(importlib.import_module(mod), cls)()
            heads[name] = RolloutHead(node, name=name, direct=direct, col=col)
        except Exception:                                     # pragma: no cover
            continue
    return heads
