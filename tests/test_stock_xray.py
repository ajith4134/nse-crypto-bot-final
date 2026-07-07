"""Tests for the Stock X-Ray pure analytics (no network): exchange routing, zones, depth, candles."""
import unittest

from trading.broker_sense.stock_xray import (
    _is_option, _opt_exchange, _to_list_candles, _slim_candle,
    demand_supply_zones, depth_imbalance, circuit_bands,
)


class TestExchangeRouting(unittest.TestCase):
    def test_equity_ending_ce_is_not_option(self):
        self.assertFalse(_is_option("RELIANCE", "intraday"))     # RELIAN-CE trap
        self.assertEqual(_opt_exchange("RELIANCE", "NSE", "intraday"), "NSE")

    def test_real_option(self):
        self.assertTrue(_is_option("NIFTY07JUL2624500CE", "options"))
        self.assertEqual(_opt_exchange("NIFTY07JUL2624500CE", "NSE", "options"), "NFO")

    def test_bse_index_option_routes_bfo(self):
        self.assertEqual(_opt_exchange("SENSEX09JUL2678600CE", "NSE", "options"), "BFO")

    def test_digit_before_ce_required(self):
        self.assertTrue(_is_option("INFY28JUL261080CE", "intraday"))   # 0-CE (digit) → option
        self.assertFalse(_is_option("ACE", "intraday"))                # no digit → not


class TestCandleConversion(unittest.TestCase):
    def test_dict_to_list(self):
        rows = [{"timestamp": 1, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 100}]
        self.assertEqual(_to_list_candles(rows), [[1, 10.0, 12.0, 9.0, 11.0, 100.0]])

    def test_slim_candle_json_safe(self):
        c = _slim_candle({"timestamp": 1783395900, "open": 10, "high": 12, "low": 9, "close": 11, "volume": 5})
        self.assertEqual(c, {"t": 1783395900, "o": 10.0, "h": 12.0, "l": 9.0, "c": 11.0, "v": 5.0})


class TestZones(unittest.TestCase):
    def test_swing_zones(self):
        # build candles with a clear swing high (resistance) and low (support)
        base = [{"high": 100 + (i % 5), "low": 90 - (i % 5), "close": 95} for i in range(60)]
        base[30] = {"high": 120, "low": 95, "close": 95}       # swing high above price
        base[45] = {"high": 96, "low": 70, "close": 95}        # swing low below price
        z = demand_supply_zones(base)
        self.assertTrue(z["available"])
        self.assertTrue(any(s["level"] >= 95 for s in z["supply"]))
        self.assertTrue(any(d["level"] <= 95 for d in z["demand"]))

    def test_too_few_candles(self):
        self.assertFalse(demand_supply_zones([{"high": 1, "low": 1, "close": 1}])["available"])


class TestDepthAndCircuit(unittest.TestCase):
    def test_depth_imbalance(self):
        d = {"data": {"totalbuyqty": 300, "totalsellqty": 100,
                      "bids": [{"price": 10, "quantity": 5}], "asks": [{"price": 11, "quantity": 3}]}}
        r = depth_imbalance(d)
        self.assertEqual(r["imbalance"], 0.5)                  # (300-100)/400
        self.assertEqual(r["best_bid"], 10.0)

    def test_circuit_bands(self):
        c = circuit_bands({"prev_close": 100})
        self.assertEqual(c["upper_circuit"], 110.0)
        self.assertEqual(c["lower_circuit"], 90.0)


if __name__ == "__main__":
    unittest.main()
