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


# --------------------------------------------------------------------------- #
#  Multi-timeframe (MTF) input — stack higher-timeframe context onto a base TF
# --------------------------------------------------------------------------- #
def _interval_ms(interval: str) -> int:
    unit = interval[-1]
    mult = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit]
    return int(interval[:-1]) * mult * 1000


def _latest_completed_idx(open_times: list[int], t: int, interval_ms: int) -> int:
    """Largest index j of a higher-TF candle that has fully CLOSED by base time t
    (open_times[j] + interval_ms <= t). Using a candle still forming at t would
    leak its (future) close -> this is the causal, no-look-ahead alignment."""
    import bisect
    return bisect.bisect_right(open_times, t - interval_ms) - 1


def make_mtf_dataset(symbol="BTCUSDT", base="5m",
                     context=("15m", "30m", "1h"), target="direction",
                     loader=load_klines, label=None) -> dict:
    """Multi-timeframe input: each base-`base` row is augmented with the features
    of the most recent COMPLETED candle on each higher timeframe in `context`
    (causal — a context candle is used only once it has fully closed by the base
    row's time, so no look-ahead). Standard MTF trading-feature recipe.

    `loader(symbol, interval) -> [(open_ms, close, volume)]` lets the SAME builder
    serve crypto (Binance klines) AND Indian equities (yfinance intraday).
    """
    base_rows = loader(symbol, base)
    built = F.build(base_rows)
    base_dates = built["dates"]                  # openTime (ms) per X row
    X = [list(row) for row in built["X"]]
    names = list(built["feature_names"])

    for tf in context:
        ctx_built = F.build(loader(symbol, tf))
        ctx_times = ctx_built["dates"]
        ctx_X = ctx_built["X"]
        d = len(ctx_built["feature_names"])
        ims = _interval_ms(tf)
        names += [f"{tf}_{nm}" for nm in ctx_built["feature_names"]]
        for i, t in enumerate(base_dates):
            j = _latest_completed_idx(ctx_times, t, ims)
            X[i].extend(ctx_X[j] if j >= 0 else [0.0] * d)

    if target not in TARGETS:
        raise ValueError(f"unknown target '{target}'")
    return {"symbol": symbol, "base": base, "context": list(context),
            "name": f"{symbol} multi-timeframe {base}+{'+'.join(context)}",
            "source": "mtf", "feature_names": names, "n": len(X), "X": X,
            "y": built[TARGETS[target]],
            "targets": {"direction": built["y_direction"], "magnitude": built["y_return"],
                        "regime": built["y_regime"], "volatility": built["y_vol_high"]}}
