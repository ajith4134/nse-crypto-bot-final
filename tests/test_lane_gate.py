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


# every gate knob that lives in the prod .env — cleared per test so only the guard under
# test can fire (each test class re-enables exactly the one it exercises)
_GATE_KNOBS = ("X11_MIN_RANGE_PCT", "X16_MIN_DOLLAR_VOL_M", "X17_COUNTER_TREND_PCT",
               "X17_NEUTRAL_PCT", "X17_TREND_DAYS", "STOP_REENTRY_COOLDOWN_MIN")


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
        # The prod ~/.env (pulled in by the config import chain) carries the live gate
        # knobs — X11/X16/X17 are all ON in production. These tests pin per-guard
        # behavior, so every gate not under test must start DISABLED or an unrelated
        # guard fires first and the assertion reads the wrong refusal (seen live:
        # "illiquid" != "freshness"). Same leak pattern as tests/test_profit_tailgate.py.
        self._saved_knobs = {}
        for k in _GATE_KNOBS:
            self._saved_knobs[k] = os.environ.pop(k, None)
        with lg._lock:                      # cold cache per test
            lg._cache["ts"] = 0.0
            lg._cache["stats"] = {}

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()
        for k in ("LANE_GATE_DB", "LANE_KILL", "FRESH_GATE", "LANE_KILL_MIN_N"):
            os.environ.pop(k, None)
        for k in _GATE_KNOBS:               # restore prod values for anything after us
            os.environ.pop(k, None)
            v = getattr(self, "_saved_knobs", {}).get(k)
            if v is not None:
                os.environ[k] = v


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

    def test_core_lanes_and_lens_prefix_never_die(self):
        """Review fix: killing the PRIMARY lanes (learned_direction / live_loop) would
        silently stop most trading and starve the ledger; lens:* has its own verdicts."""
        _mkdb(self.db, [("learned_direction", -2.0, 1)] * 150
              + [("live_loop", -2.0, 1)] * 150 + [("lens:debate", -2.0, 1)] * 150)
        for tag in ("learned_direction", "live_loop", "lens:debate"):
            self.assertEqual(self.lg.killed(tag), (False, ""), tag)

    def test_tiny_loss_lane_survives_hysteresis(self):
        """Review fix: −$12 over 120 trades is break-even noise, not a kill."""
        _mkdb(self.db, [("meh_lane", -0.1, 1)] * 120)
        self.assertEqual(self.lg.killed("meh_lane"), (False, ""))

    def test_killed_lane_gets_parole_once_per_window(self):
        """Live-verification fix: a retired lane earns ONE probation entry per
        LANE_KILL_PROBATION_H so it can redeem itself — then is refused again."""
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        ok1, g1, why1 = self.lg.check("bad_lane", "A/USDT:USDT", "LONG", "futures")
        self.assertTrue(ok1)
        self.assertIn("parole", why1)
        ok2, g2, _ = self.lg.check("bad_lane", "A/USDT:USDT", "LONG", "futures")
        self.assertFalse(ok2)
        self.assertEqual(g2, "lane_kill")
        st = state.load_json("lane_gate.json", {})
        self.assertEqual(st["parole"]["bad_lane"], 1)
        self.assertEqual(st["killed"]["bad_lane"], 1)
        os.environ["LANE_KILL_PROBATION_H"] = "0"     # 0 disables parole
        try:
            with self.lg._lock:
                pass
            state.save_json("lane_gate.json", {})
            ok3, g3, _ = self.lg.check("bad_lane", "A/USDT:USDT", "LONG", "futures")
            self.assertFalse(ok3)
        finally:
            os.environ.pop("LANE_KILL_PROBATION_H", None)

    def test_old_trades_outside_window_do_not_count(self):
        _mkdb(self.db, [("was_bad", -1.0, 30)] * 200)   # all older than the 14d window
        self.assertEqual(self.lg.killed("was_bad"), (False, ""))

    def test_missing_db_fails_open(self):
        os.environ["LANE_GATE_DB"] = "/nonexistent/nope.sqlite"
        self.assertEqual(self.lg.killed("anything"), (False, ""))

    def test_check_records_refusal_counter(self):
        _mkdb(self.db, [("bad_lane", -1.0, 1)] * 120)
        os.environ["LANE_KILL_PROBATION_H"] = "0"     # isolate the kill path from parole
        try:
            ok, guard, why = self.lg.check("bad_lane", "AKE/USDT:USDT", "LONG", "futures")
        finally:
            os.environ.pop("LANE_KILL_PROBATION_H", None)
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
        os.environ["LANE_KILL_PROBATION_H"] = "0"
        self.addCleanup(os.environ.pop, "LANE_KILL_PROBATION_H", None)
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
        os.environ["LANE_KILL_PROBATION_H"] = "0"
        ec = self._ec()
        cli = mock.Mock()
        try:
            with mock.patch.object(ec, "_client", return_value=cli), \
                 mock.patch.object(ec, "_pair_tradeable", return_value=True):
                res = ec.place_order(symbol="AKE/USDT:USDT", action="BUY",
                                     enter_tag="bad_lane", segment="futures")
        finally:
            os.environ.pop("LANE_KILL_PROBATION_H", None)
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


