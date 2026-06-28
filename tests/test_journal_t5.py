"""Trading Phase T5 (Trade Journal & Brain-Confidence) acceptance tests — fully offline.

Pins KNOWN-VALUE assertions against the pure-Python journal package so CI passes with
no broker/exchange/disk access: the 85+ column ClosedTrade schema + serialisation,
Indian/crypto transaction-cost math, per-trade quality metrics (R-multiple / MAE-MFE /
timing), the JournalAnalytics roll-up, behavioural screening (revenge / overtrading),
the per-symbol Bayesian ConfidenceBook, the HTML/PDF tearsheet, and an end-to-end
TradeJournal trip.

Every TradeJournal is built with persist=False and every file write targets the
session scratchpad so nothing in the repo is touched. Deterministic throughout.
"""
from __future__ import annotations

import json
import os
import tempfile
import unittest

from trading.journal.analytics import JournalAnalytics, analyze_trades
from trading.journal.behavior import (
    flag_overtrading,
    flag_revenge_trade,
    screen_behavior,
)
from trading.journal.charges import crypto_charges, net_pnl, nse_charges
from trading.journal.confidence import ConfidenceBook, SymbolConfidence
from trading.journal.journal import TradeJournal
from trading.journal.quality import r_multiple, trade_quality
from trading.journal.schema import COLUMNS, ClosedTrade, csv_header
from trading.journal.tearsheet import (
    equity_curve,
    monthly_pnl,
    render_tearsheet,
    render_tearsheet_pdf,
)

_SCRATCH = "/tmp/claude-1000/-home-karan18190164/bd731724-5220-4673-838e-92680bac705f/scratchpad"


class TestSchema(unittest.TestCase):
    def test_columns_count_and_row_length(self):
        self.assertGreaterEqual(len(COLUMNS), 85)
        self.assertEqual(len(ClosedTrade().to_row()), len(COLUMNS))
        # csv_header is the same single source of truth, comma-joined
        self.assertEqual(csv_header().split(","), COLUMNS)

    def test_from_dict_round_trips(self):
        t = ClosedTrade(trade_id="T1", symbol="RELIANCE", direction="LONG",
                        entry_price=100.0, exit_price=110.0, quantity=10.0)
        again = ClosedTrade.from_dict(t.to_dict())
        self.assertEqual(again.to_dict(), t.to_dict())

    def test_from_dict_ignores_unknown_keys(self):
        again = ClosedTrade.from_dict({"symbol": "X", "not_a_field": 123})
        self.assertEqual(again.symbol, "X")

    def test_json_list_fields_survive_to_row(self):
        t = ClosedTrade(
            partial_exits=[{"price": 101.0, "qty": 5}],
            tags=["breakout", "A+"],
            node_contributions=[{"node": "n1", "w": 0.5}],
        )
        row = dict(zip(COLUMNS, t.to_row()))
        # list/dict cells are JSON-encoded strings in a CSV row
        self.assertEqual(json.loads(row["partial_exits"]), [{"price": 101.0, "qty": 5}])
        self.assertEqual(json.loads(row["tags"]), ["breakout", "A+"])
        self.assertEqual(json.loads(row["node_contributions"]), [{"node": "n1", "w": 0.5}])


class TestCharges(unittest.TestCase):
    def test_eq_intraday_known_values(self):
        ch = nse_charges("eq_intraday", buy_value=100000.0, sell_value=110000.0)
        # STT is sell-side only on intraday equity
        self.assertAlmostEqual(ch["stt"], 27.5, places=4)
        # stamp duty is buy-side only
        self.assertAlmostEqual(ch["stamp_duty"], 3.0, places=4)
        self.assertAlmostEqual(ch["exchange_txn_charges"], 6.237, places=4)
        self.assertAlmostEqual(ch["sebi_charges"], 0.21, places=4)
        self.assertAlmostEqual(ch["brokerage"], 40.0, places=4)
        # GST = 18% of (brokerage + exchange txn + SEBI)
        self.assertAlmostEqual(
            ch["gst"],
            0.18 * (ch["brokerage"] + ch["exchange_txn_charges"] + ch["sebi_charges"]),
            places=3,
        )
        self.assertAlmostEqual(ch["total_charges"], 85.3075, places=4)

    def test_fut_vs_opt_differ(self):
        fut = nse_charges("fut", buy_value=100000.0, sell_value=100000.0)
        opt = nse_charges("opt", buy_value=100000.0, sell_value=100000.0)
        self.assertNotAlmostEqual(fut["total_charges"], opt["total_charges"], places=2)
        # options STT (0.1% sell) >> futures STT (0.02% sell) on equal turnover
        self.assertGreater(opt["stt"], fut["stt"])

    def test_unknown_segment_raises(self):
        with self.assertRaises(ValueError):
            nse_charges("forex", buy_value=1.0, sell_value=1.0)

    def test_crypto_fee_and_funding(self):
        ch = crypto_charges(entry_notional=10000.0, exit_notional=12000.0,
                            funding_pnl=-50.0, taker_rate=0.0005)
        # fee = (entry + exit) * taker_rate
        self.assertAlmostEqual(ch["maker_taker_fee"], 11.0, places=8)
        self.assertAlmostEqual(ch["funding_pnl"], -50.0, places=8)
        # total cost = fee − funding_pnl ; funding paid (negative) increases cost
        self.assertAlmostEqual(ch["total_charges"], 61.0, places=8)

    def test_net_pnl_subtracts(self):
        self.assertAlmostEqual(net_pnl(1000.0, 85.3075), 914.6925, places=4)


