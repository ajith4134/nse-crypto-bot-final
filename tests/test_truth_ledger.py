"""Tests for trading/direction/truth_ledger — D1 of the Direction Accuracy Program."""
import json
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


def _write_feather(root: Path, rel: str, t0: int, closes: list[float]) -> None:
    import pandas as pd
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame({
        "date": pd.to_datetime([(t0 + i * 300) * 10**9 for i in range(len(closes))],
                               utc=True),
        "close": closes})
    df.to_feather(p)


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self._candles = tempfile.TemporaryDirectory()
        import os
        os.environ["DIRECTION_CANDLE_DIR"] = self._candles.name
        from trading.direction import truth_ledger as tl
        tl._CANDLE_CACHE.clear()
        self.tl = tl

    def tearDown(self):
        import os
        state.STATE_DIR = self._o
        os.environ.pop("DIRECTION_CANDLE_DIR", None)
        self._t.cleanup()
        self._candles.cleanup()


class TestRecord(_Iso):
    def test_record_appends_and_normalizes(self):
        ok = self.tl.record(symbol="ETH/USDT:USDT", market="crypto", segment="futures",
                            direction="CE", source="fusion", regime="trend",
                            ref_price=100.0)
        self.assertTrue(ok)
        rows = [json.loads(x) for x in
                (Path(state.STATE_DIR) / "direction_truth_pending.jsonl")
                .read_text().splitlines()]
        self.assertEqual(rows[0]["direction"], "LONG")     # CE → LONG
        self.assertEqual(rows[0]["market"], "CRYPTO")

    def test_neutral_and_sourceless_rejected(self):
        self.assertFalse(self.tl.record(symbol="X/USDT", market="crypto",
                                        segment="spot", direction="neutral",
                                        source="s", regime="r"))
        self.assertFalse(self.tl.record(symbol="X/USDT", market="crypto",
                                        segment="spot", direction="LONG",
                                        source="", regime="r"))

    def test_kill_switch(self):
        import os
        os.environ["DIRECTION_TRUTH"] = "0"
        try:
            self.assertFalse(self.tl.record(symbol="X/USDT", market="crypto",
                                            segment="spot", direction="LONG",
                                            source="s", regime="r"))
        finally:
            os.environ.pop("DIRECTION_TRUTH")


class TestTickLabeling(_Iso):
    def test_tick_labels_from_feather_and_aggregates(self):
        # candles rise 100 → 160 over 5h; decision 4.5h ago at 100
        t0 = int(time.time()) - int(4.5 * 3600)
        closes = [100.0 + i for i in range(60)]
        _write_feather(Path(self._candles.name),
                       "futures/ETH_USDT_USDT-5m-futures.feather", t0, closes)
        self.tl.record(symbol="ETH/USDT:USDT", market="CRYPTO", segment="futures",
                       direction="LONG", source="fusion", regime="trend",
                       ts=float(t0 + 300), ref_price=101.0)
        self.tl.record(symbol="ETH/USDT:USDT", market="CRYPTO", segment="futures",
                       direction="SHORT", source="contra", regime="trend",
                       ts=float(t0 + 300), ref_price=101.0)
        rep = self.tl.tick(budget_s=10)
        self.assertEqual(rep["resolved"], 6)               # 2 rows × 3 horizons
        self.assertEqual(rep["still_pending"], 0)
        rates = {(r["source"], r["horizon"]): r for r in self.tl.hit_rates()}
        self.assertEqual(rates[("fusion", "1h")]["correct"], 1)   # rising → LONG right
        self.assertEqual(rates[("contra", "1h")]["correct"], 0)   # rising → SHORT wrong
        # pending file drained
        rep2 = self.tl.tick(budget_s=10)
        self.assertEqual(rep2["resolved"], 0)

    def test_not_due_stays_pending(self):
        self.tl.record(symbol="ETH/USDT:USDT", market="CRYPTO", segment="futures",
                       direction="LONG", source="fusion", regime="trend",
                       ts=time.time(), ref_price=1.0)
        rep = self.tl.tick(budget_s=10)
        self.assertEqual(rep["resolved"], 0)
        self.assertEqual(rep["still_pending"], 1)

    def test_no_feather_no_probe_expires_honestly(self):
        # NSE symbol, no data source, decision far in the past → expires as no_data
        self.tl.record(symbol="NSE:XYZ", market="NSE", segment="options",
                       direction="LONG", source="picker", regime="chop",
                       ts=time.time() - 20 * 3600, ref_price=50.0)
        rep = self.tl.tick(budget_s=10)
        self.assertEqual(rep["resolved"], 0)
        self.assertEqual(rep["still_pending"], 0)          # gone from pending
        self.assertEqual(self.tl.hit_rates(), [])          # and never faked a label


class TestWilson(_Iso):
    def test_wilson_small_n_stays_wide(self):
        rate, lo, hi = self.tl._wilson(3, 4)
        self.assertAlmostEqual(rate, 0.75)
        self.assertLess(lo, 0.45)                          # 3/4 is NOT proof of edge
        rate2, lo2, _ = self.tl._wilson(75, 100)
        self.assertGreater(lo2, 0.65)                      # 75/100 is


class TestBackfill(_Iso):
    def test_backfill_labels_exit_sign_and_is_idempotent(self):
        t0 = int(time.time()) - 6 * 3600
        _write_feather(Path(self._candles.name),
                       "futures/BTC_USDT_USDT-5m-futures.feather", t0,
                       [100.0 + i for i in range(70)])
        entry_iso = __import__("datetime").datetime.fromtimestamp(
            t0 + 300, tz=__import__("datetime").timezone.utc).isoformat()
        state.save_json("journal.json", [
            {"symbol": "BTC/USDT:USDT", "direction": "LONG", "entry_price": 101.0,
             "exit_price": 99.0, "entry_datetime": entry_iso,
             "exit_datetime": entry_iso, "quantity": 1, "exchange": "binance",
             "decision_snapshot": {"strategy": "trend_tema", "segment": "futures",
                                   "regime": "trend"}},
            {"symbol": "BTC/USDT:USDT", "direction": "SHORT", "entry_price": 101.0,
             "exit_price": 99.0, "entry_datetime": entry_iso,
             "exit_datetime": entry_iso, "quantity": 1, "exchange": "binance",
             "decision_snapshot": {"strategy": "meanrev_rsi", "segment": "futures",
                                   "regime": "trend"}},
        ])
        rep = self.tl.backfill_journal()
        self.assertEqual(rep["scanned"], 2)
        # each row: 1 exit label + 3 feather horizons
        self.assertEqual(rep["labeled"], 8)
        rows = {(r["source"], r["horizon"]): r for r in self.tl.hit_rates()}
        self.assertEqual(rows[("trend_tema", "exit")]["correct"], 0)   # exited lower
        self.assertEqual(rows[("meanrev_rsi", "exit")]["correct"], 1)
        self.assertEqual(rows[("trend_tema", "1h")]["correct"], 1)     # price ROSE at 1h
        rep2 = self.tl.backfill_journal()                  # idempotent
        self.assertEqual(rep2["skipped_seen"], 2)
        self.assertEqual(rep2["labeled"], 0)

    def test_status_shape(self):
        s = self.tl.status()
        for k in ("enabled", "pending", "rollups", "worst_sources", "honest_note"):
            self.assertIn(k, s)


if __name__ == "__main__":
    unittest.main()
