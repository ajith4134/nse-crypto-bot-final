"""Feature bus — every data stream the brain owns, joined into ONE per-bar
feature vector for the CORTEX arc (user mandate 2026-07-04: "the brain has a
lot of other data which can be fed to the neural network").

Three block tiers, by training honesty:
  1. CANDLE-DERIVED (fully historical, always trainable):
     * MTF block   — higher-timeframe context resampled from the same candles
                     (1h trend/RSI/volatility: the videos' multi-TF doctrine).
     * MARKET block — BTC/cross-market context from the on-disk BTC candles
                      (BTC return, relative strength, rolling correlation).
  2. RECORDED (historical since its recorder started running):
     * order-book psychology block — trading/brain/psychology.load_depth_features
       (lives in cortex_signal._psych_block).
  3. LIVE-RECORDED (this module's recorder): brain-only signals with no natural
     history — regime probs, hypothesis-learner bias, psych fear, LLM p_up.
     ``record_live`` appends them per (symbol, ts) to a jsonl ring; ``live_block``
     as-of-joins them at train time. Until history accrues they are zero-filled
     with ok=0 — the net learns the flag, nothing is fabricated.

All blocks return (n, len(NAMES)) numpy arrays aligned to a WARM-UP-GATED
feature frame that carries a 'date' column. Failures zero-fill honestly."""
from __future__ import annotations

import json
import os
from functools import lru_cache

import numpy as np

MTF_NAMES = ["h1_d_ema", "h1_rsi", "h1_ret", "h1_vol"]
MARKET_NAMES = ["btc_ret_1", "rel_ret_btc", "corr_btc_20"]
LIVE_KEYS = ["regime_p0", "regime_p1", "regime_p2", "learner_bias",
             "psych_fear", "llm_p_up"]
LIVE_NAMES = LIVE_KEYS + ["live_ok"]

_LIVE_DIR = os.path.join(os.path.dirname(__file__), "data", "brain_feats")
_MAX_LIVE_BYTES = 10_000_000


def _bar_ts(feat) -> np.ndarray:
    import pandas as pd
    return pd.to_datetime(feat["date"]).astype("int64").to_numpy() / 1e9


# ── tier 1a: multi-timeframe context (from the SAME candles → always honest) ──
def mtf_block(feat) -> np.ndarray:
    """1h context per bar: distance to 1h EMA(20), 1h RSI(14)/100, last full
    1h return, 1h realized vol (20). Uses only bars ≤ the current one."""
    n = len(feat)
    out = np.zeros((n, len(MTF_NAMES)))
    try:
        import pandas as pd
        import pandas_ta_classic as ta
        df = feat.set_index(pd.to_datetime(feat["date"]))
        h1 = df["close"].resample("1h").last().dropna()
        if len(h1) < 25:
            return out
        ema = h1.ewm(span=20, adjust=False).mean()
        rsi = ta.rsi(h1, length=14)
        ret = h1.pct_change()
        vol = ret.rolling(20).std()
        # as-of join: last COMPLETED 1h bar for each base bar (no look-ahead)
        h1_ts = h1.index.astype("int64").to_numpy() / 1e9 + 3600  # completion time
        bts = _bar_ts(feat)
        idx = np.searchsorted(h1_ts, bts, side="right") - 1
        c = df["close"].to_numpy(float)
        for i in range(n):
            j = idx[i]
            if j < 20:
                continue
            e, r, rt, v = ema.iloc[j], rsi.iloc[j], ret.iloc[j], vol.iloc[j]
            if np.isfinite(e) and e:
                out[i, 0] = c[i] / float(e) - 1.0
            out[i, 1] = float(r) / 100.0 if np.isfinite(r) else 0.0
            out[i, 2] = float(rt) if np.isfinite(rt) else 0.0
            out[i, 3] = float(v) if np.isfinite(v) else 0.0
    except Exception:
        pass
    return out


# ── tier 1b: BTC / cross-market context (BTC candles on disk) ────────────────
@lru_cache(maxsize=1)
def _btc_series():
    """(ts_seconds, close) of the on-disk BTC 1m candles (cached per process)."""
    import pandas as pd
    from data.downloads import locate_freqtrade_1m
    pick = [f for f in locate_freqtrade_1m() if "BTC_USDT_USDT-1m-futures" in f]
    if not pick:
        return np.zeros(0), np.zeros(0)
    df = pd.read_feather(pick[0])
    ts = pd.to_datetime(df["date"]).astype("int64").to_numpy() / 1e9
    return ts, df["close"].to_numpy(float)