class TestQuality(unittest.TestCase):
    def test_long_win_r_multiple_exact(self):
        # risk = |100-95| * 10 = 50 ; net = 100 => r = 2.0
        self.assertAlmostEqual(r_multiple(100.0, 100.0, 95.0, 10.0), 2.0, places=9)
        t = ClosedTrade(direction="LONG", entry_price=100.0, exit_price=110.0,
                        quantity=10.0, initial_sl_price=95.0, net_pnl=100.0)
        q = trade_quality(t)
        self.assertAlmostEqual(q["r_multiple"], 2.0, places=9)

    def test_r_multiple_none_on_zero_risk(self):
        self.assertIsNone(r_multiple(100.0, 100.0, 100.0, 10.0))

    def test_timing_fields(self):
        t = ClosedTrade(direction="LONG", entry_price=100.0, exit_price=110.0,
                        quantity=10.0,
                        entry_datetime="2026-06-01T09:30:00",
                        exit_datetime="2026-06-01T11:45:30")
        q = trade_quality(t)
        self.assertEqual(q["holding_duration"], "02:15:30")
        self.assertEqual(q["entry_hour"], 9)
        self.assertEqual(q["day_of_week"], "Monday")

    def test_mae_mfe_pct_present(self):
        t = ClosedTrade(direction="LONG", entry_price=100.0, exit_price=110.0,
                        quantity=10.0, mae=50.0, mfe=150.0)
        q = trade_quality(t)
        # mae_move = 50/10 = 5 -> 5% of entry ; mfe_move = 150/10 = 15 -> 15%
        self.assertAlmostEqual(q["mae_pct"], 5.0, places=6)
        self.assertAlmostEqual(q["mfe_pct"], 15.0, places=6)


class TestAnalytics(unittest.TestCase):
    def _fixture(self):
        # ordered W W W L L => max_win_streak 3, max_loss_streak 2
        pnls = [100.0, 200.0, 300.0, -50.0, -100.0]
        return [ClosedTrade(trade_id=f"t{i}", strategy_name="Breakout", net_pnl=p)
                for i, p in enumerate(pnls)]

    def test_headline_stats_exact(self):
        a = analyze_trades(self._fixture())
        self.assertEqual(a.total_trades, 5)
        self.assertEqual(a.wins, 3)
        self.assertEqual(a.losses, 2)
        self.assertAlmostEqual(a.win_rate, 60.0, places=6)
        self.assertAlmostEqual(a.gross_profit, 600.0, places=6)
        self.assertAlmostEqual(a.gross_loss, 150.0, places=6)
        self.assertAlmostEqual(a.net_pnl, 450.0, places=6)
        self.assertAlmostEqual(a.profit_factor, 4.0, places=6)
        self.assertAlmostEqual(a.avg_win, 200.0, places=6)
        self.assertAlmostEqual(a.avg_loss, 75.0, places=6)
        # expectancy = 0.6*200 - 0.4*75 = 90
        self.assertAlmostEqual(a.expectancy, 90.0, places=6)
        self.assertEqual(a.max_win_streak, 3)
        self.assertEqual(a.max_loss_streak, 2)

    def test_by_dimension_buckets(self):
        a = analyze_trades(self._fixture())
        bucket = a.by_dimension["strategy_name"]["Breakout"]
        self.assertEqual(bucket["trades"], 5)
        self.assertEqual(bucket["wins"], 3)
        self.assertAlmostEqual(bucket["win_rate"], 60.0, places=6)
        self.assertAlmostEqual(bucket["net_pnl"], 450.0, places=6)

    def test_empty_list_is_safe(self):
        a = analyze_trades([])
        self.assertIsInstance(a, JournalAnalytics)
        self.assertEqual(a.total_trades, 0)
        self.assertEqual(a.win_rate, 0.0)
        self.assertIsNone(a.profit_factor)
        # JSON-able even when empty
        json.dumps(a.as_dict())


