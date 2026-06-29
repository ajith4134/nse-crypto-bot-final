# Crypto Screeners / Filters — Ranked OSS Report (per segment)

> Goal: monitor a wide, varied crypto universe and surface trade candidates **per segment**
> (Spot, USDⓢ-M Perp, COIN-M, Options) using **ccxt public data (no key, CPU-only)**, with
> selectable filters mirroring the Binance app. Researched via real web searches against
> ccxt/freqtrade/Binance docs, GitHub and PyPI, current to **June 2026**.
> pip versions below were verified locally with `/home/karan18190164/.venv/bin/pip index versions`.

---

## 0. TL;DR — Recommended stack

**`ccxt` (already our `ExchangeClient`) + ported freqtrade pairlist-filter algorithms + Binance implicit `/futures/data` endpoints for funding/OI/long-short + `ta` (or TA-Lib, already installed) for volatility + `pycoingecko` for market-cap tiers.**

Everything needed for ALL requested filters across ALL four segments is **public, no API key, CPU-only**. No paid feed is required. A paid/aggregated feed (Coinglass / Coinalyze) is optional and only buys you *cross-exchange aggregated* funding/OI/long-short — not needed for a Binance-first screener.

---

## 1. Library ranking (verified)

| # | Lib / source | Role in screener | Stars | License | Latest (pip-verified) | Key? | CPU | pip |
|---|---|---|---|---|---|---|---|---|
| 1 | **ccxt** | Core: tickers, markets, funding, OI, OHLCV, greeks; multi-exchange | ~35k | MIT | **4.5.61** (2026-06-27) ✅ INSTALLED | No (public) | Yes | `ccxt` |
| 2 | **freqtrade** (pairlist filters) | Filter *algorithms* to port: VolumePairList, PercentChangePairList, AgeFilter, VolatilityFilter, RangeStabilityFilter, MarketCapPairList, Shuffle/Offset | ~51.9k | GPLv3 | **2026.5.1** ✅ | No (public) | Yes | `freqtrade` (works; docs prefer script/docker due to TA-Lib build) |
| 3 | **python-binance** | Direct Binance spot+fapi+dapi+eapi REST (alt to ccxt implicit) | ~7.2k | MIT | **1.0.37** (2026-06-08) ✅ | No (market data) | Yes | `python-binance` |
| 4 | **ta** (bukosabino) | Volatility: ATR, Bollinger band-width, std vol — pure-Python, no C dep | ~5.1k | MIT | current ✅ | No | Yes | `ta` |
| 4= | **TA-Lib** | Volatility: ATR/NATR/STDDEV (faster, needs C lib) | ~12.1k | BSD-2 | **0.6.8** ✅ INSTALLED | No | Yes | `ta-lib` (C lib present) |
| 5 | **pycoingecko** | Market-cap tiers / rank / categories / 7d change | ~1.1k | MIT | **3.2.0** ✅ | Free demo key nudged | Yes | `pycoingecko` |
| 6 | **cryptofeed** | OPTIONAL streaming: FUNDING / OPEN_INTEREST / LIQUIDATIONS channels | ~2.9k | MIT-style | **2.4.1** (2025-02) ✅ | No (market data) | Yes | `cryptofeed` |
| 7 | **py-vollib-vectorized** / **optlib** | OPTIONAL fallback IV+greeks compute (Black-76) if an exchange omits IV | 0.4k / 1.6k | MIT | on pip ✅ | No | Yes | `py-vollib-vectorized` / `optlib` |
| 8 | **tardis-dev** | OPTIONAL historical options IV/greeks/OI (Deribit) | — | — | **4.2.0** ✅ | Paid (free = 1st-of-month) | Yes | `tardis-dev` |
| 9 | **coinglass-api / coinalyze** wrappers | OPTIONAL cross-exchange aggregated funding/OI/long-short | small | MIT | `coinglass-api` on pip (`coinglass` is NOT) | **Key required** (Coinglass paid; Coinalyze has free key) | Yes | `coinglass-api` |
| — | **hummingbot** | Not a screener (execution/MM only) — skip for screening | ~18k | Apache-2 | 20260610 ✅ | — | — | — |
| — | **coinmarketcap** / **python-coinmarketcap** | Market-cap alt to CoinGecko | — | Apache-2 | `coinmarketcap` **5.0.3** ✅ | **CMC key required** | Yes | `coinmarketcap` |

**pip caveats found:** `pandas-ta` (twopirllc) is **NOT installable** from our index and the original repo/PyPI history was wiped ~Sep 2025 (supply-chain concern) — use **`ta`** or the community fork **`pandas-ta-classic`** instead. `coinglass` (bare name) is **not on PyPI**; the usable wrapper is **`coinglass-api`**.

---

## 2. ccxt screening capability map (what's DIRECTLY available, public, no key)

Latest ccxt **4.5.61** (2026-06-27), 106 exchanges, all CPU-only HTTP. Source: ccxt manual + PyPI.

| ccxt unified method | Returns (key fields) | Segments | Status |
|---|---|---|---|
| `fetch_tickers()` | dict by symbol: `last, open, high, low, quoteVolume, baseVolume, change, percentage, vwap` | spot / swap / future / option (call per market type) | **Direct.** Primary volume + 24h%change screen |
| `fetch_markets()` / `.markets` | `type` (spot/swap/future/option), `spot/swap/future/option/contract` bools, `linear/inverse`, `settle`, `base/quote`, `active`, `expiry`, `strike`, `optionType` | all | **Direct.** Segment + instrument filtering |
| `fetch_funding_rate(s)` | `fundingRate, markPrice, indexPrice, nextFundingTimestamp` (all swaps at once) | USDⓢ-M, COIN-M | **Direct** |
| `fetch_funding_rate_history()` | historical funding (auto-paginate `params={'paginate':True}`) | USDⓢ-M, COIN-M | **Direct** |
| `fetch_open_interest(symbol)` | `openInterestAmount, openInterestValue` | perp/future/option | **Direct** (per-symbol; no "all" form → loop) |
| `fetch_open_interest_history()` | OHLC-style OI series (Binance keeps ~30d) | USDⓢ-M, COIN-M | **Direct** |
| `fetch_long_short_ratio_history()` | global long/short account ratio series | USDⓢ-M | **Direct (unified)**, Binance + Bitget. No single-shot `fetch_long_short_ratio` |
| `fetch_ohlcv()` | `[ts,o,h,l,c,v]` → compute ATR / realized vol | all | **Direct** |
| `fetch_mark_price(s)` | mark/index price | perps | **Direct** |
| `fetch_greeks` / `fetch_all_greeks` | `delta,gamma,theta,vega,rho,bidIV,askIV,markIV,markPrice,underlyingPrice` | Options (Deribit/Bybit/OKX best; Binance eapi supported) | **Direct.** IV+greeks straight from exchange |
| `fetch_option` / `fetch_option_chain` | option contract / chain detail | Options | **Direct** |
| `fetch_volatility_history(code)` | exchange-published vol history | Options (Deribit) | **Direct** |

