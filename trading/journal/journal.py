"""trading/journal/journal.py — TradeJournal orchestrator (T5).

The single honest entry point for the closed-trade journal. `record()` takes a
ClosedTrade, fills in the derived columns (charges → net P&L, quality metrics,
behaviour flags), updates the per-symbol confidence book, and persists the whole
journal as JSON (reuses trading.state). `analytics()`, `tearsheet()`, `export_csv()`
and `status()` read off the accumulated trades.

It composes the T5 leaf modules behind fixed contracts:
  charges.nse_charges / crypto_charges / net_pnl
  quality.trade_quality(trade) -> dict of quality fields
  behavior.screen_behavior(trades, ...) -> mutates flags, returns summary
  confidence.ConfidenceBook.update_from_trade(trade)
  analytics.analyze_trades(trades) -> JournalAnalytics
  tearsheet.render_tearsheet(trades, ...) -> html
"""
from __future__ import annotations

from trading import state
from trading.journal.analytics import analyze_trades
from trading.journal.behavior import screen_behavior
from trading.journal.charges import crypto_charges, net_pnl, nse_charges
from trading.journal.confidence import ConfidenceBook
from trading.journal.quality import trade_quality
from trading.journal.schema import COLUMNS, ClosedTrade, csv_header
from trading.journal.tearsheet import render_tearsheet

_CRYPTO_EXCHANGES = {"binance", "bybit", "okx", "kucoin", "coinbase", "kraken", "bitget"}
_CRYPTO_INSTRUMENTS = {"PERP", "SPOT", "QUARTERLY"}


def _is_crypto(trade: ClosedTrade) -> bool:
    return (trade.exchange or "").lower() in _CRYPTO_EXCHANGES \
        or (trade.instrument_type or "").upper() in _CRYPTO_INSTRUMENTS


def _segment(trade: ClosedTrade) -> str:
    it = (trade.instrument_type or "").upper()
    if it in ("CE", "PE", "OPT"):
        return "opt"
    if it in ("FUT",):
        return "fut"
    return "eq_delivery" if (trade.product_type or "").upper() == "CNC" else "eq_intraday"


