"""Tests for trading/broker_sense/screen_mirror.py — the Brain Screen Mirror store.

State is isolated to a temp dir (project rule: monkeypatch trading.state.STATE_DIR)."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from trading import state


class FakePage:
    """Minimal Playwright-page stand-in for the capture path."""
    url = "https://www.binance.com/en/futures/BTCUSDT"
    viewport_size = {"width": 1280, "height": 800}

    def __init__(self, fail: bool = False):
        self._fail = fail

    def screenshot(self, **kw):
        if self._fail:
            raise RuntimeError("page gone")
        return b"\xff\xd8\xff fake-jpeg-bytes"

    def title(self):
        return "BTCUSDT | Binance Futures"

    def is_closed(self):
        return False


class ScreenMirrorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.patch = mock.patch.object(state, "STATE_DIR", Path(self.tmp.name))
        self.patch.start()
        from trading.broker_sense import screen_mirror as sm
        self.sm = sm
        sm._LAST_TS.clear()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_record_frame_and_status(self):
        ok = self.sm.record("binance", FakePage(), force=True)
        self.assertTrue(ok)
        self.assertTrue((self.sm.frame("binance") or b"").startswith(b"\xff\xd8"))
        st = self.sm.status()
        b = st["brokers"]["binance"]
        self.assertTrue(b["live"])
        self.assertIn("futures/BTCUSDT", b["url"])

    def test_action_logged_with_click_marker(self):
        self.sm.log_action("binance", FakePage(), "click",
                           "the star icon", xy=(640, 120), ok=True)
        acts = self.sm.actions("binance")
        self.assertEqual(len(acts), 1)
        self.assertEqual(acts[0]["act"], "click")
        self.assertEqual(acts[0]["xy"], [640, 120])
        self.assertTrue(acts[0]["frame"])
        st = self.sm.status()["brokers"]["binance"]
        self.assertEqual(st["last_action"]["xy"], [640, 120])

    def test_idle_throttle_keeps_feed_but_skips_frame(self):
        pg = FakePage()
        self.assertTrue(self.sm.record("binance", pg, force=True))
        # immediately again, no force → frame throttled, action still recorded
        got = self.sm.record("binance", pg, action={"act": "read", "detail": "x"})
        self.assertFalse(got)
        acts = self.sm.actions("binance")
        self.assertEqual(acts[-1]["act"], "read")
        self.assertFalse(acts[-1]["frame"])

    def test_page_failure_never_raises_and_logs_action(self):
        got = self.sm.record("binance", FakePage(fail=True),
                             action={"act": "click", "detail": "y"}, force=True)
        self.assertFalse(got)
        acts = self.sm.actions("binance")
        self.assertEqual(acts[-1]["frame"], False)

    def test_kill_switch(self):
        with mock.patch.dict("os.environ", {"SCREEN_MIRROR": "0"}):
            self.assertFalse(self.sm.record("binance", FakePage(), force=True))
            self.assertFalse(self.sm.status()["enabled"])

    def test_record_bytes_lands_frame_and_keeps_last_action(self):
        pg = FakePage()
        self.assertTrue(self.sm.record("binance", pg,
                                       action={"act": "click", "detail": "z"}, force=True))
        # reused eyes screenshot → new frame + meta, previous last_action preserved
        self.sm._LAST_TS.clear()                       # bypass the idle throttle
        self.assertTrue(self.sm.record_bytes("binance", b"jpegbytes2",
                                             url="https://x", viewport={"w": 10, "h": 5}))
        st = self.sm.status()["brokers"]["binance"]
        self.assertEqual(st["url"], "https://x")
        self.assertEqual(st["last_action"]["act"], "click")
        self.assertEqual(self.sm.frame("binance"), b"jpegbytes2")

    def test_record_bytes_throttled_and_never_raises(self):
        self.sm._LAST_TS.clear()
        self.assertTrue(self.sm.record_bytes("binance", b"a"))
        self.assertFalse(self.sm.record_bytes("binance", b"b"))   # inside min interval
        self.assertFalse(self.sm.record_bytes("binance", b""))    # empty shot is a no-op

    def test_actions_trimmed_to_cap(self):
        pg = FakePage()
        for i in range(self.sm._MAX_ACTIONS + 25):
            self.sm._append_action("binance", {"act": "read", "i": i})
        acts = self.sm.actions("binance", limit=self.sm._MAX_ACTIONS + 50)
        self.assertLessEqual(len(acts), self.sm._MAX_ACTIONS)
        self.assertEqual(acts[-1]["i"], self.sm._MAX_ACTIONS + 24)


if __name__ == "__main__":
    unittest.main()
