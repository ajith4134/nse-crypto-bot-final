# Web-Data Motto Migration — research + build plan (2026-07-12)

Goal: implement THE MOTTO — replace API market-data paths with navigation of the logged-in
Binance/Upstox web apps + local vision; CPU reserved for brain intelligence; APIs execution-only.

## Audit summary (full details from Explore run, this date)

Stack is mature (sessions/live_browser/interception/ui_data/human_ui/nav_brain/ocular/vision_worker/
app_school/screen_mirror all built, both brokers logged in). The gaps:

- **A** `interception.py:345` forwards ONLY `candles` to `ui_data.feed_capture` — orderbook, funding,
  OI, long_short, taker_volume, mark_price, option_chain, ticker are classified+cached but never
  reach fusion/data_failsafe.
- **B** `binance_stream.py` mirror = PUBLIC fstream/fapi WS, not the account web app. True motto path
  = RAM mirror fed by interception captures of the app's own WS/XHR.
- **C** `brain_executor._ohlcv` (ccxt), Freqtrade VolumePairList + candle_updater — ungated API.
- **D** `fast_candles.py:96-110` tries ccxt-direct BEFORE the UI-only gate.
- **E** Upstox/NSE: no web candle path; Upstox web WS is protobuf, undecoded.
- **F** Governor (`ui_data.maybe_auto_flip`) OFF because fresh coverage 0.0 — nothing drives the app
  to keep shortlist symbols streaming. Need a coverage crawler.
- **G** vision_worker/chart_vision render charts from API candles, not app pixels.

## OSS candidates (Phase-1, cheap signals)

| Project | Repo | Key features | Activity | Fit | Verdict |
|---|---|---|---|---|---|
| upstox-python (official SDK) | github.com/upstox/upstox-python | Official MarketDataFeedV3.proto + generated `MarketDataFeed_pb2.py`; decodes Upstox WS protobuf → JSON (ltpc/ohlc/depth) | Official, active | HIGH | **ADOPT proto+pb2 only** — decode captured web-app WS frames; do NOT use its websocket client (that would be an API feed, violating motto) |
| Realtime-stock-price-streaming | github.com/naveennk045/Realtime-stock-price-streaming | Example wiring of V3 proto | small | low | reference only |
| binance-spot-api-docs | github.com/binance/binance-spot-api-docs | Canonical JSON shapes for kline/depth/ticker WS frames (web app uses same shapes) | official | HIGH | reference for classifier edge cases |
| unicorn-binance-websocket-api | github.com/oliver-zehentleitner/unicorn-binance-websocket-api | Full public WS SDK | active | n/a | REJECT — public API feed, violates motto |

Recommendation: no new framework needed. Reuse our interception/ui_data/nav stack; vendor ONLY the
official Upstox proto (+ `protobuf` runtime already available via deps) to decode captured frames.

## Build plan (workstreams)

- **W1 ui_market superstore** — extend the UI-data door to ALL kinds: forward every classified kind
  from interception → `ui_data` (candles + orderbook + funding + OI + long_short + taker + mark +
  ticker + option_chain + movers); RAM index + cross-process snapshot; freshness gates per kind.
- **W2 gate the API tilts** — `binance_orderflow`, fuse() tilt fetchers, `fast_candles` (ccxt-first
  bug), `brain_executor._ohlcv`: prefer web-captured data via the door; UI-only mode = web or honest
  None, never silent API.
- **W3 web mirror** — `web_mirror.py`: same read API as `binance_stream` (movers/funding/book/…)
  but fed from interception captures of the logged-in app; governor picks web-mirror when fresh,
  public mirror only as failsafe (staged: motto end-state removes it).
- **W4 coverage crawler** — nav routine that drives the Binance app (watchlist/screener/chart tabs,
  multi-TF) so the app's own streams keep the funnel shortlist fresh ≥80% → governor flips UI-only ON
  and it STAYS on. Uses app_school routes + fast_nav + sessions; RAM-cheap page pool.
- **W5 Upstox decode** — vendor MarketDataFeedV3.proto; decode captured pro.upstox.com WS protobuf
  frames → candles/depth into the door (NSE path).
- **W6 app-pixel vision** — vision_worker prefers real app chart screenshots (multi-TF captured by
  crawler) over API-rendered charts; qwen2.5-vl reads them; render-from-door-candles as fallback.
- **W7 extra-surface sweep** — wire additional classified kinds (liquidations, long-short ratios,
  mark/index premium, option chain) as fusion tilts + xray fields.
- **W8 learning feeds** — captured data → evidence/xray/decision episodes; crawler outcomes →
  fast_nav_stats/ui_skills so navigation self-improves.

Execution order: W1 → W2 → W4 → W3 → W6 → W5 → W7 → W8 (W1/W2 unlock the governor; W4 makes it stick).
