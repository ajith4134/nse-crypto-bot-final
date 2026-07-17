"""Tests for profit tailgating (trading/execution/profit_tailgate) — the ratcheting profit lock."""
import os, tempfile, unittest
from pathlib import Path
import trading.state as state

# the prod ~/.env (loaded by conftest/import chain) may carry the crypto sweep overrides;
# these tests pin the DEFAULT behavior, so the overrides must not leak in
_ENV_KNOBS = ("TAILGATE_ARM_PROFIT_PCT_CRYPTO", "TAILGATE_DIST_MAX_CRYPTO")


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(); self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        self._env = {k: os.environ.pop(k, None) for k in _ENV_KNOBS}
    def tearDown(self):
        state.STATE_DIR = self._o; self._t.cleanup()
        for k, v in self._env.items():
            if v is not None:
                os.environ[k] = v


class TestRatchet(_Iso):
    def test_locked_profit_ratchets_up_never_down(self):
        from trading.execution import profit_tailgate as pt
        a = pt.locked_profit("crypto", "futures", trade_id="T", profit_pct=8, peak_profit_pct=10)
        self.assertAlmostEqual(a["locked_profit_pct"], 7.0)     # 10 * (1-0.30)
        self.assertFalse(a["exit"])
        b = pt.locked_profit("crypto", "futures", trade_id="T", profit_pct=11, peak_profit_pct=14)
        self.assertAlmostEqual(b["locked_profit_pct"], 9.8)     # ratcheted UP (14*0.7 > 7)
        # peak falls back but lock does NOT drop
        c = pt.locked_profit("crypto", "futures", trade_id="T", profit_pct=9.5, peak_profit_pct=12)
        self.assertGreaterEqual(c["locked_profit_pct"], 9.8)    # never below prior lock
        self.assertTrue(c["exit"])                              # profit 9.5 <= lock 9.8 → exit

    def test_not_armed_below_threshold(self):
        from trading.execution import profit_tailgate as pt
        d = pt.locked_profit("crypto", "spot", trade_id="X", profit_pct=0.2, peak_profit_pct=0.3)
        self.assertFalse(d["exit"])

    def test_exit_fires_when_profit_gapped_negative(self):
        """2026-07-10 regression: profit fell straight through the lock into the red between
        polls — the old `profit_pct > 0` guard then blocked the exit FOREVER and the trade
        rode down to the hard stop, giving back the whole locked gain."""
        from trading.execution import profit_tailgate as pt
        a = pt.locked_profit("crypto", "futures", trade_id="G", profit_pct=4, peak_profit_pct=5)
        self.assertFalse(a["exit"])                             # riding above the lock
        b = pt.locked_profit("crypto", "futures", trade_id="G", profit_pct=-2.7, peak_profit_pct=5)
        self.assertTrue(b["exit"])                              # gapped below zero → still exits

    def test_stored_peak_ratchets_never_below_lock(self):
        """2026-07-10 regression: callers derive the peak from live data each poll; a lower
        reading (e.g. a mixed leverage basis) must never shrink the stored peak below the
        lock — the file showed impossible locked > peak states."""
        from trading.execution import profit_tailgate as pt
        pt.locked_profit("crypto", "futures", trade_id="P", profit_pct=9, peak_profit_pct=10)
        c = pt.locked_profit("crypto", "futures", trade_id="P", profit_pct=2, peak_profit_pct=3)
        self.assertAlmostEqual(c["peak_profit_pct"], 10.0)      # peak held, not overwritten down
        self.assertGreaterEqual(c["peak_profit_pct"], c["locked_profit_pct"])

    def test_exit_fires_at_exact_lock_equality(self):
        """2026-07-10 regression (owner report): trade sat with profit EQUAL to the shown
        locked profit and never exited. Module-level: equality must exit. The live_loop
        caller bug (deciding via should_exit's fresh peak×(1−dist) line instead of the
        ratcheted _dec['exit'] it displays) is fixed by using _dec['exit'] directly."""
        from trading.execution import profit_tailgate as pt
        a = pt.locked_profit("crypto", "futures", trade_id="EQ", profit_pct=8, peak_profit_pct=10)
        lock = a["locked_profit_pct"]
        b = pt.locked_profit("crypto", "futures", trade_id="EQ", profit_pct=lock,
                             peak_profit_pct=10)
        self.assertTrue(b["exit"])                              # profit == lock → exit, not <

    def test_ratcheted_lock_beats_fresh_line_after_dist_loosens(self):
        """The displayed lock is the RATCHET (never down). If the learned distance loosens,
        should_exit's fresh line drops BELOW the ratchet — the exact divergence that left
        live_loop trades touching their displayed lock without exiting. locked_profit must
        still exit at the ratcheted value."""
        from trading import state as st
        from trading.execution import profit_tailgate as pt
        pt.locked_profit("crypto", "futures", trade_id="RD", profit_pct=9, peak_profit_pct=10)
        st.save_json("profit_tailgate.json",                    # loosen dist 0.30 → 0.55
                     {"dist": {"crypto|futures|any": {"value": 0.55, "n": 9}}})
        fresh_exit, _, _ = pt.should_exit("crypto", "futures", 7.0, 10.0)
        self.assertFalse(fresh_exit)                            # fresh line 4.5 says "ride"
        d = pt.locked_profit("crypto", "futures", trade_id="RD", profit_pct=7.0,
                             peak_profit_pct=10)
        self.assertTrue(d["exit"])                              # ratchet 7.0 says EXIT

    def test_learn_tightens_after_poor_capture(self):
        from trading.execution import profit_tailgate as pt
        base = pt.learned_distance("crypto", "futures")
        for _ in range(6):
            pt.learn("crypto", "futures", peak_profit_pct=10.0, captured_pct=2.0)  # gave lots back
        self.assertLessEqual(pt.learned_distance("crypto", "futures"), base + 0.01)


