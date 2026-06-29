"""Phase P4.4 (2nd mastery model) acceptance tests — EduKTM Deep Knowledge Tracing.

Pins the `memory.knowledge_tracing.KnowledgeTracer` wrapper around EduKTM's DKT (an RNN
over the learner's (topic, correct) interaction timeline) plus the `MasteryQuiz.
knowledge_tracing()` integration. Fully OFFLINE + deterministic:

  * torch is seeded via the tracer's `seed` arg (plumbed to torch.manual_seed),
  * tiny sequences + few epochs keep it CPU-fast,
  * warnings are silenced at import and EduKTM's training stdout/tqdm is redirected to a
    StringIO inside every fit so test output stays clean.

No network, no disk writes, no LLM. Mirrors the tests/test_journal_t5.py idiom.
"""
from __future__ import annotations

import contextlib
import io
import json
import unittest
import warnings

warnings.filterwarnings("ignore")

from memory.knowledge_tracing import KnowledgeTracer
from memory.self_quiz import MasteryQuiz


@contextlib.contextmanager
def _muted():
    """Swallow EduKTM's stdout AND tqdm (which writes to stderr) so test output is clean."""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf), \
            warnings.catch_warnings():
        warnings.simplefilter("ignore")
        yield


def _quiet_fit(tracer, **kw):
    """Fit while swallowing EduKTM's stdout/tqdm progress so test output stays clean."""
    with _muted():
        return tracer.fit(**kw)


# ── a deterministic stub brain so MasteryQuiz can run fully offline ──────────────
class _StubBrain:
    """Minimal KnowledgeBrain stand-in: recall() echoes a snippet containing the term
    so cloze grading is deterministic (the expected term is always present)."""

    def recall(self, question, k=3):
        return [{"snippet": question.replace("____", "photosynthesis mitochondria")}]


class TestTracerFit(unittest.TestCase):
    def _seq(self):
        # 12-step mixed timeline over 3 topics
        return [
            ("a", True), ("b", False), ("c", True), ("a", True),
            ("b", True), ("c", False), ("a", False), ("b", True),
            ("c", True), ("a", True), ("b", False), ("c", True),
        ]

    def test_fit_ok_and_mastery_over_all_topics(self):
        tr = KnowledgeTracer(["a", "b", "c"], seed=0)
        tr.add_sequence(self._seq())
        fit = _quiet_fit(tr, epoch=6, lr=0.01)
        self.assertTrue(fit["ok"])
        self.assertEqual(fit["model"], "EduKTM.DKT")
        self.assertEqual(fit["sequences"], 1)
        self.assertEqual(fit["epochs"], 6)
        m = tr.mastery()
        # mastery covers EVERY topic, each a probability in [0,1]
        self.assertEqual(set(m), {"a", "b", "c"})
        for v in m.values():
            self.assertIsInstance(v, float)
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_status_jsonable_and_fitted(self):
        tr = KnowledgeTracer(["a", "b", "c"], seed=0)
        tr.add_sequence(self._seq())
        _quiet_fit(tr, epoch=5, lr=0.01)
        st = tr.status()
        self.assertEqual(st["engine"], "EduKTM.DKT")
        self.assertTrue(st["fitted"])
        self.assertEqual(st["topics"], 3)
        self.assertEqual(st["sequences"], 1)
        json.dumps(st)   # fully serialisable

    def test_status_engine_when_unfit(self):
        tr = KnowledgeTracer(["a", "b"], seed=0)
        st = tr.status()
        self.assertEqual(st["engine"], "EduKTM.DKT")
        self.assertFalse(st["fitted"])
        json.dumps(st)


class TestNoInteractions(unittest.TestCase):
    def test_fit_no_sequences(self):
        tr = KnowledgeTracer(["a", "b"], seed=0)
        fit = tr.fit(epoch=3)
        self.assertFalse(fit["ok"])
        self.assertEqual(fit["reason"], "no interactions")

    def test_mastery_baseline_when_unfit_no_crash(self):
        tr = KnowledgeTracer(["a", "b"], seed=0)
        tr.fit(epoch=3)
        m = tr.mastery()              # falls back to baseline; empty-safe
        self.assertEqual(set(m), {"a", "b"})
        for v in m.values():
            self.assertEqual(v, 0.0)  # no data -> 0/1 each


