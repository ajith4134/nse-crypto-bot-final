"""Regression tests for the Live-Browser ↔ funnel profile-ownership coordination.

Bug (2026-07-11): the dashboard's Live-Browser login panel and the funnel both opened the SAME
Chromium user-data-dir (browser_profiles/<broker>) at once. Chromium mandates one process per
profile, so concurrent access corrupted the cookie DB — operator logins never persisted (bounced
back to the login screen) and the panel's frames hitched. The fix makes the funnel YIELD the
profile while the operator is logging in (login-lock flag), so the login browser is the sole
owner. These tests pin that coordination without needing a real browser.
"""
import tempfile
import time
import unittest
from pathlib import Path

from trading import state


class LiveLoginCoordTest(unittest.TestCase):
    def setUp(self):
        # isolate-state: never touch the live state dir (memory: isolate-state-in-tests)
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp())

    def tearDown(self):
        state.STATE_DIR = self._orig

    def test_begin_end_flag(self):
        from trading.broker_sense import sessions as s
        self.assertFalse(s.login_in_progress("binance"))
        s.begin_operator_login("binance")
        self.assertTrue(s.login_in_progress("binance"))
        s.end_operator_login("binance")
        self.assertFalse(s.login_in_progress("binance"))
        # end is idempotent (operator can Close twice)
        s.end_operator_login("binance")

    def test_stale_lock_self_expires(self):
        from trading.broker_sense import sessions as s
        s.begin_operator_login("binance")
        p = s._login_lock_path("binance")
        p.write_text(str(time.time() - (s._LOGIN_LOCK_MAX_AGE_S + 60)))  # abandoned
        self.assertFalse(s.login_in_progress("binance"))  # reclaimed
        self.assertFalse(p.exists())                       # and cleaned up

    def test_release_only_login_locked_context(self):
        from trading.broker_sense import sessions as s

        class FakeCtx:
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

        mgr = s.SessionManager()
        binance_ctx, upstox_ctx = FakeCtx(), FakeCtx()
        mgr._contexts["binance"], mgr._contexts["upstox"] = binance_ctx, upstox_ctx
        s.begin_operator_login("binance")
        released = mgr.release_if_login_locked()
        self.assertEqual(released, ["binance"])
        self.assertTrue(binance_ctx.closed)
        self.assertNotIn("binance", mgr._contexts)
        # a broker with no login in progress is left untouched
        self.assertFalse(upstox_ctx.closed)
        self.assertIn("upstox", mgr._contexts)

    def test_page_yields_none_and_releases_during_login(self):
        from trading.broker_sense import sessions as s

        class FakeCtx:
            def close(self):
                pass

        mgr = s.SessionManager()
        mgr._contexts["binance"] = FakeCtx()
        s.begin_operator_login("binance")
        # page() must refuse to open the shared profile while the operator is logging in
        self.assertIsNone(mgr.page("binance"))
        self.assertNotIn("binance", mgr._contexts)  # and it released the held context


if __name__ == "__main__":
    unittest.main()
