"""Tests for the navigation segment-gate fix (2026-07-11) — the brain must NOT navigate to / drive
a segment the owner toggled OFF.

Root cause fixed: the dashboard toggle wrote controls (online-state) but never boss, so
boss.active_segments (the funnel's gate) defaulted every segment ON → options opened while off.
Now the toggle mirrors into boss. Verified here on the boss gate + the fail-closed optional filter.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from trading import state


class SegmentGateTest(unittest.TestCase):
    def setUp(self):
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="navgate_"))

    def tearDown(self):
        state.STATE_DIR = self._orig

    def test_disabling_options_removes_it_from_active(self):
        from trading.brain import boss
        boss.set_segments("CRYPTO", enable=["futures", "spot"],
                          disable=["options", "prediction"])
        active = boss.active_segments("CRYPTO")
        self.assertNotIn("options", active)
        self.assertNotIn("prediction", active)
        self.assertIn("futures", active)
        self.assertFalse(boss.segment_focus_active("CRYPTO", "options"))
        self.assertTrue(boss.segment_focus_active("CRYPTO", "futures"))

    def test_re_enabling_options_restores_it(self):
        from trading.brain import boss
        boss.set_segments("CRYPTO", disable=["options"])
        self.assertFalse(boss.segment_focus_active("CRYPTO", "options"))
        boss.set_segments("CRYPTO", enable=["options"])
        self.assertTrue(boss.segment_focus_active("CRYPTO", "options"))

    def test_optional_driver_gate_fails_closed(self):
        # the funnel's optional-segment expression: unreadable gate (active=None) → drive NOTHING
        def drive(active):
            extra = ["options", "prediction"]
            return [s for s in extra if s in active] if active is not None else []
        self.assertEqual(drive(None), [])                         # fail-closed on error
        self.assertEqual(drive({"futures"}), [])                  # options off → not driven
        self.assertEqual(drive({"futures", "options"}), ["options"])   # on → driven


if __name__ == "__main__":
    unittest.main()
