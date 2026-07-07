"""tests/test_created_strategies.py — the strategy-creator loop is closed.

Verifies (research/strategy-creator-to-brain.md): a brain-CREATED strategy admitted to the
SkillLibrary becomes a first-class executable LibraryStrategy that the LIVE executor
(LibraryBrainDecider → library.registry.executable()) actually picks from — so created strategies
can win real trades, not just sit in a ledger.

  - load_created_strategies() wraps an admitted genome skill as an executable LibraryStrategy.
  - get_registry() executable() includes it; the executor's strategies() sees it.
  - the signal is feature-GUARDED: a feed missing a needed column → FLAT (0), never a raise.
  - get_registry() auto-refreshes when the SkillLibrary store changes (loop closes live).

State is isolated (trading.state.STATE_DIR -> tmp) so the live SkillLibrary/registry are safe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from trading.strategy.features import FEATURE_NAMES


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    from trading import state
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    # reset the registry module cache so each test rebuilds against the isolated store
    from trading.strategy.library import registry
    monkeypatch.setattr(registry, "_REGISTRY", None)
    monkeypatch.setattr(registry, "_CREATED_SIG", None)
    return tmp_path


def _admit_one_genome(seed: int = 1, metric: float = 0.9) -> str:
    """Create a real DEAP genome + admit it to the SkillLibrary; return its skill name."""
    from trading.strategy.genome import random_strategy
    from trading.brain.skills import SkillLibrary
    rng = np.random.default_rng(seed)
    strat = random_strategy(list(FEATURE_NAMES), rng, market="CRYPTO")
    lib = SkillLibrary()
    res = lib.admit_strategy(strat, metric, metrics={"oos_sharpe": metric}, source="evolution")
    assert res.get("admitted"), res
    return lib.best(market="CRYPTO").name


def _full_feature_df(n: int = 60) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    return pd.DataFrame({f: rng.normal(0, 1, n) for f in FEATURE_NAMES})


def test_created_strategy_wrapped_and_executable(isolated_state):
    name = _admit_one_genome()
    from trading.strategy.library.created import load_created_strategies
    created = load_created_strategies()
    assert len(created) == 1
    s = created[0]
    assert s.name == name
    assert s.is_executable                      # OHLCV-feed → executable
    assert s.category == "machine_learning"
    assert s.family.startswith("created:")
    assert s.params.get("metric") is not None


def test_created_reaches_registry_and_executor(isolated_state):
    name = _admit_one_genome()
    from trading.strategy.library.registry import get_registry
    execs = get_registry(reload=True).executable()
    assert name in {x.name for x in execs}, "created strategy missing from executable()"
    # the REAL crypto executor decider must see it too
    from trading.crypto.freqtrade.brain_executor import LibraryBrainDecider
    names = {getattr(x, "name", None) for x in LibraryBrainDecider().strategies()}
    assert name in names, "created strategy missing from executor.strategies()"


def test_signal_is_feature_guarded(isolated_state):
    _admit_one_genome()
    from trading.strategy.library.created import load_created_strategies
    s = load_created_strategies()[0]
    # full feature frame → a real +1/-1/0 series (no raise)
    full = s.make_signal(_full_feature_df())
    assert set(full.unique()) <= {-1, 0, 1}
    # a frame missing every genome feature → FLAT, never a KeyError
    empty = pd.DataFrame({"unrelated": np.zeros(20)})
    flat = s.make_signal(empty)
    assert (flat == 0).all()


def test_registry_auto_refreshes_on_store_change(isolated_state):
    from trading.strategy.library import registry
    # first build: no created strategies yet
    assert not [x for x in registry.get_registry().executable() if x.family.startswith("created:")]
    # admit one → next get_registry() (no reload flag) must pick it up via the store signature
    name = _admit_one_genome()
    execs = registry.get_registry().executable()
    assert name in {x.name for x in execs}, "auto-refresh did not pick up the new created strategy"


def test_min_metric_gate(isolated_state):
    _admit_one_genome(metric=0.1)
    from trading.strategy.library.created import load_created_strategies
    assert load_created_strategies(min_metric=0.5) == []      # below floor → excluded
    assert len(load_created_strategies(min_metric=0.0)) == 1  # at floor → included
