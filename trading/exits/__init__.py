"""trading/exits/ — four separate trailing-exit components over one signed engine.

The operator wants FOUR visibly-distinct components (per direction × purpose), which
is exactly the honest split the ecosystem uses (see research/trailing-exit-systems.md):
ONE ratcheting trailing engine + a profit-offset gate + a side sign — NOT four
unrelated algorithms. Each component below is a thin, separately-named wrapper that
pre-configures the shared `TrailingEngine` for its direction and purpose:

    LongProfitTrail   long  trailing TAKE-PROFIT  ratchets UP,   armed after +offset
    LongStopTrail     long  trailing STOP-LOSS    ratchets UP,   armed from entry
    ShortProfitTrail  short trailing TAKE-PROFIT  ratchets DOWN, armed after +offset
    ShortLossTrail    short trailing STOP-LOSS    ratchets DOWN, armed from entry

Stop levels come from a chosen `mode`:
    "pct"        — peak-since-entry × (1 ∓ trail_pct)              (simple percentage)
    "atr"        — close ∓ atr_mult · ATR  (Wilder, volatility-scaled)
    "chandelier" — pandas_ta_classic.ce()  long/short stop column (extreme ∓ mult·ATR)
    "supertrend" — pandas_ta_classic.supertrend() long/short stop (trend-flip trail)

All CPU-first, offline, deterministic. `TrailingEngine.update()` is a per-tick state
machine returning {exit, stop, peak, reason}. Adaptive modes keep a small OHLC buffer
and recompute the indicator from pandas_ta_classic each tick (battle-tested stop math,
no reimplementation). Validated offline against vectorbt in tests/test_trailing_exits.py.
"""
from __future__ import annotations

from trading.execution.trailing import WilderATR, _is_long

__all__ = [
    "TrailingEngine",
    "LongProfitTrail",
    "LongStopTrail",
    "ShortProfitTrail",
    "ShortLossTrail",
    "make_exit",
    "status",
    "build_demo_trailing",
]

_VALID_MODES = ("pct", "atr", "chandelier", "supertrend")


