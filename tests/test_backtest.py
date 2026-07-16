"""B4 regression tests for per-trade return extraction in strategy backtests."""
import unittest



class TestSegmentTradeReturns(unittest.TestCase):
    """B4 regression (2026-07-16): short winners must be POSITIVE per-trade returns.
    vectorbt from_orders(targetpercent) trade records inverted shorts — a 60% short-only
    oracle showed 41.5% positive trades while its equity rose; the DSR ran on that
    corrupted series and promoted 0 candidates ever."""

    def test_short_winner_is_positive(self):
        from trading.strategy.backtest import _segment_trades
        import numpy as np
        close = np.array([100.0, 95.0, 90.0, 90.0])
        target = np.array([-1, -1, -1, 0])      # short 100 -> 90
        tr = _segment_trades(target, close, cost_rate=0.0003)
        self.assertEqual(len(tr), 1)
        self.assertEqual(tr[0]["side"], -1)
        self.assertAlmostEqual(tr[0]["ret"], 0.10 - 0.0006, places=6)

    def test_long_loser_is_negative_and_segments_split(self):
        from trading.strategy.backtest import _segment_trades
        import numpy as np
        close = np.array([100.0, 98.0, 98.0, 100.0, 103.0])
        target = np.array([1, 1, 0, -1, -1])
        tr = _segment_trades(target, close, cost_rate=0.0)
        self.assertEqual([t["side"] for t in tr], [1, -1])
        self.assertAlmostEqual(tr[0]["ret"], -0.02, places=6)   # long 100->98
        self.assertAlmostEqual(tr[1]["ret"], -0.03, places=6)   # short 100->103 loses

    def test_backtest_signal_mean_ret_sign_matches_equity(self):
        """Directional consistency on a short-only winner series end-to-end."""
        import numpy as np
        import pandas as pd
        from trading.strategy.backtest import backtest_signal
        n = 300
        close = pd.Series(100.0 * np.exp(-0.001 * np.arange(n)))   # steady downtrend
        df = pd.DataFrame({"close": close})
        sig = pd.Series([-1] * n)
        res = backtest_signal(sig, df)
        rets = [t["ret"] for t in res.trades]
        self.assertGreater(res.metrics["total_return"], 0)
        self.assertGreater(sum(rets), 0)                            # no sign inversion


if __name__ == "__main__":
    unittest.main()
