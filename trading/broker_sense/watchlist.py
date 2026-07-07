"""trading/broker_sense/watchlist.py — hot watchlist with TTL (saver E).

A symbol the screeners surface stays "hot" for K bars; only HOT symbols get candle
screenshots + book monitoring; cold symbols drop out automatically. This bounds — by
construction — how many symbols the expensive vision stages ever touch, no matter how
noisy the screeners get. Open positions are pinned hot (exits must always be managed).
"""
from __future__ import annotations

import time

from trading import state

_FILE = "broker_sense_watchlist.json"
_BAR_S = 300                                    # heat is measured in 5m bars


class HotWatchlist:
    def __init__(self, *, ttl_bars: int = 6, max_hot: int = 40, market: str | None = None):
        # PER-MARKET file (bugfix 2026-07-06): crypto cycles constantly and floods a shared
        # watchlist, evicting every NSE symbol (max_hot cap) → the NSE lane only ever saw crypto
        # pairs OpenAlgo couldn't resolve → non_neutral=0 forever. Namespacing by market fixes it.
        self.market = market
        self._file = f"broker_sense_watchlist_{market}.json" if market else _FILE
        self.ttl_bars = ttl_bars
        self.max_hot = max_hot
        self.data: dict = state.load_json(self._file, {})   # sym -> {last_seen_bar, hits, pinned}

    @staticmethod
    def _bar() -> int:
        return int(time.time() // _BAR_S)

    def touch(self, symbol: str, *, score: float = 0.0) -> None:
        d = self.data.setdefault(symbol, {"hits": 0, "score": 0.0})
        d["last_seen_bar"] = self._bar()
        d["hits"] = d.get("hits", 0) + 1
        d["score"] = max(float(d.get("score", 0)), abs(score))

    def pin(self, symbol: str) -> None:
        """Open positions stay hot regardless of TTL."""
        self.touch(symbol)
        self.data[symbol]["pinned"] = True

    def unpin(self, symbol: str) -> None:
        if symbol in self.data:
            self.data[symbol].pop("pinned", None)

    def hot(self) -> list[str]:
        """Current hot set, hottest first, hard-capped at max_hot (saver E bound)."""
        bar = self._bar()
        alive = {s: d for s, d in self.data.items()
                 if d.get("pinned") or bar - d.get("last_seen_bar", 0) <= self.ttl_bars}
        self.data = alive
        state.save_json(self._file, self.data)
        ranked = sorted(alive, key=lambda s: (not alive[s].get("pinned"),
                                              -alive[s].get("score", 0),
                                              -alive[s].get("hits", 0)))
        return ranked[: self.max_hot]

    def status(self) -> dict:
        return {"ttl_bars": self.ttl_bars, "max_hot": self.max_hot,
                "n_tracked": len(self.data),
                "hot": self.hot()[:20]}
