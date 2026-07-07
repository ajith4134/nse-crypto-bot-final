# Web Reader / Broker Scraper — OSS Research
**Date:** 2026-07-05  
**Goal:** Brain reads all broker web UIs (AngelOne, Upstox, Binance, Bybit, Coinbase) as PRIMARY data source, with session-cookie persistence, full feature access, dashboard panel + signal feed.

---

## Candidate Table

| Project | Repo / URL | Key Features | Activity | Fit Score | Verdict |
|---------|-----------|--------------|----------|-----------|---------|
| **browser-use** (already vendored) | vendor/browser_use_src/ | Playwright-based browser agent, DOM+screenshot hybrid, BrowserContextConfig supports storage_state (Issue #702) | Active, already in project | 10/10 | ✅ USE — already here, handles session |
| **Playwright storage_state** | playwright.dev/python/docs/auth | `context.storage_state(path='session.json')`, `new_context(storage_state=...)` — saves cookies+localStorage+IndexedDB; `launch_persistent_context(user_data_dir=...)` for full profile persistence | Built into Playwright | 10/10 | ✅ USE — core session persistence mechanism |
| **cryptofeed** | pypi.org/project/cryptofeed/ | 40+ exchanges incl. Binance/Bybit/Coinbase; WebSocket+REST; L1/L2/L3 order books, trades, tickers, funding rates, open interest, liquidations, OHLCV; authenticated channels for balances/orders; normalized callbacks; Redis/Kafka/Postgres backends | v2.4.1, Feb 2025, Beta, Python 3.9+ | 9/10 | ✅ USE — crypto exchange real-time data |
| **indian-stock-mcp-agent** | github.com/Sparker0i/indian-stock-mcp-agent | Playwright persistent context per broker, network interception (captures JSON from broker's own APIs), AES-256 session encryption, 6h TTL; supports Groww/Zerodha/INDmoney (NOT AngelOne/Upstox directly) | 11 stars, 13 commits, TypeScript | 6/10 | ⚠️ BORROW APPROACH — network intercept pattern is excellent; TypeScript so don't import directly |
| **OpenAlgo** (already running) | github.com/marketcalls/openalgo | Unified API for AngelOne, Upstox + 30+ brokers; option chain, IV smile, max pain, vol surface, GEX dashboard built-in; already running as OpenAlgo server | Active, already in project | 8/10 | ✅ USE AS FALLBACK — already wired; use web scraper as PRIMARY, OpenAlgo as API fallback |
| **AngelOneOptionChainSmartApi** | github.com/markov404/AngelOneOptionChainSmartApi | AngelOne SmartAPI NFO option chain reader (Python) | Low activity, small | 5/10 | ⚠️ REFERENCE — SmartAPI approach, not web scraping |
| **upstox-python** | github.com/upstox/upstox-python | Official Upstox Python SDK with OptionsApi (get_put_call_option_chain) | Official SDK | 6/10 | ⚠️ API FALLBACK — use when web session expires |
| **python-binance** | github.com/sammchardy/python-binance | Binance Exchange API Python — comprehensive REST+WebSocket | Active, 3k+ stars | 7/10 | ⚠️ API FALLBACK — cryptofeed preferred for normalised multi-exchange |
| **ZerodhaAtom / Zerodha-Selenium-Login** | github.com/harpalnain/ZerodhaAtom | Selenium-based Zerodha automation | Older, Selenium | 3/10 | ❌ SKIP — Playwright is better, Zerodha not priority |

---

## Recommendation

**Architecture: 3-layer stack**

### Layer 1 — Session Management (Playwright persistent_context)
- One `user_data_dir` per broker: `trading/web_sessions/{broker}/profile/`
- On startup: try loading saved `storage_state.json` → if expired, open visible browser → user logs in → brain saves state
- Uses `browser.launch_persistent_context(user_data_dir=..., headless=False)` for first login, then `headless=True` with loaded storage_state for data extraction
- Session TTL detection: test a known authenticated URL after load; if redirect to login, trigger re-auth

### Layer 2 — Data Extraction
**Indian brokers (AngelOne, Upstox):**
- Use **network interception** (Playwright `page.on("response", ...)`) to capture the broker's own internal API calls that power their web UI — much more reliable than DOM scraping
- AngelOne internal APIs: option chain JSON at `apiconnect.angelbroking.com`, market data at `margincalculator.angelbroking.com/...`
- Upstox internal APIs: intercepted from network tab
- Also use DOM selectors for account balance, positions table (simpler pages)

**Crypto exchanges (Binance, Bybit, Coinbase):**
- **cryptofeed** (pip install): WebSocket streams for L2 order book, trades, tickers, funding rates, open interest, OHLCV — normalized across all three
- Playwright scraping for UI-only features: Binance futures screener, Bybit liquidation heatmap, Coinbase futures list

### Layer 3 — Signal Bridge
- `web_signal.py`: aggregates all extracted data → converts to standard brain signal format
- Registers as a signal source in the brain's signal pipeline (same interface as other signal nodes)
- Updates every 30s for Indian brokers, real-time WebSocket for crypto

**Primary/Fallback priority:**
1. Primary: Web scraper / cryptofeed WebSocket
2. Fallback: OpenAlgo REST API (already running)
3. Fallback 2: Direct exchange APIs (python-binance, upstox-python)

---

## Files to Build

```
trading/web_reader/
  __init__.py
  session_manager.py          # Playwright persistent_context per broker, storage_state save/load
  extractors/
    __init__.py
    angelone.py               # Network intercept → option chain OI/premium, balance, top movers, positions
    upstox.py                 # Network intercept → option chain, F&O positions, balance
    binance_web.py            # cryptofeed WebSocket + Playwright for UI-only features
    bybit_web.py              # cryptofeed WebSocket + Playwright
    coinbase_web.py           # cryptofeed WebSocket (view-only, no account)
  web_signal.py               # Aggregates → brain signal format
  web_reader_loop.py          # Daemon: poll extractors, update signal, handle session expiry
dashboard/routes/web_reader_ext.py   # /api/trading/web-reader/* endpoints
dashboard/web/src/trading/WebReaderPanel.jsx  # Live panel: per-broker data tiles
```

---

## Sources
- https://github.com/Sparker0i/indian-stock-mcp-agent
- https://pypi.org/project/cryptofeed/
- https://playwright.dev/python/docs/auth
- https://github.com/browser-use/browser-use/issues/702
- https://github.com/marketcalls/openalgo
- https://github.com/markov404/AngelOneOptionChainSmartApi
- https://github.com/upstox/upstox-python
- https://github.com/sammchardy/python-binance