**Needs ccxt implicit / raw Binance endpoint** (still public, no key — ccxt auto-generates `fapiPublicGet*`, `fapiDataGet*`, `dapiPublicGet*`, `eapiPublicGet*` from path; naming = `<prefix><Public|Private|Data><Verb><PathCamelCase>`, version dropped):
- **Top-trader long/short split** — `fapiDataGetTopLongShortAccountRatio`, `fapiDataGetTopLongShortPositionRatio`
- **Taker buy/sell volume** — `fapiDataGetTakerLongShortRatio`
- **Global long/short** (if you prefer raw) — `fapiDataGetGlobalLongShortAccountRatio`
- **OI history** — `fapiDataGetOpenInterestHist`
- **Option mark IV + greeks + OI** — `eapiPublicGetMark`, `eapiPublicGetOpenInterest`
- **Binance futures "categories"** — `fapiPublicGetExchangeInfo` then bucket on `underlyingSubType` / `underlyingType` / `contractType` / `marginAsset` / `onboardDate` (see §5)

**Needs 3rd-party feed:** nothing for a Binance-first screener. Only *cross-exchange aggregated* funding/OI/long-short dashboards (Coinglass/Coinalyze) would justify an external feed.

---

## 3. freqtrade pairlist filters = ready-made screener filters

freqtrade GPLv3, ~51.9k★, uses **ccxt under the hood**, CPU-only, no key for public data. The filter *algorithms* map almost 1:1 to our requested filters:

| freqtrade handler/filter | Our filter | Metric / params |
|---|---|---|
| **VolumePairList** | volume rank + **relative/unusual volume** | top-N by `quoteVolume`; `lookback_days/lookback_period` range mode sums volume over N candles (relative volume) |
| **PercentChangePairList** | **top gainers / losers**, 24h/Nd change | sort/filter by 24h %change; lookback mode → %change over N candles; `sort_direction`, `min/max_value` |
| **MarketCapPairList** | **market-cap tiers** | CoinGecko mcap rank `max_rank`, `categories`, whitelist/blacklist mode |
| **AgeFilter** | **new listings** | `min_days_listed` / `max_days_listed` |
| **VolatilityFilter** | **volatility** | stddev of returns over `lookback_days`, `min/max_volatility` |
| **RangeStabilityFilter** | range/ROC band | rate-of-change over `lookback_days`, `min/max_rate_of_change` |
| PriceFilter / SpreadFilter | price & liquidity guards | `min/max_price`, `low_price_ratio`, `max_spread_ratio` |
| ShuffleFilter / OffsetFilter / PerformanceFilter | diversification / paging / self-perf | — |
| CrossMarketPairList | spot-vs-futures availability | `pairs_exist_on` |

**Gap:** freqtrade has **NO FundingRateFilter and NO open-interest pairlist** (verified full `plugins/pairlist/` dir). Funding rate is only used at trade level (`futures_funding_rate`), not as a screen. → We build funding/OI/long-short filters ourselves from ccxt/Binance endpoints (§2).

**Reuse caveat (important):** filters subclass `IPairList` and are built via `PairListResolver`/`PairListManager`; the constructor takes freqtrade's **`Exchange` wrapper, not a raw ccxt client**. So **port the per-filter logic** (it's small: % change, stddev vol, ROC, age, mcap-rank) onto our existing `ExchangeClient(ccxt)` rather than importing the classes. License is GPLv3 — porting algorithm logic into our private non-published project is fine (no-license-filter / reuse-real-code-first applies).

---

## 4. Options screening (Binance eapi + Deribit)

- **Live, free, no-key path = ccxt:** `fetch_greeks`/`fetch_all_greeks` give **bid/ask/mark IV + delta/gamma/theta/vega/rho + underlyingPrice**; `fetch_open_interest` gives OI by strike; `fetch_tickers` gives mark/last/volume. Unified option symbol `BASE/QUOTE:SETTLE-YYMMDD-STRIKE-{C|P}` parses to `market['strike'|'expiry'|'optionType']` → bucket **CE/PE, expiry, ITM/ATM/OTM** vs `underlyingPrice`.
- **Binance options direct:** `GET /eapi/v1/mark` → `markPrice, bidIV, askIV, markIV, delta, theta, gamma, vega`; `/eapi/v1/openInterest` (needs `underlyingAsset`+`expiration`); `/eapi/v1/ticker` (volume, but **IV/OI not on ticker**). All public.
- **Max-pain & PCR:** compute ourselves from per-strike OI (max pain = strike minimizing Σ option intrinsic value; PCR = put OI ÷ call OI). Reference repos: Deribit official max-pain Python, `asad70/Options-Max-Pain-Calculator`, `atrybyme/Open-Interest-NSE-Live-Analysis`.
- **Fallback IV/greeks** if an exchange omits them: **py-vollib-vectorized** (fast, MIT) or **optlib** (Black-76, good for crypto futures-style options).
- **Historical IV/greeks/surface:** **tardis-dev** (paid; free first-day-of-month tier to prototype). Surface/skew viz repos: `joshuapjacob/crypto-volatility-surface` (Binance), `dwasse/vol-surface-visualizer`, `FlyCapital/bitVolSurfacePublic` (Deribit SABR).

---

## 5. Binance futures "categories" — how to mirror the app (VERIFIED live)

**There is no category endpoint.** Pull `GET /fapi/v1/exchangeInfo` (public) once and bucket by these per-symbol fields (confirmed against live API):
- **`underlyingSubType`** = the app's tag tabs. Live tags incl: `DeFi, TradFi, Alpha, AI, Layer-1, Meme, USDC, Gaming, Layer-2, PoW, RWA, Index, **Pre-IPO**, ...`
- **`underlyingType`** = `COIN / COMMODITY / KR_EQUITY / ...`
- **`contractType`** = `PERPETUAL` vs **`TRADIFI_PERPETUAL`** (tokenized TradFi stocks/commodities)
- **`marginAsset` / `quoteAsset`** = `USDT` vs `USDC` (USDC-margined)
- **`onboardDate`** (ms epoch) = "New listings (monthly)"; **"All"** = `status==TRADING`

Verified examples: **XAGUSDT** (silver) → `contractType=TRADIFI_PERPETUAL, underlyingType=COMMODITY, underlyingSubType=[TradFi], margin=USDT`. **SKHYNIXUSDT** → `underlyingType=KR_EQUITY, contractType=TRADIFI_PERPETUAL, margin=USDT`. Normal **BTCUSDT** → `contractType=PERPETUAL, underlyingType=COIN`.

---

## 6. Per-segment mapping table: filter → data source → library

