"""vote_log: write-only per-candidate vote vector — bounded, never raises, never read back."""
import json
import unittest
import tempfile
from unittest import mock


class VoteLogTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patcher = mock.patch("trading.state.STATE_DIR", self.tmp.name)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_logs_one_row_per_candidate(self):
        from trading.direction import vote_log
        vote_log.log(symbol="BTC/USDT", market="CRYPTO", segment="futures",
                     lane="breadth", regime="trend_up", decided="long",
                     reads=[("indicator_fusion", 0.61), ("river_online", 0.97)])
        rows = [json.loads(l) for l in open(vote_log._path())]
        self.assertEqual(len(rows), 1)
        r = rows[0]
        self.assertEqual(r["symbol"], "BTC/USDT")
        self.assertEqual(r["lane"], "breadth")
        self.assertEqual(r["decided"], "long")
        self.assertEqual(r["votes"], {"indicator_fusion": 0.61, "river_online": 0.97})

    def test_bad_reads_never_raise_and_skip_junk(self):
        from trading.direction import vote_log
        vote_log.log(symbol="X", market="CRYPTO", segment="spot", lane="selective",
                     reads=[("ok", 0.5), ("junk", None), ("worse", "nan?")])
        rows = [json.loads(l) for l in open(vote_log._path())]
        self.assertEqual(rows[0]["votes"], {"ok": 0.5})
        # empty/None reads: no row, no exception
        vote_log.log(symbol="X", market="CRYPTO", segment="spot", lane="selective", reads=[])
        vote_log.log(symbol="X", market="CRYPTO", segment="spot", lane="selective",
                     reads=[("all_junk", None)])
        self.assertEqual(sum(1 for _ in open(vote_log._path())), 1)

    def test_disabled_by_env(self):
        from trading.direction import vote_log
        with mock.patch.dict("os.environ", {"VOTE_LOG": "0"}):
            vote_log.log(symbol="X", market="CRYPTO", segment="spot", lane="breadth",
                         reads=[("a", 0.4)])
        self.assertFalse(vote_log._path().exists())

    def test_rotation_keeps_newest(self):
        from trading.direction import vote_log
        with mock.patch.object(vote_log, "_MAX_LINES", 10), \
             mock.patch.object(vote_log, "_MAX_KEEP", 5), \
             mock.patch.object(vote_log, "_EST_BYTES_PER_LINE", 1):
            for i in range(30):
                vote_log.log(symbol=f"S{i}", market="CRYPTO", segment="spot",
                             lane="breadth", reads=[("a", 0.6)])
        rows = [json.loads(l) for l in open(vote_log._path())]
        self.assertLessEqual(len(rows), 6)
        self.assertEqual(rows[-1]["symbol"], "S29")


if __name__ == "__main__":
    unittest.main()
