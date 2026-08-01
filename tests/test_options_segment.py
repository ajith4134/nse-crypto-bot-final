"""Options-segment regressions (2026-07-10).

Three stacked bugs hid each other and made the options segment look alive while
opening nothing (or the wrong thing):
  1. Funnel.executor() cached one executor for all segments (tests in
     test_broker_sense.TestExecutorPerSegment).
  2. The tradeability guard validated option contracts against ccxt spot/swap
     markets — every legitimate option entry was silently vetoed.
  3. _run_options_cycle counted refused orders as "entered" (phantom logging),
     and market-entered hollow books (first real fill: ask 300.0 / bid 0.2 →
     stop_loss -99.9% in 5 seconds).
"""
from __future__ import annotations

import unittest
from unittest import mock


class TestOptionsTradeabilityGuard(unittest.TestCase):
    def setUp(self):
        from trading.crypto.engine_client import CryptoEngineClient
        self.cli = CryptoEngineClient.__new__(CryptoEngineClient)
        CryptoEngineClient._MARKETS_CACHE.clear()
        self.addCleanup(CryptoEngineClient._MARKETS_CACHE.clear)

    def test_options_validate_against_segment_whitelist(self):
        wl = {"whitelist": ["ETH/USDC:USDC-260710-1600-C"]}
        seg_client = mock.Mock()
        seg_client.whitelist.return_value = wl
        with mock.patch.object(type(self.cli), "_client", return_value=seg_client):
            self.assertTrue(
                self.cli._pair_tradeable("ETH/USDC:USDC-260710-1600-C", "options"))
            self.assertFalse(
                self.cli._pair_tradeable("BTC/USDC:USDC-260101-1-P", "options"))
        seg_client.whitelist.assert_called_once()      # second lookup hit the cache

    def test_empty_whitelist_fails_open_and_is_not_cached(self):
        seg_client = mock.Mock()
        seg_client.whitelist.return_value = {"whitelist": []}
        with mock.patch.object(type(self.cli), "_client", return_value=seg_client):
            self.assertTrue(self.cli._pair_tradeable("ANY", "options"))
        self.assertNotIn("options", type(self.cli)._MARKETS_CACHE)


def _bare_executor():
    """A BrainExecutor shell with only what _run_options_cycle touches."""
    from trading.crypto.freqtrade.brain_executor import BrainExecutor
    ex = BrainExecutor.__new__(BrainExecutor)
    cli = mock.Mock()
    cli.open_pairs.return_value = []
    ex.client = lambda: cli
    ex.symbols = lambda: ["ETH/USDC:USDC-260710-1600-C"]
    ex.decider = mock.Mock()
    ex.decider.decide.return_value = {"action": "LONG"}
    return ex, cli


class TestOptionsCycleHonesty(unittest.TestCase):
    def test_refused_order_is_skipped_not_entered(self):
        ex, cli = _bare_executor()
        cli.place_order.return_value = {"ok": False, "guard": "tradeability"}
        with mock.patch.object(type(ex), "_option_book_ok", return_value=True):
            res = ex._run_options_cycle(allow_live=False)
        self.assertEqual(res["entered"], [])
        self.assertEqual(res["skipped"], 1)

    def test_accepted_order_counts_as_entered(self):
        ex, cli = _bare_executor()
        cli.place_order.return_value = {"trade_id": 1, "is_open": True}
        with mock.patch.object(type(ex), "_option_book_ok", return_value=True):
            res = ex._run_options_cycle(allow_live=False)
        self.assertEqual(res["entered"], ["ETH/USDC:USDC-260710-1600-C"])

    def test_hollow_book_skips_before_any_order(self):
        ex, cli = _bare_executor()
        with mock.patch.object(type(ex), "_option_book_ok", return_value=False):
            res = ex._run_options_cycle(allow_live=False)
        cli.place_order.assert_not_called()
        self.assertEqual(res["entered"], [])
        self.assertEqual(res["skipped"], 1)


class TestOptionBookGuard(unittest.TestCase):
    def _guard(self, bids, asks, env=None):
        # 2026-07-23: the guard reads Binance's own eapi book via binance_options.option_book
        # since the 2026-07-13 rewrite (ccxt.deribit returned empty books for Binance symbols).
        # The old ccxt mock was dead — the real network call ran and failed the tight-book case.
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        ex = BrainExecutor.__new__(BrainExecutor)
        bid = float(bids[0][0]) if bids else 0.0
        ask = float(asks[0][0]) if asks else 0.0
        bk = (bid, ask) if (bids or asks) else None
        with mock.patch("trading.broker_sense.binance_options.option_book",
                        return_value=bk), \
             mock.patch.object(BrainExecutor, "_to_binance_option",
                               return_value="ETH-260710-1600-C"), \
             mock.patch.dict("os.environ", env or {}, clear=False):
            return ex._option_book_ok("ETH/USDC:USDC-260710-1600-C")

    def test_hollow_book_refused(self):
        self.assertFalse(self._guard(bids=[[0.2, 1]], asks=[[300.0, 1]]))

    def test_no_bid_refused(self):
        self.assertFalse(self._guard(bids=[], asks=[[300.0, 1]]))

    def test_tight_book_accepted(self):
        self.assertTrue(self._guard(bids=[[100.0, 1]], asks=[[105.0, 1]]))

    def test_kill_switch_disables_guard(self):
        self.assertTrue(self._guard(bids=[], asks=[],
                                    env={"OPTIONS_LIQ_GUARD": "0"}))


if __name__ == "__main__":
    unittest.main()
