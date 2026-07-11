"""trading/broker_sense/chart_render.py — draw candle charts locally, two flavors.

`plain()`   — the bare 24-bar candlestick picture the vendored CNN (cnn_direction.py, Lane A)
              was TRAINED on. Kept pixel-compatible so the CNN stays in-distribution.
`annotated()` — a Binance-style chart WITH the built-in indicators drawn on it (MA 7/25/99,
              Bollinger Bands, volume, RSI, MACD) for the VLM lane (chart_vlm.py, Lane B) to
              read the indicators off the PICTURE — the owner's 2026-07-11 requirement.

Reuse-first: indicators via TA-Lib (installed, C-fast), rendering via mplfinance (the standard
candlestick+panel plotter). No login and no GPU — this is the rule-4 fail-safe path that always
produces an indicator chart even when the live Binance UI screenshot is unavailable. When we DO
have the real Binance-UI screenshot (with the user's own indicators on it), Lane B reads that
pixel-for-pixel instead; this renderer guarantees an indicator chart either way.
"""
from __future__ import annotations

import os
import time

from trading import state

_SHOT_DIR = "chart_shots"
BARS = 24                       # CNN training window (plain)
ANNOT_BARS = 120                # enough history for MA99 / MACD26 to be valid on the annotated chart


def _shot_dir():
    d = state._path(_SHOT_DIR)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _out(symbol: str, tf: str, tag: str) -> str:
    return str(_shot_dir() / f"{symbol.split('/')[0]}_{tf}_{tag}{int(time.time()*1000)}.png")


def plain(rows: list, symbol: str = "x", tf: str = "x", out_path: str | None = None) -> str | None:
    """The CNN's plain 24-bar candlestick render (behaviour-compatible with the old
    chart_vision._render_api). Returns the png path or None if no data."""
    if not rows:
        return None
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(2.4, 2.4), dpi=100)
    for i, r in enumerate(rows[-BARS:]):
        o, h, l, c = float(r[1]), float(r[2]), float(r[3]), float(r[4])
        up = c >= o
        ax.plot([i, i], [l, h], lw=0.7, color="0.4")
        ax.add_patch(plt.Rectangle((i - 0.33, min(o, c)), 0.66, abs(c - o) or 1e-9,
                                   color=("white" if up else "black"), ec="0.2", lw=0.4))
    ax.set_axis_off()
    fig.tight_layout(pad=0)
    path = out_path or _out(symbol, tf, "p")
    fig.savefig(path, facecolor="0.75")
    plt.close(fig)
    return path


def _frame(rows: list):
    """OHLCV rows [ts,o,h,l,c,v] → mplfinance-ready DataFrame with a DatetimeIndex."""
    import pandas as pd
    ts = [int(r[0]) for r in rows]
    unit = "ms" if ts and ts[0] > 1_000_000_000_000 else "s"   # binance ms vs s
    df = pd.DataFrame({
        "Open": [float(r[1]) for r in rows], "High": [float(r[2]) for r in rows],
        "Low": [float(r[3]) for r in rows], "Close": [float(r[4]) for r in rows],
        "Volume": [float(r[5]) if len(r) > 5 else 0.0 for r in rows],
    }, index=pd.to_datetime(ts, unit=unit))
    return df[~df.index.duplicated(keep="last")].sort_index()


