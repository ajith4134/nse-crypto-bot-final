"""Golden datasets + evaluation — the 'known input->output first' discipline.

Generates a deterministic, non-linearly-separable dataset (XOR-of-signs with
Gaussian noise) so that a single linear node cannot solve it but a stacked
ensemble can — exactly the supervised loop: fit on known I/O, measure accuracy,
and only then trust the node on unknown inputs.

Inputs:  rng seed, sample count, noise level.
Outputs: (X, y) golden pairs; accuracy() over predictions.

Multi-output scoring (see core/heads.py): score_head() / baseline_for() score
ANY task — binary, multiclass, or regression — given a head and the general
`predict_output(X)` rows. Each returns one headline number per head plus extras
for the dashboard, against an honest per-task baseline (majority for
classification, mean-of-train predictor for regression). Walk-forward discipline
is the caller's job; these functions just score given (pred, y).
"""
from __future__ import annotations

import random

import numpy as np

from core.heads import OutputHead
from core.node_protocol import Labels, Matrix


def make_golden_dataset(n: int = 600, noise: float = 0.45,
                        seed: int = 7) -> tuple[Matrix, Labels]:
    """2-D XOR-of-signs: y = 1 iff (x>0) XOR (y>0), plus Gaussian noise."""
    rng = random.Random(seed)
    X: Matrix = []
    y: Labels = []
    for _ in range(n):
        cx = rng.choice([-1.0, 1.0])
        cy = rng.choice([-1.0, 1.0])
        px = cx + rng.gauss(0, noise)
        py = cy + rng.gauss(0, noise)
        X.append([px, py])
        y.append(1 if (cx > 0) ^ (cy > 0) else 0)
    return X, y


def train_test_split(X: Matrix, y: Labels, test_frac: float = 0.3,
                     seed: int = 7) -> tuple[Matrix, Labels, Matrix, Labels]:
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * (1 - test_frac))
    tr, te = idx[:cut], idx[cut:]
    return ([X[i] for i in tr], [y[i] for i in tr],
            [X[i] for i in te], [y[i] for i in te])


def accuracy(pred: Labels, y: Labels) -> float:
    return sum(int(a == b) for a, b in zip(pred, y)) / len(y)


# --- multi-output scoring ---------------------------------------------------

def argmax_labels(pred_output: list[list[float]]) -> Labels:
    """Collapse classification probability rows to predicted class labels.

    Each row is a length-n_classes probability vector; the label is its argmax.
    """
    return [int(np.argmax(row)) for row in pred_output]


def _macro_f1(pred: Labels, y: Labels, n_classes: int) -> float:
    """Unweighted mean of per-class F1 (each class counts equally)."""
    f1s = []
    for c in range(n_classes):
        tp = sum(1 for p, t in zip(pred, y) if p == c and t == c)
        fp = sum(1 for p, t in zip(pred, y) if p == c and t != c)
        fn = sum(1 for p, t in zip(pred, y) if p != c and t == c)
        denom = 2 * tp + fp + fn
        f1s.append((2 * tp / denom) if denom else 0.0)
    return float(np.mean(f1s)) if f1s else 0.0


def _r2(pred: list[float], y: list[float]) -> float:
    """Coefficient of determination; 0 when y has no variance (and pred==mean)."""
    yt = np.asarray(y, dtype=float)
    yp = np.asarray(pred, dtype=float)
    ss_res = float(np.sum((yt - yp) ** 2))
    ss_tot = float(np.sum((yt - yt.mean()) ** 2))
    if ss_tot == 0.0:
        return 1.0 if ss_res == 0.0 else 0.0
    return 1.0 - ss_res / ss_tot


def score_head(head: OutputHead, pred_output: list[list[float]], y: Labels) -> dict:
    """Score predictions for one head with the metric appropriate to its task.

    pred_output is the general `predict_output(X)` shape: one row per input —
    a length-n_classes probability vector for classification, or a length-1
    [value] row for regression.

    Returns {"metric": str, "value": float, "extra": {...}} so the dashboard can
    show one headline number per head.
    """
    if head.is_classification:
        pred = argmax_labels(pred_output)
        return {"metric": "accuracy",
                "value": accuracy(pred, y),
                "extra": {"macro_f1": _macro_f1(pred, y, head.n_classes),
                          "n": len(y)}}
    # regression: rows are [value]
    pred = [float(row[0]) for row in pred_output]
    yf = [float(v) for v in y]
    mae = float(np.mean(np.abs(np.asarray(pred) - np.asarray(yf)))) if y else 0.0
    return {"metric": "r2",
            "value": _r2(pred, yf),
            "extra": {"mae": mae, "n": len(y)}}


def baseline_for(head: OutputHead, y_train: Labels, y_test: Labels) -> dict:
    """Honest per-task baseline scored on y_test, same shape as score_head().

    classification -> majority-class (of y_train) accuracy on y_test;
    regression     -> mean-of-y_train predictor's R2 (~0) and MAE on y_test.
    """
    if head.is_classification:
        majority = max(set(y_train), key=y_train.count) if y_train else 0
        pred_output = [[1.0 if c == majority else 0.0
                        for c in range(head.n_classes)] for _ in y_test]
        return score_head(head, pred_output, y_test)
    # regression: constant predictor = mean of training targets
    mean = float(np.mean([float(v) for v in y_train])) if y_train else 0.0
    pred_output = [[mean] for _ in y_test]
    return score_head(head, pred_output, y_test)


def selective_accuracy(proba, y, coverages=(0.5, 0.3, 0.1)) -> list[dict]:
    """Accuracy on the TOP-confidence fraction of samples (selective prediction).

    `proba` = binary p_up per sample; confidence = max(p, 1-p). For each
    coverage c, keep the ceil(c*n) most-confident samples and score accuracy
    there — the number that matters for a trading net that ABSTAINS on
    coin-flips (CANON-49 dead-band; the reflex arc acts only where confident).
    Rows: {coverage, n, accuracy, baseline} where baseline = majority share of
    y WITHIN the selected subset (the honest comparison at that coverage).
    """
    import numpy as _np
    p = _np.asarray([float(v) for v in proba])
    yy = _np.asarray([int(v) for v in y])
    conf = _np.maximum(p, 1.0 - p)
    order = _np.argsort(-conf)
    out = []
    for c in coverages:
        k = max(1, int(_np.ceil(c * len(p))))
        idx = order[:k]
        pred = (p[idx] >= 0.5).astype(int)
        acc = float((pred == yy[idx]).mean())
        share = float(yy[idx].mean())
        out.append({"coverage": round(float(c), 2), "n": int(k),
                    "accuracy": round(acc, 4),
                    "baseline": round(max(share, 1 - share), 4)})
    return out
