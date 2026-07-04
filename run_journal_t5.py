"""run_journal_t5.py — Trading Phase T5 (Brain Confidence + Trade Journal) offline demo + status.

Drives the network-INDEPENDENT closed-trade journal end to end on a deterministic set
of synthetic CLOSED trades (NO network, NO API keys, fully reproducible). Every T5
analytic lights up on the same recorded trades:

  1. record() ~9 closed trades spanning NSE equity (MIS long+short), NSE options
     (CE/PE premiums), crypto perp (with funding) and an NSE delivery (CNC), across
     two calendar dates — charges → net P&L, MAE/MFE/R-multiple/efficiency quality,
     revenge/overtrading behaviour flags and per-symbol confidence all populate.
  2. per-trade net P&L + R-multiple + total charges for a couple of representative
     trades (NSE equity + crypto perp).
  3. the analytics summary — win rate, profit factor, expectancy, streaks, and the
     win-rate/net-P&L breakdown by instrument/strategy/regime.
  4. the behaviour screen — revenge-trade + overtrading counts and flagged ids.
  5. the per-symbol Brain confidence book (Bayesian win-rate + calibration/Brier).
  6. an HTML tearsheet + a PDF tearsheet (quantstats-enriched, weasyprint) written
     to the scratchpad dir, with their paths + byte sizes.
  7. a CSV export to the scratchpad dir, printing the canonical column count.
  8. the honest journal.status() snapshot as indented JSON (what the dashboard reads).

Everything is pure CPU logic on injected trades — the same TradeJournal records live
NSE (OpenAlgo) + crypto (ccxt) outcomes once the execution loop feeds it ClosedTrades.

Usage:
    .venv/bin/python run_journal_t5.py
"""
from __future__ import annotations

import tempfile
import json
import os
import sys

from trading.journal import ClosedTrade, TradeJournal
from trading.journal.behavior import screen_behavior
from trading.journal.tearsheet import render_tearsheet, render_tearsheet_pdf

SCRATCH = tempfile.mkdtemp(prefix="mlnb_scratch_")  # session-independent temp dir

# Tight daily limit so the demo's clustered same-day trades trip the overtrading
# detector; 5-minute revenge window is the module default.
_DAILY_LIMIT = 3
_REVENGE_WINDOW_MIN = 5


def _hdr(title: str) -> None:
    print(f"\n=== {title} ===")