### SPOT (`api.binance.com /api/v3`, ccxt `binance` spot)
| Filter | Data source | Library call |
|---|---|---|
| Quote ccy (USDT/USDC/BTC/BNB) | market `quote` field | ccxt `fetch_markets` filter `quote` |
| Sort by 24h volume | ticker `quoteVolume` | ccxt `fetch_tickers` → VolumePairList logic |
| 24h change% / gainers-losers | ticker `percentage` | ccxt `fetch_tickers` → PercentChangePairList logic |
| Unusual / relative volume | OHLCV volume over N candles | ccxt `fetch_ohlcv` → VolumePairList range mode |
| 7d change | CoinGecko `/coins/markets` | `pycoingecko` |
| Volatility (ATR/realized) | OHLCV | ccxt `fetch_ohlcv` + `ta`/`ta-lib` ATR/NATR/STDDEV |
| New listings | listing age from candles | AgeFilter logic |
| Market-cap tiers | CoinGecko mcap rank | `pycoingecko` / MarketCapPairList logic |

### USDⓢ-M PERP (`fapi.binance.com /fapi/v1`, ccxt `swap` `linear` `settle∈USDT/USDC`)
| Filter | Data source | Library call |
|---|---|---|
| Category tabs (All/new/TradFi/Pre-IPO/USDC) | `/fapi/v1/exchangeInfo` fields | ccxt `fapiPublicGetExchangeInfo` (bucket §5) |
| Gainers/losers, vol, 24h% | `/fapi/v1/ticker/24hr` | ccxt `fetch_tickers(type=swap)` |
| Funding rate | `/fapi/v1/premiumIndex` / `fundingRate` | ccxt `fetch_funding_rates` |
| Open interest + OI change | `/fapi/v1/openInterest` + `/futures/data/openInterestHist` | ccxt `fetch_open_interest` + `fetch_open_interest_history` |
| Long/short ratio | `/futures/data/globalLongShortAccountRatio` + top* | ccxt `fetch_long_short_ratio_history` / `fapiDataGet*` |
| Taker buy/sell | `/futures/data/takerlongshortRatio` | ccxt `fapiDataGetTakerLongShortRatio` |
| Volatility | OHLCV | ccxt `fetch_ohlcv` + `ta` |
| New listings (monthly) | `onboardDate` | exchangeInfo |

### COIN-M (`dapi.binance.com /dapi/v1`, ccxt `swap`/`future` `inverse` `settle=coin`)
| Filter | Data source | Library call |
|---|---|---|
| 24h vol / change% | `/dapi/v1/ticker/24hr` (uses `symbol` or `pair`) | ccxt `fetch_tickers` / `dapiPublicGetTicker24hr` |
| Funding | `/dapi/v1/premiumIndex` | ccxt `fetch_funding_rates` |
| Open interest + change | `/dapi/v1/openInterest` + `/futures/data/openInterestHist` (uses `pair`+`contractType`) | ccxt `fetch_open_interest` + `dapiDataGetOpenInterestHist` |
| Long/short, taker | `/futures/data/...` (pair+contractType) | ccxt `dapiDataGet*` |
| Volatility | OHLCV | ccxt `fetch_ohlcv` + `ta` |

### OPTIONS (`eapi.binance.com /eapi/v1`; also Deribit, ccxt `option`)
| Filter | Data source | Library call |
|---|---|---|
| Universe (strike/expiry/CE-PE) | `/eapi/v1/exchangeInfo` / symbol parse | ccxt `fetch_markets(type=option)` → `strike/expiry/optionType` |
| Volume sort | `/eapi/v1/ticker` | ccxt `fetch_tickers` |
| IV + skew | `/eapi/v1/mark` (`markIV,bidIV,askIV`) | ccxt `fetch_greeks` / `fetch_all_greeks` |
| Greeks | `/eapi/v1/mark` | ccxt `fetch_greeks` |
| Open interest | `/eapi/v1/openInterest` (underlying+expiry) | ccxt `fetch_open_interest` / `eapiPublicGetOpenInterest` |
| Max-pain / PCR | per-strike OI | compute (Deribit/asad70 algo) |
| ITM/ATM/OTM | strike vs `underlyingPrice` | ccxt index/mark + bucket |
| Fallback IV/greeks | OHLCV/price | `py-vollib-vectorized` / `optlib` |

---

## 7. How it plugs into our existing `ExchangeClient(ccxt)`

1. **No new exchange client needed** — our `ExchangeClient` already wraps ccxt 4.5.61. Add screener methods that call `fetch_tickers`, `fetch_markets`, `fetch_funding_rates`, `fetch_open_interest(_history)`, `fetch_long_short_ratio_history`, `fetch_greeks/fetch_all_greeks`, and the implicit `fapiPublicGetExchangeInfo` / `fapiDataGet*` / `eapiPublicGet*`.
2. **Segment selector** = filter `exchange.markets` by `type`/`linear`/`inverse`/`settle`/`active` + Binance `underlyingSubType`/`contractType`/`marginAsset`/`onboardDate` tags (§5) for the app-style category tabs.
3. **Filter engine** = a small `filters.py` porting freqtrade's algorithms (PercentChange, Volume+relative, Age, Volatility, RangeStability, MarketCap) onto our ccxt client — each is a pure function over a tickers/OHLCV snapshot.
4. **Derivatives filters** (funding, OI + OI-change, long/short, taker) = our own functions over the ccxt unified + implicit Binance endpoints — these are the pieces freqtrade lacks.
5. **Volatility** = `ta` (pure-Python, no C) or the already-installed **TA-Lib 0.6.8** for ATR/NATR/STDDEV on `fetch_ohlcv` output.
6. **Market-cap tiers** = `pycoingecko` (free; optional demo key) for rank/category/7d, joined on base symbol.
7. **Options analytics** = ccxt greeks/OI + a tiny max-pain/PCR helper; optional `py-vollib-vectorized` for fallback IV.
8. **Optional realtime** = `cryptofeed` FUNDING/OPEN_INTEREST/LIQUIDATIONS channels if we later want push-based alerts instead of polling.

All of the above is **public, keyless, CPU-only** — consistent with our CPU-first, secrets-safe, reuse-real-code-first conventions.

---

