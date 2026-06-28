"""trading/strategy/genome.py — DEAP genetic-programming strategy genome (T8.1, reuse-first).

The GP engine is **DEAP** (`deap.gp`): strategies are strongly-typed GP expression trees
that compile to a vectorised boolean signal. We only supply the trading-specific glue:
the typed primitive set (comparisons / logic / crossovers over features), feature
normalisation so a single constant range is meaningful across all features, and the
Strategy wrapper (serialise via the tree's string form; map long/short trees → +1/-1/0).

Typed primitive set:
  types  : FloatS (a feature Series), BoolS (a boolean Series), float (a constant)
  prims  : and_/or_ (BoolS,BoolS→BoolS); gt/lt/xup/xdn (FloatS,FloatS→BoolS);
           gtc/ltc (FloatS,float→BoolS)
  terms  : the feature args (FloatS); a constant grid (float); TRUE/FALSE (BoolS — these
           guarantee DEAP can always close a branch, sidestepping the typed-GP
           "no terminal of type BoolS" generation error)

Features are z-scored (full-sample) before evaluation so `gt(rsi, sma_fast)` and
`gtc(mom, 1.5)` are scale-free and comparable. Live use would z-score on a rolling window.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from deap import gp

from trading.strategy.features import FEATURE_NAMES

# constant grid (in z-score space) usable by gtc/ltc
_CONST_GRID = [-2.0, -1.5, -1.0, -0.5, 0.0, 0.5, 1.0, 1.5, 2.0]


class FloatS:  # type tag: a float feature Series
    pass


class BoolS:   # type tag: a boolean Series
    pass


# ── primitive functions (operate on pandas Series, broadcast-safe) ───────────────
def _and(a, b):
    return a & b


def _or(a, b):
    return a | b


def _gt(a, b):
    return a > b


def _lt(a, b):
    return a < b


def _gtc(a, c):
    return a > c


def _ltc(a, c):
    return a < c


def _xup(a, b):
    return (a > b) & (a.shift(1) <= b.shift(1))


def _xdn(a, b):
    return (a < b) & (a.shift(1) >= b.shift(1))


_PSET_CACHE: dict[tuple, gp.PrimitiveSetTyped] = {}


def get_pset(features: list[str]) -> gp.PrimitiveSetTyped:
    """Build (once, cached) the typed primitive set for a given feature ordering."""
    key = tuple(features)
    if key in _PSET_CACHE:
        return _PSET_CACHE[key]
    pset = gp.PrimitiveSetTyped("MAIN", [FloatS] * len(features), BoolS)
    pset.renameArguments(**{f"ARG{i}": f for i, f in enumerate(features)})
    pset.addPrimitive(_and, [BoolS, BoolS], BoolS, name="and_")
    pset.addPrimitive(_or, [BoolS, BoolS], BoolS, name="or_")
    pset.addPrimitive(_gt, [FloatS, FloatS], BoolS, name="gt")
    pset.addPrimitive(_lt, [FloatS, FloatS], BoolS, name="lt")
    pset.addPrimitive(_xup, [FloatS, FloatS], BoolS, name="xup")
    pset.addPrimitive(_xdn, [FloatS, FloatS], BoolS, name="xdn")
    pset.addPrimitive(_gtc, [FloatS, float], BoolS, name="gtc")
    pset.addPrimitive(_ltc, [FloatS, float], BoolS, name="ltc")
    for c in _CONST_GRID:
        pset.addTerminal(c, float, name=f"c_{str(c).replace('-', 'm').replace('.', '_')}")
    pset.addTerminal(True, BoolS, name="TRUE")
    pset.addTerminal(False, BoolS, name="FALSE")
    _PSET_CACHE[key] = pset
    return pset


def _zscore(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    z = {}
    for f in features:
        col = df[f].astype(float)
        sd = col.std()
        z[f] = (col - col.mean()) / sd if sd and sd > 0 else col * 0.0
    return pd.DataFrame(z, index=df.index)


def random_tree(pset: gp.PrimitiveSetTyped, rng: np.random.Generator, *, depth: int = 3):
    """A random valid typed GP tree (BoolS root). Retries around typed-gen edge cases."""
    random.seed(int(rng.integers(0, 2**31 - 1)))
    last = None
    for _ in range(20):
        try:
            return gp.PrimitiveTree(gp.genHalfAndHalf(pset, min_=1, max_=depth))
        except Exception as exc:  # rare typed-generation failure → retry with new seed
            last = exc
            random.seed(random.randint(0, 2**31 - 1))
    raise RuntimeError(f"could not generate a valid GP tree: {last}")


def compile_signal(tree, pset: gp.PrimitiveSetTyped, zdf: pd.DataFrame,
                   features: list[str]) -> pd.Series:
    """Compile a tree and evaluate it on the z-scored frame → boolean Series."""
    func = gp.compile(tree, pset)
    out = func(*[zdf[f] for f in features])
    if not isinstance(out, pd.Series):                 # degenerate tree (e.g. just TRUE)
        out = pd.Series(bool(out), index=zdf.index)
    return out.fillna(False).astype(bool)


@dataclass
class Strategy:
    market: str
    long_src: str                                      # str(PrimitiveTree)
    features: list[str]
    short_src: str | None = None
    allow_short: bool = True
    stop_atr: float = 2.0
    target_atr: float = 3.0
    id: str = ""
    provenance: dict = field(default_factory=lambda: {"generation": 0, "parents": [],
                                                      "mutations": []})

    def _pset(self) -> gp.PrimitiveSetTyped:
        return get_pset(self.features)

    def long_tree(self):
        return gp.PrimitiveTree.from_string(self.long_src, self._pset())

    def short_tree(self):
        return (gp.PrimitiveTree.from_string(self.short_src, self._pset())
                if self.short_src else None)

    def signal(self, df: pd.DataFrame) -> pd.Series:
        pset = self._pset()
        zdf = _zscore(df, self.features)
        long_sig = compile_signal(self.long_tree(), pset, zdf, self.features)
        if self.allow_short and self.short_src:
            short_sig = compile_signal(self.short_tree(), pset, zdf, self.features)
        else:
            short_sig = pd.Series(False, index=df.index)
        out = pd.Series(0, index=df.index, dtype=int)
        out[long_sig & ~short_sig] = 1
        out[short_sig & ~long_sig] = -1
        return out

    def to_dict(self) -> dict:
        return {"market": self.market, "long_src": self.long_src, "short_src": self.short_src,
                "features": list(self.features), "allow_short": self.allow_short,
                "stop_atr": self.stop_atr, "target_atr": self.target_atr, "id": self.id,
                "provenance": self.provenance}

    @classmethod
    def from_dict(cls, d: dict) -> "Strategy":
        return cls(market=d["market"], long_src=d["long_src"], features=list(d["features"]),
                   short_src=d.get("short_src"), allow_short=d.get("allow_short", True),
                   stop_atr=d.get("stop_atr", 2.0), target_atr=d.get("target_atr", 3.0),
                   id=d.get("id", ""),
                   provenance=d.get("provenance", {"generation": 0, "parents": [], "mutations": []}))


def random_strategy(features: list[str], rng: np.random.Generator, *, market: str = "CRYPTO",
                    depth: int = 3, strat_id: str = "") -> Strategy:
    pset = get_pset(features)
    allow_short = bool(rng.random() < 0.7)
    long_t = random_tree(pset, rng, depth=depth)
    short_t = random_tree(pset, rng, depth=depth) if allow_short else None
    return Strategy(
        market=market, long_src=str(long_t), features=list(features),
        short_src=str(short_t) if short_t is not None else None, allow_short=allow_short,
        stop_atr=round(float(rng.uniform(1.0, 4.0)), 2),
        target_atr=round(float(rng.uniform(1.5, 6.0)), 2), id=strat_id,
    )
