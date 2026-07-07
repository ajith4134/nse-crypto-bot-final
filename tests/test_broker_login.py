"""Tests for the broker login flow (trading/broker_sense/sessions) — multi-step aware, offline.

Binance's login is TWO steps: step 1 = email/phone only + 'Log In'; step 2 = password (then
OTP). The single-step detector missed step 1 entirely (no password field → 'no login needed'),
so the brain never logged in. These tests pin the multi-step detection + fill sequence with a
stateful fake page. STATE_DIR-isolated; no real browser.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trading.state as state
from trading.broker_sense import sessions as S


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)
        import trading.brain.credentials as cred
        cred._VAULT = None

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()
        import trading.brain.credentials as cred
        cred._VAULT = None


class _El:
    def __init__(self, kind, text="", page=None):
        self.kind, self.text, self.page = kind, text, page
        self.filled = None
        self.clicked = False

    def inner_text(self):
        return self.text

    def get_attribute(self, _n):
        return None

    def fill(self, v):
        self.filled = v

    def press(self, _k):
        if self.page:
            self.page._submit()

    def click(self):
        self.clicked = True
        if self.page:
            self.page._submit()


class _FakeBinance:
    """Stateful two-step login: step1 email+button, step2 password+button, step3 logged-in."""
    def __init__(self):
        self.step = 1
        self.filled_user = None
        self.filled_pw = None

    def _submit(self):
        if self.step == 1:
            self.step = 2
        elif self.step == 2:
            self.step = 3                        # logged in

    @property
    def body(self):
        return {1: "Log in\nEmail/Phone number", 2: "Enter your password",
                3: "Dashboard Estimated Balance Wallet"}[self.step]

    def _email(self):
        el = _El("email", "", self); el._owner = "user"
        return el

    def _btn(self):
        return _El("button", "Log In", self)

    def _pw(self):
        el = _El("password", "", self); el._owner = "pw"
        return el

    def query_selector(self, sel):
        s = sel.lower()
        if "password" in s:
            return self._pw() if self.step == 2 else None
        if "one-time-code" in s or "otp" in s:
            return None
        if any(k in s for k in ("email", "tel", "user", "mobile", "phone")) or "text" in s:
            return self._email() if self.step == 1 else None
        if "submit" in s or s == "button":
            return self._btn()
        return None

    def query_selector_all(self, _sel):
        return [self._btn()]

    def inner_text(self, _sel="body"):
        return self.body

    def wait_for_timeout(self, _ms):
        pass

    # record fills by routing through a tracking wrapper
    def track(self):
        orig_qs = self.query_selector

        def qs(sel):
            el = orig_qs(sel)
            if el is not None and getattr(el, "_owner", None) == "user":
                _orig = el.fill
                el.fill = lambda v: (setattr(self, "filled_user", v), _orig(v))
            if el is not None and getattr(el, "_owner", None) == "pw":
                _orig = el.fill
                el.fill = lambda v: (setattr(self, "filled_pw", v), _orig(v))
            return el
        self.query_selector = qs


class TestLoginDetection(unittest.TestCase):
    def test_looks_like_login_step1_email_only(self):
        pg = _FakeBinance()                      # step 1: no password, but email + "Log in"
        self.assertTrue(S._looks_like_login(pg))

    def test_not_login_when_no_affordance(self):
        class Plain:
            def query_selector(self, sel):
                return None
            def inner_text(self, _s="body"):
                return "Markets overview top gainers"
        self.assertFalse(S._looks_like_login(Plain()))

    def test_click_login_presses_login_button(self):
        pg = _FakeBinance()
        self.assertTrue(S._click_login(pg))
        self.assertEqual(pg.step, 2)             # advanced to the password step


class TestChallengeDetection(unittest.TestCase):
    def test_image_captcha_detected(self):
        class Cap:
            def inner_text(self, _s="body"):
                return "Log in\nPlease select all images with car\nVerify"
            def query_selector(self, _sel):
                return None
        self.assertTrue(S._challenge_present(Cap()))

    def test_clean_page_no_challenge(self):
        class Clean:
            def inner_text(self, _s="body"):
                return "Estimated Balance 1234 USDT Spot Wallet"
            def query_selector(self, _sel):
                return None
        self.assertFalse(S._challenge_present(Clean()))


class TestClickLoginSelectivity(unittest.TestCase):
    class _P:
        def __init__(self, buttons):
            self.buttons = buttons  # list of _El

        def query_selector_all(self, _sel):
            return self.buttons

    def test_skips_sso_and_consent_clicks_real_submit(self):
        google = _El("button", "Continue with Google")
        cookie = _El("button", "Accept Cookies")
        real = _El("button", "Log In")
        p = self._P([cookie, google, real])
        p.buttons[0].page = p.buttons[1].page = p.buttons[2].page = None
        self.assertTrue(S._click_login(p))
        self.assertTrue(real.clicked)            # the real submit
        self.assertFalse(google.clicked)         # NOT the SSO button
        self.assertFalse(cookie.clicked)         # NOT the cookie button


class TestChallengeNoFalsePositive(unittest.TestCase):
    def test_carousel_slider_is_not_a_challenge(self):
        class Page:
            def inner_text(self, _s="body"):
                return "Estimated Balance 1200 USDT   Markets carousel slider promo"
            def query_selector(self, _sel):
                return None                      # no captcha element — just a promo carousel
        self.assertFalse(S._challenge_present(Page()))

    def test_real_image_captcha_still_detected(self):
        class Page:
            def inner_text(self, _s="body"):
                return "Please select all images with a car"
            def query_selector(self, _sel):
                return None
        self.assertTrue(S._challenge_present(Page()))


class TestMultiStepLogin(_IsolatedState):
    def test_login_fills_email_then_password(self):
        from trading.brain.credentials import get_vault
        from trading.broker_sense.brokers import REGISTRY
        get_vault().submit("binance.com", {"username": "me@x.com", "password": "SEKRET"})
        pg = _FakeBinance(); pg.track()
        ok = S.SessionManager()._login(pg, REGISTRY["binance"])
        self.assertEqual(pg.filled_user, "me@x.com")   # step 1 email filled
        self.assertEqual(pg.filled_pw, "SEKRET")       # step 2 password filled (multi-step!)
        self.assertTrue(ok)                             # reached logged-in (no password field left)


if __name__ == "__main__":
    unittest.main()
