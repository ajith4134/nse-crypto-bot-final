"""trading/strategy/library/ — curated institutional Strategy Library (the active T8 feature).

A catalog of the *named, proven* strategies used by quant funds / prop desks / market
makers, organised by the 15 institutional categories and the 7 market segments
(NSE cash/intraday/futures/options, MCX commodities, crypto spot/futures/options).

Reuse-first: indicator math is **TA-Lib** (158 C indicators) via `features_ext.py`; the
strategies are thin signal functions that read those columns and emit a +1/-1/0 target
position, scored by the existing `trading.strategy.backtest.backtest_signal`. Strategies
whose edge needs data the OHLCV feed doesn't carry (order-book L2, ticks, IV/greeks, OI,
funding, multi-asset spreads) are catalogued honestly as *data-gated* — full spec, no
fabricated backtest — and light up the moment those columns exist (the repo already
computes greeks, funding, OI elsewhere).

The genetic creation/mutation/evolution engine is gated OFF for this phase
(`trading.strategy.control`); this library is what runs now. Later, survivors here seed
that engine.
"""
from __future__ import annotations

from trading.strategy.library.base import (
    DataReq,
    LibraryStrategy,
    StrategyStatus,
)
from trading.strategy.library.features_ext import EXT_FEATURE_NAMES, compute_features_ext
from trading.strategy.library.registry import (
    LibraryRegistry,
    all_strategies,
    get_registry,
)

__all__ = [
    "DataReq", "LibraryStrategy", "StrategyStatus",
    "compute_features_ext", "EXT_FEATURE_NAMES",
    "LibraryRegistry", "all_strategies", "get_registry",
]