class TestCryptoSweepOverrides(_Iso):
    """2026-07-17 sweep knobs: crypto-only arm override + dist cap; NSE untouched."""

    def test_crypto_arm_override_and_dist_cap(self):
        from trading.execution import profit_tailgate as pt
        os.environ["TAILGATE_ARM_PROFIT_PCT_CRYPTO"] = "1.0"
        os.environ["TAILGATE_DIST_MAX_CRYPTO"] = "0.2"
        # peak 1.5 ≥ overridden arm 1.0 → armed; lock = 1.5*(1-0.2) = 1.2 (capped dist)
        a = pt.locked_profit("crypto", "futures", trade_id="C1",
                             profit_pct=1.3, peak_profit_pct=1.5)
        self.assertAlmostEqual(a["locked_profit_pct"], 1.2)
        self.assertAlmostEqual(a["distance_pct"], 0.2)
        # falls to the lock → exit
        b = pt.locked_profit("crypto", "futures", trade_id="C1",
                             profit_pct=1.1, peak_profit_pct=1.5)
        self.assertTrue(b["exit"])

    def test_nse_ignores_crypto_overrides(self):
        from trading.execution import profit_tailgate as pt
        os.environ["TAILGATE_ARM_PROFIT_PCT_CRYPTO"] = "1.0"
        os.environ["TAILGATE_DIST_MAX_CRYPTO"] = "0.2"
        # NSE: default arm 3.0 still applies (peak 1.5 NOT armed), default dist 0.25
        a = pt.locked_profit("nse", "mtf", trade_id="N1",
                             profit_pct=1.3, peak_profit_pct=1.5)
        self.assertEqual(a["locked_profit_pct"], 0.0)
        self.assertFalse(a["exit"])
        self.assertGreater(a["distance_pct"], 0.2)


if __name__ == "__main__":
    unittest.main()
