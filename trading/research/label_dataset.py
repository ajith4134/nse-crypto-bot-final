"""Labelled dataset builder — the foundation for testing whether ANY signal has edge.

WHY THIS EXISTS (2026-07-18): we measured that NOT ONE of the brain's entry-time features
separates winners from losers (fusion_p_up t=+0.01, ld_p_up t=−1.59 i.e. slightly inverted,
psychology ~0). Every experiment tuning exits/gates on top of that was rearranging a coin
flip. Before anything else is tuned, a signal must demonstrate out-of-sample edge on an
honest dataset. This module builds that dataset.

THREE RULES IT ENFORCES (each one is a way people fool themselves):
1. NO SURVIVORSHIP — labels EVERY symbol at EVERY sampled time, not just the trades the
   system chose to take. The traded set is exactly the biased sample that hides the truth.
2. NO LOOKAHEAD — every feature is computed from bars STRICTLY BEFORE the decision index;
   the label uses bars STRICTLY AFTER it. The split point is never included in features.
3. COST-AWARE LABELS — a move that cannot clear round-trip fees is not an opportunity, so
   the primary label is "did the move exceed cost", not "did price go up".

The output carries `symbol` and `ts` so downstream CV can be PURGED and EMBARGOED — a random
split on overlapping time series will manufacture edge that does not exist.

Usage:
    from trading.research.label_dataset import build
    df = build(horizon_bars=4, sample_every=4, max_symbols=None)
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

DATA_DIR = Path.home() / "trading/crypto/freqtrade/user_data/data/binance/futures"
OUT_DIR = Path.home() / "research/datasets"

# round-trip taker cost in % of notional (0.05%/side) — the bar any move must clear
ROUND_TRIP_COST_PCT = 0.10


def _symbol_files(timeframe: str = "15m") -> list[Path]:
    return sorted(DATA_DIR.glob(f"*-{timeframe}-futures.feather"))


def _pretty(path: Path) -> str:
    """SOL_USDT_USDT-15m-futures.feather -> SOL/USDT:USDT"""
    stem = path.name.split("-")[0]
    if stem.endswith("_USDT_USDT"):
        return stem[: -len("_USDT_USDT")] + "/USDT:USDT"
    return stem.replace("_", "/")


def _features_at(c, h, l, v, i: int, bars_per_hour: int = 12) -> dict | None:
    """Features from bars [.. i-1] ONLY. `i` is the decision bar and is EXCLUDED, so a
    feature can never peek at the bar whose forward return becomes the label.

    bars_per_hour: 12 for 5m bars (the intraday default), 4 for 15m.
    """
    need = 168 * bars_per_hour + 1            # 7 days of history
    if i < need:
        return None
    px = c[i - 1]
    if not px or px <= 0:
        return None

    B = bars_per_hour

    def ret(bars: int) -> float:
        base = c[i - 1 - bars]
        return (px - base) / base * 100.0 if base else 0.0

    n15, n1h, n4h, n24h = max(1, B // 4), B, 4 * B, 24 * B
    hi1, lo1 = max(h[i - n1h:i]), min(l[i - n1h:i])
    hi4, lo4 = max(h[i - n4h:i]), min(l[i - n4h:i])
    hi24, lo24 = max(h[i - n24h:i]), min(l[i - n24h:i])
    bars_r = [(h[j] - l[j]) / c[j] * 100.0 for j in range(i - n4h, i) if c[j]]
    bs = sorted(bars_r)
    med_bar = bs[len(bs) // 2] if bs else 0.0
    vol_recent = sum(v[i - n1h:i]) / n1h
    vol_base = sum(v[i - n24h:i]) / n24h
    ema_n = n1h
    ema = sum(c[i - ema_n:i]) / ema_n
    dollar_vol = sum(c[j] * v[j] for j in range(i - n24h, i))     # 24h notional traded

    # INTRADAY-FIRST feature set: the short horizons lead, the slow ones are context.
    return {
        "ret_15m": ret(n15), "ret_1h": ret(n1h), "ret_4h": ret(n4h),
        "ret_24h": ret(n24h), "ret_7d": ret(168 * B),
        "pos_1h": (px - lo1) / (hi1 - lo1) if hi1 > lo1 else 0.5,
        "pos_4h": (px - lo4) / (hi4 - lo4) if hi4 > lo4 else 0.5,
        "pos_24h": (px - lo24) / (hi24 - lo24) if hi24 > lo24 else 0.5,
        "range_1h_pct": (hi1 - lo1) / px * 100.0,
        "range_4h_pct": (hi4 - lo4) / px * 100.0,
        "range_24h_pct": (hi24 - lo24) / px * 100.0,
        "med_bar_pct": med_bar,
        "vol_ratio": vol_recent / vol_base if vol_base else 1.0,
        "dist_ema1h_pct": (px - ema) / ema * 100.0 if ema else 0.0,
        "dollar_vol_24h": dollar_vol,
        # squeeze: current 1h range vs the 24h norm — the one lane that ran green live
        "squeeze": ((hi1 - lo1) / px * 100.0) / (((hi24 - lo24) / px * 100.0) / 24.0)
                   if hi24 > lo24 and px else 1.0,
        "trend_agree": (1.0 if (ret(n15) > 0) == (ret(n1h) > 0) else 0.0)
                       + (1.0 if (ret(n1h) > 0) == (ret(n4h) > 0) else 0.0)
                       + (1.0 if (ret(n4h) > 0) == (ret(168 * B) > 0) else 0.0),
    }


def build(timeframe: str = "5m", sample_every: int = 12,
          horizons: tuple[int, ...] = (3, 6, 12, 24),
          max_symbols: int | None = None, min_dollar_vol: float = 0.0) -> pd.DataFrame:
    """Label every symbol at every sampled bar, for INTRADAY horizons.

    Default 5m bars with horizons 3/6/12/24 bars = 15m / 30m / 1h / 2h forward — matching
    how this system actually trades (live median hold ~9-23 min), NOT daily-rebalance
    research horizons.
    sample_every: stride between decision points (12 x 5m = 1h) so consecutive rows do not
                  share most of their label window — overlapping labels inflate significance.
    """
    rows: list[dict] = []
    bars_per_hour = 12 if timeframe == "5m" else 4
    files = _symbol_files(timeframe)
    if max_symbols:
        files = files[:max_symbols]
    hmax = max(horizons)
    need = 168 * bars_per_hour + 1
    for path in files:
        try:
            df = pd.read_feather(path)
        except Exception:
            continue
        if len(df) < need + hmax + 10:
            continue
        c = df["close"].tolist(); h = df["high"].tolist()
        l = df["low"].tolist();  v = df["volume"].tolist()
        ts = df["date"].tolist()
        sym = _pretty(path)
        for i in range(need, len(c) - hmax, sample_every):
            f = _features_at(c, h, l, v, i, bars_per_hour)
            if f is None:
                continue
            if min_dollar_vol and f["dollar_vol_24h"] < min_dollar_vol:
                continue
            entry = c[i]                       # fill at the decision bar's close
            if not entry or entry <= 0:
                continue
            f.update({"symbol": sym, "ts": ts[i], "entry": entry})
            for hb in horizons:
                fwd = (c[i + hb] - entry) / entry * 100.0
                f[f"fwd_{hb}"] = fwd
                # excursions INSIDE the horizon — needed to study exits honestly later
                f[f"mfe_{hb}"] = (max(h[i + 1:i + 1 + hb]) - entry) / entry * 100.0
                f[f"mae_{hb}"] = (min(l[i + 1:i + 1 + hb]) - entry) / entry * 100.0
                # PRIMARY label: a SIGNED move that clears round-trip cost.
                # 0 = no tradeable opportunity either way (the honest majority class).
                f[f"y_{hb}"] = (1 if fwd > ROUND_TRIP_COST_PCT
                                else (-1 if fwd < -ROUND_TRIP_COST_PCT else 0))
            rows.append(f)
    return pd.DataFrame(rows)


def save(df: pd.DataFrame, name: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.feather"
    df.reset_index(drop=True).to_feather(out)
    return out
