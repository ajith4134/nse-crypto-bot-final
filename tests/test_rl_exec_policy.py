"""W6 RL execution-policy tests — tiny synthetic data, isolated STATE_DIR."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np


def _ohlcv(n=400, seed=0, drift=0.001):
    rng = np.random.default_rng(seed)
    c = 100 * np.cumprod(1 + drift + 0.004 * rng.standard_normal(n))
    o = np.roll(c, 1)
    o[0] = c[0]
    h = np.maximum(o, c) * (1 + 0.002 * rng.random(n))
    low = np.minimum(o, c) * (1 - 0.002 * rng.random(n))
    v = 10 + rng.random(n)
    ts = np.arange(n) * 300_000
    return np.column_stack([ts, o, h, low, c, v])


class RlExecPolicyTest(unittest.TestCase):
    def setUp(self):
        os.environ["ML_NETWORK_SKIP_HEAVY"] = "1"
        self._tmp = tempfile.TemporaryDirectory()
        from trading import state
        self._p = mock.patch.object(state, "STATE_DIR", Path(self._tmp.name))
        self._p.start()
        import trading.rl.exec_policy as ep
        self._pdir = mock.patch.object(ep, "_DIR", Path(self._tmp.name) / "rl_exec")
        self._pdir.start()

    def tearDown(self):
        self._pdir.stop()
        self._p.stop()
        self._tmp.cleanup()

    def test_env_ambiguous_candle_is_loss(self):
        from trading.rl.exec_policy import _SL_MULTS, _TP_MULTS, TradingExecEnv
        arr = _ohlcv(120)
        i = 60
        env = TradingExecEnv(arr)
        env.i = i
        entry = arr[i, 4]
        atr = env.atr[i]
        # force the NEXT candle to touch both stop and target for a long
        arr[i + 1, 2] = entry + _TP_MULTS[0] * atr * 2      # high beyond target
        arr[i + 1, 3] = entry - _SL_MULTS[0] * atr * 2      # low beyond stop
        env2 = TradingExecEnv(arr)
        env2.i = i
        r = env2._simulate((1, _SL_MULTS[0], _TP_MULTS[0]))
        self.assertLess(r, 0)                              # counted as LOSS (vp2 rule)

    def test_env_no_trade_advances(self):
        from trading.rl.exec_policy import TradingExecEnv
        env = TradingExecEnv(_ohlcv(120))
        obs, _ = env.reset()
        self.assertEqual(obs.shape[0], env.window * env.feats.shape[1])
        _o, r, done, _t, info = env.step(0)                 # no-trade
        self.assertEqual(r, 0.0)
        self.assertAlmostEqual(info["equity"], 1.0)

    def test_train_and_signal_smoke(self):
        from trading.rl import exec_policy as ep
        out = ep.train_policy(_ohlcv(360), timesteps=512, tag="t")
        self.assertTrue(out["ok"], out)
        self.assertIn("holdout", out)
        self.assertIsInstance(out["overfit_gap"], float)
        sig = ep.latest_signal(_ohlcv(120, seed=1), tag="t")
        self.assertTrue(sig["available"])
        self.assertIn(sig.get("action"), ("no-trade", "long", "short"))

    def test_node_face_honest_neutral_untrained(self):
        from trading.rl.exec_policy import RLExecPolicyNode
        node = RLExecPolicyNode("missing")
        p = node.predict_proba([[0.0]] * 3)
        self.assertEqual(p, [0.5, 0.5, 0.5])


if __name__ == "__main__":
    unittest.main()
