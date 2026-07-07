"""Tests for Phase E — Avalanche ContinualLearner + world-model continual update."""
import numpy as np
import pandas as pd
import pytest

torch = pytest.importorskip("torch")
pytest.importorskip("avalanche")

from trading.brain.continual import ContinualLearner  # noqa: E402
from trading.brain.worldmodel import MarketWorldModel  # noqa: E402


def _regime(seed, w, n=240):
    """Binary task whose decision boundary depends on the regime weight vector w."""
    rnd = np.random.default_rng(seed)
    X = rnd.normal(size=(n, 6)).astype(np.float32)
    y = (X @ np.asarray(w) > 0).astype(np.int64)
    return X, y


def test_learns_sequential_regimes_without_forgetting():
    # regime A and regime B share structure but differ (related, not adversarial —
    # matching real market regimes; replay+EWC must retain A while learning B)
    Xa, ya = _regime(1, [1.0, 1.0, 0.5, 0.0, 0.0, 0.0])
    Xb, yb = _regime(2, [1.0, 0.8, 0.0, 0.5, 0.0, 0.0])
    cl = ContinualLearner(n_features=6, epochs=6)
    e1 = cl.learn_experience(Xa, ya)
    acc_a_before = e1["acc_per_regime"][0]
    e2 = cl.learn_experience(Xb, yb)
    acc_a_after = e2["acc_per_regime"][0]
    assert acc_a_before >= 0.75, f"failed to learn regime A ({acc_a_before})"
    assert e2["acc_per_regime"][1] >= 0.7, "failed to learn regime B"
    # anti-catastrophic-forgetting: regime A retained within a modest margin
    assert acc_a_after >= acc_a_before - 0.15, (
        f"catastrophic forgetting: {acc_a_before} -> {acc_a_after}")
    proba = cl.predict_proba(Xa[:8])
    assert len(proba) == 8 and all(0 <= p <= 1 for p in proba)
    assert cl.status()["engine"].startswith("avalanche")


def _ohlcv(seed, n=160, drift=0.0):
    rnd = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rnd.normal(drift, 0.01, n)))
    return pd.DataFrame({"open": close, "high": close * 1.01,
                         "low": close * 0.99, "close": close,
                         "volume": rnd.uniform(1e5, 2e5, n)})


def test_worldmodel_updates_online_with_replay():
    wm = MarketWorldModel(seed=0)
    out1 = wm.update_online(_ohlcv(1))
    out2 = wm.update_online(_ohlcv(2, drift=0.002))     # new regime window
    assert out2["windows"] == 2 and out2["rows"] > out1["rows"]
    assert out2["fitted"] and out2["pattern"] == "dreamer-continual-replay"
    # rolling replay cap: old windows fall off, model keeps fitting
    for s in range(3, 13):
        out = wm.update_online(_ohlcv(s))
    assert out["windows"] == 8                           # max_windows honoured
