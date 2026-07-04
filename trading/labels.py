"""Barrier-style 3-class labeling for CORTEX lanes (CANON-28; PNP-14/PNP-15).

Implements the PNP videos' target construction faithfully:

* **PNP-14** — barrier-style 3-class target: a bar is labeled UP (2) if price
  moves +`pipdiff` before it moves -`pipdiff * sl_tp_ratio` within the horizon,
  DOWN (0) if the lower barrier is hit first, else UNCLEAR (1). The
  `sl_tp_ratio` (SLTPRatio) parameterizes the take-profit/stop-loss asymmetry.
* **PNP-15** — a horizon of N bars (default 30) plus a MANDATORY class-balance
  check: :func:`class_balance` reports per-class counts/shares and raises a
  warn flag whenever any class holds <10% of the labels (the majority-class
  pitfall — a model "beating" such a target by always predicting the majority
  class is caught by trading.fitness.majority_gate, CANON-36).

Deliberately ~50 lines of plain numpy (stitch-map row 4: from-scratch is
cheaper than any dependency here); the outer per-bar loop is fine at daily/1m
scale, the inner barrier scan is vectorized.
"""
from __future__ import annotations

import numpy as np

#: label values (fixed by the PNP spec: 0=down, 1=unclear, 2=up)
DOWN, UNCLEAR, UP = 0, 1, 2

#: mandatory class-balance floor (PNP-15): warn when any class share is below this
MIN_CLASS_SHARE = 0.10


def barrier_label(close, pipdiff: float, sl_tp_ratio: float = 1.0,
                  horizon_bars: int = 30) -> np.ndarray:
    """3-class barrier labels for every bar of `close` (CANON-28).

    For each bar i, scan the next `horizon_bars` bars: label UP (2) if
    ``close[j] - close[i] >= +pipdiff`` happens strictly before
    ``close[j] - close[i] <= -pipdiff * sl_tp_ratio``; DOWN (0) if the lower
    barrier is hit strictly first; UNCLEAR (1) if neither barrier is hit
    within the horizon or both are crossed on the same bar (ambiguous gap).
    Trailing bars with a truncated window are scanned over what remains.
    """
    if pipdiff <= 0:
        raise ValueError("pipdiff must be > 0")
    if sl_tp_ratio <= 0:
        raise ValueError("sl_tp_ratio must be > 0")
    c = np.asarray(close, dtype=float)
    n = c.shape[0]
    up_bar, dn_bar = float(pipdiff), float(pipdiff) * float(sl_tp_ratio)
    labels = np.full(n, UNCLEAR, dtype=int)
    for i in range(n):
        diff = c[i + 1: i + 1 + horizon_bars] - c[i]   # vectorized barrier scan
        if diff.size == 0:
            continue
        hit_up = np.flatnonzero(diff >= up_bar)
        hit_dn = np.flatnonzero(diff <= -dn_bar)
        first_up = hit_up[0] if hit_up.size else np.inf
        first_dn = hit_dn[0] if hit_dn.size else np.inf
        if first_up < first_dn:
            labels[i] = UP
        elif first_dn < first_up:
            labels[i] = DOWN
        # tie or neither → stays UNCLEAR
    return labels


def class_balance(labels) -> dict:
    """Per-class counts/shares + the MANDATORY imbalance warn flag (PNP-15).

    Always reports all three classes (0/1/2) even at zero count, so a fully
    missing class is flagged, not hidden. ``warn`` is True when any class
    share is below MIN_CLASS_SHARE (10%); ``warn_classes`` lists the culprits.
    """
    lab = np.asarray(labels, dtype=int)
    total = int(lab.shape[0])
    counts = {cls: int(np.count_nonzero(lab == cls)) for cls in (DOWN, UNCLEAR, UP)}
    shares = {cls: (counts[cls] / total if total else 0.0) for cls in counts}
    warn_classes = [cls for cls, sh in shares.items() if sh < MIN_CLASS_SHARE]
    return {"total": total, "counts": counts, "shares": shares,
            "warn": bool(warn_classes), "warn_classes": warn_classes}
