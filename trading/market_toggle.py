"""trading/market_toggle.py — NSE master on/off switch (T1 §7).

Hard contract: when the master toggle is OFF there is ZERO activity — no tick
polling, no WebSocket, no orders. Turning it ON starts the live feed; turning it
OFF stops the feed completely. State is persisted so a restart restores the last
chosen position (defaulting to OFF — safe by default).

The toggle also acts as an order guard: order dispatch must check `assert_on()`
so nothing fires while the market is switched off.
"""
from __future__ import annotations

from typing import Callable

from trading import state

_TOGGLE_FILE = "market_toggle.json"


class MarketOff(RuntimeError):
    """Raised when an action is attempted while the master toggle is OFF."""


class MasterToggle:
    """On/off switch for a market (e.g. 'NSE'), with start/stop side effects."""

    def __init__(
        self,
        market: str = "NSE",
        on_start: Callable[[], None] | None = None,
        on_stop: Callable[[], None] | None = None,
    ):
        self.market = market.upper()
        self._on_start = on_start
        self._on_stop = on_stop
        persisted = state.load_json(_TOGGLE_FILE, {})
        # Safe default: OFF unless explicitly persisted ON.
        self._on = bool(persisted.get(self.market, False))

    @property
    def is_on(self) -> bool:
        return self._on

    def turn_on(self) -> bool:
        """Switch ON and start the feed. Returns True if state changed."""
        if self._on:
            return False
        self._on = True
        self._persist()
        if self._on_start:
            self._on_start()
        return True

    def turn_off(self) -> bool:
        """Switch OFF and stop ALL activity. Returns True if state changed."""
        if not self._on:
            return False
        self._on = False
        self._persist()
        if self._on_stop:
            self._on_stop()
        return True

    def set(self, on: bool) -> bool:
        return self.turn_on() if on else self.turn_off()

    def assert_on(self) -> None:
        """Guard: raise MarketOff if the market is switched off."""
        if not self._on:
            raise MarketOff(f"{self.market} master toggle is OFF — no activity allowed.")

    def _persist(self) -> None:
        data = state.load_json(_TOGGLE_FILE, {})
        if not isinstance(data, dict):
            data = {}
        data[self.market] = self._on
        state.save_json(_TOGGLE_FILE, data)
