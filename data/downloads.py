"""CORTEX B6 — real market-data downloaders (research/ultra-network-data-plan.md).

Never data-gate: fetch the real series. Sources chosen to avoid the cloud-IP blocks the
data plan documents (yfinance 429s from GCP; nselib chain IP-blocked):

  * crypto 1m/…  — Binance public archive via the existing data.binance.fetch_klines
                   (public CDN, zero rate-budget) + a locator for the freqtrade on-disk
                   dump the plan says is already present (416 pairs × many TFs).
  * daily equity/index — stooq public CSV endpoint (no key, no yfinance).
  * EUR/USD daily — stooq `eurusd` (dukascopy hourly is a later, heavier lane).

Everything lands under data/cache/ on disk immediately (persist-findings discipline).
"""
from __future__ import annotations

import csv
import io
import os
import urllib.request

import numpy as np

_CACHE = os.path.join(os.path.dirname(__file__), "cache")
_STOOQ = "https://stooq.com/q/d/l/?s={sym}&i=d"
_UA = {"User-Agent": "Mozilla/5.0 (cortex-datafetch)"}

__all__ = ["download_stooq_daily", "download_binance", "locate_freqtrade_1m",
           "cached_path"]


def _ensure_cache() -> str:
    os.makedirs(_CACHE, exist_ok=True)
    return _CACHE


def cached_path(name: str) -> str:
    return os.path.join(_ensure_cache(), name)


# ── stooq daily (public CSV, no key, cloud-IP friendly) ──────────────────────
def download_stooq_daily(symbol: str, *, save: bool = True, timeout: int = 30) -> dict:
    """Download a daily OHLCV series from stooq. `symbol` e.g. 'spy.us', 'eurusd', '^ndq'.

    Returns {'symbol','dates','open','high','low','close','volume','path'} with numpy
    arrays. Raises on an empty/blocked response (never returns a silent stub).
    """
    url = _STOOQ.format(sym=urllib.parse.quote(symbol.lower()))
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        text = r.read().decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows or "Close" not in (rows[0] if rows else {}):
        raise RuntimeError(f"stooq returned no data for {symbol!r} "
                           f"(first 80 chars: {text[:80]!r})")
    cols = {k: [] for k in ("Date", "Open", "High", "Low", "Close", "Volume")}
    for row in rows:
        for k in cols:
            cols[k].append(row.get(k, ""))
    out = {
        "symbol": symbol,
        "dates": np.array(cols["Date"]),
        "open": np.array(cols["Open"], dtype=float),
        "high": np.array(cols["High"], dtype=float),
        "low": np.array(cols["Low"], dtype=float),
        "close": np.array(cols["Close"], dtype=float),
        "volume": np.array([float(v) if v not in ("", "N/A") else 0.0
                            for v in cols["Volume"]]),
        "path": None,
    }
    if save:
        path = cached_path(f"stooq_{symbol.lower().replace('^','idx_').replace('.','_')}.csv")
        with open(path, "w", newline="") as fh:
            fh.write(text)
        out["path"] = path
    return out


# ── crypto via the existing Binance archive helper ───────────────────────────
def download_binance(symbol: str = "BTCUSDT", interval: str = "1m",
                     total: int = 2000) -> list[tuple]:
    """Reuse data.binance.load_klines (public Binance archive/REST). Returns OHLCV rows."""
    from data.binance import load_klines
    return load_klines(symbol=symbol, interval=interval)


def locate_freqtrade_1m(base: str | None = None) -> list[str]:
    """Find the on-disk freqtrade 1m dumps the data plan says already exist.

    Returns the list of *.feather/*.json 1m files under the freqtrade user_data dir so the
    short-TF lane can train with ZERO new downloads (data-plan "start training today").
    """
    base = base or os.path.join(os.path.dirname(__file__), os.pardir,
                                "trading", "crypto", "freqtrade", "user_data", "data")
    base = os.path.abspath(base)
    hits: list[str] = []
    if not os.path.isdir(base):
        return hits
    for root, _dirs, files in os.walk(base):
        for f in files:
            # freqtrade names files "<PAIR>-1m.feather" or "<PAIR>-1m-futures.feather"
            if ("-1m." in f or "-1m-" in f) and (f.endswith(".feather") or f.endswith(".json")):
                hits.append(os.path.join(root, f))
    return sorted(hits)
