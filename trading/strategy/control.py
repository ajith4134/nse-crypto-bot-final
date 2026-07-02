"""trading/strategy/control.py — feature gate for the evolution/mutation engine.

The strategy CREATION / MUTATION / EVOLUTION engine (DEAP NSGA-II in `evolve.py`, the
genetic operators in `operators.py`) is intentionally **gated OFF by default**. The
current phase only runs the curated, hand-mapped **Strategy Library**
(`trading/strategy/library/`) so we can measure how the known institutional templates
perform on their own BEFORE letting the genetic engine breed/mutate new variants on top
of the survivors.

Nothing here deletes or weakens the evolution code — it stays intact and fully tested.
Flipping the flag (env `STRATEGY_EVOLUTION_ENABLED=1`, or `set_evolution_enabled(True)`,
or calling `evolve(..., force=True)`) re-arms it for the later "evolve the winners" phase.
"""
from __future__ import annotations

import os

# Default OFF for this phase. Env override lets ops re-arm without a code change.
_DEFAULT_ENABLED = False


def _env_flag() -> bool | None:
    raw = os.environ.get("STRATEGY_EVOLUTION_ENABLED")
    if raw is None:
        return None
    return raw.strip().lower() in ("1", "true", "yes", "on")


_OVERRIDE: bool | None = None


def evolution_enabled() -> bool:
    """True if the genetic creation/mutation/evolution engine is allowed to run."""
    if _OVERRIDE is not None:
        return _OVERRIDE
    env = _env_flag()
    if env is not None:
        return env
    return _DEFAULT_ENABLED


def set_evolution_enabled(enabled: bool) -> None:
    """Programmatically arm/disarm the engine (overrides env + default)."""
    global _OVERRIDE
    _OVERRIDE = bool(enabled)


def require_evolution_enabled(*, force: bool = False) -> None:
    """Raise unless the engine is enabled (or explicitly forced for an internal demo)."""
    if force or evolution_enabled():
        return
    raise StrategyEvolutionDisabled(
        "Strategy creation/mutation/evolution is gated OFF for this phase "
        "(trading.strategy.control). The curated Strategy Library is the active feature — "
        "run `run_strategy_library.py`. To re-arm the genetic engine set "
        "STRATEGY_EVOLUTION_ENABLED=1, call set_evolution_enabled(True), or pass "
        "evolve(..., force=True)."
    )


class StrategyEvolutionDisabled(RuntimeError):
    """Raised when the evolution engine is invoked while gated off."""