class TradeJournal:
    """Accumulates closed trades + every T5 analytic on top of them."""

    def __init__(self, *, state_file: str = "journal.json", daily_limit: int = 10,
                 revenge_window_min: int = 5, persist: bool = True,
                 confidence_book: ConfidenceBook | None = None):
        self.state_file = state_file
        self.daily_limit = daily_limit
        self.revenge_window_min = revenge_window_min
        self.persist = persist
        self.confidence = confidence_book or ConfidenceBook()
        self._trades: list[ClosedTrade] = []
        if persist:
            self._load()

    # ── persistence ─────────────────────────────────────────────────────────────
    def _load(self) -> None:
        rows = state.load_json(self.state_file, [])
        if isinstance(rows, list):
            self._trades = [ClosedTrade.from_dict(r) for r in rows if isinstance(r, dict)]
            for t in self._trades:
                self.confidence.update_from_trade(t)

    def _save(self) -> None:
        if self.persist:
            state.save_json(self.state_file, [t.to_dict() for t in self._trades])

    # ── derive columns ──────────────────────────────────────────────────────────
    def _compute_gross(self, t: ClosedTrade) -> float:
        if t.gross_pnl:
            return t.gross_pnl
        if not (t.entry_price and t.exit_price and t.quantity):
            return 0.0
        sign = -1.0 if (t.direction or "").upper() == "SHORT" else 1.0
        return sign * (t.exit_price - t.entry_price) * t.quantity

    def _apply_charges(self, t: ClosedTrade) -> None:
        entry_val = t.entry_price * t.quantity
        exit_val = t.exit_price * t.quantity
        if _is_crypto(t):
            ch = crypto_charges(entry_notional=entry_val, exit_notional=exit_val,
                                funding_pnl=t.funding_pnl)
            t.maker_taker_fee = ch["maker_taker_fee"]
            t.total_charges = ch["total_charges"]
        else:
            if (t.direction or "").upper() == "SHORT":
                buy_value, sell_value = exit_val, entry_val
            else:
                buy_value, sell_value = entry_val, exit_val
            ch = nse_charges(_segment(t), buy_value=buy_value, sell_value=sell_value)
            t.stt = ch["stt"]
            t.exchange_txn_charges = ch["exchange_txn_charges"]
            t.sebi_charges = ch["sebi_charges"]
            t.stamp_duty = ch["stamp_duty"]
            t.brokerage = ch["brokerage"]
            t.gst = ch["gst"]
            t.total_charges = ch["total_charges"]

    # ── record ──────────────────────────────────────────────────────────────────
    def record(self, trade: ClosedTrade) -> ClosedTrade:
        """Finalise a closed trade: charges → net P&L, quality, behaviour, confidence."""
        trade.gross_pnl = self._compute_gross(trade)
        self._apply_charges(trade)
        trade.net_pnl = net_pnl(trade.gross_pnl, trade.total_charges)
        margin = trade.margin_used or (trade.entry_price * trade.quantity) or None
        if margin:
            trade.net_pnl_pct = trade.net_pnl / margin * 100.0
        if _is_crypto(trade):
            trade.net_pnl_crypto = trade.net_pnl

        # quality metrics (R-multiple, efficiency, duration, …)
        for k, v in trade_quality(trade).items():
            setattr(trade, k, v)

        # behaviour flags (mutates flags in place). Screen only the SAME-DAY slice, not
        # the whole history: flags are stamped at close time and both signals are local —
        # revenge looks back revenge_window_min, overtrading counts the calendar day.
        # screen_behavior is O(n²) with a datetime parse per comparison, so re-screening
        # 2,700+ rows per close turned a 415-trade backfill into hours (2026-07-09) and
        # silently taxed every live close as the journal grew.
        day = str(trade.entry_datetime or trade.exit_datetime or "")[:10]
        same_day = [t for t in self._trades
                    if day and (str(t.entry_datetime or "").startswith(day)
                                or str(t.exit_datetime or "").startswith(day))]
        screen_behavior(same_day + [trade], daily_limit=self.daily_limit,
                        revenge_window_min=self.revenge_window_min)

        # W1 goal scoreboard (owner goal 2026-07-07): every closed trade carries its own
        # toward-goal score — net PnL as a fraction of its segment's DAILY goal pace.
        # Central here so EVERY engine (live loop, Freqtrade ingest, sandbox) gets it.
        try:
            from trading import goal as _goal
            _gs = _goal.score_trade(trade.to_dict())
            if _gs.get("goal_score") is not None:
                trade.goal_score = _gs["goal_score"]
                trade.toward_goal = _gs["toward_goal"]
        except Exception:
            pass

        # per-symbol confidence recalibration
        self.confidence.update_from_trade(trade)

        # W7 track record: every closed trade is one RUN for its strategy — trust
        # follows the accumulated record (vp4's thousand-task library), not the code.
        try:
            from trading.brain import track_record as _tr
            _win = (trade.net_pnl > 0) if trade.net_pnl is not None else None
            _tr.bump(f"strategy:{trade.strategy_name or 'unknown'}",
                     kind="strategy", win=_win)
        except Exception:
            pass

        self._trades.append(trade)
        self._save()
        return trade

    # ── reads ───────────────────────────────────────────────────────────────────
    @property
    def trades(self) -> list[ClosedTrade]:
        return list(self._trades)

    def analytics(self):
        return analyze_trades(self._trades)

    def tearsheet(self, **kw) -> str:
        return render_tearsheet(self._trades, **kw)

    def export_csv(self, path: str) -> str:
        import csv
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            for t in self._trades:
                w.writerow(t.to_row())
        return path

    def status(self) -> dict:
        a = self.analytics()
        return {
            "n_trades": len(self._trades),
            "columns": len(COLUMNS),
            "analytics": a.as_dict() if hasattr(a, "as_dict") else a,
            "confidence": self.confidence.as_dict(),
        }
