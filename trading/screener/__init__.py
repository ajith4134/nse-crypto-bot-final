"""trading/screener — per-segment ranked candidate screeners (NSE + crypto).

Offline-safe, CPU-first, reuse-first. The live trade loop calls `Screener` to build
a dynamic, varied watchlist per selected segment; every live data call degrades to a
deterministic stub so tests and the dashboard never break.

Public API:
    Screener, build_demo_screener
    screen_nse_movers, screen_nse_fno,
    screen_crypto_spot, screen_crypto_futures, screen_crypto_options
    apply_technical_filters  (+ the freqtrade-ported pairlist filters in .filters)
"""
from __future__ import annotations

from trading.screener.filters import (
    age_filter,
    apply_technical_filters,
    oi_buildup,
    percent_change_filter,
    range_stability,
    realized_volatility,
    relative_volume,
    score_rows,
    volatility_filter,
    volume_filter,
)
from trading.screener.screener import (
    SEGMENTS,
    Screener,
    build_demo_screener,
    screen_crypto_futures,
    screen_crypto_options,
    screen_crypto_spot,
    screen_nse_fno,
    screen_nse_movers,
)
from trading.screener.stubs import stub_candidates

__all__ = [
    "Screener", "build_demo_screener", "SEGMENTS",
    "screen_nse_movers", "screen_nse_fno",
    "screen_crypto_spot", "screen_crypto_futures", "screen_crypto_options",
    "apply_technical_filters", "percent_change_filter", "volume_filter",
    "relative_volume", "age_filter", "volatility_filter", "realized_volatility",
    "range_stability", "oi_buildup", "score_rows", "stub_candidates",
]