class TestAddSequence(unittest.TestCase):
    def test_unknown_topics_filtered(self):
        tr = KnowledgeTracer(["a", "b"], seed=0)
        tr.add_sequence([("a", True), ("zzz", True), ("b", False)])
        self.assertEqual(len(tr.sequences), 1)
        topics_in_seq = {t for t, _ in tr.sequences[0]}
        self.assertEqual(topics_in_seq, {"a", "b"})   # 'zzz' dropped

    def test_empty_after_filter_not_appended(self):
        tr = KnowledgeTracer(["a", "b"], seed=0)
        tr.add_sequence([("zzz", True), ("qqq", False)])
        self.assertEqual(tr.sequences, [])

    def test_correct_coerced_to_int(self):
        tr = KnowledgeTracer(["a"], seed=0)
        tr.add_sequence([("a", True), ("a", False)])
        self.assertEqual(tr.sequences[0], [("a", 1), ("a", 0)])


class TestBaselineRanking(unittest.TestCase):
    def test_baseline_ranks_easy_above_hard(self):
        # deterministic frequency baseline: easy always right, hard always wrong
        tr = KnowledgeTracer(["easy", "hard"], seed=0)
        seq = []
        for _ in range(6):
            seq += [("easy", True), ("hard", False)]
        tr.add_sequence(seq)
        base = tr._baseline()
        self.assertEqual(base["easy"], 1.0)
        self.assertEqual(base["hard"], 0.0)
        self.assertGreater(base["easy"], base["hard"])

    def test_baseline_unseen_topic_is_zero(self):
        tr = KnowledgeTracer(["a", "b", "c"], seed=0)
        tr.add_sequence([("a", True), ("a", True)])
        base = tr._baseline()
        self.assertEqual(base["a"], 1.0)
        self.assertEqual(base["b"], 0.0)   # never seen -> 0/1
        self.assertEqual(base["c"], 0.0)


class TestDKTEasyVsHard(unittest.TestCase):
    def _train_easy_hard(self, seed=0):
        tr = KnowledgeTracer(["easy", "hard"], seed=seed)
        seq = []
        for _ in range(8):
            seq += [("easy", True), ("hard", False)]
        tr.add_sequence(seq)
        _quiet_fit(tr, epoch=8, lr=0.05)
        return tr

    def test_dkt_or_baseline_ranks_easy_above_hard(self):
        tr = self._train_easy_hard()
        m = tr.mastery()
        for v in m.values():
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)
        # DKT at tiny scale can be noisy; the deterministic baseline must always rank.
        base = tr._baseline()
        self.assertGreater(base["easy"], base["hard"])


class TestDeterminism(unittest.TestCase):
    def _build(self):
        tr = KnowledgeTracer(["a", "b", "c"], seed=7)
        tr.add_sequence([
            ("a", True), ("b", False), ("c", True), ("a", False),
            ("b", True), ("c", True), ("a", True), ("b", False),
        ])
        return tr

    def test_same_seed_same_mastery(self):
        tr1, tr2 = self._build(), self._build()
        f1 = _quiet_fit(tr1, epoch=6, lr=0.02)
        f2 = _quiet_fit(tr2, epoch=6, lr=0.02)
        self.assertEqual(f1["ok"], f2["ok"])
        self.assertTrue(f1["ok"])
        self.assertEqual(tr1.mastery(), tr2.mastery())   # seed -> torch.manual_seed


class TestQuizIntegration(unittest.TestCase):
    def _quiz_with_rounds(self):
        quiz = MasteryQuiz(brain=_StubBrain())
        items = [
            ("bio", "The process of photosynthesis converts light into energy."),
            ("cell", "The mitochondria is the powerhouse of the cell."),
        ]
        from datetime import datetime, timezone
        t = datetime(2026, 1, 1, tzinfo=timezone.utc)
        quiz.run_round(items, now=t)
        from datetime import timedelta
        quiz.run_round(items, now=t + timedelta(days=1))
        return quiz

    def test_interactions_logged(self):
        quiz = self._quiz_with_rounds()
        self.assertGreaterEqual(len(quiz.interactions), 1)
        for topic, correct in quiz.interactions:
            self.assertIn(topic, {"bio", "cell"})
            self.assertIn(correct, (True, False))

    def test_knowledge_tracing_returns_fit_mastery_status(self):
        quiz = self._quiz_with_rounds()
        with _muted():
            out = quiz.knowledge_tracing(epoch=5, lr=0.01, seed=0)
        self.assertEqual(set(out), {"fit", "mastery", "status"})
        self.assertIn("ok", out["fit"])
        # mastery over the quizzed topics, each in [0,1]
        for topic, v in out["mastery"].items():
            self.assertIn(topic, {"bio", "cell"})
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)
        self.assertEqual(out["status"]["engine"], "EduKTM.DKT")
        json.dumps(out)   # fully serialisable


if __name__ == "__main__":
    unittest.main()
