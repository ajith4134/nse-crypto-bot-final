"""trading/broker_sense/binance_sectors.py — Binance-native sector taxonomy + rotation (P3).

Binance classifies every coin into sectors (AI, Meme, RWA, DeFi, Layer1_Layer2, Gaming, Solana,
Payments, …) — a rich, curated taxonomy it computes and serves FREE via the public products
endpoint (the same data its markets page uses). We read it (no local classification, no paid data)
and turn it into a real edge: SECTOR ROTATION — when a coin's sector is broadly pumping, that's
confluence; when its whole sector is bleeding, fade/abstain.

  • tags_for(symbol)      → Binance's sector tags for a symbol (via its base asset).
  • sector_rotation()     → per-sector average 24h %change (from the WS mirror's pushed tickers),
                            ranked hot→cold. Pure RAM once the products map is cached.
  • sector_signal(symbol) → {tags, sector, sector_momentum, tilt} — a bounded directional lean
                            from the symbol's strongest sector's momentum.

Products map is TTL-cached (~1h; sectors change slowly). Everything degrades to empty/None honestly
when the feed is cold. Kill switch: BINANCE_SECTORS=0. Public data, no keys.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

_PRODUCTS_URL = "https://www.binance.com/bapi/asset/v2/public/asset-service/product/get-products"
_TTL = float(os.getenv("BINANCE_SECTORS_TTL", "3600") or 3600)
_cache: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("BINANCE_SECTORS", "1").strip().lower() not in ("0", "false", "off")


def _get_json(url: str):
    """GET+parse; isolated for test monkeypatch. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "clienttype": "web"})
        with urllib.request.urlopen(req, timeout=12) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _base_tags() -> dict:
    """{base_asset: [tags]} from Binance's products endpoint. TTL-cached; serves last-good on failure."""
    now = time.time()
    with _lock:
        hit = _cache.get("base_tags")
        if hit and now - hit[0] <= _TTL:
            return hit[1]
    d = _get_json(_PRODUCTS_URL)
    rows = (d or {}).get("data") if isinstance(d, dict) else None
    if not rows:
        with _lock:
            hit = _cache.get("base_tags")
            return hit[1] if hit else {}
    out: dict = {}
    for r in rows:
        base = r.get("b")                       # base asset, e.g. "BTC"
        tags = r.get("tags") or []
        if base and tags:
            out.setdefault(base.upper(), set()).update(tags)
    out = {k: sorted(v) for k, v in out.items()}
    with _lock:
        _cache["base_tags"] = (now, out)
    return out


def _base_of(symbol: str) -> str:
    raw = (symbol or "").upper().replace("/", "").split(":")[0]
    for q in ("USDT", "USDC", "BUSD", "FDUSD"):
        if raw.endswith(q):
            return raw[: -len(q)]
    return raw


def tags_for(symbol: str) -> list[str]:
    if not enabled():
        return []
    return _base_tags().get(_base_of(symbol), [])


# ── sector rotation from the mirror's pushed tickers ─────────────────────────
def sector_rotation(*, min_members: int = 3, min_quote_volume: float = 1e6) -> list[dict]:
    """Per-sector average 24h %change over liquid members (from the WS mirror). Ranked hot→cold.
    Binance classifies; Binance pushes the prices; we just average. Cheap RAM once products cached."""
    if not enabled():
        return []
    bt = _base_tags()
    try:
        from trading.broker_sense.binance_stream import get_mirror
        rows = get_mirror().futures_rows(min_quote_volume=min_quote_volume)
    except Exception:
        rows = []
    agg: dict = {}
    for r in rows:
        base = _base_of(r.get("raw") or "")
        pc = r.get("pct_change")
        if pc is None:
            continue
        for tag in bt.get(base, []):
            a = agg.setdefault(tag, {"sum": 0.0, "n": 0})
            a["sum"] += pc
            a["n"] += 1
    out = [{"sector": t, "avg_pct_change": round(a["sum"] / a["n"], 3), "members": a["n"]}
           for t, a in agg.items() if a["n"] >= min_members]
    out.sort(key=lambda x: x["avg_pct_change"], reverse=True)
    return out


def sector_signal(symbol: str) -> dict:
    """Sector-rotation read for one symbol: its tags, its strongest-momentum sector, and a bounded
    directional tilt in [-1,1] from that sector's average move. +1 = sector broadly up (long-favourable)."""
    tags = tags_for(symbol)
    out = {"symbol": _base_of(symbol), "tags": tags, "sector": None,
           "sector_momentum": None, "tilt": None}
    if not tags:
        return out
    rot = {r["sector"]: r for r in sector_rotation(min_members=2)}   # 2 = still meaningful for niche sectors
    mine = [rot[t] for t in tags if t in rot]
    if not mine:
        return out
    top = max(mine, key=lambda r: abs(r["avg_pct_change"]))    # the symbol's most-moving sector
    out["sector"] = top["sector"]
    out["sector_momentum"] = top["avg_pct_change"]
    out["tilt"] = max(-1.0, min(1.0, top["avg_pct_change"] / 5.0))   # ±5% sector move → full tilt
    return out


def clear_cache() -> None:
    with _lock:
        _cache.clear()
