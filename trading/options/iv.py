"""trading/options/iv.py — IV Rank + IV Percentile (T4 §4 of features list).

Two distinct, often-confused measures of "is implied vol high right now?":

  IV Rank       = (IV_now − IV_low) / (IV_high − IV_low) × 100
                  where high/low are over the lookback (default 252 trading days
                  ≈ 52 weeks). Pure range position; one spike skews it.
  IV Percentile = % of observations in the lookback that were BELOW IV_now × 100.
                  Distribution-aware; robust to a single outlier.

`IVHistory` keeps a rolling window (deque) of daily ATM IVs so both update in O(1).
Pure Python, deterministic. The implied-vol numbers themselves come from
trading.options.greeks.implied_vol on the live chain.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


def iv_rank(current: float, history: list[float], *, lookback: int = 252) -> float | None:
    """IV Rank in [0,100], or None if there isn't a non-degenerate range."""
    window = list(history)[-lookback:]
    if not window:
        return None
    lo, hi = min(window), max(window)
    if hi - lo <= 1e-12:
        return None
    return max(0.0, min(100.0, (current - lo) / (hi - lo) * 100.0))


def iv_percentile(current: float, history: list[float], *, lookback: int = 252) -> float | None:
    """IV Percentile in [0,100]: fraction of lookback observations below `current`."""
    window = list(history)[-lookback:]
    if not window:
        return None
    below = sum(1 for v in window if v < current)
    return below / len(window) * 100.0


@dataclass
class IVHistory:
    """Rolling daily-ATM-IV window feeding IV Rank / Percentile."""

    lookback: int = 252
    _values: deque = field(default_factory=deque, init=False)

    def __post_init__(self) -> None:
        if self.lookback < 1:
            raise ValueError("lookback must be >= 1")
        self._values = deque(maxlen=self.lookback)

    def push(self, iv: float) -> "IVHistory":
        if iv < 0:
            raise ValueError("iv must be >= 0")
        self._values.append(float(iv))
        return self

    def extend(self, ivs: list[float]) -> "IVHistory":
        for v in ivs:
            self.push(v)
        return self

    @property
    def values(self) -> list[float]:
        return list(self._values)

    def rank(self, current: float | None = None) -> float | None:
        cur = self._values[-1] if current is None and self._values else current
        return None if cur is None else iv_rank(cur, self.values, lookback=self.lookback)

    def percentile(self, current: float | None = None) -> float | None:
        cur = self._values[-1] if current is None and self._values else current
        return None if cur is None else iv_percentile(cur, self.values, lookback=self.lookback)

    def as_dict(self) -> dict:
        cur = self._values[-1] if self._values else None
        return {
            "n": len(self._values), "lookback": self.lookback, "current": cur,
            "low": min(self._values) if self._values else None,
            "high": max(self._values) if self._values else None,
            "iv_rank": self.rank(), "iv_percentile": self.percentile(),
        }
