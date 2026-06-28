"""Crypto on-chain intelligence: SOPR, MVRV (z-score), Fear & Greed.

Phase-T8 (deferred). OFFLINE-TESTABLE + GATED via an injected ``fetcher``.

Design
------
- Network is *only* touched when a default live fetcher is actually called.
- Tests inject a deterministic stub ``fetcher`` -> no network, no new deps.
- Every live fetcher is wrapped in try/except and degrades to ``{}`` on any
  failure, so the public methods stay honest via ``available`` flags.

A ``fetcher`` is any callable ``fetcher(kind: str) -> dict`` where ``kind`` is
one of ``"fear_greed"``, ``"sopr"``, ``"mvrv"``. Returning ``{}`` (or junk)
means "not available" and the caller reports ``available=False``.

Secrets are read from the environment only (never hardcoded).

Free sources wired by the default live fetcher:
- Fear & Greed: https://api.alternative.me/fng/
- SOPR / MVRV: https://bitcoin-data.com  (free, no key)
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, Optional

import requests

# Generous client-side timeout; live calls only happen when explicitly invoked.
_TIMEOUT = 10

FNG_URL = "https://api.alternative.me/fng/"
# bitcoin-data.com exposes free "last" endpoints for on-chain ratios.
SOPR_URL = "https://bitcoin-data.com/v1/sopr/last"
MVRV_URL = "https://bitcoin-data.com/v1/mvrv-zscore/last"


def _safe_float(value: Any) -> Optional[float]:
    """Coerce ``value`` to float, or ``None`` if impossible."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _default_live_fetcher(kind: str) -> Dict[str, Any]:
    """Hit FREE public sources. Returns ``{}`` on ANY failure (honest gate)."""
    headers = {"User-Agent": "ml-network-brain/onchain"}
    # An API key is supported but never required for these free endpoints.
    api_key = os.environ.get("BITCOINDATA_API_KEY")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        if kind == "fear_greed":
            resp = requests.get(FNG_URL, timeout=_TIMEOUT, headers=headers)
            resp.raise_for_status()
            return resp.json() or {}
        if kind == "sopr":
            resp = requests.get(SOPR_URL, timeout=_TIMEOUT, headers=headers)
            resp.raise_for_status()
            return resp.json() or {}
        if kind == "mvrv":
            resp = requests.get(MVRV_URL, timeout=_TIMEOUT, headers=headers)
            resp.raise_for_status()
            return resp.json() or {}
    except Exception:
        return {}
    return {}


class OnChainMetrics:
    """Crypto on-chain signals with honest availability gating.

    Parameters
    ----------
    fetcher:
        Optional callable ``fetcher(kind) -> dict``. When ``None`` a default
        live fetcher (free public sources) is used. Inject a stub in tests for
        deterministic, offline behaviour.
    """

    def __init__(self, fetcher: Optional[Callable[[str], Dict[str, Any]]] = None) -> None:
        self._fetch = fetcher if fetcher is not None else _default_live_fetcher

    # -- individual signals -------------------------------------------------
    def fear_greed(self) -> Dict[str, Any]:
        """Crypto Fear & Greed index -> {value:0-100, label, available}."""
        raw = self._safe_call("fear_greed")
        value: Optional[float] = None
        label: Optional[str] = None

        # alternative.me shape: {"data": [{"value": "40", "value_classification": "Fear"}]}
        data = raw.get("data") if isinstance(raw, dict) else None
        if isinstance(data, list) and data:
            entry = data[0] if isinstance(data[0], dict) else {}
            value = _safe_float(entry.get("value"))
            label = entry.get("value_classification") or entry.get("label")
        elif isinstance(raw, dict):
            # tolerate a flat stub shape too
            value = _safe_float(raw.get("value"))
            label = raw.get("label") or raw.get("value_classification")

        available = value is not None
        if available and label is None:
            label = self._fng_label(value)
        return {
            "value": value,
            "label": label,
            "available": available,
        }

    def sopr(self) -> Dict[str, Any]:
        """Spent Output Profit Ratio -> {value, signal, available}.

        SOPR > 1 => coins moving in profit (profit-taking).
        SOPR < 1 => coins moving at a loss (capitulation).
        """
        raw = self._safe_call("sopr")
        value = self._extract_value(raw, ("sopr", "value", "d"))
        available = value is not None
        signal = None
        if available:
            signal = "profit-taking" if value >= 1.0 else "capitulation"
        return {
            "value": value,
            "signal": signal,
            "available": available,
        }

    def mvrv(self) -> Dict[str, Any]:
        """MVRV (Market-Value-to-Realized-Value) z-score.

        -> {value, zscore, signal, available}. High z-score => overvalued
        (market top zone); low/negative z-score => undervalued (bottom zone).
        """
        raw = self._safe_call("mvrv")
        zscore = self._extract_value(raw, ("mvrvZscore", "zscore", "z", "value", "d"))
        value = self._extract_value(raw, ("mvrv", "ratio", "value"))
        if value is None:
            value = zscore
        available = zscore is not None
        signal = None
        if available:
            # Conventional MVRV z-score zones: >7 euphoria/top, <0 bottom.
            if zscore >= 3.0:
                signal = "overvalued"
            elif zscore <= 0.0:
                signal = "undervalued"
            else:
                signal = "neutral"
        return {
            "value": value,
            "zscore": zscore,
            "signal": signal,
            "available": available,
        }

    # -- combined -----------------------------------------------------------
    def report(self) -> Dict[str, Any]:
        """JSON-able combined dict with honest ``available`` flags."""
        fg = self.fear_greed()
        sp = self.sopr()
        mv = self.mvrv()
        return {
            "fear_greed": fg,
            "sopr": sp,
            "mvrv": mv,
            "available": bool(fg["available"] or sp["available"] or mv["available"]),
        }

    # -- helpers ------------------------------------------------------------
    def _safe_call(self, kind: str) -> Dict[str, Any]:
        try:
            out = self._fetch(kind)
        except Exception:
            return {}
        return out if isinstance(out, dict) else {}

    @staticmethod
    def _extract_value(raw: Dict[str, Any], keys: tuple) -> Optional[float]:
        """Pull the first parseable numeric value from ``raw`` for ``keys``.

        Tolerates flat dicts and ``{"data": {...}}`` / ``{"data": [{...}]}``.
        """
        candidates = [raw]
        if isinstance(raw, dict):
            d = raw.get("data")
            if isinstance(d, dict):
                candidates.append(d)
            elif isinstance(d, list) and d and isinstance(d[0], dict):
                candidates.append(d[0])
        for cand in candidates:
            if not isinstance(cand, dict):
                continue
            for key in keys:
                if key in cand:
                    val = _safe_float(cand[key])
                    if val is not None:
                        return val
        return None

    @staticmethod
    def _fng_label(value: float) -> str:
        if value < 25:
            return "Extreme Fear"
        if value < 45:
            return "Fear"
        if value < 55:
            return "Neutral"
        if value < 75:
            return "Greed"
        return "Extreme Greed"
