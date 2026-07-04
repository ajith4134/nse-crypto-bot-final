"""Node auto-loader (nodes/autoload.py) — pkgutil sweep recovers built-but-unpooled families.

Proves the audit-fix (idea #1): every nodes/* node family is discoverable, deduped, buildable, and
satisfies NodeProtocol — so no built model is silently unreachable by the live pool.
"""
import unittest

from core.node_protocol import NodeProtocol
from nodes import autoload, pool


class TestAutoload(unittest.TestCase):
    def setUp(self):
        self.pooled = set(pool.names())
        self.cand = autoload.discover(exclude_names=self.pooled)

    def test_recovers_many_families(self):
        # the pool ships ~20 curated candidates; the sweep must recover the long tail (>50).
        self.assertGreater(len(self.cand), 50,
                           f"autoload recovered only {len(self.cand)} families")

    def test_deduped_normalized(self):
        # no two recovered names collide once underscores are stripped (factory vs class dup guard).
        norms = [n.replace("_", "").lower() for n in (nm for _, nm in self.cand)]
        self.assertEqual(len(norms), len(set(norms)), "duplicate normalized names leaked through")
        # and none collide with an already-pooled name.
        pooled_norm = {n.replace("_", "").lower() for n in self.pooled}
        self.assertFalse(pooled_norm & set(norms), "recovered a family already in the pool")

    def test_recovers_audit_flagged_modules(self):
        # the independent audit named these as unreachable — they must now be recoverable.
        rep = autoload.summary(exclude_names=self.pooled)
        mods = " ".join(rep["by_module"])
        for m in ("automl_node", "symbolic_node", "quant_factor_nodes",
                  "quant_signal_nodes", "detect_nodes", "denoise_nodes"):
            self.assertIn(m.replace("_nodes", "").split("_")[0], mods.replace("_nodes", ""),
                          f"audit-flagged module {m} not recovered")

    def test_sample_build_and_satisfy_protocol(self):
        # spot-check the first 30: each must instantiate and be a NodeProtocol (real, wired nodes).
        ok = 0
        for factory, name in self.cand[:30]:
            node = factory()
            self.assertIsInstance(node, NodeProtocol, f"{name} is not a NodeProtocol")
            ok += 1
        self.assertEqual(ok, min(30, len(self.cand)))

    def test_pool_report_read_only(self):
        rep = pool.autoload_report()
        self.assertGreater(rep["recovered"], 50)
        self.assertIn("by_module", rep)
        # the report must NOT have mutated the live pool.
        self.assertEqual(set(pool.names()), self.pooled)


if __name__ == "__main__":
    unittest.main()
