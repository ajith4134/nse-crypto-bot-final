"""trading/crypto/markets.py — live crypto markets/screener feed (Binance-style table).

One cheap pass over ccxt `fetch_tickers` (+ one funding-rate call for perps) yields a ranked,
filterable market list the dashboard renders like Binance's markets tab and the brain screens
trades from: symbol, base, segment, last price, 24h %, 24h quote volume, a volatility proxy
(24h high-low range %), and perp funding. Sortable by volume / movers / volatility / funding /
price. Offline-safe: returns [] on failure.
"""
from __future__ import annotations

import time

_CACHE: dict = {}
_QUOTE = "USDT"


def _client(segment: str):
    import ccxt
    opts = {"enableRateLimit": True}
    if segment == "perp":
        opts["options"] = {"defaultType": "swap"}
    return ccxt.binance(opts)


def _funding(ex) -> dict:
    try:
        fr = ex.fetch_funding_rates()
        return {s: float((v or {}).get("fundingRate") or 0.0) for s, v in fr.items()}
    except Exception:
        return {}


def live_markets(*, segment: str = "perp", sort: str = "volume", limit: int = 80,
                 search: str = "") -> list[dict]:
    """Ranked live market rows. segment ∈ {perp, spot}; sort ∈
    {volume, movers, gainers, losers, volatility, funding, price}."""
    key = f"{segment}:{sort}:{limit}:{search}"
    hit = _CACHE.get(key); now = time.monotonic()
    if hit and now - hit[0] < 8:
        return hit[1]
    try:
        ex = _client(segment)
        ex.load_markets()
        tickers = ex.fetch_tickers()
        funding = _funding(ex) if segment == "perp" else {}
    except Exception:
        return []
    rows = []
    for sym, t in tickers.items():
        m = ex.markets.get(sym, {})
        if m.get("quote") != _QUOTE or not m.get("active"):
            continue
        if segment == "perp" and not m.get("swap"):
            continue
        if segment == "spot" and not m.get("spot"):
            continue
        base = m.get("base", "")
        if search and search.upper() not in (base + sym).upper():
            continue
        last = float(t.get("last") or 0.0)
        hi, lo = float(t.get("high") or 0.0), float(t.get("low") or 0.0)
        vol_range = ((hi - lo) / last * 100.0) if last else 0.0
        rows.append({
            "symbol": sym, "display": sym.split(":")[0].replace("/", ""), "base": base,
            "segment": "PERP" if segment == "perp" else "SPOT",
            "last": last, "pct_24h": float(t.get("percentage") or 0.0),
            "quote_volume": float(t.get("quoteVolume") or 0.0),
            "volatility": round(vol_range, 2),
            "funding": round(funding.get(sym, 0.0) * 100.0, 4),
        })
    keyfn = {
        "volume": lambda r: r["quote_volume"],
        "movers": lambda r: abs(r["pct_24h"]),
        "gainers": lambda r: r["pct_24h"],
        "losers": lambda r: -r["pct_24h"],
        "volatility": lambda r: r["volatility"],
        "funding": lambda r: abs(r["funding"]),
        "price": lambda r: r["last"],
    }.get(sort, lambda r: r["quote_volume"])
    rows.sort(key=keyfn, reverse=True)
    rows = rows[:max(1, int(limit))]
    _CACHE[key] = (now, rows)
    return rows
