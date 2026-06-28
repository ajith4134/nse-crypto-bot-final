"""NSE FII/DII cash-market flows (Phase-T8 advanced intelligence).

OFFLINE-TESTABLE + GATED:
    The network fetch goes through an INJECTED ``fetcher`` callable, so unit
    tests can pass a deterministic stub and run with no network. The default
    live fetcher only performs real HTTP when ``FiiDiiFlows`` is constructed
    without a fetcher AND a data method is actually called.

Secrets-safe: no API keys are used or stored.

Public source wired (for reference, used only when called live):
    NSE FII/DII Trade React API
        https://www.nseindia.com/api/fiidiiTradeReact
    Requires a browser User-Agent + a warmed-up session cookie (NSE rejects
    bare requests). Wrapped in try/except -> returns [] on any failure (honest).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

# Live endpoint references (no secrets).
NSE_FIIDII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"
NSE_HOME_URL = "https://www.nseindia.com"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/reports/fii-dii",
}

# Canonical numeric fields (₹cr).
_NUM_FIELDS = (
    "fii_buy",
    "fii_sell",
    "fii_net",
    "dii_buy",
    "dii_sell",
    "dii_net",
)


def _live_fetch() -> List[Dict]:
    """Default live fetcher. Real HTTP, only invoked when called live.

    Returns raw rows (list of dicts). Returns [] on ANY failure (honest).
    """
    try:
        import requests  # local import: keeps module import cheap & offline-safe

        sess = requests.Session()
        sess.headers.update(_BROWSER_HEADERS)
        # Warm up to obtain NSE session cookies.
        sess.get(NSE_HOME_URL, timeout=10)
        resp = sess.get(NSE_FIIDII_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            # Some NSE payloads wrap rows in a key.
            for key in ("data", "fiidii", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def _to_float(value) -> float:
    """Best-effort numeric coercion; tolerant of ₹ commas / blanks / None."""
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    try:
        cleaned = str(value).replace(",", "").replace("₹", "").strip()
        if cleaned in ("", "-", "--", "NA", "N/A"):
            return 0.0
        return float(cleaned)
    except Exception:
        return 0.0


def _normalize(row: Dict) -> Dict:
    """Map a raw row (varied key spellings) into the canonical schema."""
    if not isinstance(row, dict):
        return {}

    def pick(*names):
        for n in names:
            if n in row and row[n] not in (None, ""):
                return row[n]
        return None

    date = pick("date", "tradeDate", "Date", "trade_date") or ""

    fii_buy = _to_float(pick("fii_buy", "fiiBuyValue", "FII_BUY", "fiiBuy"))
    fii_sell = _to_float(pick("fii_sell", "fiiSellValue", "FII_SELL", "fiiSell"))
    fii_net = pick("fii_net", "fiiNetValue", "FII_NET", "fiiNet")
    dii_buy = _to_float(pick("dii_buy", "diiBuyValue", "DII_BUY", "diiBuy"))
    dii_sell = _to_float(pick("dii_sell", "diiSellValue", "DII_SELL", "diiSell"))
    dii_net = pick("dii_net", "diiNetValue", "DII_NET", "diiNet")

    # Derive net if not provided.
    fii_net = _to_float(fii_net) if fii_net is not None else (fii_buy - fii_sell)
    dii_net = _to_float(dii_net) if dii_net is not None else (dii_buy - dii_sell)

    return {
        "date": str(date),
        "fii_buy": fii_buy,
        "fii_sell": fii_sell,
        "fii_net": fii_net,
        "dii_buy": dii_buy,
        "dii_sell": dii_sell,
        "dii_net": dii_net,
    }


class FiiDiiFlows:
    """Daily FII/DII cash-market activity (₹cr).

    Args:
        fetcher: optional callable returning raw rows (list of dicts). When
            None, a gated live NSE fetcher is used (real HTTP only on call).
    """

    def __init__(self, fetcher: Optional[Callable[[], List[Dict]]] = None):
        self._fetcher = fetcher or _live_fetch

    def _rows(self) -> List[Dict]:
        try:
            raw = self._fetcher() or []
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        rows = [_normalize(r) for r in raw]
        return [r for r in rows if r]

    def latest(self) -> Dict:
        """Most recent day's flows (first row), or {} if none."""
        rows = self._rows()
        return rows[0] if rows else {}

    def trend(self, n: int = 5) -> Dict:
        """Cumulative net FII/DII over the last ``n`` days + a simple bias."""
        rows = self._rows()[: max(0, int(n))]
        fii_cum = sum(r["fii_net"] for r in rows)
        dii_cum = sum(r["dii_net"] for r in rows)

        if fii_cum > 0:
            fii_bias = "FII bullish"
        elif fii_cum < 0:
            fii_bias = "FII bearish"
        else:
            fii_bias = "FII neutral"

        if dii_cum > 0:
            dii_bias = "DII bullish"
        elif dii_cum < 0:
            dii_bias = "DII bearish"
        else:
            dii_bias = "DII neutral"

        return {
            "days": len(rows),
            "fii_net_cum": round(fii_cum, 2),
            "dii_net_cum": round(dii_cum, 2),
            "fii_bias": fii_bias,
            "dii_bias": dii_bias,
            "dates": [r["date"] for r in rows],
        }

    def status(self) -> Dict:
        """JSON-able summary."""
        rows = self._rows()
        return {
            "source": "NSE fiidiiTradeReact",
            "rows": len(rows),
            "latest": self.latest(),
            "trend": self.trend(),
        }
