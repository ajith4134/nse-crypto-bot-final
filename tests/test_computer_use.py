"""tests/test_computer_use.py — the brain's computer-use / GUI agent (trading/brain/gui).

Verifies (research/brain-advanced-features-chat.md — "AI controlling the dashboard"):
  - TargetRegistry ships the two operable surfaces (own dashboard + Freqtrade/FreqUI).
  - Perception reads HTML controls (stdlib parser) and reads a chart from candle data.
  - ActionExecutor is PAPER-FIRST: dry_run plans without firing; live-affecting actions are
    refused unless the executor is armed.
  - GuiSkillLibrary (Voyager-pattern) retrieves a skill by goal and compounds success stats.
  - GuiReflector (Reflexion) distils + recalls lessons.
  - ComputerUseAgent runs a full observe→decide→act→reflect→learn step and practices.
  - ComputerUseNode satisfies NodeProtocol and registers (dashboard-sync).

State is isolated (trading.state.STATE_DIR -> tmp) so the live skills/lessons/wallets are safe.
"""
from __future__ import annotations

import pytest

from core.node_protocol import NodeProtocol


@pytest.fixture()
def isolated_state(tmp_path, monkeypatch):
    from trading import state
    monkeypatch.setattr(state, "STATE_DIR", tmp_path)
    return tmp_path


# ---- targets ---------------------------------------------------------------
def test_default_targets_are_own_and_freqtrade(isolated_state):
    from trading.brain.gui.targets import TargetRegistry
    reg = TargetRegistry(persist=True)
    names = {t.name for t in reg.all()}
    assert {"own_dashboard", "freq_ui"} <= names
    own = reg.get("own_dashboard")
    assert own.kind == "own" and own.api_base.startswith("http")


# ---- perception ------------------------------------------------------------
def test_html_controls_parse():
    from trading.brain.gui.perception import _ButtonHarvester
    h = _ButtonHarvester()
    h.feed('<div><button id="go">Start</button><a href="/x">Open FreqUI</a>'
           '<input type="submit" value="Halt"></div>')
    labels = {e["text"] or e["value"] for e in h.elements}
    assert "Start" in labels and "Halt" in labels


def test_chart_reader_reads_trend():
    from trading.brain.gui.perception import ChartReader
    up = [{"open": i, "high": i + 1, "low": i - 1, "close": float(i)} for i in range(1, 30)]
    r = ChartReader().read_candles(up, "BTC/USDT", "CRYPTO", "5m")
    assert r.trend == "up" and r.last == 29.0 and r.n == 29


# ---- actions: paper-first guard --------------------------------------------
def test_dry_run_plans_without_firing(isolated_state):
    from trading.brain.gui.actions import ActionExecutor
    ex = ActionExecutor()                       # default_dry_run=True, allow_live=False
    res = ex.control("start", "CRYPTO")         # dry by default
    assert res.dry_run and res.ok and res.method == "planned"


def test_live_affecting_refused_unless_armed(isolated_state):
    from trading.brain.gui.actions import ActionExecutor
    ex = ActionExecutor(allow_live=False)
    res = ex.control("mode", "CRYPTO", dry_run=False, mode="REAL", confirm=True)
    assert not res.ok and "not armed" in res.reason


# ---- skills (Voyager) ------------------------------------------------------
def test_skill_retrieval_and_success_compounding(isolated_state):
    from trading.brain.gui.skills import GuiSkillLibrary
    lib = GuiSkillLibrary(persist=True)
    got = lib.retrieve("start crypto", k=1)
    assert got and got[0].name == "start_crypto"
    lib.record_use("start_crypto", True)
    lib.record_use("start_crypto", True)
    assert lib.get("start_crypto").success_rate == 1.0
    # persisted across a fresh load
    lib2 = GuiSkillLibrary(persist=True)
    assert lib2.get("start_crypto").n_used == 2


# ---- reflection (Reflexion) ------------------------------------------------
def test_reflector_distils_and_recalls(isolated_state):
    from trading.brain.gui.reflection import GuiReflector
    rf = GuiReflector(persist=True)
    rf.reflect("start crypto", [{"action": "start", "ok": False, "reason": "URLError unreachable"}], ok=False)
    rec = rf.recall("start crypto")
    assert rec and "unreachable" in rec[0].lesson.lower()
    assert len(rf.failures()) == 1


# ---- agent loop ------------------------------------------------------------
def test_agent_step_and_practice(isolated_state):
    from trading.brain.gui import ComputerUseAgent
    a = ComputerUseAgent(persist=True)
    r = a.step("start crypto", dry_run=True)    # offline-safe: dashboard not running
    assert r["ok"] and r["plan"]["chosen_skill"] == "start_crypto"
    pr = a.practice(rounds=2)
    assert pr["n_skills_practiced"] >= 1
    # experiment feeds the HypothesisLedger research loop
    ex = a.experiment(trades=[])
    assert ex["available"] is True


def test_agent_aborts_into_halted_market(isolated_state, monkeypatch):
    from trading.brain.gui import ComputerUseAgent
    a = ComputerUseAgent(persist=True)
    # fake a HALTED safety read so 'start' is refused (kill-switch respected)
    monkeypatch.setattr(a, "_safety", lambda *args, **kw: {"halted": True, "trading_state": "HALTED",
                                                           "mode": "PAPER", "enabled": False})
    plan = a.decide("start crypto")
    assert plan["abort"] and "HALTED" in plan["reason"]


# ---- NodeProtocol (dashboard-sync) ----------------------------------------
def test_node_conforms_and_registers(isolated_state):
    from trading.brain.gui import ComputerUseNode, register_computer_use_agent
    node = ComputerUseNode()
    assert isinstance(node, NodeProtocol)
    node.fit([[0.0]], [1])
    p = node.predict_proba([[0.0], [0.0]])
    assert len(p) == 2 and all(0.0 <= x <= 1.0 for x in p)
    reg = register_computer_use_agent()
    assert reg.name == "computer_use_agent"
