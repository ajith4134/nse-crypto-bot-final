"""Tests for the ultra-advanced multi-timeframe indicator-fusion engine (offline, no network).

Covers the indicator math on synthetic trend/range candles, the regime-gated per-TF vote, the
multi-TF confluence + higher-TF veto, the vision fuse, the meta-label gate, and the ATR triple-
barrier geometry. `fuse()`'s network fetch is monkeypatched so the whole thing runs offline.
"""
from __future__ import annotations

import math
import unittest
from unittest import mock

from trading.broker_sense import indicator_fusion as IF


def _series(trend: float, n: int = 240, start: float = 100.0, noise: float = 0.0) -> list:
    rows, p = [], start
    for i in range(n):
        p = p * (1 + trend) + noise * math.sin(i)
        rows.append([i, p * (1 - 0.001), p * (1 + 0.002), p * (1 - 0.002), p, 1000])
    return rows


class TestIndicators(unittest.TestCase):
    def test_uptrend_votes_long_trend_regime(self):
        d = IF.indicators_from_ohlcv(_series(0.004))
        self.assertTrue(d["available"])
        self.assertGreater(d["vote"], 0.5)
        self.assertEqual(d["supertrend"]["dir"], 1)
        self.assertEqual(d["sar"]["dir"], 1)
        self.assertEqual(d["regime"], "trend")
        self.assertGreater(d["adx"]["adx"], 25)

    def test_downtrend_votes_short(self):
        d = IF.indicators_from_ohlcv(_series(-0.004))
        self.assertLess(d["vote"], -0.4)
        self.assertEqual(d["supertrend"]["dir"], -1)
        self.assertEqual(d["sar"]["dir"], -1)

    def test_range_regime_low_adx(self):
        d = IF.indicators_from_ohlcv(_series(0.0, noise=0.5))
        self.assertEqual(d["regime"], "range")
        self.assertLess(d["adx"]["adx"], 25)

    def test_short_series_unavailable(self):
        self.assertFalse(IF.indicators_from_ohlcv(_series(0.004, n=20)).get("available"))
        self.assertFalse(IF.indicators_from_ohlcv([]).get("available"))

    def test_indicator_primitives(self):
        c = [float(r[4]) for r in _series(0.003)]
        self.assertGreater(IF._ema(c, 9), 0)
        self.assertGreater(IF._sma(c, 50), 0)
        o, h, l, cc = IF._ohlc(_series(0.003))
        self.assertGreater(IF._atr(h, l, cc), 0)
        adx, pdi, mdi = IF._adx(h, l, cc)
        self.assertGreater(pdi, mdi)                 # uptrend → +DI dominates


class TestBarriers(unittest.TestCase):
    def test_long_barriers_geometry(self):
        b = IF._barriers("long", 100.0, 2.0)
        self.assertLess(b["stop"], 100.0)
        self.assertGreater(b["target"], 100.0)
        self.assertAlmostEqual(b["rr"], 2.5 / 1.5, places=2)

    def test_short_barriers_flip(self):
        b = IF._barriers("short", 100.0, 2.0)
        self.assertGreater(b["stop"], 100.0)
        self.assertLess(b["target"], 100.0)

    def test_neutral_no_plan(self):
        self.assertIsNone(IF._barriers("neutral", 100.0, 2.0)["stop"])


class TestMetaLabel(unittest.TestCase):
    def test_fallback_gate_when_uq_absent(self):
        with mock.patch("trading.uq.conformal.get_uq", side_effect=RuntimeError("no model")):
            strong = IF._meta_label(0.6, "long", "crypto", "BTC/USDT")
            weak = IF._meta_label(0.1, "long", "crypto", "BTC/USDT")
        self.assertTrue(strong["act"])
        self.assertFalse(weak["act"])
        self.assertTrue(strong["source"].startswith("fallback"))


class TestFuse(unittest.TestCase):
    def setUp(self):
        # isolate from the async deep-vision cache (vision_worker) — these tests validate the
        # numeric confluence + explicitly-passed vision, not whatever a live read cached.
        from trading.broker_sense import vision_worker
        self._dv = mock.patch.object(vision_worker, "deep_vision", return_value=None)
        self._dv.start()
        self.addCleanup(self._dv.stop)
        # isolate from the external on-chain fetch (altdata.onchain) — deterministic + fast
        self._oc = mock.patch.object(IF, "_onchain_cached", return_value=None)
        self._oc.start()
        self.addCleanup(self._oc.stop)
        # isolate from the per-5m-bar fuse() memo: these tests re-mock _fetch per case, so a
        # cached result from a prior test (same symbol + bar) must not leak in. (2026-07-12)
        IF._FUSE_CACHE.clear()

    def _patch_fetch(self, trend):
        return mock.patch.object(IF, "_fetch",
                                 side_effect=lambda sym, mkt, tf, bars=IF._BARS: _series(trend))

    def test_fuse_uptrend_all_tfs(self):
        with self._patch_fetch(0.004):
            r = IF.fuse("BTC/USDT", "crypto",
                        vision={"5m": {"p_up": 0.62, "direction": "long", "source": "fast:ohlcv"}})
        self.assertTrue(r["available"])
        self.assertEqual(r["direction"], "long")
        self.assertGreater(r["confluence"], 0)
        self.assertIsNotNone(r["barriers"]["stop"])
        self.assertIn(r["trigger_tf"], IF._TRIGGER_TFS + tuple(r["per_tf"]))
        self.assertTrue(all(v["available"] for v in r["per_tf"].values()))

    def test_fuse_downtrend_short(self):
        with self._patch_fetch(-0.004):
            r = IF.fuse("BTC/USDT", "crypto")
        self.assertEqual(r["direction"], "short")
        self.assertLess(r["confluence"], 0)

    def test_fuse_unavailable_when_no_data(self):
        with mock.patch.object(IF, "_fetch", return_value=None):
            r = IF.fuse("BTC/USDT", "crypto")
        self.assertFalse(r["available"])
        self.assertEqual(r["direction"], "neutral")
        self.assertEqual(r["p_up"], 0.5)

    def test_vision_disagreement_shrinks_conviction(self):
        # numeric = strong long, vision = strong short → conviction shrinks vs vision-agree case
        with self._patch_fetch(0.004):
            agree = IF.fuse("BTC/USDT", "crypto",
                            vision={"5m": {"p_up": 0.9, "direction": "long"}})
            disagree = IF.fuse("BTC/USDT", "crypto",
                               vision={"5m": {"p_up": 0.1, "direction": "short"}})
        self.assertGreater(agree["confluence"], disagree["confluence"])


if __name__ == "__main__":
    unittest.main()