## 8. Key sources
- ccxt manual / methods: https://github.com/ccxt/ccxt/wiki/manual · https://docs.ccxt.com/docs/exchanges/binance · https://docs.ccxt.com/docs/exchanges/deribit · types: https://raw.githubusercontent.com/ccxt/ccxt/master/ts/src/base/types.ts
- freqtrade pairlists: https://www.freqtrade.io/en/stable/plugins/ · source: https://github.com/freqtrade/freqtrade/tree/develop/freqtrade/plugins/pairlist · `IPairList`: https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/plugins/pairlist/IPairList.py
- Binance fapi: https://developers.binance.com/docs/derivatives/usds-margined-futures/market-data/rest-api/ (Exchange-Information, 24hr-Ticker, Mark-Price, Open-Interest, Open-Interest-Statistics, Long-Short-Ratio)
- Binance dapi: https://developers.binance.com/docs/derivatives/coin-margined-futures/market-data/rest-api/
- Binance eapi: https://developers.binance.com/docs/derivatives/options-trading/market-data/ (Option-Mark-Price, Open-Interest)
- XAGUSDT launch: https://www.binance.com/en/square/post/01-07-2026-binance-futures-to-launch-usd-margined-xagusdt-perpetual-contract-...
- python-binance: https://github.com/sammchardy/python-binance · pycoingecko: https://github.com/man-c/pycoingecko · cryptofeed: https://github.com/bmoscon/cryptofeed · ta: https://github.com/bukosabino/ta · TA-Lib: https://github.com/TA-Lib/ta-lib-python
- Options OSS: py_vollib https://github.com/vollib/py_vollib · optlib https://github.com/dbrojas/optlib · tardis-dev https://pypi.org/project/tardis-dev/ · Deribit max-pain https://insights.deribit.com/dev-hub/deribit-max-pain-python-code/ · crypto-volatility-surface https://github.com/joshuapjacob/crypto-volatility-surface
- Aggregated (optional/paid): coinglass-api https://github.com/dineshpinto/coinglass-api · coinalyze https://github.com/ivarurdalen/coinalyze

---

## Exhaustive Crypto Filter Catalog (every criterion)

> Master taxonomy stitched from full field-lists of **TradingView** (3 crypto screeners), **CoinGecko**, **CoinMarketCap**, **DefiLlama**, **Token Terminal**, **Coinglass** (every API-v4 endpoint), **Glassnode**, **Santiment**, **Messari**, **IntoTheBlock**, **CryptoQuant**, plus **Binance / Bybit / OKX / Deribit** native screener + options fields. Researched June 2026 via live source/API docs (URLs in §sources at end of this section). Every criterion is tagged with **Stack** = how WE get it:
>
> **Availability legend**
> - **ccxt** — ccxt public unified method, no key, CPU-only (our `ExchangeClient`)
> - **raw** — free but only in ccxt `info`/implicit endpoint (`fapiDataGet*`, `eapiPublicGet*`, OKX `rubik`, Bybit v5) — still keyless
> - **CG** — free CoinGecko API (Demo/keyless)
> - **chain** — free public chain API (mempool.space, blockchain.com, blockchair, Etherscan, beaconcha.in)
> - **compute** — derive locally from cheaper free data
> - **free-ext** — other free endpoint (alternative.me Fear&Greed, GitHub API, DefiLlama)
> - **PAID** — needs paid feed (Glassnode / Santiment / Messari / CryptoQuant / IntoTheBlock / Coinglass-API / Token Terminal / Laevitas / Amberdata / Tardis / LunarCrush key)
>
> **Headline:** of ~350 distinct criteria below, the **entire PRICE / VOLUME / MARKET-CAP / VOLATILITY-TECHNICAL / DERIVATIVES / OPTIONS** blocks are reachable **free** (ccxt + raw + CoinGecko + local compute). Only the **on-chain behavioral suite** (MVRV/SOPR/NUPL/realized-cap/exchange-&-miner-flows/holder-cohorts) and **aggregated cross-exchange + ETF-flow + proprietary-index** dashboards are genuinely PAID.

### Cat 1 — PRICE / PERFORMANCE

| Criterion | Sources exposing it | Stack |
|---|---|---|
| Last / open / high / low / close (24h) | all exchanges, TV `close/open/high/low`, CG | ccxt / CG |
| 24h % change (`change`/`percentage`) | all; TV `change`; CG `price_change_percentage_24h`; CMC | ccxt / CG |
| 1h % change | TV `change\|60`; CG `..._1h_in_currency`; CMC `percent_change_1h` | CG / compute |
| 4h % change | TV `change\|240` | compute (OHLCV) |
| 7d % change | TV `Perf.W`; CG `..._7d`; CMC sort `volume_7d`/web | CG / compute |
| 14d % change | CG `..._14d_in_currency` | CG |
| 30d % change | TV `Perf.1M`; CG `..._30d`; CMC `percent_change_30d` | CG / compute |
| 60d / 90d (3M) % change | TV `Perf.3M`; CMC `percent_change_60d/90d`; Messari roi 3mo | CG-paid / compute |
| 6M % change | TV `Perf.6M` | compute |
| YTD % change | TV `Perf.YTD`; Messari roi YTD | compute |
| 1y % change | TV `Perf.Y`; CG `..._1y`; Messari roi 1yr | CG / compute |
| 5y / all-time % change | TV `Perf.5Y`, `Perf.All` | compute |
| 200d % change | CG `..._200d_in_currency` | CG |
| Change-from-open / gap | TV `change_from_open`, `gap_percent` | compute |
| All-Time-High (ATH) + date | CG `ath`/`ath_date`; Messari; TV valuation | CG |
| % from ATH (down from ATH) | CG `ath_change_percentage`; Messari `percent_down` | CG |
| All-Time-Low (ATL) + date | CG `atl`/`atl_date` | CG |
| % from ATL (up from ATL) | CG `atl_change_percentage` | CG |
| New 24h highs / lows | exchange `high_24h`/`low_24h` vs price | compute |
| Top gainers / losers (rank) | CG `top_gainers_losers`(paid); CMC gainers-losers; all-exchange UIs | compute (sort `percentage`) |
| Breakout (price vs N-day high / Donchian) | TV `Donchian`; compute | compute |
| Price range min/max filter | CMC `price_min`/`price_max`; freqtrade PriceFilter | ccxt / compute |
| ROI (since launch) / ROI vs BTC/ETH | CG `roi`; Messari `roi_data`, `roi_by_year` | CG / compute |
| Price drawdown (relative) | Glassnode `price_drawdown_relative`; TV | compute |

### Cat 2 — VOLUME / LIQUIDITY

| Criterion | Sources | Stack |
|---|---|---|
| 24h base volume | all; TV `volume`; CG `total_volume` (base) | ccxt / CG |
| 24h quote/USD volume (vol×price) | TV `Value.Traded`; ccxt `quoteVolume`; CG `total_volume` | ccxt / CG |
| 7d / 30d volume | CMC `volume_7d`/`volume_30d`; DefiLlama DEX vol | CMC-key / DL |
| Avg volume 10/30/60/90d | TV `average_volume_*_calc` | compute (OHLCV) |
| Relative volume (RVOL) / unusual volume | TV `relative_volume_10d_calc`, intraday; freqtrade VolumePairList range | compute |
| Volume change % | TV `volume\|` modifiers; CMC `volume_change_24h` | compute |
| Volume / market-cap ratio (turnover) | Messari `volume_turnover`; TV `market_cap_to_volume` | compute |
| 24h turnover (quote) | Bybit `turnover24h`; OKX `volCcy24h` | ccxt |
| Spot vs perp volume split | per-segment `fetch_tickers`; Coinglass spot-vs-deriv | compute / PAID(agg) |
| Bid-ask spread | order book best bid/ask; Bybit `bid1/ask1`; freqtrade SpreadFilter | ccxt (`fetch_order_book`) |
| Order-book depth / liquidity (±2%) | `fetch_order_book`; ITB market depth | ccxt / compute |
| VWAP / VWMA | ccxt ticker `vwap`; TV `VWAP`,`VWMA` | ccxt / compute |
| Number of market pairs | CMC `num_market_pairs`; CG | CG |
| Coinbase premium / on-exchange premium | Coinglass `coinbase-premium-index`; CryptoQuant | compute (cross-exch) |
| CVD / footprint / netflow (spot) | Coinglass `spot-cvd-history`, `spot-footprint` | PAID |

