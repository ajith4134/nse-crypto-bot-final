"""M1 (2026-07-12): the D6 meta-labeler is a STACKING meta-learner over indicator_fusion lens
outputs (replacing CORTEX's fixed hierarchical gate, which underperformed naive baseline). This
locks: (1) the shared lens_features extractor is stable + serve-safe, (2) _featurize merges the
lens columns, (3) the model trains on and can learn a lens signal, (4) truth_ledger.record carries
features through to the training example.
"""
import json
import os
import tempfile
import unittest

from trading import state


class TestMetaStackingFeatures(unittest.TestCase):
    def test_lens_features_extract_and_defaults(self):
        from trading.direction import meta_labeler as ml
        fz = {"available": True, "direction": "long", "p_up": 0.71, "confluence": 0.42,
              "order_flow": {"tilt": 0.3}, "ai_select": {"ai_selected": True},
              "volume_profile": {"available": True, "tilt": 0.5},
              "direction_equation": {"tilt": 0.15}, "vision_dir": 0.33}
        lf = ml.lens_features(fz)
        self.assertEqual(lf["f_confluence"], 0.42)
        self.assertEqual(lf["f_orderflow"], 0.3)
        self.assertEqual(lf["f_ai"], 1.0)
        self.assertEqual(lf["f_direq"], 0.15)
        # unavailable → safe zeros, p_up defaults to 0.5 (never fabricated direction)
        z = ml.lens_features(None)
        self.assertEqual(z["f_p_up"], 0.5)
        self.assertEqual(z["f_confluence"], 0.0)
        # every declared lens column is present (serve/train parity)
        feat = ml._featurize({"source": "indicator_fusion", "direction": "LONG",
                              "confidence": 0.6, "features": lf})
        for k in ml._LENS_NUMS:
            self.assertIn(k, feat)

    def test_cortex_features_folded_into_stack(self):
        from trading.direction import meta_labeler as ml
        cf = ml.cortex_features({"side": "short", "confidence": 0.8})
        self.assertEqual(cf["f_cortex_side"], -1.0)
        self.assertEqual(cf["f_cortex_conf"], 0.8)
        # absent cortex → safe zeros (learnable input, never fabricated)
        self.assertEqual(ml.cortex_features(None), {"f_cortex_side": 0.0, "f_cortex_conf": 0.0})
        # cortex columns live in the same stacking feature space as the lenses
        self.assertIn("f_cortex_side", ml._LENS_NUMS)
        merged = {**ml.lens_features(None), **ml.cortex_features({"side": "long", "confidence": 0.5})}
        feat = ml._featurize({"source": "cortex", "direction": "LONG", "features": merged})
        self.assertEqual(feat["f_cortex_side"], 1.0)

    def test_record_carries_features(self):
        from trading.direction import truth_ledger as tl
        d = tempfile.mkdtemp()
        old = state.STATE_DIR
        state.STATE_DIR = d
        try:
            os.environ["DIRECTION_TRUTH"] = "1"        # ensure ledger enabled
            ok = tl.record(symbol="BTC", market="CRYPTO", segment="futures", direction="long",
                           source="indicator_fusion", confidence=0.7,
                           features={"f_confluence": 0.42, "f_orderflow": 0.3})
            self.assertTrue(ok)
            pend = tl._pending_path()
            rows = [json.loads(x) for x in pend.read_text().splitlines() if x.strip()]
            self.assertTrue(rows and rows[-1].get("features", {}).get("f_confluence") == 0.42)
        finally:
            state.STATE_DIR = old


if __name__ == "__main__":
    unittest.main()
