# Universe-scan architecture — how real projects scan 100s–1000s of symbols for trades

**Problem:** our brain loop iterates every whitelisted pair (293 crypto / ~2000 NSE) and re-runs
the FULL 153-strategy library backtest per pair, single-threaded, every cycle → ~30 s/pair → one
cycle never completes → no opens/exits, only futures ever runs. Round-robin+parallel+cache only
*spreads/speeds* the same expensive per-pair loop; it doesn't remove the wedge. Question from owner:
is there a better way, and how did other projects solve it?

## What the field actually does (research 2026-07-05)

Every mature framework uses the SAME three complementary techniques — none of them is "loop over
every pair and re-backtest N strategies each cycle":

| Technique | Who | What it does | Why it beats round-robin |
|---|---|---|---|
| **Coarse→Fine funnel** | QuantConnect **Lean** (Algorithm Framework: Universe Selection) | Cheap vectorized COARSE filter over the WHOLE universe (price/dollar-volume) narrows 8,000 → a few; expensive FINE/alpha model runs ONLY on survivors | Compute is always spent on the best candidates, not a blind rotation; whole universe screened every bar |
| **Vectorized signal compute** | **VectorBT** (NumPy+Numba+Rust), **Freqtrade** (vectorized `populate_indicators`), **Polars+Numba** | Indicators/signals computed as ARRAY ops across all pairs at once → "thousands of strategies in seconds"; Freqtrade docs mandate vectorized (called once/candle), warn looping per-row is "a lot slower" | Replaces 293×153 Python-loop (hours) with array ops (seconds) — the actual bottleneck removed, not hidden |
| **Event-driven + incremental** | **Nautilus Trader** (Rust core, circular-buffer indicators), crypto screeners (Altrady/TradingView: websocket) | Recompute only on NEW candle via websocket; indicators update incrementally (O(1)/bar), bounded memory | No blind 60 s full-rescan; work happens exactly when data changes |

### Reuse candidates (capability-ranked; some already vendored)
| Project | Repo | Role in our fix | Reuse | Fit |
|---|---|---|---|---|
| **Freqtrade** | vendor/freqtrade (have it) | Vectorized `populate_indicators` pattern + `VolumePairList`/`VolatilityFilter` ARE a coarse filter already | vendored | ★★★ our engine — copy its vectorized-signal discipline |
| **VectorBT** | polakowo/vectorbt (pip) | Vectorized multi-asset signal+backtest engine; scan all pairs × strategies as arrays | pip (heavy) | ★★★ reference for Stage-2 vectorized scan |
| **Polars + Numba** | pola-rs/polars, G-Research/polars-numba | Fast vectorized coarse screener over 100s–1000s symbols; Numba rolling kernels ~tens of ms | pip | ★★★ Stage-1 coarse screen |
| **ti_numba / fastfinance** | qrak/ti_numba, RomFR57/fastfinance | Numba-JIT technical indicators for the coarse screener | pip/vendor | ★★ indicator kernels |
| **QuantConnect Lean** | QuantConnect/Lean | Architectural PATTERN (coarse→fine), not the C# code | pattern only | ★★★ blueprint |
| **Nautilus Trader** | nautechsystems/nautilus_trader (pip) | Event-driven core + incremental indicators if we go streaming | pip (Rust) | ★★ optional streaming upgrade |

## Recommended architecture (better than round-robin+parallel+cache)

**Two-stage funnel + vectorized coarse screen + event-driven trigger** — covers the FULL universe
every bar, and only spends the expensive brain on the best few:

1. **Stage 1 — coarse screen (whole universe, cheap, vectorized).** On each 5 m candle close,
   compute a cheap score for ALL 293 crypto + all NSE symbols using vectorized Polars/NumPy +
   Numba indicators (momentum/vol/breakout/z-score). O(N), seconds, not hours. Rank → top-K
   candidates. ALWAYS include current open positions (so exits are managed every bar).
2. **Stage 2 — fine (expensive, only top-K + open positions).** Run the full 153-strategy brain
   ensemble + per-coin backtest + UQ gate ONLY on the ~20–40 Stage-1 survivors, parallelized across
   the 12 cores. This is where the deep compute goes — on the pairs that already look promising.
3. **Event-driven trigger.** Fire on 5 m candle close (websocket), not a blind 60 s poll; cache
   Stage-1 features per bar (incremental). Segments (futures/spot/options/prediction) each get a
   turn every bar because Stage-2 is now bounded.

**Why it's strictly better than round-robin:**
- Round-robin still runs the full per-pair backtest, just N pairs/cycle → *slow* full-universe
  coverage and still heavy. The funnel screens the WHOLE universe every bar (cheap) and only deep-
  computes the top few → full coverage + fast cycles simultaneously.
