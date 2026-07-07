"""Tests for the broker built-in-feature exploitation subsystem (trading/broker_sense/broker_features).

Covers the pure logic (no browser): catalog, weighted fusion, learned per-feature weights (stacking),
new-entry detection, stacking credit at close, preset invention. STATE_DIR-isolated."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trading.state as state


class _Isolated(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        import trading.broker_sense.broker_features as bf
        bf._PERF = None

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()
        import trading.broker_sense.broker_features as bf
        bf._PERF = None


class TestCatalog(_Isolated):
    def test_catalog_has_owner_named_upstox_features(self):
        from trading.broker_sense.broker_features import FEATURE_CATALOG
        names = {f["name"] for f in FEATURE_CATALOG["upstox"]}
        for n in ("momentum_gainers_1m", "momentum_gainers_5m", "trending_under_500",
                  "top_gainers", "top_losers", "algovers", "scalper", "chart360", "oi_analysis"):
            self.assertIn(n, names)

    def test_catalog_has_binance_features(self):
        from trading.broker_sense.broker_features import FEATURE_CATALOG
        names = {f["name"] for f in FEATURE_CATALOG["binance"]}
        for n in ("top_movers", "funding_board", "liquidation_heatmap", "long_short_leaderboard"):
            self.assertIn(n, names)


class TestFusion(_Isolated):
    def test_symbol_in_more_bullish_pickers_scores_higher(self):
        from trading.broker_sense import broker_features as bf
        fmap = {"top_gainers": [{"symbol": "RELIANCE", "change": 3.0}],
                "trending_stocks": [{"symbol": "RELIANCE", "change": 2.0},
                                    {"symbol": "TCS", "change": 1.0}],
                "momentum_gainers_5m": [{"symbol": "RELIANCE", "change": 1.5}]}
        ranked = bf.fuse("upstox", fmap)
        self.assertEqual(ranked[0]["symbol"], "RELIANCE")
        self.assertEqual(ranked[0]["side"], "long")
        self.assertGreaterEqual(len(ranked[0]["features"]), 3)

    def test_bearish_picker_pushes_short(self):
        from trading.broker_sense import broker_features as bf
        ranked = bf.fuse("upstox", {"top_losers": [{"symbol": "XYZ", "change": -4.0}]})
        self.assertEqual(ranked[0]["side"], "short")


class TestPerfStacking(_Isolated):
    def test_weight_rises_with_wins(self):
        from trading.broker_sense import broker_features as bf
        p = bf.get_perf()
        base = p.weight("binance", "top_gainers")
        for _ in range(6):
            p.record("binance", "top_gainers", win=True, pnl=5.0)
        self.assertGreater(p.weight("binance", "top_gainers"), base)

    def test_credit_symbol_rewards_pickers_that_listed_it(self):
        from trading.broker_sense import broker_features as bf
        bf._record_snapshots("binance", {"top_gainers": [{"symbol": "BTC/USDT:USDT"}],
                                         "top_losers": [{"symbol": "ETH/USDT:USDT"}]})
        credited = bf.credit_symbol("binance", "BTC/USDT:USDT", win=True, pnl=10.0)
        self.assertIn("top_gainers", credited)
        self.assertNotIn("top_losers", credited)
        self.assertEqual(bf.get_perf().perf["binance|top_gainers"]["wins"], 1)


class TestNewEntry(_Isolated):
    def test_new_entry_detected_after_snapshot(self):
        from trading.broker_sense import broker_features as bf
        self.assertEqual(sorted(bf.new_entries("upstox", "top_gainers", ["A", "B"])), ["A", "B"])
        bf._record_snapshots("upstox", {"top_gainers": [{"symbol": "A"}]})
        self.assertEqual(bf.new_entries("upstox", "top_gainers", ["A", "C"]), ["C"])


class TestPresetInvention(_Isolated):
    def test_invent_preset_is_deterministic_and_persists(self):
        from trading.broker_sense import broker_features as bf
        a = bf.invent_preset("binance", 0)
        self.assertTrue(a["name"].startswith("inv_"))
        self.assertEqual(len(a["filters"]), 2)
        self.assertIn(a["name"], bf.invented_presets("binance"))


class TestWatchlistGated(_Isolated):
    def test_watchlist_is_read_only_without_flag(self):
        import os
        from trading.broker_sense import broker_features as bf
        os.environ.pop("BROKER_WATCHLIST_WRITE", None)
        out = bf.watchlist_remember("upstox", ["RELIANCE", "TCS"])
        self.assertFalse(out["wrote"])
        self.assertEqual(out["would_add"], ["RELIANCE", "TCS"])


if __name__ == "__main__":
    unittest.main()
