"""Tests for invent-beyond #1 — local grounded eyes (OmniParser icon grounding)."""
from __future__ import annotations

import io
import os
import unittest
from unittest import mock


def _png(w=200, h=120):
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (20, 20, 24)).save(buf, format="PNG")
    return buf.getvalue()


def _eyes(boxes):
    """GroundedEyes with the YOLO stage stubbed to fixed boxes (label logic stays real)."""
    from trading.brain.vision.grounded_eyes import GroundedEyes
    ge = GroundedEyes(model=None)
    ge._detect = lambda png: [dict(b) for b in boxes]
    return ge


_STAR = {"x1": 10, "y1": 10, "x2": 40, "y2": 40, "cx": 25, "cy": 25,
         "conf": 0.9, "kind": "icon", "label": ""}
_BTN = {"x1": 100, "y1": 10, "x2": 180, "y2": 40, "cx": 140, "cy": 25,
        "conf": 0.8, "kind": "icon", "label": ""}


class TestGrounding(unittest.TestCase):
    def test_ocr_inside_box_names_the_element(self):
        ge = _eyes([_STAR, _BTN])
        ocr = [{"cx": 140, "cy": 25, "text": "Add to Watchlist"}]
        els = ge.ground(_png(), ocr)
        self.assertEqual(els[1]["label"], "Add to Watchlist")
        self.assertEqual(els[0]["label"], "")          # icon with no text stays unlabeled

    def test_ocr_caption_below_names_the_icon(self):
        ge = _eyes([_STAR])
        ocr = [{"cx": 25, "cy": 55, "text": "Favorites"}]   # just below the 40px box edge
        els = ge.ground(_png(), ocr)
        self.assertEqual(els[0]["label"], "Favorites")

    def test_locate_matches_labeled_element_center(self):
        ge = _eyes([_STAR, _BTN])
        ocr = [{"cx": 140, "cy": 25, "text": "Add to Watchlist"}]
        self.assertEqual(ge.locate("watchlist", _png(), ocr=ocr), (140, 25))
        self.assertIsNone(ge.locate("logout", _png(), ocr=ocr))  # honest miss

    def test_som_pick_clicks_the_chosen_real_element(self):
        ge = _eyes([_STAR, _BTN])
        with mock.patch("core.llm.vision_chat", return_value="1"):
            xy = ge.locate_som("the buy-side button", _png())
        self.assertEqual(xy, (140, 25))                # element #1's center — never a guess
        self.assertEqual(ge.stats["som_hits"], 1)

    def test_som_absent_answer_is_a_miss_not_a_click(self):
        ge = _eyes([_STAR])
        with mock.patch("core.llm.vision_chat", return_value="-1"):
            self.assertIsNone(ge.locate_som("nonexistent", _png()))

    def test_som_image_is_valid_png(self):
        from trading.brain.vision.grounded_eyes import GroundedEyes
        marked = GroundedEyes._som_image(_png(), [_STAR, _BTN])
        self.assertTrue(marked.startswith(b"\x89PNG"))


class TestAvailability(unittest.TestCase):
    def test_kill_switch_returns_none(self):
        import trading.brain.vision.grounded_eyes as g
        with mock.patch.dict(os.environ, {"GROUNDED_EYES": "0"}):
            self.assertIsNone(g.get_grounded())

    def test_status_never_loads_the_model(self):
        import trading.brain.vision.grounded_eyes as g
        st = g.status()
        self.assertIn("enabled", st)
        self.assertIn("weights_cached", st)


if __name__ == "__main__":
    unittest.main()
