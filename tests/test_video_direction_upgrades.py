"""Tests for the 2026-07-17 video-derived direction upgrades.

Covers: opening_range_profile (anchored window, TPO degrade, honest misses),
value_area_events (trap/acceptance state machine, fresh-trigger-only),
market_state (corr regime, breadth tilt, spillover copy/seesaw split, conditioners),
vp_events (readings + level cache + ledger recording, isolated STATE_DIR),
cycle_gate (a real cycle passes the permutation null, a random walk fails it).
"""
from __future__ import annotations

import math
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from trading.broker_sense import volume_profile as vp

ANCHOR = 1_760_000_000 - (1_760_000_000 % 86_400)      # a clean UTC day open (epoch s)


def _bar(ts_s, o, h, l, c, v=100.0):
    return [ts_s * 1000, o, h, l, c, v]


def _or_window(anchor=ANCHOR, minutes=15, price=100.0, vol=100.0):
    """1m bars filling the opening-range window, volume concentrated at `price`."""
    return [_bar(anchor + i * 60, price, price + 1.0, price - 1.0, price, vol)
            for i in range(minutes)]


class TestOpeningRangeProfile(unittest.TestCase):
    def test_levels_from_window(self):
        rows = _or_window()
        # bars OUTSIDE the window at a wild price must not affect the profile
        rows += [_bar(ANCHOR + 3600, 500, 501, 499, 500, 9999)]
        p = vp.opening_range_profile(rows, ANCHOR, 15)
        self.assertTrue(p["available"])
        self.assertEqual(p["basis"], "volume")
        self.assertEqual(p["n_bars"], 15)
        self.assertTrue(99.0 <= p["val"] <= p["poc"] <= p["vah"] <= 101.5)
        self.assertEqual(p["anchor_ts"], ANCHOR)
        self.assertEqual(p["end_ts"], ANCHOR + 900)

    def test_tpo_degrade_without_volume(self):
        rows = [_bar(ANCHOR + i * 60, 100, 101, 99, 100, 0.0) for i in range(15)]
        p = vp.opening_range_profile(rows, ANCHOR, 15)
        self.assertTrue(p["available"])
        self.assertEqual(p["basis"], "tpo")

    def test_uncovered_window_is_honest(self):
        self.assertFalse(vp.opening_range_profile([], ANCHOR, 15)["available"])
        # data starting mid-window → refused (false levels are worse than none)
        rows = [_bar(ANCHOR + 360 + i * 60, 100, 101, 99, 100) for i in range(9)]
        self.assertFalse(vp.opening_range_profile(rows, ANCHOR, 15)["available"])


def _va():
    return {"available": True, "vah": 101.0, "val": 99.0, "poc": 100.0}


def _ev_bar(i, o, h, l, c):
    return [(ANCHOR + 900 + i * 300) * 1000, o, h, l, c, 100.0]


class TestValueAreaEvents(unittest.TestCase):
    def test_trap_short_fires_on_last_bar(self):
        bars = [_ev_bar(0, 100, 100.5, 99.5, 100.2),        # inside
                _ev_bar(1, 100.2, 102.4, 100.1, 102.0),     # closed ABOVE VAH (excursion)
                _ev_bar(2, 102.0, 102.2, 100.2, 100.4)]     # closed back inside → trap NOW
        ev = vp.value_area_events(bars, _va())
        self.assertEqual(ev["event"], "trap")
        self.assertEqual(ev["side"], "short")
        self.assertAlmostEqual(ev["stop"], 102.4)           # the excursion extreme
        self.assertAlmostEqual(ev["target"], 99.0)          # the far VA edge
        self.assertGreaterEqual(ev["strength"], 0.55)

    def test_stale_trigger_never_fires(self):
        bars = [_ev_bar(0, 100, 100.5, 99.5, 100.2),
                _ev_bar(1, 100.2, 102.4, 100.1, 102.0),
                _ev_bar(2, 102.0, 102.2, 100.2, 100.4),     # trap completed here…
                _ev_bar(3, 100.4, 100.6, 100.0, 100.3)]     # …but this is the last bar
        self.assertEqual(vp.value_area_events(bars, _va())["event"], "")

    def test_trap_long_below_val(self):
        bars = [_ev_bar(0, 100, 100.5, 99.5, 100.0),
                _ev_bar(1, 100.0, 100.1, 97.8, 98.2),       # closed BELOW VAL
                _ev_bar(2, 98.2, 100.0, 98.0, 99.6)]        # back inside → trapped sellers
        ev = vp.value_area_events(bars, _va())
        self.assertEqual((ev["event"], ev["side"]), ("trap", "long"))
        self.assertAlmostEqual(ev["stop"], 97.8)
        self.assertAlmostEqual(ev["target"], 101.0)

    def test_acceptance_pullback_long(self):
        bars = [_ev_bar(0, 100, 100.5, 99.5, 100.2),
                _ev_bar(1, 100.2, 101.8, 100.1, 101.6),     # close above VAH  (1)
                _ev_bar(2, 101.6, 102.3, 101.4, 102.1),     # close above VAH  (2) → accepted
                _ev_bar(3, 102.1, 102.2, 100.9, 101.5)]     # pullback touches VAH, closes above
        ev = vp.value_area_events(bars, _va())
        self.assertEqual((ev["event"], ev["side"]), ("accept_pullback", "long"))
        self.assertAlmostEqual(ev["stop"], 100.9)           # the pullback bar's low
        self.assertIsNone(ev["target"])                     # let it run — trail per candle
        self.assertEqual(ev["trail"], "candle_low")

    def test_failed_acceptance_is_no_play(self):
        bars = [_ev_bar(0, 100, 100.5, 99.5, 100.2),
                _ev_bar(1, 100.2, 101.8, 100.1, 101.6),
                _ev_bar(2, 101.6, 102.3, 101.4, 102.1),     # accepted…
                _ev_bar(3, 102.1, 102.2, 100.2, 100.5)]     # …then closed back INSIDE (late trap)
        self.assertEqual(vp.value_area_events(bars, _va())["event"], "")


