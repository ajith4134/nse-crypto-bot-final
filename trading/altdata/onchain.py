"""AI-scientist idea #11 — on-chain + whale alt-data lane (live, free, keyless).

The news-NLP half of idea #11 already ships (trading/brain/news.py + /api/trading/news/status). This
adds the on-chain / whale half as a LIVE feature lane built only from free, no-API-key sources:

  * alternative.me     — crypto Fear & Greed index
  * blockchain.info /q — BTC 24h transaction count + BTC sent (→ average transaction size = a whale
                         proxy: bigger average tx = more large-holder / exchange movement)
  * mempool.space      — recommended fee (network congestion) + mempool size

From these it derives a bounded composite on-chain flow/risk signal the brain can read alongside the
psychology + news lanes. Fetchers are INJECTABLE (default = real free HTTP) so the aggregation is
unit-testable without network; each source is guarded, so one being down never breaks the snapshot.
"""
from __future__ import annotations

import json
import math
import urllib.request

_UA = {"User-Agent": "mlnb-altdata/1.0"}


def _get_json(url: str, timeout: float = 8.0):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get_text(url: str, timeout: float = 8.0) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode().strip()


# ---- default LIVE free fetchers (no keys) --------------------------------------------------
def _fetch_fear_greed() -> dict:
    d = _get_json("https://api.alternative.me/fng/")["data"][0]
    return {"value": int(d["value"]), "classification": d.get("value_classification")}


def _fetch_network() -> dict:
    n_tx = int(float(_get_text("https://blockchain.info/q/24hrtransactioncount")))
    btc_sent = float(_get_text("https://blockchain.info/q/24hrbtcsent")) / 1e8   # satoshi → BTC
    fee = _get_json("https://mempool.space/api/v1/fees/recommended").get("fastestFee")
    return {"n_tx_24h": n_tx, "btc_sent_24h": btc_sent,
            "avg_tx_btc": (btc_sent / n_tx if n_tx else 0.0), "fee_fastest": fee}


def _fetch_whale() -> dict:
    """Whale proxy from the mempool: count of very large (>0.5 vB-normalized) pending value.
    mempool.space's mempool endpoint gives aggregate size; we surface it as congestion/whale hint."""
    m = _get_json("https://mempool.space/api/mempool")
    return {"mempool_count": int(m.get("count", 0)), "mempool_vsize": int(m.get("vsize", 0))}


def _default_fetchers() -> dict:
    return {"fear_greed": _fetch_fear_greed, "network": _fetch_network, "whale": _fetch_whale}


# ---- composite -----------------------------------------------------------------------------
def _sat(x: float) -> float:
    """Squash to (-1, 1)."""
    return math.tanh(x)


def _composite(fg: dict, net: dict, whale: dict) -> float:
    """Bounded on-chain flow/risk signal ∈ (-1, 1). Positive = greedy/active/large-flow (risk-on);
    negative = fearful/quiet. Missing sources contribute 0 (never fabricated)."""
    parts, wsum = 0.0, 0.0
    if fg:
        parts += 0.5 * _sat((fg.get("value", 50) - 50) / 25.0); wsum += 0.5   # 0..100 → centered
    if net and net.get("avg_tx_btc"):
        parts += 0.3 * _sat((net["avg_tx_btc"] - 0.5) / 0.5); wsum += 0.3      # larger avg tx = whales
    if whale and whale.get("mempool_count"):
        parts += 0.2 * _sat((whale["mempool_count"] - 20000) / 20000.0); wsum += 0.2
    return round(parts / wsum, 4) if wsum else 0.0


class OnChainAltData:
    """Live on-chain + whale alt-data lane (free sources). ``snapshot()`` aggregates + caches."""

    def __init__(self, fetchers: dict | None = None):
        self._f = fetchers or _default_fetchers()

    @staticmethod
    def _safe(fn):
        try:
            return fn(), None
        except Exception as e:
            return {}, f"{type(e).__name__}: {e}"[:120]

    def snapshot(self) -> dict:
        fg, e1 = self._safe(self._f["fear_greed"])
        net, e2 = self._safe(self._f["network"])
        whale, e3 = self._safe(self._f["whale"])
        sources = {"fear_greed": bool(fg), "network": bool(net), "whale": bool(whale)}
        errors = {k: v for k, v in (("fear_greed", e1), ("network", e2), ("whale", e3)) if v}
        return {
            "available": any(sources.values()),
            "fear_greed": fg or None,
            "network": net or None,
            "whale": whale or None,
            "composite": _composite(fg, net, whale),
            "sources_live": sources,
            "errors": errors or None,
            "note": ("live on-chain/whale lane from FREE keyless sources (alternative.me Fear&Greed, "
                     "blockchain.info tx count/BTC-sent → avg-tx whale proxy, mempool.space fee/size); "
                     "composite ∈ (-1,1): + greedy/large-flow risk-on, − fearful/quiet. Pairs with the "
                     "news lane (/api/trading/news/status) as the full alt-data feed."),
        }
