# Web Reader / Broker Automation — Deep OSS Research
**Date:** 2026-07-05  
**Goal:** Build a trading brain that uses broker web apps as PRIMARY data source (APIs fallback only).  
**Targets:** AngelOne, Upstox, Groww (NSE) + Binance, Bybit, Coinbase (crypto)  
**Scope:** 4 research angles: (1) Indian broker web automation, (2) Crypto WebSocket data, (3) Visual/VLM screen reading, (4) Multi-broker unified APIs.

---

## ANGLE 1 — Indian Broker Web Automation

### Candidate Table

| Project | Repo | Key Features | Activity | Stars | Fit Score | Verdict |
|---|---|---|---|---|---|---|
| **indian-stock-mcp-agent** | https://github.com/Sparker0i/indian-stock-mcp-agent | Playwright + network interception, AES-256-GCM session encrypt, 6h TTL, persistent browser profiles, supports Groww/Zerodha/INDmoney | TypeScript, 13 commits, active | 11 | 8/10 | ✅ BORROW PATTERN — network interception approach is best-in-class; rewrite in Python |
| **angel-one/smartapi-python** | https://github.com/angel-one/smartapi-python | Official AngelOne SDK, TOTP auth, WebSocket2.0 market feed, order management, OHLCV, option Greeks, top gainers/losers API | Python 100%, 198 commits | 172 | 9/10 | ✅ USE — official SDK for AngelOne REST + WebSocket; no browser needed for data |
| **upstox-python** | https://github.com/upstox | Official Upstox SDK, OAuth2, option chain API (`get_put_call_option_chain`), REST + WebSocket | Official, active | ~500 | 8/10 | ✅ USE — official SDK as fallback; web session for live screener data |
| **upstox-totp** | https://github.com/batpool/upstox-totp | TOTP automation for Upstox API auth, pyOTP, curl-cffi, token caching (JSON/Redis/SQLite), Python 3.12+ | 11 stars, v1.0.8 Sep 2025 | 11 | 7/10 | ✅ USE — handles TOTP for unattended Upstox login |
| **nsepython** | https://github.com/aeron7/nsepython | Unofficial NSE API wrapper: option chain, OHLCV, index data, futures OI, FII/DII, Greeks (Black-Scholes), no login | Python, v2.97 May 2025 | 357 | 10/10 | ✅ USE — zero-login NSE data; option chain OI, greeks, FII/DII |
| **Python-NSE-Option-Chain-Analyzer** | https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer | Real-time NSE option chain (OI, ΔOI, strike boundaries), 1-min refresh, no login, NSE public API | Python 3.6+, v5.8 May 2026 | 632 | 9/10 | ✅ USE — production-ready NSE OI scraper, no auth needed |
| **markov404/AngelOneOptionChainSmartApi** | https://github.com/markov404/AngelOneOptionChainSmartApi | AngelOne SmartAPI → NFO option chain (CE/PE via WebSocket2.0), every 3 min, Python | Last commit Feb 2023 | 17 | 5/10 | ⚠️ BORROW APPROACH — old but shows WebSocket2.0 snap-quote pattern for OI |
| **excel-option-chain** | https://github.com/Neeraj-prajapat/excel-option-chain | AngelOne API → NIFTY/BANKNIFTY option chain in Excel | Feb 2025 | 6 | 3/10 | ⚠️ REFERENCE ONLY |
| **nse-oi-analysis** | https://github.com/HawkEyeCoding/nse-oi-analysis | NSE scraper → NIFTY/BANKNIFTY OI sum near ATM, intraday trend | Inactive | ~5 | 4/10 | ⚠️ REFERENCE — OI signal formula useful |
| **manddar/Open-Interest-Data-Extractor** | https://github.com/manddar/Open-Interest-Data-Extractor | NSE website OI extractor, Python | May 2026 | 14 | 5/10 | ⚠️ REFERENCE |
| **Akash9078/option-chain-dashboard** | https://github.com/Akash9078/option-chain-dashboard | NSE unofficial API + Streamlit UI, Apr 2026 | Apr 2026 | 0 | 4/10 | ⚠️ REFERENCE |

### Key Technical Patterns Found

**Network Interception (best approach for AngelOne/Upstox web sessions):**
- `indian-stock-mcp-agent` uses `page.on("response", handler)` to capture XHR/fetch responses from broker's own internal REST APIs — zero DOM fragility
- Session stored as persistent browser profile at `./browser-data/{broker}/` with AES-256-GCM encryption
- 6h TTL with auto-relogin on expiry
- OTP: manual entry (user pastes into CLI), stored for session only
- Pattern: TypeScript but rewriting to Python Playwright is straightforward

