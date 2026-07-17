"""Shared loaders for the 2026-07-17 discussion-session experiments (E1-E6).

Read-only over: direction_truth_train.jsonl (labeled claims), mirror_candles.json.gz
(today's RAM snapshot), freqtrade feather OHLCV (deep history to 07-16 18:55),
tradesv3.dryrun.sqlite (closed trades). Never writes project state.
"""
from __future__ import annotations

import gzip
import json
import os
import sqlite3
from functools import lru_cache

import numpy as np
import pandas as pd

HOME = os.path.expanduser("~")
DATA = os.path.join(HOME, "trading/crypto/freqtrade/user_data/data/binance")
CLEAN_TS = 1784236980.0          # 2026-07-16 21:23 UTC — post B1/B2-fix window
SPLIT_TS = 1784282640.0          # 2026-07-17 10:04 UTC — control-lane split


def flat(sym: str) -> str:
    return str(sym or "").replace("/", "").split(":")[0].upper()


def base(sym: str) -> str:
    f = flat(sym)
    return f[:-4] if f.endswith("USDT") else f


# ── candles ──────────────────────────────────────────────────────────────────────
_mirror = None


def _load_mirror() -> dict:
    global _mirror
    if _mirror is None:
        with gzip.open(os.path.join(HOME, "trading/state/mirror_candles.json.gz"), "rt") as f:
            _mirror = json.load(f).get("candles", {})
    return _mirror


@lru_cache(maxsize=700)
def bars5(sym: str) -> np.ndarray | None:
    """5m bars [ts, o, h, l, c] float64, feather history + today's mirror merged."""
    b = base(sym)
    parts = []
    for path in (os.path.join(DATA, "futures", f"{b}_USDT_USDT-5m-futures.feather"),
                 os.path.join(DATA, f"{b}_USDT-5m.feather")):
        if os.path.exists(path):
            df = pd.read_feather(path)
            ts = df["date"].astype("int64").to_numpy() / 1e9
            parts.append(np.column_stack([ts, df[["open", "high", "low", "close"]]
                                          .to_numpy(dtype=np.float64)]))
            break                                   # futures preferred; don't mix basis
    rows = _load_mirror().get(flat(sym), {}).get("300")
    if rows:
        parts.append(np.asarray(rows, dtype=np.float64))
    if not parts:
        return None
    arr = np.concatenate(parts)
    arr = arr[np.argsort(arr[:, 0])]
    _, keep = np.unique(arr[:, 0], return_index=True)
    return arr[keep]


def close_at(arr: np.ndarray, ts: float) -> float | None:
    """Close of the last 5m bar starting at or before ts (max 10min staleness)."""
    i = np.searchsorted(arr[:, 0], ts, side="right") - 1
    if i < 0 or ts - arr[i, 0] > 600:
        return None
    return float(arr[i, 4])


def fwd_ret(arr: np.ndarray, ts: float, horizon_s: float) -> float | None:
    a, b = close_at(arr, ts), close_at(arr, ts + horizon_s)
    if a is None or b is None or a <= 0:
        return None
    return b / a - 1.0


def range_pos(arr: np.ndarray, ts: float, minutes: int = 30) -> float | None:
    """Mirror of truth_ledger.range_position: cur close vs prior-`minutes` hi/lo."""
    n = max(3, minutes // 5 + 1)
    i = np.searchsorted(arr[:, 0], ts, side="right")
    if i < n or ts - arr[i - 1, 0] > 600:
        return None
    win = arr[i - n:i]
    cur = win[-1, 4]
    hi, lo = win[:-1, 2].max(), win[:-1, 3].min()
    if hi <= lo:
        return None
    return float(np.clip((cur - lo) / (hi - lo), 0.0, 1.0))


def pos_bucket(rp: float | None) -> str | None:
    if rp is None:
        return None
    return "top" if rp > 0.8 else ("bottom" if rp < 0.2 else "mid")


# ── claims + trades ──────────────────────────────────────────────────────────────
def load_claims() -> pd.DataFrame:
    rows = []
    with open(os.path.join(HOME, "trading/state/direction_truth_train.jsonl")) as f:
        for line in f:
            try:
                rows.append(json.loads(line))
            except Exception:
                pass
    df = pd.DataFrame(rows)
    df = df[df["market"].fillna("CRYPTO").str.upper() == "CRYPTO"]
    df["correct"] = df["correct"].astype(bool)
    return df


def load_trades() -> pd.DataFrame:
    con = sqlite3.connect(os.path.join(HOME, "tradesv3.dryrun.sqlite"))
    df = pd.read_sql_query(
        "SELECT id, pair, is_short, enter_tag, exit_reason, open_rate, close_rate, "
        "min_rate, max_rate, close_profit, close_profit_abs, stake_amount, leverage, "
        "open_date, close_date FROM trades WHERE is_open=0 AND close_profit IS NOT NULL",
        con)
    con.close()
    for c in ("open_date", "close_date"):
        df[c] = pd.to_datetime(df[c], utc=True, format="mixed")
    df["open_ts"] = df["open_date"].astype("int64") / 1e9
    return df
