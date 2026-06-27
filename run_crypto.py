"""run_crypto.py — train the prediction-graph network on REAL crypto data.

Fetches BTC/ETH+majors (CoinGecko, keyless), builds the direction dataset,
trains the stacked ensemble with a CHRONOLOGICAL split (past->future), and
writes state.json so the live dashboard reflects real-data training.

Run:  python3 run_crypto.py   (or: make crypto)
"""
from __future__ import annotations

import json
import os
import time

from core import registry
from data.dataset import MAJORS, chrono_split, ensure, make_dataset
from eval.golden import accuracy
from nodes.base_learners import DecisionStumpNode, KNNNode, LogisticRegressionNode
from nodes.phase2_nodes import GaussianNBNode, MLPNode, ReservoirNode
from nodes.stacking_node import StackingEnsembleNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
BASE_FACTORIES = [
    lambda: LogisticRegressionNode(name="logreg"),
    lambda: KNNNode(k=15, name="knn"),
    lambda: DecisionStumpNode(name="stump"),
    lambda: MLPNode(hidden=8, name="mlp"),
    lambda: ReservoirNode(size=40, name="reservoir"),
    lambda: GaussianNBNode(name="gaussnb"),
]


def main(coin: str = "bitcoin", days: int = 365) -> dict:
    registry.reset()
    counts = ensure(MAJORS, days)
    ds = make_dataset(coin, target="direction")
    Xtr, ytr, Xte, yte = chrono_split(ds["X"], ds["y"], 0.7)

    base_acc = {}
    for factory in BASE_FACTORIES:
        node = factory().fit(Xtr, ytr)
        registry.register(node)
        acc = accuracy(node.predict(Xte), yte)
        base_acc[node.name] = acc
        registry.set_metrics(node.name, {"test_accuracy": round(acc, 4)})

    ens = StackingEnsembleNode(BASE_FACTORIES, folds=5, name="stacking_ensemble")
    ens.fit(Xtr, ytr)
    registry.register(ens, upstream=ens.base_names)
    ens_acc = accuracy(ens.predict(Xte), yte)
    registry.set_metrics(ens.name, {"test_accuracy": round(ens_acc, 4)})

    up_rate = sum(yte) / len(yte)            # naive 'always up' baseline
    baseline = max(up_rate, 1 - up_rate)
    snap = registry.snapshot()
    state = {
        "project": "ML Network Brain — Crypto (real data)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "dataset": {
            "name": f"{coin} daily next-day direction (CoinGecko)",
            "n": len(ds["X"]), "features": len(ds["feature_names"]),
            "train": len(Xtr), "test": len(Xte),
            "coins": list(counts.keys()),
            "feature_names": ds["feature_names"],
            "naive_baseline": round(baseline, 4),
        },
        "headline_accuracy": round(ens_acc, 4),
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n, "test_accuracy": round(base_acc[n], 4)} for n in base_acc]
                   + [{"name": ens.name, "test_accuracy": round(ens_acc, 4)}],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    s = main()
    print(f"Dataset: {s['dataset']['name']}  n={s['dataset']['n']} "
          f"train={s['dataset']['train']} test={s['dataset']['test']}")
    print(f"Naive baseline (always-majority): {s['dataset']['naive_baseline']:.3f}")
    print(f"Ensemble test accuracy:           {s['headline_accuracy']:.3f}")
    for n in s["nodes"]:
        print(f"  {n['kind']:5} {n['name']:20} acc={n['metrics'].get('test_accuracy')}")
