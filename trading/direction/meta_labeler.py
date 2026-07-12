"""trading/direction/meta_labeler.py — D6: the direction meta-labeler (Pillar 27).

López de Prado meta-labeling (SOTA notes §1 — the proven form of "fix a wrong
signal"): the primary signal proposes a SIDE; this secondary model predicts
P(that side is correct) from the decision's context, and the executor only commits
capital when that calibrated probability clears META_MIN_P. This is the
accuracy-coverage dial that makes "≥80% on taken trades" honest: raise the bar,
trade less, be right more — with the coverage cost visible, never hidden.

Trains on the Truth Ledger's own labeled examples (direction_truth_train.jsonl —
11k+ from the journal backfill on day one, growing every funnel cycle). Features are
decision-time only (source, regime, segment, horizon, confidence, hour/day, side,
plus the source's measured hit-rate prior) — nothing post-hoc, so there is no lookahead.
Time-ordered holdout (never shuffled: shuffling leaks regimes across the split) +
isotonic calibration on the holdout, honest AUC/Brier stored with the model.

HONESTY GUARD: while the holdout AUC is below META_MIN_AUC (default 0.55) the gate is
ADVISORY-ONLY — a model that can't rank decisions gets to watch, not veto. Explore
mode is always advisory (its job is generating training data).

Levers: META_GATE=0 disables, META_MIN_P (default 0.55), META_HORIZON (1h),
META_RETRAIN_H (6), META_MIN_EXAMPLES (1000), META_MIN_AUC (0.55).
CPU: LightGBM, trains in seconds on 10-50k rows.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from trading import state

_TRAIN = "direction_truth_train.jsonl"
_MODEL = "direction_meta.pkl"
_CATS = ("source", "regime", "segment", "market", "horizon")
# LENS features (M1, 2026-07-12): the D6 meta-labeler becomes a STACKING meta-learner — it now
# also consumes every indicator_fusion lens output (order-flow / volume-profile / YOLO / the
# discovered direction-equation / on-chain / sectors / vision / confluence). One calibrated model
# learns how much to trust each lens PER regime/source from realized outcomes, replacing CORTEX's
# fixed hierarchical gate (which underperformed naive baseline). Zero-filled for pre-M1 examples
# and any decision where a lens was unavailable, so the model degrades gracefully as data accrues.
_LENS_NUMS = ("f_confluence", "f_p_up", "f_orderflow", "f_sectors", "f_ai", "f_vp",
              "f_yolo", "f_direq", "f_onchain", "f_vision",
              # CORTEX ensemble folded in as a learnable input (2026-07-12) — the stack learns its
              # conditional reliability instead of discarding the anti-signal (see cortex_features).
              "f_cortex_side", "f_cortex_conf")
_NUMS = ("confidence", "dir_long", "taken", "hour", "dow", "source_prior") + _LENS_NUMS


def lens_features(fusion: dict | None) -> dict:
    """Flatten an indicator_fusion.fuse() output into the meta-learner's numeric lens features
    (0.0 when a lens is unavailable, p_up→0.5). ONE code path shared by train-time (truth_ledger
    record) and predict-time (executor gate) so there is no train/serve skew. Pure — takes a plain
    dict, imports nothing (avoids the indicator_fusion↔direction cycle)."""
    fz = fusion or {}

    def _n(v, d=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d

    of = fz.get("order_flow") or {}
    sec = fz.get("sectors") or {}
    vp = fz.get("volume_profile") or {}
    yolo = fz.get("chart_yolo") or {}
    deq = fz.get("direction_equation") or {}
    onc = fz.get("onchain") or {}
    ai = fz.get("ai_select") or {}
    return {
        "f_confluence": _n(fz.get("confluence")),
        "f_p_up": _n(fz.get("p_up"), 0.5),
        "f_orderflow": _n(of.get("tilt")),
        "f_sectors": _n(sec.get("tilt")),
        "f_ai": 1.0 if ai.get("ai_selected") else 0.0,
        "f_vp": _n(vp.get("tilt")) if vp.get("available") else 0.0,
        "f_yolo": _n(yolo.get("score")),
        "f_direq": _n(deq.get("tilt")) if deq else 0.0,
        "f_onchain": _n(onc.get("composite")) if onc.get("available") else 0.0,
        "f_vision": _n(fz.get("vision_dir")),
    }


def cortex_features(sig: dict | None) -> dict:
    """CORTEX ensemble output as stacking features (2026-07-12): the shadow network becomes a
    learnable INPUT to the meta-learner rather than a discarded anti-signal — the stack learns its
    conditional reliability per regime/source. side→{long:+1, short:-1, flat/none:0}; 0-filled when
    absent. Same pure-function contract as lens_features (shared train + serve, no skew)."""
    s = sig or {}
    side = str(s.get("side") or "").lower()

    def _n(v, d=0.0):
        try:
            return float(v)
        except (TypeError, ValueError):
            return d

    return {"f_cortex_side": 1.0 if side == "long" else -1.0 if side == "short" else 0.0,
            "f_cortex_conf": _n(s.get("confidence"))}


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _enabled() -> bool:
    return os.environ.get("META_GATE", "1") in ("1", "true", "TRUE", "yes", "on")


def _model_path() -> Path:
    return Path(state.STATE_DIR) / _MODEL


# ── feature building (shared by train + predict: one code path, no drift) ────────


def _source_prior(source: str, horizon: str) -> float:
    """The source's measured cross-regime hit-rate at this horizon (0.5 when unknown)
    — the Truth Ledger prior, the single strongest decision-time feature."""
    try:
        agg = state.load_json("direction_truth.json", {}).get("buckets") or {}
        n = c = 0
        suffix = f"|{horizon}"
        prefix = f"{source}|"
        for key, b in agg.items():
            if key.startswith(prefix) and key.endswith(suffix):
                n += int(b.get("n", 0))
                c += int(b.get("correct", 0))
        return c / n if n >= 10 else 0.5
    except Exception:
        return 0.5


def _featurize(ex: dict) -> dict:
    """One example/decision dict → flat feature dict (categoricals stay strings)."""
    ts = float(ex.get("ts") or time.time())
    dt = datetime.fromtimestamp(ts, tz=timezone.utc)
    conf = ex.get("confidence")
    hz = str(ex.get("horizon") or os.environ.get("META_HORIZON", "1h"))
    feat = {"source": str(ex.get("source") or "unknown"),
            "regime": str(ex.get("regime") or "unknown"),
            "segment": str(ex.get("segment") or "futures"),
            "market": str(ex.get("market") or "CRYPTO"),
            "horizon": hz,
            "confidence": float(conf) if conf is not None else -1.0,
            "dir_long": 1.0 if str(ex.get("direction")).upper() == "LONG" else 0.0,
            "taken": 1.0 if ex.get("taken") else 0.0,
            "hour": float(dt.hour), "dow": float(dt.weekday()),
            "source_prior": _source_prior(str(ex.get("source") or "unknown"), hz)}
    # STACKING lens features (M1): read the flat lens dict stored on the example (train) or passed
    # by the executor (predict); 0.0-fill anything missing so old examples still train cleanly.
    lf = ex.get("features") or {}
    for k in _LENS_NUMS:
        try:
            feat[k] = float(lf.get(k, 0.0) or 0.0)
        except (TypeError, ValueError):
            feat[k] = 0.0
    return feat


def _frame(rows: list[dict]):
    import pandas as pd
    df = pd.DataFrame([_featurize(r) for r in rows])
    for c in _CATS:
        df[c] = df[c].astype("category")
    return df


# ── training ──────────────────────────────────────────────────────────────────────


def train(min_examples: int | None = None) -> dict:
    """Fit LightGBM + isotonic calibration on the Truth Ledger's labeled examples.
    Returns the honest report {n, auc, brier, base_rate, trained} and persists the
    model; raises nothing — errors come back as {"error": ...}."""
    try:
        import joblib
        import numpy as np
        from lightgbm import LGBMClassifier
        from sklearn.isotonic import IsotonicRegression
        from sklearn.metrics import brier_score_loss, roc_auc_score

        need = int(min_examples if min_examples is not None
                   else _env_f("META_MIN_EXAMPLES", 1000))
        p = Path(state.STATE_DIR) / _TRAIN
        if not p.exists():
            return {"error": "no training file"}
        rows = []
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        rows = [r for r in rows if r.get("horizon") != "exit"]   # exit labels carry
        if len(rows) < need:                                     # exit-policy noise
            return {"error": f"only {len(rows)} examples (< {need})"}
        rows.sort(key=lambda r: float(r.get("ts") or 0))         # time order
        df = _frame(rows)
        y = np.array([1 if r.get("correct") else 0 for r in rows])
        cut = int(len(df) * 0.8)
        if cut < 200 or len(df) - cut < 100:
            return {"error": "not enough rows for a time-ordered holdout"}
        model = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                               min_child_samples=40, verbose=-1)
        model.fit(df.iloc[:cut], y[:cut], categorical_feature=list(_CATS))
        raw = model.predict_proba(df.iloc[cut:])[:, 1]
        auc = float(roc_auc_score(y[cut:], raw)) if len(set(y[cut:])) > 1 else 0.5
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
        iso.fit(raw, y[cut:])
        cal = iso.predict(raw)
        rep = {"n": len(df), "n_holdout": len(df) - cut, "auc": round(auc, 4),
               "brier": round(float(brier_score_loss(y[cut:], cal)), 4),
               "base_rate": round(float(y.mean()), 4), "trained": time.time(),
               "categories": {c: df[c].cat.categories.tolist() for c in _CATS}}
        joblib.dump({"model": model, "iso": iso, "meta": rep}, _model_path())
        return rep
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def maybe_train() -> dict | None:
    """Loop hook: retrain when the model is absent or older than META_RETRAIN_H.
    Cheap no-op otherwise."""
    try:
        meta = (load_model() or {}).get("meta") or {}
        age_h = (time.time() - float(meta.get("trained") or 0)) / 3600
        if meta and age_h < _env_f("META_RETRAIN_H", 6):
            return None
        return train()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


_LOADED: dict = {"mtime": None, "bundle": None}


def load_model() -> dict | None:
    """The persisted {model, iso, meta} bundle, mtime-cached per process."""
    p = _model_path()
    try:
        mtime = p.stat().st_mtime
    except OSError:
        return None
    if _LOADED["mtime"] == mtime and _LOADED["bundle"] is not None:
        return _LOADED["bundle"]
    try:
        import joblib
        bundle = joblib.load(p)
        _LOADED.update(mtime=mtime, bundle=bundle)
        return bundle
    except Exception:
        return None


# ── the gate ──────────────────────────────────────────────────────────────────────


def p_correct(example: dict) -> float | None:
    """Calibrated P(direction correct) for one decision dict (same keys the Truth
    Ledger records). None when no usable model exists — callers must treat None as
    'no opinion', never as 0 or 1."""
    bundle = load_model()
    if not bundle:
        return None
    try:
        import pandas as pd
        feats = _featurize(example)
        cats = (bundle["meta"].get("categories") or {})
        df = pd.DataFrame([feats])
        for c in _CATS:                          # unseen categories → NaN (LightGBM-safe)
            df[c] = pd.Categorical([feats[c]], categories=cats.get(c) or [feats[c]])
        raw = float(bundle["model"].predict_proba(df)[:, 1][0])
        return float(bundle["iso"].predict([raw])[0])
    except Exception:
        return None


def gate(direction: str, example: dict) -> dict:
    """{"p", "allow", "advisory", "auc"} — allow=False ONLY when a proven model
    (holdout AUC ≥ META_MIN_AUC) prices this decision below META_MIN_P."""
    out = {"p": None, "allow": True, "advisory": True, "auc": None}
    try:
        if not _enabled():
            return out
        bundle = load_model()
        if not bundle:
            return out
        auc = float((bundle["meta"] or {}).get("auc") or 0.5)
        out["auc"] = auc
        p = p_correct({**example, "direction": direction})
        out["p"] = None if p is None else round(p, 4)
        if p is None:
            return out
        out["advisory"] = auc < _env_f("META_MIN_AUC", 0.55)
        if not out["advisory"] and p < _env_f("META_MIN_P", 0.55):
            out["allow"] = False
        return out
    except Exception:
        return out


def status() -> dict:
    """Panel/API snapshot: model freshness + honest holdout quality + levers."""
    meta = (load_model() or {}).get("meta") or {}
    return {"enabled": _enabled(), "model": bool(meta),
            "trained": meta.get("trained"), "n": meta.get("n"),
            "auc": meta.get("auc"), "brier": meta.get("brier"),
            "base_rate": meta.get("base_rate"),
            "enforcing": bool(meta) and float(meta.get("auc") or 0)
            >= _env_f("META_MIN_AUC", 0.55),
            "levers": {"META_MIN_P": _env_f("META_MIN_P", 0.55),
                       "META_MIN_AUC": _env_f("META_MIN_AUC", 0.55),
                       "META_RETRAIN_H": _env_f("META_RETRAIN_H", 6)}}
