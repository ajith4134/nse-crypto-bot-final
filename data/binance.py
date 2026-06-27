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


# Intraday direction horizons (in klines): next 1, 4, and 24 candles ahead.
KLINE_HORIZONS = (1, 4, 24)


def _multi_horizon_dir(closes: list[float], n_rows: int,
                       horizons=KLINE_HORIZONS) -> tuple[dict, int]:
    """Build {"dir_h": [...]} direction targets for several look-aheads.

    F.build emits one X row per close index in range(START, len-1), so X row j
    maps to close index START+j. For each horizon h, target = 1 if the close h
    candles ahead is higher (causal: uses only closes[i+h]). The tail rows whose
    h-ahead future is missing are dropped; we return the common valid length so
    callers can keep every target dict aligned 1:1 with the (trimmed) X rows.
    """
    longest = max(horizons)
    valid = 0
    for j in range(n_rows):                       # furthest in-range row for all horizons
        if F.START + j + longest <= len(closes) - 1:
            valid = j + 1
        else:
            break
    targets = {}
    for h in horizons:
        targets[f"dir_{h}"] = [
            1 if closes[F.START + j + h] > closes[F.START + j] else 0
            for j in range(valid)
        ]
    return targets, valid


def make_kline_dataset(symbol="BTCUSDT", interval="1h", target="volatility") -> dict:
    rows = load_klines(symbol, interval)
    built = F.build(rows)
    if target not in TARGETS:
        raise ValueError(f"unknown target '{target}'")
    closes = [r[1] for r in rows]
    dir_targets, valid = _multi_horizon_dir(closes, len(built["X"]))
    # Trim X / single-target y to the multi-horizon valid length so every target
    # stays aligned 1:1 with the X rows (no look-ahead in the dropped tail).
    X = built["X"][:valid]
    y = built[TARGETS[target]][:valid]
    targets = {
        "direction": built["y_direction"][:valid],
        "magnitude": built["y_return"][:valid],
        "volatility": built["y_vol_high"][:valid],
        **dir_targets,                            # dir_1 / dir_4 / dir_24
    }
    return {"symbol": symbol, "interval": interval, "target": target,
            "feature_names": built["feature_names"],
            "X": X, "y": y, "targets": targets}
