"""Golden datasets + evaluation — the 'known input->output first' discipline.

Generates a deterministic, non-linearly-separable dataset (XOR-of-signs with
Gaussian noise) so that a single linear node cannot solve it but a stacked
ensemble can — exactly the supervised loop: fit on known I/O, measure accuracy,
and only then trust the node on unknown inputs.

Inputs:  rng seed, sample count, noise level.
Outputs: (X, y) golden pairs; accuracy() over predictions.
"""
from __future__ import annotations

import random

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
