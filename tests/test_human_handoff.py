"""tests/test_human_handoff.py — mid-session human-CAPTCHA handoff.

Hermetic: state is isolated by monkeypatching trading.state.STATE_DIR (project rule), the
VNC bring-up is disabled (HUMAN_HANDOFF_VNC=0 → no subprocess), the screen mirror is off
(SCREEN_MIRROR=0 → the park loop's refresh short-circuits), and Telegram runs dry-run (no
creds). guard()'s sleeper is replaced so the blocking park loop runs at zero wall-clock.
"""
import importlib
import os
import unittest


class FakePage:
    """Minimal Playwright-page stand-in for is_human_challenge + screen_mirror.record."""
    def __init__(self, body="normal trading page", url="https://binance.com/futures"):
        self._body = body
        self.url = url
        self._closed = False
        self.viewport_size = {"width": 1600, "height": 1000}

    def inner_text(self, _sel):
        return self._body

    def __init_widgets__(self, widgets):
        self._widgets = widgets or {}

    _widgets: dict = {}

    def with_widgets(self, widgets):
        self._widgets = widgets
        return self

    def query_selector_all(self, sel):
        for key, els in (self._widgets or {}).items():
            if key in sel:
                return els
        return []                                    # no captcha widget → text match decides

    def query_selector(self, _sel):
        return None

    def is_closed(self):
        return self._closed

    def title(self):
        return "Binance"

    def screenshot(self, **_kw):
        return b"\xff\xd8\xff"                        # tiny fake jpeg


CHALLENGE_BODY = "Security Verification — Slide to complete the puzzle"


def _fresh_module(tmp_state):
    """Reload trading.state pointed at a temp dir, then human_handoff, so every test is
    fully isolated (state file, throttle caches, parking set)."""
    import trading.state as state
    state.STATE_DIR = tmp_state
    from trading.broker_sense import human_handoff
    importlib.reload(human_handoff)
    human_handoff._sleep = lambda _s: None           # no real waiting in the park loop
    return human_handoff


