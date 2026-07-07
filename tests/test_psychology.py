"""Trader-psychology engine (order-book depth) — pure-computation tests.

State-isolated: STATE_DIR is redirected to a temp dir BEFORE any trading import so the
sidecar entry-meta tests never touch the live journal/state (convention: Path, not str).
"""
import random
import tempfile
import time
import unittest
from collections import deque
from pathlib import Path

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # MUST precede any state-touching import

from trading.brain.psychology import (  # noqa: E402
    BookSnapshot, StoikovMicroprice, detect_walls, depth_slope_bias,
    evaluate_ring, psych_columns, ring_to_frame, PSYCH_TRADE_COLUMNS,
)


def _snap(mid, bid_boost=0.0, ask_boost=0.0, ts=None, levels=5):
    bids = [(round(mid - 0.01 * (i + 1), 4), 50.0 + (bid_boost if i == 1 else 0.0))
            for i in range(levels)]
    asks = [(round(mid + 0.01 * (i + 1), 4), 50.0 + (ask_boost if i == 1 else 0.0))
            for i in range(levels)]
    return BookSnapshot(ts=ts or time.time(), bids=bids, asks=asks,
                        last_price=mid, last_qty=5.0)


def _ring(n=150, bid_boost=0.0, ask_boost=0.0, seed=7):
    rng = random.Random(seed)
    ring = deque(maxlen=720)
    mid = 100.0
    for t in range(n):
        mid += rng.gauss(0, 0.02)
        ring.append(_snap(mid, bid_boost=bid_boost, ask_boost=ask_boost, ts=1e9 + t))
    return ring


class TestSnapshots(unittest.TestCase):
    def test_from_ccxt(self):
        s = BookSnapshot.from_ccxt({"bids": [[100, 2], [99, 3]], "asks": [[101, 1]],
                                    "timestamp": 1700000000000})
        self.assertEqual(s.mid, 100.5)
        self.assertEqual(s.bids[0], (100.0, 2.0))

    def test_from_openalgo_dict_rows(self):
        s = BookSnapshot.from_openalgo({"data": {
            "bids": [{"price": 100, "quantity": 5}, {"price": 99.5, "quantity": 2}],
            "asks": [{"price": 100.5, "quantity": 4}], "ltp": 100.2}})
        self.assertEqual(s.mid, 100.25)
        self.assertEqual(s.last_price, 100.2)

    def test_empty_side_returns_none(self):
        self.assertIsNone(BookSnapshot.from_ccxt({"bids": [], "asks": [[1, 1]]}))

    def test_ring_to_frame_columns(self):
        df = ring_to_frame(_ring(5), levels=5)
        for col in ("bid_price_1", "bid_qty_5", "ask_price_1", "mid_price"):
            self.assertIn(col, df.columns)
        self.assertEqual(len(df), 5)


class TestSignals(unittest.TestCase):
    def test_bid_heavy_book_scores_positive(self):
        r = evaluate_ring(_ring(150, bid_boost=300.0))
        self.assertIsNotNone(r)
        self.assertGreater(r["psych_obi"], 0.2)
        self.assertGreater(r["trader_psychology"], 0.0)
        self.assertIn(r["psych_label"], ("optimistic", "greedy", "euphoric", "balanced", "anxious"))

    def test_ask_heavy_book_scores_negative(self):
        r = evaluate_ring(_ring(150, ask_boost=300.0))
        self.assertLess(r["psych_obi"], -0.2)
        self.assertLess(r["trader_psychology"], 0.0)

    def test_score_bounded(self):
        for boost in (0.0, 500.0):
            r = evaluate_ring(_ring(80, bid_boost=boost))
            self.assertGreaterEqual(r["trader_psychology"], -1.0)
            self.assertLessEqual(r["trader_psychology"], 1.0)
            self.assertGreaterEqual(r["psych_fear"], 0.0)
            self.assertLessEqual(r["psych_fear"], 1.0)

    def test_wall_detection_bias(self):
        s = _snap(100.0, bid_boost=400.0)
        walls = detect_walls(s)
        self.assertGreater(walls["bias"], 0.0)
        self.assertTrue(walls["bid_walls"])

    def test_depth_slope_symmetric_book_is_zero(self):
        s = _snap(100.0)
        self.assertAlmostEqual(depth_slope_bias(s), 0.0, places=6)

    def test_single_snapshot_still_evaluates(self):
        r = evaluate_ring([_snap(100.0)])
        self.assertIsNotNone(r)
        self.assertEqual(r["n_snapshots"], 1)

    def test_microprice_fallback_is_weighted_mid_adjustment(self):
        m = StoikovMicroprice()
        s = BookSnapshot(ts=0, bids=[(99.0, 90.0)], asks=[(101.0, 10.0)])
        adj = m.adjustment(s)                      # imb = 0.9 → drift toward the ask
        self.assertGreater(adj, 0.0)

    def test_psych_columns_subset(self):
        r = evaluate_ring(_ring(60))
        cols = psych_columns(r)
        self.assertIn("trader_psychology", cols)
        for k in cols:
            self.assertIn(k, PSYCH_TRADE_COLUMNS)


