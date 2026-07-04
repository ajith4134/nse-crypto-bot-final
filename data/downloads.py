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
import lzma
import os
import struct
import urllib.error
import urllib.parse
import urllib.request
import zipfile

import numpy as np

_CACHE = os.path.join(os.path.dirname(__file__), "cache")
_STOOQ = "https://stooq.com/q/d/l/?s={sym}&i=d"
_UA = {"User-Agent": "Mozilla/5.0 (cortex-datafetch)"}
# a full browser UA — NSE/dukascopy reject the bare fetch UA above
_BROWSER_UA = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}
# dukascopy tick prices are integers in instrument "points"; divide by this scale
_DUKA_SCALE = {"EURUSD": 1e5, "GBPUSD": 1e5, "USDJPY": 1e3, "USDCHF": 1e5,
               "AUDUSD": 1e5, "USDCAD": 1e5, "XAUUSD": 1e3}

__all__ = ["download_stooq_daily", "download_binance", "locate_freqtrade_1m",
           "download_dukascopy", "download_nse_bhavcopy", "cached_path"]


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


# ── dukascopy forex ticks (public datafeed, LZMA .bi5) ───────────────────────
def download_dukascopy(instrument: str = "EURUSD", year: int = 2024,
                       month: int = 1, day: int = 2, hours=range(24), *,
                       save: bool = True, timeout: int = 30) -> dict:
    """Download one day of dukascopy tick data (CANON-05 forex lane).

    dukascopy serves hourly LZMA-compressed `.bi5` files at
    datafeed.dukascopy.com/datafeed/<INS>/<YYYY>/<MM-1>/<DD>/<HH>h_ticks.bi5
    (month is 0-indexed). Each 20-byte record is big-endian
    (ms_in_hour:uint32, ask:uint32, bid:uint32, ask_vol:float, bid_vol:float)
    with prices in instrument points. Returns arrays for ask/bid/volumes and the
    ms-since-epoch-less per-tick hour offset. Raises with a clear message if the
    cloud IP is blocked (never a silent stub — the never-data-gate rule)."""
    scale = _DUKA_SCALE.get(instrument.upper(), 1e5)
    base = ("https://datafeed.dukascopy.com/datafeed/{ins}/{y:04d}/{m:02d}/"
            "{d:02d}/{h:02d}h_ticks.bi5")
    ms, ask, bid, av, bv = [], [], [], [], []
    fetched_hours = 0
    for h in hours:
        url = base.format(ins=instrument.upper(), y=year, m=month - 1, d=day, h=h)
        req = urllib.request.Request(url, headers=_BROWSER_UA)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = r.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 404:            # no ticks that hour (market closed) — skip
                continue
            raise RuntimeError(f"dukascopy blocked/failed for {instrument} "
                               f"{year}-{month:02d}-{day:02d} h{h}: HTTP {exc.code}")
        if not raw:
            continue
        buf = lzma.decompress(raw)
        fetched_hours += 1
        for off in range(0, len(buf), 20):
            t, a, b, avol, bvol = struct.unpack(">IIIff", buf[off:off + 20])
            ms.append(h * 3_600_000 + t)
            ask.append(a / scale); bid.append(b / scale)
            av.append(avol); bv.append(bvol)
    if fetched_hours == 0:
        raise RuntimeError(f"dukascopy returned no ticks for {instrument} "
                           f"{year}-{month:02d}-{day:02d} (IP-blocked or holiday)")
    out = {"instrument": instrument.upper(),
           "ms": np.array(ms, dtype=np.int64),
           "ask": np.array(ask), "bid": np.array(bid),
           "ask_vol": np.array(av), "bid_vol": np.array(bv),
           "mid": (np.array(ask) + np.array(bid)) / 2.0, "path": None}
    if save:
        path = cached_path(f"duka_{instrument.upper()}_{year}{month:02d}{day:02d}.csv")
        with open(path, "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["ms", "ask", "bid", "mid", "ask_vol", "bid_vol"])
            for i in range(len(ms)):
                w.writerow([out["ms"][i], out["ask"][i], out["bid"][i],
                            out["mid"][i], out["ask_vol"][i], out["bid_vol"][i]])
        out["path"] = path
    return out


# ── NSE end-of-day bhavcopy (public archive ZIP) ─────────────────────────────
def download_nse_bhavcopy(year: int = 2024, month: int = 1, day: int = 2, *,
                          save: bool = True, timeout: int = 30) -> dict:
    """Download the NSE cash-market end-of-day bhavcopy (CANON-05 equities lane).

    Uses the current UDiFF full-bhavcopy archive:
    nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_<YYYYMMDD>_F_0000.csv.zip
    Returns {'rows': [dict...], 'columns', 'n', 'path'}. NSE blocks bare fetch
    UAs and cloud IPs (documented in the data plan); on a block this raises a
    clear RuntimeError rather than returning a fake stub. A ~/nse_cookies.txt
    Netscape cookie jar, if present, is attached to defeat the WAF."""
    ymd = f"{year:04d}{month:02d}{day:02d}"
    url = ("https://nsearchives.nseindia.com/content/cm/"
           f"BhavCopy_NSE_CM_0_0_0_{ymd}_F_0000.csv.zip")
    opener = urllib.request.build_opener()
    cookie_path = os.path.expanduser("~/nse_cookies.txt")
    if os.path.exists(cookie_path):
        import http.cookiejar
        jar = http.cookiejar.MozillaCookieJar(cookie_path)
        try:
            jar.load(ignore_discard=True, ignore_expires=True)
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar))
        except Exception:
            pass
    headers = dict(_BROWSER_UA); headers["Referer"] = "https://www.nseindia.com/"
    req = urllib.request.Request(url, headers=headers)
    try:
        with opener.open(req, timeout=timeout) as r:
            raw = r.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"NSE bhavcopy blocked for {ymd}: HTTP {exc.code} "
                           f"(cloud-IP/WAF block — drop ~/nse_cookies.txt to defeat)")
    try:
        zf = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise RuntimeError(f"NSE bhavcopy for {ymd} is not a zip "
                           f"(likely a WAF HTML block; first 80: {raw[:80]!r})")
    name = zf.namelist()[0]
    text = zf.read(name).decode("utf-8", "replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise RuntimeError(f"NSE bhavcopy for {ymd} was empty")
    out = {"rows": rows, "columns": list(rows[0].keys()), "n": len(rows),
           "path": None}
    if save:
        path = cached_path(f"nse_bhavcopy_{ymd}.csv")
        with open(path, "w", newline="") as fh:
            fh.write(text)
        out["path"] = path
    return out


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
