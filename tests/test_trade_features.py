"""tests/test_trade_features.py — the trade-row → node-network bridge (TradeOutcomeNet).

Verifies: the fixed feature vector matches FEATURE_NAMES for both open- and closed-trade
dicts; the network trains on closed trades and predicts open ones; it learns a separable
signal (OOF accuracy beats the base rate); and it degrades honestly when under-sampled.
"""
import random

from trading.brain.trade_features import (
    FEATURE_NAMES,
    TradeOutcomeNet,
    trade_feature_row,
)


def _closed(win: bool, i: int) -> dict:
    conf = 0.6 + random.random() * 0.3 if win else 0.25 + random.random() * 0.3
    return dict(
        symbol="BTC/USDT", market="CRYPTO", exchange="binance", direction="LONG",
        quantity=1, entry_price=65000, capital=65000, leverage=1,
        market_regime_entry="trending" if win else "volatile",
        brain_confidence_entry=conf, mfe=800 if win else 90, mae=90 if win else 700,
        r_multiple=(1.9 if win else -1.0), net_pnl=(500 if win else -400),
        node_contributions=[{"anomaly_score": 0.1,
                             "news_compound": 0.3 if win else -0.2, "recall_bias": 0.1}],
        entry_datetime="2026-06-29T10:30:00")


def test_feature_row_length_matches_schema():
    row_closed = trade_feature_row(_closed(True, 0))
    row_open = trade_feature_row(dict(symbol="ETH/USDT", market="CRYPTO", direction="LONG",
                                      quantity=2, entry_price=3000, capital=6000,
                                      peak_profit=120, peak_loss=-30,
                                      brain_entry={"confidence": 0.7, "regime": "trending"}))
    assert len(row_closed) == len(FEATURE_NAMES)
    assert len(row_open) == len(FEATURE_NAMES)
    assert all(isinstance(v, float) for v in row_closed + row_open)


def test_network_trains_and_predicts():
    random.seed(7)
    closed = [_closed(i % 5 != 0, i) for i in range(45)]   # ~80% wins, both classes present
    net = TradeOutcomeNet().fit_from_journal(closed)
    assert net.trained is True
    assert net.engine in ("gated_moe", "numpy_logreg")
    assert net.n_train == 45
    # learns a real signal: out-of-fold accuracy beats the base rate
    assert net.oof_accuracy is not None and net.oof_accuracy >= net.base_rate

    preds = net.predict([dict(symbol="BTC/USDT", market="CRYPTO", direction="LONG",
                              quantity=1, entry_price=65000, capital=65000, peak_profit=400,
                              peak_loss=-20, brain_confidence_entry=0.8,
                              market_regime_entry="trending")])
    assert len(preds) == 1
    p = preds[0]
    assert p["symbol"] == "BTC/USDT"
    assert 0.0 <= p["p_win"] <= 1.0
    assert p["verdict"] in ("WIN likely", "LOSS likely", "uncertain")


def test_degrades_honestly_when_undersampled():
    net = TradeOutcomeNet().fit_from_journal([_closed(True, i) for i in range(4)])
    assert net.trained is False
    out = net.predict_one(dict(symbol="X", direction="LONG", entry_price=1, quantity=1,
                               brain_entry={"confidence": 0.66}))
    assert out["p_win"] is None
    assert out["verdict"] == "insufficient history"
    assert out["confidence"] == 0.66      # falls back to the brain confidence on the trade