class TestJournalWiring(unittest.TestCase):
    def test_schema_has_psych_and_snapshot_columns(self):
        from trading.journal.schema import COLUMNS
        for c in ("trader_psychology", "psych_label", "psych_obi", "psych_fear",
                  "psych_deeplob_prob_up", "decision_snapshot"):
            self.assertIn(c, COLUMNS)

    def test_feature_row_includes_psych(self):
        from trading.brain.trade_features import FEATURE_NAMES, trade_feature_row
        self.assertIn("psych_alignment", FEATURE_NAMES)
        row = trade_feature_row({"direction": "SHORT", "quantity": 1, "entry_price": 10,
                                 "trader_psychology": -0.5, "psych_fear": 0.7})
        self.assertEqual(len(row), len(FEATURE_NAMES))
        self.assertEqual(row[FEATURE_NAMES.index("psych_alignment")], 0.5)

    def test_crypto_sidecar_round_trip(self):
        import datetime as dt
        from trading.crypto import freqtrade_ingest
        from trading.crypto.freqtrade import entry_meta
        now = dt.datetime.now(dt.timezone.utc)
        entry_meta.record("ETH/USDT:USDT", "futures", {
            "psychology": {"trader_psychology": -0.33, "psych_label": "fearful"},
            "decision_snapshot": {"direction": "SHORT", "strategy": "sX"}})
        ft = {"trade_id": 9, "pair": "ETH/USDT:USDT", "is_short": True, "open_rate": 10.0,
              "close_rate": 9.0, "amount": 1.0, "trading_mode": "futures",
              "open_date": now.isoformat(), "close_date": now.isoformat()}
        t = freqtrade_ingest.map_trade(ft)
        self.assertEqual(t.trader_psychology, -0.33)
        self.assertEqual(t.decision_snapshot["strategy"], "sX")

    def test_sidecar_no_match_outside_window(self):
        import datetime as dt
        from trading.crypto.freqtrade import entry_meta
        entry_meta.record("XRP/USDT:USDT", "futures", {"psychology": {"trader_psychology": 0.1}})
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=2)).isoformat()
        self.assertIsNone(entry_meta.lookup("XRP/USDT:USDT", "futures", old))


class TestDeepLob(unittest.TestCase):
    def test_sampling_and_forward_shape(self):
        import numpy as np
        from trading.brain import psych_deeplob as D
        series = (np.cumsum(np.random.default_rng(0).normal(0, 0.01, (200, 20)), axis=0)
                  + 100).astype("float32")
        X, y = D.make_samples(series)
        self.assertEqual(X.shape[1:], (D.WINDOW, 20))
        self.assertEqual(len(X), len(y))
        self.assertTrue(set(y).issubset({0, 1, 2}))

    def test_predict_none_without_model(self):
        from trading.brain import psych_deeplob as D
        if not D.MODEL_PATH.exists():          # honest: no model → None, never a fake prob
            self.assertIsNone(D.predict_prob_up(_ring(120)))


if __name__ == "__main__":
    unittest.main()