### Cat 3 — MARKET-CAP / SUPPLY / CATEGORY

| Criterion | Sources | Stack |
|---|---|---|
| Market cap | CG `market_cap`; CMC; TV `market_cap_calc`; Messari | CG |
| Market-cap rank | CG `market_cap_rank`; CMC `cmc_rank` | CG |
| Market-cap tier (large/mid/small/micro) | bucket on mcap | compute |
| Market-cap dominance (% of total) | CMC `market_cap_dominance`; CG `market_cap_percentage`; Coinglass BTC dominance | CG |
| Market-cap change 24h (abs/%) | CG `market_cap_change_24h(_percentage)` | CG |
| FDV (fully diluted valuation) | CG `fully_diluted_valuation`; CMC `fully_diluted_market_cap`; TV `market_cap_diluted_calc` | CG |
| Mcap / FDV ratio | derive | compute |
| Mcap / TVL ratio | DefiLlama `mcaptvl`; CMC `tvl_ratio`; Token Terminal | DL |
| Circulating supply | CG `circulating_supply`; CMC; TV; Messari | CG |
| Total supply | CG `total_supply`; CMC; TV | CG |
| Max supply | CG `max_supply`; CMC | CG |
| Circulating/total ratio; % supply issued | derive; Messari `supply_y2050_issued_percent` | compute / PAID |
| Supply inflation rate (annual) | Messari `annual_inflation_percent`; Glassnode `issued`/`inflation_rate` | chain / PAID |
| Stock-to-Flow | Messari `stock_to_flow`; Coinglass `stock-flow`; CryptoQuant | compute(chain) / PAID |
| Y2050 / liquid / staked supply | Messari `y_2050_*`, `liquid supply`, staking | PAID |
| Category / sector (L1/L2/DeFi/meme/AI/RWA/gaming…) | CG `categories`; CMC `tag`; TV `sector`; Token Terminal sectors | CG |
| Chain / ecosystem filter | CG ecosystem categories; CMC platform; DefiLlama `chains` | CG / DL |
| Token unlock / vesting schedule | Coinglass `coin-unlock-list`; DefiLlama Pro | CG(partial) / PAID |
| Tokenholder count | Token Terminal `tokenholders`; CMC DexScan | PAID |

### Cat 4 — VOLATILITY / TECHNICAL (same TA set as stocks)

All TA below = **compute** from `fetch_ohlcv` via `ta`/TA-Lib; TradingView is the no-code equivalent and Coinglass sells precomputed RSI/MACD/ATR "heatmap lists" (`futures-rsi-list`, `futures-macd-list`, `futures-avg-true-range-list` = PAID, but identical math locally).

| Criterion | TV field / source | Stack |
|---|---|---|
| ATR / NATR / ADR | TV `ATR`,`ADR`; Coinglass ATR list | compute |
| Realized volatility 1d/1w/1m/3m/6m/1y | TV `Volatility.D/W/M`; Glassnode `realized_volatility_*` | compute |
| Bollinger Bands (upper/lower/basis) + band-width | TV `BB.upper/lower/basis`; freqtrade | compute |
| Keltner / Donchian channels | TV `KltChnl.*`, `Donchian` | compute |
| RSI (7/14) + RSI heatmap | TV `RSI`,`RSI7`; Coinglass `futures-rsi-list` | compute |
| Stochastic %K/%D, Stoch-RSI | TV `Stoch.K/D`, `Stoch.RSI.K/D` | compute |
| MACD (line/signal/hist) | TV `MACD.macd/signal` | compute |
| ADX + DI+/DI- | TV `ADX`,`ADX+DI`,`ADX-DI` | compute |
| CCI, Momentum, ROC, Williams %R, Ultimate Osc, Awesome Osc, Bull/Bear Power | TV `CCI20`,`Mom`,`ROC`,`W.R`,`UO`,`AO`,`BBPower` | compute |
| MFI / Chaikin Money Flow | TV `MoneyFlow`,`ChaikinMoneyFlow` | compute |
| Moving averages SMA/EMA 5/10/20/30/50/100/200/300 | TV `SMA*`/`EMA*` | compute |
| Hull MA, VWMA, Ichimoku, Parabolic SAR, Aroon | TV `HullMA*`,`VWMA`,`Ichimoku.BLine`,`P.SAR`,`Aroon.*` | compute |
| Supertrend | (TV chart-only; not a screener column) | compute |
| Pivots (Classic/Fib/Camarilla/Woodie/DeMark) | TV `Pivot.M.*` | compute |
| Technical rating ("Strong Buy"→"Strong Sell") | TV `Recommend.All/MA/Other` | compute |
| Correlation / beta to BTC / ETH | Glassnode `correlation_btc_7d`,`beta_btc_7d`; Messari risk | compute |
| Sharpe ratio (30d/90d/1y/3y) | Messari `sharpe_ratios` | compute |
| Range stability / rate-of-change band | freqtrade RangeStabilityFilter | compute |

### Cat 5 — DERIVATIVES (perps / futures) — the big crypto-specific set

