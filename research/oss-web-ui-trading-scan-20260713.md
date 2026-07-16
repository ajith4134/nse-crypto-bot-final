# OSS scan — trading on the broker WEB-ACCOUNT UI (not APIs): ideas to adopt/switch

Date 2026-07-13 · Phase-1 SELECT (cheap signals only: README/stars/activity — no source read yet).
Concept researched: our own model — perceive the logged-in broker web app (Binance + Upstox), take
ALL market data from the UI (interception + vision), execute via API. Goal: find OSS that does this
"to the fullest" or more advanced, and map concrete ADOPT/SWITCH moves. **Recommend-only.**

## TL;DR — the 3 findings that matter most

1. **Two SOTA GUI-perception models beat our current vision-locate approach and run LOCALLY** —
   Microsoft **OmniParser** (25.1k⭐) turns a screenshot into structured, labelled interactive
   elements for a VLM; ByteDance **UI-TARS** (11.2k⭐, Apache-2.0, 7B local) is an end-to-end
   grounding agent matching Claude Computer Use. Both support Qwen2.5-VL (our local vision stack).
   → the biggest upgrade available to `human_ui` / `nav_brain` / `brain/gui`.
2. **Independent proof that VLMs CANNOT read charts for direction/patterns** — a 4-frontier-model
   benchmark (incl. Opus 4.7) on 40 real signals: **51-57% direction (= coin-flip), 1/215 patterns,
   strong long-bias, zero confidence calibration.** This confirms our own measured result and says:
   use vision for UI GROUNDING (reading numbers/elements), NOT for price prediction. Numeric data
   must come from the WS feed (`upstox_feed`), which is exactly the design we shipped today.
3. **A resilience tool we're missing** — `protobuf-inspector` auto-reverse-engineers unknown
   protobuf blobs, so when Upstox/Binance change their web-feed schema our `upstox_feed` can
   self-recover instead of going dark.

## Map-first (what we ALREADY have — do NOT re-adopt)
`upstox_feed.py` (Upstox web-app protobuf-WS decode) · `interception.py` (in-browser Playwright WS/REST
capture) · `ui_market`/`ui_data` (RAM mirror + coverage governor) · `vision_worker`/`chart_vlm`/`chart_capture`
(local qwen2.5-VL chart read) · `sessions`/`live_browser`/`human_ui` (headed-stealth Chromium + vision
locate→click + human CAPTCHA/QR handoff) · `brain/gui` ComputerUseAgent + **vendored browser-use** ·
`nav_brain` Planner-Actor-Validator (already borrowed from Skyvern 2.0). We are already at/near SOTA on
the *agent-loop* and *WS-interception* axes; the gaps are **element grounding**, **feed resilience**,
and **anti-bot hardening**.

## Ranked candidates by dimension

### A. GUI perception / element grounding  (highest-value gap)
| Project | Repo | Signal | Why it beats us | Verdict |
|---|---|---|---|---|
| **OmniParser V2** | microsoft/OmniParser | 25.1k⭐, v2.0.1 Sep-2025, Qwen2.5-VL, CC-BY/MIT (icon model AGPL) | screenshot→structured interactive-region + icon-function map; DOM-independent, survives UI redesigns | **ADOPT** into `human_ui`/`nav_brain` perception |
| **UI-TARS 1.5-7B** | bytedance/UI-TARS | 11.2k⭐, Apache-2.0, local 7B, 42.5% OSWorld | end-to-end grounding model (elements as first-class), matches Claude Computer-Use; open weights | **EVALUATE→ADOPT** as the eyes-hand grounding model |
| Aria-UI / Zoom-to-Essence / UGround | (arXiv/HF) | research | trainless/zoom grounding tricks | idea pool for the locator |

### B. UI market-data capture / interception
| Project | Repo | Signal | Role for us | Verdict |
|---|---|---|---|---|
| **protobuf-inspector** | mildsunrise/protobuf-inspector | 1.1k⭐, ISC, Python | infers unknown protobuf schema from raw blobs | **ADOPT** — auto-heal `upstox_feed` on schema change |
| **mitmproxy + mitmproxy2swagger** | mitmproxy/mitmproxy · alufers/mitmproxy2swagger | 44k⭐ | system-proxy TLS/WS capture + auto-endpoint discovery | **ADOPT (tooling)** — discover new Upstox/Binance data endpoints fast; complements in-browser capture |
| **tradingview-scraper** family | mnwato/tradingview-scraper · dearvn/tradingview_ws · endenwer/tradingview-ws | active | reverse-engineered TradingView WS OHLC/quote/screener | **ADOPT (optional lane)** — extra UI-data source (TV already in our funnel) |
| Realtime Upstox WS v3 | naveennk045/Realtime-stock-price-streaming | small | Upstox MarketDataFeedV3 proto reference | reference for v3 (we decode v2/v3) |

