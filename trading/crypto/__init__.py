"""trading/crypto/ — Trading Phase T2 (Crypto Foundation).

The crypto counterpart to the T1 NSE package, built on ccxt's unified API
(Binance + Bybit by default; any of ccxt's 100+ exchanges via config). Mirrors
T1's architecture and REUSES its primitives (MasterToggle, TickCache, state).

T2 components (CPU-only, secrets-safe, paper-first):
  • config.py          — CryptoConfig: exchanges, mode, optional keys, defaults
  • exchange_client.py — ccxt wrapper: spot/swap(perp)/future(quarterly)/option;
                         public ticker/orderbook/funding; guarded live orders
  • liquidation.py     — isolated/cross liquidation-price calculator (pure math)
  • paper_engine.py    — paper-fill simulator: walks the REAL order book to fill,
                         tracks positions, leverage, margin mode, and PnL
  • funding.py         — funding-rate monitor across exchanges (perp basis)
  • feed.py            — ccxt poller into a reused TickCache (toggle-gated)
  • watchlist.py       — persisted crypto watchlist (own state file)
  • session.py         — CryptoSession orchestrator (one honest entry point)

Public market data + the paper simulator need NO API keys. Only LIVE order
placement does, and it is refused unless TRADING_MODE=live AND explicitly allowed.
See trading-execution-blueprint.md §7 (Phase T2).
"""
from __future__ import annotations

from trading.crypto.config import CryptoConfig, crypto_config

__all__ = ["CryptoConfig", "crypto_config"]
