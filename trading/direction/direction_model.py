"""trading/direction/direction_model.py — the direction-aware model (proposal B, 2026-07-13).

A gradient-boosted classifier (CatBoost; the 2026 SOTA for tabular microstructure per the
research pass) trained on the Truth Ledger's RESOLVED direction outcomes to predict p_up
DIRECTLY from the decision-time feature vector. Emitted as a NEW truth-ledger source
`direction_model` into learned_direction.decide() — so it earns its own MEASURED edge and,
once proven, drives direction (and appears in the Direction X-Ray). It never dominates until
the ledger proves it: decide() gives an unproven source the same tiny weight as any other.

Label is direction-aware: label_up = ((direction == long) == correct) — long-right and
short-wrong are both "up". Trained offline on direction_truth_train.jsonl (no lookahead:
features are decision-time only). Reuse-first: CatBoost + the existing truth-ledger dataset;
falls back to sklearn GradientBoosting only if CatBoost is unavailable. Persists to
trading/state/direction_model.cbm (+ feature list). Fail-open — a model problem never breaks
a decision (predict returns None → the source is simply absent that trade).
"""
from __future__ import annotations

import json
import os
from pathlib import Path

TRAIN_FILE = "direction_truth_train.jsonl"
MODEL_FILE = "direction_model.cbm"
META_FILE = "direction_model.json"
SOURCE = "direction_model"


def enabled() -> bool:
    return os.environ.get("DIRECTION_MODEL", "1") in ("1", "true", "TRUE", "yes", "on")


def _state_dir() -> Path:
    from trading import state
    return Path(state.STATE_DIR)


def _label_up(ex: dict) -> int | None:
    d = str(ex.get("direction") or "").lower()
    c = ex.get("correct")
    if d not in ("long", "short") or c is None:
        return None
    return int((d == "long") == bool(c))


def _rows() -> tuple[list[dict], list[int]]:
    """Read resolved examples → (feature dicts, labels). Uses each example's numeric
    `features` (the recorded decision-time lens/microstructure inputs)."""
    p = _state_dir() / TRAIN_FILE
    X: list[dict] = []
    y: list[int] = []
    if not p.exists():
        return X, y
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        try:
            ex = json.loads(line)
        except Exception:
            continue
        lab = _label_up(ex)
        feats = ex.get("features")
        if lab is None or not isinstance(feats, dict) or not feats:
            continue
        num = {k: float(v) for k, v in feats.items()
               if isinstance(v, (int, float))}
        if num:
            X.append(num)
            y.append(lab)
    return X, y


def _matrix(X: list[dict], names: list[str]):
    return [[row.get(n, 0.0) for n in names] for row in X]


def train(min_examples: int = 200) -> dict:
    X, y = _rows()
    if len(X) < min_examples or len(set(y)) < 2:
        return {"trained": False, "n": len(X),
                "reason": f"need ≥{min_examples} resolved examples with features + both classes"}
    names = sorted({k for row in X for k in row})
    M = _matrix(X, names)
    cut = int(len(M) * 0.8)                            # time-ordered holdout (file is append-order)
    Xtr, ytr, Xte, yte = M[:cut], y[:cut], M[cut:], y[cut:]
    try:
        from catboost import CatBoostClassifier
        model = CatBoostClassifier(iterations=300, depth=5, learning_rate=0.05,
                                   loss_function="Logloss", verbose=0,
                                   auto_class_weights="Balanced")
        model.fit(Xtr, ytr)
        engine = "catboost"
    except Exception:
        from sklearn.ensemble import GradientBoostingClassifier
        model = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05)
        model.fit(Xtr, ytr)
        engine = "sklearn_gbm"
    # honest holdout AUC
    auc = None
    try:
        from sklearn.metrics import roc_auc_score
        proba = model.predict_proba(Xte)[:, 1]
        if len(set(yte)) == 2:
            auc = round(float(roc_auc_score(yte, proba)), 4)
    except Exception:
        pass
    sd = _state_dir()
    try:
        if engine == "catboost":
            model.save_model(str(sd / MODEL_FILE))
        else:
            import pickle
            (sd / MODEL_FILE).write_bytes(pickle.dumps(model))
    except Exception as e:
        return {"trained": False, "n": len(X), "reason": f"persist failed: {e}"[:120]}
    (sd / META_FILE).write_text(json.dumps(
        {"engine": engine, "features": names, "n": len(X), "holdout_auc": auc,
         "pos_rate": round(sum(y) / len(y), 4)}))
    return {"trained": True, "engine": engine, "n": len(X), "holdout_auc": auc,
            "n_features": len(names)}


_CACHE: dict = {"model": None, "names": None, "mtime": 0.0}


def _load():
    sd = _state_dir()
    mp, meta = sd / MODEL_FILE, sd / META_FILE
    if not (mp.exists() and meta.exists()):
        return None, None
    mt = mp.stat().st_mtime
    if _CACHE["model"] is not None and _CACHE["mtime"] == mt:
        return _CACHE["model"], _CACHE["names"]
    info = json.loads(meta.read_text())
    try:
        if info.get("engine") == "catboost":
            from catboost import CatBoostClassifier
            m = CatBoostClassifier()
            m.load_model(str(mp))
        else:
            import pickle
            m = pickle.loads(mp.read_bytes())
    except Exception:
        return None, None
    _CACHE.update({"model": m, "names": info.get("features") or [], "mtime": mt})
    return m, _CACHE["names"]


def predict(features: dict) -> float | None:
    """p_up in [0,1] from the decision-time features, or None (untrained / no overlap)."""
    if not enabled() or not isinstance(features, dict):
        return None
    m, names = _load()
    if m is None or not names:
        return None
    num = {k: float(v) for k, v in features.items() if isinstance(v, (int, float))}
    if not any(n in num for n in names):
        return None                                    # no feature overlap → no honest call
    try:
        p = float(m.predict_proba([[num.get(n, 0.0) for n in names]])[0][1])
        return round(min(0.98, max(0.02, p)), 4)
    except Exception:
        return None


def status() -> dict:
    sd = _state_dir()
    meta = sd / META_FILE
    if meta.exists():
        try:
            return {"trained": True, **json.loads(meta.read_text())}
        except Exception:
            pass
    return {"trained": False}
