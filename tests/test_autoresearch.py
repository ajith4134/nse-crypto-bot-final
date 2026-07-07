"""Tests for trading/strategy/autoresearch.py — the live autoresearch driver (#5).

State-isolated (monkeypatched STATE_DIR); breed() is stubbed per test so no test spends
minutes inside DEAP — run_cycle's own logic (data sourcing, honest skips, accounting,
W7 track-record wiring) is what's under test. The ui_data rows snapshot/hydration added
for the driver is covered too.
"""
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import trading.state as tstate


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()


def _rows(n=120, base=100.0):
    t0 = int(time.time() * 1000) - n * 900_000
    out = []
    px = base
    for i in range(n):
        px = px * (1.0 + (0.001 if i % 3 else -0.0012))
        out.append([t0 + i * 900_000, px, px * 1.002, px * 0.998, px * 1.001, 10.0 + i])
    return out


class TestRunCycle(_IsolatedState):
    def test_honest_skip_when_no_data(self):
        from trading.strategy import autoresearch
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=None):
            rec = autoresearch.run_cycle()
        self.assertIn("skipped", rec["result"])
        self.assertEqual(rec["admitted"], 0)
        d = tstate.load_json("autoresearch.json", {})
        self.assertEqual(d["cycles"], 1)
        self.assertEqual(d["totals"]["skipped_markets"], 1)
        for m in rec["markets"].values():          # every market records WHY it skipped
            self.assertIn("insufficient", m["data"])

    def test_cycle_runs_breed_and_accounts(self):
        from trading.strategy import autoresearch
        breed_res = {"ran": True, "gated": False, "admitted_total": 3,
                     "markets": {"CRYPTO": {"evaluated": 14, "admitted": 2}},
                     "portfolio": {"generators": ["optuna_tune"],
                                   "markets": {"CRYPTO": {"optuna_tune":
                                                          {"tested": 8, "admitted": 1}}}}}
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv",
                        return_value=_rows()), \
             mock.patch("trading.strategy.evolved_link.breed",
                        return_value=breed_res) as mb:
            rec = autoresearch.run_cycle()
        self.assertEqual(rec["result"], "ok")
        self.assertEqual(rec["admitted"], 3)       # breed's own admitted_total
        self.assertEqual(rec["tested"], 22)        # 14 DEAP evaluated + 8 portfolio
        (args, kwargs) = mb.call_args
        self.assertIn("CRYPTO", args[0])           # real frame reached breed()
        self.assertGreaterEqual(len(args[0]["CRYPTO"]), 60)
        self.assertEqual(kwargs.get("seed"), 1)    # deterministic per-cycle seed
        # W7: track record + meta-article queue got the cycle
        tr = tstate.load_json("track_records.json", {})
        self.assertEqual(tr.get("autoresearch", {}).get("runs"), 1)
        self.assertTrue(tstate.load_json("meta_articles.json", []))

    def test_gated_recorded_honestly(self):
        from trading.strategy import autoresearch
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv",
                        return_value=_rows()), \
             mock.patch("trading.strategy.evolved_link.breed",
                        return_value={"ran": False, "gated": True}):
            rec = autoresearch.run_cycle()
        self.assertIn("gated", rec["result"])

    def test_breed_exception_never_raises(self):
        from trading.strategy import autoresearch
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv",
                        return_value=_rows()), \
             mock.patch("trading.strategy.evolved_link.breed",
                        side_effect=RuntimeError("boom")):
            rec = autoresearch.run_cycle()
        self.assertIn("error", rec["result"])
        d = tstate.load_json("autoresearch.json", {})
        self.assertEqual(d["totals"]["errors"], 1)

    def test_symbol_rotation_and_history_bound(self):
        from trading.strategy import autoresearch
        seen = []
        def _ohlcv(symbol, market, timeframe="15m", limit=500):
            if market == "crypto":
                seen.append(symbol)
            return None
        with mock.patch.dict(os.environ,
                             {"AUTORESEARCH_SYMBOLS_CRYPTO": "A/USDT,B/USDT"}), \
             mock.patch("trading.broker_sense.data_failsafe.ohlcv", side_effect=_ohlcv):
            for _ in range(3):
                autoresearch.run_cycle()
        self.assertEqual(seen, ["B/USDT", "A/USDT", "B/USDT"])   # cycle % len rotation
        d = tstate.load_json("autoresearch.json", {})
        self.assertEqual(len(d["history"]), 3)


