"""Step 3 evidence: do chaos-feature nodes hold accuracy better under noise?

Sweeps Mackey-Glass noise and compares the reservoir node against the new
recurrence and chaos-feature nodes, so we can see which degrades slowest.
"""
from __future__ import annotations

from data.benchmarks import make_benchmark_dataset
from data.dataset import chrono_split
from eval.golden import accuracy
from nodes.chaos_nodes import ChaosFeatureNode, RecurrenceNode
from nodes.phase2_nodes import ReservoirNode

LEVELS = [0.0, 0.02, 0.05, 0.1, 0.2]
MODELS = {
    "reservoir": lambda: ReservoirNode(size=30, name="r"),
    "recurrence": lambda: RecurrenceNode(k=20, name="rc"),
    "chaos_feat": lambda: ChaosFeatureNode(name="cf"),
}


def main() -> dict:
    table = {}
    for nz in LEVELS:
        ds = make_benchmark_dataset("mackey_glass", n=800, noise=nz)
        Xtr, ytr, Xte, yte = chrono_split(ds["X"], ds["y"], 0.7)
        row = {}
        for name, fac in MODELS.items():
            node = fac().fit(Xtr, ytr)
            row[name] = round(accuracy(node.predict(Xte), yte), 4)
        table[nz] = row
    return table


if __name__ == "__main__":
    t = main()
    print(f"{'noise':>7} | " + " | ".join(f"{m:>10}" for m in MODELS))
    print("-" * 46)
    for nz in LEVELS:
        print(f"{nz:>7} | " + " | ".join(f"{t[nz][m]:>10.3f}" for m in MODELS))