- It finds MORE trades (owner's goal): the coarse screen surfaces the best opportunities across all
  293/2000 symbols every bar, instead of whatever N pairs the rotation cursor happens to land on.
- It's how QuantConnect, VectorBT, Nautilus, Freqtrade, and every crypto screener actually do it.

Round-robin+parallel+cache is still useful as the *fallback within Stage-2* (rotate the top-K,
cache backtests per bar), but the funnel + vectorized coarse screen is the real fix.

## Owner's idea (2026-07-05): offload to the BROKER APPS (screener + data via computer-use)

Full idea across 4 messages: instead of pulling all data via API and computing signals over the
whole universe, have the **brain open the broker/trading apps in its built-in browser** (owner
provides OTP/login via Brain Chat), **use the broker's own screeners/filters to shortlist + rank**
which stocks/coins to trade, decide on that shortlist, place paper trades, and **also read candle
data + order book + all market data from the apps** — reserving APIs only for placing orders.
Goal: save compute + gain accuracy.

### Honest engineering assessment (two different problems — don't conflate)
- **Problem 1 — universe-scan compute (REAL).** Root cause = 153-strategy backtest × 293 pairs, NOT
  the data fetch. **Offloading the COARSE SCREEN to a battle-tested screener is exactly right** and
  is industry best practice (Danelfin/Trade-Ideas → 50-100 shortlist → deep tool; QuantConnect
  coarse→fine; UniverseScreener). ✅ Strong YES.
- **Problem 2 — getting candles/order-book via GUI-scraping (CAUTION).** The data *fetch* was never
  the bottleneck — API pulls are cheap, instant, and **exact**. Having a vision/LLM agent READ
  numeric price/order-book off a rendered app is **slower, less accurate (a misread digit = a wrong
  trade), MORE compute (running the agent), and brittle** (UI changes, sessions). That works
  *against* the stated goals (accuracy + compute). Order books update many times/sec — a GUI agent
  can't keep up. ⚠️ For raw market data, APIs win.
  - **Legit exception:** NSE data that's IP-blocked / broker-only (e.g. option chain — nselib is
    IP-blocked per memory). There, reading from the logged-in broker app (Kite) is a reasonable
    FALLBACK for data we genuinely can't get via API. Crypto exchange APIs are open → no need.

### Best implementation of the owner's instinct (screener-offload, done right)
- **Stage 1 coarse = external screener, API-first:**
  - **NSE + crypto:** `tradingview-screener` / `tvscreener` (Python, TradingView's *official* scanner
    API — stocks, crypto, forex, futures, options; 3000-13000 fields incl. technicals; SQL-like
    filters; multi-timeframe; NO login/scrape). One library covers BOTH markets. ← the big find.
  - **NSE also:** Chartink scanner → webhook → **OpenAlgo** (we already run OpenAlgo; integration is
    documented) + PKScreener (OSS NSE breakout screener).
  - **GUI fallback (owner's exact vision):** computer-use agent (we have vendored `browser-use` +
    `trading/brain/gui/agent.py` + `trading/brain/credentials.py` vault + Brain Chat for OTP) drives
    the broker app for screens/data that have NO API. Keep this as the FALLBACK, not the primary,
    because of the documented browser-agent demo→production reliability gap (arxiv 2511.19477,
    2512.02261) — and per that research, **risk/size/stop decisions stay in code, never the LLM.**
- **Stage 2 fine = our brain** deep-evaluates the shortlist (153 strategies + UQ), now cheap (~20-40
  symbols). **Execution = APIs** (OpenAlgo/Freqtrade), as the owner said.

### Prior art that IS this idea (reuse pool)
| Project | What | Reuse |
|---|---|---|
| tradingview-screener / tvscreener | Official TV scanner API, NSE+crypto, technicals+fundamentals | pip — Stage-1 coarse (both markets) |
| Chartink → OpenAlgo webhook | NSE scanner alerts → our OpenAlgo | have OpenAlgo — wire webhook |
| PKScreener | OSS NSE breakout/pattern screener | pip/vendor |
| browser-use (+ our gui/agent.py) | computer-use to drive broker app (OTP via chat) | vendored — GUI fallback |
| TradingAgents / AlpacaTradingAgent | multi-agent LLM trading (API-exec, risk-in-code) | reference |

**Verdict:** the owner's screener-offload instinct is correct and matches best practice — implement
it as an API-first external-screener coarse stage (tradingview-screener covers NSE+crypto) with the
computer-use broker-app path as the fallback for API-less/blocked screens+data. Get raw
candles/order-book via API (exact, fast) — use GUI-reading only where an API genuinely doesn't exist
(some NSE data). This beats both "compute the coarse score ourselves" and "GUI-scrape everything."

## Owner's expanded vision (2026-07-05 v2): GUI-first perception — candle-image ML + screen-monitor

