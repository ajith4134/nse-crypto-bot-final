"""trading/execution/trailing.py — trailing-stop strategies (T3 §3, §4, §5).

All stops here are CLIENT-SIDE: in live trading they run in a WebSocket tick loop
(not as a resting broker stop), which is what lets us trail exponentially and use
ATR/SAR/Chandelier logic the broker can't express. Each strategy is a small state
machine fed bars and returning the current stop level; the stop RATCHETS — it only
ever moves in the favourable direction (up for longs, down for shorts), never giving
back ground. `exit_triggered(price)` says when price has touched/breached the stop.

Bar inputs are (high, low, close). Price-only callers pass the same value three
times. Pure Python, deterministic — no network, fully unit-testable.

Strategies:
  ExponentialTrailingStop — trail distance SHRINKS as profit grows (locks faster).
  ATRTrailingStop         — stop = close ∓ mult·ATR (volatility-scaled).
  ChandelierExit          — stop = extreme-since-entry ∓ mult·ATR.
  ParabolicSAR            — classic Wilder SAR dots.
  ProfitLockTrailing      — wrapper: hold initial stop until +X%, then jump to
                            breakeven and hand off to an inner trailing strategy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field


def _is_long(side: str) -> bool:
    s = side.lower()
    if s in ("long", "buy", "b"):
        return True
    if s in ("short", "sell", "s"):
        return False
    raise ValueError(f"unknown side: {side!r}")


class WilderATR:
    """Incremental Wilder Average True Range. Feed (high, low, close) per bar."""

    def __init__(self, period: int = 14):
        if period < 1:
            raise ValueError("period must be >= 1")
        self.period = period
        self.atr: float | None = None
        self._prev_close: float | None = None
        self._seed: list[float] = []

    def update(self, high: float, low: float, close: float) -> float:
        if self._prev_close is None:
            tr = high - low
        else:
            tr = max(high - low, abs(high - self._prev_close), abs(low - self._prev_close))
        self._prev_close = close
        if self.atr is None:
            self._seed.append(tr)
            # provisional simple average until we have `period` bars
            self.atr = sum(self._seed) / len(self._seed)
            if len(self._seed) >= self.period:
                self.atr = sum(self._seed) / self.period
        else:
            self.atr = (self.atr * (self.period - 1) + tr) / self.period
        return self.atr


class TrailingStop:
    """Base: ratchet logic + exit test shared by every concrete strategy."""

    def __init__(self, side: str, entry_price: float):
        self.long = _is_long(side)
        self.entry_price = float(entry_price)
        self.stop: float | None = None

    def _ratchet(self, candidate: float) -> float:
        """Move the stop only in the favourable direction; return the live stop."""
        if self.stop is None:
            self.stop = candidate
        elif self.long:
            self.stop = max(self.stop, candidate)
        else:
            self.stop = min(self.stop, candidate)
        return self.stop

    def exit_triggered(self, price: float) -> bool:
        if self.stop is None:
            return False
        return price <= self.stop if self.long else price >= self.stop

    # subclasses implement update(high, low, close) -> float (the live stop)
    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        raise NotImplementedError


class ExponentialTrailingStop(TrailingStop):
    """Trail distance shrinks as open profit grows → SL accelerates toward price.

    distance_frac(profit) = clamp(base_frac · exp(-k · profit_frac), floor, base)
    Stop is trailed from the favourable extreme (peak for long, trough for short):
        long  stop = peak  · (1 - distance_frac)
        short stop = trough · (1 + distance_frac)
    With k=0 this is a plain percentage trailing stop.
    """

    def __init__(self, side: str, entry_price: float, *, base_frac: float = 0.03,
                 floor_frac: float = 0.004, k: float = 8.0):
        super().__init__(side, entry_price)
        if not (0 < floor_frac <= base_frac):
            raise ValueError("require 0 < floor_frac <= base_frac")
        self.base_frac = base_frac
        self.floor_frac = floor_frac
        self.k = k
        self._extreme = entry_price

    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        price = high if close is None else close
        peak_px = high if (close is None) else max(high, close)
        trough_px = low if (low is not None) else price
        if self.long:
            self._extreme = max(self._extreme, peak_px)
            profit_frac = max(0.0, (self._extreme - self.entry_price) / self.entry_price)
        else:
            self._extreme = min(self._extreme, trough_px if low is not None else price)
            profit_frac = max(0.0, (self.entry_price - self._extreme) / self.entry_price)
        dist = self.base_frac * math.exp(-self.k * profit_frac)
        dist = min(self.base_frac, max(self.floor_frac, dist))
        candidate = (self._extreme * (1 - dist)) if self.long else (self._extreme * (1 + dist))
        return self._ratchet(candidate)


class ATRTrailingStop(TrailingStop):
    """Volatility-scaled stop: stop = close ∓ mult · ATR (Wilder)."""

    def __init__(self, side: str, entry_price: float, *, period: int = 14, mult: float = 3.0,
                 atr: WilderATR | None = None):
        super().__init__(side, entry_price)
        self.mult = mult
        self.atr = atr or WilderATR(period)

    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        if low is None or close is None:        # price-only feed
            low = close = high
        a = self.atr.update(high, low, close)
        candidate = (close - self.mult * a) if self.long else (close + self.mult * a)
        return self._ratchet(candidate)


class ChandelierExit(TrailingStop):
    """Chandelier Exit: stop hangs mult·ATR off the extreme reached since entry.

        long  stop = highest_high_since_entry - mult · ATR
        short stop = lowest_low_since_entry   + mult · ATR
    """

    def __init__(self, side: str, entry_price: float, *, period: int = 22, mult: float = 3.0,
                 atr: WilderATR | None = None):
        super().__init__(side, entry_price)
        self.mult = mult
        self.atr = atr or WilderATR(period)
        self._extreme = entry_price

    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        if low is None or close is None:
            low = close = high
        a = self.atr.update(high, low, close)
        if self.long:
            self._extreme = max(self._extreme, high)
            candidate = self._extreme - self.mult * a
        else:
            self._extreme = min(self._extreme, low)
            candidate = self._extreme + self.mult * a
        return self._ratchet(candidate)


class ParabolicSAR(TrailingStop):
    """Classic Wilder Parabolic SAR (acceleration factor steps from af0 to af_max).

    Unlike the others this stop can FLIP sides when SAR is crossed; on a flip it
    resets to the prior extreme and reverses `long`. `exit_triggered` reports the
    bar on which the active side's SAR was breached (i.e. the flip bar).
    """

    def __init__(self, side: str, entry_price: float, *, af0: float = 0.02,
                 af_step: float = 0.02, af_max: float = 0.2):
        super().__init__(side, entry_price)
        self.af0, self.af_step, self.af_max = af0, af_step, af_max
        self.af = af0
        self._ep = entry_price          # extreme point in the current trend
        self._sar = entry_price
        self.stop = entry_price
        self._flipped = False
        self._started = False

    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        if low is None or close is None:
            low = close = high
        self._flipped = False
        if not self._started:
            self._ep = high if self.long else low
            self._sar = self.entry_price
            self._started = True
            self.stop = self._sar
            return self._sar

        sar = self._sar + self.af * (self._ep - self._sar)
        if self.long:
            if low <= sar:             # breach → flip to short
                self.long = False
                sar = self._ep            # new SAR = prior extreme
                self._ep = low
                self.af = self.af0
                self._flipped = True
            else:
                if high > self._ep:
                    self._ep = high
                    self.af = min(self.af_max, self.af + self.af_step)
        else:
            if high >= sar:            # breach → flip to long
                self.long = True
                sar = self._ep
                self._ep = high
                self.af = self.af0
                self._flipped = True
            else:
                if low < self._ep:
                    self._ep = low
                    self.af = min(self.af_max, self.af + self.af_step)
        self._sar = sar
        self.stop = sar
        return sar

    def exit_triggered(self, price: float) -> bool:
        # SAR signals an exit on the bar it flips trend.
        return self._flipped


@dataclass
class ProfitLockTrailing:
    """Profit-lock wrapper (T3 §5): hold the initial stop until +X% open profit,
    then jump the stop to breakeven (entry) and delegate to an inner trailing
    strategy. Before the lock triggers, the stop stays at `initial_stop`.

    `inner` is any TrailingStop; if omitted, the stop simply locks at breakeven and
    then trails by the same percentage as the lock threshold.
    """

    side: str
    entry_price: float
    initial_stop: float
    lock_after_frac: float = 0.01          # +1% open profit arms the lock
    inner: TrailingStop | None = None

    stop: float = field(init=False)
    locked: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        self._long = _is_long(self.side)
        self.stop = self.initial_stop
        if self.inner is None:
            self.inner = ExponentialTrailingStop(
                self.side, self.entry_price,
                base_frac=self.lock_after_frac, floor_frac=self.lock_after_frac / 4, k=6.0,
            )

    def _profit_frac(self, price: float) -> float:
        if self._long:
            return (price - self.entry_price) / self.entry_price
        return (self.entry_price - price) / self.entry_price

    def update(self, high: float, low: float | None = None, close: float | None = None) -> float:
        price = high if close is None else close
        if not self.locked and self._profit_frac(price) >= self.lock_after_frac:
            self.locked = True
        if not self.locked:
            return self.stop                       # still risking the original stop
        inner_stop = self.inner.update(high, low, close)
        # Never let the locked stop fall below breakeven.
        be = self.entry_price
        candidate = max(inner_stop, be) if self._long else min(inner_stop, be)
        if self._long:
            self.stop = max(self.stop, candidate)
        else:
            self.stop = min(self.stop, candidate)
        return self.stop

    def exit_triggered(self, price: float) -> bool:
        return price <= self.stop if self._long else price >= self.stop
