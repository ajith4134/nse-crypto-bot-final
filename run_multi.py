"""run_multi.py — the MULTI-OUTPUT network: an output layer of several heads.

This realises the plan's output layer (not one binary label). On the SAME input
features it trains an independent sub-network per OutputHead — covering all three
task types at once:

    direction  -> binary       (up/down)
    regime     -> multiclass-3 (down/flat/up)
    magnitude  -> regression   (next-step return)

Each head gets its own base-node pool (classifiers auto-handle multiclass;
regressors for the regression head) plus a per-head meta combiner (soft-vote for
classification, mean for regression) that REALLY consumes the base nodes'
predictions. Honest walk-forward split; each head scored with its task's metric
against its task's baseline (majority / mean predictor). Writes state.json with a
real `heads` list + nodes/edges tagged by head, so the dashboard renders multiple
outputs (honest wiring: a node connects only to the head it actually predicts).

Run:  python run_multi.py [benchmark]    (or: make multi)
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
from core.heads import TASK_REGRESSION, OutputHead
from data.benchmarks import make_benchmark_dataset
from data.dataset import chrono_split
from eval.golden import baseline_for, score_head
from nodes import oss_nodes as O

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
N = 1500

HEADS = [
    OutputHead("direction", "binary", 2, "next-step direction (up/down)"),
    OutputHead("regime", "multiclass", 3, "next-step regime (down/flat/up)"),
    OutputHead("magnitude", "regression", 1, "next-step return (regression)"),
]


def cls_pool():
    """Classifier base nodes — the same factories handle binary AND multiclass
    (SklearnNode switches on class count), so one pool serves direction+regime."""
    return [
        ("sk_logreg", O.logreg_node),
        ("sk_knn10", lambda: O.knn_node(10)),
        ("sk_rf100", lambda: O.rf_node(100, None, "sk_rf100")),
        ("xgboost", O.xgboost_node),
        ("lightgbm", O.lightgbm_node),
        ("sk_mlp16", lambda: O.mlp_node(16)),
    ]


def reg_pool():
    """Regressor base nodes for the regression head."""
    return [
        ("sk_ridge", O.ridge_reg_node),
        ("sk_rf_reg", lambda: O.rf_reg_node(100)),
        ("sk_gbdt_reg", O.gbdt_reg_node),
        ("xgboost_reg", O.xgb_reg_node),
    ]


class _MetaView:
    """Minimal NodeProtocol-satisfying view of a per-head meta combiner.

    The combiner is a real soft-vote (classification) / mean (regression) over
    the base nodes' predictions, so upstream=base_names is a TRUE dependency.
    """

    def __init__(self, name, head: OutputHead, proba):
        from core.node_protocol import IOSchema
        self.name = name
        self.kind = "meta"
        self.summary = ("soft-vote over base-node class probabilities"
                        if head.is_classification else "mean over base-node predictions")
        self.task = head.task
        self.head = head.name
        self.schema = IOSchema(0, "base-node predictions", f"{head.task} output")
        self._proba = proba

    def fit(self, X, y):
        return self

    def predict_proba(self, X):
        return [float(r[-1]) for r in self._proba]

    def predict(self, X):
        return [int(np.argmax(r)) for r in self._proba]


def _combine(outputs, task):
    """Soft-vote (classification) or mean (regression) over base predict_output."""
    return np.mean([np.asarray(o, dtype=float) for o in outputs], axis=0)


def main(benchmark: str = "mackey_glass", n: int = N) -> dict:
    registry.reset()
    ds = make_benchmark_dataset(benchmark, n=n, noise=0.05)
    X, feat = ds["X"], ds["feature_names"]

    head_reports = []
    for h in HEADS:
        y = ds["targets"][h.name]
        Xtr, ytr, Xte, yte = chrono_split(X, y, 0.7)
        pool = reg_pool() if h.task == TASK_REGRESSION else cls_pool()

        base_names, base_outs = [], []
        for base_name, factory in pool:
            nd = factory()
            nd.head, nd.task = h.name, h.task
            nd.name = f"{base_name}@{h.name}"
            nd.fit(Xtr, ytr)
            registry.register(nd)
            out = nd.predict_output(Xte)
            sc = score_head(h, out, yte)
            registry.set_metrics(nd.name, {"metric": sc["metric"], "value": round(sc["value"], 4)})
            base_names.append(nd.name)
            base_outs.append(out)

        # per-head meta = real soft-vote / mean over the base nodes' outputs
        meta_out = _combine(base_outs, h.task)
        meta_sc = score_head(h, meta_out.tolist(), yte)
        meta = _MetaView(f"meta@{h.name}", h, meta_out)
        registry.register(meta, upstream=base_names)
        registry.set_metrics(meta.name, {"metric": meta_sc["metric"], "value": round(meta_sc["value"], 4)})

        # output node for this head (the network's ŷ for this target)
        out_node = _MetaView(f"ŷ:{h.name}", h, meta_out)
        out_node.kind = "output"
        registry.register(out_node, upstream=[meta.name])

        base = baseline_for(h, ytr, yte)
        head_reports.append({
            "name": h.name, "task": h.task, "metric": meta_sc["metric"],
            "value": round(meta_sc["value"], 4), "baseline": round(base["value"], 4),
            "beats_baseline": bool(meta_sc["value"] > base["value"]), "n_base_nodes": len(base_names),
        })

    snap = registry.snapshot()
    state = {
        "project": f"ML Network Brain — MULTI-OUTPUT ({benchmark})",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "scikit-learn · XGBoost · LightGBM (multi-head: binary · multiclass · regression)",
        "dataset": {"name": f"{benchmark} (synthetic, known process)", "n": ds["n"],
                    "features": len(feat), "feature_names": feat,
                    "train": int(n * 0.7), "test": int(n * 0.3)},
        "heads": head_reports,
        "multi_output": True,
        "nodes": snap["nodes"], "edges": snap["edges"],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


if __name__ == "__main__":
    bench = sys.argv[1] if len(sys.argv) > 1 else "mackey_glass"
    s = main(bench)
    print(f"MULTI-OUTPUT network on: {s['dataset']['name']}  ({len(s['heads'])} output heads)")
    print(f"{'head':12} {'task':11} {'metric':9} {'value':>7} {'baseline':>9}  beats?")
    for h in s["heads"]:
        print(f"{h['name']:12} {h['task']:11} {h['metric']:9} {h['value']:7.3f} {h['baseline']:9.3f}"
              f"  {'YES' if h['beats_baseline'] else 'no'}  ({h['n_base_nodes']} nodes)")
    print(f"total nodes: {len(s['nodes'])}  edges: {len(s['edges'])}")