| Criterion | Sources / exact fields | Stack |
|---|---|---|
| Funding rate (current) | ccxt `fetch_funding_rate(s)`; Binance `lastFundingRate`; Bybit/OKX `fundingRate`; Coinglass `fr-exchange-list` | ccxt |
| Predicted / next funding + countdown | `nextFundingRate`/`nextFundingTime`; OKX `nextFundingRate` | ccxt |
| Funding-rate history (OHLC) | ccxt `fetch_funding_rate_history`; Coinglass `fr-ohlc-histroy` | ccxt |
| Average funding (Nd) | derive from history | compute |
| OI-weighted funding (aggregated) | Coinglass `oi-weight-ohlc-history` | PAID |
| Vol-weighted funding (aggregated) | Coinglass `vol-weight-ohlc-history` | PAID |
| Funding min/max caps | Bybit `upper/lowerFundingRate`; OKX `min/maxFundingRate` | raw |
| Funding arbitrage (cross-exch APR) | Coinglass `fr-arbitrage` | PAID |
| Open interest (amount + value) | ccxt `fetch_open_interest`; Coinglass `oi-exchange-list` | ccxt |
| OI history (OHLC) | ccxt `fetch_open_interest_history`; Binance `openInterestHist` | ccxt / raw |
| OI change % (15m/1h/4h/24h) | derive from OI history | compute |
| OI / market-cap ratio; OI / volume ratio | derive (OI ccxt + mcap CG) | compute |
| Aggregated OI (cross-exchange, stable/coin-margin split) | Coinglass `oi-ohlc-aggregated-*` | PAID |
| Exchange OI dominance | Coinglass / derive | compute / PAID |
| Long/short ratio — global accounts | ccxt `fetch_long_short_ratio_history`; Binance `globalLongShortAccountRatio` | ccxt |
| Long/short — top-trader accounts | Binance `topLongShortAccountRatio`; Coinglass | raw |
| Long/short — top-trader positions | Binance `topLongShortPositionRatio` | raw |
| Net long/short position | Coinglass `net-position` | PAID |
| Taker buy/sell volume + ratio | Binance `takerlongshortRatio`; OKX `taker-volume`; Coinglass | raw |
| Liquidations — long/short/total | Coinglass `aggregated-liquidation-history`; ccxt `fetch_liquidations` (Binance/Deribit public) | ccxt(partial) / PAID |
| Liquidation order stream (real-time) | Coinglass `liquidation-order`; cryptofeed LIQUIDATIONS channel | PAID / ccxt-stream |
| Liquidation heatmap / map / max-pain | Coinglass `liquidation-*-heatmap/map`, `liquidation-max-pain` | PAID |
| Basis / annualized basis | Bybit `basis`/`basisRate`/`basisRateYear`; Coinglass `basis`; Glassnode | ccxt / compute |
| Premium index (mark vs index) | ccxt `fetch_mark_price`; Binance `premiumIndex` | ccxt |
| Perp vs spot spread | derive (perp mark − spot last) | compute |
| Estimated leverage ratio | CryptoQuant; Glassnode `futures_estimated_leverage_ratio` | PAID |
| Max leverage (per contract) | Bybit/OKX `lever`; market info | raw |
| Contract type — PERPETUAL vs TRADIFI_PERPETUAL | Binance `contractType`; bucket | raw |
| Underlying type — COIN / COMMODITY / KR_EQUITY / INDEX | Binance `underlyingType` | raw |
| Category tags — All/New/TradFi/Pre-IPO/USDC/DeFi/AI/Meme/L1/L2/PoW/RWA/Index/Gaming/Alpha | Binance `underlyingSubType`+`marginAsset`+`onboardDate`; OKX/Bybit zones | raw + CG |
| Margin asset (USDⓢ-M USDT/USDC vs COIN-M inverse) | `marginAsset`/`settle`; market `linear`/`inverse` | ccxt |
| Quarterly contract type / delivery date | Binance dapi `CURRENT_QUARTER`/`NEXT_QUARTER`; `deliveryDate` | raw |
| New listings (perp onboard) | Binance `onboardDate`; Bybit `launchTime`; OKX `listTime` | raw |
| Coinbase premium index | Coinglass; CryptoQuant | compute |

### Cat 6 — OPTIONS

Deribit (dominant) computes greeks+IV server-side → most are **ccxt** direct; analytics (skew/PCR/max-pain/GEX) = **compute** from public OI+greeks. Coinglass/Laevitas/Amberdata sell turnkey but are PAID.

| Criterion | Sources / fields | Stack |
|---|---|---|
| Implied volatility — mark / bid / ask IV | ccxt `fetch_greeks` (`mark/bid/askImpliedVolatility`); Deribit `mark_iv`; OKX `markVol`; Bybit `markIv` | ccxt |
| IV per strike (smile) | iterate Deribit `get_book_summary_by_currency` | ccxt |
| ATM IV | strike nearest spot | compute |
| IV rank / IV percentile | from DVOL or stored daily IV; Laevitas | compute / PAID |
| DVOL / volatility index (BTCDVOL, ETHDVOL) | ccxt `fetch_volatility_history`; Deribit `get_volatility_index_data` | ccxt |
| Realized vol / IV-vs-RV | compute or Laevitas/Amberdata | compute / PAID |
| IV skew — 25-delta risk reversal | select Δ≈±0.25 strikes, IV(call)−IV(put) | compute |
| 25-delta butterfly | (IV25c+IV25p)/2 − ATM IV | compute |
| Volatility smile / surface (raw) | mark_iv across strike×expiry | compute |
| SVI-calibrated smooth surface | Amberdata TrueLine, Block Scholes | PAID |
| Term structure (ATM IV vs DTE) | group ATM IV by expiry | compute |
| Greeks — delta/gamma/theta/vega/rho | ccxt `fetch_greeks`/`fetch_all_greeks`; OKX `opt-summary`; Deribit `greeks{}` | ccxt |
| Put/call ratio (OI & volume) | group OI/vol by optionType; OKX `oi-volume-ratio`; Coinglass | compute |
| Max pain | strike minimizing writer payout from OI-by-strike; Coinglass `option-max-pain` | compute / PAID |
| Open interest by strike / expiry | ccxt OI grouped; OKX `oi-volume-strike/expiry` | compute / raw |
| OI by put vs call | group `open_interest` by type | compute |
| Options volume / notional / turnover | Deribit `stats.volume`,`volume_usd`; Bybit `totalVolume` | ccxt |
| Gamma exposure (GEX) / dealer gamma | Σ(gamma×OI×spot²), dealer-signed | compute / PAID |
| Delta exposure (DEX), vanna, charm | from greeks + OI | compute / PAID |
| Moneyness ITM/ATM/OTM | strike vs `underlyingPrice`/`index_price` | compute |
| Days-to-expiry / strike distance | `(expiry−now)`; strike−spot | compute |
| Options flow / block trades | Deribit `get_last_block_trades`; Laevitas/Greeks.live | ccxt / PAID |
| Fallback IV/greeks (compute) | py-vollib-vectorized / optlib (Black-76) | compute |
| 25-delta skew / OI / put-call (BTC on-chain options view) | Glassnode derivatives | PAID |

### Cat 7 — ON-CHAIN (crypto-unique)

Mostly **PAID** (entity-clustering / realized-cost-basis). Free substitutes: NVT, Stock-to-Flow, Puell, hash rate, total active-address count, supply+inflation via **chain** APIs; everything needing UTXO-age or labeled wallets is PAID.

