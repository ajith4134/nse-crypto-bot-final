"""trading/brain/school.py — the School: dual-track curriculum L0→L6 with real exams
(Brain Ultra Upgrade R2, R21, R27; GOAL.md Pillar 3).

The Teacher runs the brain (the student) through levels. TWO tracks per level (R21 —
the taught subject is INTELLIGENCE itself, trading is the applied domain):

  Track A — HOW TO BE INTELLIGENT: recall (find the right memory from a partial cue),
  connect (multi-hop reasoning across neuron links), apply (produce the action for a
  neuron whose action facet is HIDDEN — knowledge→action conversion, R27).
  Track B — THE DOMAIN: same exam machinery over that level's domain neurons
  (facts/news → episodes/lessons → strategies/skills → research sources → findings →
  instruction evolution evidence).

Grading is held-out and mechanical (R10 honesty): the student answers ONLY from its own
neuron recall; the grader compares against source data the student is never shown as
the answer. Promotion needs BOTH tracks ≥ PASS_SCORE. Every exam is persisted as an
exam neuron + school.json history (trading/state — monkeypatch STATE_DIR in tests),
and each tested neuron gets record_exam() so decayed knowledge is re-examined (R28).

Exam questions are generated from REAL neurons (memory/self_quiz.make_cloze salient-term
blanking); an empty level yields an honest "not enough material" instead of a fake pass.
"""
from __future__ import annotations

import random
import time

from memory.neurons import NeuronStore, _jaccard, _words, get_store
from memory.self_quiz import MasteryQuiz
from trading import state

SCHOOL_FILE = "school.json"
PASS_SCORE = 0.7
MIN_QUESTIONS = 3

CURRICULUM: dict[str, dict] = {
    "L0": {"name": "Literacy", "kinds": None,
           "goal": "read/write/link/search its own neurons"},
    "L1": {"name": "Primary — market basics", "kinds": ("fact", "news", "source"),
           "goal": "candles, orderbook, fees, symbols, current events"},
    "L2": {"name": "Secondary — signals & risk", "kinds": ("concept", "episode", "lesson"),
           "goal": "indicators, risk, position sizing, own trade history"},
    "L3": {"name": "Undergrad — strategies", "kinds": ("strategy", "skill", "book-chapter"),
           "goal": "strategy library mastery, regime fit"},
    "L4": {"name": "Masters — research", "kinds": ("source", "finding"),
           "goal": "web research → neurons → instructions"},
    "L5": {"name": "PhD — invention", "kinds": ("finding", "invention"),
           "goal": "hypothesis → experiment → validated invention"},
    "L6": {"name": "Professor — self-evolution", "kinds": ("instruction",),
           "goal": "edits+mutates own instructions; evolved children beat parents"},
}
LEVEL_ORDER = list(CURRICULUM)


class _Student:
    """The brain-as-student: answers ONLY from its own neuron recall."""

    def __init__(self, store: NeuronStore):
        self.store = store

    def recall(self, query: str, k: int = 3) -> list[dict]:
        return [{"snippet": f"{h['title']} {h['body']} {h['action']}"}
                for h in self.store.search(query, k=k)]


