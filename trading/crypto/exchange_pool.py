"""trading/crypto/exchange_pool.py — multi-venue market-DATA pool (ban-proofing).

Round-robins every public crypto data read (ticker / order book / funding rate)
across several exchanges' PUBLIC ccxt endpoints — Binance, Bybit, OKX, KuCoin —
with a hard per-venue token-bucket budget and automatic failover, so no single
venue ever carries all four segments' data load again (Binance IP-banned the VM
with 418/-1003 on 2026-07-03; see research/multi-venue-data-pool.md).

DATA PLANE ONLY. Live order execution stays on the configured exchange
(Binance/Bybit) — this pool never places orders and never uses API keys.

Guarantees by construction:
  • a venue is never called above its budget (default 60 req/min, far under every
    venue's public limit) — out-of-budget venues are skipped, not queued;
  • 418/429/"banned"/-1003 style responses put the venue in exponential cooldown;
  • a symbol missing on a venue skips that venue (markets cached per venue);
  • same unified-ccxt return shapes as ExchangeClient (linear perps BASE/QUOTE:QUOTE).
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

# venue rotation per ccxt defaultType — kucoin derivatives are a SEPARATE ccxt id.
_POOL_VENUES = {
    "spot": ["binance", "bybit", "okx", "kucoin"],
    "swap": ["binance", "bybit", "okx", "kucoinfutures"],
    "future": ["binance", "bybit", "okx", "kucoinfutures"],
}
_BUDGET_PER_MIN = float(os.getenv("VENUE_BUDGET_PER_MIN", "60"))
_BAN_MARKERS = ("418", "429", "-1003", "banned", "too many", "rate limit", "ratelimit")


class _TokenBucket:
    """Hard per-venue request budget: capacity == refill/min == _BUDGET_PER_MIN."""

    def __init__(self, per_min: float = _BUDGET_PER_MIN):
        self.capacity = per_min
        self.tokens = per_min
        self.rate = per_min / 60.0          # tokens per second
        self.ts = time.monotonic()
        self.lock = threading.Lock()

    def take(self) -> bool:
        with self.lock:
            now = time.monotonic()
            self.tokens = min(self.capacity, self.tokens + (now - self.ts) * self.rate)
            self.ts = now
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return True
            return False


class _Venue:
    def __init__(self, name: str, default_type: str):
        self.name = name
        self.default_type = default_type
        self.bucket = _TokenBucket()
        self.cooldown_until = 0.0
        self.cooldown_s = 60.0              # doubles per ban-marker error, caps at 1h
        self.errors = 0
        self.calls = 0
        self._ex: Any | None = None
        self._markets: dict | None = None
        self._lock = threading.Lock()

    def client(self) -> Any:
        with self._lock:
            if self._ex is None:
                import ccxt  # type: ignore
                self._ex = getattr(ccxt, self.name)({
                    "enableRateLimit": True,          # ccxt's own throttle stays on top
                    "timeout": 15000,
                    "options": {"defaultType": self.default_type},
                })
            return self._ex

    def markets(self) -> dict:
        if self._markets is None:
            self._markets = self.client().load_markets()
        return self._markets

    def cooling(self) -> bool:
        return time.monotonic() < self.cooldown_until

    def punish(self, exc: Exception) -> None:
        self.errors += 1
        msg = str(exc).lower()
        if any(m in msg for m in _BAN_MARKERS):
            self.cooldown_until = time.monotonic() + self.cooldown_s
            self.cooldown_s = min(self.cooldown_s * 2, 3600.0)
        else:                                # transient (timeout/5xx): brief backoff
            self.cooldown_until = time.monotonic() + 5.0

    def reward(self) -> None:
        self.calls += 1
        self.cooldown_s = 60.0               # healthy call resets the ban backoff


class ExchangePool:
    """Round-robin + budget + failover over the public venues for ONE market type."""

    def __init__(self, market_type: str = "swap", quote: str = "USDT",
                 preferred: str | None = None):
        default_type = {"spot": "spot", "swap": "swap", "future": "future"}.get(
            market_type, "swap")
        names = list(_POOL_VENUES.get(market_type, _POOL_VENUES["swap"]))
        if preferred and preferred in names:  # keep the execution venue first in rotation
            names.remove(preferred)
            names.insert(0, preferred)
        self.market_type = market_type
        self.quote = quote
        self.venues = [_Venue(n, default_type) for n in names]
        self._rr = 0
        self._rr_lock = threading.Lock()

    # ── symbol helpers ─────────────────────────────────────────────────────────
    def _norm(self, symbol: str) -> str:
        if self.market_type in ("swap", "future") and ":" not in symbol and "/" in symbol:
            return f"{symbol}:{self.quote}"
        return symbol

    def _has_symbol(self, v: _Venue, symbol: str) -> bool:
        try:
            return symbol in v.markets()
        except Exception as exc:             # markets load failed → treat as unavailable
            v.punish(exc)
            return False

    # ── core dispatch ──────────────────────────────────────────────────────────
    def _call(self, method: str, symbol: str, *args) -> dict:
        sym = self._norm(symbol)
        with self._rr_lock:
            start = self._rr
            self._rr = (self._rr + 1) % len(self.venues)
        last_exc: Exception | None = None
        for i in range(len(self.venues)):
            v = self.venues[(start + i) % len(self.venues)]
            if v.cooling() or not v.bucket.take():
                continue
            if not self._has_symbol(v, sym):
                continue
            try:
                out = getattr(v.client(), method)(sym, *args)
                v.reward()
                return out
            except Exception as exc:         # noqa: BLE001 — venue failover by design
                v.punish(exc)
                last_exc = exc
        raise RuntimeError(
            f"all venues failed/out-of-budget for {method}({symbol}): {last_exc}")

    # ── public data API (mirrors ExchangeClient shapes) ────────────────────────
    def ticker(self, symbol: str) -> dict:
        return self._call("fetch_ticker", symbol)

    def order_book(self, symbol: str, limit: int = 50) -> dict:
        return self._call("fetch_order_book", symbol, limit)

    def funding_rate(self, symbol: str) -> dict:
        # funding exists only on derivatives venues; spot pools raise cleanly.
        return self._call("fetch_funding_rate", symbol)

    def ohlcv(self, symbol: str, timeframe: str = "5m", limit: int = 200) -> list:
        return self._call("fetch_ohlcv", symbol, timeframe, None, limit)

    def status(self) -> dict:
        """Honest per-venue health for the dashboard (calls/errors/cooldown/budget/ban-backoff)."""
        now = time.monotonic()
        venues = []
        for v in self.venues:
            cooling = v.cooling()
            venues.append({
                "name": v.name,
                "calls": v.calls,
                "errors": v.errors,
                "cooling": cooling,
                "cooldown_remaining": round(max(0.0, v.cooldown_until - now), 1) if cooling else 0.0,
                "backoff_s": round(v.cooldown_s, 1),        # doubles per ban-marker; >60 = getting banned
                "budget_left": round(v.bucket.tokens, 1),
                "budget_cap": round(v.bucket.capacity, 1),
                "status": ("banned" if cooling and v.cooldown_s > 120 else
                           "cooling" if cooling else
                           "active" if v.calls > 0 else "idle"),
            })
        return {"market_type": self.market_type, "venues": venues}


def all_pools_status() -> dict:
    """Status of every pool that ALREADY EXISTS (never constructs a new one — cheap, read-only).
    This is what the dashboard's Exchange-Data-Venues panel reads to show the ban-proof pool
    working: which venues are serving market data, their budgets, and any ban cooldowns."""
    with _POOLS_LOCK:
        pools = list(_POOLS.values())
    return {"enabled": pool_enabled(),
            "pools": [p.status() for p in pools]}


# ── shared pools (one per market type; reuse == shared rate limiter, per ccxt docs) ──
_POOLS: dict[str, ExchangePool] = {}
_POOLS_LOCK = threading.Lock()


def get_pool(market_type: str = "swap", quote: str = "USDT",
             preferred: str | None = None) -> ExchangePool:
    key = f"{market_type}:{quote}"
    with _POOLS_LOCK:
        p = _POOLS.get(key)
        if p is None:
            p = _POOLS[key] = ExchangePool(market_type, quote, preferred)
        return p


def pool_enabled() -> bool:
    """Env kill-switch (MULTI_VENUE_POOL=0 reverts to single-exchange reads)."""
    return os.getenv("MULTI_VENUE_POOL", "1").lower() not in ("0", "false", "off")
