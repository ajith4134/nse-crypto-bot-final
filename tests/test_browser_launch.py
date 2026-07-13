"""Tests for browser_launch (adopt item 5) — STEALTH_BROWSER routing between standard Playwright
and the Patchright anti-detect fork, with an honest fallback that never breaks a login."""
import os
import unittest

from trading.broker_sense import browser_launch as bl


class TestRouting(unittest.TestCase):
    def setUp(self):
        self._prev = os.environ.get("STEALTH_BROWSER")

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("STEALTH_BROWSER", None)
        else:
            os.environ["STEALTH_BROWSER"] = self._prev

    def test_default_is_playwright(self):
        os.environ.pop("STEALTH_BROWSER", None)
        self.assertEqual(bl.mode(), "playwright")
        self.assertEqual(bl.active(), "playwright")

    def test_flag_selects_patchright_when_ready(self):
        os.environ["STEALTH_BROWSER"] = "patchright"
        # active() honours the flag only if patchright+browser are installed; else falls back.
        self.assertEqual(bl.active(), "patchright" if bl._patchright_ready() else "playwright")

    def test_sync_playwright_returns_a_manager(self):
        os.environ.pop("STEALTH_BROWSER", None)
        mgr = bl.sync_playwright()
        self.assertTrue(hasattr(mgr, "start"))       # same surface as playwright's

    def test_status_shape(self):
        s = bl.status()
        self.assertIn("requested", s)
        self.assertIn("active", s)
        self.assertIn("patchright_ready", s)


if __name__ == "__main__":
    unittest.main()
