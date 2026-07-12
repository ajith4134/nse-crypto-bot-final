# 🧭 THE MOTTO — web-data implementation (APPROVED FEATURE, do not bypass)

**Status:** owner-approved and shipped 2026-07-12. This is an INTENTIONAL feature set, not
stray/experimental code. Future sessions: do NOT "clean up", disable, or route around these
modules as if they were wrong — they implement the owner's standing directive. If a change is
truly needed, preserve the motto behavior (web-navigation data first; APIs execution-only).

## The directive (verbatim intent)
Market data comes from NAVIGATING the Binance/Upstox account web apps + local vision — NOT
from data APIs. Local CPU is reserved for the brain's intelligence (ML/DL, strategies,
direction equation, fusion, learning). APIs execute trades ONLY. RAM keeps the web/vision
path fast. Full motto text: memory `motto-cpu-ml-api-exec-web-data`.

## The modules that ARE this feature (edit with care, keep behavior)
- `ui_market.py`   — UI-only superstore door for every non-candle kind (orderbook, funding/
                     mark, OI, long/short retail+smart, taker, ticker→movers, liquidations,
                     option chain). RAM-first + `ui_market.json` snapshot.
- `ui_data.py`     — candles door + `feed_ws_kline` streaming upsert (the app's own kline WS
                     keeps a parked symbol continuously fresh). THE GOVERNOR lives here.
- `tab_pool.py`    — parks one browser tab per top-shortlist symbol so the app streams
                     klines/depth/mark by itself; rotates multi-TF; snapshots real app-chart
                     pixels to `state/app_charts/` for the vision model.
- `interception.py`— `_forward()` routes EVERY classified capture (REST+WS) into the doors.
- `upstox_feed.py` — decodes Upstox Pro's protobuf WS (vendor/upstox_proto schema) → doors.
- Door-first reads in: `data_failsafe.py`, `fast_candles.py`, `binance_orderflow.py`,
  `crypto/freqtrade/brain_executor._ohlcv`. UI-only mode NEVER falls back to an API — a miss
  is an honest None. Do not "fix" that by re-adding an API path.

## Levers (don't hardcode these off)
UI_ONLY_DATA (+ governor `ui_only_mode.json`), UI_TAB_POOL / UI_TAB_POOL_N / UI_TAB_TFS,
UI_CRAWL, UI_MARKET_FRESH_<KIND>, HUMAN_HANDOFF (CAPTCHA handoff runs on parked tabs).

## Data flow (how a trade opens under the motto)
parked/crawled web tabs → app's own WS/XHR → interception classifies → ui_data/ui_market
(RAM) → fast_candles(LOOK) + indicator_fusion.fuse() + ocular(VERIFY) + vision_worker (reads
app-chart pixels) → direction equation + strategies + meta-labeler (CPU) → decision → funnel
executor → **API places the order only**. See memory `motto-web-data-superstore`.
