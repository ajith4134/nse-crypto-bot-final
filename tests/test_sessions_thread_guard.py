"""Regression test for the sync-Playwright cross-thread crash (W2, 2026-07-12).

The crypto funnel's reflex/pullback-sweeper thread touched the main loop's sync-Playwright
browser, throwing `greenlet.error: cannot switch to a different thread` and crash-looping the
funnel before any full cycle completed. SessionManager now pins browser ownership to one thread
and degrades foreign-thread access to the API/None path. This test locks that invariant in.
"""
import threading
import unittest

from trading.broker_sense.sessions import SessionManager


class TestSessionThreadGuard(unittest.TestCase):
    def test_owner_thread_allowed_foreign_refused(self):
        m = SessionManager()
        m.claim_browser_owner()                       # main/owner thread
        self.assertTrue(m._own_thread())

        res = {}

        def foreign():
            res["own"] = m._own_thread()               # must be False (not the owner)
            try:
                m.context("binance")                   # must refuse, not crash cross-thread
                res["ctx"] = "no-raise"
            except RuntimeError:
                res["ctx"] = "refused"

        t = threading.Thread(target=foreign)
        t.start()
        t.join()

        self.assertTrue(m._own_thread())               # owner still owns after foreign access
        self.assertFalse(res["own"])                   # foreign refused
        self.assertEqual(res["ctx"], "refused")        # context() raised instead of greenlet-crash

    def test_page_returns_none_on_foreign_thread(self):
        m = SessionManager()
        m.claim_browser_owner()
        out = {}

        def foreign():
            # page() must return None on a foreign thread (the funnel's documented API fallback),
            # never touch the browser. Passing a bogus broker is fine — the guard returns first.
            out["page"] = m.page("binance")

        t = threading.Thread(target=foreign)
        t.start()
        t.join()
        self.assertIsNone(out["page"])


if __name__ == "__main__":
    unittest.main()
