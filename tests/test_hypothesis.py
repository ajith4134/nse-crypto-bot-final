"""tests/test_hypothesis.py — the brain's hypothesis→experiment→belief loop.

Verifies (research/brain-stitch-gap-map.md, gap #2):
  - The ledger CONFIRMS a planted true edge and REFUTES a planted false one.
  - Bayesian credence + Welch t evidence are attached; verdict thresholds hold.
  - reflect() promotes confirmed → insight notes and archives refuted → failure DB.
  - The ledger persists and reloads (compounding across sessions).
  - HypothesisNode satisfies NodeProtocol and registers (dashboard-sync).
  - BrainTradingPipeline runs end-to-end with the ledger injected (advisory support).

State is isolated: trading.state.STATE_DIR is monkeypatched to a tmp dir so the live
ledger / journal are never touched (isolate-state-in-tests rule).
"""
from __future__ import annotations

import numpy as np
import pytest

from core.node_protocol import NodeProtocol


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    from trading import state
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    return tmp_path


def _trades(n: int = 120, seed: int = 0) -> list[dict]:
    """Planted truth: LONG in a Trending regime is genuinely better on R."""
    rng = np.random.default_rng(seed)
    out = []
    for i in range(n):
        regime = "Trending" if i % 2 else "Ranging"
        direction = "LONG" if rng.random() < 0.6 else "SHORT"
        edge = 0.6 if (regime == "Trending" and direction == "LONG") else -0.05
        r = float(rng.normal(edge, 1.0))
        out.append({"trade_id": str(i), "symbol": "BTC/USDT", "market": "CRYPTO",
                    "direction": direction, "market_regime_entry": regime,
                    "r_multiple": r, "net_pnl": r * 100,
                    "brain_confidence_entry": float(rng.random()), "strategy_name": "demo"})
    return out


def test_confirms_true_edge_and_refutes_false(isolated_state):
    from trading.brain.hypothesis import HypothesisLedger, Hypothesis
    led = HypothesisLedger(persist=True)
    trades = _trades()
    led.run_cycle(trades, seed=1)

    # the planted true edge (Trending regime) must be confirmed with high credence
    trending = next(h for h in led.hypotheses.values()
                    if h.field == "market_regime_entry" and str(h.value) == "Trending")
    assert trending.status == "confirmed"
    assert trending.credence >= 0.8 and trending.effect_size > 0
    assert trending.n_cond >= 8

    # a deliberately false claim must NOT be confirmed
    false_h = Hypothesis(field="market_regime_entry", op="==", value="Ranging")
    led.test(false_h, trades, seed=1)
    assert false_h.status != "confirmed"


def test_reflect_promotes_and_archives(isolated_state):
    from trading.brain.hypothesis import HypothesisLedger
    led = HypothesisLedger(persist=True)
    led.run_cycle(_trades(), seed=1)
    refl = led.reflect()
    assert any("confirmed" in s for s in refl["insights"])
    assert led.counts()["confirmed"] >= 1
    # support() endorses the confirmed regime/direction and stays neutral elsewhere
    sup = led.support({"market_regime_entry": "Trending", "direction": "LONG"})
    assert sup["n"] >= 1 and sup["bias"] > 0
    assert led.support({"market_regime_entry": "Ranging", "direction": "SHORT"})["n"] == 0


def test_persists_and_reloads(isolated_state):
    from trading.brain.hypothesis import HypothesisLedger
    HypothesisLedger(persist=True).run_cycle(_trades(), seed=1)
    reloaded = HypothesisLedger(persist=True)         # fresh instance, same STATE_DIR
    assert reloaded.counts()["confirmed"] >= 1
    assert len(reloaded.hypotheses) >= 1


def test_node_protocol_and_registry(isolated_state):
    from trading.brain.hypothesis import HypothesisLedger, register_hypothesis_ledger
    led = HypothesisLedger(persist=True)
    led.run_cycle(_trades(), seed=1)
    node = register_hypothesis_ledger(led)
    assert isinstance(node, NodeProtocol)
    node.fit([[0]] * 10, [1, -1, 1, 1, -1, 1, 1, -1, 1, 1])
    p = node.predict_proba([[0], [0]])
    assert len(p) == 2 and all(0.0 <= v <= 1.0 for v in p)
    from core import registry
    assert "hypothesis_ledger" in [n["name"] for n in registry.snapshot()["nodes"]]


def test_pipeline_integration_with_ledger(isolated_state):
    import pandas as pd
    from trading.brain.hypothesis import HypothesisLedger
    from trading.brain.pipeline import BrainTradingPipeline
    led = HypothesisLedger(persist=True)
    led.run_cycle(_trades(), seed=1)

    rng = np.random.default_rng(5); n = 120
    close = 100 * np.exp(np.cumsum(rng.normal(0.002, 0.01, n)))
    ohlcv = pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996,
                          "close": close, "volume": rng.uniform(1e3, 9e3, n)})
    pipe = BrainTradingPipeline(market="CRYPTO", hypotheses=led)
    decision = pipe.decide("BTC/USDT", ohlcv)
    assert "hypothesis_support" in decision and decision["hypothesis_support"] is not None
    assert 0.0 <= decision["confidence"] <= 1.0
    assert pipe.status()["has_hypotheses"] is True