class _FakeMirror:
    """Deterministic mirror stand-in: leaders trend, one large follower lags, small caps flat."""

    def __init__(self, breadth_up=True):
        self.n_syms = 40
        self.breadth_up = breadth_up

    def movers(self, n=100, *, by="quote_volume", min_quote_volume=0.0):
        rows = [{"symbol": "BTCUSDT", "quote_volume": 1e9},
                {"symbol": "ETHUSDT", "quote_volume": 8e8},
                {"symbol": "BIGUSDT", "quote_volume": 5e8}]
        rows += [{"symbol": f"S{i:02d}USDT", "quote_volume": 1e6 - i}
                 for i in range(self.n_syms - 3)]
        return rows[:n]

    def candles(self, symbol, tf=300, n=49):
        base = {"BTCUSDT": 50_000.0, "ETHUSDT": 3_000.0, "BIGUSDT": 100.0}.get(symbol, 1.0)
        out = []
        t0 = int(time.time() // 300) * 300 - n * 300
        for i in range(n):
            # everyone rides one factor (high corr); BTC/ETH add a strong final 15m push;
            # BIG lags the push; small caps get a tiny drift so breadth is one-sided
            px = base * (1.0 + 0.001 * math.sin(i / 5.0))
            if symbol in ("BTCUSDT", "ETHUSDT") and i >= n - 3:
                px *= 1.01
            if symbol.startswith("S"):
                px *= 1.0 + (0.0005 if self.breadth_up else -0.0005) * i
            out.append([t0 + i * 300, px, px * 1.001, px * 0.999, px])
        return out


class TestMarketState(unittest.TestCase):
    def setUp(self):
        from trading.direction import market_state as ms
        ms._SNAP.clear()
        self.ms = ms

    def _patched(self, mirror):
        return mock.patch("trading.broker_sense.binance_stream.get_mirror",
                          return_value=mirror)

    def test_snapshot_and_regime(self):
        with self._patched(_FakeMirror()):
            s = self.ms.snapshot()
            self.assertTrue(s["available"])
            self.assertGreaterEqual(s["n_symbols"], 10)
            self.assertIsNotNone(s["corr_top20"])
            self.assertIn(self.ms.corr_regime(s), ("high", "mid", "low"))
            cond = self.ms.conditioners()
            for k in ("ev_corr_regime", "ev_breadth_15m", "ev_btc_lead_15m"):
                self.assertIn(k, cond)

    def test_spillover_large_copies_unfollowed_leader(self):
        with self._patched(_FakeMirror()), \
                mock.patch("trading.direction.truth_ledger.record") as rec:
            self.ms._SNAP.clear()
            reads = dict(self.ms.readings("BIG/USDT:USDT", record=True))
            self.assertIn("spillover_large", reads)
            self.assertGreater(reads["spillover_large"], 0.5)   # leader up, BIG lagging → long
            self.assertTrue(rec.called)

    def test_spillover_seesaw_contra_for_small_caps(self):
        with self._patched(_FakeMirror()):
            self.ms._SNAP.clear()
            reads = dict(self.ms.readings("S30/USDT:USDT", record=False))
            self.assertIn("spillover_seesaw", reads)
            self.assertLess(reads["spillover_seesaw"], 0.5)     # leaders up → contra small caps

    def test_breadth_tilt_only_when_extreme(self):
        with self._patched(_FakeMirror(breadth_up=True)):
            self.ms._SNAP.clear()
            reads = dict(self.ms.readings("S05/USDT:USDT", record=False))
            self.assertIn("breadth_tilt", reads)
            self.assertGreater(reads["breadth_tilt"], 0.5)

    def test_leaders_get_no_spillover_reading(self):
        with self._patched(_FakeMirror()):
            self.ms._SNAP.clear()
            reads = dict(self.ms.readings("BTC/USDT:USDT", record=False))
            self.assertNotIn("spillover_large", reads)
            self.assertNotIn("spillover_seesaw", reads)


class TestVpEvents(unittest.TestCase):
    def setUp(self):
        from trading.direction import vp_events as vpe
        self.vpe = vpe
        self.tmp = tempfile.TemporaryDirectory()
        self._sd = mock.patch("trading.state.STATE_DIR", Path(self.tmp.name))
        self._sd.start()

    def tearDown(self):
        self._sd.stop()
        self.tmp.cleanup()

    def test_trap_reading_recorded_and_cached(self):
        anchor = self.vpe.anchors()[0][1]

        class _M:
            def candles(self, sym, tf, n):
                if tf == 60:                       # the OR window, mark-price (TPO degrade)
                    return [[anchor + i * 60, 100, 101, 99, 100] for i in range(16)]
                bars = [[anchor + 900, 100, 100.5, 99.5, 100.2],
                        [anchor + 1200, 100.2, 102.4, 100.1, 102.0],
                        [anchor + 1500, 102.0, 102.2, 100.2, 100.3]]   # trap short NOW
                return bars

        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=_M()), \
                mock.patch.object(self.vpe, "_volume_candles_1m", return_value=None), \
                mock.patch("trading.direction.truth_ledger.record") as rec:
            reads = self.vpe.readings("BTC/USDT:USDT", segment="futures")
            srcs = dict(reads)
            trap = [k for k in srcs if k.startswith("vp_trap:")]
            self.assertTrue(trap, f"no trap source in {srcs}")
            self.assertLess(srcs[trap[0]], 0.5)                  # short lean
            self.assertTrue(rec.called)
            plan = self.vpe.readings.last_plans[trap[0]]
            self.assertEqual(plan["side"], "short")
            self.assertEqual(plan["basis"], "tpo")
            # levels were cached for the session
            from trading import state
            self.assertTrue(state.load_json("vp_or_levels.json", {}))

    def test_disabled_flag(self):
        with mock.patch.dict("os.environ", {"VP_OR_SOURCE": "0"}):
            self.assertEqual(self.vpe.readings("BTC/USDT:USDT"), [])


