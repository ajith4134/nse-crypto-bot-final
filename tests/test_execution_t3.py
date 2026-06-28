"""Trading Phase T3 (Trade Execution Engine) acceptance tests — fully offline.

Exercises the pure, network-independent execution logic so CI passes without any
broker/exchange access: order-lifecycle state machine, MAE/MFE excursion tracking,
trailing-stop strategies (exponential / ATR / Chandelier / profit-lock), partial
profit-booking ladders, the daily circuit breaker, SEBI margin estimates, bracket
/cover order builders, the kill switch, and an end-to-end ExecutionEngine trip.

Every test is deterministic; the DailyCircuitBreaker is always built with
persist=False so nothing touches disk.
"""
from __future__ import annotations

import unittest

from trading.execution.bracket import bracket_order, cover_order
from trading.execution.circuit_breaker import CircuitBreakerTripped, DailyCircuitBreaker
from trading.execution.engine import ExecutionEngine, TradeManager
from trading.execution.kill_switch import KillSwitch
from trading.execution.mae_mfe import MAEMFE
from trading.execution.margin import (
    check_fo_order,
    check_margin,
    nse_fo_margin,
    nse_intraday_margin,
)
from trading.execution.order_state import (
    InvalidTransition,
    Order,
    OrderStatus,
)
from trading.execution.profit_booking import ProfitLadder, Rung
from trading.execution.trailing import (
    ATRTrailingStop,
    ChandelierExit,
    ExponentialTrailingStop,
    ProfitLockTrailing,
)


class TestOrderState(unittest.TestCase):
    def test_partial_then_full_weighted_avg(self):
        o = Order(id="o1", symbol="X", exchange="NSE", side="buy", quantity=10)
        self.assertEqual(o.status, OrderStatus.PENDING)
        o.fill(4, 100.0)
        self.assertEqual(o.status, OrderStatus.PARTIAL)
        self.assertTrue(o.status.is_open)
        self.assertAlmostEqual(o.remaining, 6.0, places=9)
        o.fill(6, 110.0)
        self.assertEqual(o.status, OrderStatus.FILLED)
        self.assertTrue(o.status.is_terminal)
        # size-weighted average: (4*100 + 6*110)/10 = 106
        self.assertAlmostEqual(o.avg_price, 106.0, places=9)
        self.assertAlmostEqual(o.remaining, 0.0, places=9)

    def test_overfill_raises(self):
        o = Order(id="o2", symbol="X", exchange="NSE", side="sell", quantity=5)
        with self.assertRaises(InvalidTransition):
            o.fill(6, 50.0)

    def test_fill_after_cancel_raises(self):
        o = Order(id="o3", symbol="X", exchange="NSE", side="buy", quantity=5)
        o.cancel()
        self.assertEqual(o.status, OrderStatus.CANCELLED)
        self.assertTrue(o.status.is_terminal)
        with self.assertRaises(InvalidTransition):
            o.fill(1, 50.0)

    def test_reject_only_from_pending(self):
        o = Order(id="o4", symbol="X", exchange="NSE", side="buy", quantity=5)
        o.fill(1, 10.0)
        with self.assertRaises(InvalidTransition):
            o.reject("too late")


