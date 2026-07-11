"""Tests for trading/broker_sense/nav_brain.py — Planner-Actor-Validator navigation loop.

Covers: the segment gate (never plans an OFF segment), heuristic planning over allowed segments,
stuck-detection, the validator, a completing navigation, and — critically — that a STUCK browser
triggers a replan and TERMINATES (no infinite loop). LLM is forced off (heuristic path); boss's
active_segments is mocked; the browser is a fake with injectable perceive/act.
"""
from __future__ import annotations

import unittest
from unittest import mock

from trading.broker_sense.nav_brain import NavBrain


class _Fake:
    """A fake browser: perceive() returns the current page; act() advances to the next page."""
    def __init__(self, pages):
        self.pages = pages
        self.i = 0
        self.acted = []

    def perceive(self):
        return self.pages[min(self.i, len(self.pages) - 1)]

    def advance_act(self, action):
        self.acted.append(action)
        self.i += 1

    def stuck_act(self, action):        # never changes the page → looping
        self.acted.append(action)


def _nav(fake, act, segs=("futures", "spot"), **kw):
    nb = NavBrain(fake.perceive, act, market="crypto", **kw)
    nb.allowed_segments = lambda: set(segs)          # pin the gate for determinism
    return nb


class TestGate(unittest.TestCase):
    def test_off_segment_actions_dropped(self):
        fake = _Fake([{"url": "a", "text": "x"}])
        nb = _nav(fake, fake.advance_act, segs=("futures", "spot"))   # options OFF
        gated = nb._gate([{"type": "click", "target": "Options tab", "segment": "options"},
                          {"type": "click", "target": "Futures tab", "segment": "futures"}])
        self.assertEqual([a["segment"] for a in gated], ["futures"])   # options dropped

    def test_heuristic_plan_only_allowed(self):
        fake = _Fake([{"url": "a", "text": "x"}])
        nb = _nav(fake, fake.advance_act, segs=("futures",))
        with mock.patch("core.llm.chat", side_effect=RuntimeError("no llm")):
            plan = nb.plan("screen entries", fake.perceive())
        self.assertTrue(plan)
        for a in plan:
            self.assertNotIn("options", f"{a.get('target')} {a.get('segment')}".lower())


class TestStuckAndValidate(unittest.TestCase):
    def test_is_stuck(self):
        nb = _nav(_Fake([{}]), lambda a: None)
        self.assertTrue(nb.is_stuck(["s", "s", "s"]))
        self.assertFalse(nb.is_stuck(["s", "t", "s"]))

    def test_validate_detects_no_change(self):
        nb = _nav(_Fake([{}]), lambda a: None)
        p = {"url": "u", "text": "futures market"}
        self.assertFalse(nb.validate({"target": "futures"}, p, p))         # identical → not valid
        self.assertTrue(nb.validate({"target": "futures"},
                                    {"url": "u", "text": "spot"}, p))      # changed + target present


class TestNavigate(unittest.TestCase):
    def test_completes_when_pages_progress(self):
        pages = [{"url": "home", "text": "home"},
                 {"url": "fut", "text": "futures market book"},
                 {"url": "spot", "text": "spot market book"}]
        fake = _Fake(pages)
        nb = _nav(fake, fake.advance_act, segs=("futures", "spot"))
        with mock.patch("core.llm.chat", side_effect=RuntimeError("no llm")):
            rep = nb.navigate("screen the enabled segments")
        self.assertTrue(rep["steps"] >= 1)
        self.assertEqual(rep["allowed_segments"], ["futures", "spot"])

    def test_stuck_browser_replans_and_terminates(self):
        # a browser that NEVER changes page must not infinite-loop: detect stuck → replan → stop
        fake = _Fake([{"url": "same", "text": "same page forever"}])
        nb = _nav(fake, fake.stuck_act, segs=("futures",), max_steps=20, max_replans=2, stuck_k=3)
        with mock.patch("core.llm.chat", side_effect=RuntimeError("no llm")):
            rep = nb.navigate("do something")
        self.assertLessEqual(rep["steps"], 20)          # bounded — terminated
        self.assertGreaterEqual(rep["replans"], 1)      # noticed it was stuck
        self.assertFalse(rep["completed"])              # honest: didn't pretend success

    def test_never_navigates_off_segment_end_to_end(self):
        fake = _Fake([{"url": "home", "text": "home"}, {"url": "fut", "text": "futures"}])
        nb = _nav(fake, fake.advance_act, segs=("futures",))     # options OFF
        with mock.patch("core.llm.chat", side_effect=RuntimeError("no llm")):
            nb.navigate("trade")
        for a in fake.acted:
            self.assertNotIn("options", f"{a.get('target')} {a.get('segment')}".lower())


if __name__ == "__main__":
    unittest.main()