**AngelOne SmartAPI (official, no browser needed for market data):**
- Auth: `smartConnect.generateSession(clientCode, password, totp)` — returns JWT + feedToken
- WebSocket2.0 snap-quote: subscribe to option chain tokens → streaming CE/PE OI + LTP + greeks
- REST: `getCandle()`, top gainers/losers, option Greeks endpoint
- TOTP: `pyotp.TOTP(totp_secret).now()` — supports unattended auth

**Upstox TOTP (unattended Upstox auth):**
- `pip install upstox-totp`; uses `UPSTOX_TOTP_SECRET` env var → `pyOTP`
- Returns access token for Upstox REST/WebSocket APIs
- Token cached in JSON/Redis/SQLite

**NSE Public APIs (zero login — best for OI data):**
- `https://www.nseindia.com/api/option-chain-v3?type=Indices&symbol=NIFTY` → full OI chain
- `nsepython` wraps all NSE public endpoints: `nse_optionchain_scrapper()`, futures OI, FII/DII
- Works without cookies or login; just set User-Agent header
- `Python-NSE-Option-Chain-Analyzer` shows session headers needed to bypass NSE's basic anti-scrape

---

## ANGLE 2 — Crypto WebSocket Real-Time Data

### Candidate Table

| Project | Repo | Exchanges | Channels | Auth | Activity | Stars | Fit Score | Verdict |
|---|---|---|---|---|---|---|---|---|
| **cryptofeed** | https://github.com/bmoscon/cryptofeed | 40+ (Binance/Binance-Futures/Bybit/Coinbase/OKX/Deribit/KuCoin) | L1/L2/L3 OB, trades, ticker, funding, OI, liquidations, OHLCV | Yes (private: balance/orders) | Python, v2.4.1 Feb 2025 | 2.9k | 10/10 | ✅ BEST — most complete, normalized across all exchanges |
| **ccxt / ccxt.pro** | https://github.com/ccxt/ccxt + https://docs.ccxt.com/docs/pro-manual | 100+ (Binance/Bybit/Coinbase Advanced) | watchOrderBook, watchTicker, watchTrades, watchOHLCV, watchLiquidations | Yes | Python async, 34k stars, v4+ | 34k | 9/10 | ✅ USE — best unified REST fallback + WS for orderbook/ticker; funding rate via REST |
| **pybit** | https://github.com/bybit-exchange/pybit | Bybit only | OB, ticker, funding, OI, liquidations, kline, trades | Yes (private) | Python 3.10+, v5.16.0 Apr 2026 | 661 | 8/10 | ✅ USE — official Bybit SDK; most complete Bybit coverage |
| **binance-connector-python** | https://github.com/binance/binance-connector-python | Binance only (spot + futures + options) | All Binance streams: depth, ticker, funding, OI, liquidations, mark price, kline | Yes (private) | Python 3.10+, 2.9k stars, active | 2.9k | 8/10 | ✅ USE — official Binance; all futures streams available |
| **coinbase-advanced-py** | https://github.com/coinbase/coinbase-advanced-py | Coinbase only | WebSocket: ticker, L2 OB, market trades, user, heartbeats, futures_balance_summary | Ed25519/ECDSA JWT | Python, v1.8.4 Jun 2026, 350 stars | 350 | 8/10 | ✅ USE — official Coinbase Advanced SDK; India view-only confirmed |
| **BybitMarketData** | https://github.com/sferez/BybitMarketData | Bybit futures only | WS: ticker (incl. funding rate + OI), real-time JSON capture | Public only | ML-focused, Python | ~50 | 5/10 | ⚠️ REFERENCE — shows WS schema for funding+OI from Bybit |
| **fundingrate** | https://github.com/jironghuang/fundingrate | Multi-exchange | Funding rate collector | Public REST | Python, small | ~30 | 4/10 | ⚠️ REFERENCE — lightweight funding rate poller |
| **cryptofeed-yas** | https://pypi.org/project/cryptofeed-yas/ | cryptofeed fork | Same as cryptofeed + extras | Yes | PyPI fork | small | 4/10 | ⚠️ SKIP — use main cryptofeed |

### Key Technical Details

**cryptofeed (RECOMMENDED PRIMARY for crypto data):**
```python
pip install cryptofeed[all]
```
- Exchanges: Binance, BinanceFutures, BinanceDelivery, Bybit, Coinbase, OKX, Deribit, Kraken, KuCoin, Gate.io, 40+ more
- Channels: `TRADES`, `TICKER`, `L2_BOOK`, `L3_BOOK`, `FUNDING`, `OPEN_INTEREST`, `LIQUIDATIONS`, `INDEX`, `CANDLES`
- Backends: Redis, Kafka, PostgreSQL, MongoDB, InfluxDB, ZeroMQ, RabbitMQ, GCP Pub/Sub
- Private channels (need API keys): order status, balances, fills
- Python 3.8+, asyncio-based
- Cython hot paths for performance

