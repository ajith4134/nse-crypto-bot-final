"""Tests for the multi-segment Freqtrade fork (vendor/freqtrade) + its glue.

Covers: per-segment Trade isolation (ContextVar scoping), new-trade segment stamping,
init_db idempotency, option ATM ranking in AllMarketsPairList, segment config fan-out in
worker_multi, and the config template's mlnb_segments emission. Pure in-memory / temp-env —
never touches the live journal, wallets or config.json.
"""
import os
import unittest
from datetime import datetime, timezone


class TestSegmentIsolation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from freqtrade.persistence import init_db
        init_db("sqlite://")

    def _mk(self, pair: str, seg: str | None):
        from freqtrade.enums import TradingMode
        from freqtrade.persistence import Trade
        from freqtrade.persistence.segment_context import segment_scope
        with segment_scope(seg):
            t = Trade(pair=pair, exchange="binance", open_rate=1.0, stake_amount=10,
                      amount=10, fee_open=0.0, fee_close=0.0, is_open=True,
                      open_date=datetime.now(timezone.utc), trading_mode=TradingMode.SPOT)
            self.assertEqual(t.bot_segment, seg)
            Trade.session.add(t)
            Trade.commit()
        return t

    def test_scoped_queries_and_aggregate(self):
        from freqtrade.persistence import Trade
        from freqtrade.persistence.segment_context import segment_scope, set_segment
        self._mk("AAA/USDT:USDT", "futures")
        self._mk("AAA/USDT", "spot")
        self._mk("AAA-OPT", "options")
        set_segment(None)
        self.assertGreaterEqual(Trade.get_open_trade_count(), 3)  # aggregate sees all
        with segment_scope("spot"):
            rows = Trade.get_trades_proxy(is_open=True)
            self.assertEqual({r.pair for r in rows}, {"AAA/USDT"})
            self.assertEqual(Trade.get_open_trade_count(), 1)
            self.assertEqual(Trade.total_open_trades_stakes(), 10)
        with segment_scope("futures"):
            self.assertEqual([t.pair for t in Trade.get_open_trades()], ["AAA/USDT:USDT"])

    def test_to_json_carries_segment(self):
        from freqtrade.persistence import Trade
        from freqtrade.persistence.segment_context import segment_scope
        self._mk("BBB/USDT", "prediction")
        with segment_scope("prediction"):
            j = Trade.get_trades_proxy(is_open=True)[0].to_json()
        self.assertEqual(j.get("bot_segment"), "prediction")

    def test_init_db_same_url_is_noop(self):
        from freqtrade.persistence import Trade, init_db
        before = Trade.session
        init_db("sqlite://")
        self.assertIs(Trade.session, before)


class TestOptionRank(unittest.TestCase):
    def test_atm_nearest_expiry_first_per_underlying(self):
        from freqtrade.plugins.pairlist.AllMarketsPairList import AllMarketsPairList
        syms = [
            "BTC/USDC:USDC-260710-90000-C",   # later expiry
            "BTC/USDC:USDC-260703-40000-C",   # deep OTM
            "BTC/USDC:USDC-260703-60000-C",   # ATM-ish (median strike)
            "AVAX/USDC:USDC-260703-4-P",      # deep OTM
            "AVAX/USDC:USDC-260703-6.5-P",    # ATM-ish
            "AVAX/USDC:USDC-260703-6.6-C",
        ]
        ranked = AllMarketsPairList._option_rank(syms)
        # first picks are each underlying's nearest-expiry median strike, interleaved
        first_two = set(ranked[:2])
        self.assertIn("BTC/USDC:USDC-260703-60000-C", first_two)
        self.assertIn("AVAX/USDC:USDC-260703-6.5-P", first_two)
        self.assertNotIn("BTC/USDC:USDC-260710-90000-C", ranked[:4])

    def test_non_option_symbols_keep_order(self):
        from freqtrade.plugins.pairlist.AllMarketsPairList import AllMarketsPairList
        syms = ["BTC/USDT", "ETH/USDT"]
        self.assertEqual(AllMarketsPairList._option_rank(syms), syms)


class TestSegmentConfigFanout(unittest.TestCase):
    def test_forced_overrides_keep_non_futures_dry(self):
        from freqtrade.worker_multi import _SEGMENT_FORCED, _deep_update
        base = {"dry_run": False, "trading_mode": "futures", "exchange": {"name": "binance"}}
        for seg in ("spot", "options", "prediction"):
            cfg = dict(base, exchange=dict(base["exchange"]))
            _deep_update(cfg, _SEGMENT_FORCED[seg])
            self.assertTrue(cfg["dry_run"], seg)   # never inherit live
        self.assertEqual(_SEGMENT_FORCED["options"]["trading_mode"], "option")
        self.assertEqual(_SEGMENT_FORCED["prediction"]["trading_mode"], "prediction")

    def test_trading_modes_extended(self):
        from freqtrade.constants import TRADING_MODES
        from freqtrade.enums import TradingMode
        self.assertIn("option", TRADING_MODES)
        self.assertIn("prediction", TRADING_MODES)
        self.assertEqual(TradingMode.OPTION.value, "option")
        self.assertEqual(TradingMode.PREDICTION.value, "prediction")

    def test_config_template_emits_segments(self):
        os.environ["CRYPTO_SEGMENTS"] = "futures,spot"
        try:
            from trading.crypto.freqtrade.config_template import build_config, enabled_segments
            self.assertEqual(enabled_segments(), ["futures", "spot"])
            c = build_config()
            segs = c["mlnb_segments"]
            self.assertTrue(segs["futures"]["enabled"])
            self.assertTrue(segs["spot"]["enabled"])
            self.assertFalse(segs["options"]["enabled"])
            self.assertEqual(segs["options"]["overrides"]["exchange"]["name"], "deribit")
            self.assertEqual(
                segs["prediction"]["overrides"]["exchange"]["name"], "predictionpaper")
        finally:
            os.environ.pop("CRYPTO_SEGMENTS", None)


if __name__ == "__main__":
    unittest.main()
