# Trading Execution Phase — Complete Blueprint

> **Status:** Research + Planning complete. **T1 (NSE Foundation) BUILT + LIVE-VERIFIED**
> against a running OpenAlgo server (Zerodha, paper/analyzer mode): real connectivity,
> instrument search, WS tick feed, master toggle, and full paper order place→modify→cancel
> all confirmed (2026-06-28). `trading/` package + `run_trading.py` + 12 passing tests.
> Server runs at ~/srv/openalgo (gunicorn+eventlet).
> **T2 (Crypto Foundation) BUILT + LIVE-VERIFIED** (`trading/crypto/`: ccxt exchange
> client, liquidation calc, paper-fill engine walking the real order book, funding monitor,
> feed, watchlist, CryptoSession; `run_crypto_trading.py`; 14 offline tests). Confirmed live
> vs Binance perps (2026-06-28): real ticks, funding rates across binance+bybit with spread,
> paper order on real order book with correct liquidation price. Paper-first, no keys;
> live order path key-gated.
> **T3 (Trade Execution Engine) BUILT** (`trading/execution/`: order lifecycle SM,
> tick-by-tick MAE/MFE, exponential/ATR/SAR/Chandelier trailing + profit-lock, partial
> profit-booking ladder, daily circuit breaker, SEBI SPAN+exposure margin check,
> bracket/cover builders, kill-switch; `ExecutionEngine` composes them with honest
> `status()`; `run_trading_t3.py` deterministic offline demo). Network-INDEPENDENT —
> market I/O injected, so one engine drives paper/live NSE+crypto + tests.
> **T4 (Options Intelligence) BUILT** (`trading/options/`: Black-76 Greeks — analytic +
> optional fast-vollib backend, implied vol, IV Rank/Percentile, Max Pain, PCR (OI+volume),
> GEX + zero-gamma flip + gamma walls, OI heatmap/OITracker, multi-leg payoff (breakevens +
> max P/L), `OptionsChain` container tying one injected-quote snapshot to every analytic with
> honest `status()`; `run_options_t4.py` deterministic offline demo). Quotes INJECTED — fully
> offline-testable, live feed only supplies OptionQuotes.
> **T5 (Brain Confidence + Analytics) BUILT** (`trading/journal/`: 85+ column closed-trade
> journal (single-source schema), Indian (STT/txn/brokerage/GST/SEBI/stamp) + crypto
> (maker/taker + funding) charges → net P&L, MAE/MFE/R-multiple/entry-exit-efficiency
> quality, analytics (win-rate by instrument/strategy/regime/day/hour, profit factor,
> expectancy, win/loss streaks, R-multiple distribution, MAE/MFE scatter), revenge-trade +
> overtrading detector, per-symbol Brain confidence (Bayesian win-rate + Brier calibration)
> with recalibration hook, QuantStats-enriched dependency-free HTML + PDF tearsheet
> (weasyprint); `TradeJournal` composes them with honest `status()`; `run_journal_t5.py`
> deterministic offline demo). Trades INJECTED — offline-testable, the execution loop only
> feeds ClosedTrades.
> **T6 (Dark-Pro UI) BUILT** (`dashboard/web/src/trading/`: React + TradingView Lightweight
> Charts v5 PriceChart, custom OrderFlowMap depth/flow primitive, scrolling TickerTape,
> 22-col OpenTradesPanel, 110-col ClosedTradesTable (sort/filter/column-chooser/CSV export),
> single-trade TradeDrilldown (inline-SVG replay + MAE/MFE band), Brain ConfidenceHeatmap,
> ContextPanel (VIX/FII-DII/Fear&Greed, honest available-flags), NSE+Crypto pop-out
> MarketWindows; `TradingDashboard` + Brain/Trading tab in `App.jsx`, fed by one
> `useTrading()` hook off 5 new honest backend endpoints — /tickers /opentrades /closedtrades
> /confidence /context — all demo-labelled, real computed state only). Verified: `npm run
> build` green (1221 modules), every endpoint serves live JSON.
> **T7 (Alerts + Automation) BUILT** (`trading/alerts/`, Telegram-only by request: AlertEvent
> model + builders (fill / daily P&L / signal / circuit-breaker / kill), smart TTL +
> content-hash dedup (critical bypasses), secrets-safe AlertConfig from env (token redacted,
> dry-run without creds), TelegramChannel (INJECTED transport, dry-run aware, live verified),
> Markdown formatter, AlertDispatcher (dedup → fan-out, honest status()), /positions /pnl /kill
> CommandRouter over injected callables, daily/weekly ReportScheduler (deterministic run_due),
> live python-telegram-bot runner (guarded import); `run_alerts_t7.py` deterministic offline
> demo + `/api/trading/alerts/status` dashboard endpoint). Transport INJECTED — fully
> offline-testable, real delivery key-gated on TELEGRAM_BOT_TOKEN+TELEGRAM_CHAT_ID.
> **T8.1 (Strategy genome + operators + walk-forward backtest) BUILT — REUSE-FIRST**
> (`trading/strategy/`: wraps battle-tested OSS behind thin adapters — **TA-Lib** for the
> feature frame, **DEAP** typed genetic-programming for the genome (z-scored features →
> +1/-1/0 signal) + its cxOnePoint/mutUniform/mutNodeReplacement operators, **vectorbt** for
> the vectorized no-lookahead backtest (next-bar execution, cost on turnover); our code is the
> glue: trading primitive set, genome↔signal bridge, walk-forward OOS fold splitter,
> market-legal feature sets, provenance. `run_strategy_t8.py` deterministic offline demo +
> `/api/trading/strategy/status` dashboard endpoint; 28 offline tests). New deps: talib, deap,
> vectorbt, gplearn (CPU; numpy 2.3 intact). OHLCV INJECTED — offline-testable on seeded
> synthetic bars; live crypto (ccxt)/NSE (OpenAlgo) frames feed the same genome/backtest.
> **T8.2 (journal-fitness + overfitting guardrails) BUILT — REUSE-FIRST**
> (`trading/strategy/fitness.py` + `guardrails.py`: multi-objective OUT-OF-SAMPLE fitness
> over the T8.1 walk-forward folds — expectancy / OOS Sharpe / -|max drawdown| / -trade-count
> penalty, returned both scalarised (ranking) and as an NSGA-II objective tuple (T8.3), with
> an optional T5 journal realised-P&L blend so the score tracks live behaviour; overfitting
> guardrails (López de Prado): Probabilistic & **Deflated Sharpe** (scipy norm/skew/kurtosis,
> benchmark inflated by N trials), **PBO via CSCV** (combinatorially-symmetric IS/OOS splits),
> Spearman **rank-IC** gate, plus walk-forward OOS-positivity / min-trades / max-drawdown gates;
> reuse-first — all statistics from `scipy.stats`, our code is the formulas + gating glue, no
> new deps. `run_strategy_t8.py` extended (T8.2 fitness leaderboard + top-N guardrail report
> with DSR/PSR + population PBO) and `/api/trading/strategy/status` now emits per-strategy
> `fitness_score` + `guardrail_passed` and a top-level `guardrails.pbo`. Verified offline,
> deterministic, exit 0 — as expected NO random genome clears the 12-trial deflated Sharpe
> (honest: random genomes rarely beat a multiple-testing-deflated benchmark). OHLCV/journal
> INJECTED — offline-testable on seeded synthetic bars.
> **T8.3 (DEAP NSGA-II evolution loop → NodeProtocol promotion) BUILT** — REUSE-FIRST
> (`trading/strategy/evolve.py` + `registry.py`: a (μ+λ) NSGA-II loop over the Strategy
> genome — `deap.tools.selNSGA2` environmental selection + `tools.sortNondominated` for the
> Pareto front — driving each individual through the T8.2 OUT-OF-SAMPLE multi-objective
> fitness (expectancy / OOS Sharpe / -|max DD| / -trade penalty) every generation so the
> front never regresses; survivors are gated by the T8.2 overfitting guardrails and the
> passers are PROMOTED to NodeProtocol `StrategyNode`s via a `StrategyRegistry` (the brain can
> route/ensemble them like any other node, with a sample `predict_proba` over a trading
> feature matrix); reuse-first — selection/Pareto from `deap.tools`, our glue is the toolbox
> wiring + guardrail gate + genome→node bridge, no new deps. `run_strategy_t8.py` extended
> (per-generation history table, Pareto-front size, promoted-node count, and an always-on
> genome→NodeProtocol promotion-path demo) + `/api/trading/evolution/status` dashboard
> endpoint emitting the JSON-able `EvolutionResult.as_dict()` (history, pareto_size,
> n_promoted, best, registry). Verified offline, deterministic, exit 0. OHLCV INJECTED —
> offline-testable on seeded synthetic bars; live ccxt/OpenAlgo frames feed the same loop.
> **T8.4 (episodic experience bank + semantic memory) BUILT — REUSE-FIRST** (`trading/brain/`):
> LanceDB-backed Case-Based Reasoning over a deterministic, no-leakage numeric trade-setup
> vector — retrieve the k analogous past trades for a new setup → bias the decision by their
> outcomes (expected win-rate / expected P&L / directional bias / confidence, with an
> auditable precedent trail), accuracy growing mechanically as the case base grows, with a
> numpy exact-kNN fallback so it always works; mem0 semantic text-memory (free-text trade
> lessons that don't fit a vector) shipped WITH this step — REAL LLM-extracted/consolidated
> memory when MEM0_ENABLED=1 + an OpenAI-compatible LLM is configured, a functional keyword
> dry-run otherwise. `run_brain_t8.py` deterministic offline demo + `/api/trading/experience/status`
> dashboard endpoint. Trades INJECTED — offline-testable, the live loop feeds the same cases.
> **T8.5 (continual learning + self-eval auto-quiz) BUILT — REUSE-FIRST** (`trading/brain/`):
> River online-learning `OnlineNode` (NodeProtocol, StandardScaler→LogisticRegression, ADWIN
> concept-drift detection that keeps learning tick-by-tick and flags regime shifts);
> P&L/importance-weighted `ReplayBuffer` + `replay_retrain` interleaving old regimes with new
> samples (anti-catastrophic-forgetting); **AutoQuiz prequential (test-then-train) self-test
> that PROVES predictive accuracy rises with experience** — the accuracy-vs-trade-count curve
> + its fitted slope are the honest proof on a learnable stream; MAML-style `MetaLearner`
> warm-start (clone global learned state into a new per-symbol model) quantifying few-shot
> sample-efficiency (warm-vs-cold accuracy + gain); Reflexion self-critique notes (predicted
> vs actual → short lesson) written into the T8.4 semantic memory. Reuse-first — online ML /
> drift from **river**, our code is the NodeProtocol glue + prequential quiz + meta-init +
> reflection. `run_brain_t8.py` extended (AutoQuiz curve + slope, drift events, warm/cold
> few-shot adapt, Reflexion note) + `/api/trading/selfeval/status` dashboard endpoint.
> Deterministic, offline, exit 0. Streams SEEDED-SYNTHETIC — offline-testable, the live loop
> feeds the same online/replay/quiz path. Next: T8.6 (pattern/regime [STUMPY/hmmlearn] +
> asset-picking/entry-exit).
> **T8.6 (pattern/regime + asset-picking + entry/exit) BUILT — REUSE-FIRST** (`trading/brain/`):
> **STUMPY** matrix-profile motif/anomaly (discord) discovery + **TA-Lib** candlestick
> recognizers (`PatternScanner.scan` → motifs/anomalies/anomaly-score/candles-firing);
> **hmmlearn** GaussianHMM regime detection auto-labelled bull/bear/neutral (`RegimeModel`)
> + `RegimeGate` regime-gated strategy activation; asset-picking via a **VENDORED gplearn**
> symbolic factor miner (`vendor/gplearn` — first use of the vendor-first rule, a LEARNED
> symbolic ranking program, factor_source='gplearn') with a composite z-score fallback +
> Spearman rank-IC quality gate; regime/anomaly-gated `EntryExitPolicy` (entry blocked off-
> regime or on anomaly spike; exit on regime-change / anomaly / signal-reversal) with an
> optional **River** learned-exit OnlineNode. Engines pip-installed (STUMPY/hmmlearn/TA-Lib
> are compiled — not vendorable), gplearn VENDORED in-tree. Honest deferrals: **Qlib**
> (no py3.13 wheel) for a richer alpha-expression factor layer, **FinRL** RL-exits (the lean
> River learned-exit covers it now, same `should_exit` interface). `run_brain_t8.py` extended
> (T8.6 pattern/regime scan + LEARNED gplearn program + asset-pick + entry/exit decisions) +
> `/api/trading/patterns/status` dashboard endpoint. Deterministic, offline, exit 0. OHLCV
> SEEDED-SYNTHETIC (bull/bear/neutral segments + injected discord) — offline-testable, the
> live loop feeds the same scan/regime/pick/gate path. Next: T8.7 (autonomous news research +
> sentiment nodes).
>
> **T8.7 (autonomous news research + sentiment) BUILT — VENDOR-FIRST** (`trading/brain/`):
> **VENDORED VADER** (`vendor/vaderSentiment`, finance-lexicon-boosted: beat/miss/upgrade/
> probe/…) CPU sentiment scoring headline tone → [-1,1] compound + label, no download;
> **FinBERT** (ProsusAI) optional gated backend (`SentimentScorer(backend='finbert'/'auto')`,
> activates when `transformers` installed, else clean VADER fallback); **NewsResearcher**
> (`feedparser` RSS behind an INJECTED fetcher → offline-testable on a fixed NewsItem list)
> aggregating per-symbol news sentiment (avg compound / label / bullish-vs-bearish / top
> headlines); **NewsSentimentNode** (NodeProtocol, compound→p(bullish)); gated **GPT-Researcher**
> autonomous-web-research hook (`autonomous_research`, set `GPT_RESEARCHER_ENABLED=1` + an LLM
> key) that degrades to a note offline; feeds the **T7 Telegram** alert path / **Stream-of-Mind**.
> `run_brain_t8.py` extended (T8.7 scoring + per-symbol research for RELIANCE/BTC + p(bullish)
> node + gated autonomous status + dry-run Telegram sentiment alert) + `/api/trading/news/status`
> dashboard endpoint. Deterministic, offline (fixed NewsItem feed — never calls real RSS/
> network), exit 0. Next: T8.8 (skill library + self-improvement [GEPA/DSPy] + observability
> [Langfuse]).
>
> **T8.8 (skill library + self-improvement + observability) BUILT — REUSE-FIRST** (`trading/brain/`):
> **Voyager-pattern SkillLibrary** (`skills.py`: quality-gated, growing, JSON-persisted store of
> VALIDATED strategy/rule skills — admits only if a skill clears the metric gate AND beats any
> same-named incumbent + market/metric-ranked retrieval, so the library compounds only with
> what worked); **SelfImprover** (`selfimprove.py`: deterministic CPU hill-climb optimising
> params against the T8.2 fitness — e.g. EntryExitPolicy `max_anomaly`/`exit_threshold` — REAL,
> offline) PLUS a gated **DSPy/GEPA** LLM-program optimiser (the previously-deferred GEPA/DSPy
> land HERE, where an LLM reasoning module exists; activates with `DSPY_ENABLED=1` + an
> OpenAI-compatible key); **BrainTracer** observability (`observability.py`: local in-memory
> span recorder → **Stream-of-Mind** feed, optional **Langfuse** export when `LANGFUSE_*` keys
> set). `run_brain_t8.py` extended (T8.8 skill admit/reject/improve + Stream-of-Mind spans +
> SelfImprover start→best + gated DSPy status) + `/api/trading/skills/status` dashboard endpoint.
> Deterministic, offline (demo SkillLibrary `persist=False` — no disk state), exit 0. New pip
> deps: `dspy` (bundles `gepa`), `langfuse` (frameworks — gated).
> **T8.9 (end-to-end brain pipeline + safety review) BUILT — FINALE** (`trading/brain/pipeline.py`):
> **BrainTradingPipeline** stitches the full T8 stack into ONE traced, safety-gated decision per
> market — features (T8.1) → regime (T8.6) → pattern/anomaly (T8.6) → news-sentiment (T8.7) →
> evolved-strategy signal (T8.1–3) → experience-recall bias (T8.4) → regime/anomaly-gated entry
> (T8.6) — with EVERY step recorded by the BrainTracer (T8.8) → **Stream-of-Mind**, and the final
> action **SAFETY-GATED to FLAT** whenever the **T3 kill-switch** is engaged or the
> **DailyCircuitBreaker** has tripped. `safety_review()` audits the paper-first posture (kill-switch
> + breaker wired, entry-gating + tracer active) before any live capital. ONE code path drives both
> NSE + Crypto (all components INJECTED). `run_brain_t8.py` finale (T8.9: CRYPTO BTC/USDT + NSE
> RELIANCE end-to-end decisions + Stream-of-Mind + safety_review + a demonstrated kill-switch→FLAT
> gate) + `/api/trading/brain/status` dashboard endpoint. Deterministic synthetic OHLCV + FIXED
> offline news feed, `persist=False`, exit 0.
> **Phase T8 (strategy creation/mutation/evolution + ultra-brain) is COMPLETE (T8.1–T8.9).**
> Next: T8 dashboard panel (React) + full-suite verification.
> **Sources:** Deep research (106 agents, 1.77M tokens, 18 adversarially-verified claims, 7 killed).
> **Date:** 2026-06-28. **Hard rules carried in:** CPU-first, reuse-first (stitch OSS), ask-to-install,
> honest-wiring (dashboard shows only real state), secrets in `.env`.

---

## 0. Vision

Two independently on/off-switchable trading markets — (A) Indian NSE and (B) Crypto — each opening
its own dashboard window (separate browser tab/popup). Both wired to the ML Network Brain for
per-symbol confidence scores recalibrated continuously against realized P&L. Paper trading on live
market data with a hard switch to real money. A watchlist with search (empty = bot self-selects).

**Design language:** Dark Pro — Binance/TradingView aesthetic (dark bg, neon green/red P&L,
glowing charts, dense data, TradingView Lightweight Charts v5).

---

## 1. Confirmed Market Scope

### A. NSE Window — 6 Market Types

| Market Type | Instruments | Broker APIs |
|---|---|---|
| **Intraday (MIS)** | All ~5000 NSE-listed stocks | Zerodha + Upstox + Angel One |
| **MTF (Margin Trade Financing)** | MTF-eligible stocks (~500), overnight leverage up to 4× | Zerodha Kite |
| **Equity Options** | All F&O stocks (~200) — all strikes, weekly/monthly expiry | Zerodha + Upstox + Angel |
| **Index Options** | Nifty50, BankNifty, FinNifty, MidcapNifty, Sensex (weekly + monthly) | All 3 brokers |
| **Equity + Index Futures** | All F&O stocks + Nifty/BankNifty/FinNifty (near/mid/far month) | All 3 brokers |
| **Commodities + Derivatives** | MCX: Gold, Silver, Crude Oil, Natural Gas, Copper, Zinc, Aluminium, Lead, Nickel; NCDEX agri; options on Gold + Crude | Zerodha + Angel (MCX-enabled) |

**NSE-specific rules:**
- Instruments CSV download at startup (Zerodha scripmaster: 50k+ instruments)
- MCX session: 9 AM – 11:30 PM (evening session included)
- T+1 settlement tracking for equity CNC positions
- MTF overnight interest calculation
- F&O ban list monitor (auto-skip banned stocks)
- Circuit limit monitor (auto-cancel if upper/lower circuit hit)
- SEBI SPAN + Exposure margin check before every order
- Auto-squareoff: NSE/BSE 15:15, MCX 23:30, CDS 16:45 IST

### B. Crypto Window — 3 Market Types + Full Leverage

| Market Type | Instruments | Exchanges | Leverage |
|---|---|---|---|
| **Spot** | All pairs (BTC/USDT, ETH/USDT, altcoins) | Binance + Bybit | 1× |
| **Perpetual Futures (USDS-M)** | BTC, ETH, all major alts | Binance + Bybit | Up to 125× (Binance) / 100× (Bybit) |
| **Dated/Quarterly Futures** | BTC quarterly, ETH quarterly | Binance + Bybit | Up to 20× |
| **Options** | BTC, ETH options | Binance (European) + Bybit + Deribit (via ccxt) | Up to 10× |
| **COIN-M Futures** | Inverse BTC/ETH (coin-margined) | Binance | Up to 125× |

**Crypto-specific requirements:**
- Leverage selector per trade (dropdown: 1×, 2×, 5×, 10×, 20×, 50×, 100×, 125×)
- Margin mode toggle per symbol: Cross vs Isolated
- Liquidation price shown real-time on every leveraged open position
- Funding rate + next funding countdown per perpetual (Binance + Bybit)
- COIN-M vs USDS-M portfolio shown separately (different margin pools)

---

## 2. Verified OSS Stack (research-confirmed)

### ✅ CONFIRMED — Build On These

#### NSE Layer

| Library | GitHub / Docs | PyPI | What it does | Confidence |
|---|---|---|---|---|
| **OpenAlgo** (server) | [github.com/marketcalls/openalgo](https://github.com/marketcalls/openalgo) · [docs.openalgo.in](https://docs.openalgo.in) | `pip install openalgo` | Self-hosted Flask+React middleware: 33 Indian brokers unified via one REST API, all segments (NSE/BSE/NFO/BFO/MCX/CDS), built-in ₹1 Crore paper sandbox with exchange-aligned auto-squareoff (NSE 15:15, MCX 23:30), single endpoint paper↔live toggle, PnL Tracker via TradingView Lightweight Charts, webhook receiver | **3-0 HIGH** |
| **OpenAlgo Python Library** | [github.com/marketcalls/openalgo-python-library](https://github.com/marketcalls/openalgo-python-library) | `pip install openalgo` | 100+ technical indicators, Rust core via PyO3, TA-Lib speed without TA-Lib install | **3-0 HIGH** |
| **OpenBull** | [github.com/marketcalls/openbull](https://github.com/marketcalls/openbull) | — (self-hosted) | React 19 + FastAPI; 5 broker connectors; tick-driven paper engine with T+1 settlement; 8 options analytics REST routes: /gex /maxpain /ivsmile /volsurface /oitracker /optiongreeks | **2-1 MEDIUM** (2 months old) |
| **pykiteconnect** | [github.com/zerodha/pykiteconnect](https://github.com/zerodha/pykiteconnect) · [kite.trade/docs](https://kite.trade/docs/connect/v3/) | `pip install kiteconnect` | Official Zerodha client v5.2.0; EXCHANGE_NSE, EXCHANGE_NFO; KiteTicker WebSocket streaming | **3-0 HIGH** |
| **Upstox Python SDK v2** | [github.com/upstox/upstox-python](https://github.com/upstox/upstox-python) · [upstox.com/developer/api-documentation](https://upstox.com/developer/api-documentation/open-api/) | `pip install upstox-python-sdk` | Official Upstox v2 client; order placement, WebSocket market data feed | supporting |
| **smartapi-python** | [github.com/angel-one/smartapi-python](https://github.com/angel-one/smartapi-python) · [smartapi.angelbroking.com](https://smartapi.angelbroking.com/docs) | `pip install smartapi-python` | Official Angel One client; four-factor auth (API key + PIN + TOTP via pyotp); SmartWebSocketV2 streams NSE_CM, NSE_FO, MCX_FO; no built-in paper trading | **3-0 HIGH** |
| **fast-vollib** | [github.com/raeidsaqur/fast-vollib](https://github.com/raeidsaqur/fast-vollib) · [arXiv:2604.27210](https://arxiv.org/abs/2604.27210) | `pip install fast-vollib` | Black-76 (MCX commodity options), Black-Scholes, BSM; single `get_all_greeks()`; drop-in py_vollib compat via `patch_py_vollib()` | **2-1 HIGH** (pre-1.0; keep py_vollib_vectorized as fallback) |
| **py_vollib_vectorized** | [github.com/marcdemers/py_vollib_vectorized](https://github.com/marcdemers/py_vollib_vectorized) | `pip install py-vollib-vectorized` | Vectorized Black-Scholes Greeks — fallback if fast-vollib breaks | safety net |
| **nsepy** | [github.com/swapniljariwala/nsepy](https://github.com/swapniljariwala/nsepy) | `pip install nsepy` | Historical NSE OHLCV data, OI data, F&O data (free, no API key) | data source |
| **nsetools** | [github.com/vsjha18/nsetools](https://github.com/vsjha18/nsetools) | `pip install nsetools` | Live NSE quotes, gainers/losers, FII/DII data scraper | data source |
| **pyotp** | [github.com/pyauth/pyotp](https://github.com/pyauth/pyotp) | `pip install pyotp` | TOTP generation for Angel One two-factor auth | auth utility |

#### Crypto Layer

| Library | GitHub / Docs | PyPI | What it does | Confidence |
|---|---|---|---|---|
| **ccxt** | [github.com/ccxt/ccxt](https://github.com/ccxt/ccxt) · [docs.ccxt.com](https://docs.ccxt.com) | `pip install ccxt` | Unified API for 106 exchanges (Binance, Bybit, OKX, KuCoin Futures, Hyperliquid, BitMEX certified); REST + WebSocket; spot/swap(perp)/futures/options with leverage | **3-0 HIGH** |
| **python-binance** | [github.com/sammchardy/python-binance](https://github.com/sammchardy/python-binance) · [python-binance.readthedocs.io](https://python-binance.readthedocs.io) | `pip install python-binance` | Binance-specific client for REST + WebSocket; covers spot, margin, USDS-M futures, COIN-M futures, options | supporting |
| **pybit** | [github.com/bybit-exchange/pybit](https://github.com/bybit-exchange/pybit) | `pip install pybit` | Official Bybit Python SDK; spot, perpetual, futures, options via REST + WebSocket | supporting |
| **deribit-api-python** | [github.com/deribit/deribit-api-python](https://github.com/deribit/deribit-api-python) | `pip install deribit-api` | Deribit options (BTC/ETH) via WebSocket — for crypto options analytics | crypto options |

#### Backtesting + Analytics + Risk

| Library | GitHub / Docs | PyPI | What it does | Confidence |
|---|---|---|---|---|
| **vectorbt** | [github.com/polakowo/vectorbt](https://github.com/polakowo/vectorbt) · [vectorbt.dev](https://vectorbt.dev) | `pip install vectorbt` | NumPy + Numba + Rust backtesting; win rate, profit factor, expectancy, Sharpe, Calmar, Omega, Sortino. ⚠️ MAE/MFE/R-multiples are PRO-only (paid) — implement custom | **3-0 HIGH** |
| **QuantStats** | [github.com/ranaroussi/quantstats](https://github.com/ranaroussi/quantstats) | `pip install quantstats` | `qs.reports.html(returns)` → full HTML tearsheet; Pandas 2.x compatible (v0.0.81) | **3-0 HIGH** |
| **Riskfolio-Lib** | [github.com/dcajasn/Riskfolio-Lib](https://github.com/dcajasn/Riskfolio-Lib) · [riskfolio-lib.readthedocs.io](https://riskfolio-lib.readthedocs.io) | `pip install riskfolio-lib` | CVaR, VaR, Entropic VaR, Kelly Criterion (Log Mean Risk), HRP, MVO portfolio optimization | **confirmed** |
| **PyPortfolioOpt** | [github.com/robertmartin8/PyPortfolioOpt](https://github.com/robertmartin8/PyPortfolioOpt) · [pyportfolioopt.readthedocs.io](https://pyportfolioopt.readthedocs.io) | `pip install PyPortfolioOpt` | Black-Litterman, Efficient Frontier, L2 regularization, mean-variance | supporting |
| **backtrader** | [github.com/mementum/backtrader](https://github.com/mementum/backtrader) · [backtrader.com](https://www.backtrader.com) | `pip install backtrader` | Event-driven backtesting; multi-data feeds; analyzers; observers | supporting |
| **pyfolio** | [github.com/quantopian/pyfolio](https://github.com/quantopian/pyfolio) | `pip install pyfolio` | Rolling Sharpe, underwater plot, position concentration tearsheet | supporting |
| **empyrical** | [github.com/quantopian/empyrical](https://github.com/quantopian/empyrical) | `pip install empyrical` | All standard risk metrics as standalone functions (Sharpe, Sortino, Calmar, max DD) | supporting |
| **pandas-ta** | [github.com/twopirllc/pandas-ta](https://github.com/twopirllc/pandas-ta) | `pip install pandas-ta` | 130+ technical indicators (superset of TA-Lib), all on pandas DataFrames | **reuse-first** |
| **ta-lib** (C) | [github.com/mrjbq7/ta-lib](https://github.com/mrjbq7/ta-lib) · [ta-lib.org](https://ta-lib.org) | `pip install TA-Lib` (needs C lib) | 150+ indicators, C core speed; fallback when pandas-ta missing | speed fallback |
| **mlfinlab** | [hudsonthames.org/mlfinlab](https://hudsonthames.org/mlfinlab/) | ❌ **ALL-RIGHTS-RESERVED COMMERCIAL** | ❌ **DO NOT USE** — not open source | **KILLED** |

#### UI / Charting

| Library | GitHub / Docs | Install | What it does |
|---|---|---|---|
| **TradingView Lightweight Charts v5** | [github.com/tradingview/lightweight-charts](https://github.com/tradingview/lightweight-charts) · [tradingview.github.io/lightweight-charts](https://tradingview.github.io/lightweight-charts/) | `npm install lightweight-charts` | OHLCV charts, dark theme, real-time streaming; MIT; the only chart library needed |
| **OrderFlowMap** | [github.com/Azhagesan-dev/OrderFlowMap](https://github.com/Azhagesan-dev/OrderFlowMap) | Clone + adapt | Canvas 2D Custom Series Primitives: HeatmapPrimitive, WallsPrimitive, BubblesPrimitive. ⚠️ Needs our custom WebSocket adapter for NSE/crypto feeds |
| **ChartForge** | [github.com/ShisMomin/chartforge](https://github.com/ShisMomin/chartforge) | Clone + adapt | Multi-chart layout + symbol/timeframe sync — steal the layout pattern |

#### Alerts

| Library | GitHub | PyPI | What it does |
|---|---|---|---|
| **python-telegram-bot** | [github.com/python-telegram-bot/python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) · [docs.python-telegram-bot.org](https://docs.python-telegram-bot.org) | `pip install python-telegram-bot` | Trade fills, P&L alerts, `/positions` `/pnl` `/kill` Telegram commands |
| **discord-webhook** | [github.com/lovvskillz/python-discord-webhook](https://github.com/lovvskillz/python-discord-webhook) | `pip install discord-webhook` | Signal alerts to Discord channels |
| **TradingView-Webhook-Bot** | [github.com/fabston/TradingView-Webhook-Bot](https://github.com/fabston/TradingView-Webhook-Bot) | Clone + adapt | Pattern reference for Telegram/Discord/Slack/Email alert dispatch from webhooks |
| **Trendoscope TV-Telegram Bot** | [github.com/trendoscope-algorithms/Tradingview-Telegram-Bot](https://github.com/trendoscope-algorithms/Tradingview-Telegram-Bot) | Clone + adapt | Alert → Telegram with current chart snapshot; steal the chart-snapshot pattern |

---

### ❌ KILLED — Do NOT Use

| Project | GitHub | Reason (adversarially verified) |
|---|---|---|
| **pyalgotrading** | [github.com/algobulls/pyalgotrading](https://github.com/algobulls/pyalgotrading) | Only documented for Alpaca (US) — zero public Indian broker connectors (2-1 confirmed) |
| **mlfinlab** | [hudsonthames.org/mlfinlab](https://hudsonthames.org/mlfinlab/) | **All-rights-reserved commercial license** — NOT open source; do not use |
| **freqtrade** | [github.com/freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | Crypto-only; no NSE/MCX support; no Indian broker connectors |
| **jesse** | [github.com/jesse-ai/jesse](https://github.com/jesse-ai/jesse) | Crypto-only; no NSE/MCX support |
| **hummingbot** | [github.com/hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | No options trading support anywhere in codebase (spot + perp only) |
| **nautilus_trader** | [github.com/nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | No Indian broker adapters; custom Rust adapter = months of work; no NSE/MCX |

### ⚠️ PARTIALLY USEFUL — Steal Patterns Only

| Project | GitHub | What to steal |
|---|---|---|
| **freqtrade** | [github.com/freqtrade/freqtrade](https://github.com/freqtrade/freqtrade) | Steal: strategy dry-run pattern, hyperopt, Telegram bot integration, REST API design |
| **jesse** | [github.com/jesse-ai/jesse](https://github.com/jesse-ai/jesse) | Steal: clean live/paper parity design, backtest debugger, DNA-style strategy config |
| **hummingbot** | [github.com/hummingbot/hummingbot](https://github.com/hummingbot/hummingbot) | Steal: market-making inventory skew, cross-exchange connector pattern |
| **nautilus_trader** | [github.com/nautechsystems/nautilus_trader](https://github.com/nautechsystems/nautilus_trader) | Steal: order lifecycle state machine design, event bus architecture |
| **OpenBB** | [github.com/OpenBB-finance/OpenBBTerminal](https://github.com/OpenBB-finance/OpenBBTerminal) | Steal: earnings, macro, options flow, dark pool prints data pipeline patterns |
| **Lumibot** | [github.com/Lumiwealth/lumibot](https://github.com/Lumiwealth/lumibot) | Steal: unified broker abstraction layer connector pattern |
| **buzz/algo_trading_india** | [github.com/buzzsubash/algo_trading_strategies_india](https://github.com/buzzsubash/algo_trading_strategies_india) | Reference: Zerodha 2FA automated login + token management + MTM square-off pattern |

---

## 3. System Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        REACT DASHBOARD (Dark Pro)                             │
│                                                                               │
│  ┌────────────────────────────────┐  ┌─────────────────────────────────────┐ │
│  │   NSE WINDOW (own tab/popup)   │  │  CRYPTO WINDOW (own tab/popup)      │ │
│  │  TradingView Charts v5         │  │  TradingView Charts v5               │ │
│  │  OrderFlowMap (heatmap/walls)  │  │  OrderFlowMap (heatmap/walls)        │ │
│  │  Options Chain + Greeks live   │  │  Funding rate + Liquidation price    │ │
│  │  GEX | Max Pain | IV Surface   │  │  L/S ratio | Fear & Greed            │ │
│  │  OI Heatmap | PCR | IV Rank    │  │  On-chain signals (SOPR/MVRV)        │ │
│  │  India VIX | FII/DII flows     │  │  Leverage selector + Margin mode     │ │
│  │  Watchlist (search + on/off)   │  │  Watchlist (search + on/off)         │ │
│  │  Open Trades (20 cols, live)   │  │  Open Trades (20 cols, live)         │ │
│  │  Closed Trades (85 cols)       │  │  Closed Trades (85 cols)             │ │
│  │  Trade Journal + Analytics     │  │  Trade Journal + Analytics           │ │
│  └───────────────┬────────────────┘  └──────────────┬──────────────────────┘ │
│                  │                                   │                         │
│  ┌───────────────▼───────────────────────────────────▼──────────────────────┐ │
│  │              BRAIN CONFIDENCE PANEL + STREAM-OF-MIND                     │ │
│  │  Per-symbol confidence scores (live, recalibrated vs realized P&L)       │ │
│  │  Brain's live thoughts (ephemeral TTL-fade feed)                         │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
└───────────────────────────────┬──────────────────────────┬────────────────────┘
                                │                          │
              ┌─────────────────▼──────────┐  ┌───────────▼──────────────────┐
              │     NSE ENGINE              │  │     CRYPTO ENGINE             │
              │  OpenAlgo Server            │  │  ccxt unified (Binance+Bybit) │
              │  (127.0.0.1:5000)           │  │  spot/perp/fut/options        │
              │  33 brokers unified         │  │  all leverage modes           │
              │  paper↔live single toggle   │  │  paper↔live single toggle    │
              │  auto-squareoff rules       │  │  funding rate monitor         │
              │  NSE/BSE/NFO/MCX/CDS       │  │  liquidation price calc        │
              └────────────┬───────────────┘  └───────────┬──────────────────┘
                           │                              │
              ┌────────────▼──────────────────────────────▼──────────────────┐
              │              ML NETWORK BRAIN (320-node network)              │
              │  Per-symbol confidence score (updated after each closed trade)│
              │  Regime classifier (trending/ranging/volatile) → strat select │
              │  Meta-labeling filter on signals                              │
              │  Auto-quiz self-testing (P4.4 — proves accuracy rises)        │
              └────────────┬──────────────────────────────┬──────────────────┘
                           │                              │
              ┌────────────▼──────────────┐  ┌───────────▼──────────────────┐
              │   NSE ANALYTICS            │  │   CRYPTO ANALYTICS            │
              │  fast-vollib Greeks        │  │  ccxt funding rates           │
              │  OpenBull options suite    │  │  Liquidation heatmap (API)    │
              │  (GEX/MaxPain/IV/OI)       │  │  L/S ratio feeds              │
              │  India VIX scrape          │  │  Fear & Greed Index           │
              │  FII/DII NSE API scrape    │  │  On-chain (SOPR/MVRV free API)│
              │  OI/PCR live (broker WS)   │  │  Basis tracking (spot-perp)   │
              │  Expiry calendar           │  │  Funding rate prediction       │
              └────────────┬──────────────┘  └───────────┬──────────────────┘
                           │                              │
              ┌────────────▼──────────────────────────────▼──────────────────┐
              │         TRADE MANAGEMENT + RISK LAYER                         │
              │  Custom MAE/MFE tracker (tick-by-tick, fills vectorbt gap)   │
              │  Exponential trailing SL (client-side WebSocket tick loop)    │
              │  ATR-based + Parabolic SAR + Chandelier Exit trailing         │
              │  Profit lock (move SL to BE after +X%, then trail)           │
              │  Partial profit booking (50% at T1, trail rest to T2)        │
              │  Scaling in (pyramiding) + Scaling out (partial exits)        │
              │  Re-entry logic (re-enter on next signal after stop-out)      │
              │  Riskfolio-Lib: VaR / CVaR / Kelly / HRP                     │
              │  Portfolio heat monitor (% capital at risk across all trades) │
              │  Correlation monitor (flag if too correlated = single bet)    │
              │  Daily loss circuit breaker (auto-flat all, halt trading)     │
              │  Margin utilization alert (auto-reduce at threshold)          │
              │  Beta-adjusted position sizing                                │
              │  Stress test: "what if Nifty drops 5% right now?"            │
              │  QuantStats tearsheet (daily auto-generated HTML + PDF)       │
              └────────────┬──────────────────────────────────────────────────┘
                           │
              ┌────────────▼──────────────────────────────────────────────────┐
              │              ALERTS LAYER                                      │
              │  python-telegram-bot: fills + P&L + /positions /pnl /kill    │
              │  Discord webhooks (signal alerts)                              │
              │  Email: daily tearsheet PDF                                    │
              │  Push notifications (Pushover/Firebase for mobile)            │
              │  Smart deduplication (no repeat alerts for same event)        │
              └────────────────────────────────────────────────────────────────┘
```

---

## 4. Open Trades Table — Dashboard (20 columns, real-time)

| Column | Description |
|---|---|
| Symbol | RELIANCE / BTCUSDT |
| Instrument Type | EQ / CE / PE / FUT / PERP / SPOT |
| Direction | LONG / SHORT |
| Qty / Lots | Shares or F&O lots or crypto qty |
| Entry Price | Actual fill price |
| Current Price | Live mark price |
| Unrealized P&L ₹/$ | Live, colour-coded green/red glow |
| Unrealized P&L % | % of margin used |
| MAE (₹) | Max loss reached so far |
| MAE Time | 🕐 Datetime MAE was hit |
| MFE (₹) | Max profit reached so far |
| MFE Time | 🕐 Datetime MFE was hit |
| Trailing SL Price | Current trailing SL (updates live) |
| Distance to SL | % gap between current price and trailing SL |
| Profit Lock Level | Where profit-lock triggered |
| Holding Time | HH:MM:SS since entry |
| Leverage | (Crypto only) 1× – 125× |
| Liquidation Price | (Crypto leveraged only) live |
| Funding Paid/Rcvd | (Crypto perp only) cumulative |
| Confidence Score | Brain's live confidence % for this symbol |
| Strategy Tag | Which strategy opened this |
| Status | OPEN / PARTIAL / TRAILING / LOCKED |

---

## 5. Closed Trades Table — Full Journal (85+ columns)

### Identity & Classification
- Trade ID, Broker Order ID (Entry), Broker Order ID (Exit)
- Symbol, Exchange (NSE/BSE/MCX/Binance/Bybit)
- Instrument Type (EQ/CE/PE/FUT/PERP/QUARTERLY/SPOT/OPT)
- Direction (LONG/SHORT), Product Type (MIS/CNC/NRML/MTF/MARGIN/CROSS/ISOLATED)
- Strategy Name, Setup Type (Breakout/Reversal/Momentum/Scalp/Swing/Hedge)
- Market Session, Broker Used

### F&O / Options Specific
- Underlying Symbol, Underlying Price at Entry, Underlying Price at Exit
- Expiry Date, Strike Price, Option Type (CE/PE), Lot Size, Number of Lots

### Execution Data
- Entry DateTime (ms precision), Exit DateTime (ms precision)
- Entry Price, Exit Price, Entry Order Type, Exit Order Type
- Intended Entry Price, Intended Exit Price
- Entry Slippage ₹, Exit Slippage ₹
- Partial Exits (JSON list: [{price, qty, time, reason}])

### P&L (Gross → Net)
- Gross P&L ₹
- STT ₹, Exchange Transaction Charges ₹, Brokerage ₹, GST on Brokerage ₹
- SEBI Charges ₹, Stamp Duty ₹, Other Charges ₹
- Total Charges ₹, **Net P&L ₹**, Net P&L %
- MTF Interest ₹ (overnight MTF cost)
- Funding Rate PnL ₹ (crypto perp — total funding collected/paid)
- Maker/Taker Fee ₹/$ (crypto exchange fee)
- Net P&L (Crypto) $ after all exchange fees + funding

### Risk & Sizing
- Margin Used ₹/$, Leverage Applied, Margin Mode (Cross/Isolated)
- Capital at Risk ₹ (initial SL distance × qty), Risk % of Portfolio
- Initial SL Price, Initial Target Price, Risk-Reward Ratio
- Kelly Fraction Used, Portfolio Heat at Entry
- Trailing SL Triggered (Yes/No), Profit Lock Triggered (Yes/No)

### Trade Quality Metrics
- MAE ₹, MAE Time, MAE %
- MFE ₹, MFE Time, MFE %
- Entry Efficiency % = (Exit − Entry) / (MFE − Entry) × 100
- Exit Efficiency %, R-Multiple (Net P&L / Initial Risk)
- Holding Duration (HH:MM:SS), Day of Week, Entry Hour

### Market Context at Entry
- India VIX at Entry (NSE only)
- Nifty Level at Entry (NSE stock trades — macro context)
- Market Regime at Entry (Trending/Ranging/Volatile/Crash — from Brain)
- Regime Confidence %, Volume at Entry, Relative Volume (vs 20-day avg)
- OI at Entry, OI Change %, Fear & Greed Index (Crypto)
- BTC Price at Entry (Crypto altcoins — macro context), Funding Rate at Entry
- Long/Short Ratio at Entry (Crypto)

### Options Greeks at Entry/Exit
- IV at Entry %, IV at Exit %, IV Rank at Entry, IV Percentile at Entry
- Delta, Gamma, Theta (per day), Vega, Rho — all at entry
- Delta at Exit, Total Theta Collected ₹

### Brain / AI Metadata
- Brain Confidence at Entry %, Brain Prediction (UP/DOWN/NEUTRAL)
- Brain Correct? (Yes/No — post-trade label)
- Node Contributions (JSON — which ML nodes drove the signal)
- Signal Source (which strategy/node triggered entry)

### Trade Behavior Flags
- Revenge Trade Flag (entered within 5 min of a loss)
- Overtrading Flag (beyond daily trade limit)
- Scaled In? (Yes/No), Scaled Out? (Yes/No)
- Rollover? (position rolled to next expiry), Corporate Action Impact

### User Annotations
- Notes (free text journal), Tags (user-defined)
- Mistake Type (FOMO/Early exit/Late entry/No SL/Sized too big)
- Lesson Learned (free text), Rating (1–5 stars — execution quality)

**Table features:** sortable + filterable by any column, column chooser (show/hide),
CSV/Excel export, click any row → drill-down single-trade view with chart replayed
showing entry/exit markers + MAE/MFE band.

---

## 6. Advanced Features Catalogue

### Market Microstructure
- Order Flow Imbalance (bid vs ask volume delta per tick)
- Volume Profile / Market Profile (POC, VAH, VAL, Initial Balance)
- VWAP + VWAP Bands (institutional reference price)
- L2 Order Book Depth (heatmap, bid-ask spread tracking, spoofing detection)
- Time & Sales tape (large block trade identification)
- Tick data replay at any speed (debugging + analysis)
- Footprint chart (per-candle buy/sell volume at each price level)

### NSE Options Intelligence
- Real-time Options Chain with Greeks refreshing every second
- IV Rank + IV Percentile (52-week range)
- IV Skew (put IV vs call IV by strike, term structure across expiries)
- Max Pain per expiry (price where most options expire worthless)
- Put-Call Ratio by OI and by volume (PCR-OI, PCR-VOL)
- OI Buildup / Unwinding (which strikes building vs liquidating)
- Gamma Exposure (GEX) — market maker hedging pressure zones
- Delta-neutral auto-hedge (auto-adjusts underlying to stay delta-neutral)
- Gamma Scalping (buy straddle near expiry, scalp the delta)
- Options Payoff Diagram (real-time mark-to-market P&L curve)
- Strategy Builder (Iron Condor, Butterfly, Straddle, Strangle, Calendar, Ratio)
- Probability of Profit (PoP) calculator per strategy
- Break-even auto-calculation on chart
- Theta decay clock (P&L curve vs time-to-expiry for each open position)
- Rollover tracker (near-month vs far-month OI ratio heading into expiry)

### NSE Market Intelligence
- India VIX live monitor + spike detection → auto-reduce risk
- FII/DII daily flows (NSE website scrape)
- Circuit Limit Monitor (auto-cancel if upper/lower circuit hit)
- T+1 Settlement Tracker (flag delivery obligation positions)
- SEBI Margin Rules (SPAN + Exposure margin check before order)
- Corporate Actions Calendar (dividends, splits, bonus, rights)
- NSE Announcements scraper (earnings, board meetings, bulk deals, insider)
- Bulk & Block Deals live feed
- F&O Ban List Monitor (auto-skip banned stocks)
- Expiry Week Seasonality (stats on Nifty/BankNifty Wed/Thu before expiry)
- Weekly vs Monthly Expiry dual calendar
- Rollover Cost tracking
- Synthetic Futures from options (when futures premium too high)
- STT + Brokerage Calculator (real P&L after all costs)

### Crypto Intelligence
- Funding Rate Monitor (live across Binance/Bybit/OKX)
- Funding Rate Farming detector (long spot + short perp → collect funding)
- Basis Trading (spot vs futures spread arbitrage)
- Cross-Exchange Arbitrage scanner (same pair, different CEX price gaps)
- Liquidation Heatmap (Coinglass API)
- Long/Short Ratio (exchange data → sentiment signal)
- OI % Change (OI spike = big money entering)
- Fear & Greed Index (auto-adjust risk exposure)
- Whale Alert (large on-chain transfers)
- On-chain Metrics (SOPR, MVRV, NVT via free Glassnode alternative APIs)
- Perpetual vs Quarterly Basis (term structure of futures)
- Mark Price vs Last Price deviation monitor (liquidation risk)
- Exchange Inflow/Outflow monitor (coins to/from exchanges = sell/buy signal)

### AI/ML Features (Brain Integration)
- Regime Classifier → auto-switch strategy (trending/ranging/volatile)
- Sentiment NLP on news headlines (FinBERT)
- Social Sentiment scraping (Reddit/Twitter/Telegram)
- Anomaly Detection (unusual volume, price gap, OI spike → alert)
- Online Learning (model updates after each completed trade)
- Multi-Armed Bandit (dynamic capital allocation to best strategies)
- Meta-Labeling (secondary classifier filters primary model's signals)
- Feature Importance (SHAP values → "why this trade")
- Confidence Score per symbol = Brain's P&L-calibrated probability

### Risk Management
- Portfolio VaR (Historical / Parametric / Monte Carlo, real-time)
- CVaR / Expected Shortfall
- Max Drawdown Circuit Breaker (auto-flat if drawdown > X%)
- Daily Loss Limit (hard stop, no trades rest of day)
- Correlation Monitor (alert if portfolio too correlated)
- Beta-Adjusted Position Sizing
- Kelly Criterion with fractional Kelly (0.25× default)
- Portfolio Heat (% capital at risk across all open trades)
- Sector Exposure Limits (max % in banking/IT/pharma etc.)
- Margin Utilization Alert (auto-reduce at threshold)
- Stress Test Panel ("what if Nifty drops 5% right now?")
- Scenario Analysis (COVID 2020, 2008 crisis, 2013 taper tantrum)

### Trade Management (Trailing)
- Exponential Profit Trailing SL (SL moves faster as profit grows)
- ATR-Based Trailing (N × ATR below price)
- Parabolic SAR Trailing (SL follows SAR dot)
- Chandelier Exit Trailing
- Volatility-Scaled SL (wider in high-vol, tighter in low-vol)
- Time-Based Exit (auto-exit X minutes before close/expiry)
- Profit Locking (move SL to breakeven after +X%)
- Partial Profit Booking (book 50% at T1, trail rest to T2)
- Re-entry Logic (re-enter on next signal if stopped out)
- Scaling In (pyramiding — add to position as it moves in favor)
- Scaling Out (reduce at multiple profit targets)

### Trade Journal Analytics
- Win Rate by: instrument, strategy, time of day, day of week, regime, expiry week
- Profit Factor = gross wins ÷ gross losses
- Expectancy = (win% × avg win) − (loss% × avg loss)
- Consecutive streak tracking (win/loss streaks, longest streak)
- Revenge Trade Detector (trade within 5 min of a loss → flagged)
- Overtrading Alert (> N trades/day)
- Monthly P&L heatmap (calendar view like QuantStats)
- Equity curve with drawdown underwater plot
- Performance by hour (best/worst trading hours)
- R-Multiple distribution histogram
- MAE/MFE scatter plot (entry/exit efficiency visualization)

### Automation & Alerts
- Telegram Bot: trade alerts, position updates, daily P&L summary, /kill command
- Discord Webhook: signal alerts
- WhatsApp (Twilio): critical alerts only
- Email digests: end-of-day summary + tearsheet
- Mobile Push: Pushover/Firebase
- Scheduled PDF Reports: daily/weekly auto-generated + emailed
- Smart Alert Deduplication: no spam for same event

---

## 7. Phased Build Plan

### Phase T1 — NSE Foundation (Weeks 1–2)
1. Install + configure **OpenAlgo server** (self-hosted at 127.0.0.1:5000)
2. Connect Zerodha + Upstox + Angel One via OpenAlgo broker config
3. Paper trading verified: place/cancel/modify orders via OpenAlgo REST
4. Instruments CSV download at startup (NSE F&O scripmaster: 50k+ instruments)
5. WebSocket tick feed → real-time price cache per symbol
6. Watchlist: search bar, add/remove symbols, persist to state
7. NSE on/off master toggle (when OFF = zero activity, no data polling)
8. Auto-squareoff rules enforced (NSE 15:15, MCX 23:30, CDS 16:45)
9. MTF interest calculator, circuit limit monitor, F&O ban list

### Phase T2 — Crypto Foundation (Weeks 2–3)
1. **ccxt** unified layer: Binance + Bybit spot/perp/quarterly/options
2. Leverage selector per trade, Cross vs Isolated margin toggle
3. Paper trading simulator (simulate fills against real orderbook via ccxt)
4. Crypto on/off master toggle
5. Funding rate monitor (live across Binance + Bybit perpetuals)
6. Liquidation price calculator per open leveraged position

### Phase T3 — Trade Execution Engine (Weeks 3–4)
1. Order lifecycle state machine: pending → partial → filled → cancelled
2. **Custom MAE/MFE tracker** (tick-by-tick loop — fills the vectorbt OSS gap)
3. **Exponential trailing SL** (client-side WebSocket tick loop — not server-side)
4. ATR / Parabolic SAR / Chandelier Exit trailing options
5. Profit lock (move SL to breakeven after +X% then trail)
6. Partial profit booking (50% at T1, trail rest to T2)
7. Daily loss circuit breaker (auto-flat all, halt rest of day)
8. SEBI SPAN + Exposure margin check before every NSE order
9. Bracket + cover orders for NSE intraday
10. Real-money safety kill-switch (single button → cancel all + flat all positions)

### Phase T4 — Options Intelligence (Weeks 4–5)
1. Steal + adapt **OpenBull** options analytics: /gex /maxpain /ivsmile /volsurface /oitracker /optiongreeks
2. Integrate **fast-vollib** (`get_all_greeks()` with Black-76 for MCX commodity options)
3. Live options chain table with Greeks refreshing every second
4. IV Rank + IV Percentile (52-week rolling calculation)
5. OI heatmap, PCR-OI, PCR-VOL per strike
6. Max Pain calculation per expiry (updated every tick)
7. GEX (Gamma Exposure) zones on chart
8. Options Payoff Diagram with real-time P&L curve

### Phase T5 — Brain Confidence + Analytics (Weeks 5–6)
1. Per-symbol confidence score wired to ML Network Brain
2. Recalibration loop: after each closed trade → update Brain's confidence estimate
3. **85-column closed trade journal** (all fields from Section 5)
4. Custom MAE/MFE/R-multiple computation on closed trades
5. Trade journal analytics: win rate by time/day/regime/instrument/strategy
6. Profit factor, expectancy, consecutive streak, R-multiple distribution
7. QuantStats HTML tearsheet auto-generated daily (+ PDF via weasyprint)
8. Revenge trade detector + overtrading alert

### Phase T6 — Dark Pro Dashboard (Weeks 6–7)
1. **TradingView Lightweight Charts v5** embedded (Dark theme)
2. **OrderFlowMap primitives** wired to NSE/crypto WebSocket adapters (custom adapter)
3. **NSE Window** as separate browser popup: chart + orderbook + options chain + trades
4. **Crypto Window** as separate browser popup: chart + funding rates + L/S ratio + trades
5. Live ticker tape (Nifty/BankNifty/BTC/ETH at top bar)
6. Open Trades panel (22 columns, real-time updates)
7. Closed Trades table (85+ columns, sortable/filterable/exportable)
8. Drill-down single-trade view (chart replay with entry/exit markers)
9. NSE India VIX panel, FII/DII flows panel
10. Brain Confidence Score heatmap (all watched symbols)
11. Stream-of-Mind panel (brain's live thoughts, TTL-fade from existing P4.2 code)

### Phase T7 — Alerts + Automation (Week 7–8)
1. **python-telegram-bot**: trade fills, daily P&L, /positions /pnl /kill commands
2. Discord webhooks for signal alerts
3. Email daily tearsheet (auto-generated + sent via SMTP)
4. Scheduled reports (daily/weekly PDF)
5. Smart alert deduplication

### Phase T8 — Advanced Intelligence (Weeks 8–10)
1. Sentiment NLP on news headlines (FinBERT, CPU-only ONNX)
2. FII/DII scraper (NSE website, scheduled daily)
3. NSE announcements scraper (earnings, bulk deals, corporate actions)
4. Crypto on-chain metrics (SOPR/MVRV via free CryptoQuant/Glassnode alternative APIs)
5. Liquidation Heatmap (Coinglass free API)
6. Cross-exchange arbitrage scanner (ccxt, Binance vs Bybit spread)
7. Funding rate farming detector
8. Riskfolio-Lib portfolio optimization (VaR/CVaR/Kelly/HRP)
9. Stress testing + scenario analysis panel

---

## 8. Critical Implementation Notes

1. **OpenAlgo is middleware, not a Python library** — a self-hosted server must run at
   `127.0.0.1:5000` before any order can be dispatched. Start it first; our system calls it via REST.

2. **Trailing SL must be client-side** — OpenAlgo/NSE brokers do not support server-side
   trailing stop order types for NFO options. We implement it as a WebSocket tick loop that
   fires a new SL-M order whenever the trailing condition is met.

3. **MAE/MFE must be custom-implemented** — vectorbt OSS does not include these
   (PRO-only). Implement as a tick-by-tick tracker: on each tick, compare current price
   against entry price, update running max/min and timestamp (~50 lines).

4. **OrderFlowMap needs a custom WebSocket adapter** — it is a pure visualization
   component with no broker wiring. Write a thin adapter that pipes NSE ticks from
   OpenAlgo WebSocket / ccxt WebSocket into its Canvas 2D primitives.

5. **fast-vollib is pre-1.0 (v0.1.6)** — keep `py_vollib_vectorized` as fallback. If
   fast-vollib breaks on a patch, swap in py_vollib_vectorized transparently.

6. **mlfinlab is commercial** — do not use. Implement triple-barrier labeling,
   fractional differentiation, and CPCV ourselves (~200 lines each, well-documented).

7. **Angel One requires TOTP** — `generateSession(username, pwd, pyotp.TOTP(secret).now())`.
   Store the TOTP secret in `.env`, never in code.

8. **MCX commodity options need Black-76** (not Black-Scholes) — fast-vollib covers this.
   Commodity futures options: Gold options, Crude options, Silver options on MCX.

9. **Secrets safe** — all API keys (Zerodha, Upstox, Angel One, Binance, Bybit, Telegram)
   in `.env` only, loaded via `config.py`. Never commit, print, or log keys.

10. **Multi-data rule** — every strategy and metric must be testable on NSE equities,
    NSE index options, MCX commodities, and crypto, per CONVENTIONS.md §14.

---

## 9. Dependencies to Request (ask-to-install, by phase)

### Phase T1–T2
```
pip install openalgo          # OpenAlgo Python client library
pip install kiteconnect       # pykiteconnect (Zerodha official)
pip install smartapi-python   # Angel One SmartAPI
pip install pyotp             # TOTP for Angel One 2FA
pip install ccxt              # Crypto unified exchange API
pip install websocket-client  # WebSocket connections
pip install aiohttp           # Async HTTP
```

### Phase T3–T4
```
pip install fast-vollib       # Options Greeks (Black-76, BSM, BS)
pip install py-vollib-vectorized  # Fallback Greeks
pip install pandas-ta         # 130+ technical indicators
```

### Phase T5
```
pip install vectorbt          # Backtesting + portfolio analytics
pip install quantstats        # HTML tearsheet generation
pip install riskfolio-lib     # VaR, CVaR, Kelly, HRP
pip install weasyprint        # PDF generation from HTML tearsheet
```

### Phase T7
```
pip install python-telegram-bot  # Telegram alerts
pip install discord-webhook      # Discord alerts
pip install requests             # Generic HTTP (alerts, scrapers)
```

### Phase T8
```
# FinBERT for sentiment (ONNX, CPU)
pip install transformers onnxruntime
pip install feedparser        # RSS news feeds
pip install pyperclip         # (optional) clipboard integration
```

---

## 10. Related Files
- `CONVENTIONS.md` — standing coding rules (reuse-first, honest-wiring, never-skip, etc.)
- `PROJECT_BRIEF.md` — ML Network Brain project goal and captured plans
- `ml-network-brain-ultra-blueprint.md` — Phase 4+ brain features (P4.1–P4.8)
- `ml-network-trainable-architecture.md` — DGMG trainable network (P3.5–P3.9)
- `nodes/gated_node.py` — P3.5 differentiable gate (built)
- `nodes/cascade_node.py` — P3.6 deep cascade (built)
- `core/chat_brain.py` — P4.1 brain chat with streaming (built)
- `dashboard/web/src/ChatPanel.jsx` — P4.1 dashboard chat panel (built)
- `dashboard/web/src/StreamOfMind.jsx` — P4.2 ephemeral thought panel (built)

---

*Research: 106 agents, 1.77M tokens, 2026-06-28. 18 claims confirmed 3-0 or 2-1;
7 claims killed 0-3 (pyalgotrading Indian brokers, mlfinlab OSS, freqtrade NSE,
jesse NSE, hummingbot options, OrderFlowMap NSE integration, vectorbt MAE/MFE OSS).*
