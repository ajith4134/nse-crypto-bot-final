"""W5 champion lineage + leak tripwire tests — isolated STATE_DIR."""
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class ChampionLineageTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def test_champion_triple_gate(self):
        from trading import state
        from trading.strategy.generators.base import _update_champion
        _update_champion("CRYPTO", "gen1", {"dsr": 0.7, "oos_sharpe": 1.2,
                                            "oos_total_return": 0.3})
        d = state.load_json("champion_lineage.json", {})
        self.assertEqual(d["CRYPTO"]["champion"]["id"], "gen1")
        # better DSR but worse Sharpe → NOT champion (triple gate)
        _update_champion("CRYPTO", "gen2", {"dsr": 0.9, "oos_sharpe": 0.8,
                                            "oos_total_return": 0.5})
        d = state.load_json("champion_lineage.json", {})
        self.assertEqual(d["CRYPTO"]["champion"]["id"], "gen1")
        self.assertEqual(d["CRYPTO"]["generation"], 2)
        # better on ALL THREE → champion swaps, lineage records the prior
        _update_champion("CRYPTO", "gen3", {"dsr": 0.9, "oos_sharpe": 1.5,
                                            "oos_total_return": 0.6})
        d = state.load_json("champion_lineage.json", {})
        self.assertEqual(d["CRYPTO"]["champion"]["id"], "gen3")
        last = d["CRYPTO"]["history"][-1]
        self.assertTrue(last["became_champion"])
        self.assertEqual(last["prior_champion"], "gen1")

    def test_history_bounded_and_honest(self):
        from trading import state
        from trading.strategy.generators.base import _update_champion
        for i in range(250):
            _update_champion("NSE", f"g{i}", {"dsr": 0.1, "oos_sharpe": 0.1,
                                              "oos_total_return": 0.01})
        d = state.load_json("champion_lineage.json", {})
        self.assertLessEqual(len(d["NSE"]["history"]), 200)
        self.assertEqual(d["NSE"]["generation"], 250)


if __name__ == "__main__":
    unittest.main()