class TestHumanHandoff(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmp = tempfile.TemporaryDirectory()
        os.environ["HUMAN_HANDOFF"] = "1"
        os.environ["HUMAN_HANDOFF_VNC"] = "0"        # no real x11vnc/websockify subprocess
        os.environ["SCREEN_MIRROR"] = "0"            # park-loop refresh short-circuits
        os.environ["HANDOFF_CHECK_S"] = "0"          # no throttle in tests
        os.environ["HANDOFF_MAX_WAIT"] = "3"         # park-loop safety cap (no real sleep in tests)
        os.environ.pop("TELEGRAM_BOT_TOKEN", None)   # keep Telegram dry-run
        import pathlib
        self.hh = _fresh_module(pathlib.Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()
        for k in ("HUMAN_HANDOFF_VNC", "SCREEN_MIRROR", "HANDOFF_CHECK_S", "HANDOFF_MAX_WAIT"):
            os.environ.pop(k, None)

    # ── detection ────────────────────────────────────────────────────────────
    def test_detects_slide_puzzle(self):
        from trading.broker_sense import sessions
        self.assertTrue(sessions.is_human_challenge(FakePage(CHALLENGE_BODY)))
        self.assertFalse(sessions.is_human_challenge(FakePage("just a normal chart")))

    def test_detects_binance_jigsaw_security_verification(self):
        """Regression (2026-07-12): Binance's 'Security Verification' JIGSAW puzzle — no
        'slide' wording, a canvas widget — was read as 'no challenge'. Must fire now."""
        from trading.broker_sense import sessions

        class _El:
            def is_visible(self): return True
            def bounding_box(self): return {"x": 0, "y": 0, "width": 320, "height": 240}
            def get_attribute(self, _a): return ""
        jig = FakePage("dashboard est. total value security verification user-28ba0") \
            .with_widgets({"canvas": [_El()]})
        self.assertTrue(sessions.is_human_challenge(jig))

    def test_otp_security_verification_is_not_a_challenge(self):
        """The OTP 'Security Verification' step (code input, no puzzle) must NOT hand off —
        the brain solves it via the vault. Guards against a false-positive regression."""
        from trading.broker_sense import sessions

        class _Code:
            def is_visible(self): return True
            def bounding_box(self): return {"x": 0, "y": 0, "width": 40, "height": 40}
            def get_attribute(self, _a): return ""
        otp = FakePage("security verification enter the 6-digit code sent to your email") \
            .with_widgets({"one-time-code": [_Code()], "maxlength": [_Code()]})
        self.assertFalse(sessions.is_human_challenge(otp))

    def test_detects_puzzle_action_phrases(self):
        from trading.broker_sense import sessions
        for txt in ("please complete the puzzle to continue",
                    "drag the slider to finish", "slide to verify your identity"):
            self.assertTrue(sessions.is_human_challenge(FakePage(txt)), txt)

    def test_is_human_challenge_never_raises(self):
        from trading.broker_sense import sessions
        self.assertFalse(sessions.is_human_challenge(None))     # bad input → False, no crash

    # ── guard: no challenge = fast path, no state ─────────────────────────────
    def test_guard_no_challenge_is_noop(self):
        self.assertFalse(self.hh.guard("binance", FakePage("normal page")))
        self.assertFalse(self.hh.status()["any_active"])

    # ── guard: non-blocking activation ────────────────────────────────────────
    def test_guard_activates_on_challenge(self):
        handled = self.hh.guard("binance", FakePage(CHALLENGE_BODY), block=False)
        self.assertTrue(handled)
        st = self.hh.status()
        self.assertTrue(st["any_active"])
        self.assertIn("binance", st["active_brokers"])
        self.assertEqual(st["brokers"]["binance"]["url"], "https://binance.com/futures")

    # ── guard: blocking park loop auto-resumes when the page clears ───────────
    def test_guard_blocks_then_auto_resumes(self):
        page = FakePage(CHALLENGE_BODY)
        polls = {"n": 0}
        orig = self.hh.is_challenge

        def clearing(pg):                            # challenge clears after a few polls
            polls["n"] += 1
            if polls["n"] >= 3:
                pg._body = "normal chart"            # operator solved the slider
            return orig(pg)

        self.hh.is_challenge = clearing
        try:
            self.assertTrue(self.hh.guard("binance", page))       # blocks, then returns
        finally:
            self.hh.is_challenge = orig
        st = self.hh.status()
        self.assertFalse(st["any_active"])                        # auto-deactivated
        self.assertFalse(st["brokers"]["binance"]["active"])
        self.assertTrue(st["brokers"]["binance"]["resolved"])

    # ── operator override: force resume via flag DURING the pause ────────────
    def test_request_resume_breaks_park_loop(self):
        page = FakePage(CHALLENGE_BODY)              # never clears on its own
        polls = {"n": 0}
        orig = self.hh.is_challenge

        def with_resume(pg):                         # operator clicks "I solved it" mid-pause
            polls["n"] += 1
            if polls["n"] == 2:                      # (fresh episode clears any stale flag on activate,
                self.hh.request_resume("binance")    #  so the override must arrive during the park loop)
            return orig(pg)

        self.hh.is_challenge = with_resume
        try:
            self.assertTrue(self.hh.guard("binance", page))
        finally:
            self.hh.is_challenge = orig
        self.assertFalse(self.hh.status()["any_active"])          # override broke the loop

    # ── kill switch ──────────────────────────────────────────────────────────
    def test_disabled_is_full_noop(self):
        os.environ["HUMAN_HANDOFF"] = "0"
        try:
            self.assertFalse(self.hh.guard("binance", FakePage(CHALLENGE_BODY)))
            self.assertFalse(self.hh.status()["any_active"])
        finally:
            os.environ["HUMAN_HANDOFF"] = "1"

    # ── take_control returns an honest surface even without x11vnc ────────────
    def test_take_control_surface(self):
        os.environ["HUMAN_HANDOFF_VNC"] = "1"        # actually invoke the script this time
        try:
            r = self.hh.take_control("binance")
        finally:
            os.environ["HUMAN_HANDOFF_VNC"] = "0"
        self.assertIn("novnc_path", r)
        self.assertTrue(r["novnc_path"].startswith("/handoff-vnc/"))
        # host has no x11vnc / no :99 in CI → honest flags, never a crash
        self.assertIn("ok", r)

    def test_status_shape_is_stable(self):
        st = self.hh.status()
        for k in ("enabled", "any_active", "active_brokers", "brokers", "novnc_path", "display"):
            self.assertIn(k, st)


if __name__ == "__main__":
    unittest.main()
