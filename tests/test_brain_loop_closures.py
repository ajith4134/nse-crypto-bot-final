"""Tests for the 2026-07-17 brain closed-loop corrections:
  F1 journal poison guard · S4 lesson-lens key roundtrip · S1 OPE self-tune state machine.
Each fix closed (or de-poisoned) a loop the brain THOUGHT it had but didn't."""
import os
import tempfile
import unittest
from unittest import mock

from trading import state
from trading.journal.journal import is_poison_row, _degenerate_symbol
from trading.direction import lesson_prior as lp
from trading.direction import ope, learned_direction as ld


class TestPoisonGuard(unittest.TestCase):
    def test_degenerate_symbol_rejected(self):
        for bad in ("USDT", "USD", "usdc", "", None, "USDT/USDT:USDT", " "):
            self.assertTrue(_degenerate_symbol(bad), f"{bad!r} should be degenerate")

    def test_real_symbols_kept(self):
        for ok in ("BTCUSDT", "BTC/USDT:USDT", "AKEUSDT", "NIFTY24450CE", "RELIANCE"):
            self.assertFalse(_degenerate_symbol(ok), f"{ok!r} is a real instrument")

    def test_poison_row_criteria(self):
        self.assertTrue(is_poison_row({"symbol": "USDT", "capital_at_risk": 100}))
        self.assertTrue(is_poison_row({"symbol": "BTCUSDT", "capital_at_risk": 28_000_000}))
        self.assertFalse(is_poison_row({"symbol": "BTCUSDT", "capital_at_risk": 1800}))

    def test_legit_option_near_zero_not_poison(self):
        # an option expiring near-worthless has a huge entry/exit ratio but a REAL symbol —
        # the guard is symbol/sizing based, never price-ratio based, so it must survive.
        self.assertFalse(is_poison_row({"symbol": "NIFTY07JUL2624450CE",
                                        "capital_at_risk": 5400}))


class TestLessonKeyRoundtrip(unittest.TestCase):
    def test_flat_key_matches_readings(self):
        # distill() must key the table by exactly what readings() looks up, or the lens is dead.
        for pair in ("AKE/USDT:USDT", "BTC/USDT:USDT", "0G/USDT:USDT"):
            self.assertEqual(lp._flat(pair), pair.replace("/", "").split(":")[0].upper())

    def test_readings_finds_distilled_row(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(d)):
            import time
            state.save_json(lp._TABLE, {"AKEUSDT": {
                "p_up": 0.68, "side": "long", "confidence": 0.9,
                "why": "x", "lesson_hash": "h", "ts": time.time()}})
            with mock.patch.object(lp, "enabled", lambda: True):
                r = lp.readings("AKE/USDT:USDT", record=False)   # slashed input, flat table
        self.assertEqual(r, [("lessons", 0.68)])


class TestOpeSelfTune(unittest.TestCase):
    def _report(self, live_mean, win_mean, live_acted, win_acted):
        return {"primary_horizon": "1h", "candidates": [
            {"name": "live_cfg", "env": {},
             "metrics": {"1h": {"capture_pct_mean": live_mean, "acted": live_acted}}},
            {"name": "min_n_15", "env": {"LEARNED_DIR_MIN_N": "15"},
             "metrics": {"1h": {"capture_pct_mean": win_mean, "acted": win_acted}}}]}

    def setUp(self):
        self.d = tempfile.mkdtemp()
        self._p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(self.d))
        self._p.start()
        for k in ("OPE_SELF_TUNE", "OPE_REPLAY", "LEARNED_DIR_MIN_N"):
            os.environ.pop(k, None)
        ld._OVERLAY["mtime"] = None

    def tearDown(self):
        self._p.stop()
        os.environ.pop("OPE_REPLAY", None)
        ld._OVERLAY["mtime"] = None

    def test_insufficient_acted_no_change(self):
        self.assertIn("insufficient", ope._self_tune(self._report(-0.2, 0.3, 5, 6))["status"])

    def test_applies_and_decider_adopts(self):
        r = ope._self_tune(self._report(-0.2, 0.3, 40, 40))
        self.assertEqual(r["status"], "APPLIED")
        self.assertEqual(ld._f("LEARNED_DIR_MIN_N", 100), 15.0)   # overlay wins over default

    def test_inert_during_replay(self):
        ope._self_tune(self._report(-0.2, 0.3, 40, 40))
        os.environ["OPE_REPLAY"] = "1"
        self.assertEqual(ld._f("LEARNED_DIR_MIN_N", 100), 100.0)  # replay ignores the overlay

    def test_reverts_when_live_catches_up(self):
        ope._self_tune(self._report(-0.2, 0.3, 40, 40))
        r = ope._self_tune(self._report(0.35, 0.3, 40, 40))
        self.assertIn("revert", r["status"])
        self.assertEqual(ld._f("LEARNED_DIR_MIN_N", 100), 100.0)

    def test_killswitch(self):
        os.environ["OPE_SELF_TUNE"] = "0"
        try:
            self.assertEqual(ope._self_tune(self._report(-0.2, 0.3, 40, 40))["status"], "disabled")
        finally:
            os.environ.pop("OPE_SELF_TUNE", None)


class TestGraveyard(unittest.TestCase):
    def test_idempotent_records_cause_of_death(self):
        d = tempfile.mkdtemp()
        with mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(d)):
            from trading.brain import graveyard as gy
            gy.record_death("filter:momentum", kind="lane", stage="lane_kill", metric=-446.0)
            gy.record_death("filter:momentum", kind="lane", stage="lane_kill", metric=-450.0)
            gy.record_death("explore_open_all", kind="lane", stage="lane_kill", metric=-1338.0)
            rows = gy.deaths()
            self.assertEqual(len(rows), 2)                      # deduped per entity
            mom = next(r for r in rows if r["entity"] == "filter:momentum")
            self.assertEqual(mom["seen"], 2)                    # refusals counted
            self.assertEqual(mom["metric"], -450.0)             # latest metric kept
            self.assertEqual(gy.status()["by_stage"], {"lane_kill": 2})


if __name__ == "__main__":
    unittest.main()
