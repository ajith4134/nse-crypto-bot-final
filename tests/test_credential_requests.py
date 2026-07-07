"""Tests for the credential-request → Brain Chat flow (cross-process) + proactive login ask.

Root cause fixed here: pending login requests were in-memory per-process, so an ask raised by
the funnel-LOOP process was invisible to the DASHBOARD process that renders the chat. They now
persist to disk (site + field names + note + ts only — no secrets), TTL-pruned. Also: broker
screener pages are public, so the reactive login-wall ask rarely fires — the funnel now
proactively asks to connect the target broker. STATE_DIR-isolated.
"""
from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


class TestCrossProcessPending(_IsolatedState):
    def test_ask_visible_from_a_different_vault_instance(self):
        import trading.brain.credentials as cred
        loop_vault = cred.CredentialVault()          # funnel-loop process
        loop_vault.request_login("binance.com", ["username", "password"], "connect Binance")
        dash_vault = cred.CredentialVault()          # dashboard process (fresh, empty _pending)
        sites = [p["site"] for p in dash_vault.pending()]
        self.assertIn("binance.com", sites)

    def test_submit_clears_cross_process(self):
        import trading.brain.credentials as cred
        cred.CredentialVault().request_login("angelone.in", ["username", "password"])
        cred.CredentialVault().submit("angelone.in", {"username": "u", "password": "p"})
        self.assertEqual(cred.CredentialVault().pending(), [])

    def test_pending_ttl_prunes_stale(self):
        import trading.brain.credentials as cred
        v = cred.CredentialVault()
        v.request_login("groww.in", ["username"])
        reqs = v._load_pending()
        reqs["groww.in"]["ts"] = time.time() - (cred._PENDING_TTL + 10)   # age it out
        v._save_pending(reqs)
        self.assertEqual(cred.CredentialVault().pending(), [])            # pruned on read

    def test_pending_note_has_no_secret_values(self):
        import trading.brain.credentials as cred
        v = cred.CredentialVault()
        v.request_login("binance.com", ["username", "password"], "connect Binance")
        raw = state.load_json("credential_requests.json", {})
        # only field NAMES + note + ts are persisted — never a value
        self.assertEqual(set(raw["binance.com"]["fields"]), {"username", "password"})
        self.assertNotIn("values", raw["binance.com"])


class TestProactiveAsk(_IsolatedState):
    def _mgr(self):
        from trading.broker_sense.sessions import SessionManager
        return SessionManager()

    def test_ensure_login_requested_raises_when_no_creds(self):
        mgr = self._mgr()
        raised = mgr.ensure_login_requested("binance")
        self.assertTrue(raised)
        import trading.brain.credentials as cred
        sites = [p["site"] for p in cred.CredentialVault().pending()]
        self.assertIn("binance.com", sites)

    def test_ensure_login_requested_skips_when_connected(self):
        import trading.brain.credentials as cred
        cred.CredentialVault().submit("binance.com", {"username": "u", "password": "p"})
        mgr = self._mgr()
        self.assertFalse(mgr.ensure_login_requested("binance"))

    def test_unknown_broker_is_noop(self):
        self.assertFalse(self._mgr().ensure_login_requested("not_a_broker"))

    def test_login_brokers_env_override(self):
        from trading.broker_sense.funnel import _login_brokers
        self.assertEqual(_login_brokers("crypto"), ["binance"])
        self.assertEqual(_login_brokers("nse"), ["angelone"])
        with mock.patch.dict("os.environ", {"BROKER_SENSE_LOGINS": "binance,bybit"}):
            self.assertEqual(_login_brokers("crypto"), ["binance", "bybit"])


if __name__ == "__main__":
    unittest.main()
