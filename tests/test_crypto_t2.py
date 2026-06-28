"""Trading Phase T2 (Crypto Foundation) acceptance tests — fully offline.

Exercises all network-INDEPENDENT logic so CI passes without exchange access:
config, liquidation math, order-book fill walking, paper position/PnL accounting,
funding-spread logic, and watchlist persistence. Live ccxt paths are verified by
run_crypto_trading.py against real public data.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trading.state as state
from trading.crypto.config import CryptoConfig, ExchangeKeys
from trading.crypto.funding import Funding, FundingMonitor
from trading.crypto.liquidation import distance_to_liquidation, liquidation_price
from trading.crypto.paper_engine import PaperEngine, walk_order_book
from trading.crypto.watchlist import CryptoWatchlist


# A simple symmetric book around 100.0
BOOK = {
    "asks": [[100.0, 1.0], [101.0, 2.0], [102.0, 5.0]],
    "bids": [[99.0, 1.0], [98.0, 2.0], [97.0, 5.0]],
}


class TestConfig(unittest.TestCase):
    def test_keys_optional_and_redacted(self):
        cfg = CryptoConfig(mode="paper", exchanges=("binance", "bybit"),
                           default_exchange="binance", quote="USDT",
                           _keys={"binance": ExchangeKeys("binance", "k", "s"),
                                  "bybit": ExchangeKeys("bybit")})
        self.assertTrue(cfg.has_keys("binance"))
        self.assertFalse(cfg.has_keys("bybit"))
        # status must not leak secret values
        self.assertNotIn("'s'", str(cfg.as_status()))
        self.assertEqual(cfg.as_status()["keys_present"], {"binance": True, "bybit": False})


class TestLiquidation(unittest.TestCase):
    def test_long_below_short_above_entry(self):
        ll = liquidation_price(side="long", entry_price=100.0, leverage=10, mmr=0.005)
        ls = liquidation_price(side="short", entry_price=100.0, leverage=10, mmr=0.005)
        # long: 100*(1-0.1+0.005)=90.5 ; short: 100*(1+0.1-0.005)=109.5
        self.assertAlmostEqual(ll, 90.5, places=6)
        self.assertAlmostEqual(ls, 109.5, places=6)

    def test_higher_leverage_closer_liq(self):
        low = liquidation_price(side="long", entry_price=100.0, leverage=2)
        high = liquidation_price(side="long", entry_price=100.0, leverage=50)
        self.assertLess(100 - high, 100 - low)  # 50x liquidates closer to entry

    def test_cross_pushes_liq_further(self):
        iso = liquidation_price(side="long", entry_price=100.0, leverage=10, margin_mode="isolated")
        cross = liquidation_price(side="long", entry_price=100.0, leverage=10,
                                  margin_mode="cross", extra_margin_ratio=0.2)
        self.assertLess(cross, iso)  # more collateral => lower (further) long liq

    def test_distance(self):
        d = distance_to_liquidation(side="long", mark_price=100.0, liq_price=90.0)
        self.assertAlmostEqual(d, 0.10, places=6)


class TestOrderBookFill(unittest.TestCase):
    def test_buy_walks_asks_with_slippage(self):
        f = walk_order_book("buy", 2.0, BOOK)  # 1@100 + 1@101
        self.assertTrue(f.fully_filled)
        self.assertAlmostEqual(f.avg_price, 100.5, places=6)
        self.assertGreater(f.slippage, 0)
        self.assertEqual(f.levels, 2)

    def test_sell_walks_bids(self):
        f = walk_order_book("sell", 1.0, BOOK)  # 1@99
        self.assertAlmostEqual(f.avg_price, 99.0, places=6)

    def test_partial_fill_when_thin(self):
        thin = {"asks": [[100.0, 0.5]], "bids": []}
        f = walk_order_book("buy", 2.0, thin)
        self.assertFalse(f.fully_filled)
        self.assertAlmostEqual(f.filled, 0.5, places=6)


class TestPaperEngine(unittest.TestCase):
    def test_open_increase_close_pnl(self):
        eng = PaperEngine(starting_balance=100_000.0)
        # Open long 1 BTC @ avg 100.5
        r1 = eng.market_order(symbol="BTC/USDT", exchange="binance", side="buy",
                              amount=1.0, order_book=BOOK, leverage=10)
        self.assertEqual(r1["status"], "filled")
        pos = eng.positions()[0]
        self.assertEqual(pos["side"], "long")
        self.assertAlmostEqual(pos["size"], 1.0, places=6)
        self.assertAlmostEqual(pos["margin"], pos["notional"] / 10, places=6)
        # Close by selling 1 BTC into bids (avg 99) => realised loss vs ~100.5 entry
        r2 = eng.market_order(symbol="BTC/USDT", exchange="binance", side="sell",
                              amount=1.0, order_book=BOOK, leverage=10)
        self.assertTrue(r2.get("closed"))
        self.assertLess(eng.realized_pnl, 0)         # bought high, sold low
        self.assertEqual(len(eng.positions()), 0)    # flat

    def test_flip_position(self):
        eng = PaperEngine()
        eng.market_order(symbol="BTC/USDT", exchange="binance", side="buy",
                         amount=1.0, order_book=BOOK, leverage=5)
        # Sell 2 => close 1 long, open 1 short
        r = eng.market_order(symbol="BTC/USDT", exchange="binance", side="sell",
                             amount=2.0, order_book=BOOK, leverage=5)
        self.assertTrue(r.get("flipped"))
        self.assertEqual(eng.positions()[0]["side"], "short")

    def test_liquidation_in_position_view(self):
        eng = PaperEngine()
        eng.market_order(symbol="BTC/USDT", exchange="binance", side="buy",
                         amount=1.0, order_book=BOOK, leverage=10, margin_mode="isolated")
        pos = eng.positions()[0]
        self.assertLess(pos["liquidation_price"], pos["entry_price"])  # long liq below entry


class TestFundingSpread(unittest.TestCase):
    def test_best_spread_picks_extremes(self):
        rates = [Funding("binance", "BTC/USDT:USDT", 0.0001, None),
                 Funding("bybit", "BTC/USDT:USDT", 0.0005, None),
                 Funding("okx", "BTC/USDT:USDT", -0.0002, None)]
        spread = FundingMonitor.best_spread(rates)
        self.assertEqual(spread["short_funding_exchange"], "bybit")   # highest rate
        self.assertEqual(spread["long_funding_exchange"], "okx")      # lowest rate
        self.assertAlmostEqual(spread["spread"], 0.0007, places=6)

    def test_none_when_single(self):
        self.assertIsNone(FundingMonitor.best_spread([Funding("binance", "X", 0.0001, None)]))


class TestCryptoWatchlist(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        state.STATE_DIR = self._orig
        self._tmp.cleanup()

    def test_add_remove_persist(self):
        wl = CryptoWatchlist()
        self.assertTrue(wl.add("BTC/USDT", "binance"))
        self.assertFalse(wl.add("btc/usdt", "binance"))   # dedup
        self.assertEqual(len(wl), 1)
        wl2 = CryptoWatchlist()                            # reload from disk
        self.assertEqual(len(wl2), 1)
        self.assertTrue(wl2.remove("BTC/USDT", "binance"))
        self.assertEqual(len(CryptoWatchlist()), 0)


if __name__ == "__main__":
    unittest.main()
