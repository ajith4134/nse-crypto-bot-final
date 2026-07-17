"""Tests for the E12 cross-symbol routes (dominance / rank momentum / funding divergence /
lead-lag graph / pair spread) in trading/direction/market_state.py."""
from __future__ import annotations

import math
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


def _snap(**kw):
    base = {"ts": time.time(), "available": True, "corr_top20": 0.5,
            "breadth_15m": 0.5, "btc_ret_15m": 0.0, "eth_ret_15m": 0.0,
            "alt_median_ret_15m": 0.0, "btc_lead_15m": 0.0,
            "rets_15m": {}, "rank": {}, "rets_1h": {}, "rets_4h": {},
            "btc_ret_4h": None, "alt_median_ret_4h": None, "closes": {}}
    base.update(kw)
    return base


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _reads(self, snap, symbol="AKEUSDT"):
        from trading.direction import market_state as ms
        with mock.patch.object(ms, "snapshot", return_value=snap):
            return dict(ms.readings(symbol, record=False))


class TestDominanceTilt(_Base):
    def test_btc_outrunning_alts_leans_short(self):
        r = self._reads(_snap(btc_ret_4h=0.02, alt_median_ret_4h=0.002))
        self.assertAlmostEqual(r["dominance_tilt"], 0.38)

    def test_dominance_falling_leans_long(self):
        r = self._reads(_snap(btc_ret_4h=-0.01, alt_median_ret_4h=0.001))
        self.assertAlmostEqual(r["dominance_tilt"], 0.62)

    def test_small_dominance_abstains(self):
        r = self._reads(_snap(btc_ret_4h=0.003, alt_median_ret_4h=0.001))
        self.assertNotIn("dominance_tilt", r)


class TestRankMomentum(_Base):
    def _snap_low_corr(self, own):
        rets_1h = {f"S{i}USDT": (i - 20) / 1000.0 for i in range(40)}
        rets_1h["AKEUSDT"] = own
        return _snap(corr_top20=0.2, rets_1h=rets_1h)

    def test_top_decile_long_in_low_corr(self):
        r = self._reads(self._snap_low_corr(0.5))
        self.assertEqual(r["rank_momentum"], 0.62)

    def test_bottom_decile_short(self):
        r = self._reads(self._snap_low_corr(-0.5))
        self.assertEqual(r["rank_momentum"], 0.38)

    def test_high_corr_regime_abstains(self):
        snap = self._snap_low_corr(0.5)
        snap["corr_top20"] = 0.8
        r = self._reads(snap)
        self.assertNotIn("rank_momentum", r)


class TestFundingDivergence(_Base):
    def test_crowded_pump_with_flat_leaders_fades(self):
        snap = _snap(rets_15m={"AKEUSDT": 0.02})
        fake = mock.Mock()
        fake.funding.return_value = {"funding_rate": 0.001}
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=fake):
            r = self._reads(snap)
        self.assertEqual(r["funding_divergence"], 0.35)

    def test_leader_confirmed_move_abstains(self):
        snap = _snap(rets_15m={"AKEUSDT": 0.02}, btc_ret_15m=0.01)
        r = self._reads(snap)
        self.assertNotIn("funding_divergence", r)


class TestGraphRoutes(_Base):
    def test_leadlag_edge_fires_when_follower_lags(self):
        from trading import state
        state.save_json("market_graph.json",
                        {"ts": time.time(), "available": True,
                         "edges": {"AKEUSDT": {"leader": "BTCUSDT", "lag": 2,
                                               "corr": 0.5}},
                         "pairs": []})
        snap = _snap(rets_15m={"BTCUSDT": 0.01, "AKEUSDT": 0.001},
                     btc_ret_15m=0.01)
        r = self._reads(snap)
        self.assertIn("leadlag_graph", r)
        self.assertGreater(r["leadlag_graph"], 0.5)

    def test_stale_graph_abstains(self):
        from trading import state
        state.save_json("market_graph.json",
                        {"ts": time.time() - 10 * 3600, "available": True,
                         "edges": {"AKEUSDT": {"leader": "BTCUSDT", "lag": 2,
                                               "corr": 0.5}}, "pairs": []})
        snap = _snap(rets_15m={"BTCUSDT": 0.01, "AKEUSDT": 0.0}, btc_ret_15m=0.01)
        r = self._reads(snap)
        self.assertNotIn("leadlag_graph", r)

    def test_pair_spread_leans_toward_reversion(self):
        from trading import state
        beta, mu, sd = 1.0, 0.0, 0.01
        ca, cb = 110.0, 100.0                        # spread = ln(110/100) ≈ 0.0953 → z ≈ 9.5
        state.save_json("market_graph.json",
                        {"ts": time.time(), "available": True, "edges": {},
                         "pairs": [{"a": "AKEUSDT", "b": "TAOUSDT", "beta": beta,
                                    "mu": mu, "sd": sd, "ac1": 0.9}]})
        snap = _snap(closes={"AKEUSDT": [100, ca], "TAOUSDT": [100, cb]})
        r = self._reads(snap)
        self.assertIn("pair_spread", r)
        self.assertLess(r["pair_spread"], 0.5)       # AKE rich → short lean

    def test_build_graph_finds_lagged_edge(self):
        from trading.direction import market_state as ms
        n = 49
        import random
        rnd = random.Random(7)
        lead = [100.0]
        for _ in range(n - 1):
            lead.append(lead[-1] * (1 + rnd.uniform(-0.004, 0.004)))
        follow = [100.0]
        for i in range(1, n):                        # follower copies leader's move, 1 bar late
            prev = lead[i - 1] / lead[i - 2] - 1 if i >= 2 else 0.0
            follow.append(follow[-1] * (1 + prev))
        closes = {f"L{i}USDT": list(lead) for i in range(20)}
        closes["FOLLOWUSDT"] = follow
        rank = {s: i for i, s in enumerate(closes)}
        snap = _snap(closes=closes, rank=rank)
        with mock.patch.object(ms, "snapshot", return_value=snap):
            out = ms.build_graph(force=True)
        self.assertTrue(out["available"])
        from trading import state
        g = state.load_json("market_graph.json", {})
        self.assertIn("FOLLOWUSDT", g["edges"])
        self.assertEqual(g["edges"]["FOLLOWUSDT"]["lag"], 1)


if __name__ == "__main__":
    unittest.main()
