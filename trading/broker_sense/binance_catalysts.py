"""trading/broker_sense/binance_catalysts.py — Binance-native event catalysts (P2, compute-offload).

New/upcoming listings are among the strongest short-horizon crypto catalysts (fresh perps pump on
listing-day flow). Both signals here are Binance-native and FREE — no paid data, no scraping brittle
UI:

  1. UPCOMING listings ← Binance's public announcements API (the same feed the website's
     "New Cryptocurrency Listing" page uses): "Binance Futures Will Launch <SYM> Perpetual", etc.
  2. JUST-LISTED perps ← a diff of the all-market WS mirror's universe: a symbol that appears in
     futures_rows() but was never seen before = it just started trading. Real-time, zero extra deps.

catalyst(symbol) fuses both into a compact flag the brain can size/prioritise on. Everything is
TTL-cached (announcements ~1h) or a cheap RAM diff; the seen-universe persists to a state file so
"new" is honest across restarts (the first run seeds, never false-flags the whole board as new).

NOTE: Token-Unlock catalysts are DEFERRED — DefiLlama's emissions API is now paywalled (402) and
there is no free Binance endpoint for it (zero-cost-first: we never hand the owner a pay item). Logged
to the idea ledger; will wire when a free source is found. We do NOT fabricate unlock data.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.request

from trading import state

_ANN_URL = ("https://www.binance.com/bapi/composite/v1/public/cms/article/catalog/list/query"
            "?catalogId={cat}&pageNo=1&pageSize={n}")
_ANN_TTL = float(os.getenv("BINANCE_ANN_TTL", "3600") or 3600)   # announcements change slowly
_NEW_LISTING_WINDOW_S = 3 * 24 * 3600.0                          # "new" = listed within 3 days
_cache: dict = {}
_SEEN_FILE = "binance_seen_symbols.json"
# titles are like "...Will Launch USDⓈ-Margined SKHYUSDT Perpetual..." or "Adds ANTA, CBRS, ... on"
_SYM_RE = re.compile(r"\b([A-Z0-9]{2,12})USDT?\b")
_LIST_RE = re.compile(r"\b([A-Z]{2,10})\b")


def enabled() -> bool:
    return os.getenv("BINANCE_CATALYSTS", "1").strip().lower() not in ("0", "false", "off")


def _get_json(url: str):
    """GET+parse; isolated for test monkeypatch. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "clienttype": "web"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _articles(cat: int, n: int):
    d = _get_json(_ANN_URL.format(cat=cat, n=n))
    if not isinstance(d, dict):
        return []
    data = d.get("data") or {}
    cats = data.get("catalogs")
    if isinstance(cats, list) and cats:
        return cats[0].get("articles") or []
    return data.get("articles") or []


def announcements(cat: int = 48, n: int = 20) -> list[dict]:
    """Recent Binance listing announcements (catalogId 48 = New Cryptocurrency Listing). Cached."""
    if not enabled():
        return []
    key = f"ann:{cat}:{n}"
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] <= _ANN_TTL:
        return hit[1]
    arts = _articles(cat, n)
    out = []
    for a in arts or []:
        title = str(a.get("title") or "")
        out.append({"title": title, "symbols": _extract_symbols(title),
                    "id": a.get("id") or a.get("code"), "release": a.get("releaseDate")})
    if out:
        _cache[key] = (now, out)
        return out
    return hit[1] if hit else []                              # serve last-good on a failed refresh


def _extract_symbols(title: str) -> list[str]:
    """Pull candidate base tickers from an announcement title. Heuristic; downstream validates
    against the live mirror universe so junk tokens never become fake catalysts."""
    syms = set()
    for m in _SYM_RE.finditer(title):
        syms.add(m.group(1))                                 # SKHYUSDT → SKHY
    if "Adds" in title:                                      # "Adds ANTA, CBRS, DISK ... on"
        seg = title.split("Adds", 1)[1].split(" on ")[0]
        for m in _LIST_RE.finditer(seg):
            if m.group(1) not in ("USD", "USDT", "USDC", "AND"):
                syms.add(m.group(1))
    return sorted(syms)


# ── just-listed detection via mirror universe diff ───────────────────────────
def _seen_path():
    return state._path("catalysts") / _SEEN_FILE


def _load_seen() -> dict:
    try:
        p = _seen_path()
        if p.exists():
            return json.loads(p.read_text() or "{}")
    except Exception:
        pass
    return {}


def _save_seen(seen: dict) -> None:
    try:
        p = _seen_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(seen))
        tmp.replace(p)
    except Exception:
        pass


def refresh_new_listings() -> dict:
    """Diff the mirror universe vs the persisted seen-set → mark first-seen ts for each symbol.
    First run seeds everything (no false 'new'). Returns {raw_symbol: first_seen_ts}. Cheap RAM diff."""
    try:
        from trading.broker_sense.binance_stream import get_mirror
        rows = get_mirror().futures_rows()
    except Exception:
        rows = []
    seen = _load_seen()
    now = time.time()
    seeding = not seen                                       # first ever run → seed, don't flag
    changed = False
    for r in rows:
        raw = r.get("raw")
        if raw and raw not in seen:
            seen[raw] = now if not seeding else 0.0          # 0.0 = pre-existing (seeded), not new
            changed = True
    if changed:
        _save_seen(seen)
    return seen


def new_listings(max_age_s: float = _NEW_LISTING_WINDOW_S) -> list[dict]:
    """Symbols first seen in the mirror within max_age_s (genuinely new listings). Newest first."""
    seen = refresh_new_listings()
    now = time.time()
    fresh = [{"raw": s, "age_s": round(now - t, 1)} for s, t in seen.items()
             if t and now - t <= max_age_s]
    fresh.sort(key=lambda x: x["age_s"])
    return fresh


# ── the per-symbol catalyst read ─────────────────────────────────────────────
def catalyst(symbol: str) -> dict:
    """Binance-native catalyst flags for one symbol (ccxt or raw form both accepted).

    {is_new_listing, listing_age_s, listing_announced, announcement_title}. Honest: absent data → False."""
    raw = (symbol or "").upper().replace("/", "").split(":")[0]
    base = raw[:-4] if raw.endswith("USDT") else raw
    out = {"symbol": raw, "is_new_listing": False, "listing_age_s": None,
           "listing_announced": False, "announcement_title": None}
    if not enabled():
        return out
    seen = _load_seen()
    t = seen.get(raw)
    if t and time.time() - t <= _NEW_LISTING_WINDOW_S:
        out["is_new_listing"] = True
        out["listing_age_s"] = round(time.time() - t, 1)
    for a in announcements():
        if base in a.get("symbols", []):
            out["listing_announced"] = True
            out["announcement_title"] = a.get("title")
            break
    return out
