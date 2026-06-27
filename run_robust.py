"""Harden: multi-seed robustness of the router-grown brain.

Runs the full grow-with-guard pipeline across several seeds (different chaotic
trajectories + splits) and reports mean ± std test accuracy and node counts, so
we know a single good run wasn't a fluke. Writes robustness.json.
"""
from __future__ import annotations

import json
import os

import run_brain as rb
from core.brain import GrowingBrain
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes.pool import CANDIDATES

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "robustness.json")
SEEDS = [1, 2, 3, 4, 5]


def _one(seed: int) -> dict:
    ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=seed)
    Xtr, ytr, Xval, yval, Xg, yg, Xte, yte = rb._split4_shuffled(ds["X"], ds["y"], seed=seed)
    brain = GrowingBrain([c[0] for c in CANDIDATES], [c[1] for c in CANDIDATES])
    brain.grow(Xtr, ytr, Xval, yval, combiner="router", regime_aware=True,
               k=25, Xg=Xg, yg=yg, patience=3)
    base = max(sum(yte) / len(yte), 1 - sum(yte) / len(yte))
    return {"seed": seed, "test": round(accuracy(brain.predict(Xte), yte), 4),
            "nodes": len(brain.selected), "baseline": round(base, 4)}


def main(seeds=None) -> dict:
    seeds = seeds or SEEDS
    runs = [_one(s) for s in seeds]
    accs = [r["test"] for r in runs]
    n = len(accs)
    mean = sum(accs) / n
    std = (sum((a - mean) ** 2 for a in accs) / n) ** 0.5
    summary = {
        "seeds": seeds, "runs": runs,
        "mean": round(mean, 4), "std": round(std, 4),
        "min": min(accs), "max": max(accs),
        "baseline_mean": round(sum(r["baseline"] for r in runs) / n, 4),
        "avg_nodes": round(sum(r["nodes"] for r in runs) / n, 1),
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    return summary


if __name__ == "__main__":
    s = main()
    print(f"{'seed':>5} | test  | nodes | baseline")
    print("-" * 34)
    for r in s["runs"]:
        print(f"{r['seed']:>5} | {r['test']:.3f} | {r['nodes']:>4}  | {r['baseline']:.3f}")
    print("-" * 34)
    print(f"mean test = {s['mean']:.3f} ± {s['std']:.3f}  "
          f"(min {s['min']:.3f}, max {s['max']:.3f})  vs baseline {s['baseline_mean']:.3f}")
    print(f"avg nodes kept = {s['avg_nodes']}")
