"""Tests for the per-broker public↔account data-source switch (data_sources + screen_all gating).

Covers: default public-ON, flip to account-first, cross-process persistence, and that screen_all
actually changes lanes (public OFF → drops the TradingView public floor + the public app screen,
calls account_screen instead). STATE_DIR-isolated; no browser.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import trading.state as state
from trading.broker_sense import data_sources as ds
from trading.broker_sense import screeners


class _IsolatedState(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._old
        self._tmp.cleanup()


class TestSwitch(_IsolatedState):
    def test_default_public_on(self):
        self.assertTrue(ds.public_enabled("binance"))
        self.assertTrue(ds.public_enabled("angelone"))
        self.assertFalse(ds.account_first("binance"))

    def test_flip_off_persists_cross_process(self):
        ds.set_public("binance", False)
        self.assertFalse(ds.public_enabled("binance"))     # same "process"
        # a fresh read (another process) sees the flip via the state file
        state.load_json.cache_clear() if hasattr(state.load_json, "cache_clear") else None
        self.assertTrue(ds.account_first("binance"))
        st = ds.status()
        self.assertEqual(st["binance"]["mode"], "account")
        self.assertEqual(st["angelone"]["mode"], "public")

    def test_status_only_toggleable_brokers(self):
        self.assertEqual(set(ds.status().keys()), {"binance", "angelone"})


class TestScreenAllGating(_IsolatedState):
    def _fakes(self):
        sessions = mock.MagicMock()
        return sessions

    def test_public_on_uses_tv_and_app(self):
        calls = {"tv": 0, "app": 0, "account": 0}
        with mock.patch.object(screeners, "tv_screen", lambda *a, **k: (calls.__setitem__("tv", calls["tv"] + 1) or [])), \
             mock.patch.object(screeners, "app_screen", lambda *a, **k: (calls.__setitem__("app", calls["app"] + 1) or [])), \
             mock.patch.object(screeners, "account_screen", lambda *a, **k: (calls.__setitem__("account", calls["account"] + 1) or [])):
            screeners.screen_all("crypto", self._fakes(), preset="top_movers")
        self.assertEqual(calls["tv"], 1)                   # TV public floor used
        self.assertGreaterEqual(calls["app"], 1)           # binance public screener used
        self.assertEqual(calls["account"], 0)              # account lane NOT used

    def test_public_off_uses_account_not_public(self):
        ds.set_public("binance", False)
        calls = {"tv": 0, "app": 0, "account": 0}
        with mock.patch.object(screeners, "tv_screen", lambda *a, **k: (calls.__setitem__("tv", calls["tv"] + 1) or [])), \
             mock.patch.object(screeners, "app_screen", lambda *a, **k: (calls.__setitem__("app", calls["app"] + 1) or [])), \
             mock.patch.object(screeners, "account_screen", lambda *a, **k: (calls.__setitem__("account", calls["account"] + 1) or [])):
            screeners.screen_all("crypto", self._fakes(), preset="top_movers")
        self.assertEqual(calls["tv"], 0)                   # TV public floor DROPPED (account-first)
        self.assertGreaterEqual(calls["account"], 1)       # account lane used for binance
        # binance's PUBLIC app screener must not be used
        # (other crypto brokers stay public, so app may still be called for them)


class TestAccountScreenRequiresLogin(_IsolatedState):
    def test_account_screen_empty_without_creds(self):
        from trading.broker_sense.brokers import REGISTRY
        app = REGISTRY["binance"]
        with mock.patch("trading.brain.credentials.get_vault") as gv:
            gv.return_value.get.return_value = None        # not connected
            self.assertEqual(screeners.account_screen(app, mock.MagicMock()), [])


if __name__ == "__main__":
    unittest.main()
