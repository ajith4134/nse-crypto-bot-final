# Chart-image ML/DL models → direction value (research, 2026-07-11)

Owner ask (2026-07-11): feed **multi-timeframe candlestick charts WITH Binance's built-in
indicators, screenshotted from our real Binance web account UI**, into image/chart ML/DL
models that output a value → into the direction equation. "search for the ml or dl models
which use pics or charts to give value, using only the Binance account UI."

## What we ALREADY have (map-before-research — reuse-first)
- **`vendor/candlestick_cnn/`** — hardyqr CNN-for-Stock-Market-Prediction (J.P. Morgan
  "Trading via Image Classification", arXiv:1907.10046). Trained weights shipped.
- **`trading/broker_sense/cnn_direction.py`** — `CandleDirectionModel`: candle-image →
  p_up scalar, batched CPU (~13k params, 20×20 grayscale), registered `CandleVisionNode`.
- **`trading/broker_sense/chart_vision.py`** — ALREADY captures 1m/5m/15m/1h/4h/1d per pick
  (broker-app chart → TradingView → local matplotlib render fallback), sha256-dedup, batches
  to the CNN, deletes screenshots after. Multi-TF capture is DONE.
- **`core/llm.py vision_chat()`** — free multimodal lane (gemini-2.0-flash / gemma-4-31b /
  nemotron-vl), just repaired 2026-07-11. Reads full-res images natively.
- **GAP 1:** current charts are PLAIN candlesticks — Binance built-in indicators NOT drawn.
- **GAP 2:** the neutral-band escalation is **TEXT-only** (OHLCV numbers), not the picture —
  so indicators/patterns visible in the image are thrown away.
- **GAP 3:** only the tiny 20×20 CNN; no modern high-capacity image reader.

## Phase-1 shortlist (cheap signals only — no source read yet)

| Project | Repo | What it does | In/Out | Fit | Verdict |
|---|---|---|---|---|---|
| **VLM lane (reuse ours)** | core/llm.vision_chat | Free multimodal LLM reads full-res chart WITH indicators, zero training, understands drawn indicators/patterns natively | annotated PNG → structured {dir, score, patterns} | **10** | **PRIMARY upgrade** — turn the text escalation into a VISION read of the indicator chart |
| candlestick_cnn (ours) | hardyqr/CNN-for-Stock-Market-Prediction-PyTorch | Tiny CNN, trained weights, CPU-cheap first-pass | 20×20 gray → p_up | 9 | **KEEP** as fast first-pass |
| **ChartScanAI** | Omar-Karimov/ChartScanAI | YOLOv8 detects chart patterns → Buy/Sell boxes; crypto-supported, real-time | chart PNG → detections+conf | **8** | **ADD** (vendor) — explicit pattern lane → bullish/bearish confidence scalar |
| foduucom/Stockmarket-pattern-detection | foduucom | YOLOv8 pattern detector on HuggingFace | chart PNG → detections | 7 | backup to ChartScanAI |
| amit-agni/candlesticks-deeplearning | amit-agni | Keras CNN, 5-day sliding-window image classifier | chart img → up/down | 5 | redundant w/ our CNN (TF/Keras) |
| PeerJ/PMC 2025 CNN (Japanese candlesticks) | peerj cs-2719 | Recent CNN on candlestick patterns | img → class | 4 | reference/paper (code thin) |
| Vision Transformer (custom) | various | ViT fine-tuned on chart images | img → class | 6 | VLM covers this zero-shot; revisit only if we train |

## Recommendation — STITCH a 3-lane vision cascade (all emit a scalar → equation feature)
1. **Lane A (fast): existing CNN** — first-pass p_up on every (symbol, TF) screenshot (kept).
2. **Lane B (deep): VLM chart reader** — `vision_chat` on the **Binance-UI chart WITH
   built-in indicators** → structured `{direction, score∈[-1,1], patterns[], rationale}`.
   Replaces the text-only escalation; runs on the neutral band + higher TFs (bias). FREE.
3. **Lane C (patterns): ChartScanAI YOLOv8** (vendor) → detected-pattern bullish/bearish
   confidence scalar.
- **Fuse** A+B+C per (symbol, TF) → horizon-tagged `chart_*` features into the **P1 feature
  bus** → the symbolic-regression direction equation (alphagen/Operon/pysr, Rank-IC scored).
- Needs GAP-1 fix: capture Binance charts with indicators ON (extend chart_vision capture).

## Deps status (2026-07-11, ask-to-install approved)
- pyoperon 0.6.1 ✅ installed · pysr 1.5.10 ✅ (Julia provisions on first fit) · pyoperon+pysr
  = equation engine (P2). mlfinlab = **removed from PyPI (went commercial)** → OSS replacement
  **mlfinpy** (+ `timeseriescv` for purged CV); RiskLabAI available but its numba build failed.

Sources: hardyqr/CNN-for-Stock-Market-Prediction-PyTorch · Omar-Karimov/ChartScanAI ·
foduucom/Stockmarket-pattern-detection · amit-agni/candlesticks-deeplearning · peerj.com/articles/cs-2719
