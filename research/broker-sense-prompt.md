# Broker-Sense Funnel — 10/10 build prompt (for a fresh Fable 5 session)

Copy everything in the block below into a new session.

```
Invent and build a new advanced trading feature for this project: an autonomous BROKER-APP
PERCEPTION + EXECUTION brain that finds and places trades by DRIVING BROKER WEB APPS with its own
browser + computer vision — for BOTH NSE Indian stocks and crypto, across ALL segments (NSE:
equity/futures/options; crypto: futures/spot/options/prediction). This is goal-pillar architecture
work: propose the design for approval first, then build it reuse-first. Paper-first, secrets-safe.

FIRST read (do not skip): research/universe-scan-architecture.md (full design, ALL prior-art links,
sources), research/ai-scientist/ideas-ledger.md (idea #12 "Broker-Sense Funnel"), CONVENTIONS.md,
PROJECT_BRIEF.md, /goal, and the code: trading/crypto/freqtrade/{brain_executor,run_brain_loop,
percoin_decider}.py, trading/online/live_loop.py, trading/brain/gui/agent.py, trading/brain/
credentials.py, vendor/browser_use_src, vendor/omniparser.

WHY (the problem this replaces): the current brain loop is WEDGED — it iterates the whole universe
(293 crypto / ~2000 NSE) running 153 strategy backtests per symbol, single-threaded, and NEVER
finishes a cycle -> no trades open, positions get stuck, only futures runs. Instead of us computing
signals over the whole universe, OFFLOAD the stock-picking to the brokers' own screeners and use
vision on the picked charts — saving compute and gaining accuracy.

BUILD THIS EXACT FLOW (preserve every step):
1. The brain uses ITS OWN web browser (the one it has) to open ALL the broker apps on their websites.
2. It logs in by TYPING the login details and the OTP — which it ASKS FOR in the Brain Chat box,
   where I (the owner) type them; the brain takes what I type and opens the broker app's web page.
3. It selects the trades using the broker app's ALREADY-BUILT-IN features to FILTER stocks and pick
   the best trades (use the brokers' own screeners/filters, all segments, NSE + crypto).
4. After picking the trades, for each picked stock it OPENS the candles of that stock and TAKES A
   SCREENSHOT, and uses this IMAGE of the candle pattern at 1m / 5m / 15m / 30m / 1hr for 24, and
   uses ML or DL to pick the direction — long or short, call or put, entry price, etc. — ALL this
   data. (Reuse candlestick-chart-image CNN/DL projects in the research doc: FinancialVision,
   candlesticks-deeplearning, img_candles, CNN-for-Stock-Market-Prediction-PyTorch,
   stock-pattern-recorginition; a vision-language model may also read the chart.)
5. It ALSO extracts the order-book data (like ASK and BID). For this, use a NON-INVASIVE method that
   can extract data from a web page WITHOUT touching that source — just by MONITORING it, like a
   "monitor app" / the monitor mode in Claude / screen-mirror / screen-mirroring that mirrors the
   screen and takes the data FROM the monitor. (Implement this read-only screen-perception via
   screenshot + OCR/vision on the rendered pixels — independent of the page's HTML/DOM, so it works
   on canvas order books too; reuse vendored OmniParser + paddleocr + the OCR tools in the research
   doc: Ui.Vision RPA, Copyfish, OSS-OCR, OCR.space.)
6. It PLACES the trades on PAPER using all of the above (screener pick + candle-image ML direction +
   order-book bid/ask).
7. AFTER opening the trades, it DELETES all the screenshots.
8. It uses the APIs ONLY for EXECUTION of the trades — both PAPER and REAL-money trades (OpenAlgo for
   NSE, Freqtrade for crypto). Nothing else uses the APIs; screening + candle data + order book all
   come from the broker apps via the browser/vision/monitor path above.
9. I (the owner) will DECIDE the broker apps used for real-money execution. The brain can ALSO open
   OTHER broker apps that are NOT the brokers we use for real-money execution — using those other
   apps just for screening / picking / data, not for real-money execution.

COMPUTE-SAVING FEATURES (expert additions — the whole-universe scan runs on the BROKERS' servers for
FREE; keep OUR compute tiny, cached, early-exit, and bounded by construction):
A. Server-side filter pushdown — express as MANY conditions as possible INSIDE each broker's screener
   query (volume, %-change, RSI, breakout, liquidity, spread, OI) so the broker's servers do the
   whole-universe compute for free and we only ever receive a small pre-qualified shortlist. Save +
   rotate the best-performing screener presets per segment and per market regime.
B. Cascade / tiered funnel with EARLY-EXIT — never run an expensive step on the whole universe.
   Stages get dearer and each culls: (i) broker screener -> shortlist; (ii) cheap numeric cull using
   the screener's own columns (drop illiquid / wide-spread / untradeable); (iii) a TINY fast CNN on
   the candle image for a first-pass direction on survivors; (iv) escalate to the heavy DL/VLM ONLY
   for the borderline / high-conviction few. Most candidates die at a cheap stage.
C. Event-driven, NOT polling — re-screen / re-infer only when a new candle CLOSES for that
   symbol+timeframe (websocket or screen change-detection), never on a blind timer.
D. Screenshot-hash dedup + per-bar cache — hash each candle screenshot; if identical to last bar,
   REUSE the cached ML direction and skip inference; cache (symbol, timeframe, bar) -> direction.
   Delete screenshots after use (as specified). No redundant vision runs.
E. Hot-watchlist with TTL — a symbol the screener surfaces stays "hot" for K bars; only HOT symbols
   get candle screenshots + order-book monitoring; cold symbols drop out. Bounds how many symbols we
   ever look at.
F. Batched + distilled vision — run the candle-image model as ONE batched forward pass over the
   shortlist; use a small quantized/distilled CNN (not a giant model) for direction; reserve the
   heavy model for escalations only.
G. Read-only order-book monitor, minimal + on-change — the screen-mirror reads only TOP-OF-BOOK
   (best bid/ask) for symbols we're about to trade or already holding, and only WHEN it changes —
   not the full ladder, not continuously.
H. Persistent logged-in browser sessions — keep each broker app logged in and its browser context
   REUSED across cycles (session persistence), so we don't re-login / re-render every time; refresh
   only on session expiry (ask for OTP again via Brain Chat only then).
I. Adaptive compute budget — dynamically size the shortlist N (and how many timeframes we screenshot)
   to a wall-clock / compute budget: if cycles run long, shrink; if fast, grow. Every cycle stays
   bounded and COMPLETES (this is what fixes the wedge by construction).
J. Split brokers by role for efficiency — use lightweight / free broker or 3rd-party screeners
   (no API cost to us) purely for the whole-universe narrowing, and reserve the heavier, rate-limited
   execution-broker API strictly for placing orders.

REUSE POOL (reuse-first; ask me to install anything new): vendor/browser_use_src (computer-use
browser), trading/brain/gui/agent.py, trading/brain/credentials.py (login + OTP vault), vendor/
omniparser + paddleocr (screenshot -> structured data / OCR), the candlestick-image CNN repos above,
OpenAlgo (NSE execution) + vendor/freqtrade (crypto execution). Prior art is only PIECES online — the
full autonomous broker-app-driven screener + candle-image-ML + screen-monitor funnel is the invention.

PROJECT RULES (follow exactly): PAPER-FIRST — never touch real money, real orders, API keys, or
secrets without my explicit go-ahead; reuse real tested OSS before writing from scratch (git-clone-
and-vendor when not pip-packaged); polyglot/compiled hot paths allowed; dashboard shows only REAL
wiring; regenerate INDEX.md after Python changes; run tests with the .venv interpreter
(/home/karan18190164/.venv/bin/python -m unittest discover -s tests, ML_NETWORK_SKIP_HEAVY=1); verify
live in the running app; commit only when I ask (secrets-safe scan first). Isolate
trading.state.STATE_DIR to a temp dir in any smoke test — never touch the live journal/wallets. Keep
risk/size/stop-loss decisions in CODE, never delegated to the LLM. Validate the vision/OCR reads of
price/bid/ask are accurate enough before they drive a trade (a misread digit = a wrong trade). NOTE:
the old wedged crypto brain loop (run_brain_loop) is currently PAUSED — replace it with this system.

ACCEPTANCE CRITERIA (prove each): (a) brain opens a broker web app in its browser and logs in with
login+OTP I typed in Brain Chat; (b) it picks trades using the broker's built-in filters across NSE +
crypto, all segments; (c) for each pick it screenshots the candles (1m/5m/15m/30m/1hr, 24) and an
ML/DL model outputs direction (long/short, call/put) + entry price; (d) it reads order-book bid/ask
via the non-invasive screen-monitor path (no touching the source); (e) it places PAPER trades, then
deletes all screenshots; (f) APIs are used ONLY for execution (paper + real); (g) I choose the
real-money execution brokers, and other broker apps are used for screening/data only; (h) the
compute-saving features A-J are in place and a full cycle COMPLETES in seconds within a compute
budget; (i) tests added + green, verified live, dashboard shows the real flow.

Deliverable: propose the concrete design + file plan and get my approval, THEN build it reuse-first,
test, verify live, and report. Everything paper-first until I say otherwise.
```
