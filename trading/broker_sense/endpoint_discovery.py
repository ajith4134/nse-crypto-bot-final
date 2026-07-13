"""trading/broker_sense/endpoint_discovery.py — surface UNMAPPED web-app data endpoints (adopt item 4).

The report's item 4 suggested mitmproxy2swagger to auto-map the data endpoints the broker web apps
call. Map-first finding: `interception.py` ALREADY captures every endpoint the logged-in Binance/
Upstox apps hit into `broker_endpoints.json` (URL pattern → kind → n_seen → sample_keys) — an
IN-BROWSER registry that is strictly richer than a mitmproxy flow dump (it sees the app's real
authenticated calls, already classified). So instead of a redundant proxy tool, this reads that
registry and answers the actionable question: *which endpoints are we SEEING a lot but NOT yet
capturing into ui_market/ui_data?* — i.e. the candidate new data surfaces to wire next.

For each broker it buckets endpoints into: MAPPED (a data kind the doors already consume), CANDIDATE
(unknown kind but data-shaped: JSON, market-ish sample keys, real traffic — worth capturing), and
NOISE (analytics/telemetry hosts). CANDIDATEs are ranked by traffic so the highest-value surface to
add is first. Read-only, offline, no network. CLI: `python -m trading.broker_sense.endpoint_discovery`.
"""
from __future__ import annotations

import json
from typing import Any

from trading import state

# Data kinds the ui_market / ui_data doors already consume — an endpoint mapped to one of these is
# already captured (kept in sync with interception._KIND_RULES + ui_market kinds).
_MAPPED_KINDS = {
    "ticker", "orderbook", "mark_price", "index_price", "open_interest", "long_short",
    "long_short_smart", "taker_volume", "option_chain", "recent_trades", "movers", "basis",
    "screener", "liquidation", "candles", "kline", "funding", "quote", "depth", "positions",
    "balance", "orders", "trades",
}
# Analytics / telemetry / error-reporting hosts — traffic, but never MARKET data.
_NOISE_HOSTS = (
    "mixpanel", "sentry", "google-analytics", "googletagmanager", "doubleclick", "clarity.ms",
    "amplitude", "segment.io", "datadog", "newrelic", "hotjar", "facebook", "cloudflareinsights",
    "gstatic", "fonts.googleapis", "recaptcha", "appsflyer", "branch.io", "fullstory", "optimizely",
)
# Sample-key hints that a JSON body carries MARKET data (worth capturing).
_MARKET_KEY_HINTS = {
    "ltp", "last", "price", "bid", "ask", "bids", "asks", "open", "high", "low", "close",
    "volume", "oi", "openinterest", "iv", "delta", "gamma", "theta", "vega", "strike",
    "expiry", "funding", "mark", "index", "change", "pct", "pchange", "symbol", "instrument",
    "candles", "ohlc", "depth", "quote", "greeks",
}


def _is_noise(pattern: str) -> bool:
    p = pattern.lower()
    return any(h in p for h in _NOISE_HOSTS)


def _looks_like_market_data(row: dict) -> bool:
    ct = str(row.get("content_type") or "").lower()
    if "json" not in ct and "protobuf" not in ct and "octet-stream" not in ct:
        return False
    keys = {str(k).lower() for k in (row.get("sample_keys") or [])}
    # require >=2 distinct market-key hints: a real quote/candle/chain body carries several
    # (bid+ask+last, o+h+l+c, strike+iv+delta…), so a lone generic word like a "close" button
    # label on a KYC page never trips a false candidate.
    return len(keys & _MARKET_KEY_HINTS) >= 2


def discover(broker: str | None = None, *, min_seen: int = 2) -> dict:
    """Bucket each broker's captured endpoints into mapped / candidate / noise. `candidate` =
    the unmapped, data-shaped endpoints (ranked by n_seen) we could START capturing."""
    reg = state.load_json("broker_endpoints.json", {})
    out: dict[str, Any] = {}
    for bk, endpoints in reg.items():
        if broker and bk.lower() != broker.lower():
            continue
        if not isinstance(endpoints, dict):
            continue
        mapped, candidate, noise = [], [], []
        for pattern, row in endpoints.items():
            if not isinstance(row, dict):
                continue
            kind = str(row.get("kind") or "unknown")
            n = int(row.get("n_seen") or 0)
            rec = {"pattern": pattern, "kind": kind, "n_seen": n,
                   "content_type": row.get("content_type"),
                   "sample_keys": (row.get("sample_keys") or [])[:12]}
            if _is_noise(pattern):
                noise.append(rec)
            elif kind in _MAPPED_KINDS:
                mapped.append(rec)
            elif n >= min_seen and _looks_like_market_data(row):
                candidate.append(rec)             # unmapped BUT data-shaped → wire it next
            else:
                noise.append(rec)                 # unknown + not data-shaped → ignore
        candidate.sort(key=lambda r: -r["n_seen"])
        mapped.sort(key=lambda r: -r["n_seen"])
        out[bk] = {"mapped": mapped, "candidates": candidate, "noise_count": len(noise),
                   "n_candidates": len(candidate), "n_mapped": len(mapped)}
    return out


def report(broker: str | None = None) -> str:
    """Human-readable discovery report for the CLI / a dashboard tile."""
    data = discover(broker)
    lines = ["# Endpoint discovery — unmapped web-app data surfaces\n"]
    if not data:
        return "no captured endpoints yet (broker_endpoints.json empty)."
    for bk, d in data.items():
        lines.append(f"## {bk}  — {d['n_mapped']} mapped, {d['n_candidates']} CANDIDATE, "
                     f"{d['noise_count']} noise")
        if d["candidates"]:
            lines.append("  CANDIDATES to capture next (unmapped but data-shaped, by traffic):")
            for c in d["candidates"][:15]:
                lines.append(f"    • [{c['n_seen']:>4}×] {c['pattern']}  "
                             f"keys={c['sample_keys']}")
        else:
            lines.append("  (no unmapped data-shaped endpoints — coverage looks complete)")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    print(report(sys.argv[1] if len(sys.argv) > 1 else None))
