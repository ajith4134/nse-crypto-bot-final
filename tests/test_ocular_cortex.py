"""Tests for the Ocular Cortex (trading/brain/vision/ocular_cortex) — offline, no browser.

Covers: PerceptualFrame modality fusion + fingerprint, LayoutMemory consolidation
(iconic→working→habit) + novelty detection, golden-path coordinate recall, working-memory
cross-frame grounding, free-vision describe() degradation, and decision-frame linkage.
STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state
from trading.brain.vision import ocular_cortex as oc


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


def _controls(labels):
    return [{"label": l, "tag": "button", "x": i * 10, "y": i * 5, "w": 40, "h": 20}
            for i, l in enumerate(labels)]


class TestPerceptualFrame(unittest.TestCase):
    def test_modalities_and_fingerprint(self):
        f = oc.PerceptualFrame("binance", "symbol", dom_controls=_controls(["Buy", "Sell", "Depth"]),
                               ocr_numbers={"price": 62000}, network={"orderbook": {"bids": []}},
                               api_ref={"last": 62010}, screenshot=b"png")
        self.assertEqual(set(f.modalities()), {"pixels", "dom", "ocr", "network", "api"})
        self.assertTrue(f.fingerprint)
        self.assertEqual(f.data_values()["price"], 62000)
        self.assertEqual(f.data_values()["last"], 62010)

    def test_fingerprint_stable_on_value_change_but_shifts_on_layout(self):
        a = oc.PerceptualFrame("x", "symbol", dom_controls=_controls(["Buy", "Sell"]))
        b = oc.PerceptualFrame("x", "symbol", dom_controls=_controls(["Buy", "Sell"]))
        c = oc.PerceptualFrame("x", "symbol", dom_controls=_controls(["Buy", "Sell", "Options"]))
        self.assertEqual(a.fingerprint, b.fingerprint)
        self.assertNotEqual(a.fingerprint, c.fingerprint)


class TestLayoutMemory(_IsolatedState):
    def test_consolidation_progression(self):
        mem = oc.LayoutMemory()
        labels = ["Spot", "Futures", "Depth", "Chart"]
        states = []
        for _ in range(6):
            f = oc.PerceptualFrame("binance", "symbol", dom_controls=_controls(labels))
            states.append(mem.observe(f)["consolidation"])
        self.assertEqual(states[0], "iconic")
        self.assertEqual(states[1], "working")
        self.assertEqual(states[-1], "consolidated")

    def test_novelty_on_layout_change(self):
        mem = oc.LayoutMemory()
        base = ["Spot", "Futures", "Depth", "Chart", "Filters"]
        v1 = mem.observe(oc.PerceptualFrame("b", "seg", dom_controls=_controls(base)))
        self.assertTrue(v1["novel"])                       # first sight is novel
        v2 = mem.observe(oc.PerceptualFrame("b", "seg", dom_controls=_controls(base)))
        self.assertFalse(v2["novel"])                      # same layout → known
        changed = ["Totally", "Different", "Redesigned", "Page", "Layout"]
        v3 = mem.observe(oc.PerceptualFrame("b", "seg", dom_controls=_controls(changed)))
        self.assertTrue(v3["novel"])                       # redesign → novelty flag

    def test_golden_path_recall_and_locate(self):
        mem = oc.LayoutMemory()
        f = oc.PerceptualFrame("binance", "symbol",
                               dom_controls=[{"label": "Order Book", "tag": "button",
                                              "x": 900, "y": 200, "w": 80, "h": 30}],
                               network={"orderbook": {"bids": []}, "candles": [[1]]})
        mem.observe(f)
        rec = mem.recall("binance", "symbol")
        self.assertIsNotNone(rec)
        self.assertIn("orderbook", rec["kinds"])
        xy = mem.locate("binance", "symbol", "order book")
        self.assertEqual((xy["x"], xy["y"]), (900, 200))
        # fuzzy substring locate
        self.assertIsNotNone(mem.locate("binance", "symbol", "order"))

    def test_is_novel_is_readonly(self):
        mem = oc.LayoutMemory()
        f = oc.PerceptualFrame("b", "seg", dom_controls=_controls(["A", "B", "C"]))
        self.assertTrue(mem.is_novel(f))                # unseen → novel
        self.assertTrue(mem.is_novel(f))                # calling again must NOT record it…
        self.assertIsNone(mem.recall("b", "seg"))       # …memory stays empty (no mutation)
        mem.observe(f)                                  # only observe() records
        self.assertFalse(mem.is_novel(f))               # now known

    def test_persistence_roundtrip(self):
        mem = oc.LayoutMemory()
        mem.observe(oc.PerceptualFrame("b", "screener", dom_controls=_controls(["Volume", "Gainers"])))
        mem.save()
        mem2 = oc.LayoutMemory()
        self.assertIsNotNone(mem2.recall("b", "screener"))


class TestOcularCortex(_IsolatedState):
    def _cortex(self):
        rec = mock.MagicMock()
        rec.latest.return_value = None                     # no network cache in these tests
        return oc.OcularCortex(recorder=rec)

    def test_perceive_stores_frame_and_working_memory(self):
        cx = self._cortex()
        f = cx.perceive("binance", "symbol", dom_controls=_controls(["Buy", "Sell"]),
                        ocr_numbers={"px": 100})
        self.assertEqual(f.broker, "binance")
        self.assertEqual(len(cx.working("binance", "symbol")), 1)
        self.assertEqual(cx.stats["frames"], 1)

    def test_grounding_detects_appeared_control(self):
        cx = self._cortex()
        cx.perceive("b", "symbol", dom_controls=_controls(["Buy", "Sell"]))
        cx.perceive("b", "symbol", dom_controls=_controls(["Buy", "Sell", "Depth"]))
        g = cx.ground("b", "symbol")
        self.assertIn("depth", g["appeared"])

    def test_describe_degrades_without_vision(self):
        cx = self._cortex()
        f = cx.perceive("b", "symbol", dom_controls=_controls(["Buy"]), screenshot=b"pngdata")
        with mock.patch("core.llm.vision_available", return_value=False):
            self.assertEqual(cx.describe(f), "")

    def test_describe_uses_free_vision(self):
        cx = self._cortex()
        f = cx.perceive("b", "symbol", dom_controls=_controls(["Buy"]), screenshot=b"pngdata")
        with mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat", return_value="I see a BTC order book at 62000"):
            out = cx.describe(f)
        self.assertIn("order book", out)
        self.assertEqual(f.vision_read, out)
        self.assertEqual(cx.stats["vision_reads"], 1)

    def test_decision_frame_linkage(self):
        cx = self._cortex()
        f = cx.perceive("b", "symbol", dom_controls=_controls(["Buy"]),
                        ocr_numbers={"entry": 100}, screenshot=b"pngbytes")
        path = cx.link_to_decision(f, "episode-42")
        self.assertTrue(path.endswith(".png"))
        rec = cx.recall_decision_frame("episode-42")
        self.assertEqual(rec["data_values"]["entry"], 100)
        self.assertTrue(Path(path).exists())

    def test_status_shape(self):
        cx = self._cortex()
        cx.perceive("b", "screener", dom_controls=_controls(["Gainers"]))
        st = cx.status()
        self.assertIn("layouts", st)
        self.assertIn("stats", st)


if __name__ == "__main__":
    unittest.main()
