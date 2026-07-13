"""Tests for memory/neurons.py — the instruction-shaped Neuron store (R15/R16/R24)."""
import tempfile
import unittest

from memory.neurons import KINDS, NeuronStore


def _store():
    return NeuronStore(tempfile.mkdtemp())


class NeuronStoreTest(unittest.TestCase):
    def test_action_facet_mandatory_r24(self):
        s = _store()
        with self.assertRaises(ValueError):
            s.add("fact", "t", "body", "")
        with self.assertRaises(ValueError):
            s.add("fact", "t", "body", "   ")

    def test_kind_enforced(self):
        s = _store()
        with self.assertRaises(ValueError):
            s.add("nonsense-kind", "t", "b", "a")
        for kind in KINDS:
            s.add(kind, f"title {kind}", "body text here", "use it like this",
                  auto_link=False)
        self.assertEqual(s.status()["neurons"], len(KINDS))

    def test_search_and_rehydrate(self):
        root = tempfile.mkdtemp()
        s = NeuronStore(root)
        n = s.add("fact", "RSI oversold threshold",
                  "RSI below 30 marks oversold.", "Consider longs when RSI<30.")
        hits = s.search("RSI oversold")
        self.assertTrue(hits and hits[0]["id"] == n.id)
        s2 = NeuronStore(root)                      # cold reload from sqlite
        self.assertEqual(s2.status()["neurons"], 1)
        self.assertEqual(s2.get(n.id).title, n.title)

    def test_auto_link_by_title_entity(self):
        s = _store()
        a = s.add("fact", "RSI oversold", "RSI below 30 marks oversold.", "long bias")
        s.add("fact", "RSI divergence", "price LL, RSI HL.", "upgrade long score")
        self.assertTrue(any(x["title"] == "RSI divergence" for x in s.neighbors(a.id)))

    def test_use_evidence_drives_confidence(self):
        s = _store()
        n = s.add("instruction", "entry rule", "steps", "follow steps", auto_link=False)
        s.record_use(n.id, win=True)
        s.record_use(n.id, win=True)
        s.record_use(n.id, win=False, domain="navigation")
        got = s.get(n.id)
        self.assertEqual(got.stats["times_used"], 3)
        self.assertAlmostEqual(got.confidence, (2 + 1) / (3 + 2))  # Laplace
        self.assertEqual(got.stats["by_domain"]["navigation"],
                         {"uses": 1, "wins": 0, "losses": 1})

    def test_derive_lineage_and_versions_r26(self):
        s = _store()
        p = s.add("instruction", "route v1", "steps v1", "do v1", auto_link=False)
        q = s.add("instruction", "route alt", "steps alt", "do alt", auto_link=False)
        child = s.derive([p.id, q.id], title="route v2", body="combined steps",
                         action="do combined", rel="crossover-of")
        self.assertEqual(child.version, 2)
        self.assertEqual(set(child.parents), {p.id, q.id})
        ids = {x["id"] for x in s.lineage(child.id)}
        self.assertIn(p.id, ids)

    def test_growth_and_graph_snapshot_r28(self):
        s = _store()
        a = s.add("fact", "alpha beta", "alpha beta gamma", "use alpha")
        s.add("fact", "alpha gamma", "alpha gamma delta", "use gamma")
        g = s.snapshot_graph()
        self.assertEqual(g["total_neurons"], 2)
        self.assertGreaterEqual(g["total_links"], 1)
        growth = s.growth(buckets=2)
        self.assertEqual(sum(b["neurons"] for b in growth), 2)

    def test_exam_recording(self):
        s = _store()
        n = s.add("concept", "value area", "POC/VAH/VAL", "trade edges of VA",
                  auto_link=False)
        s.record_exam(n.id, 0.87)
        self.assertAlmostEqual(s.get(n.id).exam["last_score"], 0.87)


if __name__ == "__main__":
    unittest.main()