def annotated(rows: list, symbol: str = "x", tf: str = "x",
              out_path: str | None = None) -> str | None:
    """Binance-style chart WITH indicators (MA 7/25/99 + Bollinger + volume + RSI + MACD),
    for the VLM to read. Returns the png path, or None if data/deps unavailable (honest
    degrade — the caller keeps the plain/CNN result)."""
    if not rows or len(rows) < 30:            # too few bars for indicators to mean anything
        return None
    try:
        import numpy as np
        import talib
        import mplfinance as mpf
    except Exception:
        return None
    try:
        import numpy as np
        df = _frame(rows)
        if len(df) < 30:
            return None
        c = df["Close"].to_numpy(dtype="float64")
        h = df["High"].to_numpy(dtype="float64")
        low = df["Low"].to_numpy(dtype="float64")
        v = df["Volume"].to_numpy(dtype="float64")
        # Binance's built-in overlay set (from the owner's IMG_8949): MA+EMA(7/25/99), BOLL,
        # SAR, AVL(=VWAP), plus RSI + MACD sub-panels.
        ma7, ma25, ma99 = talib.SMA(c, 7), talib.SMA(c, 25), talib.SMA(c, 99)
        ema7, ema25, ema99 = talib.EMA(c, 7), talib.EMA(c, 25), talib.EMA(c, 99)
        bb_u, _bb_m, bb_l = talib.BBANDS(c, timeperiod=20, nbdevup=2, nbdevdn=2)
        sar = talib.SAR(h, low, acceleration=0.02, maximum=0.2)
        typ = (h + low + c) / 3.0
        avl = np.cumsum(typ * v) / np.maximum(np.cumsum(v), 1e-9)       # AVL ≈ VWAP
        rsi = talib.RSI(c, timeperiod=14)
        macd, macd_sig, macd_hist = talib.MACD(c, 12, 26, 9)
        aps = [                                                    # overlays on the price panel
            mpf.make_addplot(ma7, color="#f0b90b", width=0.7),     # Binance yellow
            mpf.make_addplot(ma25, color="#e056fd", width=0.7),
            mpf.make_addplot(ma99, color="#4bc0c0", width=0.7),
            mpf.make_addplot(ema25, color="#f6465d", width=0.6, linestyle="--"),
            mpf.make_addplot(avl, color="#845ec2", width=0.8),     # AVL/VWAP
            mpf.make_addplot(sar, type="scatter", markersize=4, marker=".", color="#eaecef"),
            mpf.make_addplot(bb_u, color="#787b86", width=0.5, linestyle="--"),
            mpf.make_addplot(bb_l, color="#787b86", width=0.5, linestyle="--"),
            mpf.make_addplot(rsi, panel=2, color="#f0b90b", width=0.9, ylabel="RSI"),
            mpf.make_addplot([70] * len(df), panel=2, color="#f6465d", width=0.5, linestyle="--"),
            mpf.make_addplot([30] * len(df), panel=2, color="#0ecb81", width=0.5, linestyle="--"),
            mpf.make_addplot(macd, panel=3, color="#0ecb81", width=0.9, ylabel="MACD"),
            mpf.make_addplot(macd_sig, panel=3, color="#f6465d", width=0.9),
            mpf.make_addplot(macd_hist, panel=3, type="bar", color="#787b86", alpha=0.5),
        ]
        mc = mpf.make_marketcolors(up="#0ecb81", down="#f6465d", edge="inherit",
                                   wick="inherit", volume="in")
        style = mpf.make_mpf_style(base_mpf_style="nightclouds", marketcolors=mc,
                                   facecolor="#161a1e", edgecolor="#2b3139",
                                   gridcolor="#2b3139")
        path = out_path or _out(symbol, tf, "a")
        fig, axlist = mpf.plot(df, type="candle", style=style, addplot=aps, volume=True,
                               panel_ratios=(6, 1.4, 2, 2), figsize=(7.6, 6.8), figscale=1.0,
                               title=f"{symbol} {tf}", tight_layout=True, returnfig=True)
        _overlay_volume_profile(axlist[0], rows)          # the video's Volume Profile + value area
        fig.savefig(path, dpi=110)
        import matplotlib.pyplot as plt
        plt.close(fig)
        return path if os.path.exists(path) else None
    except Exception:
        return None


def _overlay_volume_profile(ax, rows: list) -> None:
    """Draw the Volume Profile histogram (left, horizontal) + VAH/VAL/POC lines on the price
    axis — the exact visual from the owner's champions-chart-strategy video. Best-effort."""
    try:
        from trading.broker_sense import volume_profile as vp
        p = vp.volume_profile(rows)
        if not p.get("available"):
            return
        x0, x1 = ax.get_xlim()
        width = (x1 - x0) * 0.16                          # VP occupies the left 16% of the panel
        maxv = max((vv for _, vv in p["hist"]), default=0.0) or 1.0
        bs = p["bin_size"] * 0.9
        for price, vol in p["hist"]:
            ax.barh(price, width * vol / maxv, left=x0, height=bs, align="center",
                    color="#f0b90b", alpha=0.22, zorder=0)
        for lvl, col, lbl in ((p["vah"], "#787b86", "VAH"), (p["val"], "#787b86", "VAL"),
                              (p["poc"], "#f0b90b", "POC")):
            ax.axhline(lvl, color=col, lw=0.9, ls="--", alpha=0.75, zorder=1)
            ax.text(x1, lvl, f" {lbl}", color=col, fontsize=6, va="center", ha="left")
    except Exception:
        return
