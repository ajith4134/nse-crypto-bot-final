"""tests/test_gate_tuner.py — counterfactual gate-threshold sweeps (2026-07-10)."""
from __future__ import annotations

import json


def _rows(n_low=60, n_high=60):
    # low-confidence trades lose (-0.5R), high-confidence win (+1R): best θ ≈ 0.6
    rows = []
    for _ in range(n_low):
        rows.append({"brain_confidence_entry": 0.3, "r_multiple": -0.5, "net_pnl": -5})
    for _ in range(n_high):
        rows.append({"brain_confidence_entry": 0.8, "r_multiple": 1.0, "net_pnl": 10})
    return rows


def test_sweep_finds_profitable_threshold(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(_rows()))
    from trading.brain import gate_tuner
    out = gate_tuner.tune_once()
    conf = out["signals"]["confidence"]
    assert conf["recommended"]["theta"] > 0.3          # cuts the losing lows
    assert conf["recommended"]["mean_R"] == 1.0
    assert conf["uplift_mean_R"] is not None and conf["uplift_mean_R"] > 0
    assert gate_tuner.status()["signals"]              # persisted


def test_min_support_rail(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(_rows(n_low=100, n_high=10)))
    from trading.brain import gate_tuner
    conf = gate_tuner.tune_once()["signals"]["confidence"]
    # the 10 winners alone are below MIN_N — the sweep must NOT recommend that θ
    assert conf["recommended"]["n"] >= gate_tuner.MIN_N


def test_too_few_scored_rows_is_honest(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    (tmp_path / "journal.json").write_text(json.dumps(_rows(n_low=5, n_high=5)))
    from trading.brain import gate_tuner
    conf = gate_tuner.tune_once()["signals"]["confidence"]
    assert conf.get("available") is False
