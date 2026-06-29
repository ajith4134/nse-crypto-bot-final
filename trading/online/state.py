"""trading/online/state.py — per-market state + central trading-state gate (O1).

Independent per-market control + a single safety choke-point in front of execution
(research: online-market-toggles-paper-real-switch). Each market is a `MarketState`
{enabled, mode (PAPER/REAL), allow_live, trading_state}; the `TradingStateGate` decides
whether any given order may be sent.

Trading state (NautilusTrader model):
  ACTIVE   — normal trading
  REDUCING — only position-reducing orders (graceful de-risk)
  HALTED   — deny everything except cancels (the kill-switch state)

Safety: REAL mode requires an explicit `allow_live` AND a deliberate confirmed switch;
PAPER is the default. State persists (trading.state) so toggles survive restart, but the
runtime HALT is re-applied conservatively. Honest + secrets-free.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from trading import state as _state

_STATE_FILE = "online_markets.json"


class TradingState(str, Enum):
    ACTIVE = "ACTIVE"
    REDUCING = "REDUCING"
    HALTED = "HALTED"


# Selectable trade-type SEGMENTS per market — only SELECTED segments are traded.
SEGMENTS = {
    "NSE": ["intraday", "mtf", "fno", "commodities"],   # MIS · MTF · F&O · MCX
    "CRYPTO": ["spot", "futures", "options"],            # spot · USDⓢ-M perp · options
}
_DEFAULT_SEGMENTS = {"NSE": ["intraday"], "CRYPTO": ["spot"]}   # safe minimal default


@dataclass
class MarketState:
    market: str
    enabled: bool = False                 # off by default — safe
    mode: str = "PAPER"                   # PAPER | REAL
    allow_live: bool = False              # must be True to ever send REAL
    trading_state: TradingState = TradingState.ACTIVE
    segments: list = None                 # selected trade-types; None → market default

    def __post_init__(self) -> None:
        self.market = self.market.upper()
        self.mode = self.mode.upper()
        if isinstance(self.trading_state, str):
            self.trading_state = TradingState(self.trading_state)
        valid = SEGMENTS.get(self.market, [])
        if self.segments is None:
            self.segments = list(_DEFAULT_SEGMENTS.get(self.market, valid[:1]))
        else:                              # keep only valid segments for this market
            self.segments = [s for s in self.segments if s in valid]

    # ── segment selection (the trade-type buttons) ──────────────────────────────
    def set_segments(self, segs: list) -> "MarketState":
        valid = SEGMENTS.get(self.market, [])
        self.segments = [s for s in segs if s in valid]
        return self

    def toggle_segment(self, seg: str) -> "MarketState":
        seg = seg.lower()
        if seg not in SEGMENTS.get(self.market, []):
            return self
        if seg in self.segments:
            self.segments = [s for s in self.segments if s != seg]
        else:
            self.segments = self.segments + [seg]
        return self

    def has_segment(self, seg: str) -> bool:
        return seg.lower() in self.segments

    # ── toggles ─────────────────────────────────────────────────────────────────
    def enable(self) -> "MarketState":
        self.enabled = True
        return self

    def disable(self) -> "MarketState":
        self.enabled = False
        return self

    def set_mode(self, mode: str, *, confirm: bool = False) -> dict:
        """Switch PAPER↔REAL. REAL requires allow_live AND confirm=True (deliberate)."""
        mode = mode.upper()
        if mode not in ("PAPER", "REAL"):
            return {"ok": False, "reason": f"bad mode {mode!r}"}
        if mode == "REAL":
            if not self.allow_live:
                return {"ok": False, "reason": "allow_live is False — real trading disabled"}
            if not confirm:
                return {"ok": False, "reason": "REAL switch needs confirm=True (2-step)"}
        self.mode = mode
        return {"ok": True, "mode": self.mode}

    def set_state(self, ts: TradingState | str) -> "MarketState":
        self.trading_state = TradingState(ts) if isinstance(ts, str) else ts
        return self

    @property
    def is_real(self) -> bool:
        return self.mode == "REAL"

    def as_dict(self) -> dict:
        return {"market": self.market, "enabled": self.enabled, "mode": self.mode,
                "allow_live": self.allow_live, "trading_state": self.trading_state.value,
                "is_real": self.is_real, "segments": list(self.segments),
                "available_segments": SEGMENTS.get(self.market, [])}


class TradingStateGate:
    """The single check every order passes before it can be sent."""

    @staticmethod
    def allow_order(ms: MarketState, *, reduces_position: bool = False,
                    is_real: bool | None = None) -> dict:
        """Return {ok, reason, would_be_real}. ok=False blocks the order."""
        is_real = ms.is_real if is_real is None else is_real
        if not ms.enabled:
            return {"ok": False, "reason": f"{ms.market} disabled"}
        if ms.trading_state == TradingState.HALTED:
            return {"ok": False, "reason": "HALTED (kill-switch)"}
        if ms.trading_state == TradingState.REDUCING and not reduces_position:
            return {"ok": False, "reason": "REDUCING: only position-reducing orders allowed"}
        if is_real and not ms.allow_live:
            return {"ok": False, "reason": "real order but allow_live is False"}
        return {"ok": True, "reason": "allowed", "would_be_real": bool(is_real and ms.is_real)}


@dataclass
class MarketRegistry:
    """Holds + persists per-market state for NSE + CRYPTO (and any others)."""
    markets: dict = field(default_factory=dict)
    persist: bool = True

    def __post_init__(self) -> None:
        if not self.markets:
            self.markets = {"NSE": MarketState("NSE"), "CRYPTO": MarketState("CRYPTO")}
        if self.persist:
            self._load()

    def _load(self) -> None:
        data = _state.load_json(_STATE_FILE, {})
        if isinstance(data, dict):
            for m, d in data.items():
                if isinstance(d, dict):
                    self.markets[m.upper()] = MarketState(
                        market=m, enabled=d.get("enabled", False), mode=d.get("mode", "PAPER"),
                        allow_live=d.get("allow_live", False),
                        trading_state=d.get("trading_state", "ACTIVE"),
                        segments=d.get("segments"))

    def save(self) -> None:
        if self.persist:
            _state.save_json(_STATE_FILE, {m: s.as_dict() for m, s in self.markets.items()})

    def get(self, market: str) -> MarketState:
        return self.markets.setdefault(market.upper(), MarketState(market))

    def allow_order(self, market: str, **kw) -> dict:
        return TradingStateGate.allow_order(self.get(market), **kw)

    def halt_all(self) -> None:
        for s in self.markets.values():
            s.set_state(TradingState.HALTED)
        self.save()

    def status(self) -> dict:
        return {"markets": {m: s.as_dict() for m, s in self.markets.items()}}
