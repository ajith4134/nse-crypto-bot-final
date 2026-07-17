"""Tests for trading/direction/onchain_source.py (E5 — on-chain lane as a measured lens)."""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _snap(self, composite, ts=None, available=True):
        from trading import state
        state.save_json("onchain_snapshot.json",
                        {"available": available, "composite": composite,
                         "ts": ts or time.time()})


class TestReadings(_Base):
    def test_positive_composite_leans_long_and_records(self):
        from trading.direction import onchain_source as oc
        self._snap(0.6)
        with mock.patch("trading.direction.truth_ledger.record") as rec:
            reads = oc.readings("AKE/USDT:USDT", regime="chop")
        self.assertEqual(reads, [("onchain_flow", 0.59)])       # 0.5 + 0.15*0.6
        self.assertEqual(rec.call_args.kwargs["source"], "onchain_flow")
        self.assertEqual(rec.call_args.kwargs["symbol"], "AKEUSDT")

    def test_small_composite_abstains(self):
        from trading.direction import onchain_source as oc
        self._snap(0.05)
        self.assertEqual(oc.readings("AKEUSDT"), [])

    def test_stale_snapshot_abstains(self):
        from trading.direction import onchain_source as oc
        self._snap(0.6, ts=time.time() - 7200)
        self.assertEqual(oc.readings("AKEUSDT"), [])

    def test_unavailable_abstains(self):
        from trading.direction import onchain_source as oc
        self._snap(0.6, available=False)
        self.assertEqual(oc.readings("AKEUSDT"), [])

    def test_disabled_flag(self):
        from trading.direction import onchain_source as oc
        os.environ["ONCHAIN_SOURCE"] = "0"
        try:
            self._snap(0.6)
            self.assertEqual(oc.readings("AKEUSDT"), [])
        finally:
            os.environ.pop("ONCHAIN_SOURCE", None)


class TestRefresh(_Base):
    def test_refresh_caches_snapshot(self):
        from trading import state
        from trading.direction import onchain_source as oc
        fake = {"available": True, "composite": 0.3, "sources_live": {"fear_greed": True}}
        with mock.patch("trading.altdata.onchain.OnChainAltData") as cls:
            cls.return_value.snapshot.return_value = dict(fake)
            out = oc.refresh(force=True)
        self.assertTrue(out["available"])
        snap = state.load_json("onchain_snapshot.json", {})
        self.assertEqual(snap["composite"], 0.3)
        self.assertIn("ts", snap)

    def test_refresh_throttled(self):
        from trading.direction import onchain_source as oc
        with mock.patch("trading.altdata.onchain.OnChainAltData") as cls:
            cls.return_value.snapshot.return_value = {"available": True, "composite": 0}
            oc.refresh(force=True)
            self.assertIsNone(oc.refresh())                     # within ONCHAIN_EVERY_S


if __name__ == "__main__":
    unittest.main()
