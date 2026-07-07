"""Live discovery signal + trade-decision integration (trading/brain/discovery/signal.py).

The Concept Discovery Engine's self-invented features become a live directional signal that
scales trade confidence (validated lane) with an experiment shadow lane. These tests cover the
fast signal path, the non-blocking registry, and the confidence-blend math wired into
BrainExecutor._apply_discovery — without any exchange/network dependency.
"""
from __future__ import annotations

import time
import types
import unittest
import warnings

import numpy as np

warnings.simplefilter("ignore")


def _series(n=360, seed=1):
    t = np.arange(n)
    rng = np.random.default_rng(seed)
    return 100 + np.cumsum(rng.standard_normal(n) * 0.5) + 8 * np.sin(t * 0.05)


class TestLiveSignal(unittest.TestCase):
    def test_engine_live_signal_bounds(self):
        from trading.brain.discovery import ConceptDiscoveryEngine
        close = _series()
        eng = ConceptDiscoveryEngine(window=24, latent_dim=10, dict_size=20,
                                     top_features=8, use_llm=False)
        eng.discover(series=close)
        sig = eng.live_signal(close)
        for k in ("validated", "experiment", "n_val", "n_exp"):
            self.assertIn(k, sig)
        self.assertTrue(-1.0 <= sig["validated"] <= 1.0)
        self.assertTrue(-1.0 <= sig["experiment"] <= 1.0)

    def test_live_signal_neutral_before_fit(self):
        from trading.brain.discovery import ConceptDiscoveryEngine
        eng = ConceptDiscoveryEngine(use_llm=False)          # not fitted
        sig = eng.live_signal(_series())
        self.assertEqual(sig["validated"], 0.0)
        self.assertFalse(sig.get("n_val"))

    def test_registry_nonblocking_then_ready(self):
        from trading.brain.discovery import signal as disc
        close = _series(seed=3)
        r1 = disc.signal("UNIT/USDT", close)                 # kicks a background fit
        self.assertIn("ready", r1)
        # first call must return immediately (non-blocking) — neutral until the bg fit lands
        self.assertFalse(r1["ready"])
        ready = None
        for _ in range(30):
            time.sleep(1)
            r = disc.signal("UNIT/USDT", close)
            if r["ready"]:
                ready = r
                break
        self.assertIsNotNone(ready, "background fit never completed")
        self.assertTrue(-1.0 <= ready["validated"] <= 1.0)

    def test_registry_short_series_is_safe(self):
        from trading.brain.discovery import signal as disc
        r = disc.signal("TINY/USDT", [1.0, 2.0, 3.0])
        self.assertFalse(r["ready"])
        self.assertEqual(r["validated"], 0.0)


class TestExecutorBlend(unittest.TestCase):
    def test_apply_discovery_blends_confidence(self):
        import pandas as pd
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        close = _series(seed=2)
        df = pd.DataFrame({"time": range(len(close)), "open": close, "high": close + 0.3,
                           "low": close - 0.3, "close": close, "volume": 1000.0})
        obj = types.SimpleNamespace()
        obj._ohlcv = lambda sym: df
        apply = types.MethodType(BrainExecutor.__dict__["_apply_discovery"], obj)
        brain = {"confidence": 0.6}
        apply("BTC/USDT", "LONG", brain)
        # fields always populated; confidence stays a valid probability
        self.assertIn("concept_signal", brain)
        self.assertIn("concept_experiment", brain)
        self.assertIn("concept_n", brain)
        self.assertTrue(0.0 <= brain["confidence"] <= 1.0)

    def test_apply_discovery_short_df_noop(self):
        import pandas as pd
        from trading.crypto.freqtrade.brain_executor import BrainExecutor
        df = pd.DataFrame({"close": [1.0, 2.0, 3.0]})
        obj = types.SimpleNamespace()
        obj._ohlcv = lambda sym: df
        apply = types.MethodType(BrainExecutor.__dict__["_apply_discovery"], obj)
        brain = {"confidence": 0.5}
        apply("BTC/USDT", "LONG", brain)
        self.assertEqual(brain["confidence"], 0.5)           # unchanged on insufficient data


if __name__ == "__main__":
    unittest.main()
