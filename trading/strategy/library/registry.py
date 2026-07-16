"""trading/strategy/library/registry.py — collect the catalog + coverage stats.

Imports every catalog module, concatenates their `STRATEGIES` lists into one registry,
de-duplicates by name, and exposes coverage breakdowns (by category, by segment, by
status) for the runner and the dashboard. Pure aggregation — no backtesting here.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field

from trading.strategy.library.base import (
    CATEGORIES,
    SEGMENTS,
    LibraryStrategy,
    StrategyStatus,
)

# Catalog modules (each exposes a module-level `STRATEGIES: list[LibraryStrategy]`).
_CATALOG_MODULES = [
    "trading.strategy.library.catalog.trend",
    "trading.strategy.library.catalog.mean_reversion",
    "trading.strategy.library.catalog.momentum",
    "trading.strategy.library.catalog.breakout",
    "trading.strategy.library.catalog.volatility",
    "trading.strategy.library.catalog.volume_flow",
    "trading.strategy.library.catalog.pattern",
    "trading.strategy.library.catalog.multi_indicator",
    "trading.strategy.library.catalog.statistical_arbitrage",
    "trading.strategy.library.catalog.market_making",
    "trading.strategy.library.catalog.high_frequency",
    "trading.strategy.library.catalog.order_flow",
    "trading.strategy.library.catalog.options",
    "trading.strategy.library.catalog.event_macro",
    "trading.strategy.library.catalog.machine_learning",
    "trading.strategy.library.catalog.alternative_data",
    "trading.strategy.library.catalog.meta_systems",
]


def _load_all() -> list[LibraryStrategy]:
    out: list[LibraryStrategy] = []
    seen: set[str] = set()
    for mod_name in _CATALOG_MODULES:
        try:
            mod = importlib.import_module(mod_name)
        except Exception as exc:  # a missing/broken catalog module shouldn't kill the rest
            import warnings
            warnings.warn(f"library catalog module {mod_name} failed to import: {exc}")
            continue
        for strat in getattr(mod, "STRATEGIES", []):
            if strat.name in seen:
                continue
            seen.add(strat.name)
            out.append(strat)
    # brain-CREATED strategies (foundry / generators / evolution survivors admitted to the
    # SkillLibrary) — loaded FRESH on every registry (re)build so newly-admitted strategies enter
    # the executor's executable() choice set. This is what closes the strategy-creator loop.
    try:
        from trading.strategy.library.created import load_created_strategies
        for strat in load_created_strategies():
            if strat.name in seen:
                continue
            seen.add(strat.name)
            out.append(strat)
    except Exception as exc:  # never let the created store break the static catalog
        import warnings
        warnings.warn(f"created-strategy catalog failed to load: {exc}")
    return out


@dataclass
class LibraryRegistry:
    strategies: list = field(default_factory=list)

    # ── lookups ──────────────────────────────────────────────────────────────
    def by_category(self, category: str) -> list:
        return [s for s in self.strategies if s.category == category]

    def by_segment(self, segment: str) -> list:
        return [s for s in self.strategies if segment in s.segments]

    def executable(self) -> list:
        return [s for s in self.strategies if s.is_executable]

    def data_gated(self) -> list:
        return [s for s in self.strategies if not s.is_executable]

    def get(self, name: str):
        return next((s for s in self.strategies if s.name == name), None)

    # ── coverage ───────────────────────────────────────────────────────────────
    def coverage(self) -> dict:
        n = len(self.strategies)
        execs = self.executable()
        gated = self.data_gated()
        by_cat = {c: len(self.by_category(c)) for c in CATEGORIES}
        by_cat_other = sum(1 for s in self.strategies if s.category not in CATEGORIES)
        by_seg = {seg: len(self.by_segment(seg)) for seg in SEGMENTS}
        # tally which data requirements gate the gated set
        gate_reasons: dict[str, int] = {}
        for s in gated:
            for r in s.gating_reqs:
                gate_reasons[r] = gate_reasons.get(r, 0) + 1
        # `category` collapses every brain-created strategy (foundry/generators/evolution/
        # autoresearch) to "machine_learning" regardless of what it actually does — that hides
        # whether the created pool is diverse or one generator dominating it. `family` already
        # carries the real diversity signal: "created:<source>" (pysr/alpha_mining/operon/sindy/
        # optuna/llm_mutation/evolution/rd_agent) for created strategies, or a specific sub-family
        # (e.g. "ma_crossover") for static ones — break it down separately so a category rollup
        # never silently hides a mono-source pool.
        by_family: dict[str, int] = {}
        for s in self.strategies:
            fam = s.family or "_unspecified"
            by_family[fam] = by_family.get(fam, 0) + 1
        return {
            "total": n,
            "n_executable": len(execs),
            "n_data_gated": len(gated),
            "by_category": {**by_cat, **({"_uncategorised": by_cat_other} if by_cat_other else {})},
            "by_family": dict(sorted(by_family.items(), key=lambda kv: -kv[1])),
            "by_segment": by_seg,
            "gating_reasons": dict(sorted(gate_reasons.items(), key=lambda kv: -kv[1])),
        }

    def catalog(self) -> list[dict]:
        return [s.to_dict() for s in self.strategies]


_REGISTRY: LibraryRegistry | None = None
_CREATED_SIG: object | None = None


def get_registry(*, reload: bool = False) -> LibraryRegistry:
    """Build (once, cached) the full library registry.

    Auto-rebuilds when the brain-created strategy store (SkillLibrary) changes, so a strategy
    admitted mid-run enters the executor's choice set without a restart — closing the creator loop
    live. The static institutional catalog is otherwise cached (cheap module-level constants), so
    this stays light on the per-cycle path that fixed the run_cycle wedge."""
    global _REGISTRY, _CREATED_SIG
    try:
        from trading.strategy.library.created import created_store_signature
        sig = created_store_signature()
    except Exception:
        sig = _CREATED_SIG
    if _REGISTRY is None or reload or sig != _CREATED_SIG:
        _REGISTRY = LibraryRegistry(strategies=_load_all())
        _CREATED_SIG = sig
    return _REGISTRY


def all_strategies() -> list[LibraryStrategy]:
    return get_registry().strategies
