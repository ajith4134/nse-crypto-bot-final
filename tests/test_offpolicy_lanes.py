"""Tests for invent-beyond #6 — off-policy (counterfactual) lane-weight learning."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trading.state as tstate


class TestCounterfactualWeights(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)
        import trading.broker_sense.broker_features as bf
        bf._PERF = None                              # fresh singleton per test

    def tearDown(self):
        import trading.broker_sense.broker_features as bf
        bf._PERF = None
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()

    def test_cf_bucket_never_mixes_into_onpolicy_counts(self):
        from trading.broker_sense.broker_features import get_perf
        p = get_perf()
        p.record_counterfactual("binance", "top-movers", would_win=True)
        ent = p.perf["binance|top-movers"]
        self.assertEqual(ent["n"], 0)                # on-policy count untouched
        self.assertEqual(ent["cf"], {"n": 1, "wins": 1})

    def test_cf_alone_can_move_weight_after_three_observations(self):
        from trading.broker_sense.broker_features import get_perf
        p = get_perf()
        self.assertEqual(p.weight("binance", "losers"), 1.0)     # no evidence → neutral
        for w in (True, True, True):
            p.record_counterfactual("binance", "losers", would_win=w)
        self.assertGreater(p.weight("binance", "losers"), 1.0)   # pure-cf winner lane
        for _ in range(4):
            p.record_counterfactual("binance", "noise", would_win=False)
        self.assertLess(p.weight("binance", "noise"), 1.0)       # pure-cf loser lane

    def test_blend_pulls_onpolicy_toward_cf(self):
        from trading.broker_sense.broker_features import get_perf
        p = get_perf()
        for _ in range(6):
            p.record("binance", "mixed", win=True, regime="neutral")
        w_before = p.weight("binance", "mixed", regime="neutral")
        for _ in range(6):
            p.record_counterfactual("binance", "mixed", would_win=False)
        w_after = p.weight("binance", "mixed", regime="neutral")
        self.assertLess(w_after, w_before)           # bad skips temper the hot streak

    def test_skip_resolution_credits_lane(self):
        import time as _t

        from trading import evidence
        from trading.broker_sense.broker_features import get_perf
        d = {"skips": [{"symbol": "X/USDT:USDT", "market": "crypto", "segment": "spot",
                        "direction": "long", "price_at_skip": 100.0, "lane": "gainers",
                        "ts": _t.time() - 26 * 3600, "resolved": False,
                        "snaps": [[int(_t.time() - h * 3600), 100.0 + (26 - h)]
                                  for h in range(25, -1, -1)],
                        "outcomes": {}, "verdict": "pending"}],
             "baseline": [], "failures": []}
        evidence._feed_snapshots(d, {"X/USDT:USDT": {"book": {"mid": 126.0}}}, _t.time())
        self.assertTrue(d["skips"][0]["resolved"])
        self.assertIn("bad-skip", d["skips"][0]["verdict"])      # +26% missed winner
        ent = get_perf().perf.get("binance|gainers")
        self.assertIsNotNone(ent)
        self.assertEqual(ent["cf"]["wins"], 1)                   # lane got its credit


if __name__ == "__main__":
    unittest.main()
