"""Rollout engine — CANON-47/48 (KRF-18/21/22).

* autoregressive_rollout — predict -> append the prediction back into the
  window -> repeat, k steps (the videos' multi-candle rollout; skforecast
  recursive semantics copied, not the dep).
* Direct multi-horizon support: if the model emits an (H,) vector in one call
  (a direct multi-output head, CANON-48), that vector is used directly.
* per_horizon_errors — MAE/RMSE per horizon from (N, H) true/pred matrices,
  the honest way to see rollout error compounding.
* Floors: naive persistence (repeat last value) always available; if
  trading.fitness ships baseline helpers they are used lazily; a fitted
  DLinearNode (nodes.video_lanes) can be plugged in via `floor_model`.
"""
from __future__ import annotations

import numpy as np


def _call_model(model, window: np.ndarray) -> np.ndarray:
    """Call a model on one window. Accepts a plain callable, or objects with
    rollout_step / predict. Returns a 1-D array (scalar -> shape (1,))."""
    if callable(model) and not hasattr(model, "predict"):
        out = model(window)
    elif hasattr(model, "rollout_step"):
        out = model.rollout_step(window)
    elif hasattr(model, "predict"):
        out = model.predict(window[None, ...] if window.ndim >= 1 else window)
    else:                                                    # pragma: no cover
        raise TypeError(f"unsupported model type: {type(model)!r}")
    return np.asarray(out, float).reshape(-1)


def _default_update(window: np.ndarray, pred: float) -> np.ndarray:
    """Shift the window one step and append the prediction.

    Univariate (L,): drop oldest, append pred. Multivariate (L, F): drop the
    oldest row and append a new row that copies the last row with column 0
    (the target/price column by convention) replaced by pred — callers with a
    richer feature-update rule pass their own update_fn."""
    if window.ndim == 1:
        return np.append(window[1:], pred)
    new_row = window[-1].copy()
    new_row[0] = pred
    return np.vstack([window[1:], new_row])


def autoregressive_rollout(model, window, k: int, update_fn=None) -> np.ndarray:
    """CANON-47: feed predictions back into the window, k candles ahead.

    model: callable(window)->scalar/vector, or object with rollout_step/predict.
    window: (lookback,) or (lookback, F) — NOT mutated.
    Direct-head shortcut (CANON-48): if the FIRST call returns a vector with
    >= k values, that direct multi-horizon output is returned (first k values)
    without any feedback loop."""
    window = np.asarray(window, float).copy()
    k = int(k)
    assert k >= 1, "k must be >= 1"
    update = update_fn or _default_update
    first = _call_model(model, window)
    if first.size >= k and first.size > 1:                   # direct (H,) head
        return first[:k].copy()
    preds = [float(first[0])]
    for _ in range(k - 1):                                   # predict->append
        window = update(window, preds[-1])
        preds.append(float(_call_model(model, window)[0]))
    out = np.asarray(preds, float)
    assert out.shape == (k,), f"rollout produced {out.shape}, expected ({k},)"
    return out


def per_horizon_errors(y_true_matrix, y_pred_matrix) -> dict:
    """(N, H) true vs pred -> {'mae': (H,), 'rmse': (H,)} numpy arrays —
    shows how error compounds with horizon (the honest rollout scorecard)."""
    T = np.asarray(y_true_matrix, float)
    P = np.asarray(y_pred_matrix, float)
    if T.ndim == 1:
        T = T[None, :]
    if P.ndim == 1:
        P = P[None, :]
    assert T.shape == P.shape, f"shape mismatch {T.shape} vs {P.shape}"
    err = P - T
    return {"mae": np.abs(err).mean(axis=0),
            "rmse": np.sqrt((err ** 2).mean(axis=0))}


# --------------------------------------------------------------------------- #
#  Honesty floors (CANON-36): persistence always; DLinear when provided
# --------------------------------------------------------------------------- #
def persistence_rollout(window, k: int) -> np.ndarray:
    """Naive floor: repeat the last observed target value k times."""
    w = np.asarray(window, float)
    last = float(w[-1] if w.ndim == 1 else w[-1, 0])
    return np.full(int(k), last)


def compare_to_floors(model, windows, y_true_matrix, k: int,
                      floor_model=None, update_fn=None) -> dict:
    """Roll the model AND the floors over a batch of windows; return the
    per-horizon error dicts side by side. Beats-persistence is the minimum
    bar for any trust (CANON-36); floor_model (e.g. a fitted DLinearNode)
    adds the DLinear floor.

    If trading.fitness exposes baseline helpers they win (lazy import — that
    module is built in B1 by another lane); otherwise the self-contained
    persistence floor above is used."""
    windows = [np.asarray(w, float) for w in windows]
    T = np.asarray(y_true_matrix, float)
    assert T.shape == (len(windows), int(k)), \
        f"y_true_matrix {T.shape} != ({len(windows)}, {k})"
    model_preds = np.stack([autoregressive_rollout(model, w, k, update_fn)
                            for w in windows])
    try:                                                     # lazy, optional
        from trading.fitness import persistence_baseline    # type: ignore
        pers_preds = np.stack([np.asarray(persistence_baseline(w, k), float)
                               for w in windows])
    except Exception:
        pers_preds = np.stack([persistence_rollout(w, k) for w in windows])
    out = {"model": per_horizon_errors(T, model_preds),
           "persistence": per_horizon_errors(T, pers_preds),
           "beats_persistence": bool(
               np.abs(model_preds - T).mean() < np.abs(pers_preds - T).mean())}
    if floor_model is not None:
        dl_preds = np.stack([autoregressive_rollout(floor_model, w, k,
                                                    update_fn)
                             for w in windows])
        out["dlinear"] = per_horizon_errors(T, dl_preds)
        out["beats_dlinear"] = bool(
            np.abs(model_preds - T).mean() < np.abs(dl_preds - T).mean())
    return out
