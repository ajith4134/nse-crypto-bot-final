# Crypto Spot Strategy Templates — Curated, Proven, OSS-Cited (BTC/ETH/alts, NO leverage)
> Reuse-first catalogue for the T8 genome. Each row: name | family | logic | entry | exit (SL/target/trail) | indicators+params | TF | regime | genome-mappable | source. Researched via real web search (June 2026) against freqtrade, jesse, OctoBot, Hummingbot, backtrader, QuantConnect/Lean, pandas-ta, awesome-quant.
> **Genome legend** — T8 composes TA-Lib features {ret, sma_fast/slow, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol} with threshold/crossover entry-exit ops. `yes` = expressible with those; `partial` = needs a derived/extra series (Supertrend bands, MACD diff, BB width, divergence, multi-TF, OBV/VWAP) approximable or needing one extra input; `no` = external feed (on-chain, sentiment) or non-mappable structure (Ichimoku cloud, full order-book).

---

## 1. Trend-following

| # | Name | Core logic | Entry | Exit (SL/target/trail) | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------------------------|---------------------|----|-----------|--------|--------|
| 1 | EMA Golden Cross | Fast EMA over slow EMA = uptrend | EMA12 crosses above EMA26 | EMA12 crosses below EMA26; SL 1.5×ATR | EMA(12), EMA(26) | 1h–1d | Trending | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 2 | SMA 50/200 (Death/Golden) | Classic long-term regime filter | SMA50 > SMA200 cross up | SMA50 < SMA200 cross down | SMA(50), SMA(200) | 1d | Strong trend | yes | [backtrader docs](https://www.backtrader.com/) |
| 3 | Triple EMA stack | Aligned EMAs confirm trend | EMA8>EMA21>EMA55 all rising | stack breaks; trail 2×ATR | EMA(8,21,55) | 4h | Trending | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 4 | Supertrend single | ATR band flips trend color | price closes above Supertrend | flip to red; SL = band | Supertrend(10,3.0) ATR | 1h–4h | Trending/volatile | partial (ATR band) | [Supertrend.py](https://github.com/freqtrade/freqtrade-strategies/blob/main/user_data/strategies/Supertrend.py) |
| 5 | Triple Supertrend | 3 Supertrends must agree | all 3 bands bullish | any 2 flip bearish | ST(10,1),(11,2),(12,3) | 15m–1h | Trending | partial | [PeetCrypto/freqtrade-stuff](https://github.com/PeetCrypto/freqtrade-stuff) |
| 6 | ADX trend filter | Trade only when ADX strong | +DI>-DI & ADX>25, EMA up | ADX<20 or DI cross | ADX(14), +DI/-DI, EMA(50) | 1h–4h | Trending only | partial (DI) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 7 | Donchian breakout (Turtle) | Buy N-day high | close > Donchian-20 high | close < Donchian-10 low | Donchian(20/10) = max/min | 4h–1d | Trending | yes (range_pct/max) | [jesse TurtleRules](https://github.com/jesse-ai/example-strategies/blob/master/TurtleRules/__init__.py) |
| 8 | Turtle 55/20 | Slow Turtle system 2 | 55-bar high breakout | 20-bar low exit; 2N stop | Donchian(55/20), ATR(20)=N | 1d | Trending | yes | [jesse TurtleRules](https://github.com/jesse-ai/example-strategies/blob/master/TurtleRules/__init__.py) |
| 9 | EMA ribbon | Multi-EMA fan expansion | ribbon fans up, price>all | ribbon compresses/crosses | EMA(10,20,30,40,50) | 1h | Trending | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 10 | Hull MA trend | HMA reduces lag | HMA slope turns up | HMA slope down; trail ATR | HMA(21) | 4h | Trending | partial (HMA) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 11 | KAMA adaptive trend | Adaptive MA filters chop | price>KAMA & KAMA rising | price<KAMA | KAMA(10,2,30) | 1h–4h | Trend+chop adaptive | partial (KAMA) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 12 | Parabolic SAR trend | Dots flip = stop & reverse | SAR flips below price | SAR flips above; SAR=trail | PSAR(0.02,0.2) | 1h–4h | Trending | partial (SAR) | [backtrader](https://www.backtrader.com/) |
| 13 | DEMA cross | Double-EMA less lag | DEMA(20) cross DEMA(50) | reverse cross | DEMA(20,50) | 4h | Trending | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 14 | Vortex indicator | VI+ vs VI- crossover | VI+ crosses above VI- | VI+ below VI- | VI(14) | 1h–4h | Trending | partial (VI) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 15 | EMA cross + ADX confirm | Trend + strength gate | EMA cross up AND ADX>20 | EMA cross down | EMA(9,21), ADX(14) | 1h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 16 | Guppy MMA (GMMA) | Fast vs slow EMA group | fast group above slow group | groups cross | EMA(3..15)/(30..60) | 4h–1d | Trending | yes | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 17 | Linear-regression slope | Regression channel slope+ | LR slope > 0 & price>LR | slope<0 | LinReg(50) slope | 1h–4h | Trending | partial (linreg≈ret) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 18 | TEMA + momentum | TEMA trend with mom filter | price>TEMA & mom>0 | price<TEMA | TEMA(30), MOM(10) | 1h | Trending | partial (TEMA), mom yes | [pandas-ta](https://github.com/twopirllc/pandas-ta) |

## 2. Momentum

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 19 | ROC momentum | Rate-of-change positive | ROC(12)>threshold | ROC<0; SL ATR | ROC(12) | 1h–1d | Trending | yes (mom/ret) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 20 | RSI-trend (above 50) | RSI>50 = bullish bias | RSI crosses above 50 | RSI<45 | RSI(14) | 1h–4h | Trending | yes | [jesse example-strategies](https://github.com/jesse-ai/example-strategies) |
| 21 | RSI(2) momentum pop | Connors short-term | RSI2<10 in uptrend (>SMA200) | RSI2>70 or close>SMA5 | RSI(2), SMA(200,5) | 1d | Trend pullback | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 22 | TSI true-strength | Double-smoothed momentum | TSI crosses signal up | TSI below signal | TSI(25,13,7) | 4h | Trending | partial (TSI) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 23 | Awesome Oscillator zero | AO median-momentum | AO crosses above 0 | AO below 0 | AO(5,34) | 1h | Trending | partial (AO≈sma diff) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 24 | Elder Ray power | Bull/bear power vs EMA | BullPower>0 & EMA up | BearPower spike | EMA(13), Bull/Bear power | 4h | Trending | partial | [backtrader](https://www.backtrader.com/) |
| 25 | Momentum breakout (12m) | Time-series momentum | 90-bar return > 0 | return turns negative | ret(90) | 1d | Trending | yes (ret) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 26 | CCI momentum | Commodity channel surge | CCI crosses +100 | CCI < 0 | CCI(20) | 1h–4h | Trending | partial (CCI) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 27 | Stochastic momentum (fast) | %K above %D in trend | %K cross %D up, both<80 | %K>80 cross down | Stoch(14,3,3) | 15m–1h | Trending | partial (stoch≈range) | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 28 | EWO (Elliott Wave Osc) | SMA5-SMA35 momentum | EWO>0 & RSI dip | EWO<0 | EWO(5,35), RSI(14) | 5m–1h | Trending | yes (sma diff) | [NostalgiaForInfinity](https://github.com/iterativv/NostalgiaForInfinity) |
| 29 | Coppock curve | Long-term momentum bottoms | Coppock turns up from below 0 | Coppock turns down | Coppock(14,11,10 WMA) | 1w | Bottom/trend | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |

## 3. Breakout (volatility / range / Bollinger)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 30 | Bollinger breakout | Close beyond upper band | close > BB upper(20,2) | close < BB mid | BB(20,2) | 1h–4h | Volatility expansion | yes (sma+zscore) | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 31 | Bollinger squeeze | Low BB width → expansion | BB width minimum then break up | opposite band / mid | BB(20,2), bandwidth | 1h | Range→breakout | partial (BB width) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 32 | TTM squeeze (BB in KC) | BB inside Keltner = coil | squeeze fires + mom>0 | mom flips | BB(20,2), KC(20,1.5), MOM | 1h–4h | Range→breakout | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 33 | Keltner breakout | Close beyond KC band | close > KC upper | close < KC mid | KC(20,2,ATR10) | 1h | Volatility | partial (ATR band) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 34 | Opening-range breakout | Break of first-N-bar range | break above session/day high | opposite range edge; ATR SL | range_pct, high/low | 5m–15m | Intraday vol | yes (range_pct) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 35 | N-bar high breakout | Rolling high break | close > max(high,20) | close < max(high,10) | rolling max(20/10) | 1h–4h | Trending | yes | [jesse TurtleRules](https://github.com/jesse-ai/example-strategies/blob/master/TurtleRules/__init__.py) |
| 36 | ATR channel breakout | Price beyond ATR envelope | close > EMA + k·ATR | close < EMA | EMA(20), ATR(14), k=2 | 1h | Volatility | yes (ema+atr) | [backtrader](https://www.backtrader.com/) |
| 37 | Volatility-contraction (VCP) | Tightening range then pop | atr_pct at lows then break high | break fails / mid | atr_pct, range_pct, max(high) | 4h–1d | Range→breakout | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 38 | Range box breakout | Horizontal S/R box | close > box top (consolidation) | close < box bottom | rolling high/low(50) | 1h–4h | Range→breakout | yes (range_pct) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 39 | NR7 / inside-day break | Narrowest range bar break | break of NR7 bar high | opposite side | range_pct rank(7) | 1d | Range→breakout | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 40 | Bollinger %B trend-ride | Ride band in trend | %B>0.8 & EMA up | %B<0.5 | BB(20,2) %B, EMA(50) | 1h | Trending | yes | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 41 | Donchian + ATR stop combo | Channel break, vol stop | Donchian-20 high break | 2×ATR trailing stop | Donchian(20), ATR(14) | 4h | Trending | yes | [jesse TurtleRules](https://github.com/jesse-ai/example-strategies/blob/master/TurtleRules/__init__.py) |

## 4. Mean-reversion

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 42 | RSI oversold bounce | Buy dips RSI<30 | RSI(14)<30 | RSI>50 or target +x% | RSI(14) | 15m–4h | Range/chop | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 43 | BB lower-band reversion | Buy at lower band | close < BB lower(20,2) | close ≥ BB mid | BB(20,2) | 15m–1h | Range | yes (zscore) | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 44 | BBRSI combo | BB band + RSI confirm | close<BB lower & RSI<35 | close>BB mid or RSI>65 | BB(20,2), RSI(14) | 1h | Range | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 45 | Z-score reversion | Price z-score extreme | zscore(close,20) < -2 | zscore ≥ 0 | zscore(20) | 1h–4h | Range/mean-revert | yes (zscore) | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 46 | Williams %R reversion | %R oversold | %R < -80 | %R > -20 | Williams %R(14) | 15m–1h | Range | partial (≈range_pct) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 47 | Stochastic oversold | %K/%D both low | %K<20 cross %D up | %K>80 | Stoch(14,3,3) | 15m–1h | Range | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 48 | MA distance reversion | Far below MA snaps back | close < SMA(50)·(1-k) | close ≥ SMA(50) | SMA(50), dist% | 1h–4h | Range | yes (ret vs sma) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 49 | RSI(2) Connors reversion | Ultra-short RSI | RSI2<5 above SMA200 | close>SMA5 | RSI(2), SMA(200,5) | 1d | Trend-dip | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 50 | CCI reversion | CCI extreme fade | CCI < -100 | CCI > 0 | CCI(20) | 1h | Range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 51 | Bollinger %B reversion | %B at 0 fade | %B < 0.05 | %B > 0.5 | BB(20,2) %B | 15m–1h | Range | yes | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 52 | Keltner reversion | Fade KC band touch | close < KC lower | close ≥ KC mid | KC(20,2) | 1h | Range | partial | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 53 | VWAP reversion (intraday) | Revert to VWAP | price < VWAP - k·σ | price ≥ VWAP | VWAP, σ-bands | 5m–1h | Range intraday | partial (VWAP) | [Hummingbot](https://hummingbot.org/strategies/) |
| 54 | RSI mean-revert + trend filter | Dip-buy only in uptrend | RSI<35 & price>SMA200 | RSI>60 | RSI(14), SMA(200) | 1h–4h | Trend pullback | yes | [NostalgiaForInfinity](https://github.com/iterativv/NostalgiaForInfinity) |
| 55 | Fisher transform reversion | Gaussian-ized price extreme | Fisher < -1.5 turns up | Fisher > 1.5 | Fisher(9) | 1h | Range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 56 | Detrended price osc (DPO) | Cycle low fade | DPO at cycle trough | DPO at cycle peak | DPO(20) | 4h | Cyclic/range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 57 | Half-life OU reversion | Ornstein-Uhlenbeck spread | zscore<-entry, sized by half-life | zscore→0 | OU half-life, zscore | 1h–1d | Mean-revert | partial (zscore yes, HL extra) | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |

## 5. DCA (dollar-cost-average) variants

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 58 | Time-based DCA | Buy fixed $ each interval | every N hours/days buy | hold / target % | schedule only | any | Accumulation | partial (no signal) | [OctoBot DCA mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/dca-trading-mode) |
| 59 | Dip-DCA (value averaging) | Buy more when price drops | price down x% → add tranche | target / rebalance | drawdown%, ret | 1h–1d | Accumulation/bear | yes (ret) | [OctoBot DCA mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/dca-trading-mode) |
| 60 | Martingale safety-orders | Scale-in averaging down | each -d% adds bigger order | TP on avg-price +p% | step%, volume scale | 5m–1h | Range/recovery | yes (ret ladder) | [freqtrade adjust_trade_position](https://www.freqtrade.io/en/stable/strategy-callbacks/) |
| 61 | RSI-gated DCA | DCA only when RSI low | scheduled buy if RSI<40 | TP +p% | RSI(14), schedule | 1h | Accumulation | yes | [OctoBot DCA mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/dca-trading-mode) |
| 62 | Smart-DCA (volatility-scaled) | Larger buys on high atr_pct dips | dip & atr_pct high → size up | TP / time | atr_pct, ret | 1h–4h | Accumulation | yes | [OctoBot DCA mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/dca-trading-mode) |
| 63 | Freqtrade position-adjust DCA | Native add-to-position | unrealized<-x% → add | trailing TP | adjust_trade_position cb | 5m–1h | Range/recovery | yes | [freqtrade callbacks](https://www.freqtrade.io/en/stable/strategy-callbacks/) |
| 64 | Grid-DCA hybrid | DCA ladder as buy grid | buy at -2/-4/-6% levels | sell ladder +2/+4% | price grid + averaging | 15m–1h | Range | yes | [OctoBot grid mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/grid-trading-mode) |
| 65 | Trend-DCA (only uptrend) | Accumulate above SMA200 | scheduled buy if close>SMA200 | rebalance | SMA(200), schedule | 1d | Bull accumulation | yes | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |

## 6. Grid trading

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 66 | Static grid | Fixed buy/sell levels | buy each grid step down | sell each step up | grid range, n levels | any | Range/sideways | partial (price-level engine) | [OctoBot grid mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/grid-trading-mode) |
| 67 | Geometric grid | %-spaced levels | buy at each -g% | sell at each +g% | geometric spacing | any | Range | partial | [Hummingbot Grid Strike](https://hummingbot.org/strategies/) |
| 68 | ATR-adaptive grid | Grid spacing = k·ATR | levels k·ATR apart | symmetric TP | ATR(14), k | 15m–1h | Range w/ vol | yes (atr-spaced) | [OctoBot grid mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/grid-trading-mode) |
| 69 | Bollinger grid | Grid bounded by BB | buy lower-band levels | sell upper-band levels | BB(20,2) bounds | 1h | Range | partial | [OctoBot grid mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/grid-trading-mode) |
| 70 | Grid Strike (executors) | Grid w/ per-level TP/SL | grid within price range | per-level TP & range SL | StrategyV2 executors | 5m–1h | Range | partial | [Hummingbot Grid Strike](https://hummingbot.org/strategies/) |
| 71 | Trend-following grid | Shift grid with EMA | grid recenters on EMA | range exit | EMA(50) center, grid | 15m–1h | Drift+range | partial | [OctoBot grid mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/grid-trading-mode) |

## 7. Scalping

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 72 | EMA scalp (5/13) | Fast micro-trend | EMA5 cross EMA13 up | reverse / +0.3% TP, tight SL | EMA(5,13) | 1m–5m | Intraday trend | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 73 | Bollinger scalp | Band-touch quick fade | close<BB lower(20,2) | BB mid; SL 0.5% | BB(20,2) | 1m–5m | Range intraday | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 74 | RSI scalp | RSI micro-extremes | RSI(7)<25 | RSI>55 | RSI(7) | 1m–5m | Range | yes | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 75 | Stoch-RSI scalp | Double-smoothed extreme | StochRSI<0.2 cross up | StochRSI>0.8 | StochRSI(14,14,3,3) | 1m–5m | Range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 76 | VWAP scalp | Fade/ride intraday VWAP | cross VWAP w/ rvol spike | +0.3% / VWAP touch | VWAP, rvol | 1m–5m | Intraday | partial (VWAP), rvol yes | [Hummingbot](https://hummingbot.org/strategies/) |
| 77 | Micro market-making (PMM) | Quote both sides at spread | place bid/ask at ±spread | refresh order_refresh_time | bid/ask spread, refresh | tick/1m | Range/liquid | partial (orderbook) | [Hummingbot PMM](https://hummingbot.org/strategies/v1-strategies/pure-market-making/) |
| 78 | Avellaneda-Stoikov MM | Inventory-aware quotes | reservation price ± optimal spread | inventory rebalance | A&S γ,σ,T params | tick/1m | Range/liquid | partial (orderbook+vol) | [Hummingbot A&S](https://hummingbot.org/blog/technical-deep-dive-into-the-avellaneda--stoikov-strategy/) |

## 8. MACD systems

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 79 | MACD signal cross | Line over signal | MACD line cross above signal | cross below | MACD(12,26,9) | 1h–4h | Trending | partial (ema diff) | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 80 | MACD zero cross | Histogram zero line | MACD crosses above 0 | crosses below 0 | MACD(12,26,9) | 4h | Trending | partial | [MACDZeroCross](https://github.com/freqtrade/freqtrade-strategies) |
| 81 | MACD histogram momentum | Rising histogram | hist > 0 and increasing | hist decreasing | MACD hist | 1h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 82 | MACD + RSI filter | Cross gated by RSI | MACD cross up & RSI>50 | MACD cross down | MACD(12,26,9), RSI(14) | 1h–4h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 83 | MACD + 200EMA trend | Only longs in uptrend | MACD cross up & close>EMA200 | MACD cross down | MACD, EMA(200) | 4h | Trending | partial | [jesse example-strategies](https://github.com/jesse-ai/example-strategies) |
| 84 | MACD divergence | Price LL, MACD HL | bullish divergence confirmed | signal cross down | MACD(12,26,9), pivots | 1h–4h | Reversal | partial (divergence) | [freqtrade/technical](https://github.com/freqtrade/technical) |

## 9. Ichimoku

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 85 | Ichimoku cloud breakout | Price above Kumo | close above cloud, Tenkan>Kijun | close below cloud | Ichimoku(9,26,52) | 4h–1d | Trending | no (cloud structure) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 86 | Tenkan/Kijun cross | TK cross signal | Tenkan cross above Kijun above cloud | TK cross down | Ichimoku(9,26) | 1h–4h | Trending | no | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 87 | Kumo twist | Future-cloud color flip | Senkou A crosses above B + price>cloud | twist bearish | Ichimoku(9,26,52) | 4h | Trend reversal | no | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 88 | Chikou confirmation | Lagging span free of price | Chikou above price 26 ago + cloud break | Chikou below price | Ichimoku full | 1d | Trending | no | [freqtrade/technical](https://github.com/freqtrade/technical) |

## 10. Heikin-Ashi systems

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 89 | HA trend color | Consecutive green HA | 2+ green HA candles, no lower wick | first red HA | Heikin-Ashi candles | 1h–4h | Trending | partial (HA transform) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 90 | HA + EMA | Smoothed trend gate | green HA & close>EMA50 | red HA | HA, EMA(50) | 4h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 91 | HA + MACD | HA color w/ MACD | green HA & MACD>signal | red HA / cross | HA, MACD(12,26,9) | 1h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 92 | Smoothed HA (double) | Smoothed-HA on smoothed-HA | smooth-HA flips bullish | flips bearish | EMA-smoothed HA(6) | 4h | Trending | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |

## 11. Multi-timeframe confirmation

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 93 | HTF trend + LTF entry | Daily trend, hourly trigger | 1d EMA up & 1h RSI dip | 1h RSI>60 | EMA(50)@1d, RSI@1h | 1h+1d | Trending | partial (multi-TF) | [freqtrade informative pairs](https://www.freqtrade.io/en/stable/strategy-customization/) |
| 94 | Triple-screen (Elder) | Tide/wave/ripple | weekly trend↑, daily osc dip, intraday trigger | daily osc overbought | EMA weekly, MACD daily, Stoch | multi | Trending | partial | [backtrader](https://www.backtrader.com/) |
| 95 | 4h regime + 15m entry | Regime gate + scalp | 4h SMA200 up & 15m breakout | 15m reverse | SMA(200)@4h, breakout@15m | 15m+4h | Trending | partial | [freqtrade-strategies](https://github.com/freqtrade/freqtrade-strategies) |
| 96 | MTF RSI alignment | RSI agree across TFs | RSI@1h & @4h both >50 | either <45 | RSI(14)@1h/4h | 1h+4h | Trending | partial | [freqtrade informative](https://www.freqtrade.io/en/stable/strategy-customization/) |
| 97 | MTF Supertrend stack | ST agree on 3 TFs | ST bullish @15m/1h/4h | any flips | Supertrend@3 TFs | multi | Trending | partial | [PeetCrypto/freqtrade-stuff](https://github.com/PeetCrypto/freqtrade-stuff) |

## 12. RSI-divergence

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 98 | RSI bullish divergence | Price LL, RSI HL | confirmed bullish div + close up | RSI>60 / target | RSI(14), swing pivots | 1h–4h | Reversal | partial (divergence) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 99 | RSI hidden divergence | Trend-continuation div | price HL, RSI LL in uptrend | trend break | RSI(14), pivots | 1h–4h | Trend pullback | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 100 | OBV/MACD divergence | Volume/momentum div | OBV makes HL vs price LL | confirm reversal | OBV or MACD, pivots | 4h | Reversal | partial | [freqtrade/technical](https://github.com/freqtrade/technical) |

## 13. Volume profile / OBV / VWAP

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 101 | OBV trend confirm | OBV rising = accumulation | OBV>OBV-MA & price breakout | OBV<MA | OBV, SMA(OBV,20) | 1h–4h | Trending | partial (OBV) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 102 | VWAP trend ride | Hold above VWAP | close>VWAP & rvol>1.5 | close<VWAP | VWAP, rvol | 5m–1h | Intraday trend | partial (VWAP), rvol yes | [Hummingbot](https://hummingbot.org/strategies/) |
| 103 | Anchored VWAP breakout | AVWAP from swing low | break above AVWAP | back below AVWAP | Anchored VWAP | 1h–1d | Trending | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 104 | Volume-profile POC reversion | Fade value-area edges | price at VAL → buy | back to POC | Volume Profile (POC/VAH/VAL) | 1h–4h | Range | no (profile build) | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 105 | Volume breakout (rvol) | Vol spike confirms break | breakout & rvol>2 | rvol fades / mid | rvol, range_pct | 15m–1h | Breakout | yes (rvol+range_pct) | [freqtrade VolumePairList](https://github.com/freqtrade/freqtrade) |
| 106 | Money Flow Index | Volume-weighted RSI | MFI<20 oversold (range) | MFI>80 | MFI(14) | 1h | Range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 107 | Chaikin Money Flow | Accumulation/distribution | CMF crosses above 0 | CMF below 0 | CMF(20) | 4h | Trending | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 108 | A/D line trend | Accum-distribution slope | A/D rising + price trend | A/D falling | Accum/Dist line | 4h | Trending | partial | [backtrader](https://www.backtrader.com/) |

## 14. Pivot points

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 109 | Classic pivot bounce | Buy at S1 support | price at S1 holds | back to PP / R1 | Pivot (PP,S1,R1) | 15m–1h | Range intraday | partial (pivot calc) | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 110 | Pivot breakout | Break R1 resistance | close > R1 | R2 target / PP SL | Pivot R1/R2 | 15m–1h | Breakout | partial | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 111 | Camarilla pivots | Tight intraday levels | reversal at L3/H3 | mean / next level | Camarilla H1-4/L1-4 | 5m–1h | Range | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |

## 15. Pairs / cointegration (BTC-ETH etc.)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 112 | BTC-ETH spread z-score | Cointegrated spread revert | spread z<-2 long ETH | z→0 | hedge ratio, zscore(20) | 1h–1d | Mean-revert | partial (2-asset, zscore yes) | [coderaashir/Crypto-Pairs-Trading](https://github.com/coderaashir/Crypto-Pairs-Trading) |
| 113 | Ratio mean-reversion | Asset-ratio band fade | ratio z<-2 | ratio z→0 | A/B ratio, zscore | 1h–4h | Mean-revert | partial | [fraserjohnstone/pairs-trading-backtest](https://github.com/fraserjohnstone/pairs-trading-backtest-system) |
| 114 | Cointegration-selected pairs | Engle-Granger filter then trade | spread beyond entry band | revert/stop-loss z | ADF/Johansen, zscore | 1h–1d | Mean-revert | partial (extra coint test) | [QuantConnect Pairs](https://github.com/QuantConnect/Research/blob/master/Analysis/05%20Pairs%20Trading%20Strategy%20Based%20on%20Cointegration.ipynb) |
| 115 | Kalman dynamic hedge pairs | Time-varying beta spread | Kalman spread z extreme | revert | Kalman filter, zscore | 1h–1d | Mean-revert | partial | [abailey81/Crypto-Statistical-Arbitrage](https://github.com/abailey81/Crypto-Statistical-Arbitrage) |
| 116 | Triangular ratio basket | 3-asset relative value | basket spread extreme | revert to fair | multi-asset weights, zscore | 1h–4h | Mean-revert | partial | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |

## 16. Market-regime switching

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 117 | ADX regime switch | Trend vs range router | ADX>25→trend rules; <20→MR rules | per sub-strategy | ADX(14) router | 1h–4h | Adaptive | partial (ADX gate) | [freqtrade/technical](https://github.com/freqtrade/technical) |
| 118 | Volatility-regime switch | atr_pct selects mode | high atr_pct→breakout; low→grid/MR | per mode | atr_pct percentile | 1h–4h | Adaptive | yes (atr_pct gate) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 119 | BB-width regime | Squeeze vs expansion | width low→MR; expanding→trend | per mode | BB width percentile | 1h | Adaptive | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |
| 120 | HMM/choppiness regime | Choppiness index router | CHOP<38→trend; >62→range | per mode | Choppiness(14) | 4h | Adaptive | partial | [pandas-ta](https://github.com/twopirllc/pandas-ta) |

## 17. On-chain-triggered (partial — external feed)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 121 | Exchange-netflow signal | Outflows = accumulation | net exchange outflow + price>EMA50 | inflow spike | on-chain netflow + EMA(50) | 1d | Bull accumulation | no (on-chain feed) | [OctoBot evaluators](https://www.octobot.cloud/en/guides/octobot-trading-modes/trading-modes) |
| 122 | MVRV / NUPL z-score | Valuation extremes | MVRV-Z low → accumulate | MVRV-Z high | MVRV-Z, NUPL | 1d–1w | Macro cycle | no (on-chain) | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 123 | SOPR / active-address trend | Profit-taking + adoption | SOPR>1 reset + addr rising | SOPR<1 | SOPR, active addresses | 1d | Cycle | no (on-chain) | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |

## 18. Sentiment / Fear & Greed-triggered (partial — external feed)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 124 | Fear & Greed contrarian | Buy extreme fear | F&G < 20 (extreme fear) | F&G > 75 (greed) | Alternative.me F&G index | 1d | Contrarian/cycle | no (sentiment feed) | [OctoBot evaluators](https://www.octobot.cloud/en/guides/octobot-trading-modes/trading-modes) |
| 125 | F&G + trend filter | Fear dip in uptrend | F&G<30 & close>SMA200 | F&G>70 | F&G, SMA(200) | 1d | Trend+contrarian | no (sentiment; SMA part yes) | [OctoBot evaluators](https://www.octobot.cloud/en/guides/octobot-trading-modes/trading-modes) |
| 126 | Social/AI sentiment | LLM/social score signal | sentiment score > threshold | score reverses | social/ChatGPT evaluator | 1h–1d | Event-driven | no (sentiment feed) | [OctoBot ChatGPT mode](https://www.octobot.cloud/en/guides/octobot-trading-modes/chatgpt-trading) |

## 19. Rotation (top-N momentum basket)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime fit | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|-----------|--------|--------|
| 127 | Top-N momentum rotation | Hold strongest N coins | rank by ret(90), hold top 5 | rebalance weekly, drop out of top-N | ret(30/90) ranking | 1d–1w | Trending bull | yes (ret rank) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 128 | Dual-momentum (abs+rel) | Trend-gate + relative rank | top-N AND ret>0 vs cash | ret<0 → exit to stable | ret(90), abs filter | 1w | Bull/defensive | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 129 | Risk-parity vol-weighted basket | Inverse-vol weights | rebalance to 1/vol weights | periodic rebalance | vol(30), atr_pct | 1w | All (diversified) | yes (vol weights) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |
| 130 | Sharpe/Sortino-ranked rotation | Risk-adjusted momentum | top-N by rolling Sharpe | drop below rank | ret, vol (Sharpe) | 1w | Trending | yes | [awesome-quant](https://github.com/wilsonfreitas/awesome-quant) |
| 131 | BTC-dominance rotation | Alt/BTC regime rotate | dominance falling→alts; rising→BTC | regime flip | BTC.D ret, ret rank | 1d–1w | Alt-season | partial (BTC.D extra) | [QuantConnect/Lean](https://github.com/QuantConnect/Lean) |

---

## Genome-mappability summary
- **yes (direct T8 genome):** ~52 templates — pure {ret, sma, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol} + threshold/crossover ops. Implement first.
- **partial (one derived series / multi-TF / 2-asset / extra computed indicator):** ~62 — Supertrend/Keltner/PSAR bands, MACD/AO/EWO diffs, BB-width, Stoch/CCI/%R/MFI, OBV/VWAP, pivots, divergence, pairs/cointegration, ADX gates. Add as engineered features.
- **no (external feed or non-mappable structure):** ~17 — Ichimoku cloud, volume-profile POC, full order-book MM, all on-chain (121-123) and sentiment/F&G (124-126).

## Top OSS sources (reuse-first, ranked)
1. **freqtrade / freqtrade-strategies + NostalgiaForInfinity + freqtrade/technical** — largest battle-tested crypto-spot strategy corpus (GPLv3). https://github.com/freqtrade/freqtrade-strategies · https://github.com/iterativv/NostalgiaForInfinity
2. **jesse-ai/example-strategies** — clean reference impls (Turtle, RSI). https://github.com/jesse-ai/example-strategies
3. **OctoBot (Drakkar-Software)** — DCA, Grid, basket, sentiment/AI evaluator modes. https://github.com/Drakkar-Software/OctoBot
4. **Hummingbot** — grid (Grid Strike), PMM, Avellaneda-Stoikov, cross-exchange MM. https://hummingbot.org/strategies/
5. **QuantConnect/Lean + awesome-quant + pandas-ta** — rotation, pairs/cointegration, indicators library. https://github.com/QuantConnect/Lean · https://github.com/wilsonfreitas/awesome-quant · https://github.com/twopirllc/pandas-ta

---
**Total templates: 131** (families: trend-following, momentum, breakout, mean-reversion, DCA, grid, scalping, MACD, Ichimoku, Heikin-Ashi, multi-timeframe, RSI-divergence, volume/OBV/VWAP, pivot, pairs/cointegration, regime-switching, on-chain, sentiment/F&G, rotation).
