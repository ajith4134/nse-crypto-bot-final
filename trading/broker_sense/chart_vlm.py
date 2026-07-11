"""trading/broker_sense/chart_vlm.py — Lane B of the vision cascade: read the chart IMAGE
with a free multimodal LLM (the brain's "eyes"), WITH Binance's built-in indicators drawn
on it, and emit a structured direction value for the equation.

Owner ask (2026-07-11): feed multi-timeframe candlestick charts WITH the broker's built-in
indicators — screenshotted from our real Binance web UI — into a DL model that reads the
PICTURE (not an OHLCV text summary) and returns a value. The vendored 20×20 CNN
(cnn_direction.py, Lane A) is a fast first-pass but is blind to indicators/annotations; this
lane hands the full-resolution annotated chart to a vision model that reads RSI/MACD/MA/BB/
volume and candlestick patterns natively.

Reuse-first: the model is `core.llm.vision_chat` — our repaired 2026-07-11 free vision chain
(gemini-2.0-flash → gemma-4-31b → nemotron-vl → qwen-vl). NO GPU, NO paid API, NO training:
it runs entirely on free multimodal tiers and degrades honestly (returns None) when every
vision provider is rate-limited or unconfigured, so the funnel is never wedged.

Output is a horizon-tagged scalar `score∈[-1,1]` (+ p_up, patterns, indicator reads,
rationale, honest provenance) — the shape the P1 feature bus consumes to feed the
symbolic-regression direction equation (alphagen / Operon / pysr, Rank-IC scored).

NodeProtocol face: ChartVLMNode joins the registry so the capability shows on the node graph.
"""
from __future__ import annotations

import json
import re

from core.node_protocol import BaseNode, IOSchema

# One tight instruction so cheap/fast free models still return parseable JSON. We ask for the
# fields the equation needs and NOTHING else — score is the headline feature; the rest is for
# the decision_snapshot / audit trail (honest provenance of WHAT the model saw).
_SYSTEM = (
    "You are a professional technical analyst reading a Binance candlestick chart image with "
    "the exchange's built-in indicators drawn on it: MA & EMA (7/25/99), Bollinger Bands, "
    "Parabolic SAR (dots), VWAP/AVL, RSI and MACD sub-panels, volume, and a Volume Profile "
    "histogram on the left with the Value Area high/low (VAH/VAL) and Point of Control (POC) "
    "marked. Read whichever are visible.\n"
    "Apply auction/volume-profile logic as your primary lens: where is price vs the Value Area? "
    "A FAILED AUCTION is high-conviction — if price poked OUTSIDE the value area then closed "
    "back INSIDE (especially on rising volume or absorption, a volume wall the other side can't "
    "break), lean toward reversion INTO the value area (long if it failed below VAL, short if it "
    "failed above VAH). Also weigh trend (MA/EMA ribbon, SAR flips, MACD), momentum (RSI), and "
    "band position. Judge the most likely NEXT move.\n"
    "You MUST answer. Do NOT refuse, do NOT say you need more context or a timeframe — commit to "
    "long, short, or flat from what is visible. Output ONLY the JSON object, nothing before or "
    "after it (no prose, no markdown fences). Exactly this schema:\n"
    '{"direction":"long|short|flat","score":<float -1..1, - = down, + = up>,'
    '"confidence":<float 0..1>,"patterns":[<candlestick/chart/auction patterns you see>],'
    '"indicators":{<indicator>:<short read, e.g. "RSI 71 overbought","price below VAL">},'
    '"rationale":"<one sentence>"}\n'
    'Example: {"direction":"long","score":0.45,"confidence":0.6,"patterns":["failed auction below VAL"],'
    '"indicators":{"RSI":"41 rising","price":"back inside value"},"rationale":"reversion into value area"}'
)


def _parse(raw: str) -> dict | None:
    """Robustly pull the JSON object out of a VLM reply (may be fenced or chatty)."""
    if not raw or not isinstance(raw, str):
        return None
    txt = raw.strip()
    if "```" in txt:                                   # strip ``` / ```json fences
        txt = re.sub(r"```(?:json)?", "", txt).strip()
    m = re.search(r"\{.*\}", txt, re.DOTALL)           # first {...} span
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except (json.JSONDecodeError, ValueError):
        return None


