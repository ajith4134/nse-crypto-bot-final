"""run_dev.py — train the growing network on a synthetic benchmark (default data).

Now includes: 8 base node families, a static stacking meta AND a learned router
(Phase 3, dynamic per-input routing), and a noise-sweep showing how the reservoir
node degrades as injected chaos-noise rises. Writes state.json for the dashboard.

Run:  python3 run_dev.py [benchmark]   (or: make dev)
"""
from __future__ import annotations

import json
import os
import sys
import time

from core import registry
from data.benchmarks import make_benchmark_dataset
from data.dataset import chrono_split
from eval.golden import accuracy
from nodes.base_learners import DecisionStumpNode, KNNNode, LogisticRegressionNode
from nodes.phase2_nodes import GaussianNBNode, MLPNode, ReservoirNode
from nodes.phase2b_nodes import RandomForestNode, RegimeGatedNode
from nodes.router_node import LearnedRouterNode
from nodes.stacking_node import StackingEnsembleNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
N = 1000

BASE_FACTORIES = [
    lambda: LogisticRegressionNode(name="logreg"),
    lambda: KNNNode(k=15, name="knn"),
    lambda: DecisionStumpNode(name="stump"),
    lambda: MLPNode(hidden=6, epochs=120, name="mlp"),
    lambda: ReservoirNode(size=30, name="reservoir"),
    lambda: GaussianNBNode(name="gaussnb"),
    lambda: RandomForestNode(n_trees=10, depth=3, name="random_forest"),
    lambda: RegimeGatedNode(gate_idx=8, name="regime_gated"),
]


def noise_sweep(levels) -> list[dict]:
    """Reservoir-node accuracy on Mackey-Glass as injected noise rises (fast)."""
    out = []
    for nz in levels:
        ds = make_benchmark_dataset("mackey_glass", n=700, noise=nz)
        Xtr, ytr, Xte, yte = chrono_split(ds["X"], ds["y"], 0.7)
        node = ReservoirNode(size=30, name="rsweep").fit(Xtr, ytr)
        out.append({"noise": nz, "accuracy": round(accuracy(node.predict(Xte), yte), 4)})
    return out


def main(benchmark: str = "mackey_glass") -> dict:
    registry.reset()
    ds = make_benchmark_dataset(benchmark, n=N, noise=0.0)
    Xtr, ytr, Xte, yte = chrono_split(ds["X"], ds["y"], 0.7)

    base_acc = {}
    for factory in BASE_FACTORIES:
        node = factory().fit(Xtr, ytr)
        registry.register(node)
        acc = accuracy(node.predict(Xte), yte)
        base_acc[node.name] = acc
        registry.set_metrics(node.name, {"test_accuracy": round(acc, 4)})

    base_names = [f().name for f in BASE_FACTORIES]

    ens = StackingEnsembleNode(BASE_FACTORIES, folds=3, name="stacking_ensemble").fit(Xtr, ytr)
    registry.register(ens, upstream=base_names)
    ens_acc = accuracy(ens.predict(Xte), yte)
    registry.set_metrics(ens.name, {"test_accuracy": round(ens_acc, 4)})

    router = LearnedRouterNode(BASE_FACTORIES, k=25, regime_aware=True,
                               name="learned_router").fit(Xtr, ytr)
    registry.register(router, upstream=base_names)
    rt_acc = accuracy(router.predict(Xte), yte)
    registry.set_metrics(router.name, {"test_accuracy": round(rt_acc, 4),
                                       "routing": router.routing_histogram(Xte)})

    up = sum(yte) / len(yte)
    baseline = max(up, 1 - up)
    sweep = noise_sweep([0.0, 0.02, 0.05, 0.1, 0.2, 0.4])
    snap = registry.snapshot()
    state = {
        "project": f"ML Network Brain — DEV ({benchmark})",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": f"{benchmark} (synthetic, known process) — next-step direction",
                    "n": ds["n"], "features": len(ds["feature_names"]),
                    "train": len(Xtr), "test": len(Xte),
                    "feature_names": ds["feature_names"],
                    "naive_baseline": round(baseline, 4)},
        "headline_accuracy": round(max(ens_acc, rt_acc), 4),
        "stacking_accuracy": round(ens_acc, 4),
        "router_accuracy": round(rt_acc, 4),
        "nodes": snap["nodes"], "edges": snap["edges"],
        "noise_sweep": sweep,
        "history": [{"name": n, "test_accuracy": round(base_acc[n], 4)} for n in base_acc]
                   + [{"name": "stacking_ensemble", "test_accuracy": round(ens_acc, 4)},
                      {"name": "learned_router", "test_accuracy": round(rt_acc, 4)}],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    bench = sys.argv[1] if len(sys.argv) > 1 else "mackey_glass"
    s = main(bench)
    print(f"DEV dataset: {s['dataset']['name']}  n={s['dataset']['n']}")
    print(f"Naive baseline:    {s['dataset']['naive_baseline']:.3f}")
    print(f"Stacking ensemble: {s['stacking_accuracy']:.3f}")
    print(f"Learned router:    {s['router_accuracy']:.3f}")
    for n in s["nodes"]:
        print(f"  {n['kind']:6} {n['name']:18} acc={n['metrics'].get('test_accuracy')}")
    print("noise sweep:", [(d['noise'], d['accuracy']) for d in s['noise_sweep']])
