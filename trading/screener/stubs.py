"""trading/screener/stubs.py — deterministic OFFLINE candidate lists per segment.

When a live source returns nothing (no network / nselib or ccxt unavailable / rate
limited), the `Screener` falls back to these fixed, ranked candidate lists so tests,
the live loop and the dashboard ALWAYS get a usable, varied watchlist. The numbers
are illustrative-but-stable (no randomness) so output is reproducible.
"""
from __future__ import annotations

# Each entry: (symbol, score, reason, metrics)
_STUB: dict[tuple[str, str], list[tuple]] = {
    ("NSE", "intraday"): [
        ("RELIANCE", 0.92, "stub: large-cap mover", {"pct_change": 2.4, "rvol": 1.8}),
        ("TCS", 0.86, "stub: IT leader", {"pct_change": 1.7, "rvol": 1.5}),
        ("HDFCBANK", 0.80, "stub: banking heavyweight", {"pct_change": 1.3, "rvol": 1.4}),
        ("INFY", 0.74, "stub: IT momentum", {"pct_change": 1.1, "rvol": 1.2}),
        ("ICICIBANK", 0.68, "stub: financials", {"pct_change": 0.9, "rvol": 1.1}),
        ("SBIN", 0.62, "stub: PSU bank", {"pct_change": 0.7, "rvol": 1.0}),
    ],
    ("NSE", "mtf"): [
        ("RELIANCE", 0.90, "stub: MTF-eligible large-cap", {"pct_change": 2.4}),
        ("TCS", 0.84, "stub: MTF-eligible IT", {"pct_change": 1.7}),
        ("HDFCBANK", 0.78, "stub: MTF-eligible bank", {"pct_change": 1.3}),
        ("LT", 0.72, "stub: MTF-eligible capex", {"pct_change": 1.0}),
        ("ITC", 0.66, "stub: MTF-eligible FMCG", {"pct_change": 0.8}),
    ],
    ("NSE", "fno"): [
        ("NIFTY", 0.93, "stub: index option-chain (PCR bullish)", {"pcr_oi": 1.3}),
        ("BANKNIFTY", 0.88, "stub: bank index chain", {"pcr_oi": 1.1}),
        ("RELIANCE", 0.80, "stub: stock F&O long-buildup", {"oi_buildup": "long_buildup"}),
        ("HDFCBANK", 0.73, "stub: stock F&O", {"oi_buildup": "short_covering"}),
        ("INFY", 0.66, "stub: stock F&O", {"oi_buildup": "neutral"}),
    ],
    ("NSE", "commodities"): [
        ("GOLD", 0.90, "stub: MCX bullion", {"atr_pct": 1.1}),
        ("CRUDEOIL", 0.85, "stub: MCX energy (high ATR)", {"atr_pct": 2.3}),
        ("NATURALGAS", 0.80, "stub: MCX energy (volatile)", {"atr_pct": 3.1}),
        ("SILVER", 0.74, "stub: MCX bullion", {"atr_pct": 1.6}),
        ("COPPER", 0.68, "stub: MCX base metal", {"atr_pct": 1.2}),
    ],
    ("CRYPTO", "spot"): [
        ("BTC/USDT", 0.94, "stub: top volume + momentum", {"pct_change": 3.2, "quote_volume": 1.2e10}),
        ("ETH/USDT", 0.89, "stub: high volume", {"pct_change": 2.6, "quote_volume": 6.0e9}),
        ("SOL/USDT", 0.82, "stub: volatile mover", {"pct_change": 5.1, "quote_volume": 1.5e9}),
        ("BNB/USDT", 0.75, "stub: liquidity", {"pct_change": 1.4, "quote_volume": 9.0e8}),
        ("XRP/USDT", 0.69, "stub: large-cap alt", {"pct_change": 2.0, "quote_volume": 8.0e8}),
    ],
    ("CRYPTO", "futures"): [
        ("BTC/USDT:USDT", 0.93, "stub: perp, +funding/OI", {"funding": 0.0001, "pct_change": 3.0}),
        ("ETH/USDT:USDT", 0.88, "stub: perp high OI", {"funding": 0.00008, "pct_change": 2.4}),
        ("SOL/USDT:USDT", 0.81, "stub: perp volatile", {"funding": 0.00025, "pct_change": 4.8}),
        ("DOGE/USDT:USDT", 0.72, "stub: meme perp", {"funding": 0.0003, "pct_change": 6.0}),
    ],
    ("CRYPTO", "options"): [
        ("BTC-CALL", 0.90, "stub: BTC option, high volume/IV", {"iv": 0.55}),
        ("BTC-PUT", 0.84, "stub: BTC hedge", {"iv": 0.58}),
        ("ETH-CALL", 0.78, "stub: ETH option", {"iv": 0.62}),
        ("ETH-PUT", 0.71, "stub: ETH hedge", {"iv": 0.65}),
    ],
}


def stub_candidates(market: str, segment: str, *, limit: int = 5) -> list[dict]:
    """Return the fixed ranked candidate list for (market, segment)."""
    market, segment = market.upper(), segment.lower()
    rows = _STUB.get((market, segment), [])
    out = []
    for sym, score, reason, metrics in rows[:limit]:
        out.append({
            "symbol": sym, "segment": segment, "market": market,
            "score": score, "reason": reason,
            "metrics": {**metrics, "source": "stub"},
        })
    return out
