"""Tests for profit tailgating (trading/execution/profit_tailgate) — the ratcheting profit lock."""
import tempfile, unittest
from pathlib import Path
import trading.state as state


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory(); self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
    def tearDown(self):
        state.STATE_DIR = self._o; self._t.cleanup()


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

    def test_learn_tightens_after_poor_capture(self):
        from trading.execution import profit_tailgate as pt
        base = pt.learned_distance("crypto", "futures")
        for _ in range(6):
            pt.learn("crypto", "futures", peak_profit_pct=10.0, captured_pct=2.0)  # gave lots back
        self.assertLessEqual(pt.learned_distance("crypto", "futures"), base + 0.01)


if __name__ == "__main__":
    unittest.main()
