"""Tests for trading/direction/pullback — D3 pullback entries."""
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import pullback
        self.pb = pullback

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestPullback(_Iso):
    def _arm_long(self, atr=2.0, ref=100.0):
        ok = self.pb.arm(symbol="ETH/USDT:USDT", segment="futures", direction="LONG",
                         source="explore_open_all", ref_price=ref, atr=atr)
        self.assertTrue(ok)

    def test_waits_then_triggers_on_retrace(self):
        self._arm_long()                                   # dist = 2.0 * 0.5 = 1.0
        self.assertEqual(self.pb.sweep(lambda s: 99.5), [])       # not deep enough
        hits = self.pb.sweep(lambda s: 99.0)                      # ref - dist
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["direction"], "LONG")
        self.assertEqual(self.pb.status()["n_armed"], 0)          # consumed
        self.assertEqual(self.pb.status()["stats"]["triggered"], 1)

    def test_short_triggers_on_pop_up(self):
        self.pb.arm(symbol="X/USDT:USDT", segment="futures", direction="SHORT",
                    source="s", ref_price=100.0, atr=2.0)
        self.assertEqual(self.pb.sweep(lambda s: 100.4), [])
        self.assertEqual(len(self.pb.sweep(lambda s: 101.0)), 1)

    def test_runaway_drops_honestly(self):
        self._arm_long()                                   # runaway at ref + 1.5*1.0
        self.assertEqual(self.pb.sweep(lambda s: 101.6), [])
        s = self.pb.status()
        self.assertEqual(s["n_armed"], 0)
        self.assertEqual(s["stats"]["runaway"], 1)

    def test_expiry(self):
        self._arm_long()
        def _age(d):
            d["armed"]["futures|ETH/USDT:USDT"]["armed_ts"] = time.time() - 46 * 60
            return d
        state.mutate_json("direction_pullback.json", _age, default={})
        self.assertEqual(self.pb.sweep(lambda s: 100.0), [])
        self.assertEqual(self.pb.status()["stats"]["expired"], 1)

    def test_pct_fallback_without_atr(self):
        self.pb.arm(symbol="Y/USDT", segment="spot", direction="LONG",
                    source="s", ref_price=1000.0, atr=None)       # 0.15% → dist 1.5
        self.assertEqual(self.pb.sweep(lambda s: 999.0), [])
        self.assertEqual(len(self.pb.sweep(lambda s: 998.5)), 1)

    def test_opposite_rearm_replaces_and_kill_switch(self):
        import os
        self._arm_long()
        self.pb.arm(symbol="ETH/USDT:USDT", segment="futures", direction="SHORT",
                    source="s2", ref_price=100.0, atr=2.0)
        armed = self.pb.status()["armed"]
        self.assertEqual(len(armed), 1)
        self.assertEqual(armed[0]["direction"], "SHORT")          # newer verdict wins
        os.environ["PULLBACK_ENTRY"] = "0"
        try:
            self.assertEqual(self.pb.sweep(lambda s: 200.0), [])  # disabled → no-op
        finally:
            os.environ.pop("PULLBACK_ENTRY")

    def test_no_quote_stays_armed(self):
        self._arm_long()
        self.assertEqual(self.pb.sweep(lambda s: None), [])
        self.assertEqual(self.pb.status()["n_armed"], 1)

    def test_atr_from_df(self):
        import pandas as pd
        df = pd.DataFrame({"open": [100.0] * 20, "high": [101.0] * 20,
                           "low": [99.0] * 20, "close": [100.0] * 20})
        self.assertAlmostEqual(self.pb.atr_from_df(df), 2.0)
        self.assertIsNone(self.pb.atr_from_df(df.head(5)))


if __name__ == "__main__":
    unittest.main()
