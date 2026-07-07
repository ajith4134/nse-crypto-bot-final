"""Tests for capturing a credential answer typed into Brain Chat (trading/brain/credential_chat).

Safety-critical property: when a login ask is pending, a credential answer goes to the ENCRYPTED
vault and NEVER to the cloud LLM. Covers: email+password capture, labeled fields, OTP, multi-site
disambiguation, guidance on a partial secret, and pass-through for a normal question.
STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state


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


class TestCapture(_IsolatedState):
    def _ask(self, site="binance.com", fields=("username", "password")):
        from trading.brain.credentials import get_vault
        get_vault().request_login(site, list(fields), "connect")

    def test_email_and_password_captured(self):
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask()
        out = cc.try_capture("me@example.com hunter2SECRET")
        self.assertTrue(out and out.get("captured"))
        creds = get_vault().get("binance.com")
        self.assertEqual(creds["username"], "me@example.com")
        self.assertEqual(creds["password"], "hunter2SECRET")
        # secret value must NOT appear in the reply shown to the user
        self.assertNotIn("hunter2SECRET", out["reply"])
        self.assertEqual(get_vault().pending(), [])           # ask cleared

    def test_labeled_fields(self):
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask("angelone.in", ("username", "password"))
        out = cc.try_capture("username: MYCLIENT123  password: mypin4567")
        self.assertTrue(out["captured"])
        creds = get_vault().get("angelone.in")
        self.assertEqual(creds["username"], "MYCLIENT123")
        self.assertEqual(creds["password"], "mypin4567")

    def test_newline_separated_email_password(self):
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask()
        cc.try_capture("trader@gmail.com\nP@ssw0rdLong")
        creds = get_vault().get("binance.com")
        self.assertEqual(creds["username"], "trader@gmail.com")
        self.assertEqual(creds["password"], "P@ssw0rdLong")

    def test_otp_only_ask_captures_digits(self):
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask("binance.com", ("otp",))
        out = cc.try_capture("483920")
        self.assertTrue(out["captured"])
        self.assertEqual(get_vault().get("binance.com")["otp"], "483920")

    def test_multi_site_disambiguation_by_name(self):
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask("binance.com", ("username", "password"))
        self._ask("angelone.in", ("username", "password"))
        cc.try_capture("angelone username: AB1234 password: pin9999")
        self.assertIsNotNone(get_vault().get("angelone.in"))
        self.assertIsNone(get_vault().get("binance.com"))     # only the named site saved

    def test_partial_secret_gets_guidance_not_llm(self):
        from trading.brain import credential_chat as cc
        self._ask()
        out = cc.try_capture("here is my email onlyme@example.com")   # no password parseable
        self.assertIsNotNone(out)
        self.assertFalse(out["captured"])                     # guided, not captured
        self.assertIn("NEVER send it to any LLM", out["reply"])

    def test_normal_question_passes_through(self):
        from trading.brain import credential_chat as cc
        self._ask()
        self.assertIsNone(cc.try_capture("what is the status of the network?"))

    def test_chatty_password_sentence_not_saved(self):
        # "my password is broken" must NOT save 'broken' as the password (regression)
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask()
        out = cc.try_capture("my password is broken help")
        self.assertFalse(out and out.get("captured"))          # not captured as a credential
        self.assertIsNone(get_vault().get("binance.com"))       # vault not corrupted

    def test_bare_lowercase_password_guided_not_leaked(self):
        # a lone lowercase no-digit password must be GUIDED to the vault, never sent to the LLM
        from trading.brain import credential_chat as cc
        self._ask()
        out = cc.try_capture("correcthorse")
        self.assertIsNotNone(out)                              # not passed through to the LLM
        self.assertIn("NEVER send it to any LLM", out["reply"])

    def test_single_field_ask_bare_client_code_captured(self):
        # username-only ask (Angel One flow): a bare client code IS the answer (regression:
        # it used to bounce to guidance forever; the owner could never connect)
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask(site="angelone.in", fields=("username",))
        out = cc.try_capture("A123456")
        self.assertTrue(out and out.get("captured"))
        self.assertEqual(get_vault().get("angelone.in")["username"], "A123456")

    def test_single_field_ask_typoed_label_captured_not_llm(self):
        # "clint id: A123456" (typo'd label) used to FALL THROUGH TO THE CLOUD LLM (regression)
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask(site="angelone.in", fields=("username",))
        out = cc.try_capture("clint id: A123456")
        self.assertTrue(out and out.get("captured"))
        self.assertEqual(get_vault().get("angelone.in")["username"], "A123456")

    def test_single_field_ask_chatter_not_saved(self):
        # digit-less chatter on a single-field ask must never be stored as the credential
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        self._ask(site="angelone.in", fields=("username",))
        out = cc.try_capture("thanks")
        self.assertFalse(out and out.get("captured"))
        self.assertIsNone(get_vault().get("angelone.in"))

    def test_no_pending_ask_is_passthrough(self):
        from trading.brain import credential_chat as cc
        self.assertIsNone(cc.try_capture("me@example.com somepassword123"))

    def test_explicit_connect_without_pending_ask(self):
        # no ask pending, but the operator explicitly names a broker + labels → connect anyway
        from trading.brain import credential_chat as cc
        from trading.brain.credentials import get_vault
        out = cc.try_capture("connect binance username: me@x.com password: Secret123")
        self.assertTrue(out and out.get("captured"))
        self.assertEqual(get_vault().get("binance.com")["username"], "me@x.com")

    def test_unlabeled_without_pending_does_not_capture(self):
        # no ask + no explicit broker/labels → must NOT capture (stays normal chat)
        from trading.brain import credential_chat as cc
        self.assertIsNone(cc.try_capture("just chatting me@x.com and stuff"))


class TestChatRouting(_IsolatedState):
    def test_chat_routes_credential_to_vault_not_llm(self):
        from core import chat_brain
        from trading.brain.credentials import get_vault
        get_vault().request_login("binance.com", ["username", "password"], "connect")
        with mock.patch("core.llm.chat") as llm_chat, \
             mock.patch("core.chat_brain._boss_route", return_value=None):
            out = chat_brain.chat("me@example.com myBinancePass99")
        llm_chat.assert_not_called()                          # secret never reached the LLM
        self.assertTrue(out.get("captured"))
        self.assertEqual(get_vault().get("binance.com")["password"], "myBinancePass99")


if __name__ == "__main__":
    unittest.main()