def _norm(obj: dict) -> dict:
    """Coerce a parsed VLM object into the canonical feature shape (never raises)."""
    try:
        score = float(obj.get("score"))
    except (TypeError, ValueError):
        score = None
    direction = str(obj.get("direction", "")).strip().lower()
    if score is None:                                  # derive from the word if score missing
        score = {"long": 0.5, "short": -0.5, "flat": 0.0}.get(direction, 0.0)
    score = max(-1.0, min(1.0, score))
    if direction not in ("long", "short", "flat"):     # derive from the number if word missing
        direction = "long" if score > 0.15 else "short" if score < -0.15 else "flat"
    try:
        conf = max(0.0, min(1.0, float(obj.get("confidence"))))
    except (TypeError, ValueError):
        conf = abs(score)
    patterns = obj.get("patterns") or []
    if not isinstance(patterns, list):
        patterns = [str(patterns)]
    indicators = obj.get("indicators") or {}
    if not isinstance(indicators, dict):
        indicators = {}
    return {
        "score": round(score, 4),
        "p_up": round(0.5 + score / 2.0, 4),           # map [-1,1] → [0,1] for the CNN-parity lane
        "direction": direction,
        "confidence": round(conf, 4),
        "patterns": [str(p) for p in patterns][:8],
        "indicators": {str(k): str(v) for k, v in list(indicators.items())[:8]},
        "rationale": str(obj.get("rationale", ""))[:240],
        "source": "vlm",
    }


def read_chart(images, symbol: str = "", tf: str = "", *, context: str | None = None,
               timeout: int = 20, total_timeout: float = 30.0) -> dict | None:
    """Read chart image(s) with the free vision chain → structured direction value.

    `images` is one image or a list (file path | PNG/JPEG bytes | base64 | data URL) — pass a
    multi-timeframe stack (e.g. 1m/5m/15m/1h/4h/1d) to read them together for one symbol.
    `context` is optional grounding text (e.g. the computed POC/VAH/VAL + migration bias) so the
    model reasons from exact levels instead of eyeballing them. Returns the canonical feature
    dict, or None if no vision provider answered (honest degrade; caller keeps the CNN/neutral
    result). Never raises — perception must not wedge the funnel."""
    try:
        from core import llm
        if not llm.vision_available():                 # no free vision key configured
            return None
        tag = f"{symbol} {tf}".strip()
        prompt = (f"Chart(s) for {tag}. " if tag else "") + \
            "Read the indicators and candlesticks and return the JSON."
        if context:
            prompt += f"\nMeasured levels for grounding (verify against the picture): {context}"
        raw = llm.vision_chat(prompt, images, system=_SYSTEM, max_tokens=320,
                              temperature=0.1, timeout=timeout, total_timeout=total_timeout)
    except Exception:
        return None
    obj = _parse(raw)
    if obj is None:
        return None
    out = _norm(obj)
    out["symbol"], out["tf"] = symbol, tf              # horizon tag for the feature bus
    return out


class ChartVLMNode(BaseNode):
    """NodeProtocol face: next-bar direction read from the indicator-annotated chart IMAGE
    by a free multimodal LLM (the deep lane of the vision cascade)."""
    name = "chart_vlm"
    kind = "vision"
    summary = ("Broker-Sense VLM chart reader: free multimodal LLM reads the Binance-UI chart "
               "WITH built-in indicators (RSI/MACD/MA/BB/vol) → structured direction score for "
               "the equation; degrades honestly when vision providers are throttled")
    schema = IOSchema(1, "indicator-annotated chart image", "direction score [-1,1] → p(up)")
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


def register_chart_vlm_node() -> ChartVLMNode:
    from core import registry
    node = ChartVLMNode()
    try:
        registry.register(node, summary=node.summary)
    except Exception:
        pass
    return node
