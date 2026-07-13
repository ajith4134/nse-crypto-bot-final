"""Tests for trading/direction/direction_model.py — the direction-aware GBM (proposal B)."""
import json
import tempfile
import unittest
from unittest import mock

from trading import state
from trading.direction import direction_model as dm


class DirectionModelTest(unittest.TestCase):
    def setUp(self):
        p = mock.patch.object(state, "STATE_DIR", type(state.STATE_DIR)(tempfile.mkdtemp()))
        p.start(); self.addCleanup(p.stop)
        dm._CACHE.update({"model": None, "names": None, "mtime": 0.0})

    def test_label_is_direction_aware(self):
        self.assertEqual(dm._label_up({"direction": "long", "correct": True}), 1)   # long-right = up
        self.assertEqual(dm._label_up({"direction": "short", "correct": False}), 1)  # short-wrong = up
        self.assertEqual(dm._label_up({"direction": "long", "correct": False}), 0)
        self.assertEqual(dm._label_up({"direction": "short", "correct": True}), 0)
        self.assertIsNone(dm._label_up({"direction": "neutral", "correct": True}))

    def test_train_and_predict_on_learnable_data(self):
        # a feature m_x that perfectly predicts the up-move → the GBM must learn it
        lines = []
        for i in range(400):
            up = i % 2
            # up-move when m_x high; encode via a resolved example (direction+correct → label)
            lines.append(json.dumps({"direction": "long", "correct": bool(up),
                                     "features": {"m_x": 0.9 if up else 0.1,
                                                  "m_noise": (i % 7) / 7.0}}))
        (state.STATE_DIR / dm.TRAIN_FILE).write_text("\n".join(lines))
        res = dm.train(min_examples=100)
        self.assertTrue(res["trained"], res)
        self.assertGreater(res["holdout_auc"], 0.8)             # learnable signal → high AUC
        p_up = dm.predict({"m_x": 0.95, "m_noise": 0.3})
        p_dn = dm.predict({"m_x": 0.05, "m_noise": 0.3})
        self.assertGreater(p_up, p_dn)                          # high m_x → higher p_up

    def test_predict_none_when_untrained_or_no_overlap(self):
        self.assertIsNone(dm.predict({"m_x": 0.5}))            # no model yet
        # after training, unknown features → no overlap → None
        lines = [json.dumps({"direction": "long", "correct": bool(i % 2),
                             "features": {"m_a": (i % 3) / 3.0}}) for i in range(300)]
        (state.STATE_DIR / dm.TRAIN_FILE).write_text("\n".join(lines))
        dm.train(min_examples=100)
        self.assertIsNone(dm.predict({"totally_other_feature": 1.0}))


if __name__ == "__main__":
    unittest.main()
