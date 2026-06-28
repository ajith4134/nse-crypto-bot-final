"""P4.2 acceptance: human-like ASSOCIATIVE recall (Personalized-PageRank + RRF fusion).

Verifies the upgraded KnowledgeBrain.recall: graph spreading-activation runs, results fuse
vector + associative channels, each carries a `via` tag, salience reinforces on recall, and
the vector-only path still works (backward-compatible).
"""
from __future__ import annotations

import unittest

from memory.brain import KnowledgeBrain


class TestAssociativeRecall(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        b = KnowledgeBrain()
        b.ingest_text("routing", "Phase 3 adds a learned router that sends hard instances to "
                                 "specialist nodes via dynamic ensemble selection and routing.")
        b.ingest_text("memory", "The brain stores documents as vector embeddings and a concept "
                                "graph, recalling them associatively by spreading activation.")
        b.ingest_text("chaos", "Reservoir computing and nolds measure chaos and entropy in "
                               "noisy time series on CPU.")
        cls.b = b

    def test_personalized_ranks_runs(self):
        seeds = {list(self.b.mem.chunks)[0]: 1.0}
        pr = self.b.graph.personalized_ranks(seeds)
        self.assertIsInstance(pr, dict)
        self.assertTrue(pr)                                  # PPR/spreading returns scored nodes

    def test_recall_fuses_and_tags(self):
        res = self.b.recall("how does the learned router work?", k=3)
        self.assertTrue(res)
        for r in res:
            self.assertEqual({"title", "score", "snippet", "concepts", "via"}, set(r))
            self.assertIn(r["via"], ("vector", "associative"))
            self.assertGreater(r["score"], 0)

    def test_vector_only_path(self):
        res = self.b.recall("chaos entropy", k=2, associative=False)
        self.assertTrue(res)
        self.assertTrue(all("title" in r for r in res))

    def test_salience_reinforces(self):
        cid = list(self.b.mem.chunks)[0]
        before = self.b.access.get(cid, 0)
        self.b.recall("router", k=3)                         # recall increments access counts
        self.assertGreaterEqual(sum(self.b.access.values()), before + 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
