"""Multi-venue market-data pool (trading/crypto/exchange_pool.py) — ban-proofing.

Budget/cooldown/failover are pure logic; tested with fake venues (no network).
Run: pytest tests/test_exchange_pool.py
"""
import tempfile
import time
from pathlib import Path

import trading.state as _state

_state.STATE_DIR = Path(tempfile.mkdtemp())  # isolate: never touch live state

from trading.crypto.exchange_pool import ExchangePool, _TokenBucket, _Venue  # noqa: E402


class _FakeCcxt:
    def __init__(self, name, fail=None):
        self.name, self.fail = name, fail
        self.calls = 0

    def load_markets(self):
        return {"BTC/USDT:USDT": {}}

    def fetch_ticker(self, sym, *a):
        self.calls += 1
        if self.fail:
            raise RuntimeError(self.fail)
        return {"symbol": sym, "last": 100.0, "venue": self.name}


def _pool(specs):
    """specs: [(name, fail_msg_or_None), ...] → pool with fake clients injected."""
    p = ExchangePool("swap")
    p.venues = []
    for name, fail in specs:
        v = _Venue(name, "swap")
        v._ex = _FakeCcxt(name, fail)
        v._markets = v._ex.load_markets()
        p.venues.append(v)
    return p


def test_round_robin_spreads_calls():
    p = _pool([("a", None), ("b", None), ("c", None)])
    for _ in range(6):
        p.ticker("BTC/USDT")
    calls = [v._ex.calls for v in p.venues]
    assert calls == [2, 2, 2], calls          # perfectly spread, no favorite venue


def test_failover_skips_broken_venue():
    p = _pool([("bad", "boom"), ("good", None)])
    out = p.ticker("BTC/USDT")
    assert out["venue"] == "good"


def test_ban_error_triggers_long_cooldown_and_budget_is_hard():
    p = _pool([("banned", "418 I'm a teapot"), ("ok", None)])
    p.ticker("BTC/USDT")                       # banned venue punished, ok serves
    assert p.venues[0].cooling()               # 418 → cooldown, not retried
    # budget: drain the bucket → venue refuses instead of calling
    b = _TokenBucket(per_min=2)
    assert b.take() and b.take() and not b.take()


def test_transient_error_gets_short_backoff_only():
    v = _Venue("x", "swap")
    v.punish(RuntimeError("connection timeout"))
    assert v.cooling()
    assert v.cooldown_until - time.monotonic() < 10     # ~5s, not ban-length


def test_norm_appends_settle_for_swap():
    p = ExchangePool("swap", quote="USDT")
    assert p._norm("ETH/USDT") == "ETH/USDT:USDT"
    assert p._norm("ETH/USDT:USDT") == "ETH/USDT:USDT"
    assert ExchangePool("spot")._norm("ETH/USDT") == "ETH/USDT"


def test_all_venues_down_raises():
    p = _pool([("a", "boom"), ("b", "boom")])
    try:
        p.ticker("BTC/USDT")
        assert False, "expected RuntimeError"
    except RuntimeError as e:
        assert "all venues" in str(e)


def test_crypto_options_screener_drops_expiring_contracts():
    """Regression 2026-07-03: same-day dailies (expire 08:00 UTC) topped the volume
    rank, the watchlist filled with dead symbols, and CRYPTO:options opened nothing."""
    import datetime as dt
    from trading.screener.screener import screen_crypto_options
    today = dt.datetime.now(dt.timezone.utc).strftime("%y%m%d")
    future = (dt.datetime.now(dt.timezone.utc) + dt.timedelta(days=7)).strftime("%y%m%d")

    class _Src:
        def tickers(self, seg):
            return {
                f"BTC/USDT:USDT-{today}-61000-C": {"quoteVolume": 9e9, "last": 100},
                f"BTC/USDT:USDT-{future}-61000-C": {"quoteVolume": 1e6, "last": 100},
            }

    out = screen_crypto_options(_Src(), limit=5)
    syms = [c["symbol"] for c in out]
    assert all(today not in s for s in syms), syms
    assert any(future in s for s in syms), syms
