"""Tests for trading/direction/ope.py (E1 — counterfactual replay over the vote log)."""
from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        os.environ.pop("OPE_HORIZONS", None)

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _write_votes(self, rows):
        from trading.direction.vote_log import _path
        with open(_path(), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")


def _vote_row(ts, symbol="AKEUSDT", decided="long", votes=None):
    return {"ts": ts, "symbol": symbol, "market": "CRYPTO", "segment": "futures",
            "regime": "trend_up", "lane": "breadth",
            "votes": votes or {"lens_a": 0.7, "lens_b": 0.6}, "decided": decided}


class TestLabelVotes(_Base):
    def test_labels_matured_rows_and_advances_cursor(self):
        from trading.direction import ope
        old = time.time() - 7200                      # both 15m and 1h matured
        fresh = time.time() - 60                      # nothing matured
        self._write_votes([_vote_row(old), _vote_row(fresh)])
        prices = {old: 100.0, old + 900: 101.0, old + 3600: 99.0}

        def fake_price(sym, mkt, seg, epoch):
            return prices.get(epoch)
        with mock.patch.object(ope, "_price", side_effect=fake_price):
            out = ope.label_votes()
        self.assertEqual(out["labeled"], 1)
        rows = [json.loads(l) for l in open(ope._labeled_path())]
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["outcomes"]["15m"]["sign"], 1)     # 100 → 101
        self.assertEqual(rows[0]["outcomes"]["1h"]["sign"], -1)     # 100 → 99
        # second run: cursor advanced, nothing new matured
        with mock.patch.object(ope, "_price", side_effect=fake_price):
            out2 = ope.label_votes()
        self.assertEqual(out2["labeled"], 0)

    def test_unresolvable_row_counts_skipped_never_blocks(self):
        from trading.direction import ope
        old = time.time() - 7200
        self._write_votes([_vote_row(old), _vote_row(old + 1)])
        calls = {"n": 0}

        def fake_price(sym, mkt, seg, epoch):
            calls["n"] += 1
            return None if epoch < old + 1 else 100.0    # first row's ref unresolvable
        with mock.patch.object(ope, "_price", side_effect=fake_price):
            out = ope.label_votes()
        self.assertEqual(out["skipped"], 1)
        self.assertEqual(out["labeled"], 1)


class TestEvaluate(_Base):
    def _write_labeled(self, n=40):
        from trading.direction import ope
        rows = []
        for i in range(n):
            up = i % 2 == 0
            rows.append({"ts": 1_000_000 + i, "symbol": "AKEUSDT", "market": "CRYPTO",
                         "segment": "futures", "regime": "trend_up", "lane": "breadth",
                         "decided": "long" if up else "short",
                         "votes": {"lens_a": 0.8 if up else 0.2},
                         "ref": 100.0,
                         "outcomes": {"15m": {"sign": 1 if up else -1,
                                              "move_pct": 0.5 if up else -0.5},
                                      "1h": {"sign": 1 if up else -1,
                                             "move_pct": 1.0 if up else -1.0}}})
        with open(ope._labeled_path(), "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r) + "\n")

    def test_logged_candidate_scores_perfectly_on_agreeing_tape(self):
        from trading.direction import ope
        self._write_labeled()
        rep = ope.evaluate()
        logged = next(c for c in rep["candidates"] if c["name"] == "logged")
        m = logged["metrics"]["1h"]
        self.assertEqual(m["acted"], 40)
        self.assertEqual(m["hit_rate"], 1.0)
        self.assertGreater(m["capture_pct_sum"], 39.9)

    def test_env_restored_after_evaluate(self):
        from trading.direction import ope
        self._write_labeled(4)
        os.environ["LEARNED_DIR_BAND"] = "0.02"
        try:
            ope.evaluate()
            self.assertEqual(os.environ.get("LEARNED_DIR_BAND"), "0.02")
        finally:
            os.environ.pop("LEARNED_DIR_BAND", None)

    def test_no_rows_is_honest(self):
        from trading.direction import ope
        self.assertIn("error", ope.evaluate())

    def test_report_written_and_status_reads_it(self):
        from trading.direction import ope
        self._write_labeled(10)
        ope.evaluate()
        st = ope.status()
        self.assertEqual(st["n_rows"], 10)
        self.assertIsNotNone(st["best_candidate"])


class TestMaybeRun(_Base):
    def test_disabled_flag(self):
        from trading.direction import ope
        os.environ["OPE_ENABLED"] = "0"
        try:
            self.assertIsNone(ope.maybe_run())
        finally:
            os.environ.pop("OPE_ENABLED", None)

    def test_spawns_subprocess_not_inline(self):
        from trading.direction import ope
        self._write_votes([])
        with mock.patch.object(ope.subprocess, "Popen") as pop, \
             mock.patch.object(ope, "label_votes",
                               return_value={"labeled": 3, "skipped": 0}):
            Path(ope._labeled_path()).write_text("{}\n")
            out = ope.maybe_run()
        self.assertEqual(out.get("evaluate"), "spawned")
        self.assertTrue(pop.called)
        argv = pop.call_args[0][0]
        self.assertIn("--evaluate", argv)


if __name__ == "__main__":
    unittest.main()
