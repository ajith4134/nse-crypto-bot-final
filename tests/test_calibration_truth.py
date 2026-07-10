"""tests/test_calibration_truth.py — calibration honesty + error-driven learning (2026-07-10).

Pins the ETH-brier-0.0 fix (a stored 0.0 confidence is a missing-value artifact, not a
perfect forecast), the new ECE/reliability surface, and the learn-loop's mistake-driven
topic picker.
"""
from __future__ import annotations

import json
import types

from trading.journal.confidence import ConfidenceBook, SymbolConfidence, _as_prob


def _trade(symbol="X", net_pnl=1.0, conf=None):
    return types.SimpleNamespace(symbol=symbol, net_pnl=net_pnl,
                                 brain_confidence_entry=conf,
                                 brain_prediction=None, direction="LONG",
                                 brain_correct=None)


def test_zero_and_negative_confidence_are_missing_not_perfect():
    assert _as_prob(0.0) is None          # default-value artifact, NOT a forecast
    assert _as_prob(-1) is None           # sentinel
    assert _as_prob(0.55) == 0.55
    assert _as_prob(55) == 0.55           # 0–100 scale auto-detected
    sc = SymbolConfidence(symbol="ETH")
    sc.update(won=False, predicted_prob=0.0)
    assert sc.brier is None               # the old code scored this as a PERFECT 0.0


def test_ece_and_reliability_from_real_pairs():
    book = ConfidenceBook()
    # brain says 0.9 but loses half the time → miscalibrated, ECE > 0
    for won in (True, False, True, False):
        book.update_from_trade(_trade(net_pnl=1.0 if won else -1.0, conf=0.9))
    d = book.as_dict()
    assert d["calib_n"] == 4
    assert d["ece"] is not None and d["ece"] > 0.3
    hot = [b for b in d["reliability"] if b["n"]]
    assert len(hot) == 1 and hot[0]["win_rate"] == 0.5 and hot[0]["avg_p"] == 0.9


def test_no_forecasts_means_null_not_fake(monkeypatch):
    book = ConfidenceBook()
    book.update_from_trade(_trade(conf=None))
    d = book.as_dict()
    assert d["ece"] is None and d["calib_n"] == 0


def test_mistake_topics_from_loss_clusters(monkeypatch, tmp_path):
    from trading import state as tstate
    from trading.brain.learn_loop import LearnLoop
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    rows = ([{"strategy_name": "breakout", "market_regime": "volatile", "net_pnl": -5}] * 10
            + [{"strategy_name": "meanrev", "market_regime": "ranging", "net_pnl": 3}] * 10)
    (tmp_path / "journal.json").write_text(json.dumps(rows))
    loop = LearnLoop()
    topics = loop.mistake_topics()
    assert topics and "breakout" in topics[0] and "volatile" in topics[0]
    assert not any("meanrev" in t for t in topics)     # winners are not "mistakes"
    # even cycle → the mistake topic outranks the static curriculum
    st = {"cycles": 0, "queue": [], "done": [], "errors": []}
    assert loop.pick_topic(st) == topics[0]


def test_small_or_winning_groups_do_not_trigger(monkeypatch, tmp_path):
    from trading import state as tstate
    from trading.brain.learn_loop import LearnLoop
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    rows = [{"strategy_name": "tiny", "market_regime": "any", "net_pnl": -1}] * 5
    (tmp_path / "journal.json").write_text(json.dumps(rows))
    assert LearnLoop().mistake_topics() == []          # n<8 → not a cluster yet
