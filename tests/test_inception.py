"""Tests for trading/broker_sense/inception.py — the inception ranker + lifecycle phase
+ freshness gate (SELECTION-CRITIQUE 2026-07-17)."""
from __future__ import annotations

import unittest
from unittest import mock


def _bars(closes, highs=None, lows=None, t0=1_784_300_000):
    """Synthetic 5m bars [ts, o, h, l, c]."""
    highs = highs or [c * 1.001 for c in closes]
    lows = lows or [c * 0.999 for c in closes]
    return [[t0 + i * 300, closes[i], highs[i], lows[i], closes[i]]
            for i in range(len(closes))]


def _mirror(bars, taker=None, liqs=None):
    m = mock.Mock()
    m.candles.return_value = bars
    m.taker.return_value = taker
    m.recent_liquidations.return_value = liqs or []
    m.futures_rows.return_value = []
    return m


def _patch(m):
    return mock.patch("trading.broker_sense.binance_stream.get_mirror", return_value=m)


class TestFeaturesAndScore(unittest.TestCase):
    def setUp(self):
        from trading.broker_sense import inception
        inception.clear_cache()

    def test_flat_tape_scores_low_and_quiet(self):
        from trading.broker_sense import inception
        with _patch(_mirror(_bars([100.0] * 49))):
            f = inception.features("AKE/USDT")
            self.assertIsNotNone(f)
            self.assertEqual(inception.phase("AKEUSDT"), "quiet")
            self.assertLess(inception.score(f), 2.0)     # no breakout/accel/flow terms

    def test_fresh_breakout_outscores_flat(self):
        from trading.broker_sense import inception
        # flat 4h then the LAST bar rips to a new high: the inception signature
        closes = [100.0] * 48 + [103.0]
        highs = [100.1] * 48 + [103.2]
        with _patch(_mirror(_bars(closes, highs=highs))):
            hot = inception.score(inception.features("A"))
        inception.clear_cache()
        with _patch(_mirror(_bars([100.0] * 49))):
            cold = inception.score(inception.features("A"))
        self.assertGreater(hot, cold + 1.5)              # breakout + accel dominate

    def test_stale_big_mover_is_penalized_and_phased_stale(self):
        from trading.broker_sense import inception
        # +8% move in the FIRST hour of the window, dead flat since (stale cohort)
        closes = [100.0] * 6 + [108.0] * 43
        with _patch(_mirror(_bars(closes))):
            f = inception.features("A")
            self.assertEqual(inception.phase("A"), "stale")
            ok, why = inception.fresh_ok("A", "LONG")
            self.assertFalse(ok)
            self.assertIn("stalled", why)
            # the SHORT side of the same tape is not the stale cohort (move was UP)
            inception.clear_cache()
        with _patch(_mirror(_bars(closes))):
            ok2, _ = inception.fresh_ok("A", "SHORT")
            self.assertTrue(ok2)

    def test_fresh_mover_passes_gate(self):
        from trading.broker_sense import inception
        # still climbing through the last hour → fresh
        closes = [100.0 + 0.2 * i for i in range(49)]
        with _patch(_mirror(_bars(closes))):
            ok, _ = inception.fresh_ok("A", "LONG")
            self.assertTrue(ok)
            self.assertIn(inception.phase("A"), ("fresh", "extended"))

    def test_no_data_fails_open_everywhere(self):
        from trading.broker_sense import inception
        with _patch(_mirror([])):
            self.assertIsNone(inception.features("A"))
            self.assertIsNone(inception.phase("A"))
            ok, why = inception.fresh_ok("A", "LONG")
            self.assertTrue(ok)
            self.assertIn("fail-open", why)
            self.assertEqual(inception.score(None), 0.0)

    def test_phase_and_gate_use_the_cache(self):
        """Review fix: phase()/fresh_ok() must go through cached_features — an uncached
        49-bar mirror read per truth-ledger claim was multiplying hot-path work."""
        from trading.broker_sense import inception
        calls = []
        real = inception.features

        def _counting(sym):
            calls.append(sym)
            return real(sym)
        with _patch(_mirror(_bars([100.0] * 49))), \
                mock.patch.object(inception, "features", side_effect=_counting):
            inception.phase("AKEUSDT")
            inception.fresh_ok("AKEUSDT", "LONG")
            inception.phase("AKEUSDT")
        self.assertEqual(len(calls), 1)              # one build, two cache hits

    def test_order_preserves_input_on_cold_mirror_and_ranks_hot_first(self):
        from trading.broker_sense import inception
        closes_hot = [100.0] * 48 + [103.0]
        highs_hot = [100.1] * 48 + [103.2]

        def _candles(sym, tf, n):
            return _bars(closes_hot, highs=highs_hot) if sym == "HOT" \
                else (_bars([100.0] * 49) if sym == "FLAT" else [])
        m = mock.Mock()
        m.candles.side_effect = _candles
        m.taker.return_value = None
        m.recent_liquidations.return_value = []
        with _patch(m):
            out = inception.order(["FLAT", "NODATA", "HOT"])
            self.assertEqual(out[0], "HOT")
            # ties (FLAT vs NODATA scores) keep the caller's original order
            self.assertEqual(out[1:], ["FLAT", "NODATA"])


if __name__ == "__main__":
    unittest.main()