### C. Browser automation & anti-bot
| Project | Repo | Signal | Why relevant | Verdict |
|---|---|---|---|---|
| **invisible_playwright** | feder-cr/invisible_playwright | 1.7k⭐, MIT, C++ fingerprint patches + Bezier mouse (Firefox) | drop-in Playwright anti-detect, ~400 fingerprint fields | **EVALUATE** — harden logins (note: Firefox-based; we're Chromium) |
| **CloakBrowser** | CloakHQ/cloakbrowser | new | Chromium C++ fingerprint patches, 30/30 detection tests | **EVALUATE** — the Chromium-native equivalent for our stack |
| Patchright / rebrowser / playwright-bot-bypass | various | active | Playwright-artifact stripping, runtime-fix | idea pool for `sessions` stealth |

### D. Autonomous web-trading agents (whole loop)
| Project | Repo | Signal | Why relevant | Verdict |
|---|---|---|---|---|
| **Skyvern** | Skyvern-AI/skyvern | 21.5k⭐, AGPL, Planner-Actor-Validator + CV page-read | the loop we already borrowed; CV page-read worth mining | reference (already aligned) |
| **browser-use / Stagehand** | browser-use · browserbase/stagehand | large | LLM web agents (browser-use vendored already) | keep vendored; watch releases |
| **LLM_trader** | qrak/LLM_trader | 110⭐, Python, paper-only | VLM chart-read + **ChromaDB "Reflection Engine"** (rules from closed trades) | **MINE IDEAS** — chart-read-specific reflection into our decision-memory |
| TradingAgents / TradingGoose / Alpaca / Vibe-Trading | tauricresearch/TradingAgents … | 2026 active | multi-agent analyst debate — but API-based, not web-UI | low priority (we have debate/lenses) |

### E. Our exact concept — Indian brokers on the web (validation, few new ideas)
srikar-kodakandla/**fully-automated-nifty-options-trading** (239⭐, Selenium Zerodha Kite web *explicitly to
avoid the ₹4000/mo API* — our motto in the wild; now deprecated on a data-API upgrade), ZerodhaAtom,
deCodeIt/Zerodha-Selenium-Automation, tushaar82/zerodha-automation, Upstox-Playwright-OAuth SDK. **Verdict:**
they validate the concept but are *less advanced* than us (single-strategy Selenium, no vision, no ML,
brittle DOM selectors). Confirms we're ahead on the data/brain axes; nothing to switch to.

## Concrete ADOPT / SWITCH plan (prioritized, mapped to our modules)

1. **[HIGH] Adopt OmniParser (or UI-TARS-7B) for element grounding** → `human_ui.locate()` / `nav_brain`
   Actor. Today we prompt a VLM "click the X button"; OmniParser gives a structured element map so the
   click is grounded to a detected region, surviving Upstox/Binance redesigns. Local, fits qwen2.5-VL.
   *Biggest robustness win for the eyes→hand loop.*
2. **[HIGH] Adopt protobuf-inspector as an `upstox_feed` self-heal** → when a decode yields all-empty
   messages (schema drift), run the inspector over the raw frames to re-infer field numbers and alert,
   instead of silently losing the NSE feed (which under today's `NSE_UI_ONLY` = hard abstain = no trades).
3. **[MED] Re-scope vision to grounding, not prediction** (evidence-driven, near-zero cost): keep
   `vision_worker`/`chart_vlm` as coarse CONTEXT only; do NOT let VLM chart-reads drive direction/patterns
   (benchmark + our own ledger agree they're coin-flip). Numbers come from `upstox_feed`/`ui_market`.
4. **[MED] mitmproxy2swagger discovery pass** → one-off tooling to map every data endpoint the Upstox/
   Binance web apps call, feeding new `kind`s into `ui_market`/`interception` (finds surfaces we're not
   yet capturing).
5. **[MED] Evaluate CloakBrowser/invisible_playwright** for `sessions`/`live_browser` login hardening —
   only if we observe bot-blocks; our headed-Xvfb stealth already works, so this is contingency.
6. **[LOW] TradingView-WS lane + LLM_trader reflection idea** — optional extra UI-data source; mine the
   chart-read reflection loop into our decision-memory. Nice-to-have, not core.

## Next step
Pick the items to build (I recommend #1 + #2 first). On approval this moves to Phase-2 INTEGRATE
(`/build-from-oss` → vendor + read the specific modules; `/stitch-projects` if combining). No code
changed yet.

## Sources
- https://github.com/microsoft/OmniParser · https://microsoft.github.io/OmniParser/
- https://github.com/bytedance/UI-TARS
- https://github.com/mildsunrise/protobuf-inspector
- https://github.com/mitmproxy/mitmproxy · https://github.com/alufers/mitmproxy2swagger
- https://github.com/mnwato/tradingview-scraper · https://github.com/dearvn/tradingview_ws · https://github.com/endenwer/tradingview-ws
- https://github.com/feder-cr/invisible_playwright · https://github.com/CloakHQ/cloakbrowser
- https://github.com/Skyvern-AI/skyvern · https://github.com/qrak/LLM_trader
- https://github.com/srikar-kodakandla/fully-automated-nifty-options-trading · https://github.com/harpalnain/ZerodhaAtom
- https://github.com/naveennk045/Realtime-stock-price-streaming
- https://github.com/tauricresearch/tradingagents
- VLM-charts caution: https://gist.github.com/roman-rr/c1cd675f7c35b68ae5ac281c30080166 · arXiv "Do VLMs Truly Read Candlesticks?" 2604.12659
