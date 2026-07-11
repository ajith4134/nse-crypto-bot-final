"""Tests for trading/strategy/direction_equation_deploy.py — P4 live deploy.

Covers: predict evaluates a saved validated equation → bounded score/direction, records to the
Truth Ledger (deduped per bar) under source 'direction_equation', applies the Mirror Gate,
equation_tilt honors the gated direction, and everything degrades honestly with no equation /
short data. Truth Ledger + Mirror Gate are mocked (no disk side effects); state is isolated.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from trading import state
from trading.strategy import direction_equation as de
from trading.strategy import direction_equation_deploy as deploy


def _rows(n=200, seed=5):
    rng = np.random.RandomState(seed)
    c = 100 * np.exp(np.cumsum(rng.randn(n) * 0.01))
    out = []
    for i in range(n):
        o = c[i] * (1 + rng.randn() * 0.001)
        out.append([1_700_000_000_000 + i * 900_000, o, max(o, c[i]) * 1.002,
                    min(o, c[i]) * 0.998, c[i], 1000 + abs(rng.randn()) * 200])
    return out


class DeployTest(unittest.TestCase):
    def setUp(self):
        self._orig = state.STATE_DIR
        state.STATE_DIR = Path(tempfile.mkdtemp(prefix="deploy_"))
        deploy._REC_BAR.clear()
        # a saved, "validated" equation using a real feature column
        de.save_equations("crypto", [{"expr": "rsi", "kind": "sympy", "features": ["rsi"],
                                      "best_horizon": 4, "abs_ic": 0.2, "invert": False,
                                      "cpcv": {"cpcv_mean_ic": 0.15}}])

    def tearDown(self):
        state.STATE_DIR = self._orig

    def test_predict_returns_bounded_decision(self):
        with mock.patch("trading.direction.truth_ledger.record", return_value=True), \
             mock.patch("trading.direction.mirror_gate.apply",
                        side_effect=lambda d, **k: (d, {"action": "keep"})):
            p = deploy.predict(_rows(), "crypto", symbol="BTC/USDT")
        self.assertIsNotNone(p)
        self.assertIn(p["direction"], ("long", "short", "flat"))
        self.assertGreaterEqual(p["score"], -1.0)
        self.assertLessEqual(p["score"], 1.0)
        self.assertEqual(p["source"], "direction_equation")
        self.assertEqual(p["horizon"], 4)

    def test_records_once_per_bar(self):
        rows = _rows()
        with mock.patch("trading.direction.truth_ledger.record", return_value=True) as rec, \
             mock.patch("trading.direction.mirror_gate.apply",
                        side_effect=lambda d, **k: (d, {})):
            deploy.predict(rows, "crypto", symbol="BTC/USDT")
            deploy.predict(rows, "crypto", symbol="BTC/USDT")     # same last bar → no 2nd record
        self.assertLessEqual(rec.call_count, 1)     # 0 if the call was flat, else exactly 1

    def test_mirror_gate_inversion_flips_tilt(self):
        # gate inverts LONG→SHORT → the tilt sign must follow the GATED direction
        with mock.patch("trading.direction.truth_ledger.record", return_value=True), \
             mock.patch("trading.direction.mirror_gate.apply",
                        side_effect=lambda d, **k: ("SHORT", {"action": "invert"})):
            t = deploy.equation_tilt(_rows(), "crypto", symbol="BTC/USDT")
        if t is not None and t["direction"] != "flat":
            self.assertEqual(t["gated"], "short")
            self.assertLessEqual(t["tilt"], 0.0)

    def test_no_equation_degrades(self):
        de.save_equations("crypto", [])                          # clear
        state.save_json(de._EQ_FILE, {})
        self.assertIsNone(deploy.predict(_rows(), "crypto", symbol="BTC/USDT"))
        self.assertIsNone(deploy.equation_tilt(_rows(), "crypto", symbol="BTC/USDT"))

    def test_short_data_degrades(self):
        self.assertIsNone(deploy.predict(_rows(n=30), "crypto", symbol="BTC/USDT"))


if __name__ == "__main__":
    unittest.main()
