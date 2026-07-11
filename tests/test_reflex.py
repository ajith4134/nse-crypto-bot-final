"""Tests for trading/direction/reflex — R2 Reflex fast lane (tick → order)."""
import tempfile
import unittest
from pathlib import Path

import trading.state as state


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import pullback, reflex
        self.pb = pullback
        self.rx = reflex

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestCrossed(_Iso):
    ROW = {"symbol": "ETH/USDT:USDT", "segment": "futures", "direction": "LONG",
           "ref_price": 100.0, "atr": 2.0}   # dist = 2.0 * 0.5 = 1.0

    def test_long_trigger_runaway_waiting(self):
        self.assertEqual(self.rx.crossed(self.ROW, 99.0), "trigger")
        self.assertEqual(self.rx.crossed(self.ROW, 103.0), "runaway")
        self.assertIsNone(self.rx.crossed(self.ROW, 100.2))

    def test_short_mirror(self):
        row = {**self.ROW, "direction": "SHORT"}
        self.assertEqual(self.rx.crossed(row, 101.0), "trigger")
        self.assertEqual(self.rx.crossed(row, 97.0), "runaway")
        self.assertIsNone(self.rx.crossed(row, 99.8))

    def test_bad_row_is_silent(self):
        self.assertIsNone(self.rx.crossed({"direction": "LONG"}, 1.0))


class TestVenueMapping(_Iso):
    def test_futures_and_spot_symbols(self):
        self.assertEqual(self.rx._venue_sym({"symbol": "ADA/USDT:USDT"}),
                         ("fut", "ADAUSDT"))
        self.assertEqual(self.rx._venue_sym({"symbol": "ADA/USDT"}),
                         ("spot", "ADAUSDT"))

    def test_armed_maps_group_by_venue(self):
        self.pb.arm(symbol="ETH/USDT:USDT", segment="futures", direction="LONG",
                    source="s", ref_price=100.0, atr=2.0)
        self.pb.arm(symbol="ADA/USDT", segment="spot", direction="SHORT",
                    source="s", ref_price=1.0, atr=0.02)
        by_key, streams = self.rx._armed_maps()
        self.assertIn(("fut", "ETHUSDT"), by_key)
        self.assertIn(("spot", "ADAUSDT"), by_key)
        self.assertEqual(streams["fut"], {"ethusdt@bookTicker"})
        self.assertEqual(streams["spot"], {"adausdt@bookTicker"})

    def test_options_rows_excluded(self):
        self.pb.arm(symbol="BTC/USDT:USDT", segment="options", direction="LONG",
                    source="s", ref_price=100.0)
        by_key, streams = self.rx._armed_maps()
        self.assertEqual(by_key, {})
        self.assertEqual(streams["fut"], set())


class TestTickToOrder(_Iso):
    """The injection contract reflex relies on: sweep_pullbacks(price_fn=tick)."""

    class FakeCli:
        def __init__(self):
            self.orders = []

        def tradeable_form(self, s, seg):
            return s

        def place_order(self, **kw):
            self.orders.append(kw)
            return {"ok": True}

    def test_tick_price_fn_fires_only_matching_symbol(self):
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        self.pb.arm(symbol="ETH/USDT:USDT", segment="futures", direction="LONG",
                    source="explore_open_all", ref_price=100.0, atr=2.0)
        self.pb.arm(symbol="SOL/USDT:USDT", segment="futures", direction="LONG",
                    source="explore_open_all", ref_price=50.0, atr=1.0)
        cli = self.FakeCli()
        ex = BrainExecutor(client=cli, segment="futures")
        ex._record_entry_meta = lambda *a, **k: None
        # tick only covers ETH at its trigger price; SOL must stay armed
        rep = ex.sweep_pullbacks(allow_live=False,
                                 price_fn=lambda s: 99.0 if s == "ETH/USDT:USDT" else None)
        self.assertEqual(rep["entered"], ["ETH/USDT:USDT"])
        st = self.pb.status()
        self.assertEqual(st["n_armed"], 1)
        self.assertEqual(st["armed"][0]["symbol"], "SOL/USDT:USDT")
        self.assertEqual(st["stats"]["triggered"], 1)
        self.assertEqual(cli.orders[0]["enter_tag"], "explore_open_all")

    def test_status_carries_reflex_state(self):
        state.save_json("reflex_lane.json", {"enabled": True, "ticks": 42})
        self.assertEqual(self.pb.status()["reflex"]["ticks"], 42)


if __name__ == "__main__":
    unittest.main()
