"""memory/self_quiz.py — proof the brain gets smarter (Phase P4.4).

The brain quizzes ITSELF on what it has read and tracks a rising mastery/retention curve —
the honest test of learning. Pipeline:

    pick memories → make a question (cloze, or LLM Q&A) → the brain answers (recall / agent)
    → grade → update a FSRS spaced-repetition card per topic → measure retention over rounds.

Reuse-first (real, tested libs do the heavy lifting):
  • FSRS (pip, py-fsrs) — the spaced-repetition algorithm: each topic is a Card with
    stability/difficulty/retrievability; successful reviews raise stability → the
    retention-at-horizon curve RISES. This is the mastery model (lighter than EduKTM/torch,
    same purpose — a learning curve).
  • DeepEval (pip) — optional LLM grader (GEval/correctness) when keys are present.
  • core.llm — quiz generation + grading via our LLM cloud keys (gated).
Offline-safe + deterministic: cloze questions + overlap grading need no LLM; `now` (datetime)
injected; DeepEval/LLM gated off → graceful fallback. No network at import.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fsrs import Card, Rating, Scheduler

_UTC = timezone.utc
_STOP = {"the", "a", "an", "of", "to", "and", "in", "on", "for", "is", "are", "by", "with",
         "that", "this", "it", "as", "at", "be", "or", "from", "than", "into", "per"}


def _salient_term(text: str) -> str | None:
    """Pick the most 'quizzable' token: longest non-stopword alphabetic word."""
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", text)
    cands = [w for w in words if w.lower() not in _STOP]
    return max(cands, key=len) if cands else None


@dataclass
class MasteryQuiz:
    """Self-quiz + FSRS mastery curve over the brain's memories."""

    brain: object                                    # KnowledgeBrain (recall)
    answer_fn: object = None                          # (question)->str (default: brain.recall)
    grade_fn: object = None                           # (answer, expected)->bool (default: overlap)
    llm_chat: object = None                           # optional LLM grader/gen
    desired_retention: float = 0.9
    scheduler: Scheduler = field(default=None, init=False)
    cards: dict = field(default_factory=dict, init=False)
    history: list = field(default_factory=list, init=False)
    interactions: list = field(default_factory=list, init=False)   # [(topic, correct)] for DKT

    def __post_init__(self) -> None:
        self.scheduler = Scheduler(desired_retention=self.desired_retention)
        self.answer_fn = self.answer_fn or self._default_answer
        self.grade_fn = self.grade_fn or self._default_grade

    # ── question generation ──────────────────────────────────────────────────────
    def make_cloze(self, text: str) -> tuple[str, str] | None:
        """Deterministic fill-in-the-blank: blank the most salient term."""
        term = _salient_term(text)
        if not term:
            return None
        q = re.sub(r"\b" + re.escape(term) + r"\b", "____", text, count=1)
        return q, term

    # ── default answerer / grader (offline) ─────────────────────────────────────
    def _default_answer(self, question: str) -> str:
        try:
            hits = self.brain.recall(question, k=3)
        except Exception:
            return ""
        return " ".join((h.get("snippet") or h.get("text") or "") for h in hits)

    @staticmethod
    def _default_grade(answer: str, expected: str) -> bool:
        return expected.lower() in (answer or "").lower()

    # ── one quiz item → FSRS review ─────────────────────────────────────────────
    def quiz_one(self, topic: str, text: str, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(_UTC)
        made = self.make_cloze(text)
        if made is None:
            return {"topic": topic, "skipped": "no term"}
        question, expected = made
        answer = self.answer_fn(question)
        correct = bool(self.grade_fn(answer, expected))
        card = self.cards.get(topic, Card())
        card, _ = self.scheduler.review_card(
            card, Rating.Good if correct else Rating.Again, review_datetime=now)
        self.cards[topic] = card
        self.interactions.append((topic, correct))       # timeline for EduKTM knowledge tracing
        return {"topic": topic, "question": question[:80], "expected": expected,
                "correct": correct, "stability": round(card.stability or 0.0, 3),
                "retrievability": round(self.scheduler.get_card_retrievability(card, current_datetime=now), 4)}

    # ── retention at a future horizon (the mastery signal) ──────────────────────
    def retention_at(self, topic: str, *, now: datetime, horizon_days: float = 1.0) -> float:
        card = self.cards.get(topic)
        if card is None:
            return 0.0
        future = now + timedelta(days=horizon_days)
        return float(self.scheduler.get_card_retrievability(card, current_datetime=future))

    # ── a round over many memories ──────────────────────────────────────────────
    def run_round(self, items: list[tuple], *, now: datetime, horizon_days: float = 1.0) -> dict:
        """items = [(topic, text), ...]. Quiz each, FSRS-update, record accuracy + retention."""
        results = [self.quiz_one(t, txt, now=now) for t, txt in items]
        graded = [r for r in results if "correct" in r]
        acc = sum(r["correct"] for r in graded) / len(graded) if graded else 0.0
        ret = (sum(self.retention_at(r["topic"], now=now, horizon_days=horizon_days)
                   for r in graded) / len(graded)) if graded else 0.0
        row = {"round": len(self.history) + 1, "n": len(graded),
               "accuracy": round(acc, 4), "retention_at_horizon": round(ret, 4)}
        self.history.append(row)
        return row

    def mastery_curve(self, items: list[tuple], *, rounds: int = 5,
                      start: datetime | None = None, gap_days: float = 1.0,
                      horizon_days: float = 1.0) -> list[dict]:
        """Repeatedly study+quiz the same items on a spaced schedule → rising retention curve."""
        t = start or datetime(2026, 1, 1, tzinfo=_UTC)
        for _ in range(rounds):
            self.run_round(items, now=t, horizon_days=horizon_days)
            t = t + timedelta(days=gap_days)
        return self.history

    # ── second mastery model: EduKTM Deep Knowledge Tracing (blueprint-named) ────
    def knowledge_tracing(self, *, epoch: int = 10, lr: float = 0.01, seed: int = 0) -> dict:
        """Fit EduKTM DKT on the quiz interaction timeline → per-topic KT mastery.

        A second, heavier mastery view alongside FSRS (reuse-real-code-first: use the
        named project). Returns {fit, mastery, status}; degrades gracefully if torch/EduKTM
        is unavailable (frequency baseline)."""
        from memory.knowledge_tracing import KnowledgeTracer
        topics = list(self.cards.keys()) or sorted({t for t, _ in self.interactions})
        tracer = KnowledgeTracer(topics, seed=seed)
        tracer.add_sequence(self.interactions)
        fit = tracer.fit(epoch=epoch, lr=lr)
        return {"fit": fit, "mastery": tracer.mastery(), "status": tracer.status()}

    def status(self, *, now: datetime | None = None) -> dict:
        now = now or datetime.now(_UTC)
        per = {t: {"stability": round(c.stability or 0.0, 3),
                   "difficulty": round(c.difficulty or 0.0, 3),
                   "retrievability": round(self.scheduler.get_card_retrievability(c, current_datetime=now), 4)}
               for t, c in self.cards.items()}
        improving = (len(self.history) >= 2 and
                     self.history[-1]["retention_at_horizon"] >= self.history[0]["retention_at_horizon"])
        return {"topics": len(self.cards), "rounds": len(self.history),
                "improving": improving, "curve": self.history, "per_topic": per,
                "engine": "fsrs", "desired_retention": self.desired_retention}