class TestMAEMFE(unittest.TestCase):
    def test_long_signs_and_r_multiples(self):
        m = MAEMFE(side="long", entry_price=100.0, initial_stop=90.0, qty=2.0)
        m.update(95.0)    # adverse
        m.update(110.0)   # favourable, last price
        self.assertAlmostEqual(m.mae, 5.0, places=9)   # positive
        self.assertAlmostEqual(m.mfe, 10.0, places=9)
        # risk per unit = |100-90| = 10
        self.assertAlmostEqual(m.mfe_r, 1.0, places=9)
        self.assertAlmostEqual(m.mae_r, -0.5, places=9)
        self.assertAlmostEqual(m.current_pnl, (110.0 - 100.0) * 2.0, places=9)
        self.assertAlmostEqual(m.current_r, 1.0, places=9)

    def test_short_signs_and_r_multiples(self):
        m = MAEMFE(side="short", entry_price=100.0, initial_stop=110.0, qty=1.0)
        m.update(105.0)   # adverse for a short
        m.update(90.0)    # favourable, last price
        self.assertAlmostEqual(m.mae, 5.0, places=9)
        self.assertAlmostEqual(m.mfe, 10.0, places=9)
        self.assertAlmostEqual(m.mfe_r, 1.0, places=9)
        self.assertAlmostEqual(m.current_pnl, 10.0, places=9)   # (100-90)*1
        self.assertAlmostEqual(m.current_r, 1.0, places=9)

    def test_r_none_without_stop(self):
        m = MAEMFE(side="long", entry_price=100.0)
        m.update(105.0)
        self.assertIsNone(m.mfe_r)


class TestTrailing(unittest.TestCase):
    def test_exponential_ratchets_never_backward(self):
        ts = ExponentialTrailingStop("long", 100.0, base_frac=0.03, floor_frac=0.004, k=0.0)
        stops = []
        for px in (100.0, 110.0, 105.0, 108.0):   # includes a pullback
            stops.append(ts.update(px))
        # k=0 => plain 3% trail off the running peak
        self.assertAlmostEqual(stops[1], 110.0 * 0.97, places=6)
        # stop must be non-decreasing for a long (never gives ground back)
        for a, b in zip(stops, stops[1:]):
            self.assertGreaterEqual(b, a)
        # pullback to 105 did NOT lower the stop from its 110-peak level
        self.assertAlmostEqual(stops[2], stops[1], places=6)

    def test_atr_stop_below_price_and_volatility_scaled(self):
        ts = ATRTrailingStop("long", 100.0, period=3, mult=3.0)
        stop = None
        for (h, l, c) in [(101, 99, 100), (102, 100, 101), (103, 101, 102)]:
            stop = ts.update(h, l, c)
        self.assertIsNotNone(stop)
        self.assertLess(stop, 102.0)          # below the close for a long
        self.assertFalse(ts.exit_triggered(102.0))
        self.assertTrue(ts.exit_triggered(stop - 1.0))

    def test_chandelier_hangs_off_running_high(self):
        ts = ChandelierExit("long", 100.0, period=3, mult=2.0)
        last = None
        for (h, l, c) in [(102, 99, 101), (106, 101, 105), (110, 104, 109)]:
            last = ts.update(h, l, c)
        # stop = highest_high(110) - mult*ATR, so strictly below the running high
        self.assertLess(last, 110.0)
        self.assertGreater(last, 100.0)       # has trailed up from entry region

    def test_profit_lock_holds_then_locks_breakeven(self):
        ts = ProfitLockTrailing("long", entry_price=100.0, initial_stop=95.0,
                                lock_after_frac=0.02)
        self.assertAlmostEqual(ts.update(100.0), 95.0, places=6)   # at entry: risk
        self.assertAlmostEqual(ts.update(101.0), 95.0, places=6)   # +1% < 2%: still risking
        self.assertFalse(ts.locked)
        ts.update(102.0)                                           # +2%: arm the lock
        self.assertTrue(ts.locked)
        self.assertGreaterEqual(ts.stop, 100.0)                    # >= breakeven now


