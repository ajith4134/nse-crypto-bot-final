# champions-chart-strategy — build record (BUILT 2026-07-11)

Owner approved ALL 8 ideas from understanding.md, built fully, daily-session value area for every
symbol/segment the brain opens (UTC day for crypto, IST trading day for NSE/MCX). Status: SHIPPED.

## What was built (reuse-first, tested)
- **`trading/broker_sense/volume_profile.py`** (NEW) — VP/Value-Area engine: `volume_profile`
  (POC/VAH/VAL 70% value area), `session_key` (segment-aware daily bucket), `value_migration`
  (POC building higher/lower → bias), `failed_auction` (poke-out + close-back-inside + volume
  pickup → long/short), `absorption` (declining volume on a move + wall), `order_plan` (VAH/VAL
  target + swing stop), `features` (bounded tilt + snapshot). 16 tests. Ideas 1-4, 7.
- **`indicator_fusion.py`** — 4f VP lens (bounded ±0.15 tilt into confluence, every segment) +
  6b VP order plan into the triple-barrier when a failed-auction drives. Snapshot: `volume_profile`.
- **`chart_render.py`** — `annotated()` now draws the Binance built-in set (MA+EMA 7/25/99, BOLL,
  SAR, AVL/VWAP, RSI, MACD) + the Volume Profile histogram + VAH/VAL/POC lines (matches the
  owner's IMG_8949 + the video visual). Idea 6.
- **`chart_vlm.py`** — VLM prompt teaches value-area / failed-auction / absorption + the Binance
  indicators; `read_chart(context=…)` grounds the model with measured POC/VAH/VAL. Idea 5.
- **`chart_vision.py`** — `_vision_escalate` passes the measured VP levels as VLM grounding.
- **Strategy library** — `features_ext.py` rolling `vp_*` columns (reuses the VP engine) +
  `catalog/volume_flow.py` `flow_vp_failed_auction` + `flow_vp_value_position`; the generator/
  evolver can now weight the auction edge per coin. Idea 8.

## Verified
- 100 tests green across VP/render/vlm/fusion/library; broker_sense 29 green; INDEX.md refreshed.
- VP engine on real BTC 15m: POC 64189 / VAH 64380 / VAL 63789 (VA 70.7%), migration bullish.
- Annotated render (VP + full indicators) confirmed visually (scratchpad/sample_annotated_vp.png).

## Deferred to next increment (owner said "add more ideas like this when you find them")
- Real Binance-UI screenshot capture with indicators toggled ON (currently the local render is the
  indicator source; the live-UI screenshot path in chart_vision._capture_app is plain).
- Lane C: ChartScanAI YOLOv8 pattern lane. Direction-equation P2 (Operon/pysr) / P3 / P4.