class TestStopChurnCooldown(_Iso):
    """2026-07-17 live catch: DODOX stopped 14s after entry and re-entered twice —
    same pair+direction re-entry within STOP_REENTRY_COOLDOWN_MIN is refused."""

    def _mkdb_stops(self, rows):
        """rows: (pair, is_short, exit_reason, minutes_ago)"""
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE trades (id INTEGER PRIMARY KEY, enter_tag TEXT, "
                    "is_open INT, close_profit_abs REAL, open_date TEXT, pair TEXT, "
                    "is_short INT, exit_reason TEXT, close_date TEXT)")
        for i, (pair, short, reason, mins) in enumerate(rows):
            con.execute(
                "INSERT INTO trades VALUES (?,?,0,?,datetime('now','-1 days'),?,?,?,"
                "datetime('now', ?))",
                (i, "any", -1.0, pair, short, reason, f"-{int(mins)} minutes"))
        con.commit()
        con.close()

    def test_recent_stop_blocks_same_direction_reentry(self):
        self._mkdb_stops([("DODOX/USDT:USDT", 0, "stop_loss", 5)])
        ok, guard, why = self.lg.check("live_loop", "DODOX/USDT:USDT", "LONG")
        self.assertFalse(ok)
        self.assertEqual(guard, "stop_cooldown")
        self.assertIn("re-entry blocked", why)

    def test_direction_flip_stays_allowed(self):
        self._mkdb_stops([("DODOX/USDT:USDT", 0, "stop_loss", 5)])
        ok, guard, _ = self.lg.check("live_loop", "DODOX/USDT:USDT", "SHORT")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_old_stop_or_other_exit_reason_does_not_block(self):
        self._mkdb_stops([("A/USDT:USDT", 0, "stop_loss", 90),
                          ("B/USDT:USDT", 0, "tailgate_lock", 2)])
        self.assertTrue(self.lg.check("live_loop", "A/USDT:USDT", "LONG")[0])
        self.assertTrue(self.lg.check("live_loop", "B/USDT:USDT", "LONG")[0])

    def test_zero_knob_disables(self):
        self._mkdb_stops([("C/USDT:USDT", 0, "stop_loss", 1)])
        os.environ["STOP_REENTRY_COOLDOWN_MIN"] = "0"
        try:
            self.assertTrue(self.lg.check("live_loop", "C/USDT:USDT", "LONG")[0])
        finally:
            os.environ.pop("STOP_REENTRY_COOLDOWN_MIN", None)


