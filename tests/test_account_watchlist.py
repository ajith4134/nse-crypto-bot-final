"""Tests for the Brain-Open account-watchlist sync + human-UI JSON parsing (pure logic)."""
import unittest

from trading.broker_sense.account_watchlist import plan_sync
from trading.brain.vision.human_ui import _extract_json


class TestPlanSync(unittest.TestCase):
    def test_add_new_open_trades(self):
        p = plan_sync(desired=["RELIANCE", "INFY"], already=["RELIANCE"])
        self.assertEqual(p["add"], ["INFY"])
        self.assertEqual(p["remove"], [])

    def test_remove_closed_trades(self):
        p = plan_sync(desired=["RELIANCE"], already=["RELIANCE", "TCS"])
        self.assertEqual(p["add"], [])
        self.assertEqual(p["remove"], ["TCS"])

    def test_add_and_remove_together(self):
        p = plan_sync(desired=["A", "B"], already=["B", "C"])
        self.assertEqual(p["add"], ["A"])
        self.assertEqual(p["remove"], ["C"])
        self.assertEqual(p["unchanged"], ["B"])

    def test_in_sync_is_noop(self):
        p = plan_sync(desired=["A", "B"], already=["B", "A"])
        self.assertEqual(p["add"], [])
        self.assertEqual(p["remove"], [])

    def test_dedup_and_order_stable(self):
        p = plan_sync(desired=["A", "A", "B"], already=[])
        self.assertEqual(p["target"], ["A", "B"])
        self.assertEqual(p["add"], ["A", "B"])

    def test_empty_desired_removes_all(self):
        p = plan_sync(desired=[], already=["A", "B"])
        self.assertEqual(p["remove"], ["A", "B"])


class TestVisionJsonParse(unittest.TestCase):
    def test_plain_json_object(self):
        self.assertEqual(_extract_json('{"found": true, "x": 5, "y": 9}'),
                         {"found": True, "x": 5, "y": 9})

    def test_fenced_json(self):
        self.assertEqual(_extract_json('```json\n["A","B"]\n```'), ["A", "B"])

    def test_json_embedded_in_prose(self):
        self.assertEqual(_extract_json('Sure! Here it is: {"found": false} — hope that helps'),
                         {"found": False})

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_json("no json here"))
        self.assertIsNone(_extract_json(""))


class TestBinanceFavoritesMirror(unittest.TestCase):
    """The crypto twin (binance_watchlist): pair mapping, segment gating, star idempotency,
    write gate. STATE_DIR-isolated; engine/boss/eyes stubbed."""

    def setUp(self):
        import tempfile
        from pathlib import Path

        import trading.state as tstate
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        import trading.state as tstate
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()

    def test_pair_to_binance_symbol(self):
        from trading.broker_sense.binance_watchlist import _flat
        self.assertEqual(_flat("BEL/USDT:USDT"), "BELUSDT")
        self.assertEqual(_flat("BTC/USDT"), "BTCUSDT")
        self.assertEqual(_flat(""), "")

    def test_open_symbols_obey_segment_focus(self):
        from unittest import mock

        from trading.broker_sense import binance_watchlist as bw
        cli = mock.Mock()
        cli.open_pairs.side_effect = lambda segment: {
            "futures": ["BEL/USDT:USDT"], "spot": ["SCRT/USDT"]}.get(segment, [])
        with mock.patch("trading.brain.boss.active_segments",
                        return_value=["futures"]), \
             mock.patch("trading.crypto.engine_client.CryptoEngineClient",
                        return_value=cli):
            out = bw.open_crypto_symbols()
        self.assertEqual(list(out), ["BELUSDT"])          # spot gated OFF by boss
        self.assertEqual(out["BELUSDT"]["segment"], "futures")

    def test_apply_sync_gated_without_write_flag(self):
        import os
        from unittest import mock

        from trading.broker_sense import binance_watchlist as bw
        os.environ.pop("BROKER_WATCHLIST_WRITE", None)
        with mock.patch.object(bw, "open_crypto_symbols",
                               return_value={"BELUSDT": {"pair": "BEL/USDT:USDT",
                                                         "segment": "futures"}}):
            rep = bw.apply_sync(sessions=object())
        self.assertIn("gated", rep["error"])
        self.assertEqual(rep["added"], [])

    def test_set_star_is_idempotent(self):
        from unittest import mock

        from trading.broker_sense.binance_watchlist import _set_star
        ui = mock.Mock()
        ui.read.return_value = "filled"                   # already a favorite
        self.assertTrue(_set_star(ui, "BELUSDT", True))
        ui.click.assert_not_called()                      # no needless click

    def test_set_star_confirms_after_click(self):
        from unittest import mock

        from trading.broker_sense.binance_watchlist import _set_star
        ui = mock.Mock()
        ui.read.side_effect = ["empty", "filled"]         # before → after the click
        ui.click.return_value = True
        self.assertTrue(_set_star(ui, "BELUSDT", True))
        ui.click.assert_called_once()

    def test_set_star_never_fakes_success(self):
        from unittest import mock

        from trading.broker_sense.binance_watchlist import _set_star
        ui = mock.Mock()
        ui.read.side_effect = ["empty", "empty"]          # click didn't take
        ui.click.return_value = True
        self.assertFalse(_set_star(ui, "BELUSDT", True))

    def test_star_click_target_passes_the_order_guard(self):
        """2026-07-10 regression: the target's own '(NOT any Buy/Sell/Trade button)'
        clause tripped the order-guard regex — every favorites ADD was silently
        BLOCKED. The wording sent to ui.click must never contain order verbs."""
        from unittest import mock

        from trading.brain.vision.computer_use import _control_forbidden
        from trading.broker_sense.binance_watchlist import _set_star
        ui = mock.Mock()
        ui.read.side_effect = ["empty", "filled"]
        ui.click.return_value = True
        self.assertTrue(_set_star(ui, "ARPAUSDT", True))
        target = ui.click.call_args[0][0]
        self.assertFalse(_control_forbidden(target),
                         f"star click target trips the order-guard: {target!r}")


if __name__ == "__main__":
    unittest.main()
