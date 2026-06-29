# NSE / MCX Screeners & Filters — OSS Research (ranked, cited)

> **Goal:** surface trade candidates across a wide, varied universe on NSE, **per segment**
> (Equity Intraday/MIS, MTF, F&O index+stock Options/Futures, MCX commodities), using filters like
> 52-week high/low, high-ATR movers, gainers/losers, unusual volume, OI build-up, PCR, IV rank,
> sector rotation, gap-ups/downs, breakouts.
>
> **App context:** we already trade NSE via the **OpenAlgo** server (Zerodha-backed, 128k-symbol
> master contract, REST quotes/depth/history). This report ranks OSS libraries/feeds that *add the
> screening layer* on top of (or alongside) the data we already fetch.
>
> Researched June 2026. pip availability verified against the project venv
> (`/home/karan18190164/.venv/bin/pip index versions <pkg>`).

---

## 0. TL;DR — Recommended stack (3 libs + what we already have)

| Layer | Library | Why |
|---|---|---|
| **OHLC / quotes / depth / OI / option-chain (live)** | **OpenAlgo** (we have it) + **`openalgo` py client** | Already wired; Zerodha master contract; REST quotes/depth/history; platform also exposes **option chain, Greeks, OI, vol-surface, GEX**. `openalgo` client also ships **100+ TA indicators (Rust core)** — covers most technical filters with zero extra deps. |
| **Pre-computed NSE screener feeds** (gainers/losers, most-active, 52w H/L, delivery%, bulk/block deals, FII/DII, **live option-chain → PCR/IV/max-pain**, sector indices, F&O participant OI) | **`nselib`** (primary) — Apache-2.0, actively maintained (v2.5.1, May 2026) | Single Apache-licensed lib that wraps almost every NSE "market-activity" + derivatives report we need for ready-made filter lists. No API key, CPU-only, pip-installable. |
| **Historical bhavcopy / EOD universe scans** (52-week range over full universe, F&O bhavcopy OI deltas, index history, MCX-adjacent EOD) | **`jugaad-data`** (537★, public-domain) + **`nsepython`** (357★, GPL-3.0) as fallback | jugaad-data = robust bhavcopy/EOD downloader (build your own 52w/RVOL scans offline); nsepython = broadest single-call helpers (PCR, max-pain, gainers, OI) but GPL-3.0. |
| **Technical filters on OHLC we already fetch** | **`pandas-ta-classic`** (pure-python, 284 indicators, no compile) — *use this, NOT `pandas-ta`* | `pandas-ta` is **NOT available on our pip index**; the maintained community fork `pandas-ta-classic` (v0.6.52) is. Gives ATR%, Bollinger width, ADX, RVOL, Donchian/52w-range, Supertrend. **TA-Lib (0.6.8) is also installable** if we want the C-speed version. |

> **Net:** `OpenAlgo (have) + nselib + jugaad-data + pandas-ta-classic` covers **every filter in every
> segment**. The only true gap is **MCX commodity screeners** — no good free NSE-style "MCX movers"
> feed exists; build MCX filters from **OpenAlgo/Kite MCX OHLC + pandas-ta-classic** (see §2.4, §4).

---

## 1. NSE data + screener libraries — ranked

Legend: ★ = GitHub stars (approx, mid-2026) · pip = installable on our venv index · key = needs API key · CPU = CPU-only.

### Tier 1 — recommended

#### 1a. `nselib` — **best single "screener feeds" library** ⭐ top pick
- **★** ~250 · **License: Apache-2.0** (permissive — safe to vendor/ship) · **pip ✓ (`nselib` 2.5.1, released May 2026 — actively maintained)** · **key: none** · **CPU ✓**
- PyPI: <https://pypi.org/project/nselib/>
- **Coverage (verified from PyPI 2.5.1 docs):**
  - **Capital market:** OHLCV, **delivery positions/%**, bhavcopy, **bulk & block deals**, short-selling, VaR margin, PE, **52-week high/low**.
  - **Derivatives (F&O / NFO):** futures & options pricing, **participant-wise Open Interest**, **live option chain**, FII derivative stats, **banned securities**.
  - **Market activity:** **top gainers/losers, most-active equities**, traded-stocks summary, **FII/DII activity**.
  - **Indices:** constituents + live performance for **Broad / Sectoral / Thematic / Strategy** (→ sector rotation).
  - **Extras:** India VIX history, holiday calendar, corporate actions.
- **Why #1:** one Apache-2.0 lib covers gainers/losers, most-active, 52w H/L, delivery%, bulk/block, F&O OI, option-chain, sector indices, FII/DII — i.e. almost all *ready-made filter lists* without hitting raw NSE JSON yourself.

#### 1b. `jugaad-data` — **best historical/bhavcopy downloader for offline universe scans**
- **★** ~537 · **License: "YOLO" (effectively public domain / do-anything)** · **pip ✓ (0.33.1)** · **key: none** · **CPU ✓** · actively maintained ("supports new NSE website", CI green)
- GitHub: <https://github.com/jugaad-py/jugaad-data> · PyPI: <https://pypi.org/project/jugaad-data/>
- **Coverage:** historical **stock EOD** (`stock_df`), **daily bhavcopy** + **F&O bhavcopy** (`bhavcopy_fo_save` → has OI columns), index & index-F&O history, **live quotes** via `NSELive`, option symbols (OPTSTK/OPTIDX).
- **Use it for:** building your own **52-week-range position, RVOL (volume vs 20-day avg), gap%, OI-delta** scans across the *full* universe from downloaded bhavcopies (no rate-limit pain — bhavcopy is a single daily file).

### Tier 2 — strong, single-call helpers

