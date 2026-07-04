"""trading/strategy/cpcv.py — Combinatorial Purged Cross-Validation (Pillar 20).

The default OOS evaluator for every strategy/parameter promotion. Plain walk-forward
gives ONE Sharpe number; CPCV gives a *distribution* of Sharpes over many train/test
recombinations, which is exactly what the Deflated-Sharpe / PBO defenses need to judge
whether an in-sample winner is real or a selection-bias artefact (López de Prado,
*Advances in Financial Machine Learning*, ch. 7 & 12).

Two leakage defenses are applied so the OOS blocks are honestly out-of-sample even when
labels/returns overlap in time:
  • PURGE   — drop training rows whose label window overlaps a test block.
  • EMBARGO — drop a fraction of training rows immediately AFTER each test block, where
              serial correlation would otherwise leak test information into training.

Our strategies are rule-based genomes (not fit per fold), so the train blocks are used
for purge bookkeeping and the value comes from the combinatorial OOS *paths*: with
n_groups groups and k_test test-groups per split there are C(n_groups, k_test) splits,
each yielding a pooled OOS return — a far richer distribution than 4 rolling folds.

Reuse-first: itertools.combinations + numpy; the CPCV scheme + purge/embargo is the glue.
No new deps. Pure and deterministic.
"""
from __future__ import annotations

from itertools import combinations

import numpy as np


def _group_bounds(n_rows: int, n_groups: int) -> list[tuple[int, int]]:
    """Contiguous, near-equal half-open [s, e) group ranges spanning [0, n_rows)."""
    block = n_rows // n_groups
    bounds = []
    for i in range(n_groups):
        s = i * block
        e = (i + 1) * block if i < n_groups - 1 else n_rows
        bounds.append((s, e))
    return bounds


def _purge_train(train: tuple[int, int], test_blocks: list[tuple[int, int]],
                 embargo: int) -> list[tuple[int, int]]:
    """Return the parts of a train range that survive purge+embargo around every test block."""
    segments = [train]
    for ts, te in test_blocks:
        lo = ts                     # purge: anything from test start …
        hi = te + embargo           # … through test end + embargo window
        nxt: list[tuple[int, int]] = []
        for s, e in segments:
            if e <= lo or s >= hi:          # no overlap with the exclusion zone
                nxt.append((s, e))
                continue
            if s < lo:                      # keep the left piece before the zone
                nxt.append((s, lo))
            if e > hi:                      # keep the right piece after the zone
                nxt.append((hi, e))
        segments = nxt
    return [(s, e) for s, e in segments if e - s >= 2]


def combinatorial_purged_folds(n_rows: int, *, n_groups: int = 6, k_test: int = 2,
                               embargo_pct: float = 0.01) -> list[dict]:
    """Build the CPCV splits.

    Returns a list of paths, each: {"test": [(s,e),…], "train": [(s,e),…], "groups": (…)}.
    There are C(n_groups, k_test) paths. `test` blocks are the held-out groups; `train`
    blocks are the remaining groups after purge + embargo around every test block.
    """
    if n_groups < 3:
        raise ValueError("n_groups must be >= 3 for a meaningful CPCV")
    if not (1 <= k_test < n_groups):
        raise ValueError("k_test must be in [1, n_groups)")
    if n_rows < n_groups * 2:
        raise ValueError(f"need >= {n_groups * 2} rows for {n_groups} groups, got {n_rows}")

    bounds = _group_bounds(n_rows, n_groups)
    embargo = max(1, int(n_rows * embargo_pct))
    paths: list[dict] = []
    for combo in combinations(range(n_groups), k_test):
        test_blocks = [bounds[i] for i in combo]
        train_src = [bounds[j] for j in range(n_groups) if j not in combo]
        train_blocks: list[tuple[int, int]] = []
        for tr in train_src:
            train_blocks += _purge_train(tr, test_blocks, embargo)
        paths.append({"test": test_blocks, "train": train_blocks, "groups": combo})
    return paths


def n_paths(n_groups: int, k_test: int) -> int:
    """Number of CPCV splits — C(n_groups, k_test)."""
    from math import comb
    return comb(n_groups, k_test)
