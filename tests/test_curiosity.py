"""Curiosity-driven feature discovery tests (invent-beyond #1) — isolated STATE_DIR."""
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class CuriosityTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        # reset the shared registry singleton so tests don't leak
        import trading.broker_sense.learning_columns as lc
        lc._REG = None

    def tearDown(self):
        self._p.stop()
        self._tmp.cleanup()

    def _seed(self, name, values_by_symbol, first_seen=None):
        from trading.broker_sense.learning_columns import get_registry
        reg = get_registry()
        reg.register(name, source="binance", label=name)
        if first_seen:
            reg.columns[name]["first_seen"] = first_seen
        for sym, v in values_by_symbol.items():
            reg.observe(sym, name, v)
        reg._save()

    def test_varying_new_field_is_curious(self):
        from trading.broker_sense import curiosity
        # a NEW field that varies a lot across symbols → high curiosity
        self._seed("basis_pct", {"BTC": 0.5, "ETH": 2.1, "SOL": -1.3, "APT": 4.0},
                   first_seen=time.time())
        c = curiosity.curiosity("basis_pct")
        self.assertIsNotNone(c["curiosity"])
        self.assertGreater(c["curiosity"], 0.5)

    def test_constant_field_low_curiosity(self):
        from trading.broker_sense import curiosity
        # a field identical across symbols → low informativeness
        self._seed("leverage_cap", {"BTC": 20, "ETH": 20, "SOL": 20, "APT": 20},
                   first_seen=time.time())
        c = curiosity.curiosity("leverage_cap")
        self.assertLess(c["informativeness"], 0.1)

    def test_too_few_obs_is_honest_none(self):
        from trading.broker_sense import curiosity
        self._seed("rare", {"BTC": 1.0}, first_seen=time.time())
        self.assertIsNone(curiosity.curiosity("rare")["curiosity"])

    def test_harvest_accepts_top_and_is_idempotent(self):
        from trading.broker_sense import curiosity
        self._seed("basis_pct", {"BTC": 0.5, "ETH": 2.1, "SOL": -1.3, "APT": 4.0},
                   first_seen=time.time())
        r1 = curiosity.harvest()
        self.assertIn("basis_pct", r1["accepted"])
        r2 = curiosity.harvest()               # already accepted → not re-accepted
        self.assertNotIn("basis_pct", r2["accepted"])

    def test_rank_orders_by_curiosity(self):
        from trading.broker_sense import curiosity
        self._seed("varying", {"a": 1, "b": 9, "c": 3, "d": 7}, first_seen=time.time())
        self._seed("flat", {"a": 5, "b": 5, "c": 5, "d": 5},
                   first_seen=time.time() - 30 * 86400)   # old + constant
        ranked = curiosity.rank()
        self.assertEqual(ranked[0]["name"], "varying")


if __name__ == "__main__":
    unittest.main()
