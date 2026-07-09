"""Tests for invent-beyond #3 — regime-contextual champion bandit allocator + its wiring."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import trading.state as tstate


class _StateSandbox(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old = tstate.STATE_DIR
        tstate.STATE_DIR = Path(self._tmp.name)

    def tearDown(self):
        tstate.STATE_DIR = self._old
        self._tmp.cleanup()


class TestChampionBandit(_StateSandbox):
    def test_no_champions_gives_honest_empty_allocation(self):
        from trading.strategy import champion_bandit as cb
        self.assertEqual(cb.suggest_allocation("CRYPTO", arms=[]), {})

    def test_allocation_normalizes_and_covers_all_arms(self):
        from trading.strategy import champion_bandit as cb
        alloc = cb.suggest_allocation("CRYPTO", arms=["a", "b", "c"], regime="neutral")
        self.assertEqual(set(alloc), {"a", "b", "c"})
        self.assertAlmostEqual(sum(alloc.values()), 1.0, places=2)

    def test_posterior_learns_and_shifts_allocation(self):
        from trading.strategy import champion_bandit as cb
        for _ in range(30):
            cb.update("crypto", "winner", win=True, regime="neutral")
            cb.update("crypto", "loser", win=False, regime="neutral")
        wins = sum(cb.suggest_allocation("CRYPTO", arms=["winner", "loser"],
                                         regime="neutral")["winner"] > 0.5
                   for _ in range(20))
        self.assertGreater(wins, 15)          # Beta(31,1) vs Beta(1,31): winner dominates

    def test_regime_buckets_are_independent(self):
        from trading.strategy import champion_bandit as cb
        for _ in range(10):
            cb.update("crypto", "s", win=True, regime="risk_on")
        d = tstate.load_json("champion_bandit.json", {})
        self.assertEqual(d["arms"]["crypto|s|risk_on"]["w"], 10)
        self.assertNotIn("crypto|s|risk_off", d["arms"])

    def test_stake_scale_bounded_and_neutral_for_unknown(self):
        from trading.strategy import champion_bandit as cb
        for _ in range(50):
            cb.update("crypto", "hot", win=True, regime="neutral")
            cb.update("crypto", "cold", win=False, regime="neutral")
        arms = ["hot", "cold"]
        self.assertEqual(cb.stake_scale("CRYPTO", "not-an-arm", regime="neutral",
                                        arms=arms), 1.0)         # unknown → never punished
        s = cb.stake_scale("CRYPTO", "hot", regime="neutral", arms=arms)
        self.assertTrue(0.5 <= s <= 2.0)

    def test_status_uses_persisted_arms_never_the_library(self):
        from trading.strategy import champion_bandit as cb
        # suggest_allocation with explicit arms persists nothing; simulate the executor
        # having persisted an arm list, then status() must sample from it cheaply.
        d = tstate.load_json("champion_bandit.json", {})
        d["arms"] = {}
        d["last_arms_crypto"] = ["x", "y"]
        tstate.save_json("champion_bandit.json", d)
        st = cb.status()
        self.assertEqual(set(st["allocation_crypto"]), {"x", "y"})


class TestCloseLearnOnce(_StateSandbox):
    """The close-time learning guard: exactly one credit per trade id, however many times
    map_trade re-runs (closed_view rebuilds the view on every dashboard poll)."""

    def setUp(self):
        super().setUp()
        import trading.broker_sense.broker_features as bf
        import trading.crypto.freqtrade_ingest as fi
        bf._PERF = None
        fi._LEARN_SEEN = None
        fi._LEARN_SEEN_SET = set()

    def tearDown(self):
        import trading.broker_sense.broker_features as bf
        import trading.crypto.freqtrade_ingest as fi
        bf._PERF = None
        fi._LEARN_SEEN = None
        fi._LEARN_SEEN_SET = set()
        super().tearDown()

    def _t(self, pnl=5.0, strategy="pysr_crypto_0_2"):
        class T:                                  # the two fields _learn_from_close reads
            net_pnl = pnl
            strategy_name = strategy
        return T()

    def test_learning_fires_exactly_once_per_trade(self):
        import trading.broker_sense.broker_features as bf
        from trading.crypto import freqtrade_ingest as fi
        # picker snapshot that lists the pair → credit_symbol has something to credit
        tstate.save_json("broker_feature_snapshots.json",
                         {"binance": {"gainers": {"syms": ["BTC/USDT:USDT"], "ts": 0}}})
        ft = {"trade_id": 7, "pair": "BTC/USDT:USDT"}
        for _ in range(5):                        # five dashboard polls of the same trade
            fi._learn_from_close(ft, self._t())
        ent = bf.get_perf().perf.get("binance|gainers")
        self.assertIsNotNone(ent)
        self.assertEqual(ent["n"], 1)             # ONE credit, not five
        d = tstate.load_json("champion_bandit.json", {})
        keys = [k for k in d.get("arms", {}) if k.startswith("crypto|pysr_crypto_0_2|")]
        self.assertEqual(len(keys), 1)
        self.assertEqual(d["arms"][keys[0]]["w"], 1)  # ONE posterior win

    def test_seen_guard_persists_across_process_restart(self):
        from trading.crypto import freqtrade_ingest as fi
        ft = {"trade_id": 8, "pair": "ETH/USDT:USDT"}
        fi._learn_from_close(ft, self._t())
        fi._LEARN_SEEN = None                     # simulate a fresh process
        fi._LEARN_SEEN_SET = set()
        fi._learn_from_close(ft, self._t())
        d = tstate.load_json("champion_bandit.json", {})
        keys = [k for k in d.get("arms", {}) if k.startswith("crypto|")]
        total = sum(d["arms"][k]["w"] + d["arms"][k]["l"] for k in keys)
        self.assertEqual(total, 1)                # still one observation

    def test_missing_trade_id_is_a_safe_noop(self):
        from trading.crypto import freqtrade_ingest as fi
        fi._learn_from_close({"pair": "X/USDT"}, self._t())   # must not raise or credit
        self.assertEqual(tstate.load_json("close_learn_seen.json", {}).get("ids"), None)


if __name__ == "__main__":
    unittest.main()
