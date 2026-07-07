"""Tests for the hand skill-cache (invent-beyond #2) + free-eyes glance cache (#5).

Pure-logic: STATE_DIR-isolated, no browser — HumanUI is constructed with a stub page
and the skill store is exercised through _save_skill/_replay_skill/skill_feedback.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import trading.state as tstate


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()


def _ui(name="binance"):
    """A HumanUI with everything browser-y stubbed out."""
    from trading.brain.vision.human_ui import HumanUI
    ui = HumanUI.__new__(HumanUI)
    ui.name = name
    ui.trail = []
    ui.eyes = None
    return ui


class TestSkillCache(_IsolatedState):
    def test_save_parameterizes_and_replay_instantiates(self):
        ui = _ui()
        ui._save_skill("add-fav", [{"action": "click", "target": "pin BELUSDT row"},
                                   {"action": "type", "target": "search box",
                                    "text": "BELUSDT"}], {"SYM": "BELUSDT"})
        ent = tstate.load_json("ui_skills.json", {})["binance:add-fav"]
        self.assertEqual(ent["steps"][0]["target"], "pin {SYM} row")   # templated
        self.assertEqual(ent["steps"][1]["text"], "{SYM}")
        played = []
        ui.click = lambda t: played.append(("click", t)) or True
        ui.click_and_type = lambda t, x: played.append(("type", t, x)) or True
        self.assertTrue(ui._replay_skill("add-fav", {"SYM": "XRPUSDT"}))
        self.assertEqual(played[0], ("click", "pin XRPUSDT row"))      # re-instantiated
        self.assertEqual(played[1], ("type", "search box", "XRPUSDT"))

    def test_replay_miss_counts_fail_and_two_fails_evict(self):
        ui = _ui()
        ui._save_skill("add-fav", [{"action": "click", "target": "pin {SYM} row"}], {})
        ui.click = lambda t: False                       # the click misses
        self.assertFalse(ui._replay_skill("add-fav", {"SYM": "A"}))
        self.assertEqual(tstate.load_json("ui_skills.json", {})
                         ["binance:add-fav"]["fails"], 1)
        ui.skill_feedback("add-fav", False)              # second confirmed fail
        self.assertNotIn("binance:add-fav", tstate.load_json("ui_skills.json", {}))

    def test_feedback_win_resets_fails_and_bumps_track_record(self):
        ui = _ui()
        ui._save_skill("add-fav", [{"action": "click", "target": "x"}], {})
        ui.skill_feedback("add-fav", True)
        ent = tstate.load_json("ui_skills.json", {})["binance:add-fav"]
        self.assertEqual(ent["wins"], 1)
        tr = tstate.load_json("track_records.json", {})
        self.assertEqual(tr.get("ui-skill:binance:add-fav", {}).get("wins"), 1)

    def test_no_skill_entry_means_no_replay(self):
        ui = _ui()
        self.assertFalse(ui._replay_skill("never-learned", {}))


class TestGlanceCache(_IsolatedState):
    def _eyes(self):
        from trading.brain.vision.free_eyes import FreeEyes
        eyes = FreeEyes.__new__(FreeEyes)
        eyes.page = mock.Mock()
        eyes.broker = "binance"
        eyes._recorder = None
        return eyes

    def test_glance_cached_within_ttl_and_invalidated(self):
        from trading.brain.vision import free_eyes as fe
        eyes = self._eyes()
        with mock.patch("trading.brain.vision.ocular_cortex._extract_from_page",
                        return_value=([{"label": "Star", "x": 5, "y": 6, "w": 2,
                                        "h": 2}], b"")) as ex:
            g1 = eyes.glance(want_ocr=False)
            g2 = eyes.glance(want_ocr=False)             # served from cache
            self.assertIs(g1, g2)
            self.assertEqual(ex.call_count, 1)
            eyes.invalidate_glance()
            eyes.glance(want_ocr=False)                  # fresh after an action
            self.assertEqual(ex.call_count, 2)

    def test_locate_skips_ocr_on_dom_hit(self):
        from trading.brain.vision import free_eyes as fe
        eyes = self._eyes()
        with mock.patch("trading.brain.vision.ocular_cortex._extract_from_page",
                        return_value=([{"label": "Add to Favorites", "x": 10, "y": 10,
                                        "w": 4, "h": 4}], b"png")), \
             mock.patch.object(fe, "_ocr_read") as ocr:
            xy = eyes.locate("add to favorites")
            self.assertIsNotNone(xy)
            ocr.assert_not_called()                      # lazy OCR: DOM answered


if __name__ == "__main__":
    unittest.main()
