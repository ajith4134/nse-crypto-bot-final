"""NSE corporate announcements / corporate actions (Phase-T8 adv intel).

OFFLINE-TESTABLE + GATED:
    The network fetch goes through an INJECTED ``fetcher`` callable, so unit
    tests can pass a deterministic stub and run with no network. The default
    live fetcher only performs real HTTP when ``NseAnnouncements`` is built
    without a fetcher AND a data method is actually called.

Secrets-safe: no API keys are used or stored.

Public source wired (for reference, used only when called live):
    NSE corporate announcements API
        https://www.nseindia.com/api/corporate-announcements?index=equities
    Requires a browser User-Agent + warmed-up session cookie. Wrapped in
    try/except -> returns [] on any failure (honest).
"""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional

# Live endpoint references (no secrets).
NSE_ANNOUNCEMENTS_URL = (
    "https://www.nseindia.com/api/corporate-announcements?index=equities"
)
NSE_HOME_URL = "https://www.nseindia.com"
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
}

# Recognised announcement kinds.
KINDS = ("earnings", "bulk_deal", "corp_action", "board_meeting", "other")

# Keyword -> kind classification (checked in order).
_CLASSIFY_RULES = (
    (("results", "earnings", "financial result", "quarterly"), "earnings"),
    (("bulk", "block"), "bulk_deal"),
    (("dividend", "split", "bonus", "buyback", "rights"), "corp_action"),
    (("board meeting",), "board_meeting"),
)


def _live_fetch() -> List[Dict]:
    """Default live fetcher. Real HTTP, only invoked when called live.

    Returns raw announcement rows (list of dicts). [] on ANY failure (honest).
    """
    try:
        import requests

        sess = requests.Session()
        sess.headers.update(_BROWSER_HEADERS)
        sess.get(NSE_HOME_URL, timeout=10)
        resp = sess.get(NSE_ANNOUNCEMENTS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict):
            for key in ("data", "rows", "result"):
                if isinstance(data.get(key), list):
                    return data[key]
            return [data]
        if isinstance(data, list):
            return data
        return []
    except Exception:
        return []


def classify(subject: str) -> str:
    """Classify free-text subject into a KIND via keyword match."""
    text = (subject or "").lower()
    for keywords, kind in _CLASSIFY_RULES:
        if any(k in text for k in keywords):
            return kind
    return "other"


def _normalize(row: Dict) -> Dict:
    """Map a raw row (varied key spellings) into the canonical schema."""
    if not isinstance(row, dict):
        return {}

    def pick(*names):
        for n in names:
            if n in row and row[n] not in (None, ""):
                return row[n]
        return None

    symbol = pick("symbol", "Symbol", "sym", "scrip") or ""
    subject = pick("subject", "Subject", "desc", "headline", "smIndustry") or ""
    detail = pick("detail", "attchmntText", "attachmentText", "more", "bdsm") or ""
    dt = pick("datetime", "an_dt", "anDt", "dateTime", "date", "exchdisstime") or ""

    raw_type = pick("type", "kind", "category")
    kind = str(raw_type).strip().lower() if raw_type else ""
    if kind not in KINDS:
        kind = classify(str(subject))

    return {
        "symbol": str(symbol),
        "subject": str(subject),
        "type": kind,
        "datetime": str(dt),
        "detail": str(detail),
    }


class NseAnnouncements:
    """NSE corporate announcements with classification & filtering.

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

    def recent(
        self,
        symbol: Optional[str] = None,
        kinds: Optional[Iterable[str]] = None,
        n: int = 20,
    ) -> List[Dict]:
        """Filtered, most-recent-first list of announcements."""
        rows = self._rows()
        if symbol:
            sym = symbol.strip().upper()
            rows = [r for r in rows if r["symbol"].upper() == sym]
        if kinds:
            wanted = {str(k).strip().lower() for k in kinds}
            rows = [r for r in rows if r["type"] in wanted]
        return rows[: max(0, int(n))]

    def for_symbol(self, sym: str) -> List[Dict]:
        """All announcements for a given symbol (most recent first)."""
        return self.recent(symbol=sym, n=10_000)

    def status(self) -> Dict:
        """JSON-able summary with counts by type."""
        rows = self._rows()
        counts = {k: 0 for k in KINDS}
        for r in rows:
            counts[r["type"]] = counts.get(r["type"], 0) + 1
        return {
            "source": "NSE corporate-announcements",
            "rows": len(rows),
            "by_type": counts,
            "symbols": sorted({r["symbol"] for r in rows if r["symbol"]}),
        }
