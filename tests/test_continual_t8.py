"""Trading Phase T8.5 (Continual Learning + Auto-Quiz + Meta-Init + Reflexion) tests.

Fully OFFLINE + deterministic (every RNG seeded). Proves the brain "gets smarter":

  • OnlineNode    — a River drift-aware NodeProtocol node that keeps learning tick-by-tick,
                    detects a mid-stream concept flip (ADWIN).
  • ReplayBuffer  — importance-weighted experience replay (anti-catastrophic-forgetting).
  • replay_retrain— interleave replayed past samples with new ones.
  • AutoQuiz      — PREQUENTIAL (test-then-train) self-test: HEADLINE proof that accuracy
                    rises with experience on a learnable stream, and stays ~chance on an
                    unlearnable one.
  • MetaLearner   — warm-start (meta-init) gives a few-shot advantage over a cold model.
  • Reflexion     — natural-language self-critique stored in semantic memory.

No broker/exchange/disk/network access; River models are RNG-free and all sampling uses
an injected, seeded numpy Generator.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import unittest

import numpy as np

from core.node_protocol import NodeProtocol
from trading.brain.continual import (
    OnlineNode,
    ReplayBuffer,
    replay_retrain,
)
from trading.brain.metalearn import MetaLearner
from trading.brain.selfeval import AutoQuiz, reflect, reflect_and_store
from trading.brain.semantic import SemanticMemory
from trading.journal.schema import ClosedTrade

FEATURES = ["x0", "x1", "x2", "x3"]
SEED = 1234


# ── deterministic stream helpers ─────────────────────────────────────────────────
def learnable_stream(n: int, seed: int = SEED, *, flip_at: int | None = None):
    """y = int(0.9*x0 + 0.5*x1 - 0.4*x2 + noise > 0). A genuinely learnable concept.

    If `flip_at` is given, the decision weights invert at that index (concept drift).
    """
    rng = np.random.default_rng(seed)
    samples = []
    for i in range(n):
        x = rng.normal(0.0, 1.0, size=4)
        noise = rng.normal(0.0, 0.3)
        sign = -1.0 if (flip_at is not None and i >= flip_at) else 1.0
        score = sign * (0.9 * x[0] + 0.5 * x[1] - 0.4 * x[2]) + noise
        y = int(score > 0.0)
        samples.append(([float(v) for v in x], y))
    return samples


def unlearnable_stream(n: int, seed: int = SEED):
    """y is random and independent of x — nothing to learn (accuracy must stay ~0.5)."""
    rng = np.random.default_rng(seed)
    samples = []
    for _ in range(n):
        x = rng.normal(0.0, 1.0, size=4)
        y = int(rng.integers(0, 2))
        samples.append(([float(v) for v in x], y))
    return samples


def _xy(samples):
    return [r for r, _ in samples], [y for _, y in samples]


# ── OnlineNode ───────────────────────────────────────────────────────────────────
class TestOnlineNode(unittest.TestCase):
    def test_is_node_protocol(self):
        node = OnlineNode(FEATURES)
        self.assertIsInstance(node, NodeProtocol)

    def test_schema_input_dim(self):
        node = OnlineNode(FEATURES)
        self.assertEqual(node.schema.input_dim, len(FEATURES))
        self.assertEqual(node.kind, "online")

    def test_fit_returns_self_and_proba_floats_in_range(self):
        X, y = _xy(learnable_stream(120))
        node = OnlineNode(FEATURES)
        self.assertIs(node.fit(X, y), node)
        proba = node.predict_proba(X)
        self.assertEqual(len(proba), len(X))
        for p in proba:
            self.assertIsInstance(p, float)
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

    def test_n_seen_increments(self):
        node = OnlineNode(FEATURES)
        self.assertEqual(node.n_seen, 0)
        samples = learnable_stream(40)
        for row, y in samples:
            node.learn_one(row, y)
        self.assertEqual(node.n_seen, 40)

    def test_predict_labels_binary(self):
        X, y = _xy(learnable_stream(80))
        node = OnlineNode(FEATURES).fit(X, y)
        labels = node.predict(X)
        self.assertEqual(len(labels), len(X))
        self.assertTrue(set(labels) <= {0, 1})

    def test_concept_flip_triggers_drift(self):
        # Concept inverts halfway -> ADWIN should flag at least one drift event.
        samples = learnable_stream(1200, flip_at=600)
        node = OnlineNode(FEATURES)
        for row, y in samples:
            node.learn_one(row, y)
        self.assertGreaterEqual(node.drift_events, 1)

    def test_status_keys(self):
        node = OnlineNode(FEATURES, name="on1")
        for row, y in learnable_stream(15):
            node.learn_one(row, y)
        st = node.status()
        self.assertEqual(set(st), {"name", "kind", "n_seen", "drift_events", "features"})
        self.assertEqual(st["name"], "on1")
        self.assertEqual(st["features"], len(FEATURES))
        json.dumps(st)


# ── ReplayBuffer ─────────────────────────────────────────────────────────────────
class TestReplayBuffer(unittest.TestCase):
    def test_add_increments_len(self):
        buf = ReplayBuffer(maxlen=100)
        self.assertEqual(len(buf), 0)
        for row, y in learnable_stream(10):
            buf.add(row, y)
        self.assertEqual(len(buf), 10)

    def test_maxlen_truncates(self):
        buf = ReplayBuffer(maxlen=50)
        for row, y in learnable_stream(120):
            buf.add(row, y)
        self.assertEqual(len(buf), 50)

    def test_sample_bounded_by_n_and_size(self):
        rng = np.random.default_rng(SEED)
        buf = ReplayBuffer(maxlen=100)
        for row, y in learnable_stream(20):
            buf.add(row, y)
        s = buf.sample(8, rng)
        self.assertLessEqual(len(s), 8)
        self.assertEqual(len(s), 8)
        # request more than buffer holds -> capped at buffer size
        s2 = buf.sample(500, rng)
        self.assertLessEqual(len(s2), len(buf))
        self.assertEqual(len(s2), len(buf))
        # sample items carry the stored fields
        self.assertEqual(set(s[0]), {"row", "y", "weight", "ts"})

    def test_higher_weight_items_over_represented(self):
        # 30 items; mark 3 of them with 100x weight. Sample n=5 (no-replace) many times;
        # the heavy items must be drawn far more often than a uniform expectation.
        rng = np.random.default_rng(SEED)
        buf = ReplayBuffer(maxlen=100)
        samples = learnable_stream(30)
        heavy = {0, 1, 2}
        for i, (row, y) in enumerate(samples):
            buf.add(row, y, weight=100.0 if i in heavy else 1.0, ts=float(i))
        # tag rows so we can identify them after sampling (ts is the index)
        heavy_hits = 0
        draws = 0
        trials = 400
        for _ in range(trials):
            for it in buf.sample(5, rng):
                draws += 1
                if int(it["ts"]) in heavy:
                    heavy_hits += 1
        heavy_frac = heavy_hits / draws
        # uniform would give 3/30 = 0.10 of draws to the heavy items; weighting must
        # push that far higher. Deterministic rng -> robust tolerance.
        self.assertGreater(heavy_frac, 0.30)


# ── replay_retrain ───────────────────────────────────────────────────────────────
class TestReplayRetrain(unittest.TestCase):
    def test_n_seen_is_replay_plus_new(self):
        rng = np.random.default_rng(SEED)
        buf = ReplayBuffer(maxlen=500)
        for row, y in learnable_stream(300):
            buf.add(row, y)
        new = learnable_stream(40, seed=SEED + 1)
        node = replay_retrain(FEATURES, new, buf, rng, replay_k=120)
        self.assertIsInstance(node, OnlineNode)
        self.assertEqual(node.n_seen, 120 + len(new))

    def test_replay_k_capped_at_buffer_size(self):
        rng = np.random.default_rng(SEED)
        buf = ReplayBuffer(maxlen=500)
        for row, y in learnable_stream(30):
            buf.add(row, y)
        new = learnable_stream(10, seed=SEED + 2)
        node = replay_retrain(FEATURES, new, buf, rng, replay_k=999)
        # replay capped at len(buffer) == 30
        self.assertEqual(node.n_seen, 30 + len(new))

    def test_retrained_node_predicts(self):
        rng = np.random.default_rng(SEED)
        buf = ReplayBuffer(maxlen=500)
        for row, y in learnable_stream(200):
            buf.add(row, y)
        new = learnable_stream(20, seed=SEED + 3)
        node = replay_retrain(FEATURES, new, buf, rng, replay_k=100)
        X, _ = _xy(learnable_stream(10, seed=SEED + 4))
        proba = node.predict_proba(X)
        self.assertEqual(len(proba), len(X))
        for p in proba:
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)


# ── AutoQuiz (HEADLINE) ──────────────────────────────────────────────────────────
class TestAutoQuiz(unittest.TestCase):
    def test_learnable_stream_rises_and_is_accurate(self):
        samples = learnable_stream(800)
        quiz = AutoQuiz(FEATURES, sample_every=25, warmup=10)
        res = quiz.run(samples)
        # HEADLINE proof: accuracy climbs with experience and ends well above chance.
        self.assertTrue(res.rising)
        self.assertGreater(res.slope, 0.0)
        self.assertGreater(res.final_accuracy, 0.75)

    def test_learnable_curve_nonempty_pairs(self):
        res = AutoQuiz(FEATURES).run(learnable_stream(800))
        self.assertIsInstance(res.curve, list)
        self.assertGreater(len(res.curve), 0)
        count, acc = res.curve[0]
        self.assertIsInstance(count, int)
        self.assertGreaterEqual(acc, 0.0)
        self.assertLessEqual(acc, 1.0)

    def test_as_dict_json_able(self):
        res = AutoQuiz(FEATURES).run(learnable_stream(400))
        d = res.as_dict()
        self.assertEqual(set(d), {"n", "final_accuracy", "slope", "rising", "curve"})
        json.dumps(d)

    def test_unlearnable_stream_stays_at_chance(self):
        samples = unlearnable_stream(800)
        res = AutoQuiz(FEATURES, sample_every=25, warmup=10).run(samples)
        # nothing to learn: accuracy ~0.5 and no strong upward trend
        self.assertLess(res.final_accuracy, 0.65)
        self.assertLessEqual(res.slope, 0.0005)

    def test_learnable_beats_unlearnable(self):
        learn = AutoQuiz(FEATURES).run(learnable_stream(800))
        rand = AutoQuiz(FEATURES).run(unlearnable_stream(800))
        self.assertGreater(learn.final_accuracy, rand.final_accuracy)


# ── MetaLearner (meta-init / few-shot) ───────────────────────────────────────────
class TestMetaLearner(unittest.TestCase):
    def test_warm_start_inherits_global_experience(self):
        meta = MetaLearner(FEATURES)
        for row, y in learnable_stream(200):
            meta.observe(row, y, task="A")
        cold = meta.new_task_model("cold_task", warm=False)
        warm = meta.new_task_model("warm_task", warm=True)
        self.assertEqual(cold.n_seen, 0)
        self.assertGreater(warm.n_seen, 0)
        self.assertEqual(warm.n_seen, meta.status()["global_seen"])

    def test_adapt_few_shot_gain_non_negative(self):
        meta = MetaLearner(FEATURES)
        # pool several "tasks" of the same learnable concept into the global model
        for t, off in enumerate((0, 1, 2)):
            for row, y in learnable_stream(150, seed=SEED + off):
                meta.observe(row, y, task=f"hist{t}")
        new_task = learnable_stream(60, seed=SEED + 99)
        res = meta.adapt(new_task, shots=25)
        self.assertEqual(res["shots"], 25)
        self.assertGreaterEqual(res["warm_accuracy"], res["cold_accuracy"])
        self.assertGreaterEqual(res["few_shot_gain"], 0.0)
        self.assertGreater(res["global_seen"], 0)

    def test_status_reflects_tasks(self):
        meta = MetaLearner(FEATURES)
        for row, y in learnable_stream(30):
            meta.observe(row, y)
        meta.new_task_model("RELIANCE", warm=True)
        meta.new_task_model("INFY", warm=True)
        st = meta.status()
        self.assertEqual(st["features"], len(FEATURES))
        self.assertEqual(st["global_seen"], 30)
        self.assertEqual(set(st["tasks"]), {"RELIANCE", "INFY"})


# ── Reflexion self-critique ──────────────────────────────────────────────────────
class TestReflexion(unittest.TestCase):
    def _trade(self):
        return ClosedTrade(trade_id="rfx1", symbol="RELIANCE", direction="LONG",
                           net_pnl=-120.0, entry_price=100.0, exit_price=98.0,
                           quantity=10.0)

    def test_mismatch_note_mentions_symbol_and_cue(self):
        note = reflect(self._trade(), 1, 0)   # predicted UP, got DOWN
        self.assertIsInstance(note, str)
        self.assertTrue(note)
        self.assertIn("RELIANCE", note)
        low = note.lower()
        self.assertTrue("but got" in low or "review" in low or "misled" in low)

    def test_correct_note_reinforces(self):
        note = reflect(self._trade(), 1, 1)   # predicted UP, got UP
        self.assertIn("RELIANCE", note)
        low = note.lower()
        self.assertTrue("correct" in low or "reinforce" in low)

    def test_reflect_and_store_grows_memory(self):
        sem = SemanticMemory(enabled=False)
        self.assertEqual(len(sem.all()), 0)
        res = reflect_and_store(self._trade(), 1, 0, sem)
        self.assertIn("note", res)
        self.assertTrue(res["note"])
        self.assertEqual(len(sem.all()), 1)
        # storing a second lesson grows it further
        reflect_and_store(self._trade(), 0, 0, sem)
        self.assertEqual(len(sem.all()), 2)


if __name__ == "__main__":
    unittest.main()
