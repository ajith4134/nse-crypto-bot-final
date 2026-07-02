"""run_columns.py — render the COLUMN NETWORK (A→B→C→D) into state.json.

Builds the connected column architecture the user designed and registers it honestly:
  members → per-column intra gate (A) → cross-column router (B), grown+pruned (C),
  brain-context-gated (D). Every edge is a real consumes-relationship; every weight shown
  is the actual trained value (honest-wiring rule).

state.json gets a top-level `columns` layout (ordered key/title/desc/color/members) so the
dashboard can render the columns left→right with live learned weights.

Run:  .venv/bin/python run_columns.py     (then view the dashboard)
"""
from __future__ import annotations

import os

# single-threaded BLAS BEFORE numpy/torch import — fitting the whole 108-node catalog
# many times over deadlocks under multi-threaded OpenMP/BLAS oversubscription (observed:
# the process hangs at 0% CPU). One thread per fit is the researched fix.
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    os.environ.setdefault(_v, "1")

import json
import random
import time

import numpy as np

from core import registry
from core.columns import column_for, get_column, layout_for
from data.benchmarks import make_regime_dataset
from eval.golden import accuracy
from nodes import pool
from nodes.column_network import ColumnNetworkNode
from nodes.gated_node import gate_combine, gate_train, gate_weights, standardize_fit

STATE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "state.json")
# a diverse pool spanning several columns (linear/neighbors/trees/boosting/regime)
WANT = ["sk_logreg", "sk_knn10", "sk_tree5", "sk_rf100", "sk_gbdt", "xgboost",
        "hmm_regime2"]
# FULL mode (ML_COLUMNS_FULL=1): the ENTIRE ~108-node catalog (run_multi.domain_pool),
# so every catalog node appears grouped into its column. CPU-heavy → run in background.
FULL = os.environ.get("ML_COLUMNS_FULL") == "1"


def _pool():
    if FULL:
        from run_multi import domain_pool
        dp = domain_pool()
        nm = lambda e: next(x for x in e if isinstance(x, str))
        fac = lambda e: next(x for x in e if callable(x))
        return [fac(e) for e in dp], [nm(e) for e in dp]
    facs, nms = pool.factories(), pool.names()
    chosen = [(f, n) for f, n in zip(facs, nms) if n in WANT]
    if len(chosen) < 4:
        chosen = list(zip(facs, nms))[:8]
    return [f for f, _ in chosen], [n for _, n in chosen]


def _split(X, y, frac=0.7, seed=7):
    idx = list(range(len(X)))
    random.Random(seed).shuffle(idx)
    cut = int(len(X) * frac)
    p = lambda S, I: [S[i] for i in I]
    return p(X, idx[:cut]), p(y, idx[:cut]), p(X, idx[cut:]), p(y, idx[cut:])


def main() -> dict:
    facs, nms = _pool()
    if FULL:
        # the ENTIRE catalog trains on the multi-output benchmark's direction head
        from data.benchmarks import make_benchmark_dataset
        ds = make_benchmark_dataset("mackey_glass", n=1500, noise=0.02)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["targets"]["direction"])
        net = ColumnNetworkNode(facs, nms, task="binary", head="direction",
                                grow=False, epochs=60, folds=2, intra_folds=2).fit(Xtr, ytr)
    else:
        ds = make_regime_dataset(n=1300, noise_hi=0.15, seed=7)
        Xtr, ytr, Xte, yte = _split(ds["X"], ds["y"])
        net = ColumnNetworkNode(facs, nms, grow=False, epochs=150, folds=3, intra_folds=3
                                ).fit(Xtr, ytr)
    acc = lambda node: round(accuracy(node.predict(Xte), yte), 4)
    intra = net.column_intra_weights(Xte)
    layout = net.layout()
    col_w = net.column_weights(Xte)

    registry.reset()
    # honest 3-layer wiring: members (already fitted inside each column) → columns (A) → network (B)
    member_names, column_names = [], []
    for col in net.columns:
        for e in getattr(col._gate, "experts", []):              # frozen members ("neurons")
            registry.register(e)
            registry.set_metrics(e.name, {"metric": "accuracy", "value": acc(e)})
            member_names.append(e.name)
        registry.register(col, upstream=col.members)             # A: members feed the column
        registry.set_metrics(col.name, {"metric": "intra_gate",
                                        "gate_weights": intra.get(col.column_key, {})})
        column_names.append(col.name)
    registry.register(net, upstream=column_names)                # B: columns feed the network
    registry.set_metrics(net.name, {
        "metric": "accuracy", "value": acc(net), "depth": net.depth,
        "column_weights": col_w, "pruned_columns": net.pruned_columns(Xte),
    })

    snap = registry.snapshot()
    up = sum(yte) / len(yte)
    state = {
        "project": "ML Network Brain — Column Network (A·B·C·D: intra-gate · cross-router · grow/prune · brain-gate)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "columns of same-type nodes → intra-column gate → cross-column router (grown, pruned, brain-gated)",
        "dataset": {"name": ds["name"], "feature_names": ds["feature_names"], "n": ds["n"],
                    "train": len(Xtr), "test": len(Xte), "naive_baseline": round(max(up, 1 - up), 4)},
        "headline_accuracy": acc(net),
        "network_depth": net.depth,
        "columns": layout,                       # ordered dashboard column layout
        "column_weights": col_w,                 # learned cross-column wiring (B)
        "column_intra_weights": intra,           # learned intra-column wiring (A)
        "pruned_columns": net.pruned_columns(Xte),
        "nodes": snap["nodes"], "edges": snap["edges"],
    }
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)
    return state