**ccxt.pro (RECOMMENDED for unified REST + WS):**
```python
pip install ccxt  # includes Pro WS
```
- `watchOrderBook(symbol)`, `watchTicker(symbol)`, `watchTrades(symbol)`, `watchOHLCV(symbol)`
- Binance (certified): all futures streams; Bybit (certified): OB depths [1,50,200,1000]; Coinbase Advanced: ticker + L2
- `watchFundingRate` NOT in unified interface — use exchange REST: `fetchFundingRate(symbol)`
- `watchOpenInterest` NOT unified — use exchange REST: `fetchOpenInterest(symbol)`
- Pure asyncio Python; `async def main(): await exchange.watch_order_book('BTC/USDT')`

**pybit (Bybit official):**
- `pip install pybit`; Python 3.10+
- Private: needs API key+secret
- WS: orderbook, ticker, trades, kline, liquidations, position, execution updates
- Funding rate + open interest: REST `get_tickers()` returns both in one call

**Binance connector:**
- `pip install binance-connector` (new) — replaces deprecated `binance-futures-connector`
- UMFutures WS: `depth` (L2), `bookTicker`, `markPrice` (includes funding), `forceOrder` (liquidations), `kline`
- All streams free, no auth needed for public data

**Coinbase Advanced (view-only from India):**
- `pip install coinbase-advanced-py`
- WS channels: `ticker`, `level2` (L2 orderbook), `market_trades`, `futures_balance_summary`
- `futures_balance_summary` needs auth; `ticker` + `level2` are public
- India: CDX derivatives read-only; REST can still fetch futures contract list + OI

---

## ANGLE 3 — Visual / VLM Screen Reading

### Candidate Table

| Project | Repo | What It Does | Hardware | Integration | Stars | Fit Score | Verdict |
|---|---|---|---|---|---|---|---|
| **OmniParser V2** | https://github.com/microsoft/OmniParser | Screenshot → structured UI elements + bounding boxes + interactability labels; works with any LLM | GPU recommended (60% faster than v1); no explicit CPU floor | Python, Gradio API, HuggingFace weights | 25k | 9/10 | ✅ USE — best for parsing broker UI screenshots into structured elements |
| **UI-TARS-1.5** | https://github.com/bytedance/UI-TARS | Screenshot → click coordinates + action plan + reasoning; pixel-only input; 7B/72B models | GPU for local; API endpoint available | `pip install ui-tars`; `action_parser` module | 11.1k | 8/10 | ✅ USE — best for autonomous agent actions (clicking, typing); use 7B locally |
| **UI-TARS-2** | https://arxiv.org/html/2509.02544v1 | Multi-turn RL, hierarchical memory (working + episodic), System-2 reasoning | GPU required; cloud API | Research release Sep 2025 | N/A | 7/10 | ⚠️ FUTURE — not yet widely deployed; use UI-TARS-1.5 now |
| **browser-use** | vendor/browser_use_src/ (already vendored) | LLM reads page state (DOM+screenshot hybrid) → decides clicks/types; Playwright under hood | CPU ok; LLM API needed | Already in project | ~10k | 10/10 | ✅ USE — already vendored; best for autonomous broker navigation tasks |
| **Mobile-Agent-v3.5** | https://arxiv.org/pdf/2602.16855 | Multi-platform GUI agent (mobile + desktop) with tool use and reflection | GPU for local VLM | Research | N/A | 5/10 | ⚠️ REFERENCE — less mature than UI-TARS |

### Key Technical Details

**OmniParser V2 (screen → structured data):**
- Input: raw screenshot (any resolution)
- Output: list of UI elements with bounding boxes + interactability score + caption
- Two models: icon detector (YOLO-based) + icon captioner (Florence/PaliGemma)
- `pip install omniparser` or clone + Gradio server
- Available on HuggingFace: `microsoft/OmniParser-v2.0`
- 39.5% accuracy on ScreenSpotPro (vs 0.8% for raw GPT-4o)
- Use case: feed broker screenshot → get structured list of data tables, prices, buttons

**UI-TARS-1.5 (screenshot → action):**
- Input: screenshot image pixels (any resolution)
- Output: `"Thought: I see the option chain table...\nAction: click(x=342, y=518)"`
- `from ui_tars.action_parser import parse_action_to_structure_output`
- 7B model runs on ~16GB VRAM; quantized 4-bit for 8GB
- SOTA 61.6% on ScreenSpotPro (vs Claude 27.7%)
- Use case: autonomous navigation of broker UIs; no DOM needed

