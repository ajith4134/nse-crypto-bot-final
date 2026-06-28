"""trading/online/replay.py — NSE off-hours candle/tick replay feed (Phase O3).

When NSE is closed (``MarketSession.mode() == 'REPLAY'``, see ``session.py``) we want
paper trading to keep running. The trick (Backtrader ``replaydata`` pattern, research:
online-nse-offhours-paper-trading.md) is to feed the **same strategy code** a stream of
cached historical bars *as if they were arriving live* — each step exposes only the data
up to and including the current bar, so a forming bar looks identical to a live one and
there is NO lookahead. Signal parity between LIVE and REPLAY is the whole point.

When only OHLC bars are cached, each bar can be expanded into a handful of synthetic
intra-bar ticks (MT5 4-tick model / interpolation) so SL/target/trailing logic fires on a
plausible price path. Ticks are pinned to open (first) and close (last) and never escape
[low, high].

Reuse-first / CPU-first / deterministic: numpy + pandas only, seeded RNG, fully offline.

Public API
----------
- ``synthetic_ticks(bar, n=4, *, rng=None)`` -> list[float]
- ``CandleReplay(ohlcv, *, tick_per_bar=1, pace=None)`` -> ``.stream()``, ``.window(i)``, ``.status()``
- ``ReplaySession(market, ohlcv, session=None)`` -> ``.should_replay()``, ``.run(on_bar)``, ``.status()``
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Callable, Iterator

import numpy as np
import pandas as pd

_OHLC = ("open", "high", "low", "close")


def _as_bar(bar) -> dict:
    """Normalise a bar (pd.Series / Mapping) to a plain O/H/L/C/V dict of floats."""
    if isinstance(bar, pd.Series):
        get = lambda k: bar.get(k, bar.get(k.upper()))  # noqa: E731
    else:
        get = lambda k: bar.get(k, bar.get(k.upper())) if hasattr(bar, "get") else None  # noqa: E731
    o, h, l, c = (float(get(k)) for k in _OHLC)
    v = get("volume")
    v = float(v) if v is not None and not pd.isna(v) else 0.0
    return {"open": o, "high": h, "low": l, "close": c, "volume": v}


def synthetic_ticks(bar, n: int = 4, *, rng: np.random.Generator | None = None) -> list[float]:
    """Expand a single OHLC bar into ``n`` intra-bar tick prices.

    Realistic ordering heuristic (research):
      * up-bar   (close >= open): O -> L -> H -> C
      * down-bar (close <  open): O -> H -> L -> C

    The 4 anchor prices are walked through in that order and the path is linearly
    interpolated up to ``n`` ticks. A small Brownian-bridge-style jitter (deterministic
    via ``rng``) is added to interior ticks, then everything is clamped to [low, high].
    The result always starts at ``open`` and ends at ``close`` and stays within [L, H].
    """
    b = _as_bar(bar)
    o, h, l, c = b["open"], b["high"], b["low"], b["close"]
    n = max(2, int(n))

    anchors = [o, l, h, c] if c >= o else [o, h, l, c]

    # Resample the 4-anchor polyline to n points (anchors[0]==first, anchors[-1]==last).
    pos = np.linspace(0.0, len(anchors) - 1, n)
    base = np.interp(pos, np.arange(len(anchors)), anchors)

    if rng is not None and n > 2 and h > l:
        # Brownian-bridge jitter pinned to 0 at both ends; scaled to bar range.
        scale = 0.15 * (h - l)
        t = np.linspace(0.0, 1.0, n)
        steps = rng.standard_normal(n)
        walk = np.cumsum(steps)
        bridge = walk - t * walk[-1]          # pin endpoints to 0
        base = base + scale * bridge

    base[0] = o                               # pin open
    base[-1] = c                              # pin close
    base = np.clip(base, l, h)                # never escape the bar's range
    return [float(x) for x in base]


class CandleReplay:
    """Stream a cached OHLCV frame bar-by-bar as a live-like feed (no lookahead).

    Each yielded step exposes only ``ohlcv.iloc[:i+1]`` (via :meth:`window`), so a
    strategy computing features on the window sees exactly what it would see live as the
    i-th bar finishes forming. With ``tick_per_bar > 1`` each bar also yields synthetic
    intra-bar ticks. ``pace`` (seconds) optionally throttles to wall-clock (default None =
    as-fast-as-possible, for tests).
    """

    def __init__(self, ohlcv: pd.DataFrame, *, tick_per_bar: int = 1,
                 pace: float | None = None, seed: int = 0):
        need = set(_OHLC)
        missing = need - set(ohlcv.columns)
        if missing:
            raise ValueError(f"ohlcv missing columns: {sorted(missing)}")
        self.ohlcv = ohlcv
        self.tick_per_bar = max(1, int(tick_per_bar))
        self.pace = pace
        self._rng = np.random.default_rng(seed)
        self.n_bars = len(ohlcv)

    def window(self, upto_index: int) -> pd.DataFrame:
        """Causal OHLCV slice ``[0 : upto_index+1]`` — the only data a strategy may see."""
        if upto_index < 0:
            raise IndexError("upto_index must be >= 0")
        return self.ohlcv.iloc[: upto_index + 1]

    def stream(self) -> Iterator[dict]:
        """Yield ``{index, ts, bar, ticks}`` per bar, in causal order (no lookahead)."""
        idx = self.ohlcv.index
        for i in range(self.n_bars):
            row = self.ohlcv.iloc[i]
            bar = _as_bar(row)
            ts = idx[i]
            ts = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)
            ticks = (synthetic_ticks(bar, self.tick_per_bar, rng=self._rng)
                     if self.tick_per_bar > 1 else [bar["close"]])
            if self.pace:
                time.sleep(self.pace)
            yield {"index": i, "ts": ts, "bar": bar, "ticks": ticks}

    def status(self) -> dict:
        return {"feed": "CandleReplay", "n_bars": int(self.n_bars),
                "tick_per_bar": self.tick_per_bar, "pace": self.pace}


class ReplaySession:
    """Tie a :class:`MarketSession` to a cached OHLCV frame and drive off-hours replay.

    ``.run(on_bar)`` walks the replay and calls ``on_bar(window_df, bar)`` per bar, where
    ``window_df`` is the causal slice (no lookahead) the strategy computes its signal on.
    """

    def __init__(self, market, ohlcv: pd.DataFrame, session=None, *,
                 tick_per_bar: int = 1, pace: float | None = None, seed: int = 0):
        if session is not None:
            self.session = session
            self.market = getattr(session, "market", str(market)).upper()
        else:
            from trading.online.session import MarketSession
            self.market = str(market).upper()
            self.session = MarketSession(self.market)
        self.ohlcv = ohlcv
        self.replay = CandleReplay(ohlcv, tick_per_bar=tick_per_bar, pace=pace, seed=seed)
        self._bars_replayed = 0

    def should_replay(self, when: datetime | None = None) -> bool:
        """True when the market is closed (mode == 'REPLAY') → run the off-hours feed."""
        return self.session.mode(when) == "REPLAY"

    def run(self, on_bar: Callable[[pd.DataFrame, dict], object], *,
            max_bars: int | None = None) -> dict:
        """Drive ``on_bar(window_df, bar)`` over the replay; return a summary dict."""
        count = 0
        for step in self.replay.stream():
            window = self.replay.window(step["index"])   # causal: iloc[:i+1]
            on_bar(window, step["bar"])
            count += 1
            if max_bars is not None and count >= max_bars:
                break
        self._bars_replayed = count
        return {"bars_replayed": count, "market": self.market,
                "mode": self.session.mode()}

    def status(self, when: datetime | None = None) -> dict:
        return {"engine": "ReplaySession", "market": self.market,
                "mode": self.session.mode(when), "should_replay": self.should_replay(when),
                "bars_replayed": int(self._bars_replayed),
                "feed": self.replay.status()}
