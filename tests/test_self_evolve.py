"""tests/test_self_evolve.py — lifelong self-evolving strategy loop.

Verifies (research/brain-stitch-gap-map.md, gap #3):
  - The loop honors the gate: OFF by default returns {"gated": True} (no raise).
  - force=True runs the DEAP engine, evaluates a population, records history, persists.
  - The admission wiring grows the SkillLibrary (evolved Strategy -> skill).
  - reevaluate() retires a strategy-skill that no longer scores above the floor.
  - SelfEvolveNode satisfies NodeProtocol and registers (dashboard-sync).

State is isolated (trading.state.STATE_DIR -> tmp) so the live library/history are safe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.node_protocol import NodeProtocol


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    from trading import state
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    return tmp_path


def _ohlcv(seed: int = 0, n: int = 360) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ret = rng.normal(0.0006, 0.012, n) + 0.003 * np.sin(np.arange(n) / 18)
    close = 100 * np.exp(np.cumsum(ret))
    return pd.DataFrame({"open": close, "high": close * (1 + np.abs(rng.normal(0, 0.004, n))),
                         "low": close * (1 - np.abs(rng.normal(0, 0.004, n))),
                         "close": close, "volume": rng.uniform(1e3, 9e3, n)})


def test_gated_off_by_default(isolated_state):
    from trading.strategy.self_evolve import SelfEvolvingLoop
    loop = SelfEvolvingLoop(persist=True)
    out = loop.run_generation(_ohlcv(), market="CRYPTO")     # no force
    assert out["ran"] is False and out["gated"] is True       # gate respected, no raise


def test_force_runs_and_persists(isolated_state):
    from trading.strategy.self_evolve import SelfEvolvingLoop
    loop = SelfEvolvingLoop(persist=True)
    out = loop.run_generation(_ohlcv(seed=1), market="CRYPTO", generations=3,
                              pop_size=12, seed=1, force=True)
    assert out["ran"] is True and out["evaluated"] > 0
    assert len(out["gen_history"]) == 3
    # history persisted + reloads (compounds across sessions)
    assert SelfEvolvingLoop(persist=True).status()["n_batches"] == 1


def test_admission_grows_library(isolated_state):
    """Exercise the evolve→admit wiring directly (independent of strict guardrails)."""
    from trading.strategy.evolve import evolve
    from trading.strategy.registry import promote
    from trading.strategy.operators import market_features
    from trading.strategy.self_evolve import SelfEvolvingLoop

    df = _ohlcv(seed=2)
    result = evolve(df, market="CRYPTO", generations=2, pop_size=12, seed=2, force=True)
    best = result.best[0]                                     # evolved Strategy with _fit
    node = promote(best, market_features("CRYPTO"), metrics=dict(best._fit.oos_metrics))

    loop = SelfEvolvingLoop(persist=True)
    metric, metrics = loop._node_metric(node, best)
    assert metric == pytest.approx(best._fit.score, abs=1e-6)  # uses evolved fitness score
    before = len(loop.library)
    res = loop.library.admit_strategy(best, metric, metrics=metrics, source="self_evolve")
    assert res["admitted"] is True
    assert len(loop.library) == before + 1                    # the library grew


def test_reevaluate_retires_weak_skill(isolated_state):
    from trading.strategy.evolve import evolve
    from trading.strategy.self_evolve import SelfEvolvingLoop

    df = _ohlcv(seed=3)
    best = evolve(df, market="CRYPTO", generations=2, pop_size=12, seed=3, force=True).best[0]
    loop = SelfEvolvingLoop(persist=True)
    loop.library.admit_strategy(best, best._fit.score, metrics={}, source="test")
    assert len(loop.library) == 1
    # retire anything not scoring above an impossibly-high floor -> the skill is pruned
    out = loop.reevaluate(df, market="CRYPTO", retire_below=10_000.0)
    assert len(out["retired"]) == 1 and len(loop.library) == 0


def test_node_protocol_and_registry(isolated_state):
    from trading.strategy.self_evolve import SelfEvolvingLoop, register_self_evolve
    loop = SelfEvolvingLoop(persist=True)
    node = register_self_evolve(loop)
    assert isinstance(node, NodeProtocol)
    p = node.predict_proba([[0], [0]])
    assert len(p) == 2 and all(0.0 <= v <= 1.0 for v in p)
    from core import registry
    assert "self_evolving_loop" in [n["name"] for n in registry.snapshot()["nodes"]]
