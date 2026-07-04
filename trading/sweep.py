"""Logged hyperparameter / lookback / topology sweep harness (CANON-34).

The videos (NNM-09/10, PNP-21..27, LSTM-09/18, TFM-21, GRC-27) all run manual
"try a lookback, try a topology, read the per-class metrics, write it down"
loops. CANON-34 wants that made SYSTEMATIC: an explicit grid, every trial
logged to disk with its full config, and per-CLASS metrics recorded (not just
scalar accuracy — the videos insist accuracy alone hides a majority-class
collapse).

Reuse-first: trials are scored with trading.classification_eval (CANON-37/58),
so every sweep row already carries the confusion-structure verdict. The model
factory is injected, so this works over the numpy ScratchNet core AND the video
torch lanes without importing torch here.

Chronological discipline (CANON-30): the split is an ordered index cut, never a
random shuffle — the harness refuses a caller-supplied shuffled split."""
from __future__ import annotations

import itertools
import json
import os
import time

import numpy as np

from trading.classification_eval import classification_eval

__all__ = ["grid", "chrono_split", "run_sweep"]

_LOG_DIR = os.path.join(os.path.dirname(__file__), os.pardir, "data", "cache")


def grid(**axes) -> list:
    """Cartesian product of named axes → list of param dicts.
    grid(lookback=[10,20], hidden=[(16,), (32,16)]) → 4 dicts."""
    keys = list(axes)
    return [dict(zip(keys, combo)) for combo in itertools.product(*axes.values())]


def chrono_split(n: int, val_frac: float = 0.2) -> tuple:
    """Ordered train/val index cut (no shuffle) — CANON-30."""
    cut = int(round(n * (1 - val_frac)))
    return np.arange(cut), np.arange(cut, n)


def run_sweep(build_fn, X, y, params_grid, *, val_frac: float = 0.2,
              log_name: str | None = None, proba_fn=None, seed: int = 0) -> dict:
    """Run every config in `params_grid`, log each trial, return a leaderboard.

    build_fn(params, seed) -> a fitted-able object exposing .fit(Xtr, ytr) and
      .predict(Xv); optional .predict_proba(Xv) (or pass proba_fn(model, Xv)).
    Each trial records: params, train+val accuracy, per-class report, confusion
    structure verdict, fit seconds. Trials that raise are logged with their
    error (never silently dropped). Leaderboard is sorted by val macro-F1 then
    accuracy. Logs to data/cache/<log_name>.jsonl (append, one row per trial)."""
    X, y = np.asarray(X), np.asarray(y)
    tr, va = chrono_split(len(X), val_frac)
    log_name = log_name or f"sweep_{int(len(X))}x{X.shape[1] if X.ndim > 1 else 1}"
    os.makedirs(_LOG_DIR, exist_ok=True)
    path = os.path.abspath(os.path.join(_LOG_DIR, f"{log_name}.jsonl"))
    trials = []
    with open(path, "a") as fh:
        for i, params in enumerate(params_grid):
            row = {"trial": i, "params": _jsonable(params), "ts": _now()}
            try:
                t0 = time.perf_counter()
                model = build_fn(params, seed)
                model.fit(X[tr], y[tr])
                yv = np.asarray(model.predict(X[va]))
                ytr_pred = np.asarray(model.predict(X[tr]))
                proba = None
                if proba_fn is not None:
                    proba = proba_fn(model, X[va])
                elif hasattr(model, "predict_proba"):
                    try:
                        proba = model.predict_proba(X[va])
                    except Exception:
                        proba = None
                ev = classification_eval(y[va], yv, proba)
                row.update({
                    "fit_seconds": round(time.perf_counter() - t0, 3),
                    "train_acc": float(np.mean(ytr_pred == y[tr])),
                    "val_acc": ev["report"]["accuracy"],
                    "val_macro_f1": ev["report"]["macro_f1"],
                    "per_class": ev["report"]["per_class"],
                    "structure_verdict": ev["structure_verdict"]["verdict"],
                    "flags": ev["structure_verdict"]["flags"],
                    "ok": True})
            except Exception as exc:                    # honest: keep the failure
                row.update({"ok": False, "error": str(exc)})
            fh.write(json.dumps(row) + "\n")
            trials.append(row)
            try:                                         # CANON-43 burden tally
                from trading.antioverfit import register_backtest
                register_backtest(1)
            except Exception:
                pass
    good = [t for t in trials if t.get("ok")]
    good.sort(key=lambda t: (t.get("val_macro_f1", 0), t.get("val_acc", 0)),
              reverse=True)
    return {"log_path": path, "n_trials": len(trials), "n_ok": len(good),
            "leaderboard": good, "best": good[0] if good else None,
            "failures": [t for t in trials if not t.get("ok")]}


def _jsonable(params: dict) -> dict:
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in params.items()}


def _now() -> float:
    # sweep is invoked from live code (not the resume-cached workflow), so a real
    # wall-clock stamp is fine here.
    return round(time.time(), 3)
