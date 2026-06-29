"""Phase P4.4 (FSRS self-quiz mastery tracker) acceptance tests — fully offline.

Proves the brain "gets smarter": it cloze-quizzes itself on memories, grades the
answers, drives a per-topic FSRS spaced-repetition card, and tracks a RISING
retention-at-horizon curve. Everything here is deterministic and network-free:

  * STUB brains (KnowBrain / BlankBrain) replace the real KnowledgeBrain — no recall
    index, no embeddings, no disk.
  * every `now` is an injected timezone-aware UTC datetime, so FSRS scheduling is
    reproducible run-to-run.
  * cloze question generation + substring grading need no LLM (llm_chat stays None).

Mirrors the idiom of tests/test_journal_t5.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import unittest
from datetime import datetime, timedelta, timezone

from memory.self_quiz import MasteryQuiz

_UTC = timezone.utc
_START = datetime(2026, 1, 1, tzinfo=_UTC)


# ── stub brains (no real KnowledgeBrain) ─────────────────────────────────────────
class KnowBrain:
    """A brain that "knows everything": recall returns the source texts verbatim,
    so the blanked salient term is always present in the answer → graded correct."""

    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = []

    def recall(self, query, k=3):
        self.calls.append((query, k))
        return [{"snippet": t} for t in self.texts[:k]]


class BlankBrain:
    """A brain that never learns: recall returns empty snippets → always wrong."""

    def __init__(self):
        self.calls = []

    def recall(self, query, k=3):
        self.calls.append((query, k))
        return [{"snippet": ""}]


_ITEMS = [
    ("photo", "photosynthesis converts sunlight into chemical energy"),
    ("cell", "mitochondria produces energy inside every living cell"),
]


class TestMakeCloze(unittest.TestCase):
    def test_blanks_salient_term(self):
        q = MasteryQuiz(KnowBrain([]))
        made = q.make_cloze("photosynthesis converts sunlight into energy")
        self.assertIsNotNone(made)
        question, expected = made
        self.assertIn("____", question)
        self.assertEqual(expected, "photosynthesis")

    def test_expected_is_not_a_stopword(self):
        q = MasteryQuiz(KnowBrain([]))
        from memory.self_quiz import _STOP
        _, expected = q.make_cloze("the brain learns from spaced repetition daily")
        self.assertNotIn(expected.lower(), _STOP)

    def test_term_removed_from_question(self):
        q = MasteryQuiz(KnowBrain([]))
        question, expected = q.make_cloze("mitochondria produces energy inside cells")
        self.assertNotIn(expected, question)

    def test_no_quizzable_word_returns_none(self):
        q = MasteryQuiz(KnowBrain([]))
        # every token is a stopword or shorter than 4 chars -> no salient term
        self.assertIsNone(q.make_cloze("to be or in it"))


class TestQuizOne(unittest.TestCase):
    def test_correct_path(self):
        text = _ITEMS[0][1]
        q = MasteryQuiz(KnowBrain([text]))
        r = q.quiz_one("photo", text, now=_START)
        self.assertTrue(r["correct"])
        self.assertEqual(r["expected"], "photosynthesis")
        self.assertIn("____", r["question"])
        self.assertGreater(r["stability"], 0.0)
        self.assertGreaterEqual(r["retrievability"], 0.0)
        self.assertLessEqual(r["retrievability"], 1.0)

    def test_wrong_path(self):
        text = _ITEMS[0][1]
        q = MasteryQuiz(BlankBrain())
        r = q.quiz_one("photo", text, now=_START)
        self.assertFalse(r["correct"])
        self.assertGreaterEqual(r["retrievability"], 0.0)
        self.assertLessEqual(r["retrievability"], 1.0)

    def test_skipped_when_no_term(self):
        q = MasteryQuiz(KnowBrain([]))
        r = q.quiz_one("empty", "to be or in it", now=_START)
        self.assertIn("skipped", r)
        self.assertNotIn("correct", r)

    def test_wrong_retention_below_correct(self):
        text = _ITEMS[0][1]
        good = MasteryQuiz(KnowBrain([text]))
        bad = MasteryQuiz(BlankBrain())
        good.quiz_one("photo", text, now=_START)
        bad.quiz_one("photo", text, now=_START)
        good_ret = good.retention_at("photo", now=_START, horizon_days=1.0)
        bad_ret = bad.retention_at("photo", now=_START, horizon_days=1.0)
        self.assertLess(bad_ret, good_ret)

    def test_retention_at_unknown_topic_is_zero(self):
        q = MasteryQuiz(KnowBrain([]))
        self.assertEqual(q.retention_at("never", now=_START, horizon_days=1.0), 0.0)


class TestRunRound(unittest.TestCase):
    def test_accuracy_is_fraction_correct(self):
        # answer_fn only ever knows "photosynthesis" -> item 0 correct, item 1 wrong
        def answer_fn(question):
            return "the answer is photosynthesis"

        q = MasteryQuiz(KnowBrain([]), answer_fn=answer_fn)
        row = q.run_round(_ITEMS, now=_START, horizon_days=1.0)
        self.assertEqual(row["n"], 2)
        self.assertAlmostEqual(row["accuracy"], 0.5, places=6)
        self.assertEqual(row["round"], 1)

    def test_round_index_increments_and_n_counts_graded(self):
        q = MasteryQuiz(KnowBrain([t for _, t in _ITEMS]))
        # second item ("empty") is skipped -> only 2 graded
        items = _ITEMS + [("empty", "to be or in it")]
        r1 = q.run_round(items, now=_START)
        r2 = q.run_round(items, now=_START + timedelta(days=1))
        self.assertEqual(r1["round"], 1)
        self.assertEqual(r2["round"], 2)
        self.assertEqual(r1["n"], 2)

    def test_all_correct_accuracy_one(self):
        q = MasteryQuiz(KnowBrain([t for _, t in _ITEMS]))
        row = q.run_round(_ITEMS, now=_START)
        self.assertAlmostEqual(row["accuracy"], 1.0, places=6)


class TestMasteryCurve(unittest.TestCase):
    def test_curve_rises_when_learning(self):
        q = MasteryQuiz(KnowBrain([t for _, t in _ITEMS]))
        curve = q.mastery_curve(_ITEMS, rounds=5, start=_START,
                                gap_days=1.0, horizon_days=1.0)
        self.assertEqual(len(curve), 5)
        rets = [row["retention_at_horizon"] for row in curve]
        # spaced repetition with correct answers -> non-decreasing, strictly up overall
        for a, b in zip(rets, rets[1:]):
            self.assertGreaterEqual(b, a)
        self.assertGreater(rets[-1], rets[0])
        # every round was fully correct
        for row in curve:
            self.assertAlmostEqual(row["accuracy"], 1.0, places=6)
        self.assertTrue(q.status()["improving"])

    def test_curve_does_not_rise_when_never_learning(self):
        q = MasteryQuiz(BlankBrain())
        curve = q.mastery_curve(_ITEMS, rounds=5, start=_START,
                                gap_days=1.0, horizon_days=1.0)
        rets = [row["retention_at_horizon"] for row in curve]
        # never correct -> accuracy floored at 0 and retention does not improve
        for row in curve:
            self.assertAlmostEqual(row["accuracy"], 0.0, places=6)
        self.assertLessEqual(rets[-1], rets[0])
        self.assertFalse(q.status()["improving"])

    def test_determinism(self):
        texts = [t for _, t in _ITEMS]
        q1 = MasteryQuiz(KnowBrain(texts))
        q2 = MasteryQuiz(KnowBrain(texts))
        c1 = q1.mastery_curve(_ITEMS, rounds=5, start=_START, gap_days=1.0, horizon_days=1.0)
        c2 = q2.mastery_curve(_ITEMS, rounds=5, start=_START, gap_days=1.0, horizon_days=1.0)
        self.assertEqual(c1, c2)


class TestInjectedHooks(unittest.TestCase):
    def test_grade_fn_and_answer_fn_are_honored(self):
        seen = {"answers": [], "grades": []}

        def answer_fn(question):
            seen["answers"].append(question)
            return "RECORDED-ANSWER"

        def grade_fn(answer, expected):
            seen["grades"].append((answer, expected))
            return True   # force-correct regardless of content

        q = MasteryQuiz(BlankBrain(), answer_fn=answer_fn, grade_fn=grade_fn)
        r = q.quiz_one("photo", _ITEMS[0][1], now=_START)
        self.assertTrue(r["correct"])                       # honored: grade_fn wins
        self.assertEqual(len(seen["answers"]), 1)           # honored: answer_fn called
        self.assertIn("____", seen["answers"][0])
        self.assertEqual(seen["grades"][0][0], "RECORDED-ANSWER")
        self.assertEqual(seen["grades"][0][1], "photosynthesis")

    def test_default_answer_uses_brain_recall(self):
        brain = KnowBrain([_ITEMS[0][1]])
        q = MasteryQuiz(brain)
        q.quiz_one("photo", _ITEMS[0][1], now=_START)
        self.assertEqual(len(brain.calls), 1)
        self.assertEqual(brain.calls[0][1], 3)              # default k=3


class TestStatus(unittest.TestCase):
    def test_status_shape_and_json_able(self):
        q = MasteryQuiz(KnowBrain([t for _, t in _ITEMS]))
        q.mastery_curve(_ITEMS, rounds=3, start=_START, gap_days=1.0, horizon_days=1.0)
        st = q.status(now=_START + timedelta(days=3))
        self.assertEqual(st["engine"], "fsrs")
        self.assertEqual(st["topics"], 2)
        self.assertEqual(st["rounds"], 3)
        self.assertIn("curve", st)
        for topic in ("photo", "cell"):
            pt = st["per_topic"][topic]
            self.assertIn("stability", pt)
            self.assertIn("difficulty", pt)
            self.assertIn("retrievability", pt)
        json.dumps(st)   # fully serialisable

    def test_improving_false_before_two_rounds(self):
        q = MasteryQuiz(KnowBrain([t for _, t in _ITEMS]))
        q.run_round(_ITEMS, now=_START)
        self.assertFalse(q.status()["improving"])


if __name__ == "__main__":
    unittest.main()
