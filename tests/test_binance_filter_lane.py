"""Tests for the Binance-filter TOP-N breadth lane ranker (Stage 1).

The ranker must score/sort the UI-captured universe by named filter presets, drop empty reads,
respect adaptive-N, and never crash on missing captures. Universe rows are synthetic so the tests
are deterministic and independent of the live ui_market store.
"""
import unittest

from trading.broker_sense import binance_filter_lane as bfl


def _row(sym, pct=None, vol=None, funding=None, taker=None):
    return {"symbol": sym, "last": 1.0, "pct_change": pct, "volume": vol,
            "funding_rate": funding, "open_interest": None,
            "long_short_ratio": None, "taker_imbalance": taker}


class BinanceFilterLaneTest(unittest.TestCase):
    def test_momentum_ranks_biggest_liquid_mover_first(self):
        rows = [_row("A", pct=2.0, vol=1_000_000),
                _row("B", pct=12.0, vol=5_000_000),     # biggest move + most liquid
                _row("C", pct=1.0, vol=100)]
        r = bfl.rank(rows, "momentum")
        self.assertEqual(r[0]["symbol"], "B")
        self.assertTrue(all("filter_score" in x for x in r))

    def test_empty_signal_rows_dropped(self):
        rows = [_row("A", pct=None, vol=None), _row("B", pct=5.0, vol=1_000)]
        r = bfl.rank(rows, "momentum")
        self.assertEqual([x["symbol"] for x in r], ["B"])   # A scores 0 → dropped

    def test_funding_extreme_prefers_crowded_funding(self):
        rows = [_row("A", pct=1.0, vol=1_000_000, funding=0.0001),
                _row("B", pct=1.0, vol=1_000_000, funding=0.02)]   # extreme funding
        r = bfl.rank(rows, "funding_extreme")
        self.assertEqual(r[0]["symbol"], "B")

    def test_squeeze_uses_taker_imbalance(self):
        rows = [_row("A", pct=2.0, vol=1_000_000, taker=0.05),
                _row("B", pct=2.0, vol=1_000_000, taker=0.9)]
        r = bfl.rank(rows, "squeeze")
        self.assertEqual(r[0]["symbol"], "B")

    def test_topn_caps_result(self):
        rows = [_row(f"S{i}", pct=float(i + 1), vol=1_000_000) for i in range(50)]
        r = bfl.rank(rows, "momentum", n=10)
        self.assertEqual(len(r), 10)
        # highest pct first
        self.assertEqual(r[0]["symbol"], "S49")

    def test_unknown_preset_falls_back_to_liquidity(self):
        rows = [_row("A", pct=99.0, vol=10), _row("B", pct=1.0, vol=9_000_000)]
        r = bfl.rank(rows, "does_not_exist")
        self.assertEqual(r[0]["symbol"], "B")               # liquidity → most volume wins

    def test_adaptive_n_default(self):
        self.assertEqual(bfl.adaptive_n(), 20)

    def test_score_never_crashes_on_missing(self):
        self.assertEqual(bfl.score({"symbol": "X"}, "momentum"), 0.0)
        self.assertEqual(bfl.score({"symbol": "X"}, "squeeze"), 0.0)

    def test_to_pair_bridges_flat_to_tradeable(self):
        self.assertEqual(bfl.to_pair("DODOXUSDT", "futures"), "DODOX/USDT:USDT")
        self.assertEqual(bfl.to_pair("DODOXUSDT", "spot"), "DODOX/USDT")
        self.assertEqual(bfl.to_pair("SXTUSDC", "futures"), "SXT/USDT:USDT")   # quote normalized
        self.assertEqual(bfl.to_pair("MMT/USDT:USDT", "futures"), "MMT/USDT:USDT")  # already-pair
        self.assertEqual(bfl.to_pair("", "futures"), "/USDT:USDT")             # degenerate, no crash

    def test_features_from_row_is_pure(self):
        # taker imbalance derived from buy/sell handled in features(); here just ensure the
        # ranker consumes a pre-built row without touching the live store
        rows = [_row("A", pct=3.0, vol=2_000_000)]
        self.assertEqual(bfl.rank(rows, "momentum")[0]["symbol"], "A")


if __name__ == "__main__":
    unittest.main()
