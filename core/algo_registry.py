"""Declarative algorithm registry — the scalable 'way' to add ANY ML algorithm.

One `AlgoSpec` per algorithm (a single `register(...)` line) describes how to
build and use it; the `UniversalNode` adapter (nodes/universal_node.py) turns any
spec into a NodeProtocol node. Adding an ultra-advanced ML algorithm = ONE line.

Design distilled from sklearn (duck-typed fit/predict_proba), AutoGluon (task
keys + priority), PyCaret (per-algo container fields), sktime (declarative
tag queries), OpenML (license/version pinning). The brain queries the registry
declaratively via build_nodes(task), filtering by task + (never-skip) GPU.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

REGISTRY: dict[str, "AlgoSpec"] = {}


@dataclass(frozen=True)
class AlgoSpec:
    id: str                                   # unique node id, e.g. "imodels_figs"
    import_path: str                          # "module.sub.ClassName" (classifier / default)
    tasks: frozenset                          # subset of {"binary","multiclass","regression"}
    kind: str = "ml"                          # dashboard kind
    summary: str = ""
    fixed_args: dict = field(default_factory=dict)
    reg_import_path: str | None = None        # separate regressor class if different
    probabilistic: bool | None = None         # None => auto-introspect predict_proba
    needs_gpu: bool = False
    requires_env: str = ""                    # env var that must be set to enable (license/token gate)
    license: str = ""
    priority: int = 0
    fit_method: str = "fit"                   # overrides for non-sklearn estimators
    proba_method: str = "predict_proba"
    point_method: str = "predict"


def register(**kwargs) -> AlgoSpec:
    spec = AlgoSpec(**kwargs)
    if spec.id in REGISTRY:
        raise ValueError(f"duplicate algo id: {spec.id}")
    REGISTRY[spec.id] = spec
    return spec


def import_obj(path: str):
    mod, name = path.rsplit(".", 1)
    return getattr(importlib.import_module(mod), name)


def spec_importable(spec: "AlgoSpec") -> bool:
    """True if the spec's class(es) can be imported in this env (else skip it)."""
    for p in (spec.import_path, spec.reg_import_path):
        if not p:
            continue
        try:
            import_obj(p)
        except Exception:
            return False
    return True
