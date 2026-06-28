"""trading/strategy/operators.py — mutation + crossover via DEAP gp (T8.1, reuse-first).

Genetic operators delegate to **deap.gp** (typed-aware `cxOnePoint`, `mutUniform`,
`mutNodeReplacement`); we glue them to the Strategy wrapper (parse src→tree, mutate,
serialise tree→src), add the cheap parameter mutations, and record provenance. All
operators return NEW Strategy objects and only ever produce valid (compilable) trees.
`market_features` is the extension point for market-legal building blocks (crypto-only
funding/liquidation, NSE-only VIX/FII-DII features as those columns come online).
"""
from __future__ import annotations

import copy
import random

import numpy as np
from deap import gp

from trading.strategy.features import FEATURE_NAMES
from trading.strategy.genome import Strategy, get_pset, random_tree

_MARKET_EXTRA = {"CRYPTO": [], "NSE": []}


def market_features(market: str) -> list[str]:
    return list(FEATURE_NAMES) + _MARKET_EXTRA.get(market.upper(), [])


def _safe_expr(pset, type_=None):
    """Subtree generator for mutUniform that tolerates terminal-only types (FloatS/float).

    DEAP's genFull/genGrow raise IndexError when they try to place a primitive of a type
    that has none (our FloatS/float only have terminals). Retry a few times, then fall
    back to a single terminal of the required type.
    """
    for _ in range(20):
        try:
            return gp.genGrow(pset, min_=0, max_=2, type_=type_)
        except IndexError:
            continue
    terms = pset.terminals.get(type_, [])
    if terms:
        return [random.choice(terms)]
    raise IndexError(f"no terminal available for type {type_}")


def _mutate_tree(src: str, pset, rng: np.random.Generator):
    random.seed(int(rng.integers(0, 2**31 - 1)))
    tree = gp.PrimitiveTree.from_string(src, pset)
    try:
        if rng.random() < 0.5:
            (tree,) = gp.mutNodeReplacement(tree, pset)
        else:
            (tree,) = gp.mutUniform(tree, expr=_safe_expr, pset=pset)
    except Exception:
        try:                                  # node-replacement never regenerates subtrees
            (tree,) = gp.mutNodeReplacement(tree, pset)
        except Exception:
            tree = random_tree(pset, rng)     # last resort: a fresh valid tree
    return str(tree)


def mutate(strategy: Strategy, features: list[str] | None = None,
           rng: np.random.Generator | None = None, *, n: int = 1) -> Strategy:
    """Return a mutated copy (tree mutations via DEAP + cheap param mutations)."""
    rng = rng or np.random.default_rng()
    pset = get_pset(strategy.features)
    child = copy.deepcopy(strategy)
    notes = []
    for _ in range(max(1, n)):
        r = rng.random()
        if r < 0.6:
            child.long_src = _mutate_tree(child.long_src, pset, rng)
            notes.append("long")
        elif r < 0.85 and child.short_src:
            child.short_src = _mutate_tree(child.short_src, pset, rng)
            notes.append("short")
        elif r < 0.93:
            child.stop_atr = round(float(np.clip(child.stop_atr + rng.normal(0, 0.5), 0.5, 6.0)), 2)
            child.target_atr = round(float(np.clip(child.target_atr + rng.normal(0, 0.5), 0.5, 10.0)), 2)
            notes.append("params")
        else:
            child.allow_short = not child.allow_short
            if child.allow_short and not child.short_src:
                child.short_src = str(random_tree(pset, rng))
            notes.append("allow_short")
    child.id = ""
    prov = copy.deepcopy(strategy.provenance)
    prov["parents"] = [strategy.id] if strategy.id else prov.get("parents", [])
    prov["mutations"] = prov.get("mutations", []) + notes
    prov["generation"] = prov.get("generation", 0) + 1
    child.provenance = prov
    return child


def crossover(a: Strategy, b: Strategy, rng: np.random.Generator | None = None) -> tuple:
    """Swap subtrees between the long trees of two strategies (DEAP cxOnePoint)."""
    rng = rng or np.random.default_rng()
    random.seed(int(rng.integers(0, 2**31 - 1)))
    if a.features != b.features:
        raise ValueError("crossover requires matching feature sets (same market)")
    pset = get_pset(a.features)
    ca, cb = copy.deepcopy(a), copy.deepcopy(b)
    ta = gp.PrimitiveTree.from_string(ca.long_src, pset)
    tb = gp.PrimitiveTree.from_string(cb.long_src, pset)
    ta, tb = gp.cxOnePoint(ta, tb)
    ca.long_src, cb.long_src = str(ta), str(tb)
    gen = max(a.provenance.get("generation", 0), b.provenance.get("generation", 0)) + 1
    for child, parents in ((ca, [a.id, b.id]), (cb, [b.id, a.id])):
        child.id = ""
        child.provenance = {"generation": gen, "parents": [x for x in parents if x],
                            "mutations": ["crossover"]}
    return ca, cb
