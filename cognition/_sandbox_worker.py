"""cognition/_sandbox_worker.py — isolated fit+score worker for P4.7 self-coding.

Run as a SUBPROCESS (``python -m cognition._sandbox_worker``) by cognition.self_coding.Sandbox.
Reads ONE candidate spec as JSON on stdin, regenerates the deterministic golden dataset from a
seed, builds the candidate node from its AlgoSpec (estimator import_path is allow-listed by the
parent BEFORE spawn — this worker never eval()s code), fits + scores it on a held-out split, and
writes the result as JSON on stdout. Crash / timeout / OOM in here cannot touch the parent: the
parent caps CPU + address space (resource.setrlimit) and wall-clock (subprocess timeout), and
runs us with a stripped, network-free env.

Input  (stdin JSON):  {import_path, reg_import_path, fixed_args, params, task, head,
                       dataset, n, noise, seed}
Output (stdout JSON):  {ok, score, baseline, beats, metric}  | {ok: false, error}
"""
from __future__ import annotations

import json
import sys
import warnings

warnings.filterwarnings("ignore")


def _run(req: dict) -> dict:
    from core.algo_registry import AlgoSpec
    from core.heads import OutputHead
    from data.benchmarks import make_benchmark_dataset
    from eval.golden import baseline_for, score_head
    from nodes.universal_node import UniversalNode

    task = req["task"]
    head_name = req["head"]
    # deterministic golden benchmark (known generating process) — reproducible from the seed
    ds = make_benchmark_dataset(req.get("dataset", "mackey_glass"),
                                n=int(req.get("n", 1200)), noise=float(req.get("noise", 0.05)))
    X = ds["X"]
    cut = int(len(X) * 0.7)
    Xtr, Xte = X[:cut], X[cut:]
    ytr, yte = ds["targets"][head_name][:cut], ds["targets"][head_name][cut:]

    spec = AlgoSpec(id=req.get("id", "candidate"), import_path=req["import_path"],
                    tasks=frozenset({task}), kind="invented",
                    fixed_args=req.get("fixed_args", {}),
                    reg_import_path=req.get("reg_import_path"))
    node = UniversalNode(spec, **req.get("params", {}))
    node.task, node.head = task, head_name
    node.fit(Xtr, ytr)

    n_classes = {"binary": 2, "multiclass": 3, "regression": 1}.get(task, 2)
    head = OutputHead(head_name, task, n_classes)
    sc = score_head(head, node.predict_output(Xte), yte)
    bl = baseline_for(head, ytr, yte)
    return {"ok": True, "metric": sc["metric"], "score": round(float(sc["value"]), 4),
            "baseline": round(float(bl["value"]), 4),
            "beats": bool(sc["value"] > bl["value"])}


def main() -> None:
    try:
        req = json.loads(sys.stdin.read() or "{}")
        out = _run(req)
    except Exception as e:  # any failure is a clean rejection, never a parent-side crash
        out = {"ok": False, "error": f"{type(e).__name__}: {str(e)[:160]}"}
    sys.stdout.write(json.dumps(out))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
