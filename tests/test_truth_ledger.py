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

    def test_backfill_accepts_preloaded_journal(self):
        # the live-loop ingest seam passes its already-loaded TradeJournal (2026-07-16
        # fix: backfill had no production caller and the exit horizon froze for 5 days)
        entry_iso = __import__("datetime").datetime.fromtimestamp(
            int(time.time()) - 3600, tz=__import__("datetime").timezone.utc).isoformat()
        state.save_json("journal.json", [
            {"symbol": "ETH/USDT:USDT", "direction": "LONG", "entry_price": 10.0,
             "exit_price": 11.0, "entry_datetime": entry_iso,
             "exit_datetime": entry_iso, "quantity": 1, "exchange": "binance",
             "decision_snapshot": {"strategy": "s1", "segment": "futures",
                                   "regime": "trend"}},
        ])
        from trading.journal.journal import TradeJournal
        rep = self.tl.backfill_journal(journal=TradeJournal())
        self.assertEqual(rep["scanned"], 1)
        rows = {(r["source"], r["horizon"]): r for r in self.tl.hit_rates()}
        self.assertEqual(rows[("s1", "exit")]["correct"], 1)   # exited higher, LONG

    def test_backfill_concurrent_caller_returns_locked(self):
        import fcntl
        lock_p = Path(state.STATE_DIR) / "direction_truth_backfill.lock"
        lock_p.parent.mkdir(parents=True, exist_ok=True)
        holder = open(lock_p, "w")
        try:
            fcntl.flock(holder, fcntl.LOCK_EX)
            rep = self.tl.backfill_journal()
            self.assertTrue(rep.get("locked"))
            self.assertEqual(rep["scanned"], 0)
        finally:
            fcntl.flock(holder, fcntl.LOCK_UN)
            holder.close()


if __name__ == "__main__":
    unittest.main()


class TestMethodAccuracyIsAuditable(_Iso):
    """The ledger counted HOW it resolved each label but discarded the OUTCOME — so it could not
    audit its own measurement quality. That mattered: only ~15% of 174k labels came from real candle
    feathers; 36% from mirror MARK price and 44% from timing-sensitive probes. Re-resolving from
    feathers alone gave 1h acc 0.5149 (+2.4σ) vs the mixed ledger's 0.4952 — the 'coin flip'
    headline was partly a measurement artifact (2026-07-16)."""

    def test_fold_records_accuracy_per_method_and_horizon(self):
        agg = {}
        row = {"source": "s1", "market": "CRYPTO", "regime": "any", "segment": "futures",
               "direction": "LONG", "taken": True}
        self.tl._fold(agg, row, "1h", True, "feather:perp")
        self.tl._fold(agg, row, "1h", False, "feather:perp")
        self.tl._fold(agg, row, "1h", False, "probe:ui:capture")
        ma = agg["method_acc"]
        self.assertEqual(ma["feather:perp|1h"], {"n": 2, "correct": 1})
        self.assertEqual(ma["probe:ui:capture|1h"], {"n": 1, "correct": 0})

    def test_method_acc_splits_by_horizon(self):
        agg = {}
        row = {"source": "s1", "market": "CRYPTO", "regime": "any", "segment": "futures",
               "direction": "SHORT", "taken": False}
        self.tl._fold(agg, row, "15m", True, "feather:perp")
        self.tl._fold(agg, row, "4h", True, "feather:perp")
        self.assertIn("feather:perp|15m", agg["method_acc"])
        self.assertIn("feather:perp|4h", agg["method_acc"])

    def test_bucket_key_is_UNCHANGED_so_readers_do_not_break(self):
        agg = {}
        row = {"source": "s1", "market": "CRYPTO", "regime": "any", "segment": "futures",
               "direction": "LONG", "taken": True}
        self.tl._fold(agg, row, "1h", True, "feather:perp")
        # 4 fields only — hit_rates() and the dashboards parse this shape
        k = next(iter(agg["buckets"]))
        self.assertEqual(len(k.split("|")), 4, "bucket key must stay source|market|regime|horizon")
        self.assertEqual(agg["methods"]["feather:perp"], 1)   # the old tally still works


class TestExitReasonHasItsOwnField(unittest.TestCase):
    """exit_reason was stuffed into `setup_type` — the ENTRY setup field
    (Breakout/Reversal/Momentum/Scalp/Swing/Hedge). One field, two meanings, last writer wins:
    live rows showed a MIX of force_exit/tailgate_lock (exit reasons) AND Momentum (a real setup).
    Measured 2026-07-16: 84% of exits were OUR OWN logic (36 force_exit + 18 tailgate_lock) vs only
    3 stop_loss — the brain cuts trades, price rarely kills them. Invisible without this field."""

    def test_schema_has_exit_reason(self):
        from trading.journal.schema import ClosedTrade
        t = ClosedTrade()
        self.assertTrue(hasattr(t, "exit_reason"))
        self.assertEqual(t.exit_reason, "")

    def test_exit_reason_survives_roundtrip(self):
        from trading.journal.schema import ClosedTrade
        t = ClosedTrade()
        t.exit_reason = "tailgate_lock"
        d = t.to_dict()
        self.assertEqual(d.get("exit_reason"), "tailgate_lock")
        self.assertEqual(ClosedTrade.from_dict(d).exit_reason, "tailgate_lock")

    def test_setup_type_still_populated_for_existing_readers(self):
        # live_loop:1748 and the dashboards still read setup_type AS the exit reason; do not
        # break them while the new field lands
        from trading.journal.schema import ClosedTrade
        t = ClosedTrade()
        t.setup_type = "force_exit"
        self.assertEqual(ClosedTrade.from_dict(t.to_dict()).setup_type, "force_exit")
