"""Tests for trading/direction/meta_challenger — the TabPFN duel for the D6 meta-labeler.

Engine fits are STUBBED (no real LightGBM/TabPFN training) so the duel logic is tested
deterministically and fast; the real duel is exercised via the CLI, not CI."""
import json
import tempfile
import unittest
from pathlib import Path

import trading.state as state


def _seed_train(n=400, sep=0.0):
    """Write n time-ordered training examples; `sep` shifts source_prior so a model
    COULD separate the classes (used only for the encode test, not the stubbed duel)."""
    p = Path(state.STATE_DIR) / "direction_truth_train.jsonl"
    lines = []
    for i in range(n):
        correct = i % 2
        lines.append(json.dumps({
            "ts": 1_700_000_000 + i, "symbol": "ETH/USDT:USDT", "market": "CRYPTO",
            "segment": "futures", "direction": "LONG" if i % 3 else "SHORT",
            "source": "venue_leadlag" if i % 2 else "meanrev", "regime": "chop",
            "horizon": "1h", "confidence": 0.5 + sep * (correct - 0.5), "correct": correct}))
    # a few exit rows that MUST be dropped
    for i in range(10):
        lines.append(json.dumps({"ts": 1_700_000_500 + i, "symbol": "X", "market": "CRYPTO",
                                 "segment": "futures", "direction": "LONG", "source": "s",
                                 "regime": "chop", "horizon": "exit", "correct": 1}))
    p.write_text("\n".join(lines) + "\n")


class _Iso(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self._o = state.STATE_DIR
        state.STATE_DIR = Path(self._t.name)
        from trading.direction import meta_challenger as mc
        self.mc = mc

    def tearDown(self):
        state.STATE_DIR = self._o
        self._t.cleanup()


class TestMetaChallenger(_Iso):
    def test_load_rows_drops_exit_and_time_orders(self):
        _seed_train(50)
        rows = self.mc._load_rows(1000)
        self.assertEqual(len(rows), 50)                       # 10 exit rows dropped
        self.assertTrue(all(r["horizon"] != "exit" for r in rows))
        ts = [r["ts"] for r in rows]
        self.assertEqual(ts, sorted(ts))                     # never shuffled

    def test_encoded_marks_categorical_indices(self):
        _seed_train(60)
        X, y, cat_idx = self.mc._encoded(self.mc._load_rows(1000))
        from trading.direction.meta_labeler import _CATS
        self.assertEqual(X.shape[0], 60)
        self.assertEqual(len(cat_idx), len(_CATS))           # 5 categoricals flagged
        self.assertEqual(set(y.tolist()), {0, 1})

    def test_challenge_promotes_when_tabpfn_wins(self):
        _seed_train(700)                                     # need holdout >= 100 rows
        import numpy as np
        # stub both engines: champion ~chance, challenger ranks the holdout well
        self.mc._lgbm_fit_predict = lambda ci: (lambda Xtr, ytr, Xte: np.full(len(Xte), 0.5))
        self.mc._tabpfn_fit_predict = lambda ci: (
            lambda Xtr, ytr, Xte: np.linspace(0.1, 0.9, len(Xte)))
        rep = self.mc.challenge(max_rows=700)
        self.assertNotIn("error", rep)
        self.assertEqual(rep["challenger"]["engine"], "tabpfn_v2")
        self.assertEqual(rep["champion"]["engine"], "lightgbm")
        self.assertIn("promote", rep)
        # persisted for the panel
        saved = state.load_json("direction_meta_challenger.json", {})
        self.assertEqual(saved["challenger"]["engine"], "tabpfn_v2")

    def test_challenge_errors_cleanly_on_thin_data(self):
        _seed_train(20)
        self.assertIn("error", self.mc.challenge(max_rows=400))

    def test_maybe_challenge_throttles(self):
        import time
        state.save_json("direction_meta_challenger.json", {"ts": time.time()})
        self.assertIsNone(self.mc.maybe_challenge())         # fresh → skip

    def test_status_shape(self):
        s = self.mc.status()
        self.assertIn("levers", s)
        self.assertIn("META_PROMOTE_AUC_MARGIN", s["levers"])


if __name__ == "__main__":
    unittest.main()
