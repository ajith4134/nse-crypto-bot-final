"""trading/broker_sense/binance_ai_select.py — Binance's built-in "AI Select" recommendations (P3+).

The owner asked to use Binance's web AI Select (Markets → AI Select) — its built-in function. It has
no documented API, so we discovered the REAL endpoint the page itself calls via browser network
interception (the app_school / interception pattern), then read it directly — reliable, free, no
brittle DOM scrape:

    GET bapi/apex/v1/friendly/apex/web/opportunity/recommended-assets?type=<type>

Binance returns RANKED recommended assets by type: `sentiment` (crowd/news lean, e.g. ETH/BTC/SOL)
and `technical` (its AI/technical picks, e.g. SKL/ATM/RLC). We merge them into a ranked pick list the
funnel can prioritise, plus a per-symbol flag for fusion. TTL-cached (~5m). Kill: BINANCE_AI_SELECT=0.
"""
from __future__ import annotations

import json
import os
import threading
import time
import urllib.request

_URL = ("https://www.binance.com/bapi/apex/v1/friendly/apex/web/opportunity/"
        "recommended-assets?type={type}&interval=")
_TYPES = ("sentiment", "technical")
_TTL = float(os.getenv("BINANCE_AI_SELECT_TTL", "300") or 300)
_cache: dict = {}
_lock = threading.Lock()


def enabled() -> bool:
    return os.getenv("BINANCE_AI_SELECT", "1").strip().lower() not in ("0", "false", "off")


def _get_json(url: str):
    """GET+parse; isolated for test monkeypatch. Never raises."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "clienttype": "web"})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except Exception:
        return None


def _items(typ: str) -> list[dict]:
    key = f"ai:{typ}"
    now = time.time()
    with _lock:
        hit = _cache.get(key)
        if hit and now - hit[0] <= _TTL:
            return hit[1]
    d = _get_json(_URL.format(type=typ))
    items = ((d or {}).get("data") or {}).get("items") if isinstance(d, dict) else None
    if items:
        with _lock:
            _cache[key] = (now, items)
        return items
    with _lock:
        hit = _cache.get(key)
        return hit[1] if hit else []


def picks() -> list[dict]:
    """Merged ranked AI-Select picks across types. Each: {base, symbol, types, best_rank}. Best first."""
    if not enabled():
        return []
    merged: dict = {}
    for typ in _TYPES:
        for it in _items(typ):
            base = (it.get("baseAsset") or it.get("asset") or "").upper()
            if not base:
                continue
            rank = it.get("rank")
            m = merged.setdefault(base, {"base": base, "symbol": f"{base}/USDT:USDT",
                                         "types": [], "best_rank": 999})
            if typ not in m["types"]:
                m["types"].append(typ)
            if isinstance(rank, int) and rank < m["best_rank"]:
                m["best_rank"] = rank
    out = list(merged.values())
    out.sort(key=lambda x: (x["best_rank"], -len(x["types"])))
    return out


def selected_bases() -> set:
    return {p["base"] for p in picks()}


def is_ai_selected(symbol: str) -> dict:
    """Per-symbol AI-Select flag for fusion. {ai_selected, ai_rank, ai_types}. Honest False when absent."""
    base = (symbol or "").upper().replace("/", "").split(":")[0]
    for q in ("USDT", "USDC", "BUSD", "FDUSD"):
        if base.endswith(q):
            base = base[: -len(q)]
            break
    out = {"symbol": base, "ai_selected": False, "ai_rank": None, "ai_types": []}
    if not enabled():
        return out
    for p in picks():
        if p["base"] == base:
            out.update(ai_selected=True, ai_rank=p["best_rank"], ai_types=p["types"])
            break
    return out


def clear_cache() -> None:
    with _lock:
        _cache.clear()
