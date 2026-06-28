"""Trading Phase O1–O4 (Always-Online Supervisor) acceptance tests — fully offline.

Pins behaviour of the new ``trading/online/`` package with NO network, disk, broker or
exchange access and full determinism:

  O1  session.MarketSession      — NSE calendar LIVE↔REPLAY + crypto 24/7
  O1  state.{MarketState,TradingStateGate,MarketRegistry} — per-market toggles + gate
  O2  wallet.{PaperWallet,PaperWalletBook} — editable paper-money ledger
  O3  replay.{synthetic_ticks,CandleReplay,ReplaySession} — causal off-hours feed
  O4  supervisor.OnlineSupervisor — LIVE/REPLAY price → decide → gate → PAPER fill

All RNGs are seeded, every I/O source is injected, and every ``when`` is an IST-aware
datetime so the suite is deterministic. Registries/wallets use ``persist=False`` except
the single MarketRegistry persistence round-trip, which backs up and restores the shared
state file so the repo is left untouched.
"""
from __future__ import annotations

import warnings

warnings.filterwarnings("ignore")

import json
import unittest
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from trading import state as _state
from trading.online.replay import CandleReplay, ReplaySession, synthetic_ticks
from trading.online.session import MarketSession
from trading.online.state import (
    MarketRegistry,
    MarketState,
    TradingState,
    TradingStateGate,
)
from trading.online.supervisor import OnlineSupervisor
from trading.online.wallet import PaperWallet, PaperWalletBook

IST = timezone(timedelta(hours=5, minutes=30))

# Reference IST instants (2026-06-28 is a Sunday; 06-29 Mon, 06-30 Tue — verified).
TUE_INSESSION = datetime(2026, 6, 30, 11, 0, tzinfo=IST)   # weekday, 11:00 → LIVE
TUE_OFFHOURS = datetime(2026, 6, 30, 20, 0, tzinfo=IST)    # weekday, 20:00 → REPLAY
SUNDAY = datetime(2026, 6, 28, 11, 0, tzinfo=IST)          # weekend → REPLAY


def _ohlcv(seed: int = 0, n: int = 6) -> pd.DataFrame:
    """A small deterministic OHLCV frame with a DatetimeIndex."""
    rng = np.random.default_rng(seed)
    base = 100.0 + np.cumsum(rng.standard_normal(n))
    rows = []
    for c in base:
        o = float(c) - 0.5
        rows.append({"open": o, "high": float(c) + 1.0, "low": o - 1.0,
                     "close": float(c), "volume": 1000.0})
    idx = pd.date_range("2026-06-30 09:15", periods=n, freq="5min", tz=IST)
    return pd.DataFrame(rows, index=idx)


# ── O1: session ──────────────────────────────────────────────────────────────────
class TestMarketSession(unittest.TestCase):
    def test_nse_live_during_weekday_session(self):
        s = MarketSession("NSE")
        self.assertEqual(s.mode(TUE_INSESSION), "LIVE")
        self.assertTrue(s.is_open(TUE_INSESSION))

    def test_nse_replay_offhours_weekday(self):
        s = MarketSession("NSE")
        self.assertEqual(s.mode(TUE_OFFHOURS), "REPLAY")
        self.assertFalse(s.is_open(TUE_OFFHOURS))

    def test_nse_replay_on_sunday(self):
        s = MarketSession("NSE")
        self.assertEqual(s.mode(SUNDAY), "REPLAY")
        self.assertFalse(s.is_open(SUNDAY))

    def test_crypto_always_live_and_open(self):
        s = MarketSession("CRYPTO")
        self.assertTrue(s.is_crypto)
        self.assertEqual(s.mode(SUNDAY), "LIVE")
        self.assertEqual(s.mode(TUE_OFFHOURS), "LIVE")
        self.assertTrue(s.is_open(SUNDAY))

    def test_status_jsonable_documented_keys(self):
        st = MarketSession("NSE").status(TUE_INSESSION)
        self.assertEqual(set(st), {"market", "is_crypto", "is_open", "mode", "calendar"})
        self.assertEqual(st["market"], "NSE")
        self.assertEqual(st["mode"], "LIVE")
        json.dumps(st)


