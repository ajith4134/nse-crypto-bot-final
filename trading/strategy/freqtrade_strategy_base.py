"""trading/strategy/freqtrade_strategy_base.py — concrete Freqtrade base for library strategies.

This module imports ``freqtrade`` at top level, so it is ONLY imported inside the Freqtrade
process (by the generated ``lib_*.py`` strategy files). The freqtrade-free helpers/generator live
in ``trading.strategy.freqtrade_adapter`` and never import this.

Each generated strategy is a real ``class <Name>(LibraryStrategyBase)`` with ``library_name`` set
— a genuine class statement, so Freqtrade's resolver discovers it normally (correct ``__module__``).
The base turns the library's vectorized ``+1/-1/0`` signal into Freqtrade entry/exit columns:

    +1 -> enter_long  (hold while +1)        sig<=0 -> exit_long
    -1 -> enter_short (futures, if allowed)  sig>=0 -> exit_short
"""
from __future__ import annotations

import pandas as pd
from freqtrade.strategy import IStrategy

_OHLCV = ["open", "high", "low", "close", "volume"]


class LibraryStrategyBase(IStrategy):
    """Base that runs a named LibraryStrategy's signal. Subclasses set ``library_name``."""

    INTERFACE_VERSION = 3
    timeframe = "5m"
    # exits are signal-driven (libsig flips); ROI far so it doesn't pre-empt the signal,
    # stoploss is a wide protective backstop (the library's own stop is ATR-based intrabar).
    minimal_roi = {"0": 100.0}
    stoploss = -0.15
    trailing_stop = False
    process_only_new_candles = True
    startup_candle_count = 60
    can_short = False

    library_name: str | None = None   # set by each generated subclass

    def _lib(self):
        from trading.strategy.library.registry import get_registry
        lib = get_registry().get(self.library_name)
        if lib is None or lib.signal is None:
            raise ValueError(f"library strategy {self.library_name!r} not found / has no signal")
        return lib

    def populate_indicators(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        from trading.strategy.library.features_ext import compute_features_ext
        ohlcv = dataframe[_OHLCV].reset_index(drop=True)
        sig = self._lib().make_signal(compute_features_ext(ohlcv))   # +1/-1/0
        dataframe["libsig"] = (pd.Series(sig).reindex(range(len(ohlcv)))
                               .fillna(0).astype(int).to_numpy())
        return dataframe

    def populate_entry_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["enter_long"] = (dataframe["libsig"] == 1).astype(int)
        if self.can_short:
            dataframe["enter_short"] = (dataframe["libsig"] == -1).astype(int)
        return dataframe

    def populate_exit_trend(self, dataframe: pd.DataFrame, metadata: dict) -> pd.DataFrame:
        dataframe["exit_long"] = (dataframe["libsig"] <= 0).astype(int)
        if self.can_short:
            dataframe["exit_short"] = (dataframe["libsig"] >= 0).astype(int)
        return dataframe
