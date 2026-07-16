"""tests/test_strategy_table.py — the per-coin best-strategy table producer + O(1) consumer read.

Isolated: trading.state.STATE_DIR is monkeypatched to a temp dir so the real
per_coin_strategy.json / journals are never touched. The expensive tournament is faked, so these
run in milliseconds and pin the wiring (row shape, gate flag, freshness TTL, open-coin priority,
lookup notation-drift + staleness) — not the ML ranking (that lives in test_percoin_decider)."""
from __future__ import annotations

import time
import unittest
from unittest import mock


class _Base(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        from trading import state
        self._tmp = tempfile.mkdtemp(prefix="stab_test_")
        self._old = state.STATE_DIR
        state.STATE_DIR = Path(self._tmp)
        # fresh module state (rotation cursor + cached decider) per test
        from trading.crypto.freqtrade import strategy_table as st
        st._DECIDER = None
        st._ROTATE = 0
        self.st = st

    def tearDown(self):
        from trading import state
        state.STATE_DIR = self._old
        import shutil
        shutil.rmtree(self._tmp, ignore_errors=True)


class _FakeDecider:
    """Stands in for PerCoinBrainDecider: returns a canned tournament() per coin."""
    _min_final = 0.5

    def __init__(self, by_coin):
        self.by_coin = by_coin
        self.calls = []

    def tournament(self, coin):
        self.calls.append(coin)
        return self.by_coin.get(coin, {"error": "no live bars"})


def _tourn(name, last, final, deflated_ok, psr=0.6):
    return {"ranked": [{"name": name}, {"name": "r2"}, {"name": "r3"}],
            "best": {"name": name, "last": last, "final": final,
                     "sharpe": 1.2, "win_rate": 0.55},
            "deflated_ok": deflated_ok, "deflated_psr": psr}


class TestRefreshAndRow(_Base):
    def test_row_shape_and_gate(self):
        dec = _FakeDecider({
            "BTC/USDT:USDT": _tourn("pysr_crypto_0_4", last=1, final=1.8, deflated_ok=True),
            "ETH/USDT:USDT": _tourn("alpha_crypto_0_2", last=-1, final=0.2, deflated_ok=False),
        })
        with mock.patch.object(self.st, "_decider", return_value=dec):
            rec = self.st.refresh(coins=["BTC/USDT:USDT", "ETH/USDT:USDT"])
        self.assertEqual(rec["updated"], 2)

        btc = self.st.lookup("BTC/USDT:USDT")
        self.assertEqual(btc["best_strategy"], "pysr_crypto_0_4")
        self.assertEqual(btc["signal"], "LONG")
        self.assertTrue(btc["cleared_gate"])           # last!=0, final>=0.5, deflated_ok
        self.assertEqual(btc["runners_up"], ["r2", "r3"])

        eth = self.st.lookup("ETH/USDT:USDT")
        self.assertEqual(eth["signal"], "SHORT")
        self.assertFalse(eth["cleared_gate"])          # below threshold AND deflated gate failed

    def test_flat_signal_not_gated(self):
        dec = _FakeDecider({"BTC/USDT:USDT": _tourn("s", last=0, final=9.0, deflated_ok=True)})
        with mock.patch.object(self.st, "_decider", return_value=dec):
            self.st.refresh(coins=["BTC/USDT:USDT"])
        row = self.st.lookup("BTC/USDT:USDT")
        self.assertEqual(row["signal"], "FLAT")
        self.assertFalse(row["cleared_gate"])          # last==0 → never drives, even high score

    def test_error_coin_keeps_no_row(self):
        dec = _FakeDecider({})                          # every coin errors
        with mock.patch.object(self.st, "_decider", return_value=dec):
            rec = self.st.refresh(coins=["X/USDT:USDT"])
        self.assertEqual(rec["updated"], 0)
        self.assertIsNone(self.st.lookup("X/USDT:USDT"))


class TestLookup(_Base):
    def test_notation_drift(self):
        dec = _FakeDecider({"BTC/USDT:USDT": _tourn("s", 1, 1.0, True)})
        with mock.patch.object(self.st, "_decider", return_value=dec):
            self.st.refresh(coins=["BTC/USDT:USDT"])
        # spot notation should still resolve to the perp row
        self.assertIsNotNone(self.st.lookup("BTC/USDT"))
        self.assertEqual(self.st.lookup("BTC/USDT")["best_strategy"], "s")

    def test_stale_row_is_none(self):
        from trading import state
        state.save_json(self.st._FILE, {"BTC/USDT:USDT": {
            "best_strategy": "old", "signal": "LONG", "ts": time.time() - 999999}})
        self.assertIsNone(self.st.lookup("BTC/USDT:USDT"))   # older than TTL → not attributed

    def test_missing_and_empty(self):
        self.assertIsNone(self.st.lookup(""))
        self.assertIsNone(self.st.lookup("NOPE/USDT:USDT"))


class TestOpenCoinPriority(_Base):
    def test_open_coins_refreshed_first_within_batch(self):
        universe = [f"C{i}/USDT:USDT" for i in range(10)]
        canned = {c: _tourn("s", 1, 1.0, True) for c in universe}
        dec = _FakeDecider(canned)
        with mock.patch.object(self.st, "_decider", return_value=dec), \
                mock.patch.object(self.st, "_universe", return_value=universe), \
                mock.patch.object(self.st, "_open_pairs", return_value=["C7/USDT:USDT"]):
            self.st.refresh(batch=3)
        # the open coin must be among those actually scored this (size-3) pass
        self.assertIn("C7/USDT:USDT", dec.calls)
        self.assertIsNotNone(self.st.lookup("C7/USDT:USDT"))


class TestStatus(_Base):
    def test_status_counts(self):
        dec = _FakeDecider({"BTC/USDT:USDT": _tourn("s", 1, 1.0, True),
                            "ETH/USDT:USDT": _tourn("s2", -1, 0.1, False)})
        with mock.patch.object(self.st, "_decider", return_value=dec):
            self.st.refresh(coins=["BTC/USDT:USDT", "ETH/USDT:USDT"])
        s = self.st.status()
        self.assertEqual(s["size"], 2)
        self.assertEqual(s["fresh"], 2)
        self.assertEqual(s["gate_clearing"], 1)         # only BTC cleared


if __name__ == "__main__":
    unittest.main()
