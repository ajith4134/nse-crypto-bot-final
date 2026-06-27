"""Acceptance tests for the Phase-4 knowledge brain: ingest -> recall works."""
from __future__ import annotations

import unittest

from memory.brain import KnowledgeBrain


class TestKnowledge(unittest.TestCase):
    def setUp(self):
        self.b = KnowledgeBrain()
        self.b.ingest_text("reservoir", "Reservoir computing uses a fixed random "
                           "recurrent network and trains only a linear readout. "
                           "It is fast on CPU and good for chaotic time series.")
        self.b.ingest_text("router", "The regime aware router sends each input to "
                           "the locally best node using dynamic classifier selection "
                           "based on a roughness score.")
        self.b.ingest_text("apples", "Apples are a sweet fruit that grow on trees in "
                           "temperate orchards around the world.")

    def test_recall_finds_relevant_doc(self):
        hits = self.b.recall("which model is good for chaotic time series on cpu?", k=1)
        self.assertTrue(hits)
        self.assertEqual(hits[0]["title"], "reservoir")

    def test_recall_distinguishes_topics(self):
        hits = self.b.recall("how does the router choose a node?", k=1)
        self.assertEqual(hits[0]["title"], "router")

    def test_graph_grows(self):
        s = self.b.stats()
        self.assertEqual(s["docs"], 3)
        self.assertGreater(s["by_type"]["concept"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