| Criterion | Providers / metric names | Stack |
|---|---|---|
| Active addresses (count) | Glassnode `active_count`; Santiment `daily_active_addresses`; Messari; ITB; CryptoQuant | chain(total) / PAID(cohort) |
| New addresses / network growth | Glassnode `new_non_zero_count`; Santiment `network_growth`; ITB Net Network Growth | PAID |
| Sending / receiving / non-zero / zero-balance addresses | Glassnode `sending/receiving/non_zero_count` | PAID |
| Address balance cohorts (≥0.1/1/10/100/1k/10k BTC; USD buckets) | Glassnode `min_*_count`; Santiment holders_distribution | PAID |
| Addresses in profit / loss (% supply in profit) | Glassnode `profit_count/loss_count`, `profit_relative`; ITB In/Out of Money | PAID |
| Transaction count / volume (native & USD) | Glassnode `/transactions/`; Santiment `transaction_volume`; Messari; CryptoQuant network | chain(basic) / PAID |
| Adjusted transfer volume / change-adjusted | Glassnode entity-adjusted; Messari `adjusted_transaction_volume` | PAID |
| NVT / NVT-signal (NVTS) | Glassnode `nvt`/`nvts`; Santiment; Messari `nvt_adjusted`; CryptoQuant | compute(chain) / PAID |
| MVRV (+ Z-score, LTH/STH) | Glassnode `mvrv`/`mvrv_z_score`; Santiment `mvrv_usd`(windows); CryptoQuant; ITB | PAID |
| SOPR (aSOPR, STH-SOPR, LTH-SOPR) | Glassnode `sopr*`; CryptoQuant | PAID |
| NUPL (+ STH/LTH) | Glassnode `net_unrealized_profit_loss`; Coinglass NUPL; CryptoQuant | PAID |
| Realized cap / realized price | Glassnode `marketcap_realized_usd`/`price_realized_usd`; Messari `realized_marketcap_usd`; CryptoQuant | PAID |
| Realized profit / loss; net realized P/L | Glassnode `net_realized_profit_loss` | PAID |
| Exchange inflow / outflow / netflow | Glassnode `transfers_volume_*_exchanges_*`; Santiment `exchange_inflow/outflow`; CryptoQuant (deepest) | PAID |
| Exchange reserve / balance; supply on exchanges | Glassnode `balance_exchanges`; Santiment `supply_on_exchanges`; CryptoQuant Reserve | PAID |
| Exchange net position change; whale ratio | Glassnode `exchange_net_position_change`; CryptoQuant `Exchange Whale Ratio` | PAID |
| Whale transactions (>$100k / >$1M) | Santiment `whale_transaction_count_*`; ITB Large Transactions; Coinglass whale | PAID |
| Holder concentration (whales/investors/retail; top-N %) | ITB concentration; Santiment `amount_in_top_holders`; Messari `supply_in_top_100` | PAID |
| Holders by time held (hodlers/cruisers/traders) | ITB; HODL waves | PAID |
| HODL waves / realized-cap HODL waves | Glassnode `hodl_waves`/`rcap_hodl_waves` | PAID |
| LTH / STH supply + supply held | Glassnode `lth_sum`/`sth_sum`; Coinglass LTH/STH supply | PAID |
| Liquid / illiquid supply; lost coins | Glassnode liquid/illiquid; probably/provably lost | PAID |
| Coin Days Destroyed / dormancy / liveliness / ASOL/MSOL | Glassnode `cdd`,`average_dormancy`,`liveliness`,`asol/msol`; Santiment `age_consumed`; CryptoQuant | PAID |
| Reserve Risk | Glassnode `reserve_risk`; CryptoQuant; Coinglass | PAID |
| RHODL ratio | Glassnode `rhodl_ratio`; Coinglass | PAID |
| Thermocap / thermocap multiple | Glassnode `thermocap`; CryptoQuant | PAID |
| Puell Multiple | Glassnode `puell_multiple`; Coinglass `puell-multiple`; CryptoQuant | compute(chain) / PAID |
| Stablecoin Supply Ratio (SSR) | Glassnode `ssr`; CryptoQuant | PAID |
| Miner reserves / inflow / outflow / netflow | Glassnode `balance_miners`; CryptoQuant Miner Flows; ITB | PAID |
| Miner Position Index (MPI); miner-to-exchange flow | CryptoQuant `MPI`, Miner→Exchange | PAID |
| Hash rate / difficulty / Hash Ribbons | Glassnode `hash_rate_mean`/`difficulty`; CryptoQuant; chain | chain / PAID |
| Mining revenue / Puell inputs | Glassnode miner revenue; Messari `mining_revenue` | chain / PAID |
| Fees / revenue (network) | Glassnode `/fees/`; Messari `total_fees`; chain | chain / PAID |
| TVL (DeFi) | DefiLlama `tvl`; Token Terminal; CMC `tvl` | DL(free) |
| TVL change 1d/7d/30d; chain TVL | DefiLlama `change_1d/7d/1m`, `/v2/chains` | DL |
| Protocol fees / revenue / P-F / P-S | DefiLlama `/overview/fees`; Token Terminal | DL / PAID |
| DEX / perp / options volume (on-chain) | DefiLlama `/overview/dexs|derivatives|options` | DL |
| Yield / APY (base/reward/net/30d-mean/IL-risk) | DefiLlama `/pools` (`apy`,`apyBase`,`apyReward`,`apyMean30d`,`ilRisk`) | DL |
| Stablecoin mcap / peg deviation / by chain | DefiLlama `/stablecoins`; CryptoQuant stablecoin flows | DL |
| Staking ratio / yield / tokens staked | Messari `staking_stats`; Glassnode eth2; beaconcha.in | chain / PAID |
| Estimated leverage ratio (on-chain) | Glassnode/CryptoQuant | PAID |
| Stablecoin exchange flows / SSR | CryptoQuant stablecoin flows | PAID |
| Exchange-traded fund (ETF) flows / AUM / premium | Coinglass `etf-flows-history`,`etf-aum`; Glassnode institutions | PAID |
| Active developers / commits (income-statement context) | Token Terminal `active developers` | PAID |
| DAU / MAU active users | Token Terminal; DefiLlama Pro | PAID |
| Treasury value | Token Terminal; DefiLlama Pro `/treasuries` | PAID |
| Token incentives / revenue / earnings / P-E | Token Terminal income statement | PAID |

### Cat 8 — SENTIMENT / SOCIAL

| Criterion | Providers / fields | Stack |
|---|---|---|
| Crypto Fear & Greed Index (+classification & components) | alternative.me `/fng/`; Coinglass `cryptofear-greedindex` | free-ext |
| Social volume (twitter/telegram/reddit/4chan/youtube/farcaster) | Santiment `social_volume_*`; LunarCrush | PAID / LunarCrush-key |
| Social dominance | Santiment `social_dominance`; LunarCrush; TV | PAID |
| Weighted / balanced sentiment (bull/bear) | Santiment `sentiment_weighted_total`,`sentiment_balance_total`; LunarCrush | PAID |
| Galaxy Score | LunarCrush (only source) | LunarCrush-key |
| AltRank | LunarCrush | LunarCrush-key |
| Social contributors / posts / interactions / engagement | LunarCrush; Santiment social_active_users | LunarCrush-key / PAID |
| Trending coins | CG `/search/trending`; CMC trending; Santiment trending_words; LunarCrush | CG |
| Sentiment up/down votes | CG `sentiment_votes_up/down_percentage` | CG |
| Community data (reddit subs, telegram users) | CG `community_data` | CG |
| Dev activity / GitHub commits, stars, PRs | CG `developer_data`; Santiment `dev_activity`; Messari; GitHub API; Token Terminal | CG / chain(GitHub) / PAID |
| Network growth (new addresses) as sentiment | Santiment `network_growth`; ITB | PAID |
| News sentiment / Panic Score | CryptoPanic; NewsAPI + DIY NLP | free-ext(DIY) / PAID |
| Google Trends interest | pytrends (unofficial) | free-ext |
| StockTwits bullish/bearish + trending | StockTwits free API | free-ext |
| Bull market peak / cycle indexes (Rainbow, Pi Cycle, AHR999, 2yr-MA, Golden Ratio, Bubble Index, Altcoin Season) | Coinglass cycle endpoints | PAID(API)/free(web) |
| Proprietary indexes (Whale Index, CGDI, CDRI) | Coinglass | PAID |