class TrailingEngine:
    """Shared signed ratcheting core. Works long & short; trailing-TP vs trailing-SL
    is just a `profit_offset` gate (0 ⇒ armed from entry = stop-loss trail; >0 ⇒ arms
    only after that much open profit = take-profit trail).

    update(price, atr=, high=, low=) -> {exit, stop, peak, reason}. Price-only callers
    omit high/low (they default to price). The stop RATCHETS — it only ever moves in the
    favourable direction (up for longs, down for shorts), never giving back ground.
    """

    def __init__(self, *, mode: str, direction: str, trail_pct: float | None = None,
                 atr_mult: float | None = None, profit_offset: float = 0.0,
                 atr_period: int = 14, ind_length: int | None = None,
                 entry_price: float | None = None):
        if mode not in _VALID_MODES:
            raise ValueError(f"mode must be one of {_VALID_MODES}, got {mode!r}")
        self.mode = mode
        self.direction = "long" if _is_long(direction) else "short"
        self.long = self.direction == "long"
        self.trail_pct = 0.05 if trail_pct is None else float(trail_pct)
        self.atr_mult = 3.0 if atr_mult is None else float(atr_mult)
        self.profit_offset = float(profit_offset)
        self.atr_period = int(atr_period)
        # indicator window length (ce default 22, supertrend default 7)
        self.ind_length = int(ind_length) if ind_length is not None else (
            22 if mode == "chandelier" else 7)
        self.reset(entry_price if entry_price is not None else 0.0)

    # ------------------------------------------------------------------ state
    def reset(self, entry_price: float, *, profit_offset: float | None = None) -> None:
        """(Re)arm the engine for a fresh position at `entry_price`."""
        self.entry_price = float(entry_price)
        if profit_offset is not None:
            self.profit_offset = float(profit_offset)
        self.peak = self.entry_price          # favourable extreme since entry
        self.stop: float | None = None
        self.armed = self.profit_offset <= 0.0
        self.exited = False
        self._ohlc: list[tuple[float, float, float]] = []
        self._atr = WilderATR(self.atr_period)
        self._ticks = 0

    # ------------------------------------------------------------- math
    def _profit_frac(self, price: float) -> float:
        e = self.entry_price
        if e == 0:
            return 0.0
        return (price - e) / e if self.long else (e - price) / e

    def _stop_level(self, price: float, atr: float | None, hi: float, lo: float):
        """Candidate stop for the current bar (None ⇒ keep prior stop, e.g. warming up)."""
        if self.mode == "pct":
            return self.peak * (1 - self.trail_pct) if self.long else self.peak * (1 + self.trail_pct)
        if self.mode == "atr":
            a = atr if atr is not None else self._atr.update(hi, lo, price)
            if a is None:
                return None
            return price - self.atr_mult * a if self.long else price + self.atr_mult * a
        # adaptive indicator modes need an OHLC window from pandas_ta_classic
        return self._indicator_stop()

    def _indicator_stop(self):
        if len(self._ohlc) < max(self.ind_length + 1, 3):
            return None
        import pandas as pd
        import pandas_ta_classic as pta
        h = pd.Series([b[0] for b in self._ohlc], dtype=float)
        l = pd.Series([b[1] for b in self._ohlc], dtype=float)
        c = pd.Series([b[2] for b in self._ohlc], dtype=float)
        if self.mode == "chandelier":
            out = pta.ce(h, l, c, length=self.ind_length, multiplier=float(self.atr_mult))
            col = f"CE_L_{self.ind_length}_{float(self.atr_mult)}" if self.long \
                else f"CE_S_{self.ind_length}_{float(self.atr_mult)}"
            if out is None or col not in out.columns:
                return None
            series = out[col]
        else:  # supertrend
            out = pta.supertrend(h, l, c, length=self.ind_length, multiplier=self.atr_mult)
            col = f"SUPERTl_{self.ind_length}_{float(self.atr_mult)}" if self.long \
                else f"SUPERTs_{self.ind_length}_{float(self.atr_mult)}"
            if out is None or col not in out.columns:
                return None
            series = out[col]
        series = series.dropna()
        if series.empty:
            return None
        return float(series.iloc[-1])

    def _ratchet(self, candidate: float) -> None:
        if self.stop is None:
            self.stop = candidate
        elif self.long:
            self.stop = max(self.stop, candidate)
        else:
            self.stop = min(self.stop, candidate)

    # ------------------------------------------------------------- tick
    def update(self, price: float, *, atr: float | None = None,
               high: float | None = None, low: float | None = None) -> dict:
        price = float(price)
        hi = float(high) if high is not None else price
        lo = float(low) if low is not None else price
        self._ticks += 1
        self._ohlc.append((hi, lo, price))
        # warm the internal ATR even if this tick uses an external atr value
        if atr is None and self.mode == "atr":
            pass  # _stop_level updates it
        # favourable extreme
        self.peak = max(self.peak, hi) if self.long else min(self.peak, lo)
        # arming gate (profit-trail): once armed, stays armed
        if not self.armed and self._profit_frac(self.peak) >= self.profit_offset:
            self.armed = True
        if not self.armed:
            return {"exit": False, "stop": None, "peak": self.peak, "reason": "unarmed"}

        candidate = self._stop_level(price, atr, hi, lo)
        if candidate is not None:
            self._ratchet(candidate)
        if self.stop is None:
            return {"exit": False, "stop": None, "peak": self.peak, "reason": "warming"}

        breached = price <= self.stop if self.long else price >= self.stop
        if breached:
            self.exited = True
        return {
            "exit": bool(breached),
            "stop": self.stop,
            "peak": self.peak,
            "reason": "exit" if breached else "trailing",
        }

    # ------------------------------------------------------------- dashboard
    def status(self) -> dict:
        """Honest snapshot of this exit component's live state."""
        return {
            "component": type(self).__name__,
            "direction": self.direction,
            "mode": self.mode,
            "purpose": "take_profit" if self.profit_offset > 0 else "stop_loss",
            "entry": self.entry_price,
            "peak": self.peak,
            "stop": self.stop,
            "armed": self.armed,
            "exited": self.exited,
            "trail_pct": self.trail_pct if self.mode == "pct" else None,
            "atr_mult": self.atr_mult if self.mode in ("atr", "chandelier", "supertrend") else None,
            "profit_offset": self.profit_offset,
            "ticks": self._ticks,
        }


# ====================================================================== wrappers
class LongProfitTrail(TrailingEngine):
    """LONG trailing TAKE-PROFIT: arms only after +`profit_offset` open profit, then
    ratchets a stop UP under price to lock the gain."""

    def __init__(self, entry_price: float, *, mode: str = "pct", trail_pct: float | None = None,
                 atr_mult: float | None = None, profit_offset: float = 0.01, **kw):
        super().__init__(mode=mode, direction="long", trail_pct=trail_pct,
                         atr_mult=atr_mult, profit_offset=profit_offset,
                         entry_price=entry_price, **kw)