class TestStatus(_IsolatedState):
    def test_status_reads_real_state(self):
        from trading.strategy import autoresearch
        tstate.save_json("champion_lineage.json",
                         {"CRYPTO": {"generation": 4, "champion": {"id": "x", "dsr": 0.7},
                                     "history": []}})
        tstate.save_json("leak_tripwire.json", [{"id": "cheater", "oos_sharpe": 12.0}])
        st = autoresearch.status()
        self.assertEqual(st["champion_lineage"]["CRYPTO"]["champion"]["id"], "x")
        self.assertEqual(st["leak_tripwire"][-1]["id"], "cheater")
        self.assertFalse(st["driver"]["live"])     # no cycle ran → honestly not live
        with mock.patch("trading.broker_sense.data_failsafe.ohlcv", return_value=None):
            autoresearch.run_cycle()
        self.assertTrue(autoresearch.status()["driver"]["live"])


class TestUiDataSnapshot(_IsolatedState):
    def _cold(self):
        """Patch context for a cold, never-fed process (isolated globals restored after)."""
        from trading.broker_sense import ui_data
        return (mock.patch.dict(ui_data._STORE, {}, clear=True),
                mock.patch.dict(ui_data._HITS,
                                {"served": 0, "missed": 0, "fed": 0}, clear=True),
                mock.patch.object(ui_data, "_last_hydrate", 0.0),
                mock.patch.object(ui_data, "_last_snap", 0.0),
                mock.patch.object(ui_data, "_last_rows_snap", 0.0))

    def test_rows_snapshot_and_cold_hydration(self):
        from trading.broker_sense import ui_data
        key = "BTCUSDT|15m"
        ui_data._write_rows_snapshot(
            {key: {"ts": time.time(), "url": "u", "broker": "binance",
                   "rows": _rows(50)}})
        self.assertIn(key, tstate.load_json("ui_candles.json", {}).get("rows", {}))
        p1, p2, p3, p4, p5 = self._cold()
        with p1, p2, p3, p4, p5:
            got = ui_data.ui_ohlcv("BTC/USDT", timeframe="15m", limit=10)
            self.assertIsNotNone(got)
            self.assertEqual(len(got), 10)

    def test_snapshot_merge_never_clobbers_older_keys(self):
        # a cold funnel restart writing ONE key must not drop the previous run's keys
        from trading.broker_sense import ui_data
        now = time.time()
        ui_data._write_rows_snapshot(
            {"ETHUSDT|15m": {"ts": now - 30, "rows": _rows(40)}})
        ui_data._write_rows_snapshot(
            {"BTCUSDT|15m": {"ts": now, "rows": _rows(40)}})
        rows = tstate.load_json("ui_candles.json", {}).get("rows", {})
        self.assertIn("ETHUSDT|15m", rows)         # survived the second write
        self.assertIn("BTCUSDT|15m", rows)

    def test_rehydration_picks_up_newer_snapshot(self):
        # hydrate-once would freeze the store; re-hydration must see NEWER rows
        from trading.broker_sense import ui_data
        p1, p2, p3, p4, p5 = self._cold()
        with p1, p2, p3, p4, p5:
            ui_data._write_rows_snapshot(
                {"SOLUSDT|15m": {"ts": time.time() - 10, "rows": _rows(30)}})
            self.assertIsNotNone(ui_data.ui_ohlcv("SOL/USDT", timeframe="15m"))
            newer = _rows(45)
            ui_data._write_rows_snapshot(
                {"SOLUSDT|15m": {"ts": time.time(), "rows": newer}})
            ui_data._last_hydrate = 0.0            # cadence elapsed
            got = ui_data.ui_ohlcv("SOL/USDT", timeframe="15m", limit=100)
            self.assertEqual(len(got), 45)         # served the refreshed rows

    def test_stale_snapshot_is_honest_none(self):
        from trading.broker_sense import ui_data
        tstate.save_json("ui_candles.json",
                         {"saved_ts": time.time(),
                          "rows": {"OLDUSDT|15m": {"ts": time.time() - 90000,
                                                   "rows": _rows(30)}}})
        p1, p2, p3, p4, p5 = self._cold()
        with p1, p2, p3, p4, p5:
            self.assertIsNone(ui_data.ui_ohlcv("OLD/USDT", timeframe="15m"))

    def test_feeding_process_never_hydrates(self):
        from trading.broker_sense import ui_data
        ui_data._write_rows_snapshot(
            {"XRPUSDT|15m": {"ts": time.time(), "rows": _rows(30)}})
        p1, p2, p3, p4, p5 = self._cold()
        with p1, p2, p3, p4, p5:
            ui_data._HITS["fed"] = 1               # this process's captures are truth
            self.assertIsNone(ui_data.ui_ohlcv("XRP/USDT", timeframe="15m"))


if __name__ == "__main__":
    unittest.main()