def market_block(feat, symbol: str | None) -> np.ndarray:
    """BTC context per bar: BTC 1-bar return, pair return MINUS BTC return
    (relative strength), rolling 20-bar correlation. Zero block for BTC itself
    beyond its own return (rel/corr are trivially 0/1 → kept 0 to avoid a
    constant column)."""
    n = len(feat)
    out = np.zeros((n, len(MARKET_NAMES)))
    try:
        bts_all, bclose = _btc_series()
        if len(bts_all) == 0:
            return out
        bts = _bar_ts(feat)
        width = float(np.median(np.diff(bts))) if n > 2 else 900.0
        idx = np.searchsorted(bts_all, bts, side="right") - 1
        prev = np.searchsorted(bts_all, bts - width, side="right") - 1
        valid = (idx >= 0) & (prev >= 0) & (idx > prev)
        btc_ret = np.zeros(n)
        btc_ret[valid] = bclose[idx[valid]] / bclose[prev[valid]] - 1.0
        out[:, 0] = btc_ret
        if symbol and not str(symbol).startswith("BTC/"):
            c = feat["close"].to_numpy(float)
            pret = np.concatenate([[0.0], np.diff(c) / np.where(c[:-1] == 0, np.nan, c[:-1])])
            pret = np.nan_to_num(pret)
            out[:, 1] = pret - btc_ret
            w = 20
            for i in range(w, n):
                a, b = pret[i - w:i], btc_ret[i - w:i]
                sa, sb = a.std(), b.std()
                if sa > 0 and sb > 0:
                    out[i, 2] = float(np.corrcoef(a, b)[0, 1])
    except Exception:
        pass
    return out


# ── tier 3: live brain signals — recorder + as-of join ───────────────────────
def record_live(symbol: str, values: dict) -> None:
    """Append the brain's CURRENT per-symbol signals (regime probs, learner
    bias, fear, llm p_up — whatever subset exists right now) to the per-symbol
    jsonl ring so they become TRAINABLE history, exactly like the depth
    recorder made order-book features trainable. Never raises."""
    try:
        os.makedirs(_LIVE_DIR, exist_ok=True)
        row = {"ts": float(values.get("ts") or __import__("time").time())}
        for k in LIVE_KEYS:
            v = values.get(k)
            if v is not None and np.isfinite(float(v)):
                row[k] = round(float(v), 6)
        if len(row) == 1:
            return                                       # nothing real to record
        path = os.path.join(_LIVE_DIR, symbol.replace("/", "_").replace(":", "_") + ".jsonl")
        if os.path.exists(path) and os.path.getsize(path) > _MAX_LIVE_BYTES:
            with open(path) as fh:
                keep = fh.read().splitlines()[-4000:]
            with open(path, "w") as fh:
                fh.write("\n".join(keep) + "\n")
        with open(path, "a") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception:
        pass


def live_block(feat, symbol: str | None) -> np.ndarray:
    """(n, 7) recorded brain-signal block joined as-of per bar (≤3 bar-widths
    stale) + live_ok flag. Zero-filled with ok=0 where no recording exists."""
    n = len(feat)
    out = np.zeros((n, len(LIVE_NAMES)))
    if symbol is None:
        return out
    path = os.path.join(_LIVE_DIR, symbol.replace("/", "_").replace(":", "_") + ".jsonl")
    if not os.path.exists(path):
        return out
    try:
        ts, rows = [], []
        with open(path) as fh:
            for line in fh:
                try:
                    d = json.loads(line)
                    ts.append(float(d["ts"]))
                    rows.append([float(d.get(k, 0.0)) for k in LIVE_KEYS])
                except Exception:
                    continue
        if not ts:
            return out
        ts = np.asarray(ts)
        R = np.asarray(rows)
        bts = _bar_ts(feat)
        width = float(np.median(np.diff(bts))) if n > 2 else 900.0
        idx = np.searchsorted(ts, bts, side="right") - 1
        for i in range(n):
            j = idx[i]
            if j >= 0 and (bts[i] - ts[j]) <= 3 * width:
                out[i, :len(LIVE_KEYS)] = R[j]
                out[i, -1] = 1.0
    except Exception:
        pass
    return out