def build_demo_journal() -> TradeJournal:
    """Construct the deterministic in-memory TradeJournal used by the demo + dashboard.

    Records ~9 synthetic CLOSED trades (persist=False, so nothing is written to disk).
    Each trade carries real entry/exit/qty/stop/timestamps + MAE/MFE + a Brain
    prediction, so every derived column (charges→net P&L, R-multiple, efficiency,
    behaviour flags, confidence) is a REAL computed number rather than a placeholder.
    """
    j = TradeJournal(persist=False, daily_limit=_DAILY_LIMIT,
                     revenge_window_min=_REVENGE_WINDOW_MIN)

    trades = [
        # ── Day 1 (2026-06-25) — NSE intraday equity + index options ──────────────
        # 1. RELIANCE MIS long — clean winner.
        ClosedTrade(
            trade_id="T1", symbol="RELIANCE", exchange="NSE", instrument_type="EQ",
            direction="LONG", product_type="MIS", strategy_name="Momentum",
            setup_type="Breakout", market_regime_entry="Trending",
            entry_datetime="2026-06-25T09:20:00", exit_datetime="2026-06-25T09:50:00",
            quantity=100, entry_price=2800.0, exit_price=2850.0, initial_sl_price=2780.0,
            mae=800.0, mfe=6000.0, brain_confidence_entry=0.72, brain_prediction="UP"),
        # 2. TCS MIS short — loser (price rose against the short).
        ClosedTrade(
            trade_id="T2", symbol="TCS", exchange="NSE", instrument_type="EQ",
            direction="SHORT", product_type="MIS", strategy_name="Reversal",
            setup_type="Reversal", market_regime_entry="Ranging",
            entry_datetime="2026-06-25T09:25:00", exit_datetime="2026-06-25T10:05:00",
            quantity=50, entry_price=3900.0, exit_price=3930.0, initial_sl_price=3950.0,
            mae=1500.0, mfe=600.0, brain_confidence_entry=0.58, brain_prediction="DOWN"),
        # 3. HDFCBANK MIS long — entered 2 min after T2's losing exit → revenge.
        ClosedTrade(
            trade_id="T3", symbol="HDFCBANK", exchange="NSE", instrument_type="EQ",
            direction="LONG", product_type="MIS", strategy_name="Momentum",
            setup_type="Scalp", market_regime_entry="Ranging",
            entry_datetime="2026-06-25T10:07:00", exit_datetime="2026-06-25T10:25:00",
            quantity=80, entry_price=1650.0, exit_price=1638.0, initial_sl_price=1635.0,
            mae=1280.0, mfe=560.0, brain_confidence_entry=0.61, brain_prediction="UP"),
        # 4. NIFTY CE long — index call option (premium turnover). 4th trade today.
        ClosedTrade(
            trade_id="T4", symbol="NIFTY26JUN24000CE", exchange="NFO",
            instrument_type="CE", direction="LONG", product_type="NRML",
            strategy_name="Momentum", setup_type="Breakout",
            market_regime_entry="Volatile", underlying_symbol="NIFTY",
            strike_price=24000.0, option_type="CE", lot_size=50, num_lots=2,
            entry_datetime="2026-06-25T10:30:00", exit_datetime="2026-06-25T11:10:00",
            quantity=100, entry_price=120.0, exit_price=168.0, initial_sl_price=95.0,
            mae=900.0, mfe=5200.0, brain_confidence_entry=0.80, brain_prediction="UP"),
        # 5. BANKNIFTY PE long — index put option. 5th trade today (over limit).
        ClosedTrade(
            trade_id="T5", symbol="BANKNIFTY26JUN51000PE", exchange="NFO",
            instrument_type="PE", direction="LONG", product_type="NRML",
            strategy_name="Reversal", setup_type="Reversal",
            market_regime_entry="Volatile", underlying_symbol="BANKNIFTY",
            strike_price=51000.0, option_type="PE", lot_size=15, num_lots=2,
            entry_datetime="2026-06-25T11:30:00", exit_datetime="2026-06-25T12:15:00",
            quantity=30, entry_price=210.0, exit_price=176.0, initial_sl_price=180.0,
            mae=1020.0, mfe=450.0, brain_confidence_entry=0.55, brain_prediction="DOWN"),

        # ── Day 2 (2026-06-26) — crypto perps + NSE delivery ──────────────────────
        # 6. BTC/USDT perp long — winner, funding collected.
        ClosedTrade(
            trade_id="T6", symbol="BTC/USDT", exchange="binance",
            instrument_type="PERP", direction="LONG", product_type="ISOLATED",
            strategy_name="Momentum", setup_type="Swing",
            market_regime_entry="Trending", margin_used=2000.0, leverage=10.0,
            entry_datetime="2026-06-26T08:00:00", exit_datetime="2026-06-26T14:00:00",
            quantity=0.5, entry_price=64000.0, exit_price=65200.0,
            initial_sl_price=63400.0, funding_pnl=12.5,
            mae=180.0, mfe=900.0, brain_confidence_entry=0.77, brain_prediction="UP"),
        # 7. ETH/USDT perp short — loser, funding paid (negative).
        ClosedTrade(
            trade_id="T7", symbol="ETH/USDT", exchange="binance",
            instrument_type="PERP", direction="SHORT", product_type="ISOLATED",
            strategy_name="Reversal", setup_type="Scalp",
            market_regime_entry="Volatile", margin_used=1500.0, leverage=8.0,
            entry_datetime="2026-06-26T09:00:00", exit_datetime="2026-06-26T09:40:00",
            quantity=5.0, entry_price=3400.0, exit_price=3440.0,
            initial_sl_price=3460.0, funding_pnl=-6.0,
            mae=250.0, mfe=90.0, brain_confidence_entry=0.52, brain_prediction="DOWN"),
        # 8. SOL/USDT perp long — entered 3 min after T7's losing exit → revenge.
        ClosedTrade(
            trade_id="T8", symbol="SOL/USDT", exchange="binance",
            instrument_type="PERP", direction="LONG", product_type="ISOLATED",
            strategy_name="Momentum", setup_type="Scalp",
            market_regime_entry="Volatile", margin_used=800.0, leverage=5.0,
            entry_datetime="2026-06-26T09:43:00", exit_datetime="2026-06-26T10:30:00",
            quantity=40.0, entry_price=145.0, exit_price=151.0,
            initial_sl_price=141.0, funding_pnl=3.2,
            mae=120.0, mfe=320.0, brain_confidence_entry=0.66, brain_prediction="UP"),
        # 9. ICICIBANK CNC delivery long — winner, delivery charges (STT both sides).
        ClosedTrade(
            trade_id="T9", symbol="ICICIBANK", exchange="NSE", instrument_type="EQ",
            direction="LONG", product_type="CNC", strategy_name="Swing",
            setup_type="Swing", market_regime_entry="Trending",
            entry_datetime="2026-06-26T10:00:00", exit_datetime="2026-06-26T15:10:00",
            quantity=200, entry_price=1180.0, exit_price=1212.0, initial_sl_price=1160.0,
            mae=1000.0, mfe=7200.0, brain_confidence_entry=0.69, brain_prediction="UP"),
    ]
    for t in trades:
        j.record(t)
    return j


def _print_trade(t) -> None:
    rm = f"{t.r_multiple:+.2f}R" if t.r_multiple is not None else "n/a"
    eff = f"{t.exit_efficiency:.0f}%" if t.exit_efficiency is not None else "n/a"
    print(f"  {t.trade_id} {t.symbol:<22} {t.direction:<5} {t.instrument_type:<4}"
          f"  gross={t.gross_pnl:+10.2f}  charges={t.total_charges:9.2f}"
          f"  net={t.net_pnl:+10.2f}  R={rm:<7} exit_eff={eff}")


