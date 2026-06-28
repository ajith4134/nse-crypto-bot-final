"""Phase P4.2 (human-like memory layer) acceptance tests — fully offline + deterministic.

Pins behaviour of memory.human_memory.HumanMemory against a STUB brain so CI passes with
no network: a real KnowledgeBrain downloads an embedding model on construction, so we never
build one. The stub mimics the only surface HumanMemory touches — ``brain.mem.chunks`` (a
dict {cid: {'title','text'}}) and ``brain.recall(query, k=4)`` (list of associative hits).

Time is INJECTED everywhere (epoch ``now`` with DAY=86400.0) so the Ebbinghaus decay, tier
assignment and dreaming/consolidation are bit-for-bit reproducible. Warnings are silenced so
the run is clean. Idiom mirrors tests/test_journal_t5.py (plain unittest, known-value asserts).
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import math
import unittest

from memory.human_memory import HumanMemory, MemMeta

DAY = 86400.0


# ── stub brain (no network, no model) ────────────────────────────────────────────
class _StubMem:
    """Holds the chunk store the way KnowledgeBrain.mem does."""

    def __init__(self):
        self.chunks: dict[str, dict] = {}


class StubBrain:
    """Minimal offline stand-in: exposes .mem.chunks and a deterministic .recall()."""

    def __init__(self):
        self.mem = _StubMem()

    def add(self, cid: str, title: str, text: str, score: float = 1.0) -> None:
        self.mem.chunks[cid] = {"title": title, "text": text, "score": score}

    def recall(self, query: str, k: int = 4) -> list[dict]:
        q = (query or "").lower()
        hits = []
        for ch in self.mem.chunks.values():
            hay = (ch["title"] + " " + ch["text"]).lower()
            if not q or q in hay:
                hits.append({
                    "title": ch["title"],
                    "snippet": ch["text"][:80],
                    "score": float(ch.get("score", 1.0)),
                    "via": "stub",
                })
        hits.sort(key=lambda h: h["score"], reverse=True)
        return hits[:k]


def _brain(*specs):
    """specs: (cid, title, text[, score]) -> populated StubBrain."""
    b = StubBrain()
    for spec in specs:
        b.add(*spec)
    return b


# ── decay ────────────────────────────────────────────────────────────────────────
class TestDecay(unittest.TestCase):
    def test_strength_full_at_last_recalled(self):
        hm = HumanMemory(_brain(("c1", "Alpha doc", "alpha text")), now=0.0)
        self.assertAlmostEqual(hm.strength("Alpha doc", 0.0), 1.0, places=9)

    def test_strength_monotonically_decreases(self):
        hm = HumanMemory(_brain(("c1", "Alpha doc", "alpha text")), now=0.0)
        ts = [0.0, 1 * DAY, 5 * DAY, 20 * DAY, 60 * DAY]
        vals = [hm.strength("Alpha doc", t) for t in ts]
        for earlier, later in zip(vals, vals[1:]):
            self.assertGreater(earlier, later)
        for v in vals:
            self.assertGreaterEqual(v, 0.0)
            self.assertLessEqual(v, 1.0)

    def test_unknown_unit_is_zero(self):
        hm = HumanMemory(_brain(("c1", "Alpha doc", "alpha text")), now=0.0)
        self.assertEqual(hm.strength("no such memory", 0.0), 0.0)
        self.assertEqual(hm.strength("no such memory", 99 * DAY), 0.0)


# ── stability / spacing effect ─────────────────────────────────────────────────────
class TestStability(unittest.TestCase):
    def test_stability_grows_with_recall_count_and_importance(self):
        hm = HumanMemory(_brain(), now=0.0)
        weak = MemMeta(created=0.0, last_recalled=0.0, recall_count=0, importance=0.5)
        strong = MemMeta(created=0.0, last_recalled=0.0, recall_count=5, importance=0.5)
        important = MemMeta(created=0.0, last_recalled=0.0, recall_count=0, importance=0.9)
        self.assertGreater(hm.stability(strong), hm.stability(weak))
        self.assertGreater(hm.stability(important), hm.stability(weak))

    def test_reinforced_unit_outlasts_fresh_at_same_gap(self):
        # Both keep last_recalled at 0 so the Δt is identical; only recall_count differs.
        hm = HumanMemory(_brain(("a", "Recalled doc", "x"),
                                ("b", "Untouched doc", "y")), now=0.0)
        for _ in range(3):
            hm._note_recall("Recalled doc", 0.0)
        at = 10 * DAY
        s_recalled = hm.strength("Recalled doc", at)
        s_fresh = hm.strength("Untouched doc", at)
        self.assertGreater(s_recalled, s_fresh)
        self.assertLess(s_recalled, 1.0)


# ── recall (decay-aware retrieval) ─────────────────────────────────────────────────
class TestRecall(unittest.TestCase):
    def _hm(self):
        return HumanMemory(_brain(
            ("a", "Doc about trading alpha", "shared keyword body one", 0.9),
            ("b", "Doc about market beta", "shared keyword body two", 0.7),
            ("c", "Doc about risk gamma", "shared keyword body three", 0.5),
            ("d", "Doc about flow delta", "shared keyword body four", 0.3),
        ), now=0.0)

    def test_respects_k_and_hit_shape(self):
        hm = self._hm()
        hits = hm.recall("keyword", k=2, now=2 * DAY)
        self.assertLessEqual(len(hits), 2)
        for h in hits:
            self.assertIn("strength", h)
            self.assertGreaterEqual(h["strength"], 0.0)
            self.assertLessEqual(h["strength"], 1.0)
            self.assertIn(h["tier"], {"core", "recall", "archival"})
            self.assertIn("combined", h)

    def test_sorted_by_combined_desc(self):
        hm = self._hm()
        hits = hm.recall("keyword", k=4, now=2 * DAY)
        combos = [h["combined"] for h in hits]
        self.assertEqual(combos, sorted(combos, reverse=True))

    def test_reinforce_true_bumps_recall_count(self):
        hm = self._hm()
        hits = hm.recall("keyword", k=2, now=2 * DAY, reinforce=True)
        self.assertTrue(hits)
        for h in hits:
            self.assertEqual(hm.meta[h["title"]].recall_count, 1)
            self.assertEqual(hm.meta[h["title"]].last_recalled, 2 * DAY)

    def test_reinforce_false_leaves_counts(self):
        hm = self._hm()
        hits = hm.recall("keyword", k=2, now=2 * DAY, reinforce=False)
        self.assertTrue(hits)
        for h in hits:
            self.assertEqual(hm.meta[h["title"]].recall_count, 0)

    def test_empty_recall_is_safe(self):
        hm = HumanMemory(_brain(("a", "Only doc", "body")), now=0.0)
        self.assertEqual(hm.recall("nothing matches this", k=3, now=DAY), [])


# ── tiers ──────────────────────────────────────────────────────────────────────────
class TestTiers(unittest.TestCase):
    def test_reinforced_high_untouched_archival(self):
        hm = HumanMemory(_brain(
            ("a", "Hot memory frequently used", "x"),
            ("b", "Cold trivia never used", "y"),
        ), now=0.0)
        at = 30 * DAY
        for _ in range(10):
            hm._note_recall("Hot memory frequently used", at)
        hm.assign_tiers(at)
        self.assertIn(hm.meta["Hot memory frequently used"].tier, {"core", "recall"})
        self.assertEqual(hm.meta["Cold trivia never used"].tier, "archival")


# ── dreaming ───────────────────────────────────────────────────────────────────────
class TestDream(unittest.TestCase):
    def test_forgets_only_trivia(self):
        b = _brain(
            ("a", "Reinforced memory one trading strategies", "body a"),
            ("b", "Reinforced memory two market structure", "body b"),
            ("c", "Trivial note nobody will ever care about", "body c"),
        )
        hm = HumanMemory(b, now=0.0)
        hm._note_recall("Reinforced memory one trading strategies", 0.0)
        hm._note_recall("Reinforced memory two market structure", 0.0)

        report = hm.dream(60 * DAY)

        self.assertEqual(report["forgotten"], 1)
        # the only never-recalled, low-importance unit is gone (meta + brain chunks)
        self.assertNotIn("Trivial note nobody will ever care about", hm.meta)
        titles = {ch["title"] for ch in b.mem.chunks.values()}
        self.assertNotIn("Trivial note nobody will ever care about", titles)
        # the two rehearsed memories survive
        self.assertIn("Reinforced memory one trading strategies", hm.meta)
        self.assertIn("Reinforced memory two market structure", hm.meta)

    def test_keeps_high_importance_even_if_decayed(self):
        b = _brain(("a", "Critical irreplaceable knowledge entry", "body"))
        hm = HumanMemory(b, now=0.0)
        hm.remember("Critical irreplaceable knowledge entry", now=0.0, importance=0.7)
        # fully decayed after a long gap but importance >= 0.6 -> never auto-deleted
        self.assertLess(hm.strength("Critical irreplaceable knowledge entry", 60 * DAY), 0.15)

        report = hm.dream(60 * DAY)

        self.assertEqual(report["forgotten"], 0)
        self.assertIn("Critical irreplaceable knowledge entry", hm.meta)

    def test_consolidates_near_duplicate_titles(self):
        prefix = "A" * 48  # two titles sharing the 48-char consolidation prefix
        t1, t2 = prefix + " alpha variant", prefix + " beta variant"
        b = _brain(("a", t1, "dup body"), ("b", t2, "dup body"))
        hm = HumanMemory(b, now=0.0)
        hm.remember(t1, now=0.0, importance=0.6)
        hm.remember(t2, now=0.0, importance=0.8)
        for _ in range(2):
            hm._note_recall(t1, 0.0)
        for _ in range(3):
            hm._note_recall(t2, 0.0)

        report = hm.dream(0.0)

        self.assertGreaterEqual(report["consolidated"], 1)
        survivors = [t for t in (t1, t2) if t in hm.meta]
        self.assertEqual(len(survivors), 1)
        survivor = hm.meta[survivors[0]]
        self.assertEqual(survivor.recall_count, 5)        # 2 + 3 folded together
        # survivor keeps the MAX importance: t2 0.8 + 3 recalls*0.05 = 0.95 > t1's 0.70
        self.assertAlmostEqual(survivor.importance, 0.95, places=9)

    def test_report_keys_and_remaining(self):
        b = _brain(("a", "Doc one keep", "x"), ("b", "Doc two keep", "y"))
        hm = HumanMemory(b, now=0.0)
        hm._note_recall("Doc one keep", 0.0)
        hm._note_recall("Doc two keep", 0.0)
        report = hm.dream(DAY)
        self.assertEqual(set(report), {"forgotten", "promoted", "consolidated", "remaining"})
        self.assertEqual(report["remaining"], len(hm.meta))

    def test_determinism_same_inputs_same_report(self):
        def build():
            b = _brain(
                ("a", "Stable memory one", "body a"),
                ("b", "Stable memory two", "body b"),
                ("c", "Throwaway trivia item", "body c"),
            )
            hm = HumanMemory(b, now=0.0)
            hm._note_recall("Stable memory one", 0.0)
            hm._note_recall("Stable memory two", 0.0)
            return hm

        r1 = build().dream(45 * DAY)
        r2 = build().dream(45 * DAY)
        self.assertEqual(r1, r2)


# ── status ─────────────────────────────────────────────────────────────────────────
class TestStatus(unittest.TestCase):
    def test_status_json_able_and_tiers_sum(self):
        hm = HumanMemory(_brain(
            ("a", "Doc one", "x"),
            ("b", "Doc two", "y"),
            ("c", "Doc three", "z"),
        ), now=0.0)
        st = hm.status(5 * DAY)
        json.dumps(st)  # must be fully serialisable
        self.assertEqual(st["n_memories"], 3)
        self.assertEqual(sum(st["tiers"].values()), st["n_memories"])
        self.assertIn(st["reranker"], {"off", "flashrank"})

    def test_status_reranker_off_when_disabled(self):
        hm = HumanMemory(_brain(("a", "Doc", "x")), now=0.0, use_reranker=False)
        self.assertEqual(hm.status(0.0)["reranker"], "off")


if __name__ == "__main__":
    unittest.main()
