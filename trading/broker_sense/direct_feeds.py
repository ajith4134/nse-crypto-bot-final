"""trading/broker_sense/direct_feeds.py — record market-data routes for WEBSOCKET-ONLY feeds that a
headless browser can't surface, so the App Driving School still reaches 100% coverage — honestly.

Why this exists: some market-data kinds are streamed ONLY over a websocket that the exchange's WEB
app does not open under headless automation. Verified live (2026-07-06): Binance's web futures page
polls REST (`api/v3/depth`) for the order book/ticker but opens NO websocket in headless Chromium, so
the liquidation feed (`!forceOrder@arr`) never appears in the browser's traffic and the school can't
learn it from the page.

The public feed itself is real and reachable from this box. So we stay GROUNDED exactly like the
browser school does — we record a route ONLY after observing a REAL event on the verified public
feed (never a hardcoded guess). Provenance is honest: `via="direct-ws"`, `source="direct_feed"`, so
the dashboard shows the route was grounded on the direct feed, not discovered in the app's own UI.

    from trading.broker_sense.direct_feeds import verify_and_record
    verify_and_record("binance", "liquidation", app_map)   # blocks until a real event or timeout
"""
from __future__ import annotations

import asyncio
import json

# (broker, kind) -> the canonical PUBLIC websocket feed + how to recognise a real event on it.
DIRECT_FEEDS = {
    ("binance", "liquidation"): {
        "url": "wss://fstream.binance.com/ws/!forceOrder@arr",
        # a real all-market liquidation frame looks like {"e":"forceOrder","o":{...}}
        "event_ok": lambda d: isinstance(d, dict) and d.get("e") == "forceOrder",
        "label": "Binance USDⓈ-M all-market liquidation stream (web app doesn't open it headless)",
    },
}


async def _await_event(url: str, event_ok, timeout_s: float):
    """Connect and return the first frame that passes event_ok, or None on timeout/error."""
    try:
        import websockets
    except Exception:
        return None
    try:
        async with websockets.connect(url, ping_interval=None, open_timeout=15) as ws:
            loop = asyncio.get_event_loop()
            deadline = loop.time() + timeout_s
            while loop.time() < deadline:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=max(1.0, deadline - loop.time()))
                except asyncio.TimeoutError:
                    return None
                try:
                    d = json.loads(raw)
                except Exception:
                    continue
                if event_ok(d):
                    return d
    except Exception:
        return None
    return None


def has_feed(broker: str, kind: str) -> bool:
    return (broker, kind) in DIRECT_FEEDS


def verify_and_record(broker: str, kind: str, app_map, *, timeout_s: float = 70.0) -> bool:
    """Listen on the verified public feed; on the first REAL event, record the route in `app_map`
    (grounded — never records without observing an event). Returns True if the route was recorded.
    Safe to call from sync code (spins its own event loop). Never raises."""
    spec = DIRECT_FEEDS.get((broker, kind))
    if spec is None:
        return False
    try:
        ev = asyncio.run(_await_event(spec["url"], spec["event_ok"], timeout_s))
    except Exception:
        ev = None
    if ev is None:
        return False                       # no real event observed → stay honest, record nothing
    try:
        app_map.record(broker, kind, url=spec["url"], via="direct-ws", endpoint=spec["url"])
        # tag provenance so the dashboard is honest about how this route was grounded
        r = app_map.routes.get(broker, {}).get(kind)
        if r is not None:
            r["source"] = "direct_feed"
            r["note"] = spec["label"]
        app_map.save()
        return True
    except Exception:
        return False
