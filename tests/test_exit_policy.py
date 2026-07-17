"""Tests for trading/execution/exit_policy.py (E2 — Thompson exit-policy bandit)."""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        from trading import state
        self._tmp = tempfile.TemporaryDirectory()
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        os.environ.pop("EXIT_POLICY", None)

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()


class TestChooseAssignLearn(_Base):
    def test_choose_returns_valid_arm(self):
        from trading.execution import exit_policy as xp
        for _ in range(20):
            self.assertIn(xp.choose("trend_up"), xp.ARMS)

    def test_disabled_returns_control(self):
        from trading.execution import exit_policy as xp
        os.environ["EXIT_POLICY"] = "0"
        try:
            self.assertEqual(xp.choose("chop"), "ratchet_direction")
            self.assertIsNone(xp.assignment("42"))
        finally:
            os.environ.pop("EXIT_POLICY", None)

    def test_assign_persists_and_learn_updates_posterior(self):
        from trading.execution import exit_policy as xp
        arm = xp.assign("101", regime="chop", lane="breadth", symbol="AKE/USDT:USDT",
                        atr_pct=1.1)
        rec = xp.assignment("101")
        self.assertEqual(rec["arm"], arm)
        out = xp.learn("101", profit_pct=2.5)
        self.assertTrue(out["win"])
        self.assertIsNone(xp.assignment("101"))            # assignment consumed
        st = xp.status()
        self.assertEqual(st["arms"][arm]["n"], 1)
        self.assertEqual(st["arms"][arm]["win_rate"], 1.0)

    def test_learn_unassigned_is_none(self):
        from trading.execution import exit_policy as xp
        self.assertIsNone(xp.learn("999", profit_pct=1.0))

    def test_thompson_prefers_winning_arm(self):
        from trading import state
        from trading.execution import exit_policy as xp
        bd = {}
        for arm in xp.ARMS:
            bd[f"{arm}|chop"] = ({"a": 50, "b": 5} if arm == "va_trail"
                                 else {"a": 5, "b": 50})
        state.save_json("exit_policy_bandit.json", bd)
        picks = [xp.choose("chop") for _ in range(60)]
        self.assertGreater(picks.count("va_trail"), 30)    # dominant winner dominates draws


class TestTrailArm(_Base):
    def _mirror(self, prev_low, prev_high):
        m = mock.Mock()
        m.candles.return_value = [[0, 1, prev_high, prev_low, 1],
                                  [1, 1, 99999, 0, 1]]     # last = forming bar
        return m

    def test_trail_arms_ratchets_and_exits_on_breach(self):
        from trading.execution import exit_policy as xp
        with mock.patch.object(xp, "choose", return_value="va_trail"):
            xp.assign("7", regime="trend_up", symbol="AKEUSDT")
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(prev_low=100.0, prev_high=110.0)):
            # armed by profit ≥ arm threshold; trail = prev bar low = 100
            r1 = xp.evaluate_trail("7", symbol="AKEUSDT", direction="LONG",
                                   profit_pct=1.0, price=105.0)
            self.assertFalse(r1["exit"])
            self.assertEqual(r1["trail"], 100.0)
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(prev_low=98.0, prev_high=104.0)):
            # lower prev bar must NOT loosen the trail; price below trail → exit
            r2 = xp.evaluate_trail("7", symbol="AKEUSDT", direction="LONG",
                                   profit_pct=-0.5, price=99.0)
        self.assertTrue(r2["exit"])
        self.assertEqual(r2["trail"], 100.0)

    def test_not_armed_below_threshold(self):
        from trading.execution import exit_policy as xp
        with mock.patch.object(xp, "choose", return_value="va_trail"):
            xp.assign("8", regime="chop", symbol="AKEUSDT")
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(100.0, 110.0)):
            r = xp.evaluate_trail("8", symbol="AKEUSDT", direction="LONG",
                                  profit_pct=0.1, price=100.5)
        self.assertFalse(r["exit"])
        self.assertIsNone(r["trail"])

    def test_scale_out_takes_partial_once_at_1r(self):
        from trading.execution import exit_policy as xp
        with mock.patch.object(xp, "choose", return_value="scale_out"):
            xp.assign("9", regime="trend_up", symbol="AKEUSDT", atr_pct=1.0)
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(100.0, 110.0)):
            r1 = xp.evaluate_trail("9", symbol="AKEUSDT", direction="LONG",
                                   profit_pct=1.2, price=105.0)
            self.assertGreater(r1["partial"], 0.0)
            r2 = xp.evaluate_trail("9", symbol="AKEUSDT", direction="LONG",
                                   profit_pct=1.5, price=106.0)
            self.assertEqual(r2["partial"], 0.0)           # once only

    def test_short_side_trails_prev_high(self):
        from trading.execution import exit_policy as xp
        with mock.patch.object(xp, "choose", return_value="va_trail"):
            xp.assign("10", regime="trend_down", symbol="AKEUSDT")
        with mock.patch("trading.broker_sense.binance_stream.get_mirror",
                        return_value=self._mirror(prev_low=90.0, prev_high=95.0)):
            r1 = xp.evaluate_trail("10", symbol="AKEUSDT", direction="SHORT",
                                   profit_pct=1.0, price=92.0)
            self.assertEqual(r1["trail"], 95.0)
            r2 = xp.evaluate_trail("10", symbol="AKEUSDT", direction="SHORT",
                                   profit_pct=0.2, price=96.0)
        self.assertTrue(r2["exit"])


class TestClosePartial(unittest.TestCase):
    def test_close_partial_derives_amount(self):
        from trading.crypto.engine_client import CryptoEngineClient
        ec = CryptoEngineClient.__new__(CryptoEngineClient)
        cli = mock.Mock()
        cli.status.return_value = [{"pair": "AKE/USDT:USDT", "trade_id": 5,
                                    "amount": 300.0}]
        cli.forceexit.return_value = {"result": "ok"}
        with mock.patch.object(ec, "_client", return_value=cli), \
             mock.patch.object(ec, "_check", side_effect=lambda r, _: r):
            out = ec.close_partial("AKE/USDT:USDT", 0.34)
        self.assertEqual(out, {"result": "ok"})
        self.assertAlmostEqual(cli.forceexit.call_args.kwargs["amount"], 102.0)

    def test_full_fraction_falls_back_to_close_pair(self):
        from trading.crypto.engine_client import CryptoEngineClient
        ec = CryptoEngineClient.__new__(CryptoEngineClient)
        with mock.patch.object(ec, "close_pair",
                               return_value={"result": "full"}) as cp:
            out = ec.close_partial("AKE/USDT:USDT", 1.0)
        self.assertEqual(out, {"result": "full"})
        cp.assert_called_once()


if __name__ == "__main__":
    unittest.main()
