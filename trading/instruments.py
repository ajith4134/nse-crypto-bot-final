"""trading/instruments.py — NSE/NFO/MCX instrument master via OpenAlgo.

OpenAlgo maintains the broker scripmaster (50k+ Indian instruments across
NSE/BSE/NFO/BFO/MCX/CDS) in its own DB and exposes search over it. We query that
real endpoint and cache the results locally so the watchlist search bar (T1 §6)
resolves symbols without re-hitting the server every keystroke.

Honest-wiring: search results come from the live OpenAlgo symbol DB. If the
server is down we surface the error — we never invent instruments.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from trading import state
from trading.openalgo_client import OpenAlgoClient, OpenAlgoError

_CACHE_FILE = "instruments_cache.json"

# Segments we care about in T1 (NSE window). Crypto (T2) is handled separately.
NSE_SEGMENTS = ("NSE", "BSE", "NFO", "BFO", "CDS", "BCD", "MCX", "NCDEX")


@dataclass(frozen=True)
class Instrument:
    """One tradable contract. Mirrors OpenAlgo symbol fields we use."""
    symbol: str          # OpenAlgo trading symbol, e.g. "RELIANCE" / "NIFTY28JUN24C24000"
    exchange: str        # NSE | NFO | MCX | ...
    name: str = ""       # human name / underlying
    token: str = ""      # broker instrument token
    instrument_type: str = ""  # EQ | FUT | CE | PE | ...
    expiry: str = ""     # for derivatives
    strike: float = 0.0  # for options
    lot_size: int = 0

    @classmethod
    def from_openalgo(cls, row: dict) -> "Instrument":
        """Build from an OpenAlgo search-result row (tolerant to key variants)."""
        def g(*keys, default=""):
            for k in keys:
                if k in row and row[k] not in (None, ""):
                    return row[k]
            return default

        def gf(*keys):
            v = g(*keys, default=0)
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        def gi(*keys):
            try:
                return int(float(g(*keys, default=0)))
            except (TypeError, ValueError):
                return 0

        return cls(
            symbol=str(g("symbol", "tradingsymbol", "trading_symbol")),
            exchange=str(g("exchange", "exch", "exchange_segment")).upper(),
            name=str(g("name", "company", "underlying")),
            token=str(g("token", "instrument_token", "symboltoken")),
            instrument_type=str(g("instrumenttype", "instrument_type", "type")).upper(),
            expiry=str(g("expiry", "expiry_date")),
            strike=gf("strike", "strike_price"),
            lot_size=gi("lotsize", "lot_size", "lot"),
        )


class InstrumentStore:
    """Search + cache over the OpenAlgo instrument master."""

    def __init__(self, client: OpenAlgoClient | None = None):
        self.client = client or OpenAlgoClient()
        self._cache: dict[str, list[dict]] = state.load_json(_CACHE_FILE, {})

    def search(self, query: str, exchange: str = "NSE", use_cache: bool = True) -> list[Instrument]:
        """Search the OpenAlgo symbol DB. Caches per (query, exchange)."""
        query = (query or "").strip()
        if not query:
            return []
        exchange = exchange.upper()
        key = f"{exchange}:{query.upper()}"
        if use_cache and key in self._cache:
            return [Instrument.from_openalgo(r) for r in self._cache[key]]

        rows = self._remote_search(query, exchange)
        self._cache[key] = rows
        state.save_json(_CACHE_FILE, self._cache)
        return [Instrument.from_openalgo(r) for r in rows]

    def _remote_search(self, query: str, exchange: str) -> list[dict]:
        """Hit OpenAlgo's search endpoint. Returns raw rows (list of dicts)."""
        sdk = self.client._client()  # raises a clear error if SDK/server absent
        try:
            resp = sdk.search(query=query, exchange=exchange)
        except AttributeError:
            # Older SDKs expose a single-symbol resolver instead of full search.
            resp = sdk.symbol(symbol=query, exchange=exchange)
        except Exception as exc:  # transport / server-down
            raise OpenAlgoError(f"instrument search failed: {exc}") from exc

        if not isinstance(resp, dict):
            raise OpenAlgoError(f"search: unexpected response {resp!r}")
        if resp.get("status") == "error":
            raise OpenAlgoError(f"search failed: {resp.get('message', resp)}")
        data = resp.get("data", resp.get("results", []))
        if isinstance(data, dict):  # single-symbol resolver path
            data = [data]
        return [r for r in data if isinstance(r, dict)]

    def resolve(self, symbol: str, exchange: str = "NSE") -> Instrument | None:
        """Exact-symbol lookup. Returns the first match or None."""
        for inst in self.search(symbol, exchange):
            if inst.symbol.upper() == symbol.upper():
                return inst
        return None

    def clear_cache(self) -> None:
        self._cache = {}
        state.save_json(_CACHE_FILE, self._cache)


def to_dict(inst: Instrument) -> dict:
    return asdict(inst)