class LongStopTrail(TrailingEngine):
    """LONG trailing STOP-LOSS: armed from entry, stop follows price UP (pct/ATR/
    chandelier/supertrend), exit on the drop."""

    def __init__(self, entry_price: float, *, mode: str = "pct", trail_pct: float | None = None,
                 atr_mult: float | None = None, profit_offset: float = 0.0, **kw):
        super().__init__(mode=mode, direction="long", trail_pct=trail_pct,
                         atr_mult=atr_mult, profit_offset=profit_offset,
                         entry_price=entry_price, **kw)


class ShortProfitTrail(TrailingEngine):
    """SHORT trailing TAKE-PROFIT: arms after price falls `profit_offset` in our
    favour, then ratchets a stop DOWN above price to lock the gain."""

    def __init__(self, entry_price: float, *, mode: str = "pct", trail_pct: float | None = None,
                 atr_mult: float | None = None, profit_offset: float = 0.01, **kw):
        super().__init__(mode=mode, direction="short", trail_pct=trail_pct,
                         atr_mult=atr_mult, profit_offset=profit_offset,
                         entry_price=entry_price, **kw)


class ShortLossTrail(TrailingEngine):
    """SHORT trailing STOP-LOSS: armed from entry, stop follows price DOWN, exit on
    the rise."""

    def __init__(self, entry_price: float, *, mode: str = "pct", trail_pct: float | None = None,
                 atr_mult: float | None = None, profit_offset: float = 0.0, **kw):
        super().__init__(mode=mode, direction="short", trail_pct=trail_pct,
                         atr_mult=atr_mult, profit_offset=profit_offset,
                         entry_price=entry_price, **kw)


# ====================================================================== factory
_FACTORY = {
    ("long", "profit"): LongProfitTrail,
    ("long", "stop"): LongStopTrail,
    ("long", "loss"): LongStopTrail,
    ("short", "profit"): ShortProfitTrail,
    ("short", "stop"): ShortLossTrail,
    ("short", "loss"): ShortLossTrail,
}


def make_exit(direction: str, purpose: str, *, entry_price: float, **cfg):
    """Return the right trailing-exit wrapper for (direction, purpose).

    direction: long|buy|b | short|sell|s     purpose: profit | stop | loss
    Extra kwargs (mode, trail_pct, atr_mult, profit_offset, ...) pass through.
    """
    d = "long" if _is_long(direction) else "short"
    p = purpose.lower().strip()
    p = {"take_profit": "profit", "tp": "profit", "sl": "stop", "stop_loss": "stop"}.get(p, p)
    key = (d, p)
    if key not in _FACTORY:
        raise ValueError(f"unknown (direction, purpose)={key}; "
                         f"purpose must be profit|stop|loss")
    return _FACTORY[key](entry_price, **cfg)


# ====================================================================== dashboard
def status(engine: TrailingEngine) -> dict:
    """Module-level passthrough to engine.status() for dashboard symmetry."""
    return engine.status()


def build_demo_trailing() -> dict:
    """Deterministic, offline snapshot of all four components on synthetic paths —
    for the dashboard (mirrors run_*.build_demo_* convention). No network."""
    # rise-then-fall path for the long components
    up_then_down = [100, 102, 104, 106, 108, 110, 108, 106, 104, 102, 100]
    # fall-then-rise path for the short components
    down_then_up = [100, 98, 96, 94, 92, 90, 92, 94, 96, 98, 100]

    def run(engine, path):
        events = []
        exit_idx = None
        for i, px in enumerate(path):
            r = engine.update(px)
            if r["exit"] and exit_idx is None:
                exit_idx = i
            events.append(r)
        snap = engine.status()
        snap["exit_index"] = exit_idx
        snap["exit_price"] = path[exit_idx] if exit_idx is not None else None
        return snap

    comps = {
        "LongProfitTrail": run(LongProfitTrail(100, trail_pct=0.05, profit_offset=0.03), up_then_down),
        "LongStopTrail": run(LongStopTrail(100, trail_pct=0.05), up_then_down),
        "ShortProfitTrail": run(ShortProfitTrail(100, trail_pct=0.05, profit_offset=0.03), down_then_up),
        "ShortLossTrail": run(ShortLossTrail(100, trail_pct=0.05), down_then_up),
    }
    return {
        "module": "trading/exits",
        "engine": "TrailingEngine (signed ratchet + profit-offset gate)",
        "components": comps,
        "modes": list(_VALID_MODES),
        "note": "4 separate wrappers over 1 shared engine; pandas_ta_classic for "
                "adaptive stop levels; vectorbt-validated offline.",
    }