# ── O1: state ──────────────────────────────────────────────────────────────────
class TestTradingState(unittest.TestCase):
    def test_disabled_blocks_then_enable_allows_paper(self):
        ms = MarketState("NSE")  # disabled by default
        self.assertFalse(TradingStateGate.allow_order(ms)["ok"])
        ms.enable()
        gate = TradingStateGate.allow_order(ms)  # PAPER (is_real False)
        self.assertTrue(gate["ok"])
        self.assertFalse(gate["would_be_real"])

    def test_set_mode_real_requires_allow_live_and_confirm(self):
        ms = MarketState("CRYPTO").enable()
        # blocked without allow_live
        self.assertFalse(ms.set_mode("REAL", confirm=True)["ok"])
        ms.allow_live = True
        # blocked without confirm
        self.assertFalse(ms.set_mode("REAL")["ok"])
        # allowed with allow_live + confirm
        r = ms.set_mode("REAL", confirm=True)
        self.assertTrue(r["ok"])
        self.assertEqual(ms.mode, "REAL")
        self.assertTrue(ms.is_real)

    def test_gate_blocks_real_when_allow_live_false(self):
        ms = MarketState("CRYPTO").enable()  # allow_live False
        gate = TradingStateGate.allow_order(ms, is_real=True)
        self.assertFalse(gate["ok"])
        self.assertIn("allow_live", gate["reason"])

    def test_reducing_blocks_new_allows_reduce(self):
        ms = MarketState("NSE").enable().set_state(TradingState.REDUCING)
        self.assertFalse(TradingStateGate.allow_order(ms, reduces_position=False)["ok"])
        self.assertTrue(TradingStateGate.allow_order(ms, reduces_position=True)["ok"])

    def test_halted_blocks_everything_including_reduces(self):
        ms = MarketState("NSE").enable().set_state(TradingState.HALTED)
        self.assertFalse(TradingStateGate.allow_order(ms, reduces_position=False)["ok"])
        self.assertFalse(TradingStateGate.allow_order(ms, reduces_position=True)["ok"])

    def test_halt_all_halts_every_market(self):
        reg = MarketRegistry(persist=False)
        reg.get("NSE").enable()
        reg.get("CRYPTO").enable()
        reg.halt_all()
        for s in reg.markets.values():
            self.assertEqual(s.trading_state, TradingState.HALTED)
            self.assertFalse(reg.allow_order(s.market)["ok"])

    def test_registry_status_jsonable(self):
        reg = MarketRegistry(persist=False)
        st = reg.status()
        self.assertIn("markets", st)
        self.assertIn("NSE", st["markets"])
        json.dumps(st)

    def test_persistence_round_trip(self):
        from trading.online.state import _STATE_FILE
        backup = _state.load_json(_STATE_FILE, None)  # preserve real state
        try:
            reg = MarketRegistry(persist=True)
            reg.get("CRYPTO").enable()
            reg.get("CRYPTO").allow_live = True
            reg.get("CRYPTO").set_mode("REAL", confirm=True)
            reg.save()
            # a fresh registry must reload the persisted enabled/mode
            again = MarketRegistry(persist=True)
            self.assertTrue(again.get("CRYPTO").enabled)
            self.assertEqual(again.get("CRYPTO").mode, "REAL")
        finally:
            if backup is None:
                _state.save_json(_STATE_FILE, {})
            else:
                _state.save_json(_STATE_FILE, backup)