def _node_json(name, kind, head, summary, metrics, upstream, task="binary"):
    return {"name": name, "kind": kind, "summary": summary, "input_dim": 0,
            "input_desc": "features", "output_desc": f"{task} output", "trained": True,
            "metrics": metrics, "upstream": upstream, "task": task, "head": head}


def full_render() -> dict:
    """FAST full-catalog render: ONE fit per member (deadlock-safe, single-threaded),
    gates trained OUT-OF-SAMPLE on a held-out split (honest, no k-fold explosion).
    Shows ALL ~108 catalog nodes grouped into their columns → cross-column router."""
    from core.columns import COLUMNS
    from data.benchmarks import make_benchmark_dataset

    # n kept small on purpose: several catalog nodes are O(n^2+) (optimal_transport, bocpd,
    # surrogate, tda, rqa) and explode at large n — this is a structural VIZ render, not a
    # leaderboard, so ~700 rows keeps the whole 108-node catalog fitting in ~2 min.
    ds = make_benchmark_dataset("mackey_glass", n=700, noise=0.02)
    X = np.asarray(ds["X"], dtype=float)
    y = np.asarray(ds["targets"]["direction"], dtype=int)
    n = len(X)
    idx = list(range(n))
    random.Random(7).shuffle(idx)
    a, b = int(n * 0.5), int(n * 0.75)
    tr, va, te = idx[:a], idx[a:b], idx[b:]
    Xtr, ytr, Xva, yva, Xte, yte = X[tr], y[tr], X[va], y[va], X[te], y[te]

    facs, nms = _pool()
    survivors, dropped = [], []                      # (name, col_key, va_out, te_out, va_acc)
    import sys
    for i, (f, name) in enumerate(zip(facs, nms)):
        if i % 20 == 0:
            print(f"  ...fitting {i}/{len(nms)}", flush=True)
        try:
            e = f(); e.head, e.task = "direction", "binary"
            e.fit(Xtr.tolist(), ytr.tolist())
            vo = np.nan_to_num(np.asarray(e.predict_output(Xva.tolist()), dtype=float), nan=0.5)
            to = np.nan_to_num(np.asarray(e.predict_output(Xte.tolist()), dtype=float), nan=0.5)
            if vo.shape[1] != 2 or to.shape[1] != 2:
                dropped.append(name); continue
            survivors.append((name, column_for(name), vo, to,
                              float((vo.argmax(1) == yva).mean())))
        except Exception:
            dropped.append(name)

    order = [c.key for c in COLUMNS]
    grouped: dict = {}
    for s in survivors:
        grouped.setdefault(s[1], []).append(s)
    grouped = {k: grouped[k] for k in order if k in grouped}

    nodes, edges, layout, col_te, col_keys, intra_all = [], [], [], [], [], {}
    meanc, stdc = standardize_fit(Xva)               # shared gate-input scaler (val)
    Xzc, Xzc_te = (Xva - meanc) / stdc, (Xte - meanc) / stdc
    col_va = []
    for key, mem in grouped.items():
        col = get_column(key)
        meta_va = np.stack([m[2] for m in mem], axis=1)    # (n_va, M, 2)
        meta_te = np.stack([m[3] for m in mem], axis=1)
        g, noise = gate_train(Xzc, meta_va, yva, True, 120, 0.05, 0.01, True, 0, 7)
        intra = {m[0]: round(float(w), 4)
                 for m, w in zip(mem, gate_weights(g, noise, Xzc, 0, len(mem)).mean(0))}
        intra_all[key] = intra
        col_va.append(gate_combine(gate_weights(g, noise, Xzc, 0, len(mem)), meta_va, True))
        col_te.append(gate_combine(gate_weights(g, noise, Xzc_te, 0, len(mem)), meta_te, True))
        col_keys.append(key)
        cname = f"col_{key}"
        for m in mem:
            nodes.append(_node_json(f"{m[0]}@direction", "base", "direction",
                         f"{col.title} member", {"metric": "accuracy", "value": round(m[4], 4)}, []))
            edges.append({"source": f"{m[0]}@direction", "target": cname, "head": "direction"})
        nodes.append(_node_json(cname, "column", "direction", f"Column '{col.title}': {col.desc}",
                     {"metric": "intra_gate", "gate_weights": intra}, [f"{m[0]}@direction" for m in mem]))
        edges.append({"source": cname, "target": "colnet@direction", "head": "direction"})
        layout.append({"key": key, "title": col.title, "desc": col.desc, "color": col.color,
                       "members": [m[0] for m in mem], "size": len(mem)})

    # cross-column router over all columns (input = features), out-of-sample val
    meta_col_va, meta_col_te = np.stack(col_va, axis=1), np.stack(col_te, axis=1)
    gc, nc = gate_train(Xzc, meta_col_va, yva, True, 150, 0.05, 0.01, True, 0, 7)
    cw = gate_weights(gc, nc, Xzc, 0, len(col_keys)).mean(0)
    column_weights = {k: round(float(v), 4) for k, v in zip(col_keys, cw)}
    pred = gate_combine(gate_weights(gc, nc, Xzc_te, 0, len(col_keys)), meta_col_te, True)
    acc_te = float((pred.argmax(1) == yte).mean())
    pruned = [k for k, v in column_weights.items() if v < 0.01]
    up = float(yte.mean())
    nodes.append(_node_json("colnet@direction", "column_network", "direction",
                 "Cross-column router over the full catalog (single-fit render)",
                 {"metric": "accuracy", "value": round(acc_te, 4),
                  "column_weights": column_weights, "pruned_columns": pruned},
                 [f"col_{k}" for k in col_keys]))

    state = {
        "project": "ML Network Brain — FULL Column Network (all catalog nodes → columns → router)",
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "stack": "entire node catalog grouped into columns → intra-column gate → cross-column router",
        "dataset": {"name": ds.get("name", "mackey_glass"),
                    "feature_names": ds.get("feature_names", []), "n": n,
                    "train": len(tr), "test": len(te), "naive_baseline": round(max(up, 1 - up), 4)},
        "headline_accuracy": round(acc_te, 4), "network_depth": 1,
        "columns": layout, "column_weights": column_weights,
        "column_intra_weights": intra_all, "pruned_columns": pruned,
        "dropped_nodes": dropped, "nodes": nodes, "edges": edges,
    }
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    return state


if __name__ == "__main__":
    s = full_render() if FULL else main()
    if FULL:
        print(f"FULL column network → {STATE_PATH}")
        print(f"  catalog members shown: {sum(c['size'] for c in s['columns'])}  "
              f"dropped: {len(s['dropped_nodes'])}  columns: {len(s['columns'])}  "
              f"accuracy: {s['headline_accuracy']:.3f}")
        print(f"  total graph nodes: {len(s['nodes'])}  edges: {len(s['edges'])}")
        print(f"  column weights: {s['column_weights']}")
        raise SystemExit(0)
    n_members = sum(1 for nd in s["nodes"] if nd["kind"] not in ("column", "column_network"))
    print(f"Column network → {STATE_PATH}")
    print(f"  members: {n_members}  columns: {len(s['columns'])}  "
          f"depth: {s['network_depth']}  accuracy: {s['headline_accuracy']:.3f}")
    print(f"  column weights: {s['column_weights']}")
    if s["pruned_columns"]:
        print(f"  pruned (near-zero): {s['pruned_columns']}")
