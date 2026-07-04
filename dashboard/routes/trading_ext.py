"""Extracted trading HTTP routes (dashboard/server.py split — Wave0-⑤ Group 2).

Same pattern + ``_srv(h)`` accessor as dashboard/routes/brain_ext.py: ``self.X`` → ``h.X`` and any
bare server module-level helper/global (``_trading_session``, ``_crypto_session``, ``_PRACTICE``,
``_bg_snapshot``, ``_cached_body``, ``_CT_CACHE``/``_CT_LOCK``, ``PREDICTION_COLUMNS``…) → ``_srv(h).X``
so a moved body reaches the SAME live singletons/caches/locks the inline code did (server runs as
``__main__``; a plain ``from dashboard.server import …`` would bind a duplicate module copy). Behavior
stays shape-identical — every moved route is diffed against a pre-move baseline.
"""
import json
import sys


def _srv(h):
    """The live server module, resolved off the handler instance — see brain_ext._srv for why."""
    return sys.modules[h.__class__.__module__]


def handle_practice(h):
    """GET /api/trading/practice — practice mode: brain trades HISTORIC data (trading/practice.py)."""
    try:
        from data.downloads import list_nse_dump_symbols
        from trading.practice import list_runs
        proc = _srv(h)._PRACTICE.get("proc")
        body = json.dumps({
            "runs": list_runs(),
            "running": proc is not None and proc.poll() is None,
            "nse_symbols": list_nse_dump_symbols(),
        }).encode()
    except Exception as e:
        body = json.dumps({"note": f"practice unavailable: {e}",
                           "runs": [], "nse_symbols": []}).encode()
    return h._send(200, body, "application/json")


def handle_venues(h):
    """GET /api/trading/venues — multi-venue market-DATA pool telemetry (ban-proofing): per-venue
    calls/errors/budget/ban-cooldown across binance/bybit/okx/kucoin. Read-only."""
    try:
        from trading.crypto.exchange_pool import all_pools_status
        blob = all_pools_status()
    except Exception as e:
        blob = {"enabled": None, "pools": [], "error": str(e)[:120]}
    return h._send(200, json.dumps(blob).encode(), "application/json")


def handle_brain_discovery(h):
    """GET /api/trading/brain/discovery — Concept Discovery Engine: last run's self-invented
    features + concept manifold (read-only; POST /run triggers a fresh discovery)."""
    try:
        from trading.brain.discovery import ConceptDiscoveryEngine
        blob = ConceptDiscoveryEngine.load()
    except Exception as e:
        blob = {"features": [], "manifold": {"points": [], "n_clusters": 0},
                "stats": {}, "error": str(e)[:120]}
    return h._send(200, json.dumps(blob).encode(), "application/json")


def handle_status(h):
    """GET /api/trading/status — honest trading status: real OpenAlgo connectivity + toggle/feed/
    watchlist. Lazy import so the dashboard still serves if the trading deps are absent."""
    try:
        body = json.dumps(_srv(h)._trading_session().status()).encode()
    except Exception as e:
        body = json.dumps({
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Trading T1 not configured — set OPENALGO_API_KEY in .env "
                    "and start the OpenAlgo server (see trading-execution-blueprint.md).",
        }).encode()
    return h._send(200, body, "application/json")


def handle_crypto_status(h):
    """GET /api/trading/crypto/status — honest crypto status: one CryptoSession + the Freqtrade
    engine state alongside it. Degrades to an error payload (never crashes the dashboard)."""
    try:
        snap = _srv(h)._crypto_session().status()
    except Exception as e:
        snap = {
            "available": False,
            "error": f"{type(e).__name__}: {e}",
            "hint": "Crypto T2 not ready — pip install ccxt; optionally set "
                    "CRYPTO_EXCHANGES in .env (see trading-execution-blueprint.md §7 T2).",
        }
    # Additive (T-split B): report the Freqtrade engine state alongside the legacy crypto session,
    # so the migration is honestly visible. Best-effort — never crashes.
    try:
        from trading.crypto.engine_client import CryptoEngineClient
        snap["engine"] = CryptoEngineClient().as_status()
    except Exception as e:
        snap["engine"] = {
            "engine": "freqtrade", "connected": False,
            "detail": f"{type(e).__name__}: {e}",
            "hint": "Freqtrade not ready — pip install freqtrade freqtrade-client; "
                    "start a bot with api_server enabled (see research/trading-engine-split.md).",
        }
    body = json.dumps(snap, default=str).encode()
    return h._send(200, body, "application/json")


def handle_crypto_markets(h):
    """GET /api/trading/crypto/markets — Binance-style live markets/screener feed the brain picks
    from. Query: segment(perp|spot), sort(volume|movers|gainers|losers|volatility|funding|price),
    limit, q."""
    from urllib.parse import parse_qs, urlparse
    qs = parse_qs(urlparse(h.path).query)
    g = lambda k, d="": (qs.get(k, [d])[0])
    try:
        from trading.crypto.markets import live_markets
        rows = live_markets(segment=g("segment", "perp"), sort=g("sort", "volume"),
                            limit=int(g("limit", "80") or 80), search=g("q", ""))
        out = {"rows": rows, "n": len(rows), "segment": g("segment", "perp"), "sort": g("sort", "volume")}
    except Exception as e:
        out = {"rows": [], "error": f"{type(e).__name__}: {e}"}
    return h._send(200, json.dumps(out, default=str).encode(), "application/json")