#### 1c. `nsepython` — broadest one-call helpers, but **GPL-3.0**
- **★** 357 · **License: GPL-3.0** (copyleft — fine for our *private, non-published* project per repo policy, but don't ship in a closed distributable) · **pip ✓ (2.97, May 2025)** · **key: none** · **CPU ✓**
- GitHub: <https://github.com/aeron7/nsepython> · server variant: `nsepythonserver` (cloud/Colab/AWS-friendly headers)
- **Coverage:** consolidates old `nsepy`+`nsetools`. Single calls for **option chain, PCR, max-pain**, gainers/losers, most-active, 52-week, **F&O OI**, bulk/block deals, sector indices, and some **MCX** helpers.
- **Note:** mirrors NSE site JSON, so subject to the same cookie/anti-bot handling (it bakes in browser headers). Use `nsepythonserver` on servers.

#### 1d. `nsetools` (v2.0.1) — lightweight, zero-dependency live quotes + gainers/losers
- **★** ~700 (long-standing) · **License: MIT** · **pip ✓ (2.0.1)** · **key: none** · **CPU ✓**
- GitHub: <https://github.com/vsjha18/nsetools> · PyPI: <https://pypi.org/project/nsetools/>
- **Coverage:** live quotes, all-index quotes (NIFTY/BANKNIFTY…), **top gainers/losers**, most-active, **future quotes** (expiry, premium, volatility). Pure stdlib, no deps. Narrower than nselib (no option-chain/bulk-deals), but MIT + tiny.

#### 1e. `nse` (deepak-net `nse` 3.1.0) — modern unofficial NSE API
- **★** ~150 · **License: MIT** · **pip ✓ (3.1.0)** · **CPU ✓** · PyPI: <https://pypi.org/project/nse/>
- Clean option-chain + market-report wrapper; good MIT alternative if you want to avoid nsepython's GPL.

### Tier 3 — adjacent / specific

| Library | ★ | License | pip | Role |
|---|---|---|---|---|
| **`openchart`** (marketcalls) | ~300 | **MIT** | ✓ (0.2.0) | NSE + **NFO** intraday & EOD **historical** downloader. MIT, clean. **MCX** is *not* in openchart itself but is in the sibling **Historify** app. <https://github.com/marketcalls/openchart> |
| **`yfinance`** (NSE `.NS`, indices `^NSEI`) | 18k+ | Apache-2.0 | ✓ (0.2.66+) | Backup OHLC + **52-week H/L fields**, sector via Yahoo. Good for *cross-check / off-hours*; NSE coverage is delayed & sometimes patchy. No bulk-deal/OI/option-PCR. |
| **`kiteconnect`** (Zerodha official) | ~900 | MIT | ✓ (5.2.0) | **key ✓** (Zerodha API). Authoritative **MCX + NFO + NSE** OHLC/quote/OI via the same broker OpenAlgo already uses. Historical data now **free with base subscription** (since Feb 2025). Best *raw* MCX/F&O data source if going under OpenAlgo. |
| **`breeze-connect`** (ICICI) | ~150 | MIT-ish | ✓ (1.0.69) | **key ✓** (ICICI Direct). Alt broker feed incl. option-chain/Greeks; only relevant if we add ICICI. |
| **`bsedata`** | ~250 | GPL-3.0 | ✓ (0.6.0) | BSE quotes/gainers/losers/52w — only if we extend to BSE. |
| **`nsepython2`** | — | — | ✓ (0.1.0, stub) | Ignore — early stub. |

### GitHub "stock screener" projects (NSE-specific, reusable code/patterns)

| Repo | ★ | License | pip | What it gives |
|---|---|---|---|---|
| **`pkjmesra/PKScreener`** | ~362 | **MIT** | ✓ `pip install pkscreener` (v0.46.*, **released June 2026**, very active) | **33+ built-in scanners**: 52-week breakouts (H/L), volume gainers/RVOL, **breakout/consolidation detection**, RSI, **ATR cross/trailing**, MA 50/200 crossovers, MACD, CCI, Aroon, chart patterns (VCP, H&S, double-top). Universe presets: Nifty 50/100/200/500, midcap/smallcap, **F&O stocks**. Data from NSE. **No OI filter, no MCX.** Great to *vendor as a filter engine*. <https://github.com/pkjmesra/PKScreener> |
| **`pranjal-joshi/Screeni-py`** | ~2k | GPL-3.0 | (app) | Breakout-probability + momentum-gainer patterns; configurable `.ini`. Predecessor/cousin of PKScreener. |
| **`rudradesai200/NSEStockScanner`** | small | — | (script) | Technical-basis NSE ticker scanner; reference patterns. |
| **`devangmukherjee/top-gainers-and-losers-nse`** | small | — | (script) | Daily top % movers → CSV with OHLC+volume; simple reusable pattern. |
| **`VarunS2002/Python-NSE-Option-Chain-Analyzer`** | ~600 | GPL-3.0 | (app) | Live option-chain analysis with **PCR graph + Max-Pain graph**, auto-refresh — reference for our IV/PCR/max-pain filter math. <https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer> |
| **`hi-imcodeman/stock-nse-india`** | ~600 | MIT | (Node) | Well-maintained NSE API incl. option-chain — reference for endpoint shapes. |

---

## 2. Per-segment mapping (which lib/feed covers what)

### 2.1 Equity Intraday (MIS / margin)
- **Movers / gainers-losers / most-active:** `nselib` (`top_gainers`, `top_losers`, most-active) or `nsetools`. Live.
- **Unusual volume (RVOL):** compute from `jugaad-data` bhavcopy (today vol ÷ 20-day avg) or OpenAlgo quotes.
- **52-week H/L:** `nselib` 52-week report (direct list) **or** compute from `jugaad-data` EOD history.
- **Gap-ups/downs:** today open vs prev close — OpenAlgo quote + prev-close from bhavcopy.
- **Breakouts / high-ATR:** `pandas-ta-classic` (ATR%, Donchian, Bollinger width) on OpenAlgo OHLC, **or** vendor PKScreener's scanners.
- **Delivery% (quality of move):** `nselib` delivery-position report.

### 2.2 MTF (Margin Trading Facility)
- **There is no single "MTF-eligible" OSS feed.** MTF-approved scrips are **broker/exchange lists** (Zerodha publishes its MTF list; NSE publishes the approved-securities circular).
- **Approach:** maintain the **MTF-eligible symbol list** (from the broker/NSE circular CSV) as a universe filter, then run the *same equity filters* (§2.1) restricted to that list. OpenAlgo master contract + a static MTF CSV = the practical solution. No library auto-fetches "MTF-eligible".

### 2.3 F&O (NFO — index + stock Options CE/PE & Futures)
- **Option chain (CE/PE, strikes, IV, OI):** `nselib` **live option chain** (primary, Apache-2.0); `nsepython` one-call `nse_optionchain_scrapper` (PCR/max-pain helpers); OpenAlgo platform also exposes **option chain + Greeks + OI + vol-surface + GEX** directly.
- **PCR (Put-Call Ratio):** `nsepython` returns PCR directly; else compute from `nselib`/OpenAlgo chain (ΣPE_OI / ΣCE_OI).
- **Max-pain:** `nsepython` helper / VarunS2002 analyzer math on the chain.
- **IV rank / IV percentile:** compute yourself — collect daily ATM IV (from chain) into a rolling series; IVR = (IV − 52w-min)/(52w-max − 52w-min). No lib ships IV-rank for NSE; chain IV comes from `nselib`/OpenAlgo, you store history.
- **OI build-up (long/short build-up, unwinding):** classify from **ΔOI vs ΔPrice** (price↑+OI↑=long build-up, price↓+OI↑=short build-up, etc.). Sources: `nselib` participant-wise OI + futures OI; `jugaad-data` **F&O bhavcopy** for day-over-day OI deltas across the whole F&O universe; OpenAlgo live OI.
- **Futures movers / basis:** futures quotes from `nsetools`/`nselib`/OpenAlgo.

### 2.4 Commodities — MCX (gold, silver, metals, crude oil, natural gas)
- **Key finding: no free NSE-style "MCX screener/movers" feed exists in OSS.** MCX's own site has weak/anti-bot JSON; `nsepython` claims some MCX helpers but coverage is thin/unreliable.
- **Best practical source = your broker via OpenAlgo / `kiteconnect`:** Kite Connect streams **MCX OHLC/quote/OI** (historical free since Feb 2025). OpenAlgo master contract includes MCX instruments → fetch OHLC/depth/OI through the pipe you already have.
- **Screeners for MCX = build them:** run `pandas-ta-classic` filters (ATR%, Bollinger width, RVOL, 52w-range, gap) on MCX OHLC fetched via OpenAlgo/Kite. Treat the MCX universe (GOLD, SILVER, CRUDEOIL, NATURALGAS, COPPER, ZINC, etc.) as a small fixed list and scan it like equities.
- **Supplementary global context (USD, not MCX prices):** `yfinance` (`GC=F`, `CL=F`, `NG=F`) or OilPriceAPI/commodity REST APIs for macro/cross-check only — not for MCX execution levels.

---

## 3. Technical-filter libraries (run on OHLC we already fetch)

| Library | ★ | License | pip | Notes |
|---|---|---|---|---|
| **`pandas-ta-classic`** ⭐ | (fork) | MIT | ✓ **0.6.52** | **USE THIS.** Maintained fork of pandas-ta (which is **NOT on our index**). 284 indicators, **pure-python, no C compile**, optional `numba` 6–230× speedup. CPU-only. <https://github.com/xgboosted/pandas-ta-classic> |
| **`TA-Lib`** | 10k+ | BSD | ✓ **0.6.8** | C-speed, 150+ indicators + candlestick patterns. Needs the TA-Lib C lib but the **0.6.x wheels install cleanly**. Use for hot-path / large-universe scans. |
| **`ta`** | ~4k | MIT | ✓ 0.11.0 | Pure-python, pandas-native, ~40 indicators. Simple, reliable fallback. |
| **`tsfresh`** | ~8k | MIT | ✓ 0.21.2 | Mass time-series **feature extraction** (100s of features) — for ML "volatile movement"/regime features, not simple thresholds. Heavier. |
| `pandas-ta-openbb` | — | MIT | ✓ 0.4.24 | NumPy-2/OpenBB fork; use only if inside OpenBB. |
| **OpenAlgo client built-in** | — | — | (have) | `openalgo` py ships **100+ indicators (Rust core via PyO3)** — may cover filters with zero extra install. |

### Filter → indicator recipe (per filter)
| Filter | Indicator(s) | Lib call |
|---|---|---|
| Volatile / high-ATR mover | **ATR%** = ATR(14)/Close·100; rank descending | `pandas-ta-classic.atr` / TA-Lib `ATR` |
| Volatility squeeze / expansion | **Bollinger Band width** = (upper−lower)/mid; Keltner squeeze | `bbands`, `kc` |
| Trend strength (filter chop) | **ADX(14)** > 25 | `adx` / TA-Lib `ADX` |
| 52-week-range position | (Close − 52w-low)/(52w-high − 52w-low); Donchian(252) | `donchian` + custom; or `nselib` 52w list |
| Unusual volume (RVOL) | Vol ÷ SMA(Vol,20); >2 = unusual | custom on `volume` + `sma` |
| Breakout | Close > Donchian/rolling-max(N); Supertrend flip | `donchian`, `supertrend` |
| Momentum / movers | ROC, RSI(14), MACD | `roc`, `rsi`, `macd` |
| Gap up/down | (Open−PrevClose)/PrevClose | custom |

---

## 4. Free / official sources & robustness notes

- **NSE market-data pages** (52w H/L, top-20 gainers/losers, most-active, bulk/block, FII/DII): `https://www.nseindia.com/market-data/...` — **wrapped robustly by `nselib`** (preferred over raw scraping).
- **NSE option-chain JSON:**
  - Indices: `https://www.nseindia.com/api/option-chain-indices?symbol=NIFTY`
  - Equities: `https://www.nseindia.com/api/option-chain-equities?symbol=RELIANCE`
  - **Anti-bot reality:** must first GET the main page to obtain a **session cookie**, send **browser-like headers**, and **throttle to ~3 req/s (≈3–4/min sustainable per IP)** or you get **403/CAPTCHA**. Prefer after-hours bulk pulls + 0.5–1 s sleeps. `nselib` / `nsepython` (esp. `nsepythonserver`) bake in the cookie+header dance — **use them instead of hand-rolling**.
- **MCX site:** weak/unreliable public JSON, aggressive anti-bot; **no robust OSS wrapper** → use **broker feed (OpenAlgo/Kite)** for MCX.
- **Zerodha Kite Connect:** authoritative NSE/NFO/**MCX** OHLC/OI; **historical free with base subscription since Feb 8 2025** — this is what sits under OpenAlgo, so we already have the cleanest path for F&O+MCX data.

---

## 5. RECOMMENDED stack — exact filter → data-source → library map

**Stack = OpenAlgo (have) + `nselib` + `jugaad-data` + `pandas-ta-classic`** (+ optional `nsepython`/`nsetools` for one-call helpers, `TA-Lib` for speed). All CPU-only, all pip-installable on our venv; only the broker feed needs a key (already configured).

| Segment | Filter | Data source | Library / call |
|---|---|---|---|
| **Equity Intraday** | Top gainers/losers | NSE market-activity | `nselib` top_gainers/top_losers (or `nsetools`) |
| | Most active | NSE | `nselib` most-active |
| | 52-week high/low | NSE 52w report **or** EOD hist | `nselib` 52w **/** `jugaad-data` `stock_df` |
| | Unusual volume (RVOL) | bhavcopy / quotes | `jugaad-data` bhavcopy + custom; OpenAlgo quote |
| | High-ATR / volatile | OHLC | `pandas-ta-classic.atr` (ATR%) on OpenAlgo OHLC |
| | Gap up/down | quote + prev close | OpenAlgo quote + bhavcopy prev-close |
| | Breakout | OHLC | `pandas-ta-classic` donchian/supertrend (or vendor **PKScreener**) |
| | Delivery% | NSE delivery report | `nselib` delivery positions |
| **MTF** | MTF-eligible universe | broker/NSE circular CSV (static) | maintain CSV list → then apply all Equity filters above |
| **F&O (NFO)** | Option chain (CE/PE, IV, OI) | NSE option-chain JSON | `nselib` live chain / OpenAlgo chain |
| | PCR | option chain | `nsepython` PCR / compute ΣPE_OI÷ΣCE_OI |
| | Max-pain | option chain | `nsepython` / VarunS2002 math |
| | IV rank / percentile | chain IV (stored daily) | compute (rolling 52w) — no lib ships it |
| | OI build-up (long/short) | F&O bhavcopy + live OI | `jugaad-data` `bhavcopy_fo_save` ΔOI; `nselib` participant OI; OpenAlgo OI |
| | Futures movers / basis | futures quotes | `nsetools`/`nselib`/OpenAlgo |
| **Sector rotation** (all) | Sector index performance | NSE sectoral indices | `nselib` indices (Sectoral/Thematic) |
| **Commodities (MCX)** | Movers / RVOL / ATR / 52w / gap / breakout | **MCX OHLC/OI via broker** | OpenAlgo/`kiteconnect` MCX OHLC → `pandas-ta-classic` filters (build the scan; no free MCX screener feed) |
| | Macro cross-check (USD) | Yahoo futures | `yfinance` GC=F/CL=F/NG=F (context only) |

### Install line
```bash
pip install nselib jugaad-data pandas-ta-classic   # core (Apache/PD/MIT, all on our index)
pip install nsepython nsetools                      # optional one-call PCR/max-pain/gainers helpers
pip install "TA-Lib==0.6.8"                          # optional C-speed indicators
# pip install pandas-ta   # ❌ NOT on our index — use pandas-ta-classic instead
```

### License posture (private, non-published project)
- **Permissive (safe anywhere):** `nselib` (Apache-2.0), `nsetools`/`nse`/`openchart`/`PKScreener` (MIT), `pandas-ta-classic`/`ta`/`tsfresh` (MIT), `jugaad-data` (public-domain).
- **GPL-3.0 (fine for our internal use, avoid in any closed redistributable):** `nsepython`, `bsedata`, `Screeni-py`, `Python-NSE-Option-Chain-Analyzer`.

### Known gaps / cautions
1. **MCX screeners** — no ready OSS feed; must be built on broker OHLC (covered above).
2. **MTF-eligible list** — broker/exchange circular, not a library; maintain as static CSV.
3. **IV rank** — no NSE lib ships it; we store daily ATM IV and compute the rank ourselves.
4. **NSE direct-JSON libs** (`nsepython`, raw endpoints) — rate-limited/anti-bot; prefer `nselib` wrappers + throttle, or pull through OpenAlgo/broker where possible.

---

### Primary sources
- nselib — <https://pypi.org/project/nselib/>
- jugaad-data — <https://github.com/jugaad-py/jugaad-data> · <https://pypi.org/project/jugaad-data/>
- nsepython — <https://github.com/aeron7/nsepython> · <https://pypi.org/project/nsepython/>
- nsetools — <https://github.com/vsjha18/nsetools> · <https://pypi.org/project/nsetools/>
- openchart — <https://github.com/marketcalls/openchart>
- OpenAlgo — <https://github.com/marketcalls/openalgo> · <https://docs.openalgo.in/trading-platform/python> · <https://pypi.org/project/openalgo/>
- PKScreener — <https://github.com/pkjmesra/PKScreener>
- Screeni-py — <https://github.com/pranjal-joshi/Screeni-py>
- NSE Option-Chain Analyzer (PCR/max-pain ref) — <https://github.com/VarunS2002/Python-NSE-Option-Chain-Analyzer>
- pandas-ta-classic — <https://github.com/xgboosted/pandas-ta-classic> · <https://pypi.org/project/pandas-ta-classic/>
- TA-Lib — <https://ta-lib.org/> · NSE 52w H/L page — <https://www.nseindia.com/market-data/52-week-high-equity-market>
- Kite Connect (free historical since Feb 2025) — <https://kite.trade/docs/connect/v3/market-quotes/>

---

## Exhaustive NSE Filter Catalog (every criterion)

> **Purpose:** the *complete* universe of filter/screener criteria you could ever screen NSE equity / F&O /
> MCX on — merged from the full filter sets of **Screener.in, Chartink, Trendlyne, Tickertape, StockEdge,
> TradingView (India), Investing.com, MoneyControl, NSE.com**, plus options analytics (**Sensibull, Opstra,
> Quantsapp**) and commodity/macro sources (**MCX, CFTC COT, EIA**). Researched June 2026.
>
> **"Our stack" = what we already have/installable:** OpenAlgo (quotes/depth/history/**option-chain+Greeks+OI+GEX**)
> + `nselib` (NSE market-activity & derivative reports) + `jugaad-data` (bhavcopy/EOD + F&O bhavcopy OI) +
> `pandas-ta-classic` (284 indicators) + optional `nsepython`/`nsetools` (one-call PCR/max-pain/gainers) +
> `TA-Lib` (C-speed + candlestick patterns).
>
> **Capability legend (per-filter column):**
> - **✅ Now** — computable today from data our stack already returns.
> - **🟡 Store** — computable, but we must *collect & persist a daily history* first (IV rank, delivery-spike
>   trend, OI-delta series, rollover %, momentum scores). No new vendor; just a local time-series.
> - **🔴 Extra** — needs an **external data source** our stack does not provide (analyst ratings/estimates, news
>   sentiment, MTF-eligible list, Piotroski-grade fundamentals beyond bhavcopy, CFTC COT, EIA inventories,
>   credit-rating changes, super-investor holdings).

### Coverage note (platform → strength)
- **Screener.in** = deepest *fundamentals* query engine (ratios/growth/shareholding/cash-flow/Piotroski; thin technicals).
- **Chartink** = deepest *technical/price-action* scan builder (all indicators + candlestick/chart patterns + Heikin-Ashi + intraday; 50k+ community scans; thin fundamentals).
- **Trendlyne** = broadest overall (1000+ params + DVM/Checklist/SWOT proprietary scores + SmartOptions F&O + analyst Forecaster).
- **Tickertape** = 200+ filters incl. quant set (Alpha/Sharpe/Volatility-vs-Nifty, premium-vs-sector valuation, proprietary Ranks).
- **StockEdge** = 506 ready scans + combination scans; richest candlestick (24)/Ichimoku/NR4-NR7 + F&O long-short buildup (8-tier "aggressive").
- **TradingView (India)** = 1,118 fields, every indicator with timeframe selector + full named candlestick-pattern column.
- **Investing.com** = 160+ filters across 11 tabs (Piotroski, dividend-streak, realized-vol).
- **MoneyControl / NSE.com** = ready-made market-statistics screens (movers, circuits, shockers, OI quadrants, delivery, bulk/block, advance-decline).

---

### 1. PRICE / PERFORMANCE

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **52-week high / low** (new H/L, near H/L) | breakout/breakdown extremes | all 9 | ✅ Now (`nselib` 52w list / OpenAlgo OHLC) |
| **% from 52-week high** / **% from 52-week low** | proximity to extreme (e.g. 10–30% below 52wH) | Screener, Chartink, Trendlyne, Tickertape, StockEdge, TV, Investing, MC | ✅ Now (compute from EOD) |
| **All-time high / low** (proximity, crossing/entering zone) | lifetime extremes | Chartink, StockEdge, TV, MC | 🟡 Store (need full price history) |
| **Period high/low** (1m/3m/6m/N-day) | shorter-range extremes | Chartink, StockEdge, TV | ✅ Now (rolling max/min) |
| **2-year / 5-year high-low breakout zones** | medium-horizon breakout | StockEdge | 🟡 Store |
| **Returns 1D / 1W / 1M / 3M / 6M / 1Y** | momentum over horizon | all (TV adds 5Y/All-time; SE adds 2Y) | ✅ Now |
| **YTD return** | calendar-year momentum | Screener, Trendlyne, TV, Investing, MC | ✅ Now |
| **Return vs Nifty / benchmark / sector** | relative strength | Tickertape, StockEdge (RS 21D/55D/21W, adaptive vs static), Trendlyne | ✅ Now (compute vs index OHLC) |
| **Stock CAGR** (1/3/5/10y) | long-horizon compounding | Screener, Tickertape | ✅ Now (need multi-yr EOD) |
| **Gap up / gap down %** (open vs prev close) | overnight gaps | Chartink, Trendlyne, TV, MC; NSE pre-open (IEP) | ✅ Now (OpenAlgo open + bhavcopy prev-close) |
| **Upper / lower circuit** (only-buyers/sellers, price-band hitters) | locked moves | Chartink, Trendlyne, MoneyControl, NSE | ✅ Now (`nselib`/NSE band-hitters) |
| **Price range (min/max), face value** | universe scoping | all | ✅ Now |
| **Near breakout / breakdown of S-R** | pre-breakout setup | Chartink, Trendlyne, StockEdge | ✅ Now (`pandas-ta-classic` donchian/pivots) |
| **Consolidation / range-bound (NR4 / NR7)** | range contraction | Chartink, Trendlyne, StockEdge (NR4/NR7) | ✅ Now (custom range math) |
| **VWAP-relative price** (above/below/crossing) | intraday fair-value | Chartink, Trendlyne, Tickertape, StockEdge | ✅ Now (intraday OHLCV) |
| **Pivot-relative price** (Classic/Fib/Camarilla/Woodie/DeMark) | pivot S-R | Chartink, TV, MoneyControl | ✅ Now (`pandas-ta-classic`) |
| **Higher-highs / lower-lows multi-day structure** | trend structure | StockEdge | ✅ Now (custom) |
| **Top gainers / losers (NSE & BSE)** | daily movers | Trendlyne, StockEdge, MoneyControl, NSE | ✅ Now (`nselib`/`nsetools`) |
| **Fall-from-intraday-high / recovery-from-low** | intraday reversal | MoneyControl | ✅ Now (intraday OHLC) |
| **Price shockers** | abnormal price jump | MoneyControl | ✅ Now |

### 2. VOLUME / LIQUIDITY

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Daily volume / traded qty** | activity | all | ✅ Now |
| **Average volume** (10/30/60/90d, 1M/3M) | baseline liquidity | Trendlyne, Tickertape, TV, Investing, MC | ✅ Now |
| **Relative Volume (RVOL)** (vs avg, vs same-time) | unusual participation | Chartink, Trendlyne, Tickertape, TV | ✅ Now (vol ÷ SMA(vol,N)) |
| **Volume spike / shocker / spurt** | sudden surge | Chartink, Trendlyne, StockEdge, MoneyControl, NSE (Top-25 spurts) | ✅ Now |
| **% change in volume (1D/1W)** | volume momentum | Trendlyne, Tickertape, StockEdge | ✅ Now |
| **Avg traded value / turnover (Value×Volume)** | rupee liquidity | StockEdge, TV, MoneyControl, NSE | ✅ Now |
| **Most active by value / by volume / by trades** | liquidity leaders | MoneyControl, NSE, `nselib` | ✅ Now |
| **Delivery volume % / delivery spike** | conviction of move | Trendlyne, StockEdge (daily/wk/mo), MoneyControl, NSE (MTO) | ✅ Now (`nselib` delivery report); 🟡 Store for *spike-trend* |
| **Buyer/seller-initiated trade qty, buy/sell ratio** | order-flow tilt | Chartink (trade book) | 🔴 Extra (needs tick/trade-book feed) |
| **Order book (orders, buy/sell orders)** | depth imbalance | Chartink | 🟡 OpenAlgo depth (top-5) — partial |
| **Bulk deals / block deals** (+FII/MF/DII filter) | large-investor activity | Trendlyne, Tickertape, StockEdge, MoneyControl, NSE | ✅ Now (`nselib` bulk/block) |
| **Low-price-high-volume** | penny-momentum | MoneyControl | ✅ Now |
| **Money Flow Index (MFI) / PVT / OBV / AD-line** | volume-weighted momentum | Chartink, Trendlyne, Tickertape (OBV/AD 1W), StockEdge | ✅ Now (`pandas-ta-classic`) |

### 3. VOLATILITY / MOMENTUM / TECHNICAL

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **ATR / ATR%** | volatility / over-extension | Chartink, Trendlyne, StockEdge, TV, Investing | ✅ Now (`pandas-ta-classic.atr`) |
| **Bollinger Bands** (upper/lower/basis, width, squeeze, %from) | vol expansion/contraction | all technical platforms | ✅ Now (`bbands`) |
| **Keltner / Donchian channels** | squeeze / breakout | Chartink, TV | ✅ Now (`kc`, `donchian`) |
| **ADX / DMI (+DI/−DI)** | trend strength | Chartink, Trendlyne, StockEdge, TV (9/20/50/100), Investing; Tickertape (ADX-rating) | ✅ Now (`adx`) |
| **RSI** (14/7, weekly, exponential) | over/under-bought | all | ✅ Now (`rsi`) |
| **MACD** (line/signal/histogram, cross) | momentum cross | all | ✅ Now (`macd`) |
| **Stochastic** %K/%D (multi-preset) + **Stoch RSI** | momentum oscillator | all | ✅ Now (`stoch`, `stochrsi`) |
| **CCI** | cyclical extremes | Chartink, Trendlyne, StockEdge, TV, Investing, MC | ✅ Now (`cci`) |
| **Williams %R** | over/under-bought | Tickertape, StockEdge, TV, Investing, MC | ✅ Now (`willr`) |
| **Awesome Oscillator / Ultimate Osc / Bull-Bear Power / Momentum / ROC** | extra oscillators | TV, Investing, StockEdge (ROC) | ✅ Now (`ao`,`uo`,`mom`,`roc`) |
| **Moving averages SMA & EMA** (5/10/20/30/50/100/200 + many) | trend / dynamic S-R | all | ✅ Now (`sma`,`ema`) |
| **MA crossovers** (price-MA, MA-MA, golden cross 50×200, death cross) | trend shift | all technical platforms | ✅ Now |
| **Hull MA / VWMA / WMA / TMA** | smoothed trend | Chartink (WMA/TMA), TV (Hull/VWMA) | ✅ Now (`hma`,`vwma`,`wma`) |
| **Supertrend** (+ weekly) | trend-following flip | Chartink, Trendlyne, Tickertape, StockEdge | ✅ Now (`supertrend`) |
| **Parabolic SAR** (+ weekly) | trailing reversal | Chartink, Tickertape, StockEdge, TV | ✅ Now (`psar`) |
| **Ichimoku** (Tenkan/Kijun/Span A-B/Chikou/cloud) | full trend system | Chartink, Trendlyne, StockEdge (14 scans), TV | ✅ Now (`ichimoku`) |
| **Pivot points** (5 systems) | S-R levels | Chartink, TV, MoneyControl | ✅ Now |
| **Heikin-Ashi** (HA-OHLC) | smoothed candles | Chartink | ✅ Now (custom) |
| **Beta** (vs benchmark & vs sector) | systematic risk | Screener, Trendlyne, Tickertape, StockEdge, TV (1Y), Investing | ✅ Now (compute vs index) |
| **Alpha / Sharpe / realized volatility / volatility-vs-Nifty / 1Y max loss** | risk-adjusted return | Tickertape, Investing (realized vol) | ✅ Now (compute from returns) |
| **Candlestick patterns** (Doji, Hammer, Engulfing, Harami, Morning/Evening Star, Marubozu, Shooting Star, 3 White Soldiers/Black Crows, Tweezer, Tasuki, Abandoned Baby, etc.) | reversal/continuation | Chartink, Trendlyne, StockEdge (24), TV (full named column) | ✅ Now (**TA-Lib** 60+ CDL patterns) |
| **Chart patterns** (cup&handle, flag, triangle, H&S, double-top, VCP, inside-bar, NR7) | classical patterns | Chartink, Trendlyne, vendored **PKScreener** | ✅ Now (PKScreener scanners / custom) |
| **Darvas box** | box breakout | Chartink | ✅ Now (Max/Min box) |
| **Technical Rating** (overall Buy/Sell, MA-rating, Osc-rating) | composite signal | TV, Investing, MoneyControl | ✅ Now (replicate aggregation) |
| **DVM Momentum / Momentum Score / Price-Momentum Rank** | proprietary momentum | Trendlyne (DVM), StockEdge (1M/3M/6M), Tickertape | 🟡 Store (build composite + percentile history) |

### 4. FUNDAMENTAL

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Market cap** (+ nano/micro/small/mid/large/mega tiers) | size | all | ✅ Now (price × shares; tiers from master) |
| **P/E, P/B, P/S, PEG, EV/EBITDA, EV/Sales, P/FCF, P/CFO, earnings yield, FCF yield** | valuation | Screener, Trendlyne, Tickertape (deep), TV, Investing, MC | 🔴 Extra (need fundamentals feed; `nselib` has PE only) |
| **Premium-vs-sector** (PE/PB/PS vs sector & sub-sector) | relative valuation | Tickertape, StockEdge | 🔴 Extra |
| **ROE / ROCE / ROA / ROIC / RONW** (+ 3/5/10y avg, consistency) | returns on capital | Screener, Trendlyne, Tickertape, StockEdge, TV, Investing, MC | 🔴 Extra |
| **Margins** (gross/operating/OPM/EBITDA/net/pretax/FCF, + 5y avg) | profitability | Screener, Tickertape, StockEdge, TV, Investing, MC | 🔴 Extra |
| **Sales/revenue growth** (QoQ, YoY, 3/5/7/10y, highest-in-10y) | top-line growth | Screener, Trendlyne, Tickertape, StockEdge, TV, Investing, MC | 🔴 Extra |
| **Profit / EBITDA / EPS growth** (QoQ, YoY, 5y, turnaround) | bottom-line growth | all fundamental platforms | 🔴 Extra |
| **EPS** (quarter/TTM/annual, forward) | earnings | Screener, Trendlyne, Tickertape, TV, Investing, MC | 🔴 Extra |
| **Debt/equity, LT-debt/equity, interest coverage, current/quick ratio, debt/EBITDA** | leverage/liquidity | all fundamental platforms | 🔴 Extra |
| **Efficiency** (asset/inventory/receivable turnover, DIO/DSO/DPO, cash-conversion-cycle, working-capital days) | operational efficiency | Screener, Tickertape, StockEdge, Investing | 🔴 Extra |
| **Cash flow** (CFO/FCF growth & consistency, P/CFO, P/FCF) | cash generation | Screener, Trendlyne, Tickertape, StockEdge, TV, Investing | 🔴 Extra |
| **Dividend** (yield, DPS, payout, 3/5y growth, payment streak) | income | all | 🔴 Extra (NSE corp-actions give events; ratios need feed) |
| **Promoter holding %** (+ QoQ change, foreign promoter, consistency) | ownership | Screener, Trendlyne, Tickertape, StockEdge, MC | ✅ Now (`nselib`/NSE shareholding); 🟡 Store for *change* |
| **Promoter pledge %** (+ change, 6 buckets) | pledge risk | Screener, Trendlyne, Tickertape, StockEdge (richest), MC | ✅ Now (NSE pledge disclosures) |
| **FII/FPI holding** (+ QoQ change, consistency) | foreign flows | Screener, Trendlyne, Tickertape, StockEdge, MC | ✅ Now (NSE shareholding); 🟡 Store for change |
| **DII / MF / insurance / retail / institutional holding** (+ change) | domestic flows | Screener, Trendlyne, Tickertape, StockEdge, MC | ✅ Now (shareholding pattern) |
| **Number of shareholders** (+ change) | ownership breadth | Screener, Tickertape | 🔴 Extra |
| **Piotroski F-score** | 9-pt quality | Screener (native), Trendlyne (native), Investing, Tickertape (custom) | 🔴 Extra (needs 9 fundamental inputs) |
| **Altman Z / Graham number / intrinsic value / DCF** | bankruptcy/value | Screener (custom ratios) | 🔴 Extra |
| **Proprietary quality scores** (Trendlyne Durability/Checklist/SWOT, Tickertape Fundamental Score / Earnings-Quality Rank, StockEdge Fundamental Score) | composite quality | Trendlyne, Tickertape, StockEdge | 🔴 Extra |
| **Sector / industry classification** | thematic scoping | all | ✅ Now (master contract / `nselib` indices) |

### 5. F&O / DERIVATIVES

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Open Interest (abs) + OI change %** (call/put/total, prev-day, cumulative) | positioning size | Trendlyne, StockEdge, Quantsapp, MoneyControl, NSE | ✅ Now (OpenAlgo/`nselib` OI; `jugaad-data` F&O bhavcopy) |
| **OI buildup** (long buildup / short buildup / long unwinding / short covering) | price×OI direction | StockEdge (8-tier aggressive), Trendlyne, Sensibull, Opstra, Quantsapp | ✅ Now (ΔPrice vs ΔOI logic) |
| **OI spurts / exceptional OI change** | sudden positioning | StockEdge, Quantsapp, NSE | 🟡 Store (need OI vs avg-OI series) |
| **PCR (OI-based)** = ΣPutOI/ΣCallOI | sentiment | Trendlyne, StockEdge, Sensibull, Opstra, Quantsapp | ✅ Now (`nsepython` / compute from chain) |
| **PCR (volume-based)** | sentiment (flow) | Trendlyne, Sensibull, Quantsapp | ✅ Now (per-strike volume from chain) |
| **Implied Volatility (IV)** per strike | option richness | Sensibull, Opstra, Quantsapp; Trendlyne (IV rise/fall) | ✅ Now (OpenAlgo Greeks/vol-surface, else solve Black-76) |
| **IV Rank / IV Percentile** | IV regime | Opstra (IVR), Sensibull/Quantsapp (IVP) | 🟡 Store (need 252-day IV history) |
| **IV vs HV / realized vol, skew, surface, term-structure, vol-cone** | vol structure | Opstra (most), Quantsapp | ✅ Now skew/HV; 🟡 Store for IVR-type history |
| **Max pain** | expiry magnet strike | Sensibull, Opstra, Quantsapp | ✅ Now (`nsepython` / compute from chain) |
| **Option Greeks** (Delta/Gamma/Theta/Vega/Rho) | risk sensitivities | Sensibull, Opstra, Quantsapp | ✅ Now (OpenAlgo Greeks, else Black-76) |
| **Probability of profit / expected move / ATM straddle price** | trade geometry | Sensibull, Opstra, Quantsapp | ✅ Now (from chain + IV/DTE) |
| **Futures basis / premium-discount, annualized basis, cost of carry** | spot-future spread | Trendlyne, StockEdge, Tickertape, Quantsapp | ✅ Now (spot + future) |
| **Rollover % / rollover cost** (+ vs 3M avg) | expiry carry | Trendlyne, StockEdge, Tickertape, Opstra, Quantsapp | 🟡 Store (need 2-month OI over roll window) |
| **Participant-wise OI** (FII/DII/Pro/Client × index/stock fut+opt, long/short/net + change) | smart-money positioning | Trendlyne (deepest), StockEdge, Quantsapp | ✅ Now (`nselib` participant-wise OI) |
| **FII/DII cash & F&O flow activity** | flows | Sensibull, Opstra, Quantsapp, Trendlyne, MoneyControl, NSE | ✅ Now (`nselib` FII/DII) |
| **Strike-wise OI walls / S-R, ΔOI by strike, OI gainers-losers** | chain S-R | StockEdge, Trendlyne, Sensibull, Opstra, Quantsapp, NSE | ✅ Now (option chain) |
| **Days to expiry (DTE)** | time decay window | all options platforms | ✅ Now (expiry calendar) |
| **Futures/options volume, most-active contracts** | liquidity | Trendlyne, StockEdge, Quantsapp, MoneyControl, NSE | ✅ Now |
| **F&O ban list + MWPL %** | position-limit risk | StockEdge, Opstra, Quantsapp, Trendlyne, NSE | ✅ Now (`nselib` banned securities; MWPL from NSE) |
| **Long/short ratio** | aggregate tilt | Trendlyne, StockEdge, Quantsapp | ✅ Now (participant data) |
| **OI×Price quadrant matrix, active calls/puts, futures-spot arbitrage, sector-wise OI** | derivative dashboards | MoneyControl, Quantsapp, Opstra | ✅ Now (compute from OI+price) |

### 6. CORPORATE / EVENTS

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Results / earnings date** (forthcoming) | event timing | Trendlyne, StockEdge, TV, Investing, NSE | ✅ Now (NSE board-meetings/results calendar) |
| **Dividends / bonus / splits / rights** (forthcoming, ex/record dates) | corporate actions | Trendlyne, StockEdge, NSE, MC | ✅ Now (NSE corporate-actions, `nselib`) |
| **Insider trades (PIT/SAST)** (+ cumulative 1M/3M/6M) | insider activity | Trendlyne, Tickertape, StockEdge, NSE | ✅ Now (NSE PIT filings) |
| **Credit-rating changes** | balance-sheet signal | Trendlyne (events feed), StockEdge | 🔴 Extra (rating-agency feed) |
| **Index inclusion / exclusion** | passive-flow event | Trendlyne, StockEdge, NSE | 🔴 Extra (index-review announcements) |
| **Upcoming IPO / issues** (price band, lot, listing date) | new listings | NSE, MoneyControl | ✅ Now (NSE upcoming-issues) |
| **SLBS (securities lending/borrowing)** | borrow demand | NSE | ✅ Now (NSE SLBS report) |
| **52w-high streak / new-high-new-low counts** | breadth-of-extremes | NSE, MoneyControl | ✅ Now |

### 7. SECTOR / THEMATIC / SENTIMENT

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Sector / index scoping of any screen** (Nifty 50/100/200/500, midcap, F&O universe) | universe filter | all | ✅ Now (`nselib` index constituents) |
| **Sector rotation / sectoral-index performance** | which sectors lead | Trendlyne, StockEdge, MoneyControl (sector scan/weightage), NSE | ✅ Now (`nselib` sectoral/thematic/strategy indices) |
| **Sector relative strength (stock vs sector index)** | leaders within sector | StockEdge (extensive RS scans), Trendlyne | ✅ Now (compute vs sector index) |
| **Advance / decline & market breadth** | market internals | Trendlyne, MoneyControl, NSE (cap-market snapshot) | ✅ Now (`nselib`/NSE) |
| **Increase / decrease in market cap** | cap movers | MoneyControl, NSE | ✅ Now |
| **Analyst ratings / targets / upgrades-downgrades / % upside** | sell-side view | Trendlyne (Forecaster), Tickertape (broker ratings), TV, Investing | 🔴 Extra (estimates feed) |
| **News sentiment** | qualitative tone | Trendlyne, StockEdge (news dashboard) | 🔴 Extra (news/NLP feed) |
| **Super-investor / superstar / bulk-deal holdings** | follow-the-whales | Trendlyne, StockEdge | 🔴 Extra (curated holdings DB) |
| **Thematic baskets** | theme exposure | Trendlyne, Tickertape, StockEdge | 🟡 Store (build basket lists) |
| **Top dividend yields, arbitrage opportunities** | yield/arb screens | MoneyControl | ✅ Now (yield from corp-actions; arb from fut-spot) |

### 8. COMMODITY / MCX VARIANTS

| Filter | What it screens | Platforms | Our stack |
|---|---|---|---|
| **Contango / backwardation** (curve shape, ratio future/spot) | carry regime | computed (no native NSE-style screener) | ✅ Now (≥2 contract months via OpenAlgo/Kite MCX) |
| **Near-far calendar spread** (abs, %, rolling Z-score) | curve mean-reversion | computed; Opstra-style spread tools | 🟡 Store (need spread history for Z) |
| **Curve slope / steepening-flattening** (3+ months) | term-structure trend | computed | 🟡 Store |
| **Commodity OI + OI change** (abs/%, cumulative across months) | positioning | StockEdge, MCX bhavcopy | ✅ Now (MCX OHLC/OI via broker; `jugaad-data` adjacent) |
| **OI buildup** (long/short buildup, covering, unwinding) | price×OI | StockEdge, Chartink (proxy) | ✅ Now (same logic as F&O) |
| **Commodity option-chain** (PCR, max-OI strike S-R, ΔOI) | MCX options | MCX option chain, Paytm | ✅ Now (broker chain → compute) |
| **Commodity rollover %** (+ vs 3M avg) | expiry carry | StockEdge | 🟡 Store |
| **COT / participant positioning** (CFTC: Managed-Money/Commercial net; COT index 0–100; extremes) | global positioning | CFTC (global), Barchart; MCX top-participant disclosures (India analog) | 🔴 Extra (CFTC COT feed; MCX disclosures access-restricted) |
| **Seasonality** (gold/silver/crude/natgas monthly bias, % positive years, entry/exit dates, "in-season" flag) | calendar edge | EquityClock, Barchart | 🟡 Store (need 10–20y history → compute) |
| **ATR / ATR%, RVOL, 52w H/L, gap, breakout, MA cross, RSI/MACD/Stoch/ADX, Bollinger, Supertrend, VWAP** on MCX | technicals on commodities | Chartink (15-min delayed MCX), computed | ✅ Now (`pandas-ta-classic` on broker MCX OHLC) |
| **% change / top gainers-losers (±2% movers)** | commodity movers | computed | ✅ Now |
| **Crude inventories (EIA weekly), NatGas storage (EIA), days-of-supply, refinery utilization** | fundamental overlay | EIA, Investing economic calendar | 🔴 Extra (EIA/API feeds) |
| **Macro overlays** (DXY, real yields, ETF holdings like SPDR GLD, central-bank demand) | gold/silver drivers | macro feeds | 🔴 Extra |
| **Event/surprise filter** (actual vs consensus on inventory/data release) | data-driven moves | Investing economic calendar | 🔴 Extra |

---

### Stack-coverage rollup
- **✅ Now (no new data):** essentially **all** of Price/Performance, Volume/Liquidity, Volatility/Momentum/Technical, F&O OI/PCR/Greeks/max-pain/participant/basis, Sector rotation, Corporate-actions, and **commodity technicals + curve shape**. This is the large majority of the catalog.
- **🟡 Store (collect a local daily history, then compute):** IV Rank/IV Percentile, rollover %, OI-spurt-vs-average, delivery-spike trend, all-time/2y/5y extremes, proprietary momentum composites, calendar-spread Z-scores, seasonality, thematic baskets.
- **🔴 Extra (need an outside feed):** the **fundamentals block** (all valuation/profitability/growth/leverage/efficiency ratios, EPS, Piotroski, quality scores — `nselib` gives only PE), **analyst ratings/estimates**, **news sentiment**, **MTF-eligible list**, **credit-rating & index-inclusion events**, **super-investor holdings**, and **commodity macro/COT/EIA overlays**.

### New sources cited (this section)
- Screener.in query builder — <https://www.screener.in/screens/1556145/all-parameters-search/> · <https://www.screener.in/guides/creating-screens/> · Piotroski <https://www.screener.in/screens/2/piotroski-scan/>
- Chartink scanner — <https://chartink.com/articles/scanner/scanner-user-guide/> · custom indicators <https://chartink.com/articles/scanner/now-create-your-own-custom-indicators/> · FAQ (cash-only/OI proxy) <https://chartink.com/articles/scanner/stock-screener-faq/>
- Trendlyne — all params <https://trendlyne.com/fundamentals/all-available-parameters/> · DVM scores <https://trendlyne.com/score-details/> · SmartOptions <https://smartoptions.trendlyne.com/> · participant-wise OI <https://trendlyne.com/futures-options/reports/participants-wise-oi/>
- Tickertape — filter guide <https://help.tickertape.in/support/solutions/82000073927> · screener <https://tickertape.in/screener/equity>
- StockEdge — scan groups <https://web.stockedge.com/scan-groups> · live scan inventory `api.stockedge.com/Api/AlertDashboardApi/GetAlertGroups`
- TradingView — screener <https://www.tradingview.com/screener/> · field reference <https://shner-elmo.github.io/TradingView-Screener/fields/stocks.html>
- Investing.com — stock screener <https://www.investing.com/stock-screener>
- MoneyControl — market stats / stock screener (Stock Watch, Market Statistics hub, F&O OI quadrants)
- NSE — market-data screens (top-gainers-losers, 52-week-high, volume-gainers-spurts, upper/lower-band-hitters, most-active-contracts, option-chain, advance/decline, large/bulk/block deals, pre-open-market-fno)
- Options analytics — Sensibull <https://web.sensibull.com/options-screener> · Opstra <https://opstra.definedge.com/> (IVR/skew/surface) · Quantsapp <https://web.quantsapp.com/option-chain> (IVP/participant/ban)
- Commodity/macro — MCX bhavcopy & option-chain <https://www.mcxindia.com/market-data/bhavcopy> · CFTC COT <https://www.cftc.gov/MarketReports/CommitmentsofTraders/> · EIA weekly petroleum <https://www.eia.gov/petroleum/supply/weekly/> & NG storage <https://www.eia.gov/naturalgas/storage/> · seasonality <https://equityclock.com/charts/>
