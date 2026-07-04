"""CORTEX B5 — SimLab: a psychology-free order-matching market environment (KRF-06/13).

KRF's premise (CANON-59): chart patterns are order-book/liquidity mechanics, not trader
psychology — so a purely mechanical order-matching simulator still produces gaps and
patterns and is a valid training/test environment. SimLab wraps the `order_matching`
engine to turn a stream of limit orders into executed trades and a synthetic mid-price
path the evolution lane (and any node) can train against, with NO behavioural model.

`hftbacktest` (installed) is the heavier path for real L2 replay; SimLab exposes
`HAS_HFTBACKTEST` so a future L2 lane can opt in. The default engine is dependency-light
and deterministic given a seed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

import numpy as np

try:
    from order_matching.matching_engine import MatchingEngine
    from order_matching.order import LimitOrder
    from order_matching.orders import Orders
    from order_matching.side import Side
    _HAS_OM = True
except Exception:                                                    # pragma: no cover
    _HAS_OM = False

try:
    import hftbacktest  # noqa: F401
    HAS_HFTBACKTEST = True
except Exception:                                                    # pragma: no cover
    HAS_HFTBACKTEST = False

__all__ = ["SimLab", "SimResult", "HAS_HFTBACKTEST"]

_EPOCH = datetime(2024, 1, 1)


@dataclass
class SimResult:
    mid: np.ndarray            # synthetic mid-price path (one per step)
    trade_price: np.ndarray    # last executed trade price per step (NaN if no trade)
    volume: np.ndarray         # matched size per step
    n_trades: int


class SimLab:
    """Mechanical limit-order-book simulator producing a psychology-free price path.

    At each step a small cloud of buy/sell limit orders is placed around the current
    mid at seeded-random offsets and matched. The mid is nudged by net executed
    imbalance — gaps and runs emerge from matching alone, no sentiment.
    """

    def __init__(self, *, start_price: float = 100.0, n_agents: int = 12,
                 spread: float = 0.5, tick_vol: float = 0.4, seed: int = 0):
        self.start_price = float(start_price)
        self.n_agents = int(n_agents)
        self.spread = float(spread)
        self.tick_vol = float(tick_vol)
        self._rng = np.random.default_rng(seed)

    # -- public --------------------------------------------------------------
    def run(self, steps: int = 256) -> SimResult:
        """Run `steps` matching rounds. Uses order_matching if available, else a
        self-contained numpy crossing book (identical semantics, no dependency)."""
        if _HAS_OM:
            try:
                return self._run_order_matching(steps)
            except Exception:                                        # pragma: no cover
                pass
        return self._run_numpy(steps)

    def price_series(self, steps: int = 256) -> np.ndarray:
        """Convenience: just the mid-price path (what NeatLane trains on)."""
        return self.run(steps).mid

    # -- backends ------------------------------------------------------------
    def _quotes(self, mid: float):
        """Seeded cloud of (side, price, size) around mid."""
        out = []
        for _ in range(self.n_agents):
            buy = self._rng.random() < 0.5
            off = abs(self._rng.normal(0.0, self.spread))
            price = round(mid - off if buy else mid + off, 1)
            size = float(abs(self._rng.normal(1.0, 0.3)) + 0.1)
            out.append((buy, price, size))
        return out

    def _run_order_matching(self, steps: int) -> SimResult:
        engine = MatchingEngine(seed=int(self._rng.integers(0, 2**31 - 1)))
        mid = self.start_price
        mids, tps, vols = [], [], []
        oid = 0
        for t in range(steps):
            ts = _EPOCH + timedelta(seconds=t)
            order_list = []
            for buy, price, size in self._quotes(mid):
                oid += 1
                order_list.append(LimitOrder(
                    side=Side.BUY if buy else Side.SELL, price=price, size=size,
                    timestamp=ts, order_id=str(oid), trader_id=str(oid % self.n_agents)))
            trades = engine.match(timestamp=ts, orders=Orders(order_list))
            px, vol = self._summarise_trades(trades)
            mid = px if px == px else mid + self._rng.normal(0, self.tick_vol)   # px==px: not NaN
            mids.append(mid); tps.append(px); vols.append(vol)
        return SimResult(np.array(mids), np.array(tps), np.array(vols),
                         int(np.sum(np.array(vols) > 0)))

    @staticmethod
    def _summarise_trades(trades) -> tuple[float, float]:
        """Reduce an ExecutedTrades object to (last_price, total_size). Robust to the
        exact attribute layout across order_matching versions."""
        recs = getattr(trades, "trades", None)
        if recs is None:
            recs = list(trades) if hasattr(trades, "__iter__") else []
        last_px, vol = float("nan"), 0.0
        for tr in recs:
            price = getattr(tr, "price", None)
            size = getattr(tr, "size", 0.0) or 0.0
            if price is not None:
                last_px = float(price); vol += float(size)
        return last_px, vol

    def _run_numpy(self, steps: int) -> SimResult:
        """Dependency-free crossing book: match best bids >= best asks each round."""
        mid = self.start_price
        mids, tps, vols = [], [], []
        for _ in range(steps):
            bids, asks = [], []
            for buy, price, size in self._quotes(mid):
                (bids if buy else asks).append((price, size))
            bids.sort(reverse=True); asks.sort()
            vol = 0.0; last_px = float("nan"); bi = ai = 0
            while bi < len(bids) and ai < len(asks) and bids[bi][0] >= asks[ai][0]:
                q = min(bids[bi][1], asks[ai][1])
                last_px = (bids[bi][0] + asks[ai][0]) / 2.0
                vol += q
                bids[bi] = (bids[bi][0], bids[bi][1] - q)
                asks[ai] = (asks[ai][0], asks[ai][1] - q)
                if bids[bi][1] <= 1e-9: bi += 1
                if asks[ai][1] <= 1e-9: ai += 1
            mid = last_px if last_px == last_px else mid + self._rng.normal(0, self.tick_vol)
            mids.append(mid); tps.append(last_px); vols.append(vol)
        return SimResult(np.array(mids), np.array(tps), np.array(vols),
                         int(np.sum(np.array(vols) > 0)))
