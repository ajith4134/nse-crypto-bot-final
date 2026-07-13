"""Tests for endpoint_discovery (adopt item 4) — surface unmapped web-app data endpoints."""
import unittest
from pathlib import Path
import tempfile
from trading import state
from trading.broker_sense import endpoint_discovery as ed


class TestDiscover(unittest.TestCase):
    def setUp(self):
        self._o = state.STATE_DIR
        self._t = tempfile.mkdtemp()
        state.STATE_DIR = Path(self._t)
        state.save_json("broker_endpoints.json", {"upstox": {
            "pro.upstox.com/api/option-chain": {"kind": "option_chain", "n_seen": 40,
                "content_type": "application/json", "sample_keys": ["strike", "iv", "delta"]},
            "pro.upstox.com/api/positions-live": {"kind": "unknown", "n_seen": 30,
                "content_type": "application/json", "sample_keys": ["ltp", "bid", "ask", "symbol"]},
            "api-js.mixpanel.com/engage": {"kind": "unknown", "n_seen": 133,
                "content_type": "application/json", "sample_keys": ["event", "props"]},
            "pro.upstox.com/kyc-error": {"kind": "unknown", "n_seen": 50,
                "content_type": "application/json", "sample_keys": ["Close", "Cancel"]},
        }})

    def tearDown(self):
        state.STATE_DIR = self._o

    def test_buckets(self):
        d = ed.discover("upstox")["upstox"]
        cand = [c["pattern"] for c in d["candidates"]]
        mapped = [m["kind"] for m in d["mapped"]]
        self.assertIn("pro.upstox.com/api/positions-live", cand)   # unmapped + data-shaped
        self.assertIn("option_chain", mapped)                      # already mapped
        # mixpanel = noise (host), KYC = not data-shaped (1 generic key) → neither is a candidate
        self.assertNotIn("api-js.mixpanel.com/engage", cand)
        self.assertNotIn("pro.upstox.com/kyc-error", cand)

    def test_report_runs(self):
        self.assertIn("upstox", ed.report("upstox"))


if __name__ == "__main__":
    unittest.main()
