"""trading/strategy/library/data_sources/ — REAL data fetchers for the library strategies.

Per CONVENTIONS.md §10 NEVER-SKIP: strategies are never stubbed for missing data — these
modules DOWNLOAD it (free/no-key first). Each fetch is cached to disk (data/strategy_library/)
so backtests are reproducible offline after the first download.

  crypto_deriv — ccxt: spot/perp OHLCV, funding-rate history, open interest, basis
  deribit      — Deribit public API: crypto option chains → trading.options.OptionsChain
  multi_asset  — aligned multi-symbol frames (ccxt + OpenAlgo) for pairs/spreads/baskets
"""
from __future__ import annotations

import os

# On-disk cache root (repo/data/strategy_library). Created lazily by fetchers.
CACHE_DIR = os.environ.get(
    "STRATEGY_LIB_CACHE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), "data", "strategy_library"),
)


def cache_path(name: str) -> str:
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)