class TestDeadMarketFloor(_Iso):
    """X11 (2026-07-18): entries into symbols whose realized 4h range is below
    X11_MIN_RANGE_PCT are refused (weekend stock-perps / frozen coins); no-data
    fails OPEN; 0 disables."""

    def setUp(self):
        super().setUp()
        os.environ["STOP_REENTRY_COOLDOWN_MIN"] = "0"     # isolate the floor
        self._orig_range = self.lg._range_pct_4h

    def tearDown(self):
        self.lg._range_pct_4h = self._orig_range
        os.environ.pop("STOP_REENTRY_COOLDOWN_MIN", None)
        os.environ.pop("X11_MIN_RANGE_PCT", None)
        super().tearDown()

    def test_sub_floor_range_refused_both_directions(self):
        self.lg._range_pct_4h = lambda s: 0.2
        for d in ("LONG", "SHORT"):
            ok, guard, why = self.lg.check("any_lane", "MU/USDT:USDT", d)
            self.assertFalse(ok)
            self.assertEqual(guard, "dead_market")
            self.assertIn("dead market", why)

    def test_moving_symbol_allowed(self):
        self.lg._range_pct_4h = lambda s: 5.0
        ok, guard, _ = self.lg.check("any_lane", "LAB/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_no_data_fails_open(self):
        self.lg._range_pct_4h = lambda s: None
        ok, guard, _ = self.lg.check("any_lane", "NEW/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_zero_floor_disables(self):
        os.environ["X11_MIN_RANGE_PCT"] = "0"
        self.lg._range_pct_4h = lambda s: 0.0
        ok, guard, _ = self.lg.check("any_lane", "MU/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")


class TestLiquidityFloor(_Iso):
    """X16 (2026-07-18): entries in symbols below a 30d dollar-volume floor are refused.
    Validated on live data: win rate rose monotonically across liquidity quintiles
    (.450 -> .555). No data fails OPEN; 0 disables."""

    def setUp(self):
        super().setUp()
        os.environ["STOP_REENTRY_COOLDOWN_MIN"] = "0"
        os.environ["X11_MIN_RANGE_PCT"] = "0"
        self._orig = self.lg._dollar_vol_30d

    def tearDown(self):
        self.lg._dollar_vol_30d = self._orig
        for k in ("STOP_REENTRY_COOLDOWN_MIN", "X11_MIN_RANGE_PCT", "X16_MIN_DOLLAR_VOL_M"):
            os.environ.pop(k, None)
        super().tearDown()

    def test_illiquid_symbol_refused(self):
        os.environ["X16_MIN_DOLLAR_VOL_M"] = "2.5"
        self.lg._dollar_vol_30d = lambda s: 1.0e6          # $1M/day < $2.5M floor
        ok, guard, why = self.lg.check("any", "TINY/USDT:USDT", "LONG")
        self.assertFalse(ok)
        self.assertEqual(guard, "illiquid")
        self.assertIn("floor", why)

    def test_liquid_symbol_allowed(self):
        os.environ["X16_MIN_DOLLAR_VOL_M"] = "2.5"
        self.lg._dollar_vol_30d = lambda s: 50.0e6
        ok, guard, _ = self.lg.check("any", "BTC/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_missing_data_fails_open(self):
        os.environ["X16_MIN_DOLLAR_VOL_M"] = "2.5"
        self.lg._dollar_vol_30d = lambda s: None
        ok, guard, _ = self.lg.check("any", "NEW/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_zero_floor_disables(self):
        os.environ["X16_MIN_DOLLAR_VOL_M"] = "0"
        self.lg._dollar_vol_30d = lambda s: 1.0
        ok, guard, _ = self.lg.check("any", "TINY/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")


class TestCounterTrendRefusal(_Iso):
    """X17 (2026-07-18): entries fighting the symbol's 7-day trend are REFUSED (never
    inverted — CONVENTIONS §16). Flat symbols (|trend| < neutral band) allow both sides."""

    def setUp(self):
        super().setUp()
        for k, v in (("STOP_REENTRY_COOLDOWN_MIN", "0"), ("X11_MIN_RANGE_PCT", "0"),
                     ("X16_MIN_DOLLAR_VOL_M", "0"), ("X17_COUNTER_TREND_PCT", "2.0"),
                     ("X17_NEUTRAL_PCT", "1.0")):
            os.environ[k] = v
        self._orig = self.lg._trend_pct_nd

    def tearDown(self):
        self.lg._trend_pct_nd = self._orig
        for k in ("STOP_REENTRY_COOLDOWN_MIN", "X11_MIN_RANGE_PCT", "X16_MIN_DOLLAR_VOL_M",
                  "X17_COUNTER_TREND_PCT", "X17_NEUTRAL_PCT", "X17_TREND_DAYS"):
            os.environ.pop(k, None)
        super().tearDown()

    def test_short_into_uptrend_refused(self):
        self.lg._trend_pct_nd = lambda s, d=7: +8.0
        ok, guard, why = self.lg.check("any", "UP/USDT:USDT", "SHORT")
        self.assertFalse(ok)
        self.assertEqual(guard, "counter_trend")
        self.assertIn("trend", why)

    def test_long_into_downtrend_refused(self):
        self.lg._trend_pct_nd = lambda s, d=7: -8.0
        ok, guard, _ = self.lg.check("any", "DOWN/USDT:USDT", "LONG")
        self.assertFalse(ok)
        self.assertEqual(guard, "counter_trend")

    def test_aligned_entries_allowed(self):
        self.lg._trend_pct_nd = lambda s, d=7: +8.0
        ok, guard, _ = self.lg.check("any", "UP/USDT:USDT", "LONG")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_flat_symbol_allows_both_sides(self):
        self.lg._trend_pct_nd = lambda s, d=7: +0.4      # inside the neutral band
        for d in ("LONG", "SHORT"):
            ok, guard, _ = self.lg.check("any", "FLAT/USDT:USDT", d)
            self.assertTrue(ok, d)
            self.assertEqual(guard, "")

    def test_no_data_fails_open(self):
        self.lg._trend_pct_nd = lambda s, d=7: None
        ok, guard, _ = self.lg.check("any", "NEW/USDT:USDT", "SHORT")
        self.assertTrue(ok)
        self.assertEqual(guard, "")

    def test_zero_disables(self):
        os.environ["X17_COUNTER_TREND_PCT"] = "0"
        self.lg._trend_pct_nd = lambda s, d=7: +50.0
        ok, guard, _ = self.lg.check("any", "UP/USDT:USDT", "SHORT")
        self.assertTrue(ok)
        self.assertEqual(guard, "")