Owner refined the vision to be explicitly GUI/vision-first (overrides the earlier "API-for-raw-data"
default — this is what the owner wants built): the brain uses ITS OWN web browser to open ALL broker
apps' websites; it types the login details + OTP that it ASKS for in the Brain Chat box (owner types
there); uses each broker's BUILT-IN filter/screener features to pick the best trades; then opens the
picked stocks' candles, TAKES A SCREENSHOT, and runs ML/DL on that candle-pattern IMAGE at
1m/5m/15m/30m/1hr (24) to decide direction (long/short, call/put), entry price, etc.; DELETES all
screenshots after opening trades; extracts order-book bid/ask via a NON-INVASIVE monitor / screen-
mirror method that reads the page WITHOUT touching the source (like Claude's "monitor mode"); places
PAPER trades; uses APIs ONLY for execution (paper + real). Owner decides the execution brokers; the
brain may also use OTHER broker apps just for screening/data (not real-money execution).

### Prior art for the new elements (all found online)
**Candlestick-chart IMAGE → direction via ML/DL (CNN/vision):** treating the chart as an image and
classifying bullish/bearish is well-established OSS + research:
- pecu/FinancialVision — CNN spatial features from financial charts: https://github.com/pecu/FinancialVision
- amit-agni/candlesticks-deeplearning — DL image classifier on candlestick charts: https://github.com/amit-agni/candlesticks-deeplearning
- lamfo-unb/img_candles — CNN classifies candlestick chart images: https://github.com/lamfo-unb/img_candles
- hardyqr/CNN-for-Stock-Market-Prediction-PyTorch — CNN reads candlestick graph → trend: https://github.com/hardyqr/CNN-for-Stock-Market-Prediction-PyTorch
- CharlesLoo/stock-pattern-recorginition — 2D candlestick image input → trend: https://github.com/CharlesLoo/stock-pattern-recorginition
- CNN-LSTM candlestick recognition (paper): https://pmc.ncbi.nlm.nih.gov/articles/PMC11935771/
- (also: a vision-language model / VLM can read direction + order-book numbers directly off the screenshot.)

**Non-invasive "monitor / screen-mirror" data extraction (read page WITHOUT touching the source):**
screenshot + OCR/VLM works on the RENDERED pixels, independent of HTML/DOM — exactly the owner's
"monitor mode / screen mirror" ask; reads canvas order books that have no DOM:
- Ui.Vision RPA — OCR screen-scraping (reads text/numbers off the screen): https://ui.vision/rpa/x/desktop-automation/screen-scraping
- Copyfish — browser OCR, works on any site incl. canvas/video: https://ocr.space/copyfish/docs
- Open-source OCR models compared: https://modal.com/blog/8-top-open-source-ocr-models-compared
- OCR.space API: https://ocr.space/ocrapi
- (We already vendor OmniParser (vendor/omniparser) for screenshot→structured UI, and paddleocr is the project's OCR path — reuse these for the read-only screen monitor.)

Builder note (does NOT drop the owner's spec — just validate it): confirm the vision/OCR read of
prices/bid-ask is accurate enough before it drives a trade (a misread digit = wrong trade), keep
risk/size/stop decisions in CODE not the LLM, and manage broker sessions/OTP securely via the vault.

Sources (owner-idea research):
- Chartink→OpenAlgo: https://docs.openalgo.in/trading-platform/chartink · scrapers: https://github.com/sgprasad66/ChartInkScreenerScraper , https://github.com/pkjmesra/PKScreener
- TradingView screener API (python): https://pypi.org/project/tradingview-screener/ , https://github.com/shner-elmo/TradingView-Screener , https://github.com/deepentropy/tvscreener
- Universe-screener pattern: https://github.com/u-glow/UniverseScreener
- Browser-agent reliability (risk-in-code, demo→prod gap): https://arxiv.org/pdf/2511.19477 , https://arxiv.org/pdf/2512.02261 , https://arxiv.org/pdf/2510.11695

Sources:
- QuantConnect Lean universe selection (coarse→fine): https://www.quantconnect.com/docs/v1/algorithm-framework/universe-selection , https://www.quantconnect.com/forum/discussion/4473/performance-issue-with-large-universe-screen/
- VectorBT (vectorized multi-asset): https://github.com/polakowo/vectorbt , https://vectorbt.dev/
- Freqtrade vectorized strategy guidance: https://www.freqtrade.io/en/stable/strategy-customization/
- Nautilus Trader (event-driven, incremental indicators): https://github.com/nautechsystems/nautilus_trader , https://nautilustrader.io/
- Polars+Numba fast indicators: https://github.com/G-Research/polars-numba , https://github.com/qrak/ti_numba , https://github.com/RomFR57/fastfinance
- Crypto screeners (websocket scan at scale): https://www.altrady.com/features/crypto-technical-analysis-screener , https://www.tradingview.com/crypto-screener/
