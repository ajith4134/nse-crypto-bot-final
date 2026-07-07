"""W1 goal scoreboard tests — synthetic journal rows in an isolated STATE_DIR."""
import os
import tempfile
import time
import unittest
from unittest import mock


def _row(pnl, days_ago=1.0, exchange="binance", seg="futures", it="PERP",
         sym="BTC/USDT:USDT"):
    ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time() - days_ago * 86400))
    return {"exchange": exchange, "bot_segment": seg, "instrument_type": it,
            "symbol": sym, "net_pnl": pnl, "exit_datetime": ts, "entry_datetime": ts}


class GoalScoreboardTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from pathlib import Path

        from trading import state
        self._patch = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._patch.start()

    def tearDown(self):
        self._patch.stop()
        self._tmp.cleanup()

    def test_segment_goal_merges_defaults(self):
        from trading import goal
        g = goal.segment_goal("crypto", "futures")
        self.assertIn("target_return_30d", g)
        self.assertIn("one_variable_only", g)
        self.assertGreater(g["capital_base"], 0)

    def test_score_trade_sign_and_pace(self):
        from trading import goal
        s = goal.score_trade(_row(50.0))
        self.assertTrue(s["toward_goal"])
        self.assertGreater(s["goal_score"], 0)
        s2 = goal.score_trade(_row(-50.0))
        self.assertFalse(s2["toward_goal"])
        self.assertLess(s2["goal_score"], 0)

    def test_scoreboard_verdicts(self):
        from trading import goal
        g = goal.segment_goal("crypto", "futures")
        base, target = g["capital_base"], g["target_return_30d"]
        # goal-met: pnl over the window >= target
        rows = [_row(base * target / 4, days_ago=d) for d in (1, 3, 5, 7)]
        sb = goal.scoreboard(trades=rows)
        seg = sb["segments"]["crypto.futures"]
        self.assertEqual(seg["verdict"], "goal-met")
        self.assertEqual(seg["n_trades"], 4)
        # failing: return at/below failure_below
        rows = [_row(base * g["failure_below"], days_ago=2)]
        sb = goal.scoreboard(trades=rows)
        self.assertEqual(sb["segments"]["crypto.futures"]["verdict"], "failing")
        # no-data segments still listed honestly
        self.assertEqual(sb["segments"]["nse.equity"]["verdict"], "no-data")
        self.assertEqual(sb["segments"]["nse.equity"]["n_trades"], 0)

    def test_snapshot_persisted(self):
        from trading import goal
        goal.scoreboard(trades=[_row(10.0)])
        snap = goal.last_scoreboard()
        self.assertIn("segments", snap)
        self.assertIn("crypto.futures", snap["segments"])

    def test_old_trades_excluded_from_window(self):
        from trading import goal
        sb = goal.scoreboard(trades=[_row(1000.0, days_ago=45)])
        self.assertEqual(sb["segments"]["crypto.futures"]["n_trades"], 0)


if __name__ == "__main__":
    unittest.main()
