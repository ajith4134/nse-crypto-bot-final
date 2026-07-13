# RAM symbol-data coverage audit (2026-07-13)

Owner ask: "check symbols' data — order depth, volume, and other important datatypes beyond what
already exists — make sure any I missed are also in RAM." Motto: data = web/RAM, APIs = execution only.

## What IS in RAM today (trading/broker_sense/binance_stream.py — all-market WS mirror)
ONE futures WS (`wss://fstream.binance.com/market/stream`) carries the whole universe, PUSH:
| datatype | stream | scope | accessor |
|----------|--------|-------|----------|
| mark price + **funding rate** + next-funding-time | `!markPrice@arr@1s` | ALL perps | `mark()` / `funding()` |
| 24h last / %change / high / low / **quote_volume** / **trade-count** | `!ticker@arr` | ALL symbols | `ticker()` / `movers()` / `futures_rows()` |
| **liquidations** (side-normalized) | `!forceOrder@arr` | ALL perps (event) | `recent_liquidations()` |
| multi-TF **OHLC candles** (1m/5m/15m, mark-price) | derived from markPrice | ALL perps | `candles()` / `candle_timeframes()` / **`ohlcv()`** (NEW, ccxt-shape) |
| mark-price **history** (for price_at) | derived | ALL perps | `price_at()` |
| **20-level order-book depth** (bids/asks) | `<sym>@depth20@500ms` (2nd conn) | **top-N watched only** (depth firehose) | `book()` |

Browser-captured per-symbol into `ui_market` (visited symbols only), read by `app_signals`:
taker flow, book imbalance, long/short ratio, open interest, option PCR, funding.

## Answering the audit directly
- **Volume** → ✅ 24h `quote_volume` + trade-count in RAM (`ticker()`). ❌ per-BAR candle volume
  (mark-price stream has none; only `@kline`/`@aggTrade` carry it, and there is NO all-market push
  for them — per-symbol firehose only).
- **Order depth** → ✅ 20-level in RAM (`book()`), but **top-N watched symbols only** (depth is a
  firehose; can't stream 900 symbols' depth). All-market depth ❌.
- Everything else important at the symbol level (mark/funding/liq/24h stats/candles/history) → ✅.

## The "missing" datatypes ARE collected into RAM for the symbols we trade
Correction after tracing the pipeline: `trading/broker_sense/micro_collect.py` ALREADY fetches
open-interest, 20-level depth, taker ratio, global long/short, and aggTrades from Binance's OWN
data doors THROUGH THE BROWSER SESSION (ban-safe, app-session — not a raw API), storing them into
`ui_market` (RAM) via the same parsers as passive interception. It runs in the funnel each cycle
for `open_syms + direction_collect_wanted.json` symbols. The wants are written by
`app_signals.collect → _ensure_streaming`, which is called in the executor AND (new this session)
in `indicator_fusion` for every deep-verified candidate. So:
- taker / open_interest / long_short / aggTrades / depth → ✅ in RAM for open + wanted/shortlisted
  symbols (exactly the ones we trade), via micro_collect. NOT all 900 symbols — impractical
  (browser can't fetch 900 symbols' microstructure per cycle) and unnecessary (we trade the shortlist).

Genuinely still absent (no source): per-bar candle **volume** all-market (mark-price stream has none;
`@kline`/`@aggTrade` are per-symbol firehoses). 24h volume covers the symbol-level volume need.

Net: every important datatype the brain/equations use IS in RAM for the traded set. Task #7 ("ban-safe
collector") turned out to be ALREADY WIRED (micro_collect + wanted-file); this session broadened its
coverage by registering a want for every fused candidate.

## Done this session
- `binance_stream.ohlcv(sym, tf, limit)` — RAM candles in ccxt shape; consumed by
  `indicator_fusion._fetch` + `fast_candles._ohlcv_fast` RAM-FIRST (before any ccxt API), allowed
  under UI_ONLY_DATA (web-sourced). MIRROR_CANDLES=0 kills. Completes the "multi-TF candle chart into
  RAM" — the mirror aggregated them; nothing consumed them until now. See [[inram-candles-and-coverage-lane]].

## Next
- Task #6: capture ALL `app_signals` filter kinds + `mirror.ticker()` volume/depth into the entry
  decision_snapshot and surface them as `postmortem.trade_features` (enrich, RAM-sourced).
- Task #7: ban-safe all-market collector for taker/longshort/oi/pcr (breadth) into RAM.
