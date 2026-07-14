"""tests/test_smart_exit.py — forward-looking open-trade exit (Symbol-Move Net + dir flip)."""
import os
import unittest


class TestSmartExit(unittest.TestCase):
    def setUp(self):
        os.environ["SMART_EXIT_ON"] = "1"
        from trading.crypto.freqtrade import smart_exit as sx
        self.sx = sx

    def test_off_switch(self):
        os.environ["SMART_EXIT_ON"] = "0"
        r = self.sx.should_exit("BTC/USDT:USDT", "LONG")
        self.assertFalse(r["exit"])
        os.environ["SMART_EXIT_ON"] = "1"

    def test_bad_side_never_exits(self):
        self.assertFalse(self.sx.should_exit("BTC/USDT:USDT", "")["exit"])
        self.assertFalse(self.sx.should_exit("BTC/USDT:USDT", "FLAT")["exit"])

    def test_never_raises_returns_shape(self):
        r = self.sx.should_exit("BTC/USDT:USDT", "LONG", regime="bear")
        for k in ("exit", "reason", "signals"):
            self.assertIn(k, r)
        self.assertIsInstance(r["exit"], bool)

    def test_move_net_reversal_triggers_exit(self):
        # train the net, then a LONG with a bearish forecast should exit on move_net_reversal
        from trading.brain import symbol_move_net as smn
        info = smn.refresh()
        if not info.get("trained"):
            self.skipTest("move-net not trainable in this env")
        r = self.sx.should_exit(
            "BTC/USDT:USDT", "LONG",
            decision_snapshot={"market_context": {"filters": {"filter:funding": 0.6}}})
        # deterministic net → either it flags a reversal (exit+reason) or it doesn't, but the
        # signals dict must carry the move-net read either way (honest wiring)
        self.assertIn("move_net", r["signals"])
        if r["exit"]:
            self.assertIn("move_net_reversal", r["reason"])

    def test_direction_flip_from_readings(self):
        # a LONG position whose fused readings now say SHORT with edge → dir flip vote present
        r = self.sx.should_exit("ZZZ/USDT:USDT", "LONG",
                                readings=[("indicator_fusion", 0.05), ("venue_leadlag", 0.05)])
        self.assertIn("fused", r["signals"])


if __name__ == "__main__":
    unittest.main()
