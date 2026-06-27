"""Crypto data sources (stdlib HTTP only).

CoinGecko is keyless (free public endpoint) and works today. Coinalyze and
Etherscan need keys — they read from config.settings (the gitignored .env) and
raise a clear error until a rotated key is provided. Raw pulls are cached to
data/cache/*.csv so we don't re-hit rate limits.

Inputs:  coin id / symbol, day count.
Outputs: lists of rows + cached CSV paths.
"""
from __future__ import annotations

import json
import os
import time
import urllib.request

from config import settings

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)
_UA = {"User-Agent": "ml-brain/0.1"}


def _get_json(url: str, headers: dict | None = None, timeout: int = 25) -> dict:
    req = urllib.request.Request(url, headers={**_UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _write_csv(rows: list[tuple], path: str, header: list[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        f.write(",".join(header) + "\n")
        for r in rows:
            f.write(",".join(str(x) for x in r) + "\n")


# ── CoinGecko (keyless) ──────────────────────────────────────────────
def coingecko_daily(coin: str = "bitcoin", days: int = 365,
                    vs: str = "usd") -> list[tuple]:
    """Return [(date, close, volume)] daily. Falls back to 365d if a longer
    range is blocked on the free tier."""
    def pull(d: int):
        url = (f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
               f"?vs_currency={vs}&days={d}&interval=daily")
        return _get_json(url)
    try:
        data = pull(days)
    except Exception:
        data = pull(365)
    vols = {int(t): float(v) for t, v in data.get("total_volumes", [])}
    rows = []
    for t, p in data.get("prices", []):
        ts = int(t)
        date = time.strftime("%Y-%m-%d", time.gmtime(ts / 1000))
        rows.append((date, float(p), vols.get(ts, 0.0)))
    return rows


def fetch_coin(coin: str = "bitcoin", days: int = 365) -> tuple[str, int]:
    rows = coingecko_daily(coin, days)
    path = os.path.join(CACHE, f"{coin}_daily.csv")
    _write_csv(rows, path, ["date", "close", "volume"])
    return path, len(rows)


def load_coin(coin: str = "bitcoin") -> list[tuple]:
    path = os.path.join(CACHE, f"{coin}_daily.csv")
    if not os.path.exists(path):
        fetch_coin(coin)
    rows = []
    with open(path, encoding="utf-8") as f:
        next(f)
        for line in f:
            d, c, v = line.strip().split(",")
            rows.append((d, float(c), float(v)))
    return rows


# ── Keyed sources (activate when rotated keys are in .env) ───────────
def etherscan_gas_oracle() -> dict:
    key = settings.get("ETHERSCAN_API_KEY")
    if not key:
        raise RuntimeError("ETHERSCAN_API_KEY not set — add a rotated key to .env")
    return _get_json("https://api.etherscan.io/api?module=gastracker&action=gasoracle"
                     f"&apikey={key}")


def coinalyze_funding(symbol: str = "BTCUSDT_PERP.A") -> dict:
    key = settings.get("COINALYZE_API_KEY")
    if not key:
        raise RuntimeError("COINALYZE_API_KEY not set — add a rotated key to .env")
    return _get_json("https://api.coinalyze.net/v1/funding-rate"
                     f"?symbols={symbol}", headers={"api_key": key})
