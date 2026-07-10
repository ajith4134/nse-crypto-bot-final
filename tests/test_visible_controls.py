"""Regression tests for the 2026-07-10 phantom-click fixes.

The Upstox hand looped clicking 'Okay, I Understand' at the same coords forever:
(1) DOM extraction collected invisible/occluded elements, so locate() aimed at
    controls a human could not press;
(2) dismiss_modals counted any successful mouse click as a dismissal, so a
    decorative match starved the ×-fallback and burned every cycle.
STATE_DIR-isolated, no browser.
"""
from __future__ import annotations

import tempfile
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


def _eyes():
    from trading.brain.vision.free_eyes import FreeEyes
    eyes = FreeEyes.__new__(FreeEyes)
    eyes.page = mock.Mock()
    eyes.broker = "upstox"
    eyes._recorder = None
    return eyes


class TestCoveredControls(_IsolatedState):
    def test_locate_skips_covered_dom_controls(self):
        """A control under an overlay must never win a locate (phantom-click source)."""
        from trading.brain.vision import free_eyes as fe
        eyes = _eyes()
        controls = [{"label": "Okay, I Understand", "x": 1200, "y": 20, "w": 108,
                     "h": 14, "covered": True}]
        with mock.patch("trading.brain.vision.ocular_cortex._extract_from_page",
                        return_value=(controls, b"png")), \
             mock.patch.object(fe, "_ocr_read", return_value=[]):
            self.assertIsNone(eyes.locate("Okay, I Understand"))

    def test_locate_still_finds_uncovered_controls(self):
        eyes = _eyes()
        controls = [{"label": "Okay, I Understand", "x": 700, "y": 500, "w": 108,
                     "h": 30, "covered": False}]
        with mock.patch("trading.brain.vision.ocular_cortex._extract_from_page",
                        return_value=(controls, b"png")):
            self.assertEqual(eyes.locate("Okay, I Understand"), (754, 515))

    def test_extract_uses_single_evaluate_and_never_raises(self):
        from trading.brain.vision.ocular_cortex import _extract_from_page
        pg = mock.Mock()
        pg.evaluate.return_value = [{"label": "Buy", "tag": "button", "x": 1, "y": 2,
                                     "w": 3, "h": 4, "covered": False}]
        pg.screenshot.return_value = b"png"
        controls, shot = _extract_from_page(pg)
        self.assertEqual(len(controls), 1)
        self.assertEqual(pg.evaluate.call_count, 1)      # ONE round-trip, not per-element
        self.assertEqual(shot, b"png")
        pg.evaluate.side_effect = RuntimeError("page gone")
        controls, _ = _extract_from_page(pg, want_shot=False)
        self.assertEqual(controls, [])


class TestDismissModalsProgress(_IsolatedState):
    def _ui(self):
        from trading.brain.vision.human_ui import HumanUI
        ui = HumanUI.__new__(HumanUI)
        ui.name = "upstox"
        ui.trail = []
        ui.eyes = None
        ui.page = mock.Mock()
        return ui

    def test_no_effect_label_clicked_once_then_blacklisted(self):
        """Same label still at the same spot after the click = not a dismissal: it must be
        clicked at most once per pass, never counted as cleared, never looped."""
        ui = self._ui()
        clicks = []
        with mock.patch.object(type(ui), "locate",
                               side_effect=lambda t, **k:
                               (1254, 27) if "Okay, I Understand" in t else None), \
             mock.patch.object(type(ui), "click",
                               side_effect=lambda t, **k:
                               (clicks.append(t) or True) if "Okay" in t else False):
            cleared = ui.dismiss_modals()
        self.assertEqual(cleared, 0)
        self.assertEqual(len([c for c in clicks if c == "Okay, I Understand"]), 1)

    def test_real_dismissal_counts_when_label_disappears(self):
        ui = self._ui()
        seen = {"n": 0}

        def _locate(t, **k):
            if "Okay, I Understand" in t:
                seen["n"] += 1
                return (700, 500) if seen["n"] == 1 else None   # gone after the click
            return None

        with mock.patch.object(type(ui), "locate", side_effect=_locate), \
             mock.patch.object(type(ui), "click",
                               side_effect=lambda t, **k: "Okay" in t):
            cleared = ui.dismiss_modals()
        self.assertEqual(cleared, 1)


if __name__ == "__main__":
    unittest.main()
