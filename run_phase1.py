"""run_phase1.py — train the Phase-1 prediction-graph network and emit state.json.

The supervised loop end-to-end: build golden (known) input->output pairs, fit a
stacked ensemble of base nodes, measure held-out accuracy per node and for the
ensemble, register everything, and write the state the dashboard renders.

Run:  python3 run_phase1.py   (or: make phase1)
"""
from __future__ import annotations

import json
import os
import time

from core import registry
from eval.golden import accuracy, make_golden_dataset, train_test_split
from nodes.base_learners import DecisionStumpNode, KNNNode, LogisticRegressionNode
from nodes.stacking_node import StackingEnsembleNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")

BASE_FACTORIES = [
    lambda: LogisticRegressionNode(name="logreg"),
    lambda: KNNNode(k=5, name="knn"),
    lambda: DecisionStumpNode(name="stump"),
]


def main() -> dict:
    registry.reset()
    X, y = make_golden_dataset(n=600, noise=0.45, seed=7)
    Xtr, ytr, Xte, yte = train_test_split(X, y, test_frac=0.3, seed=7)

    # Per-base metrics (trained standalone on the same split, for the dashboard).
    base_acc = {}
    for factory in BASE_FACTORIES:
        node = factory().fit(Xtr, ytr)
        registry.register(node)
        acc = accuracy(node.predict(Xte), yte)
        base_acc[node.name] = acc
        registry.set_metrics(node.name, {"test_accuracy": round(acc, 4)})

    # The meta node consumes the base nodes.
    ens = StackingEnsembleNode(BASE_FACTORIES, folds=5, name="stacking_ensemble")
    ens.fit(Xtr, ytr)
    registry.register(ens, upstream=ens.base_names)
    ens_acc = accuracy(ens.predict(Xte), yte)
    registry.set_metrics(ens.name, {"test_accuracy": round(ens_acc, 4)})

    snap = registry.snapshot()
    state = {
        "project": "ML Network Brain — Phase 1",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {"name": "XOR-of-signs (noisy)", "n": len(X),
                    "features": 2, "train": len(Xtr), "test": len(Xte)},
        "headline_accuracy": round(ens_acc, 4),
        "nodes": snap["nodes"],
        "edges": snap["edges"],
        "history": [{"name": n, "test_accuracy": base_acc.get(n)} for n in base_acc]
                   + [{"name": ens.name, "test_accuracy": round(ens_acc, 4)}],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = main()
    print(f"Ensemble test accuracy: {s['headline_accuracy']:.3f}")
    for n in s["nodes"]:
        print(f"  {n['kind']:5} {n['name']:20} acc={n['metrics'].get('test_accuracy')}")
    print(f"state -> {STATE_PATH}")