# ── O2: wallet ──────────────────────────────────────────────────────────────────
class TestPaperWallet(unittest.TestCase):
    def _crypto(self):
        return PaperWallet("CRYPTO", "USDT", 100_000.0, persist=False)

    def test_crypto_buy_then_partial_sell_realized(self):
        w = self._crypto()
        w.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        res = w.record_fill("BTCUSDT", "sell", 0.5, 60_000.0)
        # closed 0.5 of a long at +10k/unit → positive realised PnL
        self.assertGreater(res.get("realized_pnl", 0.0), 0.0)
        self.assertGreater(w.realized_pnl(), 0.0)
        # half the long still open
        self.assertEqual(len(w.positions()), 1)
        self.assertAlmostEqual(w.positions()[0]["size"], 0.5, places=9)

    def test_crypto_mark_then_unrealized_and_equity(self):
        w = self._crypto()
        w.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        eq0 = w.equity()
        out = w.mark({"BTCUSDT": 55_000.0})
        self.assertGreater(out["unrealized_pnl"], 0.0)
        self.assertAlmostEqual(out["unrealized_pnl"], 5_000.0, places=4)
        self.assertGreater(out["equity"], eq0)

    def test_top_up_adds_cash(self):
        w = self._crypto()
        cash0 = w.cash()
        w.top_up(25_000.0)
        self.assertAlmostEqual(w.cash(), cash0 + 25_000.0, places=4)
        self.assertAlmostEqual(w.starting_capital, 125_000.0, places=4)

    def test_set_starting_capital_resets_to_new_amount(self):
        w = self._crypto()
        w.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        w.set_starting_capital(7_777.0)
        self.assertAlmostEqual(w.starting_capital, 7_777.0, places=4)
        self.assertAlmostEqual(w.cash(), 7_777.0, places=4)
        self.assertEqual(w.positions(), [])

    def test_reset_restores_starting_capital_and_flat(self):
        w = self._crypto()
        w.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        w.reset()
        self.assertAlmostEqual(w.cash(), 100_000.0, places=4)
        self.assertEqual(w.positions(), [])
        self.assertAlmostEqual(w.realized_pnl(), 0.0, places=9)

    def test_summary_jsonable(self):
        w = self._crypto()
        w.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        s = w.summary()
        for k in ("market", "currency", "cash", "equity", "realized_pnl", "positions"):
            self.assertIn(k, s)
        json.dumps(s)

    def test_nse_cash_ledger(self):
        w = PaperWallet("NSE", "INR", 1_000_000.0, persist=False)
        w.record_fill("RELIANCE", "buy", 100.0, 100.0)  # spend 10,000 (fee=0)
        self.assertAlmostEqual(w.cash(), 990_000.0, places=4)
        self.assertEqual(w.positions()[0]["symbol"], "RELIANCE")
        self.assertAlmostEqual(w.positions()[0]["size"], 100.0, places=6)

    def test_walletbook_multi_portfolio_and_status(self):
        book = PaperWalletBook(persist=False)
        a = book.wallet("CRYPTO", "alpha")
        b = book.wallet("CRYPTO", "beta")
        n = book.wallet("NSE")
        self.assertIsNot(a, b)
        a.record_fill("BTCUSDT", "buy", 1.0, 50_000.0)
        st = book.status()
        self.assertEqual(len(st["wallets"]), 3)
        json.dumps(st)


