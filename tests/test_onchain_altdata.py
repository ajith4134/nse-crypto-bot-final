"""AI-scientist idea #11 — on-chain + whale alt-data lane (hermetic, injected fetchers)."""
import unittest

from trading.altdata.onchain import OnChainAltData, _composite


def _stub_fetchers(fg=70, avg_tx=1.2, mempool=40000):
    return {
        "fear_greed": lambda: {"value": fg, "classification": "Greed"},
        "network": lambda: {"n_tx_24h": 400000, "btc_sent_24h": avg_tx * 400000,
                            "avg_tx_btc": avg_tx, "fee_fastest": 20},
        "whale": lambda: {"mempool_count": mempool, "mempool_vsize": mempool * 300},
    }


class TestOnChainAltData(unittest.TestCase):
    def test_snapshot_aggregates_sources(self):
        snap = OnChainAltData(fetchers=_stub_fetchers()).snapshot()
        self.assertTrue(snap["available"])
        self.assertTrue(all(snap["sources_live"].values()))
        self.assertIsNone(snap["errors"])
        self.assertTrue(-1.0 <= snap["composite"] <= 1.0)
        self.assertIn("fear_greed", snap)
        self.assertEqual(snap["fear_greed"]["value"], 70)

    def test_composite_direction(self):
        # greedy + large avg tx + full mempool → positive (risk-on); fearful + quiet → negative
        greedy = OnChainAltData(fetchers=_stub_fetchers(fg=90, avg_tx=2.0, mempool=60000)).snapshot()
        fearful = OnChainAltData(fetchers=_stub_fetchers(fg=10, avg_tx=0.1, mempool=5000)).snapshot()
        self.assertGreater(greedy["composite"], fearful["composite"])
        self.assertGreater(greedy["composite"], 0)
        self.assertLess(fearful["composite"], 0)

    def test_partial_source_failure_never_breaks(self):
        fetchers = _stub_fetchers()
        fetchers["network"] = lambda: (_ for _ in ()).throw(RuntimeError("blockchain.info down"))
        snap = OnChainAltData(fetchers=fetchers).snapshot()
        self.assertTrue(snap["available"])                 # other sources still live
        self.assertFalse(snap["sources_live"]["network"])
        self.assertIn("network", snap["errors"])
        self.assertTrue(-1.0 <= snap["composite"] <= 1.0)  # missing source contributes 0

    def test_all_sources_down_is_honest(self):
        boom = lambda: (_ for _ in ()).throw(RuntimeError("offline"))
        snap = OnChainAltData(fetchers={"fear_greed": boom, "network": boom, "whale": boom}).snapshot()
        self.assertFalse(snap["available"])
        self.assertEqual(snap["composite"], 0.0)           # nothing fabricated

    def test_composite_bounded(self):
        self.assertTrue(-1.0 <= _composite({"value": 100}, {"avg_tx_btc": 99}, {"mempool_count": 9e9}) <= 1.0)


if __name__ == "__main__":
    unittest.main()
