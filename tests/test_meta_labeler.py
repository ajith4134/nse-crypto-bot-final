"""Tests for trading/direction/meta_labeler — D6 direction meta-labeler."""
import json
import random
import tempfile
import time
import unittest
from pathlib import Path

import trading.state as state


def _write_examples(n=3000):
    """Synthetic ledger: source 'good' correct 72%, 'bad' 28% — a learnable split."""
    rng = random.Random(7)
    rows = []
    t0 = time.time() - n * 60
    for i in range(n):
        src = "good" if i % 2 == 0 else "bad"
        p = 0.72 if src == "good" else 0.28
        rows.append({"ts": t0 + i * 60, "symbol": "X/USDT:USDT", "market": "CRYPTO",
                     "segment": "futures", "direction": rng.choice(["LONG", "SHORT"]),
                     "source": src, "confidence": rng.random(),
                     "regime": rng.choice(["trend_up", "chop"]), "taken": False,
                     "horizon": "1h", "correct": rng.random() < p,
                     "method": "feather:perp"})
    p = Path(state.STATE_DIR) / "direction_truth_train.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import meta_labeler as ml
        ml._LOADED.update(mtime=None, bundle=None)
        self.ml = ml

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestMetaLabeler(_Iso):
    def test_train_learns_source_split_and_gate_enforces(self):
        _write_examples()
        rep = self.ml.train(min_examples=1000)
        self.assertNotIn("error", rep)
        self.assertGreater(rep["auc"], 0.6)                # learnable → must rank
        ex = {"ts": time.time(), "market": "CRYPTO", "segment": "futures",
              "regime": "chop", "confidence": 0.5, "taken": False, "horizon": "1h"}
        p_good = self.ml.p_correct({**ex, "source": "good", "direction": "LONG"})
        p_bad = self.ml.p_correct({**ex, "source": "bad", "direction": "LONG"})
        self.assertGreater(p_good, p_bad)
        self.assertGreater(p_good, 0.55)
        g_bad = self.ml.gate("LONG", {**ex, "source": "bad"})
        self.assertFalse(g_bad["advisory"])                # AUC proven
        self.assertFalse(g_bad["allow"])                   # bad source blocked
        g_good = self.ml.gate("LONG", {**ex, "source": "good"})
        self.assertTrue(g_good["allow"])

    def test_no_model_is_no_opinion(self):
        self.assertIsNone(self.ml.p_correct({"source": "x", "direction": "LONG"}))
        g = self.ml.gate("LONG", {"source": "x"})
        self.assertTrue(g["allow"])
        self.assertTrue(g["advisory"])

    def test_too_few_examples_refuses(self):
        _write_examples(n=100)
        self.assertIn("error", self.ml.train(min_examples=1000))

    def test_maybe_train_skips_fresh_model(self):
        _write_examples(n=1500)
        rep = self.ml.train(min_examples=1000)
        self.assertNotIn("error", rep)
        self.assertIsNone(self.ml.maybe_train())           # fresh → no retrain

    def test_unseen_category_is_safe(self):
        _write_examples(n=1500)
        self.ml.train(min_examples=1000)
        p = self.ml.p_correct({"ts": time.time(), "source": "never_seen_lane",
                               "direction": "SHORT", "regime": "weird",
                               "segment": "options", "horizon": "1h"})
        self.assertTrue(p is None or 0.0 <= p <= 1.0)

    def test_status_shape(self):
        s = self.ml.status()
        for k in ("enabled", "model", "enforcing", "levers"):
            self.assertIn(k, s)


if __name__ == "__main__":
    unittest.main()
