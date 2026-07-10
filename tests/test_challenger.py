"""tests/test_challenger.py — TradeOutcomeNet champion/challenger duel (2026-07-10)."""
from __future__ import annotations

import os

import numpy as np
import pytest

from trading.brain.challenger import _oof_eval


def _xy(n=200, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 6))
    y = (X[:, 0] + 0.5 * X[:, 1] + rng.normal(0, 0.3, n) > 0).astype(int)
    return X, y


def test_oof_eval_protocol_scores_learnable_signal():
    X, y = _xy()

    def logreg_fp(Xtr, ytr, Xte):
        from sklearn.linear_model import LogisticRegression
        m = LogisticRegression().fit(Xtr, ytr)
        return m.predict_proba(Xte)[:, list(m.classes_).index(1)]

    r = _oof_eval(logreg_fp, X, y)
    assert r["n_scored"] == len(y)
    assert r["oof_accuracy"] > 0.8          # learnable synthetic signal
    assert r["log_loss"] < 0.6


def test_duel_honest_when_too_few_rows(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text("[]")
    from trading.brain import challenger
    out = challenger.duel()
    assert out["available"] is False and "fewer than" in out["reason"]


@pytest.mark.skipif(os.environ.get("ML_NETWORK_SKIP_HEAVY") == "1",
                    reason="TabPFN transformer inference is heavy")
def test_tabpfn_fit_predict_shapes():
    X, y = _xy(n=120)
    from trading.brain.challenger import _tabpfn_fit_predict
    p = _tabpfn_fit_predict(X[:80], y[:80], X[80:])
    assert p.shape == (40,) and ((p >= 0) & (p <= 1)).all()


def test_engine_flag_promotes_tabpfn(monkeypatch):
    """TRADE_NET_ENGINE=tabpfn routes _train_engine through the wrapper (or records an
    honest fallback_reason when the dep is unavailable)."""
    monkeypatch.setenv("TRADE_NET_ENGINE", "tabpfn")
    if os.environ.get("ML_NETWORK_SKIP_HEAVY") == "1":
        pytest.skip("heavy")
    from trading.brain.trade_features import TradeOutcomeNet
    X, y = _xy(n=60)
    net = TradeOutcomeNet()
    model = net._train_engine(X.tolist(), y.tolist())
    assert net.engine == "tabpfn_v2"
    p = model.predict_proba_row(X[0].tolist())
    assert 0.0 <= p <= 1.0
