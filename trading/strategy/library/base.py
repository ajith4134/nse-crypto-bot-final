"""trading/strategy/library/base.py — the LibraryStrategy abstraction + data-requirement model.

A LibraryStrategy is a declarative + executable description of ONE named institutional
strategy. The executable part is a pure signal function `(ext_features_df) -> Series[+1/-1/0]`
(target position; +1 long, -1 short, 0 flat) — exactly what `backtest_signal` consumes, so
every strategy plugs into the existing T8 backtest/fitness without new machinery.

`DataReq` records what each strategy actually needs. Strategies on OHLCV(+volume) are
EXECUTABLE and get a real walk-forward backtest. Strategies whose edge is structurally
order-book / tick / IV-greeks / OI / funding / multi-asset driven are DATA_GATED: we keep
the full spec (logic, params, OSS source, data needs) but DO NOT fabricate a backtest —
honest-dashboard-wiring. They become executable as soon as the feed carries those columns.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Callable, Optional

import pandas as pd


class DataReq(enum.Enum):
    """A data input a strategy needs beyond the bar itself."""
    OHLCV = "ohlcv"               # open/high/low/close — always present
    VOLUME = "volume"             # bar volume (present in our feed)
    MULTI_TF = "multi_timeframe"  # needs a second resampled timeframe (derivable)
    FUNDING = "funding"           # perp funding rate (ccxt — computed elsewhere in repo)
    OPEN_INTEREST = "open_interest"
    BASIS = "basis"               # spot-vs-future / perp basis
    IV_GREEKS = "iv_greeks"       # implied vol / delta-gamma-vega-theta (Black-76/vollib)
    OPTION_CHAIN = "option_chain"  # full chain (strikes/expiries) for multi-leg
    ORDERBOOK_L2 = "orderbook_l2"  # depth / queue / imbalance
    TICKS = "ticks"               # trade-by-trade aggressor / footprint
    MULTI_ASSET = "multi_asset"   # 2+ symbols for spread/pairs/dispersion
    FUNDAMENTALS = "fundamentals"  # earnings / book value / dividends
    NEWS_EVENTS = "news_events"    # scheduled events / macro prints / announcements

    @property
    def in_feed(self) -> bool:
        """True if the standard OHLCV+volume bar feed already carries this."""
        return self in (DataReq.OHLCV, DataReq.VOLUME, DataReq.MULTI_TF)


class StrategyStatus(enum.Enum):
    EXECUTABLE = "executable"     # runs on the OHLCV feed now → real backtest
    DATA_GATED = "data_gated"     # spec complete; needs extra data before it can run


# Segment tags (mirror the 7 research files).
SEGMENTS = (
    "nse_cash", "nse_intraday", "nse_futures", "nse_options",
    "mcx_commodities", "crypto_spot", "crypto_futures", "crypto_options",
)

# The 15 institutional categories.
CATEGORIES = (
    "trend_following", "mean_reversion", "momentum", "statistical_arbitrage",
    "market_making", "high_frequency", "order_flow", "volatility", "options",
    "event_driven", "macro", "machine_learning", "liquidity", "cross_asset",
    "relative_value",
)

SignalFn = Callable[[pd.DataFrame], pd.Series]


@dataclass
class LibraryStrategy:
    """One named strategy. `signal` is set for EXECUTABLE strategies, None for DATA_GATED."""
    name: str
    category: str                      # one of CATEGORIES
    family: str                        # finer family label (e.g. "ma_crossover")
    logic: str                         # one-line plain-English edge
    segments: tuple                    # which markets it applies to (subset of SEGMENTS)
    timeframe: str                     # e.g. "intraday 5m", "swing 1d"
    data_req: tuple = (DataReq.OHLCV, DataReq.VOLUME)
    signal: Optional[SignalFn] = None  # (ext_features) -> Series[+1/-1/0]   (OHLCV strategies)
    backtest: Optional[object] = None  # (MarketData) -> metrics dict        (data-backed strategies)
    oss_source: str = ""               # repo / source the logic mirrors
    params: dict = field(default_factory=dict)
    allow_short: bool = True
    stop_atr: float = 2.0
    target_atr: float = 3.0
    notes: str = ""

    # ── derived ────────────────────────────────────────────────────────────────
    @property
    def status(self) -> StrategyStatus:
        # data-backed strategies download their own data (data_sources/) → executable
        if self.backtest is not None:
            return StrategyStatus.EXECUTABLE
        executable = self.signal is not None and all(r.in_feed for r in self.data_req)
        return StrategyStatus.EXECUTABLE if executable else StrategyStatus.DATA_GATED

    @property
    def data_backed(self) -> bool:
        """Executable via a downloaded-data backtest(MarketData) rather than an OHLCV signal."""
        return self.backtest is not None

    @property
    def is_executable(self) -> bool:
        return self.status is StrategyStatus.EXECUTABLE

    @property
    def gating_reqs(self) -> list[str]:
        """Data inputs (beyond the bar feed) that currently gate this strategy."""
        return [r.value for r in self.data_req if not r.in_feed]

    def make_signal(self, ext_feats: pd.DataFrame) -> pd.Series:
        """Run the signal function → clean +1/-1/0 int Series aligned to ext_feats."""
        if self.signal is None:
            raise RuntimeError(f"{self.name} is data-gated; no executable signal "
                               f"(needs {self.gating_reqs}).")
        sig = self.signal(ext_feats)
        sig = pd.Series(sig, index=ext_feats.index).fillna(0)
        sig = sig.clip(-1, 1).round().astype(int)
        if not self.allow_short:
            sig = sig.clip(lower=0)
        return sig

    def to_dict(self) -> dict:
        return {
            "name": self.name, "category": self.category, "family": self.family,
            "logic": self.logic, "segments": list(self.segments),
            "timeframe": self.timeframe,
            "data_req": [r.value for r in self.data_req],
            "status": self.status.value, "gating_reqs": self.gating_reqs,
            "oss_source": self.oss_source, "params": self.params,
            "allow_short": self.allow_short, "stop_atr": self.stop_atr,
            "target_atr": self.target_atr, "notes": self.notes,
        }


# ── signal-building helpers (shared by catalog modules) ──────────────────────────
def long_when(cond: pd.Series, index) -> pd.Series:
    """+1 where cond is True, else 0."""
    return pd.Series(0, index=index, dtype=int).mask(cond.fillna(False), 1)


def long_short(long_cond: pd.Series, short_cond: pd.Series, index) -> pd.Series:
    """+1 on long_cond, -1 on short_cond (long wins ties), 0 otherwise."""
    out = pd.Series(0, index=index, dtype=int)
    s = short_cond.fillna(False)
    l = long_cond.fillna(False)
    out[s] = -1
    out[l] = 1
    return out


def stateful_band(entry_long, exit_long, entry_short=None, exit_short=None,
                  *, index) -> pd.Series:
    """Stateful position: hold +1 from entry_long until exit_long (and symmetric short).

    Many mean-reversion/breakout templates are "enter on trigger, hold until opposite/
    neutral trigger" rather than a per-bar condition. This forward-fills the position
    between an entry and its exit, causally (uses only that bar's booleans).
    """
    el = entry_long.fillna(False).to_numpy()
    xl = exit_long.fillna(False).to_numpy()
    es = (entry_short.fillna(False).to_numpy() if entry_short is not None
          else [False] * len(el))
    xs = (exit_short.fillna(False).to_numpy() if exit_short is not None
          else [False] * len(el))
    pos = 0
    out = []
    for i in range(len(el)):
        if pos == 0:
            if el[i]:
                pos = 1
            elif es[i]:
                pos = -1
        elif pos == 1 and xl[i]:
            pos = 1 if el[i] else 0
            if es[i] and not el[i]:
                pos = -1
        elif pos == -1 and xs[i]:
            pos = -1 if es[i] else 0
            if el[i] and not es[i]:
                pos = 1
        out.append(pos)
    return pd.Series(out, index=index, dtype=int)
