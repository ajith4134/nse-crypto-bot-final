"""tests/test_dreamer.py — Counterfactual Dream-Trainer (2026-07-10)."""
from __future__ import annotations

import json


def _rows():
    # 10 losers whose MAE dwarfed MFE → direction regret dominates
    losers = [{"symbol": "AAA", "strategy_name": "breakout", "net_pnl": -10,
               "mfe": 0.2, "mae": 2.0, "exit_efficiency": 0.9}] * 10
    # 10 winners that gave back most of a big MFE → exit-timing regret dominates
    leavers = [{"symbol": "BBB/USDT", "strategy_name": "meanrev", "net_pnl": 5,
                "mfe": 3.0, "mae": 0.3, "exit_efficiency": 0.2,
                "tailgate_peak_profit_pct": 3.0,
                "tailgate_locked_profit_pct": 2.8}] * 10
    return losers + leavers


def test_regret_decomposition(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(_rows()))
    from trading.brain import dreamer
    out = dreamer.dream_once()
    assert out["n_dreamed"] == 20
    by = {(l["strategy"], l["market"]): l for l in out["lessons"]}
    assert by[("breakout", "NSE")]["dominant_regret"] == "direction"
    assert by[("meanrev", "CRYPTO")]["dominant_regret"] == "exit"
    # persisted for the API + learn loop
    assert dreamer.status()["lessons"]


def test_study_topics_follow_dominant_regret(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(_rows()))
    from trading.brain import dreamer
    dreamer.dream_once()
    topics = dreamer.study_topics(max_topics=2)
    assert topics and any("exit" in t or "direction" in t for t in topics)


def test_rows_without_excursions_are_skipped_not_faked(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(
        [{"symbol": "C", "strategy_name": "s", "net_pnl": 1}] * 20))
    from trading.brain import dreamer
    out = dreamer.dream_once()
    assert out["n_dreamed"] == 0 and out["lessons"] == []
