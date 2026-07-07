"""Unit tests for BrainExecutor's options/prediction segment cycles (audit gap 4).

The futures/spot cycle is covered by the live path + test_multisegment; these tests pin the
dedicated options (ATM call/put on the underlying's direction) and prediction (SMA20 momentum)
cycles against a fake engine client — no network, no live state touched.
"""

import unittest

from trading.crypto.freqtrade.brain_executor import BrainExecutor


class FakeClient:
    def __init__(self, whitelist=None, open_pairs=None, candles=None):
        self._wl = whitelist or []
        self._open = open_pairs or []
        self._candles = candles or {}
        self.orders = []      # (symbol, side, enter_tag, segment)
        self.closed = []      # (symbol, segment)

    def whitelist(self, segment=None):
        return list(self._wl)

    def open_pairs(self, segment=None):
        return list(self._open)

    def place_order(self, symbol, action, side, allow_live=False, enter_tag=None, segment=None):
        self.orders.append((symbol, side, enter_tag, segment))
        return {"ok": True}

    def close_pair(self, pair, segment=None):
        self.closed.append((pair, segment))
        return {"ok": True}

    def pair_candles(self, pair, tf, limit=60, segment=None):
        return self._candles.get(pair, [])


class FakeDecider:
    """decide() returns a fixed action per underlying symbol."""

    def __init__(self, actions):
        self.actions = actions

    def decide(self, market, symbol, price, in_position=False):
        return {"action": self.actions.get(symbol), "size": 1.0, "_brain": {}}


BTC_CALL_NEAR = "BTC/USDC:USDC-260703-60000-C"
BTC_CALL_NEAR_HI = "BTC/USDC:USDC-260703-62000-C"
BTC_CALL_NEAR_LO = "BTC/USDC:USDC-260703-58000-C"
BTC_CALL_FAR = "BTC/USDC:USDC-260710-60000-C"
BTC_PUT_NEAR = "BTC/USDC:USDC-260703-60000-P"
ETH_CALL_NEAR = "ETH/USDC:USDC-260703-3000-C"


class TestOptionParse(unittest.TestCase):
    def test_parse_option(self):
        o = BrainExecutor._parse_option(BTC_PUT_NEAR)
        self.assertEqual(o["base"], "BTC")
        self.assertEqual(o["expiry"], "260703")
        self.assertEqual(o["strike"], 60000.0)
        self.assertEqual(o["kind"], "P")

    def test_parse_option_garbage(self):
        self.assertIsNone(BrainExecutor._parse_option("BTC/USDT:USDT"))
        self.assertIsNone(BrainExecutor._parse_option(""))


class TestOptionsCycle(unittest.TestCase):
    def _executor(self, whitelist, open_pairs, actions):
        cli = FakeClient(whitelist=whitelist, open_pairs=open_pairs)
        ex = BrainExecutor(decider=FakeDecider(actions), client=cli, segment="options")
        return ex, cli

    def test_long_buys_nearest_expiry_atm_call(self):
        ex, cli = self._executor(
            [BTC_CALL_NEAR, BTC_CALL_NEAR_HI, BTC_CALL_NEAR_LO, BTC_CALL_FAR, BTC_PUT_NEAR],
            [], {"BTC/USDT:USDT": "LONG"})
        out = ex.run_once()
        # nearest expiry (260703) + median of the 3 strikes = 60000 call
        self.assertEqual(out["entered"], [BTC_CALL_NEAR])
        self.assertEqual(cli.orders[0][0], BTC_CALL_NEAR)
        self.assertEqual(cli.orders[0][2], "opt-long-BTC")
        self.assertEqual(cli.orders[0][3], "options")

    def test_short_buys_put(self):
        ex, cli = self._executor([BTC_CALL_NEAR, BTC_PUT_NEAR], [], {"BTC/USDT:USDT": "SHORT"})
        out = ex.run_once()
        self.assertEqual(out["entered"], [BTC_PUT_NEAR])

    def test_flip_exits_wrong_direction_then_enters(self):
        ex, cli = self._executor([BTC_CALL_NEAR, BTC_PUT_NEAR], [BTC_PUT_NEAR],
                                 {"BTC/USDT:USDT": "LONG"})
        out = ex.run_once()
        self.assertEqual(cli.closed, [(BTC_PUT_NEAR, "options")])
        self.assertEqual(out["entered"], [BTC_CALL_NEAR])

    def test_no_view_closes_held(self):
        ex, cli = self._executor([BTC_CALL_NEAR], [BTC_CALL_NEAR], {"BTC/USDT:USDT": None})
        out = ex.run_once()
        self.assertEqual(cli.closed, [(BTC_CALL_NEAR, "options")])
        self.assertEqual(out["entered"], [])

    def test_already_positioned_skips(self):
        ex, cli = self._executor([BTC_CALL_NEAR, BTC_CALL_FAR], [BTC_CALL_NEAR],
                                 {"BTC/USDT:USDT": "LONG"})
        out = ex.run_once()
        self.assertEqual(cli.orders, [])
        self.assertEqual(out["entered"], [])

    def test_multiple_underlyings_independent(self):
        ex, cli = self._executor([BTC_CALL_NEAR, ETH_CALL_NEAR], [],
                                 {"BTC/USDT:USDT": "LONG", "ETH/USDT:USDT": None})
        out = ex.run_once()
        self.assertEqual(out["entered"], [BTC_CALL_NEAR])