class TestProfitBooking(unittest.TestCase):
    def test_r_multiple_rungs_fire_once(self):
        ladder = ProfitLadder(
            side="long", entry_price=100.0, quantity=100.0,
            rungs=[Rung(target=1.0, fraction=0.5, as_r=True, label="1R"),
                   Rung(target=2.0, fraction=0.5, as_r=True, label="2R")],
            initial_stop=90.0,   # risk = 10 => 1R=110, 2R=120
        )
        self.assertEqual(ladder.update(105.0), [])     # below first target
        ev1 = ladder.update(110.0)
        self.assertEqual(len(ev1), 1)
        self.assertAlmostEqual(ev1[0].qty, 50.0, places=9)
        self.assertAlmostEqual(ladder.remaining_qty, 50.0, places=9)
        self.assertEqual(ladder.update(110.0), [])     # same rung does not re-fire
        ev2 = ladder.update(120.0)
        self.assertEqual(len(ev2), 1)
        self.assertAlmostEqual(ladder.remaining_qty, 0.0, places=9)
        self.assertTrue(ladder.done)

    def test_absolute_price_rung(self):
        ladder = ProfitLadder(side="long", entry_price=100.0, quantity=10.0,
                              rungs=[Rung(target=120.0, fraction=0.3)])
        self.assertEqual(ladder.update(119.0), [])
        ev = ladder.update(121.0)
        self.assertEqual(len(ev), 1)
        self.assertAlmostEqual(ev[0].qty, 3.0, places=9)
        self.assertAlmostEqual(ladder.remaining_qty, 7.0, places=9)


class TestCircuitBreaker(unittest.TestCase):
    def test_trips_on_loss_limit_and_blocks(self):
        cb = DailyCircuitBreaker(max_daily_loss=1000.0, persist=False)
        self.assertFalse(cb.record_trade(-500.0))   # not yet
        self.assertFalse(cb.tripped)
        self.assertTrue(cb.record_trade(-600.0))     # -1100 <= -1000 => newly tripped
        self.assertTrue(cb.tripped)
        self.assertFalse(cb.allow_new_order())
        with self.assertRaises(CircuitBreakerTripped):
            cb.assert_allowed()
        cb.reset()
        self.assertTrue(cb.allow_new_order())

    def test_trips_on_max_trades(self):
        cb = DailyCircuitBreaker(max_daily_loss=10_000.0, max_trades=2, persist=False)
        self.assertFalse(cb.record_trade(0.0))
        self.assertTrue(cb.record_trade(0.0))        # 2nd trade hits the cap
        self.assertTrue(cb.tripped)

    def test_open_pnl_trips(self):
        cb = DailyCircuitBreaker(max_daily_loss=1000.0, persist=False)
        self.assertTrue(cb.mark_open_pnl(-1500.0))
        self.assertTrue(cb.tripped)


class TestMargin(unittest.TestCase):
    def test_fo_margin_math(self):
        bd = nse_fo_margin(100_000.0, span_rate=0.12, exposure_rate=0.03)
        self.assertAlmostEqual(bd["span"], 12_000.0, places=6)
        self.assertAlmostEqual(bd["exposure"], 3_000.0, places=6)
        self.assertAlmostEqual(bd["total"], 15_000.0, places=6)

    def test_intraday_leverage(self):
        bd = nse_intraday_margin(100_000.0, leverage=5.0)
        self.assertAlmostEqual(bd["total"], 20_000.0, places=6)

    def test_check_margin_gating(self):
        ok = check_margin(15_000.0, 20_000.0)
        self.assertTrue(ok.ok)
        self.assertAlmostEqual(ok.shortfall, 0.0, places=6)
        bad = check_margin(15_000.0, 10_000.0)
        self.assertFalse(bad.ok)
        self.assertAlmostEqual(bad.shortfall, 5_000.0, places=6)

    def test_check_fo_order_convenience(self):
        mc = check_fo_order(quantity=1, price=100.0, lot_size=50, available=1_000.0)
        # notional = 1*50*100 = 5000 ; total margin = 5000*0.15 = 750 <= 1000
        self.assertTrue(mc.ok)
        self.assertAlmostEqual(mc.required, 750.0, places=6)