# ── O3: replay ──────────────────────────────────────────────────────────────────
class TestReplay(unittest.TestCase):
    def test_synthetic_ticks_up_bar(self):
        bar = {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0}
        ticks = synthetic_ticks(bar, n=8, rng=np.random.default_rng(0))
        self.assertAlmostEqual(ticks[0], 100.0, places=9)
        self.assertAlmostEqual(ticks[-1], 104.0, places=9)
        self.assertTrue(all(99.0 - 1e-9 <= t <= 105.0 + 1e-9 for t in ticks))

    def test_synthetic_ticks_down_bar(self):
        bar = {"open": 104.0, "high": 105.0, "low": 99.0, "close": 100.0}
        ticks = synthetic_ticks(bar, n=8, rng=np.random.default_rng(1))
        self.assertAlmostEqual(ticks[0], 104.0, places=9)
        self.assertAlmostEqual(ticks[-1], 100.0, places=9)
        self.assertTrue(all(99.0 - 1e-9 <= t <= 105.0 + 1e-9 for t in ticks))

    def test_synthetic_ticks_deterministic(self):
        bar = {"open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0}
        a = synthetic_ticks(bar, n=8, rng=np.random.default_rng(42))
        b = synthetic_ticks(bar, n=8, rng=np.random.default_rng(42))
        self.assertEqual(a, b)

    def test_window_no_lookahead(self):
        df = _ohlcv()
        cr = CandleReplay(df)
        for i in range(len(df)):
            win = cr.window(i)
            self.assertEqual(len(win), i + 1)  # only data up to bar i
            self.assertAlmostEqual(float(win["close"].iloc[-1]),
                                   float(df["close"].iloc[i]), places=9)

    def test_replaysession_run_causal(self):
        df = _ohlcv()
        rs = ReplaySession("NSE", df)
        self.assertTrue(rs.should_replay(SUNDAY))
        seen = []

        def on_bar(window_df, bar):
            seen.append((len(window_df), bar["close"]))

        out = rs.run(on_bar, max_bars=3)
        self.assertEqual(out["bars_replayed"], 3)
        self.assertEqual([n for n, _ in seen], [1, 2, 3])  # growing causal windows

    def test_replay_status_jsonable(self):
        rs = ReplaySession("NSE", _ohlcv())
        st = rs.status(SUNDAY)
        self.assertEqual(st["market"], "NSE")
        self.assertEqual(st["mode"], "REPLAY")
        json.dumps(st)


# ── O4: supervisor ──────────────────────────────────────────────────────────────
class TestOnlineSupervisor(unittest.TestCase):
    def _sup(self):
        def crypto_price(symbol):
            return {"last": 50_000.0}

        def decide(market, symbol, data):
            return {"action": "LONG", "size": 0.1}

        return OnlineSupervisor(
            registry=MarketRegistry(persist=False),
            wallets=PaperWalletBook(persist=False),
            crypto_price_source=crypto_price,
            nse_ohlcv={"RELIANCE": _ohlcv()},
            decide_fn=decide,
        )

    def test_crypto_step_live_routes_paper_fill(self):
        sup = self._sup()
        sup.start_market("CRYPTO")
        res = sup.step(symbols={"CRYPTO": "BTCUSDT"}, when=SUNDAY)["results"][0]
        self.assertEqual(res["mode"], "LIVE")
        self.assertTrue(res["gate"]["ok"])
        self.assertEqual(res["routed"]["mode"], "PAPER")
        w = sup.wallets.wallet("CRYPTO")
        self.assertEqual(len(w.positions()), 1)
        self.assertAlmostEqual(w.positions()[0]["size"], 0.1, places=9)

    def test_nse_step_offhours_uses_replay_price(self):
        sup = self._sup()
        sup.start_market("NSE")
        res = sup.step(symbols={"NSE": "RELIANCE"}, when=SUNDAY, replay_step=0)["results"][0]
        self.assertEqual(res["mode"], "REPLAY")
        expected = round(float(_ohlcv()["close"].iloc[0]), 4)
        self.assertAlmostEqual(res["price"], expected, places=4)

    def test_stop_market_skips_next_step(self):
        sup = self._sup()
        sup.start_market("CRYPTO")
        sup.stop_market("CRYPTO")
        res = sup.step(symbols={"CRYPTO": "BTCUSDT"}, when=SUNDAY)["results"][0]
        self.assertEqual(res["skipped"], "stopped")

    def test_real_mode_without_adapter_routes_but_fails(self):
        sup = self._sup()
        sup.start_market("CRYPTO")
        sup.registry.get("CRYPTO").allow_live = True
        self.assertTrue(sup.set_mode("CRYPTO", "REAL", confirm=True)["ok"])
        res = sup.step(symbols={"CRYPTO": "BTCUSDT"}, when=SUNDAY)["results"][0]
        self.assertTrue(res["gate"]["ok"])
        self.assertEqual(res["routed"]["mode"], "REAL")
        self.assertFalse(res["routed"]["ok"])
        self.assertIn("no live adapter", res["routed"]["detail"])

    def test_status_jsonable(self):
        sup = self._sup()
        sup.start_market("CRYPTO")
        sup.step(symbols={"CRYPTO": "BTCUSDT"}, when=SUNDAY)
        st = sup.status()
        for k in ("heartbeats", "registry", "wallets", "sessions"):
            self.assertIn(k, st)
        json.dumps(st)


if __name__ == "__main__":
    unittest.main()
