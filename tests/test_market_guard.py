"""Tests for trading/market_guard + the two execution doors — multi-market isolation
(2026-07-13). A crypto-shaped symbol must NEVER reach the NSE/OpenAlgo door, and an
NSE-shaped symbol must never reach the crypto engine, whatever upstream tagged it."""
import unittest

from trading.market_guard import (CRYPTO, NSE, MarketSymbolMismatch,
                                   assert_market_symbol, market_matches,
                                   market_of_symbol)


class TestClassify(unittest.TestCase):
    def test_crypto_shapes(self):
        for s in ("BTC/USDT:USDT", "BTC/USDT", "ETH/BTC", "ETHUSDT", "SOLUSDC"):
            self.assertEqual(market_of_symbol(s), CRYPTO, s)

    def test_nse_shapes(self):
        for s in ("NSE:RELIANCE", "BSE:TCS", "NFO:NIFTY", "BFO:SENSEX", "MCX:GOLD"):
            self.assertEqual(market_of_symbol(s), NSE, s)

    def test_ambiguous_bare_tickers_are_none(self):
        # bare bases could belong to either market → never guess-block them
        for s in ("BTC", "RELIANCE", "NIFTY31JUL24C24000", "GOLD05AUG26FUT", ""):
            self.assertIsNone(market_of_symbol(s), s)


class TestMatch(unittest.TestCase):
    def test_crypto_symbol_blocked_from_nse(self):
        self.assertFalse(market_matches("NSE", "BTC/USDT:USDT"))
        self.assertFalse(market_matches("nse", "ETHUSDT"))

    def test_nse_symbol_blocked_from_crypto(self):
        self.assertFalse(market_matches("CRYPTO", "NSE:RELIANCE"))
        self.assertFalse(market_matches("crypto", "BFO:SENSEX"))

    def test_right_market_passes(self):
        self.assertTrue(market_matches("CRYPTO", "BTC/USDT:USDT"))
        self.assertTrue(market_matches("NSE", "NSE:RELIANCE"))

    def test_ambiguous_never_blocks(self):
        self.assertTrue(market_matches("NSE", "RELIANCE"))
        self.assertTrue(market_matches("CRYPTO", "BTC"))       # honest: don't guess-block

    def test_assert_raises_on_mismatch(self):
        with self.assertRaises(MarketSymbolMismatch):
            assert_market_symbol("NSE", "BTC/USDT:USDT")
        with self.assertRaises(MarketSymbolMismatch):
            assert_market_symbol("CRYPTO", "NSE:RELIANCE")
        assert_market_symbol("CRYPTO", "BTC/USDT:USDT")        # no raise
        assert_market_symbol("NSE", "RELIANCE")                # ambiguous → no raise


class TestExecAdapterDoor(unittest.TestCase):
    """The single crypto/NSE execution door rejects a cross-market symbol before placing."""

    def _adapter(self):
        from trading.broker_sense.exec_adapter import ExecAdapter

        class _Cli:                                            # records any order it's asked to place
            def __init__(self): self.calls = []
            def place_order(self, **kw): self.calls.append(kw); return {"orderid": "x"}
            def close_pair(self, *a, **k): pass
        cc, nc = _Cli(), _Cli()
        return ExecAdapter(crypto_client=cc, nse_client=nc), cc, nc

    def test_crypto_symbol_never_reaches_nse_door(self):
        adap, cc, nc = self._adapter()
        res = adap.place(market="NSE", symbol="BTC/USDT:USDT", action="BUY")
        self.assertFalse(res.get("placed"))
        self.assertIn("blocked", res)
        self.assertEqual(nc.calls, [])                         # OpenAlgo/Kite never called

    def test_uppercase_crypto_tag_still_routes_crypto(self):
        # regression: "CRYPTO" (uppercase) used to fall through the == "crypto" check → NSE door
        adap, cc, nc = self._adapter()
        res = adap.place(market="CRYPTO", symbol="BTC/USDT:USDT", action="BUY")
        self.assertTrue(res.get("placed"))
        self.assertEqual(len(cc.calls), 1)                     # crypto engine, not NSE
        self.assertEqual(nc.calls, [])

    def test_nse_symbol_never_reaches_crypto_engine(self):
        adap, cc, nc = self._adapter()
        res = adap.place(market="CRYPTO", symbol="NSE:RELIANCE", action="BUY")
        self.assertFalse(res.get("placed"))
        self.assertEqual(cc.calls, [])


class TestInstrumentKey(unittest.TestCase):
    def test_detects_upstox_instrument_keys(self):
        from trading.market_guard import is_instrument_key
        for k in ("NSE_FO|51380", "BSE_INDEX|SENSEX", "NSE_EQ|INE002A01018"):
            self.assertTrue(is_instrument_key(k), k)
        for s in ("RELIANCE", "NIFTY", "BTC/USDT:USDT", "SENSEX"):
            self.assertFalse(is_instrument_key(s), s)

    def test_exec_adapter_blocks_instrument_key_to_nse(self):
        from trading.broker_sense.exec_adapter import ExecAdapter

        class _Boom:
            def place_order(self, **k):
                raise AssertionError("OpenAlgo must not get an instrument key")
        adap = ExecAdapter(crypto_client=object(), nse_client=_Boom())
        res = adap.place(market="NSE", symbol="NSE_FO|51380", action="BUY")
        self.assertFalse(res.get("placed"))
        self.assertIn("instrument-key", res.get("blocked", ""))


if __name__ == "__main__":
    unittest.main()