class TestBracketCover(unittest.TestCase):
    def test_bracket_buy_prices_and_legs(self):
        bo = bracket_order(symbol="RELIANCE", action="BUY", quantity=10,
                           entry_price=100.0, target_points=20.0, stop_points=10.0)
        self.assertEqual(bo["kind"], "bracket")
        self.assertEqual(bo["direction"], "LONG")
        self.assertAlmostEqual(bo["target_price"], 120.0, places=6)
        self.assertAlmostEqual(bo["stop_price"], 90.0, places=6)
        self.assertAlmostEqual(bo["risk_reward"], 2.0, places=6)
        self.assertEqual(len(bo["legs"]), 3)
        legs = {leg["leg"]: leg for leg in bo["legs"]}
        self.assertEqual(legs["entry"]["action"], "BUY")
        self.assertEqual(legs["target"]["action"], "SELL")   # opposite for exit
        self.assertEqual(legs["stoploss"]["action"], "SELL")

    def test_cover_sell_two_legs(self):
        co = cover_order(symbol="RELIANCE", action="SELL", quantity=5,
                        entry_price=100.0, stop_points=8.0)
        self.assertEqual(co["kind"], "cover")
        self.assertEqual(co["direction"], "SHORT")
        self.assertAlmostEqual(co["stop_price"], 108.0, places=6)   # short stop above entry
        self.assertEqual(len(co["legs"]), 2)
        self.assertEqual(co["legs"][1]["action"], "BUY")            # exit covers the short


class TestKillSwitch(unittest.TestCase):
    def test_cancel_before_flatten_and_idempotent(self):
        order = []
        ks = KillSwitch(cancel_all=lambda: order.append("cancel") or "C",
                        flatten_all=lambda: order.append("flatten") or "F")
        rep = ks.engage("test")
        self.assertEqual(order, ["cancel", "flatten"])   # cancel strictly first
        self.assertTrue(ks.engaged)
        self.assertTrue(rep["ok"])
        rep2 = ks.engage("again")
        self.assertTrue(rep2["already_engaged"])
        self.assertEqual(order, ["cancel", "flatten"])   # no second fire

    def test_error_captured_and_latches(self):
        def boom():
            raise RuntimeError("broker down")
        ks = KillSwitch(cancel_all=lambda: "ok", flatten_all=boom)
        rep = ks.engage("test")
        self.assertTrue(ks.engaged)              # latches despite the failure
        self.assertTrue(rep["errors"])
        self.assertFalse(rep["ok"])


class TestExecutionEngine(unittest.TestCase):
    def test_losing_position_trips_breaker_and_kills(self):
        eng = ExecutionEngine(max_daily_loss=1000.0)
        # A trailing stop placed far away so the position stays OPEN and its open
        # P&L can drive the breaker (rather than the stop closing it first).
        trail = ExponentialTrailingStop("long", 100.0, base_frac=0.9, floor_frac=0.1, k=0.0)
        tm = TradeManager(symbol="X", side="long", quantity=100.0,
                          entry_price=100.0, trailing=trail, initial_stop=95.0)
        eng.open_trade("X", tm)
        # Price gaps to 89 => open P&L = (89-100)*100 = -1100 <= -1000 limit.
        result = eng.on_bar("X", high=89.0, low=89.0, close=89.0)
        self.assertTrue(result.get("circuit_breaker_tripped"))
        self.assertTrue(eng.breaker.tripped)
        self.assertTrue(eng.kill.engaged)
        status = eng.status()
        self.assertTrue(status["circuit_breaker"]["tripped"])
        self.assertTrue(status["kill_switch"]["engaged"])

    def test_register_blocked_after_trip(self):
        cb = DailyCircuitBreaker(max_daily_loss=1000.0, persist=False)
        cb.record_trade(-2000.0)
        eng = ExecutionEngine(circuit_breaker=cb)
        with self.assertRaises(CircuitBreakerTripped):
            eng.register_order(Order(id="z", symbol="X", exchange="NSE",
                                     side="buy", quantity=1))


if __name__ == "__main__":
    unittest.main()
