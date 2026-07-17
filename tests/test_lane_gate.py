"""Tests for trading/execution/lane_gate.py — kill-criteria parity + freshness gate at
the place_order chokepoint (SELECTION-CRITIQUE 2026-07-17)."""
from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state


def _mkdb(path, rows):
    """rows: (enter_tag, profit_abs, days_ago)"""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, enter_tag TEXT, "
                "is_open INT, close_profit_abs REAL, open_date TEXT)")
    for i, (tag, pnl, days) in enumerate(rows):
        con.execute("INSERT INTO trades VALUES (?,?,0,?,datetime('now', ?))",
                    (i, tag, pnl, f"-{days} days"))
    con.commit()
    con.close()


class _Iso(unittest.TestCase):
    def setUp(self):
        from trading.execution import lane_gate as lg
        self.lg = lg
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self.db = os.path.join(self._t.name, "trades.sqlite")
        os.environ["LANE_GATE_DB"] = self.db
        os.environ.pop("LANE_KILL", None)
        os.environ.pop("FRESH_GATE", None)
        with lg._lock:                      # cold cache per test
            lg._cache["ts"] = 0.0
            lg._cache["stats"] = {}

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()
        for k in ("LANE_GATE_DB", "LANE_KILL", "FRESH_GATE", "LANE_KILL_MIN_N"):
            os.environ.pop(k, None)


class TestKillCriteria(_Iso):
    def test_negative_lane_with_enough_n_is_retired(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120 + [("good_lane", +1.0, 1)] * 120)
        dead, why = self.lg.killed("bad_lane")
        self.assertTrue(dead)
        self.assertIn("retired", why)
        self.assertEqual(self.lg.killed("good_lane"), (False, ""))

    def test_small_n_lane_keeps_trading(self):
        _mkdb(self.db, [("young_lane", -1.0, 1)] * 50)
        self.assertEqual(self.lg.killed("young_lane"), (False, ""))

    def test_exempt_control_lane_never_dies(self):
        _mkdb(self.db, [("learned_direction_ctl", -1.0, 1)] * 200)
        self.assertEqual(self.lg.killed("learned_direction_ctl"), (False, ""))

    def test_old_trades_outside_window_do_not_count(self):
        _mkdb(self.db, [("was_bad", -1.0, 30)] * 200)   # all older than the 14d window
        self.assertEqual(self.lg.killed("was_bad"), (False, ""))

    def test_missing_db_fails_open(self):
        os.environ["LANE_GATE_DB"] = "/nonexistent/nope.sqlite"
        self.assertEqual(self.lg.killed("anything"), (False, ""))

    def test_check_records_refusal_counter(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        ok, guard, why = self.lg.check("bad_lane", "AKE/USDT:USDT", "LONG", "futures")
        self.assertFalse(ok)
        self.assertEqual(guard, "lane_kill")
        st = state.load_json("lane_gate.json", {})
        self.assertEqual(st["killed"]["bad_lane"], 1)


class TestFreshnessGate(_Iso):
    def test_momentum_tag_refused_when_stale_and_claim_recorded(self):
        _mkdb(self.db, [])
        recorded = []
        with mock.patch("trading.broker_sense.inception.fresh_ok",
                        return_value=(False, "stale momentum: 4h +8.0% but last hour +0.1%")), \
             mock.patch("trading.direction.truth_ledger.record",
                        side_effect=lambda **kw: recorded.append(kw)):
            ok, guard, why = self.lg.check("filter:momentum", "AKE/USDT:USDT",
                                           "LONG", "futures")
        self.assertFalse(ok)
        self.assertEqual(guard, "freshness")
        self.assertEqual(len(recorded), 1)
        self.assertEqual(recorded[0]["source"], "freshcut")
        self.assertFalse(recorded[0]["taken"])

    def test_non_momentum_tag_skips_freshness(self):
        _mkdb(self.db, [])
        with mock.patch("trading.broker_sense.inception.fresh_ok") as fo:
            ok, guard, _ = self.lg.check("lens:debate", "AKE/USDT:USDT",
                                         "SHORT", "futures")
        self.assertTrue(ok)
        fo.assert_not_called()

    def test_fresh_momentum_tag_passes(self):
        _mkdb(self.db, [])
        with mock.patch("trading.broker_sense.inception.fresh_ok",
                        return_value=(True, "fresh enough")):
            ok, guard, _ = self.lg.check("mom_trix", "AKE/USDT:USDT", "LONG", "futures")
        self.assertTrue(ok)
        self.assertEqual(guard, "")


class TestStatus(_Iso):
    def test_status_reports_retired_and_counters(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        self.lg.check("bad_lane", "A/USDT:USDT", "LONG", "futures")
        st = self.lg.status()
        self.assertIn("bad_lane", st["retired"])
        self.assertEqual(st["refusals"]["killed"]["bad_lane"], 1)
        self.assertIn("learned_direction_ctl", st["exempt"])


class TestPlaceOrderWiring(_Iso):
    """The gate must fire at the ONE chokepoint — place_order — before any transport."""

    def _ec(self):
        from trading.crypto.engine_client import CryptoEngineClient
        ec = CryptoEngineClient.__new__(CryptoEngineClient)
        ec._guard_live = lambda *a, **k: None
        return ec

    def test_killed_tag_refused_before_any_transport(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        ec = self._ec()
        cli = mock.Mock()
        with mock.patch.object(ec, "_client", return_value=cli), \
             mock.patch.object(ec, "_pair_tradeable", return_value=True):
            res = ec.place_order(symbol="AKE/USDT:USDT", action="BUY",
                                 enter_tag="bad_lane", segment="futures")
        self.assertFalse(res["ok"])
        self.assertEqual(res["guard"], "lane_kill")
        cli.forceenter.assert_not_called()

    def test_exits_never_gated(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        ec = self._ec()
        cli = mock.Mock()
        cli.forceexit.return_value = {"result": "ok"}
        with mock.patch.object(ec, "_client", return_value=cli), \
             mock.patch.object(ec, "_check", side_effect=lambda r, _: r):
            res = ec.place_order(symbol="AKE/USDT:USDT", action="EXIT",
                                 trade_id="7", segment="futures")
        cli.forceexit.assert_called_once()


class TestPhaseConditioner(_Iso):
    def test_phase_lands_in_current_conditioners(self):
        from trading.direction import truth_ledger as tl
        with mock.patch("trading.broker_sense.inception.phase", return_value="stale"):
            out = tl.current_conditioners("AKE/USDT", "CRYPTO")
        self.assertEqual(out.get("phase"), "stale")

    def test_phase_absent_when_mirror_cold_and_nse_untouched(self):
        from trading.direction import truth_ledger as tl
        with mock.patch("trading.broker_sense.inception.phase", return_value=None):
            out = tl.current_conditioners("AKE/USDT", "CRYPTO")
        self.assertNotIn("phase", out)
        with mock.patch("trading.broker_sense.inception.phase") as ph:
            tl.current_conditioners("RELIANCE", "NSE")
        ph.assert_not_called()


if __name__ == "__main__":
    unittest.main()
