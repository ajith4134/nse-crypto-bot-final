"""trading/direction/meta_challenger.py — TabPFN challenger for the D6 meta-labeler.

The direction meta-labeler (meta_labeler.py) is the "≥80% on taken trades" dial, but on
real data its LightGBM holdout AUC sits near 0.51 — it can barely rank a good decision
above a bad one, so the honesty guard keeps it advisory. Before assuming the fix is a
better MODEL, this runs the same honest champion/challenger duel proven for the
TradeOutcomeNet (brain/challenger.py): TabPFN-v2 — a prior-fitted tabular foundation model
that often beats tuned GBDTs on small tables (Hollmann et al., Nature 2025) — trained on
the EXACT same features, the EXACT same time-ordered holdout, scored on the EXACT same
AUC/Brier. If TabPFN can't beat LightGBM here either, the weakness is the FEATURES/labels,
not the engine — a finding worth more than a silent swap.

RECOMMEND-ONLY: writes trading/state/direction_meta_challenger.json; promotion stays behind
META_ENGINE=tabpfn (read by meta_labeler.train), so the live gate never switches silently.
Heavy (transformer inference) — run from the CLI (`python -m trading.direction.meta_challenger`)
or a nice-10 daemon, NEVER the funnel/dashboard hot path.

Levers: META_CHALLENGE_ROWS (newest rows used, default 3000 — CPU-time rail),
META_CHALLENGE_H (min hours between duels for maybe_challenge, default 24),
META_PROMOTE_AUC_MARGIN (challenger must beat champion holdout AUC by ≥ this, default 0.02).
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from trading import state

_EVAL = "direction_meta_challenger.json"


def _env_f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, "") or default)
    except ValueError:
        return default


def _load_rows(max_rows: int) -> list[dict]:
    """The meta-labeler's own training examples, exit-labels dropped, time-ordered,
    newest `max_rows` kept (the CPU-time rail TabPFN needs)."""
    from trading.direction.meta_labeler import _TRAIN
    p = Path(state.STATE_DIR) / _TRAIN
    if not p.exists():
        return []
    rows = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("horizon") != "exit":                # exit labels carry exit-policy noise
                rows.append(r)
    rows.sort(key=lambda r: float(r.get("ts") or 0))      # never shuffle: regimes leak
    return rows[-max_rows:] if max_rows and len(rows) > max_rows else rows


def _encoded(rows: list[dict]):
    """meta_labeler features → (numeric ndarray, y, categorical_col_indices). Categoricals
    become integer codes (TabPFN takes numeric arrays + the categorical indices)."""
    import numpy as np
    from trading.direction.meta_labeler import _CATS, _NUMS, _frame
    df = _frame(rows)
    cat_idx = []
    cols = []
    for i, c in enumerate(list(_CATS) + list(_NUMS)):
        if c in _CATS:
            cols.append(df[c].cat.codes.to_numpy(dtype=float))
            cat_idx.append(i)
        else:
            cols.append(df[c].astype(float).to_numpy())
    X = np.column_stack(cols)
    y = np.array([1 if r.get("correct") else 0 for r in rows], dtype=int)
    return X, y, cat_idx


def _holdout_scores(fit_predict, X, y, cut: int) -> dict:
    """Isotonic-calibrated holdout AUC + Brier for one engine on the time-ordered split.
    fit_predict(Xtr, ytr, Xte) → p(correct) for the holdout rows."""
    import numpy as np
    from sklearn.isotonic import IsotonicRegression
    from sklearn.metrics import brier_score_loss, roc_auc_score
    ytr, yte = y[:cut], y[cut:]
    raw = np.asarray(fit_predict(X[:cut], ytr, X[cut:]), dtype=float)
    auc = float(roc_auc_score(yte, raw)) if len(set(yte)) > 1 else 0.5
    iso = IsotonicRegression(out_of_bounds="clip", y_min=0.01, y_max=0.99)
    iso.fit(raw, yte)
    cal = iso.predict(raw)
    return {"auc": round(auc, 4), "brier": round(float(brier_score_loss(yte, cal)), 4)}


def _lgbm_fit_predict(cat_idx):
    def fp(Xtr, ytr, Xte):
        from lightgbm import LGBMClassifier
        m = LGBMClassifier(n_estimators=300, learning_rate=0.05, num_leaves=31,
                           min_child_samples=40, verbose=-1)
        m.fit(Xtr, ytr, categorical_feature=cat_idx)
        return m.predict_proba(Xte)[:, 1]
    return fp


def _tabpfn_fit_predict(cat_idx):
    def fp(Xtr, ytr, Xte):
        from tabpfn import TabPFNClassifier
        clf = TabPFNClassifier(device="cpu", n_estimators=2,         # CPU-frugal ensemble
                               ignore_pretraining_limits=True,       # accept >1k train rows
                               categorical_features_indices=cat_idx or None)
        clf.fit(Xtr, ytr)
        return clf.predict_proba(Xte)[:, 1]
    return fp


def challenge(max_rows: int | None = None) -> dict:
    """Run the LightGBM-vs-TabPFN duel on the meta-labeler's data + holdout. Returns/persists
    {champion, challenger, promote, verdict, ...}. Never raises — errors come back in the dict."""
    try:
        import numpy as np  # noqa: F401
        rows = _load_rows(int(max_rows if max_rows is not None
                              else _env_f("META_CHALLENGE_ROWS", 3000)))
        if len(rows) < 300:
            return {"error": f"only {len(rows)} usable examples (< 300)"}
        X, y, cat_idx = _encoded(rows)
        cut = int(len(X) * 0.8)
        if cut < 200 or len(X) - cut < 100:
            return {"error": "not enough rows for a time-ordered holdout"}
        if len(set(y[cut:])) < 2:
            return {"error": "holdout has a single class — cannot score AUC"}
        t0 = time.time()
        champ = _holdout_scores(_lgbm_fit_predict(cat_idx), X, y, cut)
        champ["engine"] = "lightgbm"
        champ["seconds"] = round(time.time() - t0, 1)
        t1 = time.time()
        chal = _holdout_scores(_tabpfn_fit_predict(cat_idx), X, y, cut)
        chal["engine"] = "tabpfn_v2"
        chal["seconds"] = round(time.time() - t1, 1)
        margin = _env_f("META_PROMOTE_AUC_MARGIN", 0.02)
        promote = chal["auc"] >= champ["auc"] + margin
        rep = {"champion": champ, "challenger": chal,
               "n_rows": len(X), "n_holdout": len(X) - cut,
               "base_rate": round(float(y.mean()), 4), "margin": margin,
               "promote": promote, "ts": time.time(),
               "protocol": "meta_labeler features + same 80/20 time-ordered holdout + isotonic",
               "verdict": (f"PROMOTE — TabPFN AUC {chal['auc']} beats LightGBM {champ['auc']} "
                           f"by ≥{margin}: set META_ENGINE=tabpfn" if promote else
                           f"KEEP LightGBM — TabPFN AUC {chal['auc']} vs {champ['auc']} "
                           f"(margin {margin} not cleared)")}
        state.save_json(_EVAL, rep)
        return rep
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def maybe_challenge() -> dict | None:
    """Throttled hook for a background daemon: run at most every META_CHALLENGE_H hours.
    NEVER call from the funnel/dashboard hot path (transformer inference is heavy)."""
    try:
        prev = state.load_json(_EVAL, {})
        age_h = (time.time() - float(prev.get("ts") or 0)) / 3600
        if prev and age_h < _env_f("META_CHALLENGE_H", 24):
            return None
        return challenge()
    except Exception as e:
        return {"error": f"{type(e).__name__}: {e}"}


def status() -> dict:
    """Panel/API snapshot: the last duel result + levers."""
    ev = state.load_json(_EVAL, {})
    return {"eval": ev,
            "levers": {"META_CHALLENGE_ROWS": _env_f("META_CHALLENGE_ROWS", 3000),
                       "META_CHALLENGE_H": _env_f("META_CHALLENGE_H", 24),
                       "META_PROMOTE_AUC_MARGIN": _env_f("META_PROMOTE_AUC_MARGIN", 0.02)}}


if __name__ == "__main__":
    import pprint
    pprint.pprint(challenge())