def _candles(closes):
    return [[0, c, c, c, c, 0] for c in closes]


class TestPredictionCycle(unittest.TestCase):
    MKT = "WILL-X-WIN/USDC"

    def _executor(self, closes, open_pairs=None):
        cli = FakeClient(whitelist=[self.MKT], open_pairs=open_pairs or [],
                         candles={self.MKT: _candles(closes)})
        ex = BrainExecutor(decider=FakeDecider({}), client=cli, segment="prediction")
        return ex, cli

    def test_momentum_entry(self):
        # SMA20 of 0.50 with last = 0.60 → above SMA*1.02 and inside (0.03, 0.95)
        closes = [0.50] * 30 + [0.60]
        ex, cli = self._executor(closes)
        out = ex.run_once()
        self.assertEqual(out["entered"], [self.MKT])
        self.assertEqual(cli.orders[0][2], "pred-momentum")
        self.assertEqual(cli.orders[0][3], "prediction")

    def test_no_entry_near_certainty(self):
        # last 0.97 > SMA*1.02 but outside the (0.03, 0.95) band → skip
        closes = [0.90] * 30 + [0.97]
        ex, cli = self._executor(closes)
        out = ex.run_once()
        self.assertEqual(out["entered"], [])

    def test_exit_below_sma(self):
        closes = [0.60] * 30 + [0.40]
        ex, cli = self._executor(closes, open_pairs=[self.MKT])
        out = ex.run_once()
        self.assertEqual(out["exited"], [self.MKT])
        self.assertEqual(cli.closed, [(self.MKT, "prediction")])

    def test_too_few_candles_skips(self):
        ex, cli = self._executor([0.5] * 10)
        out = ex.run_once()
        self.assertEqual(out["entered"], [])
        self.assertEqual(out["skipped"], 1)


class TestPerSegmentMaxOpenTrades(unittest.TestCase):
    def test_env_override_lands_in_segment_block(self):
        import os
        from unittest import mock
        from trading.crypto.freqtrade.config_template import _segments_block, crypto_config
        # Isolate from the operator's real .env (which may set any of these keys):
        # spot/options overridden, prediction explicitly ABSENT.
        with mock.patch.dict(os.environ):   # snapshots + restores the whole env
            for k in [k for k in os.environ if k.startswith("CRYPTO_MAX_OPEN_TRADES")]:
                del os.environ[k]
            os.environ["CRYPTO_MAX_OPEN_TRADES_SPOT"] = "7"
            os.environ["CRYPTO_MAX_OPEN_TRADES_OPTIONS"] = "3"
            block = _segments_block(crypto_config)
            self.assertEqual(block["spot"]["overrides"]["max_open_trades"], 7)
            self.assertEqual(block["options"]["overrides"]["max_open_trades"], 3)
            self.assertNotIn("max_open_trades", block["prediction"]["overrides"])


if __name__ == "__main__":
    unittest.main()
