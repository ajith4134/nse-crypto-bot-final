"""tests/test_fast_nav.py — fast-nav planner over learned app-school state (2026-07-10)."""
from __future__ import annotations

import json


def _seed(tmp_path, skills=None):
    school = {"links": {"upstox": {
        "https://pro.upstox.com/holdings": {"seen": 134, "text": "Holdings"},
        "https://pro.upstox.com/orders": {"seen": 90, "text": "Orders"},
        "https://pro.upstox.com/funds/securities/wallet": {"seen": 10, "text": "Funds"}}},
        "pages": {"upstox": {}}, "routes": {}}
    (tmp_path / "app_school_map.json").write_text(json.dumps(school))
    (tmp_path / "ui_skills.json").write_text(json.dumps(skills or {}))


def test_plan_prefers_learned_url_then_explore(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed(tmp_path)
    from trading.brain.vision import fast_nav
    p = fast_nav.plan("upstox", "holdings")
    assert p[0]["method"] == "goto" and "holdings" in p[0]["url"]
    assert p[-1]["method"] == "explore"          # honest fallback always present


def test_skill_outranks_goto(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed(tmp_path, skills={"upstox holdings open": {"app": "upstox", "wins": 5}})
    from trading.brain.vision import fast_nav
    p = fast_nav.plan("upstox", "holdings")
    assert p[0]["method"] == "skill"


def test_two_strikes_demotes_below_explore_ranking(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed(tmp_path)
    from trading.brain.vision import fast_nav
    url = "https://pro.upstox.com/holdings"
    for _ in range(2):
        fast_nav.record("upstox", "holdings", "goto", url, ok=False, latency_ms=900)
    p = fast_nav.plan("upstox", "holdings")
    top_goto = next(c for c in p if c["method"] == "goto" and c["url"] == url)
    assert top_goto.get("demoted") is True and top_goto["score"] < 0
    # a later success clears the strike counter
    fast_nav.record("upstox", "holdings", "goto", url, ok=True, latency_ms=300)
    stats = tstate.load_json("fast_nav_stats.json", {})
    assert stats["upstox"]["holdings"][f"goto:{url}"]["consecutive_fails"] == 0


def test_unknown_target_only_explores(monkeypatch, tmp_path):
    from trading import state as tstate
    monkeypatch.setattr(tstate, "STATE_DIR", tmp_path)
    _seed(tmp_path)
    from trading.brain.vision import fast_nav
    p = fast_nav.plan("upstox", "zebra unicorns")
    assert [c["method"] for c in p] == ["explore"]
