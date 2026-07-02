"""trading/strategy/library/marketdata.py — multi-input data context for library strategies.

Executable-on-OHLCV strategies only need a bar frame; the institutional strategies need more
(funding, open interest, basis, option chains, multiple symbols, fundamentals). `MarketData`
is the single context a data-backed strategy's `backtest(md)` receives — populated by the
`data_sources/` fetchers (real downloaded data, cached to disk). Everything optional so a
strategy reads only what it declared in `data_req`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd


@dataclass
class MarketData:
    """Downloaded inputs for one strategy backtest. All series share a time index where paired."""
    symbol: str = ""
    market: str = ""                                  # segment tag
    ohlcv: pd.DataFrame | None = None                 # primary bar frame (spot or perp)
    perp_ohlcv: pd.DataFrame | None = None            # perpetual/future bars (for basis/funding)
    funding: pd.Series | None = None                  # funding rate per interval (fraction)
    open_interest: pd.Series | None = None            # OI series
    basis: pd.Series | None = None                    # (perp - spot)/spot
    chain: object | None = None                       # trading.options.chain.OptionsChain snapshot
    iv_history: pd.Series | None = None               # ATM IV history (for IV rank/percentile)
    aux: dict = field(default_factory=dict)           # {symbol: ohlcv_df} for multi-asset
    fundamentals: dict = field(default_factory=dict)  # {symbol: {pe, pb, roe, ...}}
    meta: dict = field(default_factory=dict)          # source/exchange/timestamps notes

    def have(self, *attrs: str) -> bool:
        return all(getattr(self, a, None) is not None for a in attrs)
