"""Tests for trading/broker_sense/book_ofi.py — TRUE L2 OFI/GOFI per-bar history (gap B)."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state


def _snap(bid, bq, ask, aq, bids=None, asks=None):
    return {"bid": bid, "bid_qty": bq, "ask": ask, "ask_qty": aq,
            "bids": bids, "asks": asks}


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.broker_sense import book_ofi
        book_ofi._acc.clear()
        book_ofi._last_sweep[0] = 0.0
        self.bo = book_ofi

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestOfiMath(_Iso):
    def test_cks_l1_and_level2_increments_and_bar_row(self):
        # bar_s=60 → ts 1000/1001 are bar 16; ts 1061 rolls to bar 17 and persists bar 16
        self.bo.on_book("BTCUSDT", _snap(100.0, 5.0, 101.0, 7.0,
                                         bids=[[100.0, 5.0], [99.0, 10.0]],
                                         asks=[[101.0, 7.0], [102.0, 8.0]]), ts=1000.0)
        self.bo.on_book("BTCUSDT", _snap(100.0, 8.0, 101.0, 4.0,
                                         bids=[[100.0, 8.0], [99.0, 12.0]],
                                         asks=[[101.0, 4.0], [102.0, 5.0]]), ts=1001.0)
        self.bo.on_book("BTCUSDT", _snap(100.0, 1.0, 101.0, 1.0), ts=1061.0)  # bar roll
        p = Path(state.STATE_DIR) / "orderflow" / "BTCUSDT.jsonl"
        self.assertTrue(p.exists())
        row = json.loads(p.read_text().strip().splitlines()[-1])
        # L1 CKS: bid same price → +8-5 = +3 ; ask same price → -4+7 = +3 → ofi = 6
        self.assertAlmostEqual(row["ofi"], 6.0)
        # mean L1 depth = ((5+7)/2 + (8+4)/2)/2 = 6 → ofi_n = 1.0
        self.assertAlmostEqual(row["ofi_n"], 1.0)
        # gofi = 1.0 + exp(-1/3) * (level2 ofi 5 / level2 mean depth 8.75) ≈ 1.4094
        self.assertAlmostEqual(row["gofi"], 1.4094, places=3)
        # obi mean: (-1/6 + 1/3)/2 = 1/12
        self.assertAlmostEqual(row["obi"], 1.0 / 12.0, places=5)
        self.assertEqual(row["n"], 2)
        self.assertEqual(row["ts"], 16 * 60)

    def test_stale_gap_resets_diff_state(self):
        self.bo.on_book("ETHUSDT", _snap(10.0, 100.0, 10.1, 100.0), ts=1000.0)
        # 500s gap (> _RESET_S) within... a later bar; increment must NOT be fabricated
        self.bo.on_book("ETHUSDT", _snap(10.0, 999.0, 10.1, 1.0), ts=1500.0)
        self.bo.on_book("ETHUSDT", _snap(10.0, 1.0, 10.1, 1.0), ts=1561.0)   # roll bar 25
        p = Path(state.STATE_DIR) / "orderflow" / "ETHUSDT.jsonl"
        row = json.loads(p.read_text().strip().splitlines()[-1])
        self.assertAlmostEqual(row["ofi"], 0.0)      # no prev in-window → no increment

    def test_kill_switch(self):
        import os
        os.environ["BOOK_OFI"] = "0"
        try:
            self.bo.on_book("XUSDT", _snap(1.0, 1.0, 1.1, 1.0), ts=1000.0)
            self.assertEqual(self.bo._acc, {})
        finally:
            os.environ.pop("BOOK_OFI")


class TestSeriesAndJoin(_Iso):
    def _write_rows(self):
        d = Path(state.STATE_DIR) / "orderflow"
        d.mkdir(parents=True)
        rows = [{"ts": 600, "n": 2, "ofi": 6.0, "ofi_n": 1.0, "gofi": 1.4, "obi": 0.08,
                 "microdev_bp": 1.0, "spread_bp": 9.9, "depth_q": 30.0},
                {"ts": 660, "n": 4, "ofi": -2.0, "ofi_n": -0.5, "gofi": -0.3, "obi": -0.1,
                 "microdev_bp": -2.0, "spread_bp": 10.1, "depth_q": 28.0}]
        (d / "BTCUSDT.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    def test_series_resamples_to_5m(self):
        self._write_rows()
        df = self.bo.series("BTC/USDT:USDT", bar_s=300)      # candidate normalization too
        self.assertEqual(len(df), 1)
        r = df.iloc[0]
        self.assertAlmostEqual(r["of_ofi"], 4.0)             # 6 + (-2) summed into the 5m bar
        self.assertAlmostEqual(r["of_gofi_book"], 1.1)
        self.assertEqual(r["of_book_n"], 6)
        # n-weighted mean obi: (0.08*2 + -0.1*4)/6
        self.assertAlmostEqual(r["of_obi"], (0.08 * 2 - 0.1 * 4) / 6, places=6)

    def test_join_features_splices_book_columns(self):
        self._write_rows()
        import pandas as pd
        from trading.broker_sense import orderflow_store
        feats = pd.DataFrame({"ts": [300, 600, 900], "close": [1.0, 1.1, 1.2]})
        out = orderflow_store.join_features(feats, "BTCUSDT", ts_col="ts")
        for col in ("of_ofi", "of_gofi_book", "of_obi"):
            self.assertIn(col, out.columns)
        self.assertAlmostEqual(float(out.loc[out["ts"] == 600, "of_ofi"].iloc[0]), 4.0)
        # bar before the store began → NaN, never faked
        self.assertTrue(pd.isna(out.loc[out["ts"] == 300, "of_ofi"].iloc[0]))


class TestStoreSnapshotFeatParam(_Iso):
    def test_snapshot_accepts_prefetched_features(self):
        from trading.broker_sense import orderflow_store
        rec = orderflow_store.snapshot("BTCUSDT", "crypto",
                                       feat={"taker_buy_sell_ratio": 1.2,
                                             "crowd_long_pct": 0.6,
                                             "funding_rate": 0.0001})
        self.assertIsNotNone(rec)
        self.assertAlmostEqual(rec["of_taker_ratio"], 1.2)
        store = state.load_json("orderflow_store.json", {})
        self.assertIn("BTCUSDT", store)

    def test_open_interest_key_matches_what_features_emits(self):
        """binance_orderflow.features() emits `open_interest_usd`; the extractor's alias list used
        to look only for `open_interest`/`oi`, so of_oi silently stayed None even with the data
        present (found live 2026-07-16: OI filled for 100 symbols, of_oi still 0%)."""
        from trading.broker_sense import orderflow_store
        rec = orderflow_store.snapshot("ETHUSDT", "crypto",
                                       feat={"open_interest_usd": 4_351_516_252.0,
                                             "funding_rate": 0.0001})
        self.assertEqual(rec["of_oi"], 4_351_516_252.0)


class TestMirrorDepthFeedsBookOfi(_Iso):
    """MOTTO tenet 3 (owner 2026-07-16): book_ofi must be fed from the in-RAM depth stream, not
    only the browser capture. Measured that day: the browser keeps ~6 books fresh at a time
    (median age 25 h vs a 45 s TTL), while this connection pushes 20-level depth for ~120 movers
    every 500 ms — so the research's #1/#2 ranked drivers were computed for almost nothing."""

    def test_apply_depth_frame_folds_into_book_ofi(self):
        from trading.broker_sense import binance_stream, book_ofi
        m = binance_stream.BinanceUniverseMirror()
        seen = []
        with mock.patch.object(book_ofi, "on_book", side_effect=lambda *a, **k: seen.append(a)):
            m._apply_depth_frame({"stream": "btcusdt@depth20@500ms",
                                  "data": {"s": "BTCUSDT",
                                           "b": [["100.0", "5.0"], ["99.0", "7.0"]],
                                           "a": [["101.0", "3.0"], ["102.0", "9.0"]]}})
        self.assertEqual(len(seen), 1, "depth frame must reach book_ofi")
        sym, rec, _ts = seen[0]
        self.assertEqual(sym, "BTCUSDT")
        # the L1 fields are what _fold_event needs for OFI + obi/microprice/spread — a record
        # carrying only bids/asks would silently drop every one of those stats
        self.assertEqual((rec["bid"], rec["bid_qty"]), (100.0, 5.0))
        self.assertEqual((rec["ask"], rec["ask_qty"]), (101.0, 3.0))
        self.assertEqual(len(rec["bids"]), 2)

    def test_depth_frames_fold_real_ofi_into_the_accumulator(self):
        """End-to-end through the REAL accumulator (no mock): two live depth frames must produce
        a true OFI increment, proving the mirror path yields the same numbers the browser path
        does. Asserts on the accumulator rather than a finished bar because _apply_depth_frame
        stamps its own time.time() — the bar cannot be rolled deterministically from here."""
        from trading.broker_sense import binance_stream, book_ofi
        m = binance_stream.BinanceUniverseMirror()
        m._apply_depth_frame({"stream": "ethusdt@depth20@500ms",
                              "data": {"s": "ETHUSDT", "b": [["100.0", "5.0"]],
                                       "a": [["101.0", "3.0"]]}})
        # bid size grows at the same price → positive L1 OFI (buy pressure)
        m._apply_depth_frame({"stream": "ethusdt@depth20@500ms",
                              "data": {"s": "ETHUSDT", "b": [["100.0", "9.0"]],
                                       "a": [["101.0", "3.0"]]}})
        acc = book_ofi._acc.get("ETHUSDT")
        self.assertIsNotNone(acc, "mirror depth frames must reach the book_ofi accumulator")
        self.assertEqual(acc["n"], 2)
        self.assertAlmostEqual(acc["ofi_l"][0], 4.0)     # +4 bid qty at an unchanged best bid
        self.assertNotEqual(acc["obi_sum"], 0.0)         # L1 stats populated (needs bid/ask/qty)


if __name__ == "__main__":
    unittest.main()
