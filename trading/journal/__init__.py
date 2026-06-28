"""trading/journal/ — Brain Confidence + Trade Journal & Analytics (Phase T5).

Closes the loop from execution (T3) and options (T4) back into the ML Network Brain:
every closed trade is recorded in the full 85-column journal, scored for quality
(MAE/MFE/R-multiple/efficiency), aggregated into analytics (win-rate by dimension,
profit factor, expectancy, streaks), screened for bad behaviour (revenge/overtrading),
rendered as a self-contained HTML tearsheet, and fed into a per-symbol confidence
estimator that recalibrates the Brain after each outcome.

Everything is pure Python + JSON persistence (reuses trading.state), offline and
unit-testable. Optional libs (quantstats, weasyprint) are used only if installed.

Pieces (blueprint §T5, §5):
  schema      — the 85+ column ClosedTrade record + canonical column order + CSV/dict IO
  charges     — Indian (STT/txn/brokerage/GST/SEBI/stamp) + crypto (maker/taker/funding)
                cost math → gross→net P&L
  quality     — MAE/MFE/R-multiple/entry-exit efficiency/holding duration on a trade
  analytics   — win-rate by time/day/regime/instrument/strategy, profit factor,
                expectancy, streaks, R-multiple distribution, MAE/MFE scatter
  behavior    — revenge-trade detector + overtrading flagging
  confidence  — per-symbol calibrated confidence score + Brain recalibration loop
  tearsheet   — equity curve, drawdown, monthly P&L heatmap → dependency-free HTML
  journal     — TradeJournal: append/persist closed trades, run everything, status()
"""
from __future__ import annotations

from trading.journal.analytics import JournalAnalytics, analyze_trades
from trading.journal.behavior import flag_overtrading, flag_revenge_trade, screen_behavior
from trading.journal.charges import crypto_charges, nse_charges, net_pnl
from trading.journal.confidence import ConfidenceBook, SymbolConfidence
from trading.journal.quality import trade_quality
from trading.journal.schema import COLUMNS, ClosedTrade
from trading.journal.tearsheet import render_tearsheet
from trading.journal.journal import TradeJournal

__all__ = [
    "ClosedTrade", "COLUMNS",
    "nse_charges", "crypto_charges", "net_pnl",
    "trade_quality",
    "analyze_trades", "JournalAnalytics",
    "flag_revenge_trade", "flag_overtrading", "screen_behavior",
    "SymbolConfidence", "ConfidenceBook",
    "render_tearsheet",
    "TradeJournal",
]
