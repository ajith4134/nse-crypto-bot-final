"""trading/broker_sense/chart_capture.py — GAP-E: intelligent REAL Binance-UI chart capture.

The owner's ask: make the brain AUTOMATICALLY + INTELLIGENTLY navigate the Binance web page, open a
symbol's chart, ADD ALL the built-in indicators, cycle the multiple timeframes, and SCREENSHOT each
candlestick-pattern chart → into the vision cascade (chart_vlm / cnn_direction / chart_yolo).

This is vision-driven (survives Binance UI redesigns): it reuses HumanUI (see → locate-by-description
→ click at pixels) for every action, and the nav_brain segment-gate discipline so it only ever works
the ACTIVE segments. It's the real-screenshot source the YOLO lane (chart_yolo, trained on real charts)
and the VLM want — complementing the local matplotlib render.

Honest + bounded: every locate/click is best-effort (a missing button is skipped, never a crash); a
per-symbol time budget bounds the whole capture; screenshots are returned as bytes for the cascade and
NOT persisted here (the caller deletes per the owner's step-7 rule). Needs the live headed browser.
"""
from __future__ import annotations

import time

# Binance's built-in overlays the owner runs (IMG_8949): the capture tries to switch each ON.
INDICATORS = ("MA", "EMA", "BOLL", "SAR", "SuperTrend", "AVL", "VOL", "MACD", "RSI")
# tf label as it appears on the Binance web chart toolbar → our canonical key.
TF_LABELS = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h", "1d": "1D"}
_BINANCE_TRADE = "https://www.binance.com/en/trade/{base}_USDT?type=spot"


class IndicatorChartCapture:
    """Drive the live Binance web chart via HumanUI: open → enable indicators → per-TF screenshot."""

    def __init__(self, humanui, *, market: str = "crypto"):
        self.ui = humanui                  # trading.brain.vision.human_ui.HumanUI (has .page, locate)
        self.market = market
        self.stats = {"indicators_on": 0, "tf_shots": 0, "misses": 0}

    # ── low-level vision actions (reused for every step) ─────────────────────────────
    def _click(self, target: str, *, settle_ms: int = 400) -> bool:
        try:
            xy = self.ui.locate(target)
        except Exception:
            xy = None
        if not xy:
            self.stats["misses"] += 1
            return False
        try:
            self.ui.page.mouse.click(float(xy[0]), float(xy[1]))
            self.ui.page.wait_for_timeout(settle_ms)
            return True
        except Exception:
            self.stats["misses"] += 1
            return False

    def _shot(self) -> bytes:
        try:
            return self.ui.page.screenshot(type="png")
        except Exception:
            return b""

    # ── the routine ──────────────────────────────────────────────────────────────────
    def open_chart(self, symbol: str) -> bool:
        base = symbol.split("/")[0].split(":")[0]
        try:
            self.ui.page.goto(_BINANCE_TRADE.format(base=base), timeout=30000,
                              wait_until="domcontentloaded")
            self.ui.page.wait_for_timeout(1500)
            return True
        except Exception:
            return False

    def enable_all_indicators(self) -> int:
        """Open the chart's Indicators menu and switch each built-in ON. Returns how many it toggled.
        Best-effort: whatever it can't locate is skipped (the VLM still reads whatever rendered)."""
        # open the indicators panel (Binance web: an "fx"/"Indicators" button on the chart toolbar)
        if not (self._click("the Indicators button on the chart toolbar (fx icon)")
                or self._click("Indicators")):
            return 0
        n = 0
        for ind in INDICATORS:
            if self._click(f'the "{ind}" indicator in the indicators list', settle_ms=250):
                n += 1
        # close the panel so it doesn't cover the candles
        self._click("close the indicators panel", settle_ms=250) or \
            self.ui.page.keyboard.press("Escape")
        self.stats["indicators_on"] = n
        return n

    def set_timeframe(self, tf: str) -> bool:
        label = TF_LABELS.get(tf, tf)
        return self._click(f'the {label} timeframe button on the chart toolbar')

    def capture(self, symbol: str, timeframes=("15m", "1h", "4h", "1d"),
                *, budget_s: float = 90.0) -> dict:
        """Full GAP-E flow → {tf: png_bytes} for the vision cascade. Bounded by budget_s."""
        t0 = time.monotonic()
        shots: dict[str, bytes] = {}
        if not self.open_chart(symbol):
            return {"symbol": symbol, "shots": {}, "stats": self.stats, "error": "open_chart failed"}
        self.enable_all_indicators()
        for tf in timeframes:
            if time.monotonic() - t0 > budget_s:
                break
            if self.set_timeframe(tf):
                self.ui.page.wait_for_timeout(600)      # let the candles repaint at the new TF
            png = self._shot()
            if png:
                shots[tf] = png
                self.stats["tf_shots"] += 1
            # mirror the real capture so the owner SEES it in the Screen Mirror
            try:
                from trading.broker_sense import screen_mirror
                screen_mirror.record_bytes("binance", png, url=self.ui.page.url)
            except Exception:
                pass
        return {"symbol": symbol, "shots": shots, "stats": self.stats,
                "took_s": round(time.monotonic() - t0, 1)}


def capture_symbol(page, symbol: str, *, market: str = "crypto",
                   timeframes=("15m", "1h", "4h", "1d"), feed_yolo: bool = True) -> dict:
    """Convenience: build a HumanUI on a live page, capture the indicator charts for `symbol`, and
    feed the REAL screenshots to the YOLO pattern lane (chart_yolo — trained on real charts, so the
    live Binance capture is its best-fit input, unlike the synthetic render). Returns {tf: png_bytes}
    + stats + the YOLO read. Honest degrade (empty) if the browser/UI isn't cooperating."""
    try:
        from trading.brain.vision.human_ui import HumanUI
        cap = IndicatorChartCapture(HumanUI(page), market=market)
        rep = cap.capture(symbol, timeframes)
    except Exception as e:
        return {"symbol": symbol, "shots": {}, "error": str(e)[:120]}
    if feed_yolo and rep.get("shots"):
        try:                                # real screenshot → YOLO pattern read, cached per symbol
            import io
            from PIL import Image
            from trading.broker_sense import chart_yolo
            tf0 = next(iter(rep["shots"]))
            img = Image.open(io.BytesIO(rep["shots"][tf0])).convert("RGB")
            rep["yolo"] = chart_yolo.detect_and_cache(symbol, img, tf=tf0, market=market)
        except Exception:
            rep["yolo"] = None
    return rep
