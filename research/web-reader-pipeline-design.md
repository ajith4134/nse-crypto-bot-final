# Web Reader — Confirmed 2-Phase Brain Pipeline Design
**Date:** 2026-07-05  
**Status:** Architecture CONFIRMED by owner — build in Fable 5 session  
**RAM:** 32 GB (browser sessions not a constraint)

---

## Owner's Confirmed Vision

> Brain opens trading app web pages. After user provides login details once, it logs in and maintains sessions permanently. Brain uses ALL the screens and filters in the app to pick trade candidates. After picking candidates, it opens each individual stock/crypto page and reads ALL details that page provides (candles, order book, option chain, etc.). Brain then decides: entry price, direction, stop loss, order depth. Opens the trade in the execution bot.

---

## Full Pipeline: 2 Phases

### Phase 1 — Universe Scan (runs every 30 seconds, all markets simultaneously)

**Goal:** Narrow 1000+ symbols down to 10–20 high-probability candidates.  
**Method:** Read the broker's OWN screener/filter pages via network interception — servers do the ranking, brain reads the result JSON.  
**CPU cost:** Near zero (just JSON parsing). No local computation.

```
BROWSER 1: TradingView (persistent, headless after first login)
  Navigate → screener page
  Intercept → screener result JSON
  Read: top NSE stocks by volume + momentum signal (RSI cross, MACD, BB squeeze)
         top crypto pairs by signal + volume

BROWSER 2: AngelOne (persistent, headless)
  Navigate → Markets → Stock Discovery → Gainers/Losers/OI Spurts
  Intercept → internal screener JSON
  Read: NSE top movers ranked by % change + OI change
         most active F&O symbols by volume

BROWSER 3: Binance (persistent, headless)
  Navigate → Futures → Markets Overview
  Intercept → internal ticker JSON
  Read: top crypto pairs by 24h% + funding rate extremes + OI spikes

DIRECT REST (no browser, parallel, instant):
  NSE API → OI spurts list, F&O ban list, block deals        [3 calls]
  Binance REST → bulk 24h ticker + open interest all symbols  [2 calls]
  Bybit REST → all perp tickers with funding + OI             [1 call]

OUTPUT: candidate_list = [
  { symbol, market, segment, why_selected, screener_rank, initial_signal }
  × 10–20 entries
]
```

---

### Phase 2 — Deep Dive (runs per candidate, sequential, 5–10s per symbol)

**Goal:** For each candidate from Phase 1, open their individual page and read EVERYTHING the broker shows for that specific symbol. Make the final trade decision.  
**Method:** Navigate browser to symbol-specific URL. Network interception captures all the internal API calls the page makes. Brain reads all JSON.

```
FOR EACH candidate symbol:

  IF market == NSE:
    Navigate AngelOne/Upstox browser → stock detail page for {symbol}
    Intercept ALL internal API responses for that page:
      ┌─ Candle data (5m, 15m, 1h timeframes)
      ├─ Order book depth (top 10 bid/ask levels + sizes)
      ├─ Option chain for this underlying (if F&O):
      │    → per-strike OI, change in OI, LTP, IV
      │    → PCR at ATM, max pain strike
      │    → which strikes have unusual OI buildup
      ├─ Recent trades (time & sales)
      ├─ Delivery volume % (how much is delivery vs intraday)
      ├─ News feed for this symbol
      ├─ Institutional activity (FII/DII for this stock if shown)
      └─ Chart indicators already rendered (RSI, MACD values shown on screen)

  IF market == crypto:
    Navigate Binance browser → futures chart for {symbol}
    Intercept ALL internal API responses:
      ┌─ Candle data (1m, 5m, 15m, 1h)
      ├─ Order book (depth: top 20 levels, bid/ask walls)
      ├─ Recent trades + trade direction (buy-initiated vs sell-initiated)
      ├─ Funding rate (current + history trend)
      ├─ Open interest (current + 24h change)
      ├─ Long/short ratio (top traders)
      ├─ Liquidation data (recent liquidations near current price)
      └─ Mark price vs index price spread

BRAIN SYNTHESIZES ALL DATA:
  ┌─ Direction:    LONG / SHORT / SKIP
  ├─ Entry price:  limit price based on OB walls + last candle close
  ├─ Stop loss:    below/above significant OB level + ATR-based buffer
  ├─ Target:       R:R ≥ 2.0, at next resistance/support level
  ├─ Order size:   based on OB depth + available liquidity at entry price
  └─ Confidence:   score 0–1 based on signal agreement across all data

  IF confidence ≥ threshold AND direction != SKIP:
    → send to execution bot
```

---

### Phase 3 — Execution (immediate, via existing APIs)