class School:
    """Teacher module: generates exams from real neurons, grades held-out, promotes."""

    def __init__(self, store: NeuronStore | None = None, *, rng: random.Random | None = None):
        self.store = store or get_store()
        # fresh sampling each exam (fixed-seed = same questions forever = fixed-sample
        # promotions); tests inject a seeded rng for determinism
        self.rng = rng or random.Random()
        self.quiz = MasteryQuiz(brain=_Student(self.store))

    # ── material ───────────────────────────────────────────────────────────────
    def _material(self, level: str, *, n: int) -> list:
        kinds = CURRICULUM[level]["kinds"]
        pool = [x for x in self.store.all_neurons()
                if (kinds is None or x.kind in kinds) and len(x.body) > 40]
        self.rng.shuffle(pool)
        return pool[:n]

    # ── Track A: intelligence itself (R21) ─────────────────────────────────────
    def _exam_recall(self, neurons: list) -> list[dict]:
        """Find the right memory from a partial cue (cloze over the body)."""
        out = []
        for n in neurons:
            r = self.quiz.quiz_one(n.id, n.body[:400])
            if "skipped" in r:
                continue
            r["type"] = "recall"
            r["neuron"] = n.id
            out.append(r)
        return out

    def _exam_connect(self, neurons: list) -> list[dict]:
        """Multi-hop: name a neighbour — answered from links, graded against the web."""
        out = []
        for n in neurons:
            nbrs = self.store.neighbors(n.id, limit=5)
            if not nbrs:
                continue
            expected_titles = [b["title"] for b in nbrs]
            hits = self.store.search(n.title, k=6)
            answered = [h["title"] for h in hits if h["id"] != n.id]
            correct = any(t in answered for t in expected_titles)
            out.append({"type": "connect", "neuron": n.id, "correct": correct,
                        "question": f"what connects to '{n.title[:60]}'?",
                        "expected": expected_titles[0][:60]})
        return out

    def _exam_apply(self, neurons: list) -> list[dict]:
        """R27 knowledge→action: produce the HIDDEN action facet from related knowledge."""
        out = []
        for n in neurons:
            related = [h for h in self.store.search(f"{n.title} {n.body[:120]}", k=5)
                       if h["id"] != n.id]            # the source's own action is hidden
            produced = " ".join(h["action"] for h in related)
            score = _jaccard(_words(produced), _words(n.action))
            out.append({"type": "apply", "neuron": n.id,
                        "correct": score >= 0.12,     # token overlap w/ hidden action
                        "score": round(score, 3),
                        "question": f"how would you USE '{n.title[:60]}'?"})
        return out

    def _exam_select(self, neurons: list) -> list[dict]:
        """R27 knowledge-APPLICATION: given a situation, can the brain SELECT a relevant
        instruction to act on (not just recall an action string)? Uses the live apply.select
        surface — the same one the decision path uses — so this exams the real capability."""
        out = []
        try:
            from trading.brain import apply as _apply
        except Exception:
            return out
        for n in neurons:
            scenario = f"{n.title} {n.body[:80]}"
            picked = _apply.select(scenario, explore=0.0)   # deterministic (exploit)
            if picked is None:
                out.append({"type": "select", "neuron": n.id, "correct": False,
                            "question": f"which instruction applies to '{n.title[:50]}'?",
                            "note": "no instruction selected"})
                continue
            title = self.store.get(picked["id"])
            rel = _jaccard(_words(picked.get("title", "") + " " +
                                  (title.action if title else "")), _words(scenario))
            out.append({"type": "select", "neuron": n.id, "picked": picked["id"],
                        "correct": rel >= 0.06, "score": round(rel, 3),
                        "question": f"which instruction applies to '{n.title[:50]}'?"})
        return out

    # ── Track B: the domain + L6 evolution evidence ────────────────────────────
    def _exam_domain(self, level: str, neurons: list) -> list[dict]:
        if level == "L6":                             # evidence-based, not quiz-based
            out = []
            for n in neurons:
                if not n.parents:
                    continue
                parent = self.store.get(n.parents[0])
                if parent is None:
                    continue
                used = n.stats.get("wins", 0) + n.stats.get("losses", 0)
                if not used:
                    continue                          # no outcome evidence yet — a fresh
                                                      # child (conf == parent) must not
                                                      # auto-fail; it just isn't gradable
                out.append({"type": "evolution", "neuron": n.id,
                            "correct": n.confidence > parent.confidence,
                            "question": f"does evolved '{n.title[:50]}' beat its parent?",
                            "expected": f"child {n.confidence} > parent {parent.confidence}"})
            return out
        return self._exam_recall(neurons)

    # ── the exam ───────────────────────────────────────────────────────────────
    def take_exam(self, level: str, *, n_questions: int = 12,
                  now: float | None = None) -> dict:
        if level not in CURRICULUM:
            raise ValueError(f"unknown level {level!r}")
        ts = time.time() if now is None else float(now)
        material = self._material(level, n=n_questions)
        track_a = (self._exam_recall(material[: n_questions // 3])
                   + self._exam_connect(material[n_questions // 3: 2 * n_questions // 3])
                   + self._exam_apply(material[2 * n_questions // 3:]))
        if level in ("L3", "L4", "L5", "L6"):          # R27: knowledge-application graded
            track_a += self._exam_select(material[: max(2, n_questions // 4)])
        track_b = self._exam_domain(level, self._material(level, n=n_questions // 2))
        result = {"level": level, "name": CURRICULUM[level]["name"], "ts": ts}
        for track, items in (("track_a", track_a), ("track_b", track_b)):
            if len(items) < MIN_QUESTIONS:
                result[track] = {"score": None, "questions": len(items),
                                 "note": "not enough material — study more first"}
                continue
            score = sum(1 for q in items if q["correct"]) / len(items)
            result[track] = {"score": round(score, 3), "questions": len(items),
                             "items": items}
        for q in track_a + track_b:                   # R28: re-examined knowledge
            if q.get("neuron"):
                self.store.record_exam(q["neuron"],
                                       1.0 if q["correct"] else 0.0, now=ts)
        a, b = result["track_a"]["score"], result["track_b"]["score"]
        result["passed"] = (a is not None and b is not None
                            and a >= PASS_SCORE and b >= PASS_SCORE)
        self._record(result)
        return result

    def _record(self, result: dict) -> None:
        summary = {k: (v if not isinstance(v, dict) else
                       {kk: vv for kk, vv in v.items() if kk != "items"})
                   for k, v in result.items()}

        def _mut(d):
            d = d or {"level": "L0", "exams": []}
            d["exams"] = (d.get("exams", []) + [summary])[-200:]
            cur = d.get("level", "L0")
            if (result["passed"] and result["level"] == cur
                    and LEVEL_ORDER.index(cur) < len(LEVEL_ORDER) - 1):
                d["level"] = LEVEL_ORDER[LEVEL_ORDER.index(cur) + 1]
                d["promoted_ts"] = result["ts"]
            return d
        state.mutate_json(SCHOOL_FILE, _mut, default={})
        a = result["track_a"]["score"]
        b = result["track_b"]["score"]
        self.store.add(
            "exam", f"exam {result['level']} {'PASS' if result['passed'] else 'fail'} "
                    f"A={a} B={b}",
            f"Level {result['level']} ({result['name']}): track_a={a} track_b={b} "
            f"passed={result['passed']} at ts={result['ts']:.0f}.",
            "Compare with the next exam at this level: scores must not decay (R28); "
            "if track A lags, study connections; if track B lags, study the domain.",
            level=result["level"], origin="experiment", ref=SCHOOL_FILE,
            now=result["ts"], auto_link=False)

    # ── study: turn material into taught-by-linked lesson neurons ──────────────
    def study(self, topic: str, texts: list[dict], *, now: float | None = None) -> dict:
        """Teacher hands material (e.g. librarian/researcher output) → lesson neurons.

        texts: [{"title":…, "body":…, "action":…(optional), "ref":…(optional)}]
        """
        ts = time.time() if now is None else float(now)
        made = []
        for t in texts:
            if not (t.get("title") and t.get("body")):
                continue
            action = (t.get("action") or "").strip() or (
                f"Recall this when working on '{topic}'; key point: "
                f"{t['body'].strip().splitlines()[0][:180]}")
            n = self.store.add("lesson", str(t["title"])[:200], str(t["body"])[:2000],
                               action, origin="lesson", ref=str(t.get("ref") or topic),
                               now=ts)
            made.append(n.id)
        for i in range(1, len(made)):
            self.store.link(made[i], made[0], "taught-by", now=ts)
        return {"topic": topic, "neurons": made}

    def status(self) -> dict:
        d = state.load_json(SCHOOL_FILE, {}) or {}
        exams = d.get("exams", [])
        return {"level": d.get("level", "L0"),
                "level_name": CURRICULUM.get(d.get("level", "L0"), {}).get("name"),
                "exams_taken": len(exams), "recent": exams[-5:],
                "curriculum": {k: {"name": v["name"], "goal": v["goal"]}
                               for k, v in CURRICULUM.items()},
                "pass_score": PASS_SCORE}
