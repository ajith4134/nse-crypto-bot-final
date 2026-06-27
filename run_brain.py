"""run_brain.py — Step 1: let the brain GROW the network from a candidate pool.

Splits chronologically into train/val/test, grows the network on val (keeping
only nodes that improve it), evaluates the grown brain on the unseen test
window, and writes state.json with a growth curve for the dashboard.

Run:  python3 run_brain.py [benchmark]
"""
from __future__ import annotations

import json
import os
import sys
import time

from core import registry
from core.brain import GrowingBrain
import random

from data.benchmarks import make_benchmark_dataset, make_regime_dataset
from eval.golden import accuracy
from nodes.pool import CANDIDATES

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")


def _split3(X, y, a=0.6, b=0.8):
    n = len(X)
    i, j = int(n * a), int(n * b)
    return (X[:i], y[:i], X[i:j], y[i:j], X[j:], y[j:])


def _split3_shuffled(X, y, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    return _split3([X[i] for i in idx], [y[i] for i in idx])


def _split4(X, y, a=0.5, b=0.65, c=0.8):
    n = len(X)
    i, j, m = int(n * a), int(n * b), int(n * c)
    return (X[:i], y[:i], X[i:j], y[i:j], X[j:m], y[j:m], X[m:], y[m:])


def _split4_shuffled(X, y, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    return _split4([X[i] for i in idx], [y[i] for i in idx])


def main(benchmark: str = "mackey_glass") -> dict:
    registry.reset()
    if benchmark == "regime":
        # distinct calm/noisy regimes; shuffled so all regimes appear in each split
        ds = make_regime_dataset(n=1300, noise_hi=0.15)
        Xtr, ytr, Xval, yval, Xg, yg, Xte, yte = _split4_shuffled(ds["X"], ds["y"])
    else:
        ds = make_benchmark_dataset(benchmark, n=1100, noise=0.02)
        Xtr, ytr, Xval, yval, Xg, yg, Xte, yte = _split4(ds["X"], ds["y"])

    facs = [c[0] for c in CANDIDATES]
    names = [c[1] for c in CANDIDATES]
    brain = GrowingBrain(facs, names)
    history = brain.grow(Xtr, ytr, Xval, yval, combiner="router", regime_aware=True, k=25,
                         Xg=Xg, yg=yg, patience=3)   # guard set stops growth before overfitting
    sel = brain.selected_names()

    # Register the brain-selected nodes (trained on Xtr) with test metrics.
    for i in brain.selected:
        node = brain.trained[i]
        registry.register(node)
        registry.set_metrics(node.name, {"test_accuracy": round(accuracy(node.predict(Xte), yte), 4),
                                         "selected_by_brain": True})
    routed_acc = accuracy(brain.predict(Xte), yte)

    # The routed combiner node — grown BY its own router validation accuracy.
    class _RouterView:
        name, kind = "regime_router", "router"
        summary = "Brain-grown routed combiner (selection metric = router val accuracy)"
        schema = brain.trained[brain.selected[0]].schema
        def fit(self, X, y): return self
        def predict_proba(self, X): return brain.predict_proba(X)
        def predict(self, X): return brain.predict(X)
    registry.register(_RouterView(), upstream=sel)
    registry.set_metrics("regime_router", {"test_accuracy": round(routed_acc, 4)})

    up = sum(yte) / len(yte)
    snap = registry.snapshot()
    state = {
        "project": f"ML Network Brain — Router-Grown ({benchmark})",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": f"{benchmark} — network grown BY router accuracy",
                    "n": ds["n"], "features": len(ds["feature_names"]),
                    "train": len(Xtr), "val": len(Xval), "guard": len(Xg), "test": len(Xte),
                    "naive_baseline": round(max(up, 1 - up), 4),
                    "candidates": len(CANDIDATES), "selected": len(sel)},
        "headline_accuracy": round(routed_acc, 4),
        "router_accuracy": round(routed_acc, 4),
        "selected_nodes": sel,
        "growth_history": history,
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n["name"], "test_accuracy": n["metrics"].get("test_accuracy")}
                    for n in snap["nodes"]],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    bench = sys.argv[1] if len(sys.argv) > 1 else "mackey_glass"
    s = main(bench)
    print(f"Benchmark: {bench}  candidates={s['dataset']['candidates']} "
          f"selected={s['dataset']['selected']}")
    print(f"Naive baseline: {s['dataset']['naive_baseline']:.3f}")
    print("Growth (val drives selection, guard decides when to stop):")
    for h in s["growth_history"]:
        mark = "KEPT  " if h.get("kept") else "rolled"
        print(f"  +{h['added']:14} val {h['val_accuracy']:.3f}  guard {h.get('guard_accuracy')}  "
              f"[{mark} n={h['n_nodes']}]")
    print(f"Router-grown network TEST accuracy: {s['router_accuracy']:.3f} "
          f"(kept {len(s['selected_nodes'])} nodes after guard early-stop)")
    print("selected:", s["selected_nodes"])
