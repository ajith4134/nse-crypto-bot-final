"""W7 track record + rule-of-three tests — isolated STATE_DIR."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TrackRecordTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def test_bump_and_report(self):
        from trading.brain import track_record as tr
        for i in range(12):
            tr.bump("strategy:meanrev", kind="strategy", win=(i % 3 != 0))
        rc = tr.report_card()
        row = rc["actors"][0]
        self.assertEqual(row["actor"], "strategy:meanrev")
        self.assertEqual(row["runs"], 12)
        self.assertEqual(row["wins"], 8)

    def test_unproven_trust_neutral(self):
        from trading.brain import track_record as tr
        tr.bump("scout:new", kind="scout")
        t = tr.trust("scout:new")
        self.assertEqual(t["trust"], 1.0)
        self.assertEqual(t["label"], "unproven")

    def test_trust_follows_record(self):
        from trading.brain import track_record as tr
        for i in range(120):
            tr.bump("strategy:winner", win=(i % 4 != 0))     # 75% WR
        t = tr.trust("strategy:winner")
        self.assertEqual(t["label"], "proven")
        self.assertGreater(t["trust"], 1.2)

    def test_rule_of_three(self):
        from trading.brain import track_record as tr
        self.assertFalse(tr.rule_of_three("optimizer:newbie")["allowed"])
        for _ in range(3):
            tr.mark_supervised_success("optimizer:newbie")
        r = tr.rule_of_three("optimizer:newbie")
        self.assertTrue(r["allowed"])

    def test_journal_bumps_strategy_record(self):
        from trading.brain import track_record as tr
        from trading.journal import ClosedTrade, TradeJournal
        j = TradeJournal(state_file="j.json", persist=True)
        j.record(ClosedTrade(trade_id="T1", symbol="BTC/USDT:USDT",
                             exchange="binance", instrument_type="PERP",
                             direction="LONG", strategy_name="meanrev_zscore",
                             entry_datetime="2026-07-07 10:00:00",
                             exit_datetime="2026-07-07 11:00:00",
                             quantity=1.0, entry_price=100.0, exit_price=101.0))
        rc = tr.report_card()
        actors = {r["actor"] for r in rc["actors"]}
        self.assertIn("strategy:meanrev_zscore", actors)


if __name__ == "__main__":
    unittest.main()