class TestBehavior(unittest.TestCase):
    def test_revenge_within_window(self):
        loser = ClosedTrade(trade_id="L", net_pnl=-100.0,
                            exit_datetime="2026-06-01T10:00:00")
        # entered 3 min after the loss -> revenge
        soon = ClosedTrade(trade_id="R", entry_datetime="2026-06-01T10:03:00")
        self.assertTrue(flag_revenge_trade(soon, [loser], window_minutes=5))
        # entered 6 min after -> outside window
        later = ClosedTrade(trade_id="N", entry_datetime="2026-06-01T10:06:00")
        self.assertFalse(flag_revenge_trade(later, [loser], window_minutes=5))

    def test_revenge_ignores_winning_prior(self):
        winner = ClosedTrade(trade_id="W", net_pnl=100.0,
                             exit_datetime="2026-06-01T10:00:00")
        soon = ClosedTrade(trade_id="R", entry_datetime="2026-06-01T10:03:00")
        self.assertFalse(flag_revenge_trade(soon, [winner], window_minutes=5))

    def test_overtrading_threshold(self):
        self.assertFalse(flag_overtrading(10, 10))
        self.assertTrue(flag_overtrading(11, 10))

    def test_screen_behavior_counts_and_mutates(self):
        # daily_limit=2 ; 3 trades same day -> 3rd is overtrading
        trades = [
            ClosedTrade(trade_id="a", net_pnl=-10.0,
                        entry_datetime="2026-06-01T09:00:00",
                        exit_datetime="2026-06-01T09:05:00"),
            # entered 2 min after a's exit -> revenge, and 2nd of day (within limit)
            ClosedTrade(trade_id="b", net_pnl=5.0,
                        entry_datetime="2026-06-01T09:07:00",
                        exit_datetime="2026-06-01T09:10:00"),
            # 3rd of day -> overtrading
            ClosedTrade(trade_id="c", net_pnl=5.0,
                        entry_datetime="2026-06-01T12:00:00",
                        exit_datetime="2026-06-01T12:05:00"),
        ]
        summary = screen_behavior(trades, daily_limit=2, revenge_window_min=5)
        self.assertEqual(summary["revenge_count"], 1)
        self.assertEqual(summary["overtrading_count"], 1)
        # flags mutated in place
        self.assertTrue(trades[1].revenge_trade_flag)
        self.assertFalse(trades[0].revenge_trade_flag)
        self.assertTrue(trades[2].overtrading_flag)


class TestConfidence(unittest.TestCase):
    def test_win_rate_moves_and_neutral_prior(self):
        sc = SymbolConfidence(symbol="X")
        self.assertEqual(sc.n, 0)
        self.assertAlmostEqual(sc.win_rate, 0.5, places=9)   # Beta(1,1) mean
        self.assertAlmostEqual(sc.confidence, 0.5, places=9)  # n=0 -> no opinion
        sc.update(True)
        self.assertGreater(sc.win_rate, 0.5)
        sc.update(False)
        sc.update(False)
        self.assertLess(sc.win_rate, 0.5)

    def test_brier_accumulates(self):
        sc = SymbolConfidence(symbol="X")
        self.assertIsNone(sc.brier)
        sc.update(True, predicted_prob=1.0)   # perfect -> 0
        sc.update(False, predicted_prob=1.0)  # wrong & sure -> 1
        self.assertEqual(sc.brier_count, 2)
        self.assertAlmostEqual(sc.brier, 0.5, places=9)  # (0 + 1)/2

    def test_book_coerces_percentage_and_brain_correct(self):
        book = ConfidenceBook()
        # UP prediction + LONG winning trade => brain_correct True ;
        # brain_confidence_entry given as a 0–100 percentage, must coerce to 0–1.
        t = ClosedTrade(symbol="RELIANCE", direction="LONG", net_pnl=500.0,
                        brain_prediction="UP", brain_confidence_entry=80.0)
        book.update_from_trade(t)
        self.assertTrue(t.brain_correct)
        sc = book.get("RELIANCE")
        self.assertEqual(sc.n, 1)
        self.assertEqual(sc.wins, 1)
        # 80 (percent) coerced to 0.8 -> Brier = (0.8 - 1)^2 = 0.04
        self.assertAlmostEqual(sc.brier, 0.04, places=9)
        self.assertAlmostEqual(book.score("RELIANCE"), sc.confidence, places=9)
        json.dumps(book.as_dict())

    def test_book_brain_correct_false_for_up_on_loser(self):
        book = ConfidenceBook()
        t = ClosedTrade(symbol="INFY", direction="LONG", net_pnl=-300.0,
                        brain_prediction="UP", brain_confidence_entry=0.7)
        book.update_from_trade(t)
        self.assertFalse(t.brain_correct)


