"""trading/broker_sense/chart_yolo.py — Lane C of the vision cascade: YOLOv8 chart-pattern detection.

Reuses ChartScanAI (Omar-Karimov/ChartScanAI, vendored at vendor/ChartScanAI) — a YOLOv8 detector
trained to spot **Buy / Sell pattern regions** on candlestick chart images. Fast CPU inference
(~sub-second/image, no GPU), so unlike the VLM lane it CAN run in the funnel. We aggregate its
bounding-box detections into a single bullish/bearish confidence scalar — the third independent lane
of the vision cascade:

  Lane A  cnn_direction.py  — tiny trained CNN → p(next candle up)
  Lane B  chart_vlm.py      — multimodal LLM → structured {direction, score, patterns, indicators}
  Lane C  chart_yolo.py     — YOLOv8 → detected Buy/Sell pattern confidence  ← THIS

Honest by construction: returns None when ultralytics or the trained weights are absent (the lane
simply doesn't contribute); never raises into the funnel. NodeProtocol face joins the node graph.
"""
from __future__ import annotations

import math
import os

from core.node_protocol import BaseNode, IOSchema

_WEIGHTS = os.path.join(os.path.dirname(__file__), "..", "..", "vendor", "ChartScanAI",
                        "weights", "custom_yolov8.pt")
_MODEL = None
_MODEL_TRIED = False


def available() -> bool:
    """True if ultralytics is importable AND the trained weights exist."""
    if not os.path.exists(os.getenv("CHART_YOLO_WEIGHTS", _WEIGHTS)):
        return False
    try:
        import ultralytics  # noqa: F401
        return True
    except Exception:
        return False


def _model():
    """Lazy-load the YOLOv8 model once (singleton). Returns None on any failure."""
    global _MODEL, _MODEL_TRIED
    if _MODEL is not None or _MODEL_TRIED:
        return _MODEL
    _MODEL_TRIED = True
    try:
        from ultralytics import YOLO
        path = os.getenv("CHART_YOLO_WEIGHTS", _WEIGHTS)
        if not os.path.exists(path):
            return None
        _MODEL = YOLO(path)
    except Exception:
        _MODEL = None
    return _MODEL


def detect(image, *, conf: float = 0.10, symbol: str = "", tf: str = "") -> dict | None:
    """Detect Buy/Sell pattern regions on a chart image → aggregated direction scalar.

    `image` is a file path | PIL image | numpy array | bytes (whatever ultralytics accepts; a
    path is simplest). Returns {score∈[-1,1], p_up, direction, buy_conf, sell_conf, n_buy,
    n_sell, source, symbol, tf} or None if the lane is unavailable / errored. Never raises.

    conf default 0.10 (not YOLO's usual 0.25): ChartScanAI was trained on a specific chart-image
    distribution; on real broker screenshots (its best-fit input) detections are confident-but-
    fewer, so a lower gate improves recall. It finds ~nothing on our synthetic matplotlib renders
    — feed it the REAL app screenshot pixels (the eyes' captures), not a local render."""
    model = _model()
    if model is None:
        return None
    try:
        results = model.predict(image, conf=conf, verbose=False)
    except Exception:
        return None
    buy_conf = sell_conf = 0.0
    n_buy = n_sell = 0
    try:
        names = model.names or {0: "Buy", 1: "Sell"}
        for r in results:
            boxes = getattr(r, "boxes", None)
            if boxes is None:
                continue
            for cls, cf in zip(boxes.cls.tolist(), boxes.conf.tolist()):
                label = str(names.get(int(cls), "")).lower()
                if label == "buy":
                    buy_conf += float(cf)
                    n_buy += 1
                elif label == "sell":
                    sell_conf += float(cf)
                    n_sell += 1
    except Exception:
        return None
    # net bullish-minus-bearish confidence → squashed to [-1,1] (tanh keeps a single strong
    # detection from saturating; multiple agreeing detections push harder).
    score = math.tanh(buy_conf - sell_conf)
    direction = "long" if score > 0.15 else "short" if score < -0.15 else "flat"
    return {
        "score": round(score, 4), "p_up": round(0.5 + score / 2.0, 4), "direction": direction,
        "buy_conf": round(buy_conf, 4), "sell_conf": round(sell_conf, 4),
        "n_buy": n_buy, "n_sell": n_sell, "source": "yolo", "symbol": symbol, "tf": tf,
    }


_CACHE_FILE = "broker_sense_yolo_cache.json"
_MAX_AGE = 900.0                             # a pattern read is usable for ~15 min


def detect_and_cache(symbol: str, image, *, tf: str = "", market: str = "crypto") -> dict | None:
    """Run detect() on a REAL chart screenshot and cache the result per symbol so the fusion can
    read it without holding the model in the hot path. Returns the read (or None). Never raises."""
    read = detect(image, symbol=symbol, tf=tf)
    if read is None:
        return None
    try:
        import time
        from trading import state
        cache = state.load_json(_CACHE_FILE, {}) or {}
        cache[symbol] = {"ts": time.time(), "read": read}
        # keep the cache bounded (drop the oldest beyond 200 symbols)
        if len(cache) > 200:
            for k in sorted(cache, key=lambda k: cache[k].get("ts", 0))[:40]:
                cache.pop(k, None)
        state.save_json(_CACHE_FILE, cache)
    except Exception:
        pass
    return read


def cached(symbol: str, *, max_age: float = _MAX_AGE) -> dict | None:
    """Freshest cached YOLO read for `symbol`, or None if absent/stale."""
    try:
        import time
        from trading import state
        hit = (state.load_json(_CACHE_FILE, {}) or {}).get(symbol)
        if hit and (time.time() - hit.get("ts", 0)) <= max_age:
            return hit.get("read")
    except Exception:
        pass
    return None


class ChartYoloNode(BaseNode):
    """NodeProtocol face: next-move bias from YOLOv8-detected Buy/Sell chart patterns (Lane C)."""
    name = "chart_yolo"
    kind = "vision"
    summary = ("Broker-Sense YOLOv8 pattern lane (vendor/ChartScanAI): detects Buy/Sell pattern "
               "regions on the candle chart → bullish/bearish confidence scalar; CPU sub-second, "
               "degrades honestly when weights/ultralytics absent")
    schema = IOSchema(1, "candle-chart image", "pattern-detection direction score [-1,1] → p(up)")
    task = "binary"
    head = "y"

    def __init__(self):
        self._base = 0.5

    def fit(self, X, y):
        import numpy as np
        ya = np.asarray(y, dtype=float)
        if len(ya):
            self._base = float((ya > 0).mean())
        return self

    def predict_proba(self, X):
        n = len(X) if hasattr(X, "__len__") else 1
        return [self._base] * n


def register_chart_yolo_node() -> ChartYoloNode:
    from core import registry
    node = ChartYoloNode()
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
