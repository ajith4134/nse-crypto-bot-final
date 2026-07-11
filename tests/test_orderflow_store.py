"""Tests for trading/broker_sense/orderflow_store.py — per-bar real order-flow history store.

Covers: snapshot persists an order-flow record (with a GOFI proxy), same-bar dedup, series()
round-trip, join_features() splices of_* columns onto an OHLCV frame by timestamp, and honest
degrade when order-flow is unavailable. binance_orderflow is mocked; state is isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from trading import state
from trading.broker_sense import orderflow_store as ofs


def _feat(tr=1.4, crowd=62.0):
    return {"symbol": "BTCUSDT", "taker_buy_sell_ratio": tr, "crowd_long_pct": crowd,
            "smart_long_pct": 58.0, "open_interest": 1.2e9, "funding_rate": 0.0001,
            "liq_skew": -0.3}


class StoreTest(unittest.TestCase):
    def setUp(self):
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="ofs_"))

    def tearDown(self):
        state.STATE_DIR = self._orig

    def _patch(self, feat=None, enabled=True):
        import contextlib
        st = contextlib.ExitStack()
        st.enter_context(mock.patch("trading.broker_sense.binance_orderflow.enabled",
                                    return_value=enabled))
        st.enter_context(mock.patch("trading.broker_sense.binance_orderflow.features",
                                    return_value=feat if feat is not None else _feat()))
        return st

    def test_snapshot_persists_with_gofi(self):
        with self._patch():
            rec = ofs.snapshot("BTC/USDT", "crypto")
        self.assertIsNotNone(rec)
        self.assertEqual(rec["of_taker_ratio"], 1.4)
        self.assertIsNotNone(rec["of_gofi"])                 # computed proxy
        self.assertGreater(rec["of_gofi"], 0)                # ratio>1 + crowd long → positive
        self.assertEqual(ofs.series("BTC/USDT").iloc[-1]["of_crowd_long"], 62.0)

    def test_same_bar_dedup(self):
        with self._patch(_feat(tr=1.4)):
            ofs.snapshot("ETH/USDT")
        with self._patch(_feat(tr=2.0)):                     # same bar → replace, not append
            ofs.snapshot("ETH/USDT")
        s = ofs.series("ETH/USDT")
        self.assertEqual(len(s), 1)
        self.assertEqual(s.iloc[-1]["of_taker_ratio"], 2.0)

    def test_disabled_degrades(self):
        with self._patch(enabled=False):
            self.assertIsNone(ofs.snapshot("BTC/USDT"))
        self.assertIsNone(ofs.series("BTC/USDT"))

    def test_all_none_feat_skipped(self):
        with self._patch({"symbol": "X"}):                   # no order-flow fields
            self.assertIsNone(ofs.snapshot("X/USDT"))

    def test_join_features_adds_columns(self):
        # seed a store row, then join onto a DatetimeIndex OHLCV frame overlapping its ts
        with self._patch():
            rec = ofs.snapshot("BTC/USDT")
        idx = pd.to_datetime(np.arange(rec["ts"] - 600, rec["ts"] + 600, 60), unit="s")
        feats = pd.DataFrame({"close": np.arange(len(idx), dtype=float)}, index=idx)
        merged = ofs.join_features(feats, "BTC/USDT")
        self.assertIn("of_gofi", merged.columns)
        self.assertIn("of_taker_ratio", merged.columns)
        self.assertEqual(len(merged), len(feats))            # no rows lost
        self.assertTrue(merged["of_gofi"].notna().any())     # at/after the snapshot bar, filled

    def test_join_no_store_returns_unchanged(self):
        feats = pd.DataFrame({"close": [1.0, 2.0]})
        self.assertIs(ofs.join_features(feats, "NOPE"), feats)


if __name__ == "__main__":
    unittest.main()