def main() -> int:
    print("ML Network Brain — Trading T5 (Brain Confidence + Trade Journal) offline demo")
    j = build_demo_journal()
    print(f"  recorded {len(j.trades)} synthetic closed trades "
          f"(persist=False, daily_limit={_DAILY_LIMIT}, "
          f"revenge_window={_REVENGE_WINDOW_MIN}min)")

    _hdr("1. per-trade net P&L + R-multiple + charges (representative trades)")
    by_id = {t.trade_id: t for t in j.trades}
    for tid in ("T1", "T4", "T6", "T9"):
        _print_trade(by_id[tid])

    _hdr("2. analytics summary")
    a = j.analytics()
    pf = f"{a.profit_factor:.2f}" if a.profit_factor is not None else "n/a (no losses)"
    print(f"  trades={a.total_trades} wins={a.wins} losses={a.losses} "
          f"breakeven={a.breakeven}  win_rate={a.win_rate:.1f}%")
    print(f"  net_pnl={a.net_pnl:+.2f}  profit_factor={pf}  "
          f"expectancy={a.expectancy:+.2f}/trade")
    print(f"  avg_win={a.avg_win:+.2f}  avg_loss={-a.avg_loss:+.2f}  "
          f"max_win_streak={a.max_win_streak}  max_loss_streak={a.max_loss_streak}  "
          f"current_streak={a.current_streak:+d}")
    print("  R-multiple distribution: " +
          "  ".join(f"{k}={v}" for k, v in a.r_multiple_distribution.items()))
    for dim in ("instrument_type", "strategy_name", "market_regime_entry"):
        print(f"  by {dim}:")
        for key, b in sorted(a.by_dimension[dim].items()):
            print(f"      {key:<14} trades={b['trades']} "
                  f"win_rate={b['win_rate']:5.1f}%  net_pnl={b['net_pnl']:+10.2f}")

    _hdr("3. behaviour screen (revenge / overtrading)")
    beh = screen_behavior(j.trades, daily_limit=_DAILY_LIMIT,
                          revenge_window_min=_REVENGE_WINDOW_MIN)
    print(f"  revenge_count={beh['revenge_count']}  "
          f"overtrading_count={beh['overtrading_count']}")
    print(f"  flagged_trade_ids={beh['flagged_trade_ids']}")
    for t in j.trades:
        if t.revenge_trade_flag or t.overtrading_flag:
            tags = []
            if t.revenge_trade_flag:
                tags.append("REVENGE")
            if t.overtrading_flag:
                tags.append("OVERTRADING")
            print(f"      {t.trade_id} {t.symbol:<22} entry={t.entry_datetime}  "
                  f"{' + '.join(tags)}")

    _hdr("4. per-symbol Brain confidence book")
    cb = j.confidence.as_dict()
    owr = cb["overall_win_rate"]
    obr = cb["overall_brier"]
    owr_s = f"{owr*100:.1f}%" if owr is not None else "n/a"
    obr_s = f"{obr:.4f}" if obr is not None else "n/a"
    print(f"  symbols={cb['n_symbols']}  total_trades={cb['total_trades']}  "
          f"overall_win_rate={owr_s}  overall_brier={obr_s}")
    for sym, sc in sorted(cb["symbols"].items()):
        brier = f"{sc['brier']:.4f}" if sc["brier"] is not None else "n/a"
        print(f"      {sym:<22} n={sc['n']} w/l={sc['wins']}/{sc['losses']}  "
              f"win_rate={sc['win_rate']*100:5.1f}%  "
              f"confidence={sc['confidence']*100:5.1f}%  brier={brier}")

    _hdr("5. tearsheets (HTML + PDF, quantstats-enriched, weasyprint)")
    os.makedirs(SCRATCH, exist_ok=True)
    html_path = os.path.join(SCRATCH, "journal_t5_tearsheet.html")
    pdf_path = os.path.join(SCRATCH, "journal_t5_tearsheet.pdf")
    html = render_tearsheet(j.trades, title="ML-Network-Brain · T5 Trade Journal")
    with open(html_path, "w") as f:
        f.write(html)
    render_tearsheet_pdf(j.trades, pdf_path,
                         title="ML-Network-Brain · T5 Trade Journal")
    print(f"  HTML: {html_path} ({os.path.getsize(html_path):,} bytes)")
    print(f"  PDF : {pdf_path} ({os.path.getsize(pdf_path):,} bytes)")

    _hdr("6. CSV export")
    csv_path = os.path.join(SCRATCH, "journal_t5_trades.csv")
    j.export_csv(csv_path)
    with open(csv_path) as f:
        header = f.readline().strip()
    print(f"  CSV : {csv_path} ({os.path.getsize(csv_path):,} bytes, "
          f"{len(header.split(','))} columns)")

    _hdr("7. honest journal.status() snapshot (what the dashboard reads)")
    print(json.dumps(j.status(), indent=2, default=str))

    print("\n✅ T5 trade-journal + brain-confidence demo complete (offline, deterministic).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
