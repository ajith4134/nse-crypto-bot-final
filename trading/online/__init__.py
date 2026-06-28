"""trading/online/ — "Go online": continuous paper/live trading with safe switches (O1–O5).

Makes the bot run continuously — crypto paper-trades 24/7 on live public data, NSE
paper-trades off-hours by replaying its tick cache — with independent per-market on/off
toggles, a safe paper↔real switch, an editable paper wallet, and a central trading-state
gate. CPU-first, offline-testable (live feeds injected/gated). Built from the research in
research/online-*.md (reuse-first: pandas_market_calendars, APScheduler, ccxt).

Pieces:
  session     — O1: market calendar (XNSE) + LIVE↔REPLAY mode per market
  state       — O1: per-market {enabled, mode, allow_live, trading_state} + ACTIVE/REDUCING/
                HALTED gate + persisted registry
  wallet      — O2: editable per-market paper wallet (set/top-up/reset) + reality models
  replay      — O3: NSE off-hours candle/tick replay feeding the same strategy
  supervisor  — O4: always-on loop (crypto 24/7 + NSE scheduler-gated replay)
"""
from __future__ import annotations

from trading.online.session import MarketSession
from trading.online.state import (
    MarketRegistry,
    MarketState,
    TradingState,
    TradingStateGate,
)
from trading.online.wallet import PaperWallet, PaperWalletBook
from trading.online.replay import CandleReplay, ReplaySession, synthetic_ticks
from trading.online.supervisor import OnlineSupervisor

__all__ = [
    "MarketSession",
    "MarketState", "MarketRegistry", "TradingState", "TradingStateGate",
    "PaperWallet", "PaperWalletBook",
    "CandleReplay", "ReplaySession", "synthetic_ticks",
    "OnlineSupervisor",
]
