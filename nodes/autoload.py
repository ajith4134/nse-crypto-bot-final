"""pkgutil node auto-loader — the full generalization of ``nodes.pool._extra_candidates``.

The growth pool (``nodes/pool.py``) is a hand-curated candidate list, so node families that were
BUILT but never added to that list never reach the live network (the independent-audit finding:
advanced_ml / automl / symbolic / quant_factor / quant_signal / denoise / detect / cross_sectional
capabilities silently unreachable). This module sweeps EVERY ``nodes/*`` module with
``pkgutil.iter_modules`` and recovers, from each:

  (a) zero-arg (or all-defaulted) ``*_node`` factory functions defined in that module, and
  (b) concrete ``BaseNode`` subclasses whose constructor needs no required args,

returning ``(factory, name)`` tuples in the same shape ``pool.CANDIDATES`` uses.

Safety (preserves the dashboard-524 lazy-load guarantee — no heavy torch/chronos chain pulled in at
pool-import): each module import AND each factory call is individually guarded, and a ``_SKIP`` set
excludes the known-heavy foundation/DL modules (they keep their own opt-in paths in pool.py). So a
missing optional dep or a heavy module simply drops that family instead of breaking the pool. Kept
OFF by default; enabled with ``MLNB_AUTOLOAD_NODES=1``.
"""
from __future__ import annotations

import importlib
import inspect
import pkgutil

import nodes as _nodes_pkg

# Heavy / already-pooled / non-node modules — skipped so autoload stays import-light. The foundation
# + DL + micro-LLM families have their own explicit opt-in candidates in pool.py; the infra modules
# below are not node factories.
_SKIP: set[str] = {
    "__init__", "autoload", "pool", "active_subnet", "reflex", "dynamic_bus",
    "router_node", "cascade_node", "gated_node", "column_network", "column_node",
    "neat_lane", "video_lanes",
    "foundation_nodes", "dl_nodes", "micro_transformer_node", "llm_forecast_node",
    "frontier_nodes",   # frontier = heavy torch/darts experts; opt-in via foundation path
}


def _base_node():
    """The BaseNode class (lazily, so importing this module is cheap)."""
    from core.node_protocol import BaseNode
    return BaseNode


def _no_required_args(obj) -> bool:
    """True if obj (a function or a class __init__) can be called with no positional args."""
    try:
        sig = inspect.signature(obj)
    except (TypeError, ValueError):
        return False
    for p in sig.parameters.values():
        if p.name == "self":
            continue
        if p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY):
            return False
    return True


def _is_concrete_node_class(cls, base) -> bool:
    """A real, instantiable node class defined in the swept module (not the abstract base)."""
    return (isinstance(cls, type) and issubclass(cls, base) and cls is not base
            and not inspect.isabstract(cls)
            and hasattr(cls, "fit") and hasattr(cls, "predict_proba"))


def _sweep(exclude_names=()):
    """Internal generator → ``(factory, name, source_module)`` for every recoverable node family.

    Dedup is on the UNDERSCORE-NORMALIZED name so a module exposing both a ``foo_node()`` factory
    (name ``foo``) and its ``FooNode`` class (name ``foonode`` → normalizes to the same) is counted
    ONCE; the factory (the pool's convention) wins because functions are swept before classes.
    """
    base = _base_node()
    seen_norm: set = {n.replace("_", "").lower() for n in exclude_names}

    def _fresh(name: str) -> bool:
        norm = name.replace("_", "").lower()
        if norm in seen_norm:
            return False
        seen_norm.add(norm)
        return True

    for mi in pkgutil.iter_modules(_nodes_pkg.__path__):
        mname = mi.name
        if mname in _SKIP or mname.startswith("_"):
            continue
        try:
            mod = importlib.import_module(f"nodes.{mname}")
        except Exception:
            continue  # optional dep absent / import cost → skip the whole module, never break
        # (a) *_node factory functions DEFINED in this module, callable with no args
        for fname, fn in inspect.getmembers(mod, inspect.isfunction):
            if not fname.endswith("_node") or fname.startswith("_"):
                continue
            if getattr(fn, "__module__", None) != mod.__name__:
                continue  # only factories defined here, not imported helpers
            if not _no_required_args(fn):
                continue
            name = fname[:-5] or fname
            if _fresh(name):
                yield (lambda fn=fn: fn(), name, mod.__name__)
        # (b) concrete BaseNode subclasses defined here, constructible with no required args
        for cname, cls in inspect.getmembers(mod, inspect.isclass):
            if cname.startswith("_"):
                continue  # skip private mixins/helpers (e.g. _HeadMixin)
            if getattr(cls, "__module__", None) != mod.__name__:
                continue
            if not _is_concrete_node_class(cls, base):
                continue
            if not _no_required_args(cls.__init__):
                continue
            name = cname[:-4].lower() if cname.endswith("Node") else cname.lower()
            if _fresh(name):
                yield (lambda cls=cls: cls(), name, mod.__name__)


def discover(exclude_names=()) -> list[tuple]:
    """Sweep every ``nodes/*`` module → ``[(factory, name), ...]`` for all recoverable node families,
    skipping any name already in ``exclude_names`` (e.g. the pool's current names). Same tuple shape
    as ``pool.CANDIDATES``, so the pool can just extend itself with the result."""
    return [(f, n) for f, n, _ in _sweep(exclude_names)]


def summary(exclude_names=()) -> dict:
    """Honest recovery report for the dashboard/audit: total recovered beyond the pool + a per-module
    breakdown. Instantiation is NOT attempted here — only reflects what CAN be recovered."""
    by_module: dict[str, int] = {}
    names: list[str] = []
    for _f, name, src in _sweep(exclude_names):
        by_module[src] = by_module.get(src, 0) + 1
        names.append(name)
    return {"recovered": len(names), "names": sorted(names),
            "by_module": dict(sorted(by_module.items(), key=lambda kv: -kv[1]))}
