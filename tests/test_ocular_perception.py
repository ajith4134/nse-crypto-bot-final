"""Tests for OcularPerception (trading/broker_sense/ocular_perception) — funnel eyes, offline.

Covers: per-candidate enrichment fusing the interception network cache + book into a frame,
order-book summary + imbalance, learning-column discovery from captured JSON, the bounded
free-vision app-shot sink, and visual-outcome linkage of an entry. STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state
from trading.brain.vision.ocular_cortex import OcularCortex
from trading.broker_sense import ocular_perception as op
from trading.broker_sense.learning_columns import get_registry


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        import trading.broker_sense.learning_columns as lc
        lc._REG = None                                  # reset the module singleton

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()
        import trading.broker_sense.learning_columns as lc
        lc._REG = None


def _perception(network=None):
    rec = mock.MagicMock()
    kinds = network or {}

    def _latest(broker, kind, **kw):
        return kinds.get(kind)
    rec.latest.side_effect = _latest
    cortex = OcularCortex(recorder=rec)
    return op.OcularPerception(cortex=cortex, market="crypto")


class TestSummarizeBook(unittest.TestCase):
    def test_top_of_book_and_imbalance(self):
        ob = {"bids": [[100, 3], [99, 2]], "asks": [[101, 1], [102, 1]]}
        s = op._summarize_book(ob)
        self.assertEqual(s["bid"], 100.0)
        self.assertEqual(s["ask"], 101.0)
        self.assertEqual(s["depth_bid"], 5.0)
        self.assertEqual(s["depth_ask"], 2.0)
        self.assertAlmostEqual(s["imbalance"], (5 - 2) / 7, places=3)

    def test_empty_book(self):
        self.assertEqual(op._summarize_book(None), {})
        self.assertEqual(op._summarize_book({}), {})


class TestEnrich(_IsolatedState):
    def test_enrich_fuses_network_and_makes_columns(self):
        perc = _perception(network={
            "orderbook": {"bids": [[62000, 5]], "asks": [[62010, 3]]},
            "funding": {"lastFundingRate": 0.0001, "openInterest": 12345},
        })
        out = perc.enrich("BTC/USDT", lane="binance", book={"bid": 62000, "ask": 62010})
        self.assertEqual(out["broker"], "binance")
        self.assertIn("network", out["modalities"])
        self.assertIn("orderbook", out["network_kinds"])
        self.assertEqual(out["order_book"]["bid"], 62000.0)
        # numbers from the captured funding JSON became learning columns for the symbol
        snap = get_registry().snapshot("BTC/USDT")
        self.assertTrue(any("funding" in k or "openinterest" in k.lower() or "interest" in k
                            for k in snap))

    def test_enrich_past_deadline_returns_empty(self):
        perc = _perception()
        out = perc.enrich("BTC/USDT", deadline=0.0)     # monotonic deadline already passed
        self.assertEqual(out, {})

    def test_enrich_without_network_still_ok(self):
        perc = _perception(network={})
        out = perc.enrich("ETH/USDT", lane="binance", book={"bid": 3000, "ask": 3001})
        self.assertEqual(out["broker"], "binance")
        self.assertEqual(out["order_book"], {})


class TestVisionSink(_IsolatedState):
    def test_on_app_shot_reads_and_makes_columns(self):
        perc = _perception()
        with mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat",
                        return_value="Uptrend. RSI 62. Entry 62000, stop 61500, target 63000."):
            perc.on_app_shot("BTC/USDT", "15m", b"PNGBYTES")
        self.assertEqual(perc.stats["vision_reads"], 1)
        snap = get_registry().snapshot("BTC/USDT")
        self.assertTrue(snap)                            # numbers from the VLM read → columns

    def test_vision_quota_bounds_reads(self):
        perc = _perception()
        with mock.patch.dict("os.environ", {"OCULAR_VISION_QUOTA": "2"}), \
             mock.patch("core.llm.vision_available", return_value=True), \
             mock.patch("core.llm.vision_chat", return_value="RSI 50"):
            for i in range(5):
                perc.on_app_shot(f"S{i}/USDT", "15m", b"PNG")
        self.assertEqual(perc.stats["vision_reads"], 2)

    def test_vision_flag_off_skips(self):
        perc = _perception()
        with mock.patch.dict("os.environ", {"OCULAR_VISION": "0"}), \
             mock.patch("core.llm.vision_chat") as vc:
            perc.on_app_shot("BTC/USDT", "15m", b"PNG")
            vc.assert_not_called()


class TestLinkage(_IsolatedState):
    def test_link_entry_persists_frame(self):
        perc = _perception(network={"orderbook": {"bids": [[1, 1]], "asks": [[2, 1]]}})
        perc.enrich("BTC/USDT", lane="binance", book={"bid": 1, "ask": 2})
        key_path = perc.link_entry("BTC/USDT", "crypto", ts=1234567890)
        rec = perc.cortex.recall_decision_frame("crypto:BTC/USDT:1234567890")
        self.assertIsNotNone(rec)

    def test_link_entry_no_frame_returns_empty(self):
        perc = _perception()
        self.assertEqual(perc.link_entry("NEVER/SEEN", "crypto"), "")


if __name__ == "__main__":
    unittest.main()
