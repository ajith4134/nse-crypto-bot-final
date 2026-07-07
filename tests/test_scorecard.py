"""Regression tests for the segment scorecard's (market, segment) derivation
(dashboard/server.py:_trade_segment) — the grouping key for /api/trading/scorecard."""

import importlib.util
import os
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_server():
    spec = importlib.util.spec_from_file_location(
        "dash_server_test", os.path.join(_ROOT, "dashboard", "server.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestTradeSegment(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seg = staticmethod(_load_server()._trade_segment)

    def _check(self, row, expect):
        self.assertEqual(self.seg(row), expect)

    def test_crypto_futures(self):
        self._check({"exchange": "binance", "instrument_type": "PERP",
                     "symbol": "BTC/USDT:USDT"}, ("CRYPTO", "futures"))

    def test_crypto_spot(self):
        self._check({"exchange": "binance", "instrument_type": "SPOT",
                     "symbol": "BTC/USDT"}, ("CRYPTO", "spot"))
        # no instrument_type → spot inferred from the pair shape (no settle suffix)
        self._check({"exchange": "binance", "symbol": "ETH/USDT"}, ("CRYPTO", "spot"))

    def test_crypto_options(self):
        self._check({"exchange": "deribit", "instrument_type": "OPT",
                     "symbol": "AVAX/USDC:USDC-260703-6.4-P"}, ("CRYPTO", "options"))
        self._check({"exchange": "binance", "instrument_type": "",
                     "symbol": "BTC/USDC:USDC-260703-60000-C"}, ("CRYPTO", "options"))

    def test_prediction_is_its_own_market(self):
        self._check({"exchange": "predictionpaper",
                     "symbol": "WILL-USA-WIN-THE-2026-FIFA-WORLD-CUP-467/USDC"},
                    ("PREDICTION", "prediction"))
        self._check({"exchange": "binance", "symbol": "PRED:fifwc-esp-aut"},
                    ("PREDICTION", "prediction"))

    def test_nse_segments(self):
        self._check({"exchange": "NSE", "instrument_type": "EQ", "symbol": "RELIANCE"},
                    ("NSE", "intraday"))
        self._check({"exchange": "NSE", "instrument_type": "CE",
                     "symbol": "NIFTY25JUL25000CE"}, ("NSE", "options"))
        self._check({"exchange": "NSE", "instrument_type": "FUTSTK",
                     "symbol": "RELIANCE25JULFUT"}, ("NSE", "futures"))
        self._check({"exchange": "MCX", "instrument_type": "FUT",
                     "symbol": "GOLDM25JULFUT"}, ("NSE", "commodities"))
        self._check({"exchange": "NSE", "instrument_type": "EQ", "product_type": "MTF",
                     "symbol": "TCS"}, ("NSE", "mtf"))


if __name__ == "__main__":
    unittest.main()