**browser-use (already vendored — primary automation layer):**
- LLM decides actions at each step based on page snapshot (DOM tree + screenshot)
- Handles login flows, OTP entry wait, navigation between pages
- Playwright-backed: persistent contexts, storage_state, network intercept all work

---

## ANGLE 4 — Multi-Broker Unified APIs / Screeners

### Candidate Table

| Project | Repo | Brokers / Exchanges | Data Available | Stars | Fit Score | Verdict |
|---|---|---|---|---|---|---|
| **OpenAlgo** (already running) | https://github.com/marketcalls/openalgo | AngelOne, Upstox, Zerodha, Fyers + 30 more | Option chain, IV smile, max pain, GEX, vol surface, L2 book; unified REST | Active | 10/10 | ✅ PRIMARY FALLBACK — already running; full NSE broker coverage |
| **nsepython** | https://github.com/aeron7/nsepython | NSE public | Option chain, OHLCV, FII/DII, Greeks, index, futures OI | 357, May 2025 | 9/10 | ✅ USE for NSE public data without any broker login |
| **ccxt** | https://github.com/ccxt/ccxt | 100+ crypto | REST: OHLCV, OB, funding, OI, tickers | 34k, active | 9/10 | ✅ USE as REST fallback for all crypto exchanges |
| **finrl-meta** | https://github.com/AI4Finance-Foundation/FinRL-Meta | Multi-market | Market environments for RL trading agents | 1.1k | 4/10 | ⚠️ REFERENCE — RL environment wrapper, not a data source |
| **algo_trading_strategies_india** | https://github.com/buzzsubash/algo_trading_strategies_india | Zerodha, multi-broker planned | NSE/BSE algo trading, option selling NIFTY/BANKNIFTY | Active | 4/10 | ⚠️ REFERENCE — strategy code, not data layer |
| **crawlee-python** | https://github.com/apify/crawlee-python | Any web | Playwright crawler with session persistence, proxy rotation, anti-detection | 5k+, active | 7/10 | ⚠️ CONSIDER — general crawler framework; useful if broker anti-bot is aggressive |

---

## Synthesis: Recommended Architecture for Build Session

### Layer 1 — Session Management (Playwright)
**Use:** Playwright native `storage_state` + persistent context (already in `trading/broker_sense/sessions.py`)  
**Pattern borrowed from:** `indian-stock-mcp-agent` — AES-256 encrypted profiles, 6h TTL, network interception hooks  
**OTP:** vault polling pattern already in `sessions.py` — keep as-is

### Layer 2 — Indian Broker Data Extraction

