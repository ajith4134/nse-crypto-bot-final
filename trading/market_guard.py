"""trading/market_guard.py — the ONE structural boundary between markets.

Multi-market isolation in this project is by convention: every execution seam trusts an
upstream ``market`` tag ("CRYPTO" | "NSE") to decide which API door an order goes through
(Freqtrade/Binance vs OpenAlgo/Zerodha). That convention has no teeth — one wrong tag, or a
wrong-market symbol slipping into a per-market list, and a crypto ticker gets shipped to Kite
(observed 2026-07-13). This module is the last line: it classifies a symbol by its SHAPE and
rejects any (market, symbol) pair that can't be true, so a crypto symbol can NEVER reach the
NSE door and vice-versa — regardless of which upstream introduced the mismatch.

Shape rules (consolidated from the ~10 places that inlined them — conformal, dreamer, screener,
data_failsafe, ui_crawl, exchange_pool, binance_filter_lane…):
  * CRYPTO pairs carry ``/`` (BTC/USDT), ``:`` (BTC/USDT:USDT perp), or end in a crypto quote
    (BTCUSDT). Prediction-market symbols also live under CRYPTO and are never NSE-shaped.
  * NSE/BSE/MCX symbols are bare uppercase tickers (RELIANCE), dated FUT (GOLD05AUG26FUT),
    option strings (NIFTY31JUL24C24000), or venue-prefixed (NSE:… / BSE:… / NFO:… / BFO:… / MCX:…).
  * A BARE base with no distinguishing shape (``BTC``, ``RELIANCE``) is genuinely ambiguous →
    classified None and NOT blocked (honest: we never guess-block a valid ticker).

Nothing here does network or state. Import-safe everywhere (no trading.* deps).
"""
from __future__ import annotations

CRYPTO = "CRYPTO"
NSE = "NSE"

# Crypto settlement/quote assets: a symbol ending in one of these (no separator) is a
# concatenated crypto pair (BTCUSDT). Kept minimal to avoid false-positives on NSE tickers.
_CRYPTO_QUOTES = ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "DAI")
# Venue prefixes that unambiguously mark an Indian-market instrument.
_NSE_PREFIXES = ("NSE:", "BSE:", "NFO:", "BFO:", "MCX:", "CDS:")


class MarketSymbolMismatch(ValueError):
    """Raised when a symbol's shape contradicts the market it was routed to."""


def is_instrument_key(symbol: str) -> bool:
    """True for a DATA-FEED instrument-key format (Upstox: 'NSE_FO|51380', 'BSE_INDEX|SENSEX',
    'NSE_EQ|INE002A01018') — an identifier the eyes' WS feed names symbols by, NOT a broker-
    tradeable symbol. OpenAlgo/Zerodha 404 ("Symbol NSE_FO|51380 not found on NSE") on these, so
    they must never reach the execution/quote door: translate to a tradingsymbol or skip.
    Crypto pairs use '/'+':' (never '|'), so this is unambiguous."""
    return "|" in (symbol or "")


def market_of_symbol(symbol: str) -> str | None:
    """Infer the market from a symbol's SHAPE, or None when genuinely ambiguous.

    Never raises. Returns "CRYPTO", "NSE", or None (a bare base like BTC/RELIANCE that
    could belong to either — the caller must not block on None)."""
    s = (symbol or "").strip()
    if not s:
        return None
    up = s.upper()
    if up.startswith(_NSE_PREFIXES):
        return NSE
    if "/" in s or ":" in s:                       # BTC/USDT, BTC/USDT:USDT
        return CRYPTO
    # concatenated crypto pair (BTCUSDT) — but only when there's a base BEFORE the quote,
    # so a bare "USDT" or a 4-letter NSE ticker that merely ends in these chars can't trip it.
    for q in _CRYPTO_QUOTES:
        if up.endswith(q) and len(up) > len(q):
            return CRYPTO
    return None


def market_matches(market: str, symbol: str) -> bool:
    """True when `symbol`'s shape is consistent with `market` (or is ambiguous). The
    inverse — a symbol whose shape clearly belongs to the OTHER market — is False."""
    inferred = market_of_symbol(symbol)
    if inferred is None:                           # ambiguous bare ticker → don't block
        return True
    want = CRYPTO if (market or "").upper() == CRYPTO else NSE
    return inferred == want


def assert_market_symbol(market: str, symbol: str) -> None:
    """Raise MarketSymbolMismatch if `symbol` clearly belongs to the other market. The
    structural guard both API doors call before placing an order."""
    if not market_matches(market, symbol):
        raise MarketSymbolMismatch(
            f"symbol {symbol!r} is shaped {market_of_symbol(symbol)!r} but was routed to "
            f"market {(market or '').upper()!r} — cross-market order blocked")
