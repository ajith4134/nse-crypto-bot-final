"""W4 scout swarm + consensus oracle tests — isolated STATE_DIR."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ScoutsConsensusTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        os.environ["DELPHI_MIN_AGREE"] = "2"

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()
        os.environ.pop("DELPHI_MIN_AGREE", None)

    def test_single_scout_never_fires(self):
        from trading import scouts
        scouts.record_signal("eddie-fusion-conviction", symbol="BTCUSDT",
                             market="crypto", direction="long", strength=0.9)
        self.assertEqual(scouts.sophie_consensus(), [])
        self.assertEqual(scouts.status()["note"], "insufficient-scouts")

    def test_two_scouts_agree_fires_once(self):
        from trading import scouts
        scouts.record_signal("eddie-fusion-conviction", symbol="BTCUSDT",
                             market="crypto", direction="long", strength=0.7)
        scouts.record_signal("maya-whale-prints", symbol="BTCUSDT",
                             market="crypto", direction="long", strength=0.8)
        ev = scouts.sophie_consensus()
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["n_scouts"], 2)
        self.assertEqual(ev[0]["direction"], "long")
        # dedup: same agreement does not re-fire inside the window
        self.assertEqual(scouts.sophie_consensus(), [])
        self.assertIsNotNone(scouts.consensus_for("BTC/USDT:USDT"))

    def test_disagreement_no_fire(self):
        from trading import scouts
        scouts.record_signal("eddie-fusion-conviction", symbol="ETHUSDT",
                             market="crypto", direction="long", strength=0.7)
        scouts.record_signal("maya-whale-prints", symbol="ETHUSDT",
                             market="crypto", direction="short", strength=0.8)
        self.assertEqual(scouts.sophie_consensus(), [])

    def test_fusion_scout_reads_app_signals(self):
        from trading import scouts
        sigs = {"SOL/USDT:USDT": {"available": True, "direction": "long",
                                  "confluence": 0.71, "regime": "trend"},
                "WEAK/USDT:USDT": {"available": True, "direction": "long",
                                   "confluence": 0.2}}
        self.assertEqual(scouts.run_fusion_conviction_scout(sigs), 1)

    def test_whale_scout_parses_interception(self):
        from trading import scouts
        from trading.broker_sense.interception import get_recorder
        rec = get_recorder()
        trades = [{"price": 100, "qty": 1, "isBuyerMaker": True} for _ in range(20)]
        trades += [{"price": 100, "qty": 50, "isBuyerMaker": False} for _ in range(4)]
        import time as _t
        rec._cache[("binance", "recent_trades")] = {
            "body": trades, "ts": _t.time(),
            "url": "https://x/api/trades?symbol=DOGEUSDT"}
        try:
            self.assertEqual(scouts.run_whale_prints_scout(), 1)
            st = scouts.status()
            self.assertIn("maya-whale-prints", st["active_scouts"])
        finally:
            rec._cache.pop(("binance", "recent_trades"), None)


if __name__ == "__main__":
    unittest.main()
