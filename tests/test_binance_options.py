"""tests/test_binance_options.py — Binance options IV/skew regime gauge.

Offline: monkeypatch the eapi/v1/mark payload (no network). Asserts ATM IV, 25Δ skew, regime.
"""
import unittest
from unittest import mock

from trading.broker_sense import binance_options as opt


# nearest expiry 260101: ATM call/put |delta|~0.5, 25Δ put IV (0.70) > 25Δ call IV (0.55) → put skew
_FAKE_MARK = [
    {"symbol": "BTC-260101-100000-C", "markIV": "0.60", "delta": "0.50"},
    {"symbol": "BTC-260101-100000-P", "markIV": "0.62", "delta": "-0.50"},
    {"symbol": "BTC-260101-120000-C", "markIV": "0.55", "delta": "0.25"},
    {"symbol": "BTC-260101-080000-P", "markIV": "0.70", "delta": "-0.25"},
    {"symbol": "BTC-260601-100000-C", "markIV": "0.90", "delta": "0.50"},  # later expiry, ignored for ATM
    {"symbol": "ETH-260101-004000-C", "markIV": "0.80", "delta": "0.50"},
    {"symbol": "ETH-260101-004000-P", "markIV": "0.82", "delta": "-0.50"},
]


class TestOptions(unittest.TestCase):
    def setUp(self):
        opt.clear_cache()

    def test_atm_iv_and_skew(self):
        with mock.patch.object(opt, "_get_json", return_value=_FAKE_MARK):
            s = opt.iv_summary("BTC")
        self.assertEqual(s["expiry"], "260101")           # nearest expiry chosen
        self.assertAlmostEqual(s["atm_iv"], round((0.60 + 0.62 + 0.55 + 0.70) / 4, 4))  # 4 nearest-|d|-0.5
        self.assertAlmostEqual(s["skew_25d"], round(0.70 - 0.55, 4))   # put IV - call IV > 0
        self.assertGreater(s["skew_25d"], 0)              # put skew = downside hedging bid

    def test_regime_combines_btc_eth(self):
        with mock.patch.object(opt, "_get_json", return_value=_FAKE_MARK):
            r = opt.regime()
        self.assertTrue(r["available"])
        self.assertIn(r["label"], ("risk-off", "risk-on", "neutral"))
        self.assertIsNotNone(r["btc"]["atm_iv"])
        self.assertIsNotNone(r["eth"]["atm_iv"])
        self.assertGreaterEqual(r["risk_off"], -1.0)
        self.assertLessEqual(r["risk_off"], 1.0)

    def test_malformed_and_disabled_are_honest(self):
        with mock.patch.object(opt, "_get_json", return_value=[{"symbol": "junk", "markIV": "x"}]):
            self.assertEqual(opt.iv_summary("BTC")["n_contracts"], 0)
        import os
        os.environ["BINANCE_OPTIONS"] = "0"
        try:
            self.assertFalse(opt.regime().get("available"))
        finally:
            os.environ.pop("BINANCE_OPTIONS", None)


if __name__ == "__main__":
    unittest.main()
