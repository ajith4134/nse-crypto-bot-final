"""Binance public market data (no key): intraday klines + order-book snapshots.

Klines give free historical intraday candles (far more samples + structure than
daily CoinGecko). Reuses the same feature engineering as the rest of the project.
"""
from __future__ import annotations

import json
import os
import urllib.request

from data import features as F
from data.sources import CACHE  # reuse the cache dir
from data.dataset import TARGETS

_BASE = "https://api.binance.com/api/v3"
_UA = {"User-Agent": "ml-brain/0.1"}


def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def fetch_klines(symbol="BTCUSDT", interval="1h", total=2000) -> str:
    """Page backward to collect `total` candles; cache (openTime, close, volume)."""
    out, end = [], None
    while len(out) < total:
        url = f"{_BASE}/klines?symbol={symbol}&interval={interval}&limit=1000"
        if end is not None:
            url += f"&endTime={end}"
        page = _get(url)
        if not page:
            break
        out = page + out                       # prepend older pages
        end = int(page[0][0]) - 1              # before earliest openTime
        if len(page) < 1000:
            break
    out = out[-total:]
    rows = [(int(k[0]), float(k[4]), float(k[5])) for k in out]   # openTime, close, volume
    path = os.path.join(CACHE, f"{symbol}_{interval}.csv")
    with open(path, "w", encoding="utf-8") as f:
        f.write("date,close,volume\n")
        for d, c, v in rows:
            f.write(f"{d},{c},{v}\n")
    return path


def load_klines(symbol="BTCUSDT", interval="1h") -> list[tuple]:
    path = os.path.join(CACHE, f"{symbol}_{interval}.csv")
    if not os.path.exists(path):
        fetch_klines(symbol, interval)
    rows = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            d, c, v = line.strip().split(",")
            rows.append((int(d), float(c), float(v)))
    return rows


def make_kline_dataset(symbol="BTCUSDT", interval="1h", target="volatility") -> dict:
    built = F.build(load_klines(symbol, interval))
    if target not in TARGETS:
        raise ValueError(f"unknown target '{target}'")
    return {"symbol": symbol, "interval": interval, "target": target,
            "feature_names": built["feature_names"],
            "X": built["X"], "y": built[TARGETS[target]]}