class TestCycleGate(unittest.TestCase):
    def test_real_cycle_passes_random_walk_fails(self):
        from trading.strategy import cycle_gate as cg
        import numpy as np
        rng = np.random.default_rng(11)
        n = 1500
        # a genuine cycle IN RETURNS: log-price = slow sine + small noise
        t = np.arange(n)
        cyc = np.exp(0.05 * np.sin(2 * math.pi * t / 64) + 0.002 * rng.standard_normal(n)) * 100
        rep = cg.spectral_null_test(cyc.tolist(), n_sims=99)
        self.assertTrue(rep["passed"], rep)
        # a pure random walk: the video's trap — must NOT pass on returns
        rw = 100 * np.exp(np.cumsum(0.005 * rng.standard_normal(n)))
        rep = cg.spectral_null_test(rw.tolist(), n_sims=99)
        self.assertFalse(rep["passed"], rep)

    def test_citation_detection_and_gate_shape(self):
        from trading.strategy import cycle_gate as cg
        self.assertTrue(cg.is_cycle_citing("MESA adaptive dominant cycle"))
        self.assertTrue(cg.is_cycle_citing(None, "fourier momentum blend"))
        self.assertFalse(cg.is_cycle_citing("orderflow imbalance scalper", "vwap"))
        g = cg.gate("crypto_futures", "plain momentum breakout")
        self.assertEqual((g["required"], g["passed"]), (False, True))

    def test_martingale_baseline(self):
        from trading.strategy import cycle_gate as cg
        import numpy as np
        rw = 100 * np.exp(np.cumsum(0.01 * np.random.default_rng(3).standard_normal(800)))
        b = cg.martingale_baseline(rw.tolist())
        self.assertGreater(b["n"], 700)
        self.assertTrue(0.35 <= b["persistence_acc"] <= 0.65)


class TestDecideIntegration(unittest.TestCase):
    def test_new_sources_start_nearly_weightless(self):
        """Unproven sources must not be able to dominate a decision (CONVENTIONS §16)."""
        from trading.direction import learned_direction as ld
        with mock.patch("trading.direction.truth_ledger.source_reliability",
                        return_value={"n": 0, "correct": 0, "rate": None,
                                      "ci_low": None, "ci_high": None, "edge": None}):
            ld.clear_cache()
            out = ld.decide([("vp_trap:utc", 0.15), ("spillover_seesaw", 0.2),
                             ("breadth_tilt", 0.8)], market="CRYPTO", symbol="X/USDT:USDT")
            for w in out["weights"].values():
                self.assertLessEqual(w["w"], ld._cfg()["unproven_w"])
                self.assertFalse(w["invert"])
            ld.clear_cache()


if __name__ == "__main__":
    unittest.main()
