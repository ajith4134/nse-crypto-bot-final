"""trading/screener/sources.py — INJECTABLE, offline-safe market-data sources.

Two source objects feed the `Screener`. Both follow the project's offline-safe
idiom (see memory/librarian.py / trading/instruments.py): lazy-import the heavy
lib INSIDE try/except and degrade to None / [] on any failure, so tests run with
no network and the dashboard never breaks.

  • LiveNSESource   — wraps `nselib` (capital_market.* + derivatives.*) → movers,
    52-week H/L, most-active, delivery%, F&O option-chain, futures, MCX list.
  • LiveCryptoSource — reuses trading/crypto/exchange_client.ExchangeClient (ccxt):
    fetch_tickers / fetch_markets / fetch_funding_rates / fetch_open_interest.

The `Screener` accepts ANY object with these duck-typed methods, so tests inject
deterministic fakes. None / empty return → the Screener falls back to its stub.
"""
from __future__ import annotations

from typing import Any

from trading.screener.filters import _num


# MCX has no free OSS movers feed (research §2.4) — scan this fixed universe.
MCX_UNIVERSE = ("GOLD", "SILVER", "CRUDEOIL", "NATURALGAS", "COPPER", "ZINC", "ALUMINIUM")


def _rows_from_df(obj: Any) -> list[dict]:
    """Coerce a nselib return (DataFrame / list / dict) into a list of row-dicts."""
    if obj is None:
        return []
    try:
        import pandas as pd
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict("records")
    except Exception:
        pass
    if isinstance(obj, list):
        return [r for r in obj if isinstance(r, dict)]
    if isinstance(obj, dict):
        # {"data": [...]} shapes
        for v in obj.values():
            if isinstance(v, list):
                return [r for r in v if isinstance(r, dict)]
    return []


class LiveNSESource:
    """Live NSE/MCX data via `nselib`. Every call is wrapped → degrades to []/None."""

    name = "nselib"

    # ── equity movers / 52w / delivery (intraday + mtf) ──────────────────────
    def movers(self, kind: str = "gainers") -> list[dict]:
        """Top gainers or losers (NSE market-activity). kind ∈ {gainers,losers}."""
        try:
            from nselib import capital_market as cm
            flag = "gainers" if kind.startswith("gain") else "losers"
            return _normalise_nse_movers(_rows_from_df(cm.top_gainers_or_losers(flag)))
        except Exception:
            return []

    def most_active(self) -> list[dict]:
        try:
            from nselib import capital_market as cm
            return _normalise_nse_movers(_rows_from_df(cm.most_active_equities()))
        except Exception:
            return []

    def week_52(self) -> list[dict]:
        try:
            from nselib import capital_market as cm
            return _rows_from_df(cm.week_52_high_low_report())
        except Exception:
            return []

    def ohlc(self, symbol: str, period: str = "1M") -> Any:
        """Price-volume history for one symbol (for technical filters)."""
        try:
            from nselib import capital_market as cm
            return cm.price_volume_and_deliverable_position_data(symbol, period=period)
        except Exception:
            return None

    # ── F&O (fno) ────────────────────────────────────────────────────────────
    def option_chain(self, symbol: str = "NIFTY") -> Any:
        try:
            from nselib import derivatives as dv
            return dv.nse_live_option_chain(symbol)
        except Exception:
            return None

    def active_underlying(self) -> list[dict]:
        try:
            from nselib import derivatives as dv
            return _rows_from_df(dv.live_most_active_underlying())
        except Exception:
            return []

    # ── commodities (MCX) ────────────────────────────────────────────────────
    def commodities(self) -> list[str]:
        return list(MCX_UNIVERSE)


def _normalise_nse_movers(rows: list[dict]) -> list[dict]:
    """Map nselib mover columns → unified {symbol, ltp, pct_change, volume}."""
    out = []
    for r in rows:
        sym = (r.get("symbol") or r.get("symbol_name") or r.get("Symbol")
               or r.get("SYMBOL") or "")
        if not sym:
            continue
        out.append({
            "symbol": str(sym).upper(),
            "ltp": _num(r.get("ltp") or r.get("lastPrice") or r.get("LTP")
                        or r.get("last_price")),
            "pct_change": _num(r.get("pChange") or r.get("perChange")
                               or r.get("pct_change") or r.get("netPrice")),
            "volume": _num(r.get("totalTradedVolume") or r.get("volume")
                           or r.get("trade_quantity")),
            "_raw": r,
        })
    return out


class LiveCryptoSource:
    """Live crypto data via ccxt (reuses ExchangeClient). Degrades to {}/None."""

    name = "ccxt"

    def __init__(self, exchange: str = "binance"):
        self.exchange = exchange
        self._clients: dict[str, Any] = {}

    def _raw(self, market_type: str) -> Any:
        """Raw ccxt client for a market type (spot/swap/option), cached."""
        if market_type in self._clients:
            return self._clients[market_type]
        try:
            from trading.crypto.exchange_client import ExchangeClient
            mt = {"spot": "spot", "futures": "swap", "swap": "swap",
                  "options": "option", "option": "option"}.get(market_type, "spot")
            cli = ExchangeClient(self.exchange, market_type=mt)._client()
            self._clients[market_type] = cli
            return cli
        except Exception:
            return None

    def tickers(self, market_type: str = "spot") -> dict:
        cli = self._raw(market_type)
        if cli is None:
            return {}
        try:
            return cli.fetch_tickers() or {}
        except Exception:
            return {}

    def markets(self, market_type: str = "spot") -> dict:
        cli = self._raw(market_type)
        if cli is None:
            return {}
        try:
            return cli.load_markets() or {}
        except Exception:
            return {}

    def funding_rates(self, market_type: str = "futures") -> dict:
        cli = self._raw(market_type)
        if cli is None:
            return {}
        try:
            return cli.fetch_funding_rates() or {}
        except Exception:
            return {}

    def open_interest(self, symbol: str, market_type: str = "futures") -> Any:
        cli = self._raw(market_type)
        if cli is None:
            return None
        try:
            return cli.fetch_open_interest(symbol)
        except Exception:
            return None

    def greeks(self, market_type: str = "options") -> dict:
        cli = self._raw(market_type)
        if cli is None:
            return {}
        try:
            return cli.fetch_all_greeks() or {}
        except Exception:
            return {}