### Cat 9 — CATEGORY / QUALITY / LISTING

| Criterion | Sources | Stack |
|---|---|---|
| New listings / coin age | freqtrade AgeFilter; CG `/coins/list/new`(paid); CMC `date_added`; exchange `onboardDate`/`launchTime`/`listTime` | compute / raw |
| Days-since-launch range | derive from listing timestamp | compute |
| Exchange listings count (# markets) | CMC `num_market_pairs`; CG | CG |
| Quote-asset filter (USDT/USDC/BTC/BNB/FDUSD/FIAT) | exchange `quoteAsset` tabs | ccxt |
| Segment / instrument type (spot/margin/swap/future/option) | ccxt `market.type`, `linear/inverse`, `settle`, `active` | ccxt |
| Risk tags — Seed Tag / Monitoring Tag (Binance); ST/Innovation/Adventure Zone (Bybit/OKX) | exchange UI / `stTag` | raw / scrape |
| Tokenized-stock (TradFi) vs Pre-IPO vs USDC-margined | Binance `contractType=TRADIFI_PERPETUAL`, `underlyingType=KR_EQUITY/COMMODITY`, `marginAsset=USDC` | raw |
| Audit count / oracle / contract platform | DefiLlama `/protocol`; CMC platform | DL / CG |
| Project quality score / rank | Messari sector; Token Terminal; CMC DexScan | PAID |
| Contract attributes (tick/lot/min size, precision, max leverage) | ccxt `market` precision/limits; OKX `tickSz/lotSz/minSz/lever` | ccxt |
| Contract status / state (TRADING/PRE/DELIVERING/EXPIRED) | exchange `status`/`state`; OKX `state`; Binance dapi status | ccxt / raw |
| Delivery / expiry date (dated futures & options) | ccxt `market.expiry`; OKX `expTime`/`alias`; Binance `deliveryDate` | ccxt |

### Coverage summary (free vs paid)

- **100% FREE (ccxt + raw + CoinGecko + local compute):** Cat 1 PRICE, Cat 2 VOLUME/LIQUIDITY, Cat 3 MARKET-CAP/SUPPLY/CATEGORY, Cat 4 VOLATILITY/TECHNICAL, Cat 5 DERIVATIVES (per-exchange), Cat 6 OPTIONS (Deribit greeks/IV/chain + all computed analytics), Cat 9 CATEGORY/QUALITY. Fear & Greed (Cat 8) and DeFi TVL/fees/yields (Cat 7) are also free (alternative.me / DefiLlama).
- **PAID-only (no clean free substitute):** the **on-chain behavioral suite** in Cat 7 (MVRV/SOPR/NUPL/realized-cap/exchange-&-miner-&-stablecoin flows/holder cohorts/HODL waves/dormancy) → Glassnode/CryptoQuant/Santiment/IntoTheBlock; **aggregated cross-exchange** funding/OI/liquidation-heatmaps/taker + ETF flows + proprietary indexes → Coinglass API; **social/sentiment** (social volume/dominance/Galaxy Score) → Santiment/LunarCrush; **standardized financials** (revenue/earnings/P-E/DAU-MAU/tokenholders) → Token Terminal.
- **Cheapest single paid add** if we later want on-chain: **CryptoQuant or Glassnode** (flows + valuation ratios); **Coinglass** (aggregated derivatives + liquidation maps); **LunarCrush** (social, has limited free tier).

### Sources (this section)
- TradingView crypto screeners (3) + scanner field reference: https://www.tradingview.com/crypto-screener/ · https://www.tradingview.com/crypto-coins-screener/ · https://www.tradingview.com/support/solutions/43000718742-crypto-coins-screener-discover-hidden-gems/ · https://shner-elmo.github.io/TradingView-Screener/ · https://pypi.org/project/tradingview-screener/
- CoinGecko: https://docs.coingecko.com/reference/coins-markets · /coins-top-gainers-losers · /coins-categories · /search/trending · /derivatives · https://www.coingecko.com/en/categories
- CoinMarketCap: https://coinmarketcap.com/api/documentation/v1/ · pro-api-reference/cryptocurrency · https://coinmarketcap.com/gainers-losers/ · /cryptocurrency-category/ · DexScan
- DefiLlama: https://api-docs.defillama.com/ · https://defillama.com/{yields,fees,dexs,stablecoins,chains,metrics}
- Token Terminal: https://tokenterminal.com/docs/explorer/metrics · /explorer/metrics/{pf-fully-diluted,ps-fully-diluted,revenue,earnings}
- Coinglass API v4 (every endpoint): https://docs.coinglass.com/llms.txt · https://docs.coinglass.com/reference · https://www.coinglass.com/{FundingRate,options,pricing,CryptoApi}
- Glassnode: https://docs.glassnode.com/basic-api/endpoints · https://academy.glassnode.com · https://insights.glassnode.com/the-realized-cap-foundation
- Santiment: https://academy.santiment.net/metrics · SanAPI free-tier docs
- Messari: https://docs.messari.io/api-reference/endpoints/metrics · https://onchainfx.com/ourdata
- IntoTheBlock: https://resources.intotheblock.com
- CryptoQuant: https://userguide.cryptoquant.com · https://userguide.cryptoquant.com/llms-full.txt
- Binance: https://developers.binance.com/docs/derivatives/{usds-margined-futures,coin-margined-futures,options-trading}/market-data/ · /change-log · academy.binance.com/en/glossary/{seed-tag,monitoring-tag}
- Bybit: https://bybit-exchange.github.io/docs/v5/market/{tickers,instrument,open-interest,long-short-ratio,history-fund-rate,iv}
- OKX: https://www.okx.com/docs-v5/en (instruments, tickers, funding-rate, open-interest, mark-price, opt-summary, rubik trading-statistics)
- Deribit: https://docs.deribit.com/api-reference/market-data/{public-ticker,public-get_book_summary_by_currency,public-get_volatility_index_data,public-get_index_price,public-get_instrument} · https://insights.deribit.com/exchange-updates/dvol-deribit-implied-volatility-index
- Options/vol analytics: https://docs.laevitas.ch/options/analytic · https://www.amberdata.io/ad-derivatives · https://www.blockscholes.com/data · https://docs.tardis.dev/historical-data-details/deribit
- Fear & Greed: https://api.alternative.me/fng/ · LunarCrush: https://lunarcrush.com/developers/api
