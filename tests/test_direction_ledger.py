"""Tests for the Direction Decision Ledger (owner ask: what data drove each direction)."""
import tempfile
import unittest
from unittest import mock

from trading import state
from trading.brain import direction_ledger as dl


class DirectionLedgerTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(tempfile.mkdtemp()))
        p.start(); self.addCleanup(p.stop)

    def test_record_and_read(self):
        dl.record({"direction": "long", "p_up": 0.61, "confidence": 0.08,
                   "abstained": False, "n_sources": 2,
                   "weights": {"venue_leadlag": {"w": 0.05, "rate": 0.55, "n": 120,
                                                 "invert": False},
                               "funnel_mtf_vote": {"w": 0.0, "rate": 0.47, "n": 300}}},
                  symbol="BTC/USDT:USDT", market="CRYPTO", regime="trend")
        rec = dl.recent(10)
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec[0]["symbol"], "BTC/USDT:USDT")
        self.assertEqual(rec[0]["direction"], "long")
        self.assertEqual(rec[0]["drivers"][0]["source"], "venue_leadlag")  # sorted by weight
        self.assertEqual(dl.by_symbol("BTC/USDT:USDT")["p_up"], 0.61)

    def test_summary_coverage_and_abstain(self):
        dl.record({"direction": "long", "abstained": False,
                   "weights": {"a": {"w": 0.04}}}, symbol="X", market="CRYPTO")
        dl.record({"direction": "neutral", "abstained": True,
                   "weights": {"b": {"w": 0.0}}}, symbol="Y", market="CRYPTO")
        s = dl.summary()
        self.assertEqual(s["decisions"], 2)
        self.assertEqual(s["abstain_rate"], 0.5)
        self.assertEqual(s["with_driver_rate"], 0.5)      # one had a weighted source

    def test_decide_logs_rationale(self):
        # exercising learned_direction.decide should populate the ledger via _log
        from trading.direction import learned_direction as ld
        ld.decide([("funnel_mtf_vote", 0.6)], market="CRYPTO", regime="trend",
                  symbol="ETH/USDT:USDT")
        rec = dl.recent(5)
        self.assertTrue(any(r["symbol"] == "ETH/USDT:USDT" for r in rec))


if __name__ == "__main__":
    unittest.main()
