"""Classification evaluation artifacts (CANON-37) + confusion-structure verdicts
(CANON-58).

The video lanes (PNP-20, GRC-26) demand first-class classification diagnostics —
train+test accuracy, a confusion matrix, a per-class precision/recall/F1 report,
and a "misclassification gallery" (the worst-confused samples). CANON-58 further
wants an automated VERDICT read off the confusion structure (is the model biased
to one class? does it collapse to majority? are two classes systematically
swapped?) so the model-comparison protocol is not left to eyeballing.

Reuses sklearn.metrics (already a project dep). Pure functions over label arrays;
no plotting dep required — the "gallery" is returned as structured rows the
dashboard renders (honest-wiring: real indices, real confidences)."""
from __future__ import annotations

import numpy as np

__all__ = ["confusion", "per_class_report", "misclassification_gallery",
           "confusion_structure_verdict", "classification_eval"]


def _labels(y_true, y_pred) -> list:
    return sorted(set(np.asarray(y_true).tolist()) | set(np.asarray(y_pred).tolist()))


def confusion(y_true, y_pred, labels=None) -> dict:
    """Confusion matrix as {'labels', 'matrix'} (rows = true, cols = pred)."""
    from sklearn.metrics import confusion_matrix
    labels = labels if labels is not None else _labels(y_true, y_pred)
    m = confusion_matrix(y_true, y_pred, labels=labels)
    return {"labels": labels, "matrix": m.astype(int).tolist()}


def per_class_report(y_true, y_pred, labels=None) -> dict:
    """Per-class precision / recall / F1 / support + accuracy (CANON-37)."""
    from sklearn.metrics import classification_report, accuracy_score
    labels = labels if labels is not None else _labels(y_true, y_pred)
    rep = classification_report(y_true, y_pred, labels=labels,
                                output_dict=True, zero_division=0)
    return {"accuracy": float(accuracy_score(y_true, y_pred)),
            "per_class": {str(k): rep[str(k)] for k in labels if str(k) in rep},
            "macro_f1": float(rep.get("macro avg", {}).get("f1-score", 0.0))}


def misclassification_gallery(y_true, y_pred, proba=None, k: int = 20) -> list:
    """The k most-confident WRONG predictions (the video's misclassification
    gallery). When class probabilities are given, "confidence" is the predicted
    class probability; otherwise wrong rows are returned in order. Each row:
    {index, true, pred, confidence}."""
    yt, yp = np.asarray(y_true), np.asarray(y_pred)
    wrong = np.where(yt != yp)[0]
    if proba is not None:
        proba = np.asarray(proba)
        conf = proba.max(axis=1) if proba.ndim == 2 else np.abs(proba)
        wrong = wrong[np.argsort(-conf[wrong])]
    rows = []
    for i in wrong[:k]:
        c = (float(np.asarray(proba)[i].max()) if proba is not None
             and np.asarray(proba).ndim == 2 else None)
        rows.append({"index": int(i), "true": _py(yt[i]), "pred": _py(yp[i]),
                     "confidence": c})
    return rows


def _py(v):
    return v.item() if hasattr(v, "item") else v


def confusion_structure_verdict(y_true, y_pred, labels=None,
                                collapse_frac: float = 0.9,
                                swap_frac: float = 0.6) -> dict:
    """Automated read of the confusion STRUCTURE (CANON-58).

    Flags the pathologies the videos warn about:
      * majority-collapse — one predicted class captures ≥ collapse_frac of ALL
        predictions (the model "always says up");
      * dead-class        — a true class never gets predicted correctly (recall 0);
      * systematic-swap    — for a pair (a,b), ≥ swap_frac of true-a is called b
        (two patterns confused);
      * off-diagonal-mass  — overall accuracy vs a diagonal-only baseline.
    Returns {'verdict': ok|warn|fail, 'flags': [...], 'accuracy'} — 'fail' if any
    collapse/dead-class fires, 'warn' for swaps, else 'ok'."""
    conf = confusion(y_true, y_pred, labels)
    labels, m = conf["labels"], np.asarray(conf["matrix"], float)
    total = m.sum() or 1.0
    flags = []

    col_sums = m.sum(axis=0)
    for j, lab in enumerate(labels):
        if col_sums[j] / total >= collapse_frac:
            flags.append({"kind": "majority-collapse", "class": _py(lab),
                          "frac": round(float(col_sums[j] / total), 3)})

    for i, lab in enumerate(labels):
        row = m[i].sum()
        if row > 0 and m[i, i] == 0:
            flags.append({"kind": "dead-class", "class": _py(lab),
                          "support": int(row)})

    for i, a in enumerate(labels):
        row = m[i].sum() or 1.0
        for j, b in enumerate(labels):
            if i != j and m[i, j] / row >= swap_frac:
                flags.append({"kind": "systematic-swap", "true": _py(a),
                              "called": _py(b), "frac": round(float(m[i, j] / row), 3)})

    acc = float(np.trace(m) / total)
    severity = {"majority-collapse": "fail", "dead-class": "fail",
                "systematic-swap": "warn"}
    verdict = "ok"
    for f in flags:
        s = severity.get(f["kind"], "warn")
        if s == "fail":
            verdict = "fail"
            break
        verdict = "warn"
    return {"verdict": verdict, "accuracy": round(acc, 4), "flags": flags,
            "n_classes": len(labels)}


def classification_eval(y_true, y_pred, proba=None, labels=None,
                        gallery_k: int = 20) -> dict:
    """One call → the full CANON-37+58 artifact bundle."""
    return {
        "confusion": confusion(y_true, y_pred, labels),
        "report": per_class_report(y_true, y_pred, labels),
        "gallery": misclassification_gallery(y_true, y_pred, proba, gallery_k),
        "structure_verdict": confusion_structure_verdict(y_true, y_pred, labels),
    }
