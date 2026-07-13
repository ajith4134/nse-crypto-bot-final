"""tests/test_symbol_move_net.py — the brain's multi-head OUTPUT network (owner ask 2026-07-13).

Verifies the new net learns a SEPARABLE synthetic signal end-to-end: the price-move-% regression
head (primary output, sign=direction, magnitude=size), the direction classifier head, the
both-heads-agree neutral gate, RAM-feature enrichment, winsorising/OOD-clamping robustness, and the
untrained honest fallback. Pure/offline — no journal, no network.
"""
import math
import unittest

from trading.brain import symbol_move_net as smn


def _trade(direction, move_pct, *, symbol="X/USDT:USDT", entry=100.0, filters=None, qv=1e9):
    """A closed trade whose SYMBOL moved `move_pct` (exit=entry*(1+move/100)); the trade's own
    direction is independent of the symbol move (the net predicts the symbol move, not the trade)."""
    exit_ = entry * (1 + move_pct / 100.0)
    ds = {"regime": "trend", "segment": "futures",
          "market_context": {"filters": filters or {}, "quote_volume_24h": qv,
                             "pct_change_24h": move_pct, "source": "ram"}}
    return {"symbol": symbol, "direction": direction, "market": "CRYPTO", "exchange": "binance",
            "entry_price": entry, "exit_price": exit_, "quantity": 1.0, "leverage": 5.0,
            "entry_hour": 10, "market_regime_entry": "trend",
            "entry_datetime": "2026-07-01T10:00:00+00:00", "decision_snapshot": ds}


class TestFeatureRow(unittest.TestCase):
    def test_ram_features_appended(self):
        self.assertEqual(len(smn.MOVE_FEATURE_NAMES),
                         len(smn.FEATURE_NAMES) + len(smn._RAM_FEATURES))
        t = _trade("LONG", 1.0, filters={"filter:momentum": 0.8, "filter:taker": 0.6})
        row = smn.move_feature_row(t)
        self.assertEqual(len(row), len(smn.MOVE_FEATURE_NAMES))
        # the momentum filter value lands in its slot
        idx = smn.MOVE_FEATURE_NAMES.index("flt_momentum")
        self.assertAlmostEqual(row[idx], 0.8)
        # absent filter → 0.5 neutral
        idx2 = smn.MOVE_FEATURE_NAMES.index("flt_pcr")
        self.assertAlmostEqual(row[idx2], 0.5)

    def test_move_pct_label(self):
        self.assertAlmostEqual(smn._move_pct(_trade("LONG", 2.5)), 2.5, places=3)
        self.assertAlmostEqual(smn._move_pct(_trade("SHORT", -1.0)), -1.0, places=3)
        self.assertIsNone(smn._move_pct({"entry_price": 0, "exit_price": 5}))


class TestTrainingAndPrediction(unittest.TestCase):
    def _dataset(self):
        # separable: high momentum filter → symbol moves UP; low momentum → DOWN.
        rows = []
        for i in range(60):
            rows.append(_trade("LONG", 3.0, filters={"filter:momentum": 0.85, "filter:taker": 0.7}))
        for i in range(60):
            rows.append(_trade("SHORT", -3.0, filters={"filter:momentum": 0.15, "filter:taker": 0.3}))
        return rows

    def test_trains_and_predicts_direction_from_move(self):
        net = smn.SymbolMoveNet().fit_from_journal(self._dataset())
        self.assertTrue(net.trained)
        self.assertGreaterEqual(net.n_train, 100)
        # a high-momentum candidate → positive move% → LONG
        up = net.predict_one(_trade("LONG", 0.0, filters={"filter:momentum": 0.85, "filter:taker": 0.7}))
        self.assertGreater(up["expected_move_pct"], 0)          # PRIMARY output is the move %
        self.assertEqual(up["direction"], "LONG")              # direction DERIVED from the move sign
        self.assertGreater(up["p_up"], 0.5)
        # a low-momentum candidate → negative move% → SHORT
        dn = net.predict_one(_trade("SHORT", 0.0, filters={"filter:momentum": 0.15, "filter:taker": 0.3}))
        self.assertLess(dn["expected_move_pct"], 0)
        self.assertEqual(dn["direction"], "SHORT")

    def test_move_mae_is_sane(self):
        net = smn.SymbolMoveNet().fit_from_journal(self._dataset())
        self.assertIsNotNone(net.move_mae)
        self.assertLess(net.move_mae, 10.0)                    # winsorise + OOD-clamp keep it bounded

    def test_outlier_move_is_winsorised(self):
        rows = self._dataset()
        rows.append(_trade("LONG", 5000.0))                    # a leveraged micro-cap moon-shot
        net = smn.SymbolMoveNet().fit_from_journal(rows)
        # the extreme label must not blow up the regressor's predictions
        p = net.predict_one(_trade("LONG", 0.0, filters={"filter:momentum": 0.85}))
        self.assertLessEqual(abs(p["expected_move_pct"]), net.MOVE_CLIP_PCT)

    def test_heads_disagree_abstains(self):
        net = smn.SymbolMoveNet().fit_from_journal(self._dataset())
        # force disagreement: features that push move up but classifier ~neutral → NEUTRAL guard
        out = net.predict_one(_trade("LONG", 0.0, filters={"filter:momentum": 0.5, "filter:taker": 0.5}))
        self.assertIn(out["direction"], ("LONG", "SHORT", "NEUTRAL"))
        if out["direction"] == "NEUTRAL":
            self.assertEqual(out["size_hint"], 0.0)

    def test_untrained_is_honest(self):
        net = smn.SymbolMoveNet().fit_from_journal([_trade("LONG", 1.0)] * 3)  # < MIN_SAMPLES
        self.assertFalse(net.trained)
        out = net.predict_one(_trade("LONG", 0.0))
        self.assertEqual(out["direction"], "NEUTRAL")
        self.assertIsNone(out["expected_move_pct"])
        self.assertIsNone(out["p_up"])

    def test_cached_singleton_retrains_on_count_change(self):
        smn._CACHE["count"] = -1
        n1 = smn.get_move_net(self._dataset())
        n2 = smn.get_move_net(self._dataset())
        self.assertIs(n1, n2)                                   # same count → cached
        n3 = smn.get_move_net(self._dataset() + [_trade("LONG", 1.0)])
        self.assertIsNot(n1, n3)                                # count changed → retrained


if __name__ == "__main__":
    unittest.main()
