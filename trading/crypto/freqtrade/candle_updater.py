"""trading/crypto/freqtrade/candle_updater.py — keep OHLCV candle data continuously fresh.

Loops forever: refresh the multi-timeframe candle data for the top-volume USDT perps (incremental —
freqtrade download-data only fetches the missing recent candles, so cycles after the first are fast),
writing a STATUS file the forked FreqUI reads same-origin to show a live "candles: updating / updated
Nm ago" indicator. Honest: pairs are the real top-N by 24h quote volume (matches VolumePairList).

Run (in the persistent session, since the agent sandbox reaps daemons):
  nohup setsid .venv/bin/python -m trading.crypto.freqtrade.candle_updater >dashboard/candle_updater.log 2>&1 &

THROTTLE: a single download-data over all ~300 pairs × 6 TFs × 120d bursts the exchange API
and, colliding with the dashboard's own ccxt endpoints, throttles Binance → the 32-thread
dashboard server piles up on slow calls and wedges (Cloudflare 524, 2026-07-03). Fix: split the
pairs into small BATCHES run back-to-back with a short sleep between, and `nice` the subprocess
so it never starves the dashboard/trading. Full coverage preserved — just spread over time.

Env knobs: CANDLE_UPDATE_INTERVAL (s, default 900), CANDLE_UPDATE_PAIRS (default 300),
CANDLE_UPDATE_DAYS (default 120), CANDLE_UPDATE_TFS (default "1m 5m 15m 1h 4h 1d"),
CANDLE_UPDATE_BATCH (pairs per download call, default 25),
CANDLE_UPDATE_BATCH_SLEEP (s between batches, default 6), CANDLE_UPDATE_NICE (default 15).
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
INTERVAL = int(os.getenv("CANDLE_UPDATE_INTERVAL", "900"))
N_PAIRS = int(os.getenv("CANDLE_UPDATE_PAIRS", "300"))
DAYS = os.getenv("CANDLE_UPDATE_DAYS", "120")
TFS = os.getenv("CANDLE_UPDATE_TFS", "1m 5m 15m 1h 4h 1d").split()
BATCH = max(1, int(os.getenv("CANDLE_UPDATE_BATCH", "25")))
BATCH_SLEEP = max(0.0, float(os.getenv("CANDLE_UPDATE_BATCH_SLEEP", "6")))
NICE = int(os.getenv("CANDLE_UPDATE_NICE", "15"))


def _batches(pairs: list[str], size: int) -> list[list[str]]:
    return [pairs[i:i + size] for i in range(0, len(pairs), size)]


def _uidir() -> str:
    import freqtrade as _ft
    return os.path.join(os.path.dirname(_ft.__file__), "rpc", "api_server", "ui", "installed")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _write_status(uidir: str, **fields) -> None:
    try:
        with open(os.path.join(uidir, "mlnb_candles.json"), "w") as f:
            json.dump(fields, f)
    except Exception:
        pass


def _top_pairs(n: int) -> list[str]:
    """Top-n USDT perps by 24h quote volume (real ccxt data, matches the pairlist)."""
    try:
        import ccxt
        ex = ccxt.binanceusdm()
        ex.load_markets()
        tickers = ex.fetch_tickers()
        rows = []
        for sym, mk in ex.markets.items():
            if not mk.get("swap") or mk.get("quote") != "USDT" or not mk.get("active", True):
                continue
            qv = (tickers.get(sym) or {}).get("quoteVolume") or 0
            rows.append((qv, sym))
        rows.sort(reverse=True)
        return [s for _, s in rows[:n]]
    except Exception:
        return []


def _download(batch: list[str]) -> int:
    """One download-data subprocess for a small pair batch, de-prioritised (nice) so it
    never starves the dashboard/trading. Returns the process return code."""
    cmd = [os.path.join(ROOT, ".venv", "bin", "freqtrade"), "download-data",
           "--config", os.path.join(HERE, "config.json"),
           "--pairs", *batch, "--timeframes", *TFS,
           "--days", str(DAYS), "--trading-mode", "futures",
           "--data-format-ohlcv", "feather"]
    kw = dict(cwd=HERE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        kw["preexec_fn"] = lambda: os.nice(NICE)          # POSIX: lower CPU priority
    except Exception:
        pass
    return subprocess.run(cmd, **kw).returncode


def run_cycle(uidir: str, cycle: int) -> None:
    pairs = _top_pairs(N_PAIRS)
    if len(pairs) < 5:
        _write_status(uidir, state="error", reason="pair list too small", updated_at=_now(), cycle=cycle)
        return
    batches = _batches(pairs, BATCH)
    _write_status(uidir, state="updating", started_at=_now(), pairs=len(pairs),
                  batches=len(batches), timeframes=TFS, days=int(DAYS), cycle=cycle)
    last_rc = 0
    for bi, batch in enumerate(batches, 1):
        try:
            rc = _download(batch)
            last_rc = rc or last_rc
        except Exception as e:
            _write_status(uidir, state="error", reason=str(e), updated_at=_now(),
                          batch=bi, batches=len(batches), cycle=cycle)
            continue
        # progress + breathe between batches so the exchange API (and the dashboard's own
        # ccxt endpoints) are never monopolised by one giant burst.
        _write_status(uidir, state="updating", updated_at=_now(), pairs=len(pairs),
                      batch=bi, batches=len(batches), timeframes=TFS, days=int(DAYS), cycle=cycle)
        if bi < len(batches) and BATCH_SLEEP > 0:
            time.sleep(BATCH_SLEEP)
    _write_status(uidir, state="idle", updated_at=_now(), pairs=len(pairs),
                  batches=len(batches), timeframes=TFS, days=int(DAYS), cycle=cycle, last_rc=last_rc)


def main() -> int:
    uidir = _uidir()
    os.makedirs(uidir, exist_ok=True)
    cycle = 0
    while True:
        cycle += 1
        run_cycle(uidir, cycle)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    raise SystemExit(main())
