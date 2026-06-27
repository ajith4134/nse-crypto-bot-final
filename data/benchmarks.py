"""Synthetic benchmark datasets with KNOWN generating processes (stdlib only).

Used for DEVELOPING the growing network: unlike near-random market data, these
have real, measurable signal and tunable chaos/noise, so accuracy provably rises
as the network learns — and they exercise the project's core theme (finding
patterns in chaos/noise). Real-world data is swapped in after the full build.

Series are wrapped as (date, value, 0) rows and run through the SAME feature
engineering as crypto (reuse-first), yielding a next-step direction dataset.
"""
from __future__ import annotations

import math
import random

from data import features as F

BENCHMARKS = ("mackey_glass", "logistic_map", "noisy_xor")


def mackey_glass(n: int = 1500, tau: int = 17, beta: float = 0.2,
                 gamma: float = 0.1, x0: float = 1.2, noise: float = 0.0,
                 seed: int = 1) -> list[float]:
    """Discrete Mackey-Glass delay system — the classic chaotic benchmark."""
    rng = random.Random(seed)
    hist = [x0] * (tau + 1)
    out = []
    x = x0
    for _ in range(n + 200):  # warmup 200
        xtau = hist[-tau]
        x = x + (beta * xtau / (1 + xtau ** 10) - gamma * x)
        if noise:
            x += rng.gauss(0, noise)
        hist.append(x)
        out.append(x)
    return out[200:]


def logistic_map(n: int = 1500, r: float = 3.9, x0: float = 0.4,
                 noise: float = 0.0, seed: int = 2) -> list[float]:
    """Logistic map x->r*x*(1-x): deterministic chaos at r≈3.9."""
    rng = random.Random(seed)
    x = x0
    out = []
    for _ in range(n + 100):
        x = r * x * (1 - x)
        v = x + (rng.gauss(0, noise) if noise else 0.0)
        out.append(v)
    return out[100:]


def noisy_xor_series(n: int = 1500, noise: float = 0.4, seed: int = 3) -> list[float]:
    """A pseudo-series whose direction encodes a noisy nonlinear pattern."""
    rng = random.Random(seed)
    out, phase = [], 0.0
    for t in range(n):
        phase += 0.3
        v = math.sin(phase) + 0.5 * math.sin(2.7 * phase) + rng.gauss(0, noise)
        out.append(v + 5)  # keep positive for pct-change features
    return out


def make_regime_dataset(n: int = 1300, noise_hi: float = 0.15, seed: int = 1) -> dict:
    """Mackey-Glass with a noise regime shift: calm first half, chaotic-noisy
    second half. Returns X, y, and a per-row regime flag (0=calm, 1=noisy)."""
    base = mackey_glass(n=n, noise=0.0, seed=seed, x0=1.2 + (seed % 10) * 0.01)
    rng = random.Random(seed)
    half = len(base) // 2
    series = [v + (rng.gauss(0, noise_hi) if i >= half else 0.0)
              for i, v in enumerate(base)]
    rows = [(i, float(v), 0.0) for i, v in enumerate(series)]   # date = int index
    built = F.build(rows)
    regime = [1 if int(d) >= half else 0 for d in built["dates"]]
    return {"name": "mackey_glass_regime", "n": len(built["X"]),
            "feature_names": built["feature_names"], "X": built["X"],
            "y": built["y_direction"], "regime": regime}


_GEN = {"mackey_glass": mackey_glass, "logistic_map": logistic_map,
        "noisy_xor": noisy_xor_series}


def _tercile_regime(deltas: list[float]) -> list[int]:
    """Label each next-step change by terciles: 0=down, 1=flat, 2=up.

    Ranks the deltas and splits into three equal-size buckets, so the lowest
    third (most negative changes) -> 0, middle -> 1, highest third -> 2. This
    matches the 'regime' head (multiclass, 3 classes) in core/heads.py and is
    aligned 1:1 with the input rows it was computed from.
    """
    n = len(deltas)
    regime = [1] * n
    if n == 0:
        return regime
    order = sorted(range(n), key=lambda k: deltas[k])
    third = max(1, n // 3)
    for rank, idx in enumerate(order):
        regime[idx] = 0 if rank < third else (2 if rank >= 2 * third else 1)
    return regime


def make_benchmark_dataset(name: str = "mackey_glass", n: int = 1500,
                           noise: float = 0.0) -> dict:
    if name not in _GEN:
        raise ValueError(f"unknown benchmark '{name}'; choose {BENCHMARKS}")
    series = _GEN[name](n=n, noise=noise) if name != "logistic_map" \
        else _GEN[name](n=n, noise=noise)
    rows = [(f"t{i}", float(v), 0.0) for i, v in enumerate(series)]
    built = F.build(rows)
    y_dir = built["y_direction"]
    y_delta = built["y_return"]               # next-step change (magnitude head)
    # Multi-output targets, each aligned 1:1 with the X rows. 'y' below is kept
    # exactly as before (== direction) for single-target back-compat.
    targets = {
        "direction": y_dir,                   # binary: sign of next step
        "magnitude": y_delta,                 # regression: next-step change
        "regime": _tercile_regime(y_delta),   # 3-class: down/flat/up terciles
    }
    return {
        "name": name, "n": len(built["X"]),
        "feature_names": built["feature_names"],
        "X": built["X"], "y": y_dir,
        "y_return": y_delta,
        "targets": targets,
    }
