# Free / local / 24-7 "eyes" for the browser GUI agent (2026-07-07)

Goal: brain SEES broker web apps without paid/rate-limited cloud vision. Solution = turn
"look at pixels" into "read structured text + data" via a local perception ladder.

## Already installed in the venv (no new install needed)
- **rapidocr 3.9.1** (onnxruntime 1.27, CPU) — word-level boxes, ~50ms/img — **PRIMARY OCR**
- **paddleocr 3.7.0** + paddlepaddle 3.3.1 — fallback OCR (already used in book_monitor.py)
- torch 2.10+cpu, torchvision, transformers 4.57 — can load a small local VLM later
- playwright 1.60

## Existing repo infra reused (the big win — mostly wiring)
| Component | File | Gives (free) |
|---|---|---|
| NetworkRecorder | broker_sense/interception.py | app's own JSON feed by kind (candles/orderbook/ticker…) |
| _extract_from_page | brain/vision/ocular_cortex.py | DOM interactive elements + bounding boxes + screenshot |
| OcularCortex / LayoutMemory | brain/vision/ocular_cortex.py | golden-path control coords per layout (skip vision on known screens) |
| BookMonitor (OcrReader) | broker_sense/book_monitor.py | PaddleOCR region read (bid/ask) |
| discover_from_text | broker_sense/learning_columns.py | mine "<label> <number>" pairs from text |

## OCR ranking (word boxes → click coords)
1. **RapidOCR** (ONNX, fast CPU, installed) — PRIMARY
2. **PaddleOCR** (installed, proven) — FALLBACK
3. EasyOCR / Tesseract / docTR — skip (slower / heavier / obsolete for UI)

## Local VLM ranking (CPU) — OPTIONAL future, NOT needed now
1. **OmniParser** (MS) — best GUI element detection→boxes, but **GPU-only** (future upgrade)
2. **moondream2** (0.5B) — CPU-runnable ~2-5s/frame, lightweight — best CPU fallback if ever needed
3. Florence-2-base — CPU but slow (~8-15s); Qwen2-VL-2B / MiniCPM-V — GPU-preferred; ShowUI/Ferret-UI — GPU-only

## Built (commit 0b0fbf0): trading/brain/vision/free_eyes.py
- `FreeEyes(page, broker)`: glance() = DOM controls + OCR words + captured net JSON.
- `locate(target)`: DETERMINISTIC text-match (token-overlap, plural/substring tolerant) → pixel centre, 0 LLM.
- `read()`: extract screen text → answer via the TEXT model (core.llm.chat), not vision.
- human_ui.locate/read/perceive + explore()'s decision rewired FREE-FIRST; cloud vision = last resort.
- Verified live on Upstox Pro (no cloud vision): 115 OCR words, locate('Pin new symbols')→(1576,120), read watchlist with prices.

## Known refinement
- NetworkRecorder must attach BEFORE page navigation to capture the JSON feed (in the live
  test net kinds were empty because attach ran post-load). DOM+OCR already cover the need;
  wiring attach earlier (in sessions.page before goto) unlocks the network sense for candles/depth.
