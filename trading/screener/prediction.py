"""Prediction-market screener — scans ALL live event markets and ranks them for the loop.

Source: Polymarket's public gamma API (no auth, real markets/prices). Binance's own prediction
market is Predict.fun (on-chain, API-key-gated) — when a key is configured the fetch can be
pointed there; the candidate shape stays identical. Execution is PAPER-ONLY by design: a
"position" is YES/NO shares priced 0..1, simulated in the shared paper wallet.

Symbols are namespaced "PRED:<slug>" so the live loop can route quotes here (no ccxt ticker
exists for event markets). `last_price()` serves the loop's price lookups from the scan cache.
"""
from __future__ import annotations

import json
import time
import urllib.request

GAMMA_URL = ("https://gamma-api.polymarket.com/markets"
             "?closed=false&limit={limit}&order=volume24hr&ascending=false")

_CACHE: dict = {"ts": 0.0, "rows": []}          # last scan (all markets)
_PRICES: dict = {}                               # "PRED:<slug>" -> last YES price (0..1)
_TTL = 60.0                                      # scan cache TTL (seconds)


def _fetch(limit: int = 100) -> list[dict]:
    req = urllib.request.Request(GAMMA_URL.format(limit=limit),
                                 headers={"User-Agent": "mlnb-screener/1.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode())


def scan(limit: int = 100) -> list[dict]:
    """All live prediction markets (cached _TTL). Row: {symbol, question, yes, volume24h, end}."""
    now = time.time()
    if _CACHE["rows"] and now - _CACHE["ts"] < _TTL:
        return _CACHE["rows"]
    rows = []
    for m in _fetch(limit):
        try:
            prices = m.get("outcomePrices")
            if isinstance(prices, str):
                prices = json.loads(prices)
            yes = float(prices[0]) if prices else None
            if yes is None or not (0.0 < yes < 1.0):
                continue
            sym = f"PRED:{m.get('slug') or m.get('id')}"
            rows.append({"symbol": sym, "question": m.get("question", ""),
                         "yes": yes, "volume24h": float(m.get("volume24hr") or 0.0),
                         "liquidity": float(m.get("liquidity") or 0.0),
                         "end": m.get("endDate", "")})
            _PRICES[sym] = yes
        except Exception:
            continue
    if rows:
        _CACHE.update(ts=now, rows=rows)
    return rows


def last_price(symbol: str) -> float | None:
    """YES price for a PRED: symbol from the scan cache (refresh if cold)."""
    if symbol not in _PRICES:
        scan()
    return _PRICES.get(symbol)


def screen_crypto_prediction(limit: int = 5, filters: dict | None = None) -> list[dict]:
    """Ranked prediction-market candidates for the loop's watchlist.

    Edge heuristic (paper): prefer LIQUID markets whose YES price sits away from the coin-flip
    0.5 (crowd conviction) but not pinned at the extremes (no payoff left). score =
    volume-rank weight x distance-from-extremes."""
    import math
    rows = scan(limit=100)
    scored = []
    for r in rows:
        yes = r["yes"]
        edge = min(yes, 1.0 - yes)                       # 0 at the extremes, 0.5 at coin-flip
        if edge < 0.03:                                   # ≥97/3 markets: nothing left to earn
            continue
        conviction = abs(yes - 0.5) * 2                  # 0 coin-flip → 1 near-certain
        # Bounded 0..~10 like the other segment screeners — raw sqrt(volume) scores (~1500+)
        # drowned spot/futures/options out of the shared watchlist's global score sort.
        score = min(10.0, math.log10(r["volume24h"] + 10)) * (0.35 + 0.65 * conviction) * (edge / 0.5)
        scored.append({"symbol": r["symbol"], "segment": "prediction", "market": "CRYPTO",
                       "score": round(score, 4), "price": yes,
                       "reason": f"prediction: {r['question'][:60]} · yes={yes:.2f} "
                                 f"· vol24h={r['volume24h']:,.0f}"})
    scored.sort(key=lambda c: c["score"], reverse=True)
    return scored[: max(1, int(limit))]