**AngelOne:**
- PRIMARY: `angel-one/smartapi-python` (`pip install smartapi-python`) — TOTP auth, WebSocket2.0 snap-quote for option chain OI + LTP, REST for OHLCV + top movers
- SECONDARY: Playwright session + network interception (for screener pages the REST doesn't cover)
- API key + TOTP secret → unattended login

**Upstox:**
- PRIMARY: `upstox-python` official SDK + `upstox-totp` for TOTP automation (`pip install upstox-totp`)
- Option chain: `OptionsApi.get_put_call_option_chain(instrument_key, expiry_date, strike_count)`
- SECONDARY: Playwright session for screener pages

**NSE (No-login public data — best source for raw OI):**
- `nsepython` (`pip install nsepython`) → `nse_optionchain_scrapper("NIFTY")` → full OI chain, FII/DII, futures OI
- `Python-NSE-Option-Chain-Analyzer` approach: hit `nseindia.com/api/option-chain-v3` with session headers
- No login, no API key, no broker account needed

**Groww:**
- Playwright session + network interception (same `indian-stock-mcp-agent` pattern adapted to Groww)
- No official Python SDK with option chain; web interception is the only route

### Layer 3 — Crypto WebSocket Data

**All exchanges (normalized):**
- `cryptofeed` (`pip install cryptofeed[all]`) — PRIMARY for L2 OB + ticker + funding + OI + liquidations from Binance/Bybit/Coinbase simultaneously
- Asyncio-based; run in dedicated thread with `asyncio.run()`

**Per-exchange official SDKs (fallback or private channels):**
- Binance: `binance-connector-python` (`pip install binance-connector`) — all futures streams
- Bybit: `pybit` (`pip install pybit`) — official; `get_tickers()` returns funding + OI together
- Coinbase: `coinbase-advanced-py` (`pip install coinbase-advanced-py`) — L2 channel + REST for futures

**ccxt.pro as unified REST:**
- `ccxt` already likely installed; `fetchFundingRate()`, `fetchOpenInterest()`, `fetchOHLCV()` across all exchanges

### Layer 4 — Visual Screen Reading (for data not in APIs)

**OmniParser V2:** Parse broker screenshot → structured table rows  
- Use when: option chain UI has data not in the REST API; AngelOne screener shows unique ranked data
- Clone + local Gradio server or use HuggingFace API  
- `pip install omniparser` (or clone `microsoft/OmniParser`)

**browser-use (already vendored):** Autonomous navigation for multi-step flows  
- Already at `vendor/browser_use_src/` — USE THIS for initial broker login + navigation
- Best for: logging in, clicking through menus, triggering the API calls the interceptor captures

**UI-TARS-1.5:** Pixel → coordinates for cases where DOM is obfuscated  
- `pip install ui-tars`; 7B model on GPU or quantized locally
- Use only if browser-use + network interception fails on a specific broker

---

## Packages to Install (ordered by priority)

```bash
# NSE data (no login needed)
pip install nsepython

# AngelOne official SDK
pip install smartapi-python

# Upstox TOTP automation
pip install upstox-totp

# Upstox official SDK
pip install upstox-python

# Crypto: all-in-one WebSocket feed
pip install "cryptofeed[all]"

# Crypto: official exchange SDKs
pip install binance-connector pybit coinbase-advanced-py

# OmniParser (screen parsing) — clone recommended
# git clone https://github.com/microsoft/OmniParser vendor/omniparser

# UI-TARS action parser (only if GPU available)
# pip install ui-tars
```

---

## Data Flow Design (for Fable 5 build session)

```
Browser (Playwright + browser-use)
  ↓ navigate to broker page
  ↓ network intercept → capture internal API JSON
  ↓
AngelOne SmartAPI WebSocket2.0  ──┐
Upstox REST + WebSocket          ├→ Indian broker data
NSE public API (nsepython)       ──┘
                                   ↓
cryptofeed WebSocket              ──→ Crypto exchange data (Binance/Bybit/Coinbase)
                                   ↓
OmniParser (optional screenshots) ──→ Any visual data not in APIs
                                   ↓
web_signal.py
  → aggregate all → brain signal dict
  → feature_bus.record_live()
  → OpenAlgo/Freqtrade as fallback if web data absent
  → Dashboard WebReaderPanel.jsx shows per-broker tiles
```

---

## Files to Build (Fable 5 session)

```
trading/web_reader/
  __init__.py
  web_reader_loop.py             # 30s poll daemon; handles session expiry; logs abstentions
  web_signal.py                  # aggregate all sources → brain signal dict + feature_bus
  extractors/
    __init__.py
    angelone.py                  # SmartAPI WebSocket2.0 snap-quote → OI/LTP + Playwright network intercept
    upstox.py                    # upstox-python SDK + upstox-totp + Playwright screener
    nse_public.py                # nsepython: option chain, FII/DII, futures OI (NO LOGIN)
    groww.py                     # Playwright network intercept → screener data
    binance_web.py               # cryptofeed + binance-connector futures streams
    bybit_web.py                 # cryptofeed + pybit (funding+OI in one get_tickers call)
    coinbase_web.py              # cryptofeed + coinbase-advanced-py (view-only public)
    omniparser_reader.py         # OmniParser V2 integration for screenshot parsing (optional)

dashboard/routes/web_reader_ext.py    # /api/trading/web-reader/* Flask routes (_srv pattern)
dashboard/web/src/trading/WebReaderPanel.jsx  # per-broker tiles: status, last_ts, balance, OI, movers
```

---

## Sources

- https://github.com/Sparker0i/indian-stock-mcp-agent
- https://github.com/angel-one/smartapi-python
- https://github.com/batpool/upstox-totp
- https://github.com/aeron7/nsepython
- https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer
- https://github.com/markov404/AngelOneOptionChainSmartApi
- https://github.com/Neeraj-prajapat/excel-option-chain
- https://github.com/HawkEyeCoding/nse-oi-analysis
- https://github.com/bmoscon/cryptofeed
- https://github.com/ccxt/ccxt
- https://github.com/bybit-exchange/pybit
- https://github.com/binance/binance-connector-python
- https://github.com/coinbase/coinbase-advanced-py
- https://github.com/sferez/BybitMarketData
- https://github.com/jironghuang/fundingrate
- https://github.com/microsoft/OmniParser
- https://github.com/bytedance/UI-TARS
- https://huggingface.co/ByteDance-Seed/UI-TARS-1.5-7B
- https://github.com/apify/crawlee-python
- https://github.com/marketcalls/openalgo
- https://github.com/upstox/upstox-python
- https://pypi.org/project/cryptofeed/
- https://pypi.org/project/ccxt/
- https://pypi.org/project/upstox-totp/
- https://smartapi.angelbroking.com/
- https://docs.ccxt.com/docs/pro-manual
- https://docs.cdp.coinbase.com/advanced-trade/docs/ws-overview
- https://www.microsoft.com/en-us/research/articles/omniparser-v2-turning-any-llm-into-a-computer-use-agent/
- https://seed.bytedance.com/en/blog/bytedance-seed-agent-model-ui-tars-1-5-open-source-achieving-sota-performance-in-various-benchmarks
- https://arxiv.org/html/2509.02544v1 (UI-TARS-2 technical report)
- https://playwright.dev/python/docs/auth
- https://playwright.dev/python/docs/network

---

## ANGLE 5 — Full Computer Use / Screen Control Agents

**Goal:** Brain autonomously navigates trading web apps like a human — sees the screen, clicks buttons, reads all data, learns how each app works, and gets better over time. Equivalent to Claude Desktop computer use.

### Candidate Table

| Project | Repo | Control Primitives | Models | Activity | Stars | Fit Score | Verdict |
|---|---|---|---|---|---|---|---|
| **Claude Computer Use API** | https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo | screenshot, left_click, right_click, double_click, triple_click, type, key, scroll, drag, mouse_move, cursor_position, left_mouse_down/up, hold_key, wait, zoom | Claude Opus 4.8/4.7/4.6, Sonnet 4.6/4.5, Haiku 4.5 | Anthropic official, Nov 2025 beta | 17.2k | 10/10 | ✅ PRIMARY — this IS how Claude Desktop works; Python SDK; Linux Xvfb; agent loop pattern |
| **Agent-S3** (simular-ai/Agent-S) | https://github.com/simular-ai/Agent-S | screenshot, click, type, scroll, drag, key (via pyautogui) | GPT-5, OpenAI, Anthropic, Gemini, vLLM; grounding via UI-TARS-1.5-7B | Python, v0.3.2 Dec 2025, active | 12k | 10/10 | ✅ USE — highest OSWorld score (72.6% = human-level); pip install; Linux support; compositional planner |
| **SEAgent** | https://github.com/SunzeY/SEAgent | GUI screenshot + accessibility tree → actions | UI-TARS-7B evolved to SEAgent-1.0-7B | Python 3.11, Aug 2025 | 255 | 9/10 | ✅ USE for LEARNING — self-evolves by trying tasks on a new app, fails, learns, retries; will autonomously master AngelOne/Binance |
| **ZeroGUI** | https://github.com/OpenGVLab/ZeroGUI | Screenshots + VLM actions | UI-TARS-7B-DPO | Python 3.10+, May 2025 | 120 | 8/10 | ✅ USE for ONLINE LEARNING — zero human annotation; auto-generates tasks on new app, assigns own rewards, trains continuously |
| **self-operating-computer** | https://github.com/OthersideAI/self-operating-computer | screenshot, click (x,y), type, scroll, key; OCR hash-map click-by-text mode | GPT-4o, Claude 3, Gemini Pro Vision, Qwen-VL, LLaVa (local) | Python, v1.5.8 Feb 2025 | 10.2k | 8/10 | ✅ USE — simplest setup; `pip install self-operating-computer`; Mac/Win/Linux; good for quick broker exploration |
| **Midscene.js** | https://github.com/web-infra-dev/midscene | aiAct (natural language action), aiQuery (extract data), aiAssert, aiWaitFor; Playwright-native integration | UI-TARS, GPT-4o, Qwen 3.x, Gemini-3.5, Doubao | TypeScript primary, v1.10.2 Jul 2026 | 14k | 7/10 | ✅ USE for browser-only — best Playwright+VLM integration; JS-only but wrappable via Node child process from Python; web + Android |
| **browser-use** | vendor/browser_use_src/ (already vendored) | Playwright full control: click, type, scroll, navigate, screenshot, form fill, tab management, network intercept | Any LLM API | Already in project | ~12k | 10/10 | ✅ ALREADY HERE — primary browser automation layer; use for all broker browser control |
| **AGUVIS** | https://aguvis-project.github.io | Pure vision: screenshot → action (x,y + action type) | Open-source VLMs; no closed models needed | ICML 2025, Dec 2024 paper | N/A (paper) | 7/10 | ⚠️ REFERENCE — first fully autonomous vision agent without closed models; good base for offline use |
| **Salesforce GPA** | https://www.salesforce.com/blog/gpa-gui-process-automation/ | Record ONE demo → deterministic replay; Sequential Monte Carlo localization | Vision-based, local execution | Research 2025 | N/A | 7/10 | ⚠️ USE for REPLAY — after brain explores an app once, GPA approach gives 10× faster deterministic replay |
| **OpenAI Codex Record & Replay** | https://openai.com/codex | Record workflow → natural-language skill → autonomous replay | GPT-5 | v26.616, Jun 2026 | Proprietary | 5/10 | ⚠️ REFERENCE — concept: show brain once how to navigate AngelOne, it creates a reusable skill |
| **AgentDesk** | https://github.com/agentsea/agentdesk | screenshot, click, type, scroll, key, move_mouse, open_url; REST API daemon | Any LLM (via your code) | Python, v0.2.44 Apr 2024 | 222 | 5/10 | ⚠️ CONSIDER — Docker-based desktop sandbox; good for isolated safe experiments; stale since 2024 |
| **os-ai-computer-use** | https://github.com/777genius/os-ai-computer-use | Full OS control; system deps: scrot/gnome-screenshot, xdotool, xclip | GPT-5.4, Claude | Claims 75% OSWorld | ~100 | 5/10 | ⚠️ CHECK — claims top OSWorld score; verify before using; small community |

---

### Claude Computer Use API — Exact Spec (How Claude Desktop Does It)

This is what Claude Desktop uses internally. You can call the same API from Python.

**Beta header (2026):**
```
anthropic-beta: computer-use-2025-11-24
```
Supported models: `claude-opus-4-8`, `claude-opus-4-7`, `claude-opus-4-6`, `claude-sonnet-4-6`, `claude-sonnet-4-5`, `claude-haiku-4-5`

**Tool definition:**
```json
{
  "type": "computer_20251124",
  "name": "computer",
  "display_width_px": 1024,
  "display_height_px": 768,
  "display_number": 1
}
```

**All action types (what Claude can return):**
```
screenshot          → capture current screen state (no params)
left_click          → {coordinate: [x, y]}
right_click         → {coordinate: [x, y]}
middle_click        → {coordinate: [x, y]}
double_click        → {coordinate: [x, y]}
triple_click        → {coordinate: [x, y]}
left_click_drag     → {start_coordinate: [x,y], coordinate: [x,y]}
mouse_move          → {coordinate: [x, y]}
left_mouse_down     → {coordinate: [x, y]}
left_mouse_up       → {coordinate: [x, y]}
type                → {text: "string to type"}
key                 → {text: "ctrl+c"} (xdotool key names)
scroll              → {coordinate: [x,y], direction: "up|down|left|right", amount: N}
cursor_position     → {} (returns current cursor x,y)
hold_key            → {key: "shift", duration: 0.5}
wait                → {duration: 2.0}
zoom                → {coordinate: [x,y], scale: 2.0}
```

**Python agent loop pattern (exactly how Claude Desktop works):**
```python
import anthropic, base64, subprocess

client = anthropic.Anthropic()

def take_screenshot():
    # Linux: Xvfb + scrot; or playwright screenshot
    result = subprocess.run(["scrot", "-", "-"], capture_output=True)
    return base64.b64encode(result.stdout).decode()

def execute_action(action, params):
    if action == "screenshot":
        return take_screenshot()
    elif action == "left_click":
        x, y = params["coordinate"]
        subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", "1"])
    elif action == "type":
        subprocess.run(["xdotool", "type", "--", params["text"]])
    elif action == "scroll":
        x, y = params["coordinate"]
        btn = "4" if params["direction"] == "up" else "5"
        for _ in range(params.get("amount", 3)):
            subprocess.run(["xdotool", "mousemove", str(x), str(y), "click", btn])
    # ... etc

messages = [{"role": "user", "content": "Navigate to AngelOne, read the option chain for NIFTY, and return the top 5 strikes by OI"}]

for _ in range(50):  # agent loop
    response = client.beta.messages.create(
        model="claude-opus-4-8",
        max_tokens=4096,
        tools=[{"type": "computer_20251124", "name": "computer",
                "display_width_px": 1024, "display_height_px": 768}],
        messages=messages,
        betas=["computer-use-2025-11-24"],
    )
    messages.append({"role": "assistant", "content": response.content})
    
    tool_results = []
    for block in response.content:
        if block.type == "tool_use" and block.name == "computer":
            result = execute_action(block.input["action"], block.input)
            tool_results.append({
                "type": "tool_result", "tool_use_id": block.id,
                "content": [{"type": "image", "source": {"type": "base64",
                             "media_type": "image/png", "data": result}}]
            })
    
    if not tool_results:
        break  # task complete
    messages.append({"role": "user", "content": tool_results})
```

**Infrastructure required (Linux):**
```bash
# Virtual display (headless)
Xvfb :1 -screen 0 1024x768x24 &
export DISPLAY=:1

# System tools for actions
apt install xdotool scrot xclip

# OR: use Playwright (already installed) as the execution layer
# → no Xvfb needed; Playwright headless handles all clicks/types natively
```

---

### Self-Learning Architecture for Trading Apps (SEAgent + ZeroGUI Pattern)

The key insight from SEAgent and ZeroGUI: **a brain can learn to use a new app autonomously** without human annotation. The pattern:

```
1. EXPLORATION PHASE (first time the brain encounters AngelOne/Binance):
   → Brain navigates app with Claude Computer Use API (sees screen, clicks around)
   → Curriculum Generator auto-creates tasks: "find the NIFTY option chain",
     "read the top 5 OI strikes", "navigate to account balance"
   → Brain attempts each task, World State Model scores success/failure
   → Successful trajectories saved to experience memory
   → Failed trajectories used for contrastive learning

2. REFINEMENT PHASE (next 10-50 sessions):
   → Brain replays stored trajectories on the live app
   → Learns which UI elements are reliable (API JSON > DOM click)
   → Discovers that network interception captures option chain data
     without needing to click any UI element at all
   → Switches to interception-first strategy (zero clicks for data)

3. PRODUCTION PHASE (after learning complete):
   → Network interception for all data (near-zero CPU)
   → Claude Computer Use only for novel situations (app UI changed, new feature)
   → Brain's experience memory stores "AngelOne option chain = intercept URL X"
```

---

### Recommended Stack for Brain's Computer Use Capability

```
Layer 1: Action execution (what moves the mouse/keyboard)
  PRIMARY: Playwright (already in .venv) → handles browser clicks + screenshots
           → no Xvfb needed; works headless
  FALLBACK: xdotool + scrot (Linux desktop apps outside browser)

Layer 2: Vision + decision (what to click and why)
  PRIMARY: Claude Computer Use API (claude-opus-4-8, beta 2025-11-24)
           → send screenshot → get action → execute → loop
           → same as how Claude Desktop works
  SECONDARY: UI-TARS-1.5-7B local (for offline / cost-saving after training)
             → `pip install ui-tars` → parse_action_to_structure_output()

Layer 3: Self-learning (how brain gets better at using each app)
  PRIMARY: SEAgent pattern → save successful trajectories to experience memory
           → brain retries failed paths, learns reliable routes
  SECONDARY: ZeroGUI pattern → VLM auto-generates tasks on new apps,
             assigns own rewards, no human needed at all

Layer 4: Optimization (after learning complete)
  → Identify which actions can be replaced by direct API/network interception
  → Retire VLM vision for those paths; keep vision only for novel situations
  → Result: learned apps run at API speed, new apps get full vision treatment
```

---

### Files to Add in Fable 5 Build Session (Computer Use Layer)

```
trading/web_reader/computer_use/
  __init__.py
  agent_loop.py           # Claude Computer Use API loop → takes screenshot, sends to Claude, executes action
  action_executor.py      # translates Claude's action JSON → Playwright / xdotool calls
  screen_reader.py        # screenshot capture (Playwright browser or Xvfb scrot)
  app_learner.py          # SEAgent pattern: curriculum tasks, success/failure scoring, trajectory store
  experience_memory.py    # stores successful navigation trajectories per broker app
  app_explorer.py         # ZeroGUI pattern: auto-generate tasks, explore new app, discover data endpoints

trading/web_reader/computer_use/broker_skills/
  angelone_skill.py       # learned trajectory: navigate to option chain, find OI data
  binance_skill.py        # learned trajectory: navigate to liquidation map, long/short ratio
  upstox_skill.py         # learned trajectory: option chain + account balance
  tradingview_skill.py    # learned trajectory: screener filter → candidate list
```

---

### Sources (ANGLE 5)

- https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool
- https://github.com/anthropics/anthropic-quickstarts/tree/main/computer-use-demo
- https://github.com/simular-ai/Agent-S
- https://arxiv.org/html/2504.00906v1 (Agent-S2 paper)
- https://github.com/SunzeY/SEAgent
- https://arxiv.org/abs/2508.04700 (SEAgent paper)
- https://github.com/OpenGVLab/ZeroGUI
- https://arxiv.org/abs/2505.23762 (ZeroGUI paper)
- https://github.com/OthersideAI/self-operating-computer
- https://github.com/web-infra-dev/midscene
- https://midscenejs.com/integrate-with-playwright
- https://aguvis-project.github.io
- https://arxiv.org/abs/2412.04454 (AGUVIS paper)
- https://www.salesforce.com/blog/gpa-gui-process-automation/
- https://www.techtimes.com/articles/318759/20260620/openai-codex-automation-gains-record-replay-show-it-once-skip-script.htm
- https://github.com/agentsea/agentdesk
- https://github.com/ZJU-REAL/Awesome-GUI-Agents
- https://github.com/showlab/Awesome-GUI-Agent