```
IF market == NSE:
  → POST /api/v1/placeorder (OpenAlgo)
  → symbol, direction, price, quantity (from lot size), stoploss, target

IF market == crypto:
  → POST /api/v1/forcebuy (Freqtrade)
  → pair, direction, price, stoploss rate

Brain records full decision context:
  → all Phase 2 data that led to this decision (stored in decision_memory)
  → used for learning: did the trade work? adjust weights
```

---

## Data Available in Each App (by Phase)

### AngelOne — Per-Symbol Page Data

| Data | Available on page | API equivalent |
|---|---|---|
| Candle chart (5m/15m/1h/1D) | ✅ | ✅ SmartAPI getCandleData |
| Order book depth (L2) | ✅ | ✅ SmartAPI snapQuote |
| Option chain for underlying | ✅ popup | ✅ SmartAPI optionGreek |
| IV rank / IV percentile | ✅ | ❌ App-only |
| OI heatmap visual | ✅ | Partial (raw OI only) |
| Delivery volume % | ✅ | ❌ App-only |
| News feed | ✅ | ❌ App-only |
| Institutional activity | ✅ | Partial |

### Binance — Per-Symbol Futures Page Data

| Data | Available on page | API equivalent |
|---|---|---|
| Candle chart (1m/5m/15m/1h) | ✅ | ✅ /fapi/v1/klines |
| Order book L2 (depth chart) | ✅ | ✅ /fapi/v1/depth |
| Trade direction (buy/sell flow) | ✅ | ✅ aggTrades |
| Funding rate current | ✅ | ✅ /fapi/v1/premiumIndex |
| Open interest | ✅ | ✅ /fapi/v1/openInterest |
| Long/short ratio | ✅ | ✅ /futures/data/globalLongShortAccountRatio |
| Liquidation heatmap | ✅ | ❌ App-only |
| Mark vs index spread | ✅ | ✅ premiumIndex |

---

## Browser Session Map

| Browser | App | Phase used | Headless after first login |
|---|---|---|---|
| Browser 1 | TradingView | Phase 1 (screener) | Yes |
| Browser 2 | AngelOne | Phase 1 (screener) + Phase 2 (per-symbol deep dive) | Yes |
| Browser 3 | Binance | Phase 1 (screener) + Phase 2 (per-symbol deep dive) | Yes |

RAM: ~1.5 GB total for 3 headless Chrome instances (trivial on 32 GB)

---

## Files to Build (Fable 5 Session)

```
trading/web_reader/
  __init__.py
  pipeline.py                    # orchestrates Phase1 → Phase2 → Phase3
  
  phase1_scanner/
    __init__.py
    tradingview_screener.py      # TradingView screener intercept → candidate list
    angelone_screener.py         # AngelOne top movers + OI spurts intercept
    binance_screener.py          # Binance futures overview intercept + REST bulk ticker
    nse_public.py                # NSE API direct (OI spurts, F&O ban, block deals)
    bybit_screener.py            # Bybit REST all tickers
    candidate_ranker.py          # merge + rank all candidates, deduplicate
  
  phase2_deepdive/
    __init__.py
    angelone_symbol.py           # navigate to symbol page → intercept all data
    binance_symbol.py            # navigate to futures symbol → intercept all data
    data_schema.py               # SymbolData dataclass: candles, OB, OI, news, etc.
  
  phase3_decision/
    __init__.py
    brain_decision.py            # brain synthesizes SymbolData → trade decision
    entry_calculator.py          # entry price from OB walls + candle
    sl_calculator.py             # stop loss from ATR + OB
    confidence_scorer.py         # signal agreement score across all data
  
  session_manager.py             # wraps broker_sense.sessions.SessionManager
  web_signal.py                  # Phase 1 output → feature_bus signals
  web_reader_loop.py             # daemon: Phase1 every 30s → Phase2 on candidates

dashboard/routes/web_reader_ext.py      # /api/trading/web-reader/* routes
dashboard/web/src/trading/WebReaderPanel.jsx  # live panel: phase status, candidates, decisions
```

---

## Key Design Constraints

1. **Read-only in browser** — `_FORBIDDEN` regex in sessions.py blocks any click on buy/sell/order/confirm buttons. Brain NEVER places orders through the browser — only through OpenAlgo/Freqtrade APIs.
2. **Credential vault** — login details stored encrypted via `trading/brain/credentials.py`. User enters once in Brain Chat, brain saves encrypted, reuses forever.
3. **OTP one-time** — brain asks in Brain Chat when session expires, waits for user, clears OTP immediately after use.
4. **Paper first** — all trades go to paper mode until owner explicitly enables live.
5. **Phase 2 is gated** — brain only does deep dive on symbols that pass Phase 1 threshold. Max 5 deep dives per cycle to avoid rate limits.
6. **Decision recorded** — every Phase 2 dataset + brain decision stored in decision_memory for learning.
