"""run_oss.py — train the REUSE-FIRST (OSS-backed) node layer and emit state.json.

This is the realigned counterpart of run_dev.py: instead of the pure-stdlib
miniatures it trains the production OSS nodes (scikit-learn / XGBoost / LightGBM /
ReservoirPy / hmmlearn / nolds) drawn from `nodes.pool`, a real scikit-learn
StackingClassifier meta-node, and an AutoGluon reference node — registering each
so the dashboard auto-reflects them (dashboard-sync). Honest walk-forward
(chronological) split throughout.

Run:  python3 run_oss.py [benchmark]   (or: make oss)
"""
from __future__ import annotations

import json
import os
import sys
import time
import warnings

warnings.filterwarnings("ignore")

import numpy as np

np.seterr(all="ignore")

from core import registry
from data.benchmarks import make_benchmark_dataset
from data.dataset import chrono_split
from eval.golden import accuracy
from nodes import pool
from nodes.oss_nodes import SklearnStackingNode

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
N = 1200


def main(benchmark: str = "mackey_glass", with_autogluon: bool = True) -> dict:
    registry.reset()
    ds = make_benchmark_dataset(benchmark, n=N, noise=0.05)
    Xtr, ytr, Xte, yte = chrono_split(ds["X"], ds["y"], 0.7)
    up = sum(yte) / len(yte)
    baseline = max(up, 1 - up)

    base_acc: dict[str, float] = {}
    for factory in pool.factories():
        node = factory().fit(Xtr, ytr)
        registry.register(node)
        acc = accuracy(node.predict(Xte), yte)
        base_acc[node.name] = acc
        registry.set_metrics(node.name, {"test_accuracy": round(acc, 4)})
    base_names = list(base_acc)

    ens = SklearnStackingNode(name="sk_stacking").fit(Xtr, ytr)
    registry.register(ens, upstream=base_names)
    ens_acc = accuracy(ens.predict(Xte), yte)
    registry.set_metrics(ens.name, {"test_accuracy": round(ens_acc, 4)})

    ag_acc = None
    if with_autogluon:
        try:
            from nodes.automl_node import AutoGluonNode
            ag = AutoGluonNode(time_limit=25, name="autogluon").fit(Xtr, ytr)
            registry.register(ag, upstream=base_names)
            ag_acc = accuracy(ag.predict(Xte), yte)
            registry.set_metrics(ag.name, {"test_accuracy": round(ag_acc, 4)})
        except Exception as e:                       # AutoGluon optional/heavy
            print(f"[autogluon skipped: {e}]")

    snap = registry.snapshot()
    headline = max([ens_acc] + ([ag_acc] if ag_acc is not None else []))
    state = {
        "project": f"ML Network Brain — OSS node layer ({benchmark})",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "scikit-learn · XGBoost · LightGBM · ReservoirPy · hmmlearn · nolds · AutoGluon",
        "dataset": {"name": f"{benchmark} (synthetic, known process)",
                    "n": ds["n"], "features": len(ds["feature_names"]),
                    "train": len(Xtr), "test": len(Xte),
                    "feature_names": ds["feature_names"],
                    "naive_baseline": round(baseline, 4)},
        "headline_accuracy": round(headline, 4),
        "stacking_accuracy": round(ens_acc, 4),
        "autogluon_accuracy": round(ag_acc, 4) if ag_acc is not None else None,
        "nodes": snap["nodes"], "edges": snap["edges"],
        "history": [{"name": n, "test_accuracy": round(base_acc[n], 4)} for n in base_acc]
                   + [{"name": "sk_stacking", "test_accuracy": round(ens_acc, 4)}]
                   + ([{"name": "autogluon", "test_accuracy": round(ag_acc, 4)}]
                      if ag_acc is not None else []),
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    bench = sys.argv[1] if len(sys.argv) > 1 else "mackey_glass"
    s = main(bench)
    print(f"OSS node layer on: {s['dataset']['name']}  n={s['dataset']['n']}")
    print(f"Stack: {s['stack']}")
    print(f"Naive baseline:    {s['dataset']['naive_baseline']:.3f}")
    print(f"Stacking (sklearn):{s['stacking_accuracy']:.3f}")
    if s["autogluon_accuracy"] is not None:
        print(f"AutoGluon:         {s['autogluon_accuracy']:.3f}")
    for n in sorted(s["nodes"], key=lambda d: -(d['metrics'].get('test_accuracy') or 0)):
        print(f"  {n['kind']:8} {n['name']:16} acc={n['metrics'].get('test_accuracy')}")
