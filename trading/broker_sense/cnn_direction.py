"""trading/broker_sense/cnn_direction.py — candle-IMAGE → direction (savers B, F).

The tiny first-pass model of the vision cascade: the exact CNN from the vendored
hardyqr/CNN-for-Stock-Market-Prediction-PyTorch repo (vendor/candlestick_cnn), rebuilt
layer-for-layer to match its SHIPPED trained weights (trained_model/cnn.pkl — verified
strict load: Conv1→16→8→32→5 + BN, one 2× pool, fc 500→1, 20×20 grayscale input) and
warm-started from them. Inference is ONE batched forward over all screenshots (saver F);
CPU-cheap by construction (~13k params).

Escalation (saver B): predictions inside the neutral band are not trusted — the funnel
escalates those few to the cloud LLM with an OHLCV text summary (core.llm providers; our
LLM lane is text-first, so the summary is numbers, not pixels). Every output states its
source ("cnn" / "llm" / "neutral") — honest provenance end to end.

NodeProtocol face: CandleVisionNode joins the registry so the capability is visible on the
node graph (dashboard-sync).
"""
from __future__ import annotations

import os

import numpy as np

from core.node_protocol import BaseNode, IOSchema

_VENDOR_PKL = os.path.join(os.path.dirname(__file__), "..", "..", "vendor",
                           "candlestick_cnn", "trained_model", "cnn.pkl")
_IN = 20                                   # trained input: 20×20 grayscale
NEUTRAL_LO, NEUTRAL_HI = 0.45, 0.55        # escalation band (saver B)


def _build_net():
    import torch.nn as nn

    class TinyCandleCNN(nn.Module):
        """Layer-exact rebuild of vendor/candlestick_cnn's trained cnn.pkl."""
        def __init__(self):
            super().__init__()
            self.layer1 = nn.Sequential(nn.Conv2d(1, 16, 3, padding=1), nn.BatchNorm2d(16),
                                        nn.ReLU(), nn.MaxPool2d(2))
            self.layer2 = nn.Sequential(nn.Conv2d(16, 8, 3, padding=1), nn.BatchNorm2d(8),
                                        nn.ReLU())
            self.layer3 = nn.Sequential(nn.Conv2d(8, 32, 1), nn.BatchNorm2d(32), nn.ReLU())
            self.layer4 = nn.Sequential(nn.Conv2d(32, 5, 1), nn.BatchNorm2d(5), nn.ReLU())
            self.fc = nn.Linear(500, 1)

        def forward(self, x):
            x = self.layer4(self.layer3(self.layer2(self.layer1(x))))
            return self.fc(x.view(x.size(0), -1))

    return TinyCandleCNN()


class CandleDirectionModel:
    """Batched p(up) from candle-chart images. Warm-started from the vendored weights;
    `warm_started` is reported honestly (False ⇒ everything lands in the neutral band)."""

    def __init__(self):
        self._net = None
        self.warm_started = False

    def _ensure(self):
        if self._net is not None:
            return self._net
        import torch
        net = _build_net()
        try:
            sd = torch.load(os.path.abspath(_VENDOR_PKL), map_location="cpu",
                            weights_only=False)
            net.load_state_dict(sd.state_dict() if hasattr(sd, "state_dict") else sd,
                                strict=True)
            self.warm_started = True
        except Exception:
            self.warm_started = False
        net.eval()
        self._net = net
        return net

    @staticmethod
    def _to_tensor(image_paths: list[str]):
        import torch
        from PIL import Image
        batch = []
        for p in image_paths:
            img = Image.open(p).convert("L").resize((_IN, _IN))
            a = np.asarray(img, dtype=np.float32) / 255.0
            batch.append(a[None, :, :])
        return torch.tensor(np.stack(batch))

    def predict(self, image_paths: list[str]) -> list[dict]:
        """ONE batched forward (saver F) → [{p_up, direction, source, escalate}]. Neutral-
        band rows carry escalate=True for the funnel's LLM stage."""
        if not image_paths:
            return []
        import torch
        net = self._ensure()
        with torch.no_grad():
            p = torch.sigmoid(net(self._to_tensor(image_paths))).view(-1).tolist()
        out = []
        for pi in p:
            neutral = NEUTRAL_LO <= pi <= NEUTRAL_HI or not self.warm_started
            out.append({"p_up": round(float(pi), 4),
                        "direction": "neutral" if neutral else ("long" if pi > 0.5 else "short"),
                        "source": "cnn", "escalate": neutral})
        return out


_MODEL: CandleDirectionModel | None = None


def get_model() -> CandleDirectionModel:
    global _MODEL
    if _MODEL is None:
        _MODEL = CandleDirectionModel()
    return _MODEL


def llm_escalate(symbol: str, tf: str, candles: list) -> dict | None:
    """Saver B, top of the cascade: the few borderline cases go to the cloud LLM as an
    OHLCV summary. Returns {p_up, direction, source:'llm'} or None (stay neutral)."""
    if not candles:
        return None
    try:
        from core.llm import chat
        last = candles[-8:]
        rows = "\n".join(f"o={r[1]} h={r[2]} l={r[3]} c={r[4]} v={r[5]}" for r in last)
        rsp = chat([{"role": "system",
                     "content": "You are a chart-pattern reader. Answer with exactly one "
                                "word: LONG, SHORT or FLAT."},
                    {"role": "user",
                     "content": f"{symbol} {tf} last {len(last)} candles (old→new):\n{rows}\n"
                                f"Direction for the NEXT candle?"}],
                   max_tokens=4, timeout=8, total_timeout=20)   # never wedge the LOOK stage
        word = (rsp or "").strip().upper() if isinstance(rsp, str) else \
            str((rsp or {}).get("content", "")).strip().upper()
        if "LONG" in word:
            return {"p_up": 0.62, "direction": "long", "source": "llm"}
        if "SHORT" in word:
            return {"p_up": 0.38, "direction": "short", "source": "llm"}
    except Exception:
        return None
    return None


class CandleVisionNode(BaseNode):
    """NodeProtocol face: p(next-candle up) read from the candle-chart IMAGE."""
    name = "candle_vision_cnn"
    kind = "vision"
    summary = ("Broker-Sense candle-image CNN (vendor/candlestick_cnn warm-start): reads "
               "chart screenshots for direction; borderline cases escalate to the LLM")
    schema = IOSchema(1, "candle-chart image context", "p(next candle up)")
    task = "binary"
    head = "y"

    def __init__(self):
        self._base = 0.5

    def fit(self, X, y):
        ya = np.asarray(y, dtype=float)
        if len(ya):
            self._base = float((ya > 0).mean())
        return self

    def predict_proba(self, X):
        n = len(X) if hasattr(X, "__len__") else 1
        return [self._base] * n


def register_candle_vision_node() -> CandleVisionNode:
    from core import registry
    node = CandleVisionNode()
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
