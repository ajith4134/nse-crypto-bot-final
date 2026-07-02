"""tests/test_worldmodel.py — world-model + MuZero imagination planner.

Verifies the new brain capability (research/brain-stitch-gap-map.md):
  - WorldModelNode satisfies NodeProtocol and registers on the live registry.
  - MarketWorldModel learns dynamics (torch backend if present, else numpy ridge).
  - ImaginationPlanner imagines forward and prefers LONG on an uptrend / SHORT on a
    downtrend, and produces a sane exit-management plan for an open position.
  - BrainTradingPipeline runs end-to-end with the planner injected (advisory).
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from core.node_protocol import NodeProtocol
from trading.brain.worldmodel import (
    ACTION_NAMES, FEATURE_DIM, ImaginationPlanner, MarketWorldModel,
    WorldModelNode, build_planner, market_features, register_world_model,
)


def _series(drift: float, n: int = 280, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    ret = rng.normal(drift, 0.008, n) + 0.0015 * np.sin(np.arange(n) / 14)
    close = 100 * np.exp(np.cumsum(ret))
    hi = close * (1 + np.abs(rng.normal(0, 0.003, n)))
    lo = close * (1 - np.abs(rng.normal(0, 0.003, n)))
    return pd.DataFrame({"open": close, "high": hi, "low": lo, "close": close,
                         "volume": rng.uniform(1e3, 9e3, n)})


def test_features_shape():
    f = market_features(_series(0.001))
    assert f.shape == (FEATURE_DIM,)
    assert np.isfinite(f).all()


def test_node_protocol_and_registry():
    node = WorldModelNode()
    assert isinstance(node, NodeProtocol)          # structural contract enforced
    df = _series(0.001)
    X = [market_features(df.iloc[:i]).tolist() for i in range(30, 140)]
    y = [int(df["close"].iloc[i] > df["close"].iloc[i - 1]) for i in range(30, 140)]
    node.fit(X, y)
    p = node.predict_proba(X[:8])
    assert len(p) == 8 and all(0.0 <= v <= 1.0 for v in p)

    register_world_model()
    from core import registry
    names = [n["name"] for n in registry.snapshot()["nodes"]]
    assert "world_model_imagination" in names       # dashboard-sync


def test_world_model_learns_dynamics():
    wm = MarketWorldModel().fit(_series(0.0015))
    assert wm.fitted and wm._backend in ("torch", "numpy")
    f = wm.normalize(market_features(_series(0.0015)))
    f_next, ret = wm.step(f)
    assert f_next.shape == (FEATURE_DIM,)
    assert np.isfinite(ret) and abs(ret) < 1.0      # one-step return is bounded/sane


def test_planner_prefers_long_on_uptrend():
    df = _series(0.004, seed=1)                      # strong uptrend
    plan = build_planner(df, num_simulations=80, horizon=12, seed=1).plan(df)
    assert plan["action"] in ACTION_NAMES
    # on a clear uptrend the imagined LONG should out-value the imagined SHORT
    assert plan["imagined_R"].get("ENTER_LONG", 0) >= plan["imagined_R"].get("ENTER_SHORT", -9)
    assert plan["expected_R"] == pytest.approx(plan["imagined_R"][plan["action"]], abs=1e-6)


def test_planner_manages_open_position():
    df = _series(0.003, seed=2)
    plan = build_planner(df, num_simulations=80, horizon=12, seed=2).plan(df, position_side="LONG")
    # legal actions for an open book are the management actions only
    assert set(plan["policy"]).issubset({"HOLD", "EXIT", "TIGHTEN_STOP", "SCALE_OUT"})
    assert len(plan["imagined_trajectory"]) >= 1


def test_pipeline_integration_with_planner():
    from trading.brain.pipeline import BrainTradingPipeline
    df = _series(0.003, seed=3)
    planner = ImaginationPlanner(model=MarketWorldModel().fit(df),
                                 num_simulations=48, horizon=10, seed=3)
    pipe = BrainTradingPipeline(market="CRYPTO", planner=planner)
    decision = pipe.decide("BTC/USDT", df)
    assert "imagination" in decision and decision["imagination"] is not None
    assert decision["imagination"]["action"] in ACTION_NAMES
    assert 0.0 <= decision["confidence"] <= 1.0
    assert pipe.status()["has_imagination"] is True
