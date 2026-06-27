"""External real-world datasets — multi-dataset evaluation (CONVENTIONS §14).

Never crypto-only: every node is testable on diverse, free/no-key real data.
Each loader returns ascending rows of (date, close, volume) so the SAME
`data.features.build` featurizer produces X + the multi-output targets
(direction/magnitude/regime/volatility). Non-price series use a dummy volume=1.0.

Sources (all free, no API key):
  indian   — NSE/BSE equities via yfinance (e.g. RELIANCE.NS)
  sunspots — SILSO daily total sunspot number (Royal Obs. Belgium)
  weather  — Open-Meteo ERA5 archive (daily mean temperature)
  energy   — UCI household electric power (resampled to daily mean)
  ecg      — PhysioNet MIT-BIH record via wfdb (downsampled amplitude)

Raw fetches are cached under data/cache/ (gitignored). Network failures fall
back to an offline source where one exists (sunspots → statsmodels).
"""
from __future__ import annotations

import csv
import io
import os
import urllib.request

from data import features as F

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cache")
os.makedirs(CACHE, exist_ok=True)

EXTERNAL_SOURCES = ("indian", "sunspots", "weather", "energy", "ecg")


def _rows_from_values(dates, values) -> list[tuple]:
    return [(d, float(v), 1.0) for d, v in zip(dates, values) if v is not None]


# --------------------------------------------------------------------------- #
def load_indian_equity(symbol: str = "RELIANCE.NS", period: str = "8y") -> list[tuple]:
    import yfinance as yf
    df = yf.download(symbol, period=period, interval="1d", progress=False, auto_adjust=True)
    if df is None or len(df) == 0:
        raise RuntimeError(f"yfinance returned no data for {symbol}")
    close = df["Close"].to_numpy().reshape(-1)
    vol = df["Volume"].to_numpy().reshape(-1) if "Volume" in df else [1.0] * len(close)
    dates = [str(d.date()) for d in df.index]
    return [(dates[i], float(close[i]), float(vol[i]) or 1.0) for i in range(len(close))]


def load_sunspots() -> list[tuple]:
    url = "https://www.sidc.be/SILSO/INFO/sndtotcsv.php"
    path = os.path.join(CACHE, "silso_sunspots_daily.csv")
    try:
        if not os.path.exists(path):
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            with open(path, "wb") as f:
                f.write(data)
        rows = []
        with open(path, newline="") as f:
            for parts in csv.reader(f, delimiter=";"):
                if len(parts) < 5:
                    continue
                y, m, d, sn = parts[0].strip(), parts[1].strip(), parts[2].strip(), parts[4].strip()
                if sn in ("", "-1", "-1.0"):
                    continue
                rows.append((f"{y}-{m.zfill(2)}-{d.zfill(2)}", float(sn), 1.0))
        if len(rows) > 100:
            return rows
        raise RuntimeError("SILSO parse too short")
    except Exception:                                       # offline fallback
        import statsmodels.api as sm
        d = sm.datasets.sunspots.load_pandas().data
        return _rows_from_values([str(int(y)) for y in d["YEAR"]], d["SUNACTIVITY"].tolist())


def load_weather(lat: float = 28.61, lon: float = 77.21,
                 start: str = "2015-01-01", end: str = "2024-12-31") -> list[tuple]:
    url = (f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}"
           f"&start_date={start}&end_date={end}&daily=temperature_2m_mean&timezone=auto")
    import json
    raw = urllib.request.urlopen(url, timeout=40).read()
    j = json.loads(raw)
    dates = j["daily"]["time"]
    temps = j["daily"]["temperature_2m_mean"]
    return _rows_from_values(dates, temps)


def load_energy() -> list[tuple]:
    """UCI household power → daily mean Global_active_power (cached)."""
    daily = os.path.join(CACHE, "uci_energy_daily.csv")
    if os.path.exists(daily):
        rows = []
        with open(daily) as f:
            for ln in f.read().splitlines()[1:]:
                d, v = ln.split(",")
                rows.append((d, float(v), 1.0))
        return rows
    import zipfile
    url = ("https://archive.ics.uci.edu/static/public/235/"
           "individual+household+electric+power+consumption.zip")
    raw = urllib.request.urlopen(url, timeout=90).read()
    zf = zipfile.ZipFile(io.BytesIO(raw))
    name = [n for n in zf.namelist() if n.endswith(".txt")][0]
    agg: dict[str, list[float]] = {}
    with zf.open(name) as fh:
        header = fh.readline().decode().strip().split(";")
        di, gi = header.index("Date"), header.index("Global_active_power")
        for line in io.TextIOWrapper(fh, "utf-8"):
            p = line.strip().split(";")
            if len(p) <= gi or p[gi] == "?":
                continue
            dd = p[di]  # dd/mm/yyyy
            d8 = f"{dd[6:10]}-{dd[3:5]}-{dd[0:2]}"
            agg.setdefault(d8, []).append(float(p[gi]))
    rows = [(d, sum(v) / len(v), 1.0) for d, v in sorted(agg.items())]
    with open(daily, "w") as f:
        f.write("date,kw\n")
        for d, v, _ in rows:
            f.write(f"{d},{v}\n")
    return rows


def load_ecg(record: str = "100", n: int = 6000, every: int = 5) -> list[tuple]:
    import wfdb
    rec = wfdb.rdrecord(record, pn_dir="mitdb", sampto=n * every)
    sig = rec.p_signal[:, 0][::every]
    return [(f"t{i}", float(sig[i]), 1.0) for i in range(len(sig))]


_LOADERS = {
    "indian": load_indian_equity, "sunspots": load_sunspots, "weather": load_weather,
    "energy": load_energy, "ecg": load_ecg,
}
_TITLES = {
    "indian": "Indian equity (NSE, yfinance)", "sunspots": "Sunspots (SILSO daily)",
    "weather": "Weather — daily mean temp (Open-Meteo ERA5)",
    "energy": "Electricity demand (UCI household, daily)",
    "ecg": "ECG — MIT-BIH (PhysioNet, wfdb)",
}


def make_external_dataset(source: str) -> dict:
    """Fetch a real source → build X + multi-output targets via features.build."""
    if source not in _LOADERS:
        raise ValueError(f"unknown source {source!r}; choose from {EXTERNAL_SOURCES}")
    rows = _LOADERS[source]()
    # features.build computes price-style returns (close[i]/close[i-1]); non-price
    # series can be zero/negative (sunspot minima, ECG mV) -> shift strictly positive.
    closes = [r[1] for r in rows]
    mn = min(closes)
    if mn <= 0:
        shift = 1.0 - mn
        rows = [(d, c + shift, v) for d, c, v in rows]
    built = F.build(rows)
    return {
        "name": _TITLES[source], "source": source,
        "X": built["X"], "y": built["y_direction"],
        "feature_names": built["feature_names"], "n": len(built["X"]),
        "targets": {"direction": built["y_direction"], "magnitude": built["y_return"],
                    "regime": built["y_regime"], "volatility": built["y_vol_high"]},
    }