class TestTearsheet(unittest.TestCase):
    def _trades(self):
        return [
            ClosedTrade(net_pnl=100.0, entry_datetime="2026-01-15T10:00:00",
                        exit_datetime="2026-01-15T11:00:00"),
            ClosedTrade(net_pnl=-40.0, entry_datetime="2026-02-10T10:00:00",
                        exit_datetime="2026-02-10T11:00:00"),
        ]

    def test_render_html_nonempty(self):
        html = render_tearsheet(self._trades(), title="T5")
        self.assertIn("<html", html)
        self.assertIn("T5", html)

    def test_render_empty_does_not_raise(self):
        html = render_tearsheet([])
        self.assertIn("<html", html)

    def test_equity_curve_final_equity(self):
        curve = equity_curve(self._trades(), starting_equity=100000.0)
        # one starting point + one per trade
        self.assertEqual(len(curve), 3)
        self.assertAlmostEqual(curve[-1]["equity"], 100000.0 + 60.0, places=6)

    def test_monthly_pnl_keys(self):
        mp = monthly_pnl(self._trades())
        self.assertEqual(set(mp), {"2026-01", "2026-02"})
        self.assertAlmostEqual(mp["2026-01"], 100.0, places=6)
        self.assertAlmostEqual(mp["2026-02"], -40.0, places=6)

    def test_render_pdf(self):
        path = os.path.join(_SCRATCH, "tearsheet_t5.pdf")
        out = render_tearsheet_pdf(self._trades(), path, title="T5 PDF")
        self.assertEqual(out, path)
        self.assertTrue(os.path.exists(path) and os.path.getsize(path) > 0)


class TestJournalEndToEnd(unittest.TestCase):
    def _record_three(self):
        j = TradeJournal(persist=False)
        nse_win = ClosedTrade(
            trade_id="nse_win", symbol="RELIANCE", exchange="NSE",
            instrument_type="EQ", product_type="MIS", direction="LONG",
            entry_price=100.0, exit_price=110.0, quantity=100.0,
            entry_datetime="2026-06-01T09:30:00", exit_datetime="2026-06-01T10:30:00")
        nse_loss = ClosedTrade(
            trade_id="nse_loss", symbol="TCS", exchange="NSE",
            instrument_type="EQ", product_type="MIS", direction="LONG",
            entry_price=200.0, exit_price=195.0, quantity=50.0,
            entry_datetime="2026-06-01T11:00:00", exit_datetime="2026-06-01T11:30:00")
        crypto_win = ClosedTrade(
            trade_id="crypto_win", symbol="BTCUSDT", exchange="Binance",
            instrument_type="PERP", direction="SHORT",
            entry_price=70000.0, exit_price=69000.0, quantity=1.0, funding_pnl=5.0,
            entry_datetime="2026-06-01T12:00:00", exit_datetime="2026-06-01T13:00:00")
        for t in (nse_win, nse_loss, crypto_win):
            j.record(t)
        return j

    def test_net_pnl_is_gross_minus_charges(self):
        j = self._record_three()
        for t in j.trades:
            self.assertAlmostEqual(t.net_pnl, t.gross_pnl - t.total_charges, places=6)
        win = next(t for t in j.trades if t.trade_id == "nse_win")
        # gross = (110-100)*100 = 1000 for the long
        self.assertAlmostEqual(win.gross_pnl, 1000.0, places=6)
        self.assertGreater(win.total_charges, 0.0)
        self.assertLess(win.net_pnl, win.gross_pnl)
        crypto = next(t for t in j.trades if t.trade_id == "crypto_win")
        # short crypto gross = (entry-exit)*qty = 1000
        self.assertAlmostEqual(crypto.gross_pnl, 1000.0, places=6)
        self.assertIsNotNone(crypto.net_pnl_crypto)

    def test_status_sane_and_json_able(self):
        j = self._record_three()
        st = j.status()
        self.assertEqual(st["n_trades"], 3)
        self.assertEqual(st["columns"], len(COLUMNS))
        self.assertEqual(st["analytics"]["total_trades"], 3)
        self.assertEqual(st["analytics"]["wins"], 2)
        self.assertEqual(st["analytics"]["losses"], 1)
        json.dumps(st)   # fully serialisable

    def test_export_csv_header(self):
        j = self._record_three()
        path = os.path.join(_SCRATCH, "journal_t5.csv")
        j.export_csv(path)
        self.assertTrue(os.path.exists(path))
        with open(path, newline="") as f:
            header = f.readline().strip().split(",")
        self.assertEqual(len(header), len(COLUMNS))
        self.assertEqual(header, COLUMNS)


if __name__ == "__main__":
    unittest.main()
