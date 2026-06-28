"""Leverage liquidation heatmap aggregation.

Phase-T8 (deferred). OFFLINE-TESTABLE + GATED via an injected ``fetcher``.

Design
------
- Network is *only* touched when the default live fetcher is actually called.
- Tests inject a deterministic stub ``fetcher`` -> no network, no new deps.
- Coinglass (the canonical liquidation-heatmap source) requires an API key for
  most routes. Without ``COINGLASS_API_KEY`` the default fetcher returns ``{}``
  and the public methods honestly report ``available=False``.

A ``fetcher`` is any callable ``fetcher(symbol: str) -> dict`` returning either
``{"levels": [{"price", "notional", "side"}, ...]}`` or ``{}`` when no data /
no key is available.

Secrets are read from the environment only (never hardcoded).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import requests

_TIMEOUT = 10

# Coinglass-style liquidation endpoint (key-gated). Shape may evolve; the
# fetcher normalises whatever it gets and degrades to {} on any error.
COINGLASS_URL = "https://open-api-v3.coinglass.com/api/futures/liquidation/heatmap"


def _safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _default_live_fetcher(symbol: str) -> Dict[str, Any]:
    """Hit a Coinglass-style endpoint. Returns ``{}`` without a key or on error."""
    api_key = os.environ.get("COINGLASS_API_KEY")
    if not api_key:
        # Honest gate: most liquidation routes need a key.
        return {}
    try:
        resp = requests.get(
            COINGLASS_URL,
            params={"symbol": symbol},
            headers={
                "accept": "application/json",
                "CG-API-KEY": api_key,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json() or {}
    except Exception:
        return {}


class LiquidationHeatmap:
    """Aggregate leverage-liquidation levels into a heatmap.

    Parameters
    ----------
    fetcher:
        Optional callable ``fetcher(symbol) -> dict``. When ``None`` a default
        live (key-gated) fetcher is used. Inject a stub in tests for
        deterministic, offline behaviour.
    """

    def __init__(self, fetcher: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
        self._fetch = fetcher if fetcher is not None else _default_live_fetcher

    # -- core ---------------------------------------------------------------
    def heatmap(self, symbol: str) -> Dict[str, Any]:
        """-> {symbol, levels:[{price, notional, side}], available}."""
        raw = self._safe_call(symbol)
        levels = self._normalize_levels(raw)
        return {
            "symbol": symbol,
            "levels": levels,
            "available": bool(levels),
        }

    def clusters(self, symbol: str, n: int = 5) -> Dict[str, Any]:
        """Top ``n`` liquidation-magnet price clusters by notional.

        -> {symbol, clusters:[{price, notional, side}], available}.
        """
        levels = self.heatmap(symbol)["levels"]
        ranked = sorted(levels, key=lambda lv: lv.get("notional") or 0.0, reverse=True)
        top = ranked[: max(0, int(n))]
        return {
            "symbol": symbol,
            "clusters": top,
            "available": bool(top),
        }

    def nearest_cluster(self, symbol: str, price: float) -> Dict[str, Any]:
        """Nearest big liquidation level to ``price``.

        -> {symbol, price, cluster, distance, available}.
        """
        ref = _safe_float(price)
        # Consider the meaningful magnets (top clusters), not every micro-level.
        magnets = self.clusters(symbol, n=10)["clusters"]
        if ref is None or not magnets:
            return {
                "symbol": symbol,
                "price": ref,
                "cluster": None,
                "distance": None,
                "available": False,
            }
        nearest = min(
            magnets,
            key=lambda lv: abs((lv.get("price") or 0.0) - ref),
        )
        distance = abs((nearest.get("price") or 0.0) - ref)
        return {
            "symbol": symbol,
            "price": ref,
            "cluster": nearest,
            "distance": distance,
            "available": True,
        }

    def status(self) -> Dict[str, Any]:
        """JSON-able config/availability status (no network for live mode)."""
        is_default = self._fetch is _default_live_fetcher
        has_key = bool(os.environ.get("COINGLASS_API_KEY"))
        return {
            "source": "coinglass" if is_default else "injected",
            "endpoint": COINGLASS_URL if is_default else None,
            "has_api_key": has_key,
            # Injected fetchers are assumed usable; live needs a key.
            "available": (not is_default) or has_key,
        }

    # -- helpers ------------------------------------------------------------
    def _safe_call(self, symbol: str) -> Dict[str, Any]:
        try:
            out = self._fetch(symbol)
        except Exception:
            return {}
        return out if isinstance(out, dict) else {}

    @staticmethod
    def _normalize_levels(raw: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Normalise assorted shapes into ``[{price, notional, side}]``."""
        if not isinstance(raw, dict):
            return []
        rows = raw.get("levels")
        if rows is None:
            data = raw.get("data")
            if isinstance(data, dict):
                rows = data.get("levels") or data.get("liquidations")
            elif isinstance(data, list):
                rows = data
        if not isinstance(rows, list):
            return []

        out: List[Dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            price = _safe_float(row.get("price"))
            notional = _safe_float(
                row.get("notional")
                if row.get("notional") is not None
                else row.get("amount") if row.get("amount") is not None
                else row.get("volume")
            )
            if price is None or notional is None:
                continue
            side = row.get("side") or row.get("type")
            if side not in ("long", "short"):
                # Infer if encoded numerically/otherwise; default unknown.
                side = side if isinstance(side, str) else "unknown"
            out.append({"price": price, "notional": notional, "side": side})
        return out
