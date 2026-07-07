# Broker-Sense Funnel — locked design (approved 2026-07-05)

Owner-approved build (see research/broker-sense-prompt.md for the full spec; discussion resolved
2026-07-05). The brain drives broker WEB APPS with its own browser + vision to screen, analyse and
paper-trade; APIs are used ONLY for execution. Replaces the wedged `run_brain_loop` universe scan.

## Owner decisions (locked)
1. Brokers are OPTIONAL — funnel uses whichever apps have working logins; TradingView (no login)
   always covers the gap. Missing accounts never block a cycle.
2. Crypto REAL-money execution = **Binance** (not Bybit). Bybit + Coinbase = screening-only.
   NSE real = Angel One / Upstox / Groww (owner picks ONE at go-live). Paper = Zerodha sandbox
   (OpenAlgo) + Binance dry-run (Freqtrade). Real money OFF until explicit go.
3. Brain Chat asks IN DETAIL: first login per broker asks user-id + password (+ what each field is
   for); creds saved encrypted in the vault permanently; afterwards OTP-ONLY asks stating exactly
   which broker and why. (credentials.submit gains MERGE semantics so an OTP answer never clobbers
   the saved user/pass.)
4. API FAIL-SAFE for all data: any missing/inconsistent GUI read (OCR bid/ask, candle capture,
   screener field) falls back to APIs (ccxt ticker / OpenAlgo quote+depth / Freqtrade pair_candles
   / local matplotlib candle render) — NO trade is ever skipped for missing data.
5. Old `run_brain_loop` stays PAUSED (not deleted); removed permanently once the funnel proves
   itself live.
6. ULTRA app-exploration: the brain uses EVERY feature each app offers like a human trader —
   applies the app's own chart indicators before screenshotting, reads technical-rating gauges,
   market depth, news, analytics tabs, option chains — catalogs each app's features, and any NEW
   data discovered becomes DYNAMIC LEARNING COLUMNS riding decision_snapshot.app_signals into the
   trade journal → TradeOutcomeNet learning.

## Architecture (trading/broker_sense/)
- brokers.py        broker registry + ROLE ENFORCEMENT in code (screening vs exec_paper vs exec_real)
- sessions.py       persistent logged-in Playwright contexts (storage_state on disk, saver H);
                    vault login; OTP-via-Brain-Chat with detailed notes
- screeners.py      per-broker built-in screener drivers + tradingview-screener API pushdown
                    (savers A, J); preset store + rotation per segment/regime
- app_explorer.py   ultra feature exploration: per-app feature catalog + human-trader checklist;
                    discovered numeric fields → learning_columns
- learning_columns.py dynamic column registry; snapshot() → decision_snapshot.app_signals
                    (merged into ClosedTrade by freqtrade_ingest at close — no schema change)
- chart_vision.py   candle screenshots 1m/5m/15m/30m/1h × 24 bars; screenshot-hash dedup +
                    per-(symbol,tf,bar) cache (saver D); local matplotlib render fallback (rule 4);
                    screenshots DELETED after inference
- cnn_direction.py  vendored res_cnn (vendor/candlestick_cnn, warm-start cnn.pkl) batched forward
                    (saver F) + LLM escalation for borderline (saver B); NodeProtocol face
- book_monitor.py   read-only screen-mirror: screenshot region → PaddleOCR → top-of-book only,
                    on-change only (saver G); accuracy gate vs reference price
- data_failsafe.py  the rule-4 API fallbacks: ccxt/Freqtrade/OpenAlgo quotes, candles, depth
- watchlist.py      hot watchlist TTL K bars (saver E)
- funnel.py         cascade orchestrator w/ adaptive compute budget (savers B, I) — every cycle
                    COMPLETES by construction; reuses BrainExecutor gates (UQ/psych/memory) via
                    run_once(symbols=shortlist)
- exec_adapter.py   APIs ONLY for execution: crypto → CryptoEngineClient (Binance), NSE →
                    OpenAlgoClient (Zerodha sandbox); real-money branch HARD-GATED off
- run_funnel_loop.py driver replacing run_brain_loop; bar-close event trigger (saver C); boss
                    obedience + BrainLearningCycle + mind_events preserved

## Reuse decisions (build-from-oss)
| Piece | Source | Status |
|---|---|---|
| Browser + login + OCR + feed | trading/brain/gui/web_screener.py + perception.OcrReader | reuse |
| Credential vault + chat flow | trading/brain/credentials.py (+merge patch) | reuse |
| Screener pushdown | tradingview-screener 3.2.1 (pip, installed) | new dep (approved) |
| Candle-image CNN | vendor/candlestick_cnn = hardyqr/CNN-for-Stock-Market-Prediction-PyTorch (cloned 2026-07-05, depth 1) | vendored (approved) |
| OCR engine | paddleocr + paddle (installed, oneDNN-off fix in perception.py) | reuse |
| Crypto exec | trading/crypto/engine_client.CryptoEngineClient.place_order | reuse |
| NSE exec + quote/depth failsafe | trading/openalgo_client.OpenAlgoClient | reuse |
| Crypto quote failsafe | ccxt (installed) | reuse |
| Chart render fallback | matplotlib (installed) | reuse |
| Gates (risk stays in CODE) | BrainExecutor UQ/psychology/decision-memory via run_once(symbols=…) | reuse |
| Skills/reflection for app driving | trading/brain/gui/skills.py + reflection.py (Voyager/Reflexion pattern) | reuse |

Rejected: bybit for real crypto exec (owner: Binance), mplfinance (not installed; matplotlib
suffices), OmniParser-primary (GPU-heavy; PaddleOCR primary, OmniParser optional upgrade),
FinancialVision et al (candlestick_cnn chosen: cleanest PyTorch + shipped trained_model; others
remain referenced in research/universe-scan-architecture.md).
