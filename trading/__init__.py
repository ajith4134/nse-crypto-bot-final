"""trading/ — Trading Execution Phase (T1+).

Wires the ML Network Brain's confidence scores to real order execution across
two independently switchable markets:
  • NSE (this package, T1) via the self-hosted OpenAlgo middleware server.
  • Crypto (T2) via ccxt — added later.

T1 (NSE Foundation) components, all CPU-only and secrets-safe:
  • config.py        — TradingConfig: paper/live mode, OpenAlgo host/key, squareoff times
  • openalgo_client.py — thin REST wrapper over the openalgo SDK (single source of truth)
  • instruments.py   — NSE/NFO/MCX scripmaster loader + symbol search
  • tick_cache.py    — per-symbol real-time price cache (OpenAlgo WS feed, REST fallback)
  • watchlist.py     — persisted watchlist with search/add/remove
  • market_toggle.py — NSE master on/off switch (OFF = zero polling, zero activity)
  • squareoff.py     — exchange auto-squareoff rules (NSE 15:15 / MCX 23:30 / CDS 16:45 IST)

Nothing here places a live order unless TRADING_MODE=live AND the master toggle is ON.
See trading-execution-blueprint.md §7 (Phase T1) for the full plan.
"""
from __future__ import annotations

from trading.config import TradingConfig, trading_config

__all__ = ["TradingConfig", "trading_config"]
