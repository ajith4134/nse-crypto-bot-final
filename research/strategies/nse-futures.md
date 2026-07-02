# NSE Futures Trading Strategy Templates
Curated, deduped library of proven NIFTY/BANKNIFTY/FINNIFTY index-futures & stock-futures templates (intraday + positional NRML), each tagged with genome-mappability for our TA-Lib feature genome (ret/sma/ema/rsi/atr/atr_pct/mom/vol/zscore/range_pct/rvol + threshold/crossover ops).

> Genome legend: **yes** = expressible purely with our features+operators. **partial** = needs one extra data series (OI, basis/spot, multi-symbol, rollover %) but logic is rule-based. **no** = discretionary / needs order-book / event-calendar / non-mappable structure.

---

## 1. Trend-Following (EMA / Supertrend / ADX / Donchian)

| # | Name | Core logic | Entry | Exit (SL/Tgt/Trail) | Indicators+params | TF | Regime fit | Source | Genome |
|---|------|-----------|-------|--------------------|-------------------|----|-----------|--------|--------|
| 1 | EMA 9/21 crossover (index fut) | Fast/slow EMA cross signals trend | Long when EMA9 crosses above EMA21; short on reverse | SL = swing low/ATR; trail EMA21; exit on opposite cross | EMA9, EMA21 | 15m | Trending | Zerodha Varsity TA; pandas-ta | yes |
| 2 | EMA 20/50/200 stack | Multi-EMA alignment = strong trend | Long when EMA20>EMA50>EMA200 & price>EMA20 | Exit when EMA20 crosses below EMA50; SL 1.5×ATR | EMA20/50/200 | 1h/1d | Strong trend | backtrader, freqtrade | yes |
| 3 | Supertrend flip (BANKNIFTY) | Supertrend ATR band direction | Long on green flip, short on red flip | Exit on opposite flip; SL = Supertrend line | Supertrend(10,3) | 15m | Trending, high-vol | Zerodha Varsity supplementary; TradingView | partial (Supertrend≈ATR band, approximable) |
| 4 | Supertrend + EMA200 filter | Trade Supertrend only with HTF bias | Long flip only if price>EMA200 | Opposite flip or EMA200 break | Supertrend(10,3), EMA200 | 15m/1h | Trend, filters chop | TradingView scripts | partial |
| 5 | ADX trend-strength gate | Trade direction only when ADX strong | Long if +DI>-DI & ADX>25 & price>EMA20 | ADX<20 exit or DI cross; SL ATR | ADX(14), DI, EMA20 | 1h/1d | Trend onset | Zerodha Varsity ADX | partial (ADX not in core; proxy via mom+atr) |
| 6 | Donchian 20 breakout (Turtle) | Channel breakout trend entry | Long on close > 20-bar high; short < 20-bar low | Exit on 10-bar opposite Donchian; SL 2×ATR | Donchian20/10, ATR(20) | 1d | Trending/positional | Turtle system; backtrader | yes (range_pct/rolling max via threshold) |
| 7 | Donchian 55 slow trend | Longer channel for positional fut | Long > 55-bar high | Exit 20-bar low; ATR stop | Donchian55/20 | 1d | Strong positional trend | Turtle; awesome-quant | yes |
| 8 | SMA 50/200 golden/death cross | Classic LT trend regime | Long on golden cross, flat/short on death cross | Opposite cross | SMA50, SMA200 | 1d | Macro trend | backtrader docs | yes |
| 9 | Triple EMA (TEMA) trend | Reduced-lag EMA trend follow | Long when price>TEMA & TEMA rising | TEMA turns down; ATR trail | TEMA(21) | 15m/1h | Trending | pandas-ta | partial (TEMA≈ema, approximable) |
| 10 | HMA trend ride | Hull MA slope direction | Long when HMA slope>0; short slope<0 | Slope flip; chandelier exit | HMA(34) | 1h | Smooth trend | pandas-ta | partial |
| 11 | Linear-regression slope trend | Trade sign of LR slope | Long if LR(50) slope>0 & price>LR line | Slope sign flip | LinReg slope(50) | 1h/1d | Trend | QuantConnect indicators | partial (zscore proxy) |
| 12 | Heikin-Ashi trend persistence | Smoothed candles = stay in trend | Long after N consecutive HA-green bodies | First opposite HA body close; ATR SL | HA candles | 15m | Trending | freqtrade strategies | no (needs HA transform) |
| 13 | EMA ribbon expansion | Widening EMA ribbon = momentum trend | Long when ribbon (8/13/21/34) fans up | Ribbon compression/cross | EMA8/13/21/34 | 15m/1h | Trend acceleration | TradingView ribbon | yes |
| 14 | Supertrend dual-timeframe | HTF Supertrend bias + LTF entry | Long when 1h ST green & 15m ST green | 15m ST red exit | Supertrend(10,3) ×2 TF | 15m+1h | Trend | TradingView | partial |
| 15 | PSAR trend trail | Parabolic SAR flips as trend follow | Long when price>PSAR; short below | PSAR dot flip (built-in trail) | PSAR(0.02,0.2) | 15m/1h | Trending | pandas-ta | partial (PSAR not core) |

## 2. Momentum

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 16 | ROC momentum (12-day) | Rate-of-change positive momentum | Long when ROC(12)>0 & rising | ROC<0; ATR SL | ROC/mom(12) | 1d | Trending | pandas-ta; AQR momentum lit | yes (mom) |
| 17 | RSI momentum (not overbought) | Strong RSI without extreme | Long when RSI(14) crosses above 60 | RSI<50; trail | RSI(14) | 15m/1h | Trend/momentum | Zerodha Varsity RSI | yes (rsi) |
| 18 | Dual-momentum (12-1) | 12-mo less recent month rel-strength | Long top-ranked fut; rotate monthly | Rank falls below threshold | mom(252), mom(21) | 1d | Trending | Antonacci dual momentum | partial (cross-sectional rank) |
| 19 | MACD histogram momentum | Histogram acceleration | Long when MACD line crosses signal up | Hist turns negative | MACD(12,26,9) | 1h | Trend onset | pandas-ta | partial (MACD≈ema diff, approximable) |
| 20 | TSI momentum | True Strength Index zero-cross | Long TSI>0; short<0 | Zero cross | TSI(25,13) | 1h | Momentum | pandas-ta | partial |
| 21 | Relative-strength vs NIFTY | Stock fut outperforming index | Long stock fut when RS line makes new high | RS rolls over | ratio stock/NIFTY, mom | 1d | Trend/rotation | QuantConnect RS | partial (needs index series) |
| 22 | 52-week-high momentum | Buy fut near 52w high breakout | Long when price within 2% of 52w high & mom>0 | Below 50d EMA | rolling max(252), EMA50 | 1d | Bull trend | momentum lit | yes |
| 23 | Awesome Oscillator momentum | AO saucer / zero-cross | Long on AO zero-cross up | AO<0 | AO(5,34 median) | 15m/1h | Momentum | pandas-ta | partial |
| 24 | CCI momentum breakout | CCI exits +100 with thrust | Long when CCI crosses above +100 | CCI<0; ATR SL | CCI(20) | 15m/1h | Trend thrust | pandas-ta | partial |
| 25 | Momentum + vol filter | Momentum only on rising volume | Long when mom(20)>0 & rvol>1.5 | mom<0 or rvol fades | mom(20), rvol | 15m | Trend w/ participation | freqtrade | yes (mom, rvol) |

## 3. Breakout

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 26 | Opening-range breakout (ORB) | First 15/30m range break | Long > ORB high, short < ORB low | SL other side of ORB; tgt 1×ORB width; trail | ORB(15m/30m), range_pct | 5m/15m | Trending day | Quantzee NIFTY blueprint | yes (range_pct + threshold) |
| 27 | Previous-day high/low break | PDH/PDL breakout | Long > PDH; short < PDL | Opposite level; ATR trail | PDH, PDL | 15m | Expansion day | OneTradeJournal | yes |
| 28 | N-bar high breakout | Rolling X-bar high break | Long on close > prior 20-bar high | 10-bar low; ATR SL | rolling max(20) | 15m/1h | Trend onset | backtrader | yes |
| 29 | Bollinger band breakout | Close outside upper band = expansion | Long > upper BB(20,2) with rvol | Re-enter band / mid-band | BB(20,2), rvol | 15m/1h | Volatility expansion | pandas-ta | partial (BB≈sma±k·std; zscore proxy) yes-ish |
| 30 | Keltner channel breakout | Close beyond ATR-based KC | Long > KC upper(20,2×ATR) | Mid KC; ATR trail | EMA20, ATR(20) | 15m/1h | Expansion | pandas-ta | yes (ema+atr) |
| 31 | Squeeze breakout (TTM) | BB inside KC then expansion fire | Long when squeeze releases up | Momentum fade; ATR | BB(20,2), KC(20,1.5) | 15m | Low->high vol | TTM Squeeze; pandas-ta | partial |
| 32 | Inside-bar breakout | Mother-bar range break | Long > inside-bar high | Opposite extreme | range_pct, prior bar H/L | 15m/1d | Compression | price-action lit | yes |
| 33 | NR7 breakout | Narrowest range in 7 bars then break | Long > NR7 bar high | ATR SL; 2R tgt | range_pct rank(7) | 1d/15m | Vol expansion | Crabel; backtrader | yes |
| 34 | Volatility contraction pattern | Successive tightening then break | Long on breakout from VCP base | Base low SL | range_pct, atr_pct decline | 1d | Pre-trend coil | Minervini VCP | partial |
| 35 | Round-number breakout | Psychological level break (e.g. BNF 50000) | Long > round level + buffer with rvol | Back below level | price level, rvol | 5m/15m | Momentum day | trader heuristics | yes |
| 36 | First-hour high/low break | Break of 9:15-10:15 range | Long > first-hour high | EOD/15:15 or opp level | session range_pct | 15m | Trending day | Quantzee | yes |
| 37 | Gap-and-go breakout | Gap day breaks opening high | Long > day-open-range high after gap up | ORB SL; trail | gap%, ORB | 5m/15m | Momentum gap day | OneTradeJournal | partial (gap = prev close vs open) |

## 4. Mean-Reversion

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 38 | RSI(2) reversion | Connors short-term oversold | Long when RSI2<10 & price>SMA200 | RSI2>70 or SMA5 cross | RSI(2), SMA200, SMA5 | 1d | Range/pullback in trend | Connors; backtrader | yes |
| 39 | Bollinger reversion | Fade band touches to mean | Long at lower BB(20,2); short at upper | Mid-band; SL beyond band | BB(20,2) | 15m/1h | Range-bound | pandas-ta | partial (zscore proxy) yes |
| 40 | Z-score reversion | Fade price z-score extremes | Long when zscore(close,20) < -2 | zscore→0; SL -3 | zscore(20) | 15m/1h | Mean-reverting | QuantConnect | yes (zscore) |
| 41 | VWAP reversion (intraday) | Fade stretch from VWAP | Long when price < VWAP-2σ band | Back to VWAP | VWAP, std band | 5m/15m | Range day | OneTradeJournal | partial (VWAP needs vol) |
| 42 | Williams %R oversold | Fade -90 extremes | Long when %R crosses up from <-90 | %R>-50 | Williams%R(14) | 15m | Range | pandas-ta | partial |
| 43 | Stochastic reversion | Fade %K extremes in range | Long when %K<20 crosses %D up | %K>80 | Stoch(14,3,3) | 15m/1h | Range | pandas-ta | partial |
| 44 | Gap-fill reversion | Price reverts to fill open gap | Fade gap-up open toward prev close | Prev close (gap filled) | gap%, prev close | 5m/15m | Non-trending open | gap lit | partial |
| 45 | CCI reversion | Fade CCI<-100 / >+100 | Long when CCI crosses up from <-100 | CCI→0 | CCI(20) | 15m | Range | pandas-ta | partial |
| 46 | Mean reversion to EMA20 | Buy dips to rising EMA in uptrend | Long when price tags EMA20 & trend up | EMA50 break / target prior high | EMA20, EMA50 | 15m/1h | Trend pullback | freqtrade | yes |
| 47 | ATR-band fade | Fade close beyond N×ATR from VWMA | Long when close < MA - 2.5×ATR | Back to MA | SMA20, ATR(20) | 15m | Range | pandas-ta | yes (sma+atr) |
| 48 | RSI divergence reversal | Price LL but RSI HL | Long on bullish RSI divergence + confirm | Prior swing high; SL below LL | RSI(14), swing pivots | 1h | Range/reversal | Varsity RSI | no (divergence pattern) |
| 49 | Overnight reversion (positional) | Fade large single-day move next session | Short fut after +3σ day, long after -3σ | Revert to 5d mean | ret zscore(daily) | 1d | Overreaction | mean-rev lit | yes |

## 5. VWAP-Based

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 50 | VWAP trend (above/below) | Bias long above VWAP, short below | Long when price reclaims VWAP w/ momentum | VWAP loss; 15:15 close | VWAP | 5m/15m | Intraday trend | OneTradeJournal | partial |
| 51 | VWAP bounce | Buy pullback to VWAP in uptrend | Long on VWAP touch + bullish candle | Prior high; SL below VWAP | VWAP, EMA20 | 5m/15m | Trending day | TraderRahulPal TradingView | partial |
| 52 | VWAP + Supertrend combo | ST signal confirmed by VWAP side | Long when ST green & price>VWAP | ST red or 15:15 | Supertrend(10,3), VWAP | 15m | Trending intraday | gwcindia blog | partial |
| 53 | VWAP + pivot combo | VWAP confluence with pivot zone | Long at VWAP∩pivot support bounce | Central pivot / R1 | VWAP, floor pivots | 5m/15m | Range/trend | learntotrade365 | partial |
| 54 | Anchored VWAP from swing | AVWAP from major pivot as S/R | Long on reclaim of AVWAP anchored at swing low | AVWAP loss | Anchored VWAP | 15m/1h | Trend continuation | TradingView AVWAP | partial |
| 55 | VWAP std-dev band breakout | Break of VWAP+2σ = momentum | Long > VWAP+2σ with rvol | Back inside band | VWAP±2σ, rvol | 5m/15m | Expansion day | scribd VWAP scalping | partial |
| 56 | VWAP scalp (BANKNIFTY) | Fast scalps around VWAP | Long micro-pullback to VWAP, quick tgt | 0.3-0.5% tgt; tight SL | VWAP | 1m/3m | Liquid intraday | scribd ST-10.1.2 | partial |
| 57 | Multi-day VWAP (weekly) | Rolling weekly VWAP for swing fut | Long above weekly VWAP, add on tags | Weekly VWAP break | rolling VWAP(week) | 1h/1d | Swing trend | TradingView | partial |

## 6. CPR / Pivots

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 58 | Narrow CPR trend day | Narrow central pivot range → big move | Long > TC (top central) breakout | R1/R2 targets; SL below CPR | CPR (pivot,BC,TC) | 15m | Trend day | floor-pivot lit; gwcindia | partial (CPR from prev OHLC, computable) |
| 59 | Wide CPR range day | Wide CPR → mean-revert between levels | Fade R1 short / S1 long | Central pivot | CPR | 15m | Range day | floor-pivot lit | partial |
| 60 | Floor pivot bounce | Buy S1/S2 support, sell R1/R2 | Long bounce at S1 w/ confirm | Pivot/R1 | Pivots P,S1-3,R1-3 | 15m | Range | classic pivots | partial |
| 61 | Pivot breakout | Break & hold above R1 = trend | Long sustained > R1 | R2/R3; SL pivot | Floor pivots | 15m | Trend day | classic | partial |
| 62 | Camarilla intraday | Tight H3/L3 reversal, H4/L4 breakout | Fade L3 long; break H4 momentum | H3/central | Camarilla levels | 5m/15m | Range or trend | Camarilla lit | partial |
| 63 | Pivot + RSI confluence | Pivot S/R with RSI extreme | Long S1 + RSI<30 | Central pivot | Pivots, RSI(14) | 15m | Range | trader heuristics | partial |
| 64 | Weekly pivot (positional fut) | Weekly pivots for swing levels | Long > weekly R1 hold | Weekly R2; SL weekly P | Weekly pivots | 1h/1d | Swing | classic | partial |
| 65 | CPR two-day overlap | Overlapping CPR = sideways; trade range | Fade edges when CPRs overlap | Opposite edge | CPR ×2 days | 15m | Consolidation | floor-pivot lit | partial |

## 7. Volatility Breakout / ATR Channel

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 66 | ATR channel breakout | Close beyond MA±k·ATR | Long > SMA20 + 2×ATR | Mid; chandelier trail | SMA20, ATR(20) | 15m/1h | Vol expansion | backtrader | yes |
| 67 | Chandelier exit trend | ATR trailing stop from extreme | Enter on trend; trail = HH - 3×ATR | Chandelier hit | ATR(22)×3 | 1h/1d | Trend | Le Beau; pandas-ta | yes |
| 68 | Volatility-adjusted breakout (Crabel) | Open ± k×prior range | Long > open + 0.5×prevRange | Prior bar; ATR SL | range_pct, open | 15m | Expansion | Crabel ORB | yes |
| 69 | ATR% regime switch | High atr_pct → breakout mode | Take breakouts only when atr_pct>median | regime flips low | atr_pct(14) | 15m/1h | Vol regime | quant lit | yes (atr_pct) |
| 70 | Low-vol coil → breakout | atr_pct at lows precedes expansion | Long on first thrust after atr_pct trough | ATR trail | atr_pct percentile | 1h/1d | Vol cycle | quant lit | yes |
| 71 | Bollinger band-width expansion | BBW from low → directional break | Long on BBW expansion + close>upper | BBW contracts | BBW(20,2) | 15m | Squeeze release | pandas-ta | partial |
| 72 | Volatility stop trend | Wilder volatility stop trailing | Enter trend; trail vol stop | Vol stop flip | ATR(14)×3 | 1h | Trend | pandas-ta | yes |
| 73 | Range-expansion day filter | Trade only days where range_pct>1.5× avg | Direction by ORB on expansion days | EOD | range_pct, rvol | 15m | Expansion | Crabel | yes |

## 8. Basis / Cost-of-Carry / Calendar Spread

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 74 | Basis mean-reversion | Fut-spot basis reverts to fair carry | Short fut/long spot when basis > fair+band | Basis → fair | basis=fut-spot, carry | 1d/intraday | Any (arb) | Zerodha Varsity calendar; 5paisa | partial (needs spot series) |
| 75 | Cost-of-carry richness | Trade when annualized carry extreme | Sell rich premium (carry≫repo) | Carry normalizes | basis, days-to-expiry, r | 1d | Carry dislocation | 5paisa rollover | partial |
| 76 | Calendar spread (near-far) | Spread between near & next month | Long near/short far when spread>upper band | Spread reverts to mean | near-far px, zscore | 1d | Range/arb | Varsity calendar spreads | partial (2 series) |
| 77 | Calendar spread z-score | Trade spread z vs rolling band | Enter when spread z>±2 | z→0 | spread zscore(N) | 1d | Mean-rev arb | Varsity; QuantStrategy.io | partial |
| 78 | Contango/backwardation tilt | Direction from term-structure sign | Long fut in backwardation roll-yield | Structure flips | basis sign, slope | 1d | Term-structure | QuantStrategy.io contango | partial |
| 79 | Dividend-adjusted basis | Stock-fut basis cheap around ex-div | Long fut when basis < spot - PV(div) | Convergence | basis, dividend cal | 1d | Event/arb | carry lit | no (needs div calendar) |
| 80 | Intraday basis scalp | Fut leads/lags spot intraday | Trade fut on basis spike vs VWAP basis | Basis normalizes | basis tick, VWAP | 1m/5m | Liquid hours | HFT arb lit | no (tick data) |
| 81 | Synthetic vs futures parity | Fut vs synthetic (call-put) mispricing | Arb when fut ≠ synthetic forward | Convergence | fut, C-P, strike | intraday | Arb | put-call parity | no (options chain) |

## 9. Rollover / Expiry-Week

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 82 | Rollover % trend confirm | >85% rollover = strong conviction | Trade with trend if rollover% high & rising | Trend break | rollover%, OI | 1d (expiry wk) | Trend confirm | 5paisa; Angel One | partial (rollover series) |
| 83 | Low-rollover fade | <70% rollover = positions closing | Fade prevailing trend on weak rollover | Reversal target | rollover%, OI | 1d | Trend exhaustion | 5paisa | partial |
| 84 | Rollover-cost spread signal | Widening next-month premium = bullish | Long when roll spread expands vs avg | Spread narrows | roll spread, basis | 1d | Positioning | 5paisa; niftytrader | partial |
| 85 | Expiry-day pinning fade | Index gravitates to max-pain near close | Fade extremes toward max-pain on expiry | Max-pain zone | OI max-pain, price | expiry day | Expiry | options OI lit | no (full chain) |
| 86 | Expiry-week volatility crush | Vol compresses into Thu expiry | Range/mean-rev bias expiry afternoon | EOD | atr_pct, day-to-expiry | 15m expiry wk | Low realized vol | quant lit | partial (needs expiry flag) |
| 87 | Pre-roll momentum carry | Trend persists into roll, fade after | Continue trend until roll completes | Post-expiry reversal watch | rollover%, mom | 1d | Trend | Angel One rollovers | partial |
| 88 | New-series breakout | Fresh OI in new month drives trend | Long on next-month OI buildup + price break | ATR trail | next-mo OI, price | 1d | Trend onset | OI lit | partial |
| 89 | Expiry-week short-squeeze | High short OI + rollover → squeeze risk | Long when price>VWAP & OI falling (covering) | Squeeze fades | OI Δ, price, VWAP | 15m expiry wk | Squeeze | OI lit | partial |

## 10. Open Interest (OI) + Price Analysis

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 90 | Long buildup follow | Price↑ + OI↑ = fresh longs | Long on confirmed long buildup + price break | OI flattens / price < EMA20 | OI Δ, price, EMA20 | 15m/1d | Trend up | NSE OI spurts; mStock | partial |
| 91 | Short buildup follow | Price↓ + OI↑ = fresh shorts | Short on confirmed short buildup | OI flattens / cover signs | OI Δ, price | 15m/1d | Trend down | mStock; jainam | partial |
| 92 | Short-covering long | Price↑ + OI↓ = shorts exiting | Long on short-covering thrust | OI stabilizes; tgt prior high | OI Δ, price, rvol | 15m | Reversal up | StockGro; mStock | partial |
| 93 | Long-unwinding short | Price↓ + OI↓ = longs exiting | Short on long unwinding | OI stabilizes | OI Δ, price | 15m | Reversal down | mStock | partial |
| 94 | OI spurt breakout | Sudden OI surge + price break | Trade direction of OI spurt breakout | ATR trail; OI fades | OI %Δ spike, price | 5m/15m | News/expansion | NSE OI spurts; choiceindia | partial |
| 95 | OI + volume confirmation | Price + OI + rvol all aligned | Long when price↑ & OI↑ & rvol>1.5 | Any leg diverges | OI Δ, price, rvol | 15m | Institutional trend | niftytrader; traderscockpit | partial |
| 96 | OI divergence reversal | Price new high but OI falling | Fade when price↑ & OI↓ into resistance | Reversal target | OI Δ, price, pivots | 1d | Exhaustion | OI lit | partial |
| 97 | Top-OI-gainer rotation | Stock futs with biggest OI+price gain | Long top OI-gainers basket daily | Rank drops | OI %Δ rank, price | 1d | Momentum | Trendlyne SmartOptions | partial |
| 98 | OI-based S/R | Heavy-OI price zones act as S/R | Trade bounces/breaks at high-OI levels | Next OI level | OI-by-price profile | 15m | Range | OI profile lit | no (OI distribution) |
| 99 | PCR + OI sentiment filter | Put-call OI ratio gates direction | Long bias when PCR rising from low | PCR extreme | PCR, OI | 1d | Sentiment | OI lit | no (options OI) |
| 100 | Aggregate FII fut OI bias | FII net index-fut long/short positioning | Trade with FII net OI direction | Positioning flips | FII OI net (EOD) | 1d | Trend | NSE participant data | partial |

## 11. Index Arbitrage

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 101 | Cash-futures arb | Fut vs constituent basket mispricing | Short fut/long basket when fut > fair+band | Convergence at expiry | fut, basket NAV, carry | intraday | Arb | index-arb lit; Springer | no (basket exec) |
| 102 | ETF-futures arb | Index fut vs liquid index ETF | Trade spread vs fair value band | Convergence | fut, ETF px, carry | intraday | Arb | arb lit | partial (2 series) |
| 103 | Cross-index spread (NIFTY vs BANKNIFTY) | Ratio mean-reversion between indices | Long/short ratio at z extremes | z→0 | ratio, zscore | 15m/1d | Mean-rev | pairs lit | partial (2 series) |
| 104 | Sector-index vs NIFTY | Sector fut deviation from broad index | Trade spread reversion | Mean | ratio, zscore | 1d | Mean-rev | RS lit | partial |

## 12. Pair / Spread Trading (stat-arb)

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 105 | Cointegration pair (Engle-Granger) | Stationary spread of cointegrated stock futs | Long/short spread when z>±2 | z→0; stop z>±3.5 | OLS hedge ratio, ADF, zscore | 1d | Mean-rev | QuantConnect Research nb; Springer | partial (2 series) |
| 106 | Sector pair (e.g. HDFC vs ICICI) | Intra-sector mean-reversion | Spread z-entry, revert | Mean | spread zscore(60) | 1d | Range | QuantInsti EPAT | partial |
| 107 | Stock vs NIFTY beta-neutral | Hedge stock fut with index fut | Long stock/short β·index on z extreme | Mean | beta, spread zscore | 1d | Mean-rev | stat-arb lit | partial |
| 108 | Ratio spread reversion | Price-ratio of two futs reverts | Trade ratio at Bollinger extremes | Mid | ratio, BB(20,2) | 1h/1d | Range | pairs lit | partial |
| 109 | Kalman-filter dynamic hedge | Time-varying hedge ratio | Trade spread vs Kalman mean | Mean | Kalman β, residual z | 1d | Mean-rev | QuantConnect | no (Kalman state) |
| 110 | Distance-method pairs | Normalized-price min-distance pairs | Open at 2σ divergence | Convergence | normalized px, σ | 1d | Mean-rev | Gatev distance method | partial |
| 111 | Lead-lag pair | Faster fut leads slower, trade lag | Trade laggard on leader move | Catch-up done | cross-corr, lag | 5m/15m | Microstructure | stat-arb lit | partial |
| 112 | Triplet/basket spread | 3-leg market-neutral basket | Trade basket residual z | Mean | multi-OLS, zscore | 1d | Mean-rev | stat-arb lit | partial |
| 113 | Index-roll arb pair | Stock entering/leaving index | Front-run index reconstitution flow | Event passes | index-change calendar | event | Event | reconstitution lit | no (event) |
| 114 | Stochastic-spread (O-U) pair | Ornstein-Uhlenbeck spread model | Enter at O-U band, exit half-life | Mean / half-life | O-U params, zscore | 1d | Mean-rev | arxiv 1907.08397 | partial |

## 13. Gap Strategies

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 115 | Gap-up fade | Large gap-up fades intraday | Short on failure of opening high after gap | Prev close / gap fill | gap%, ORB | 5m/15m | Overreaction | gap lit | partial |
| 116 | Gap-fill continuation | Partial fill then resume gap direction | Long after gap-up holds above VWAP | EOD/trail | gap%, VWAP | 15m | Trend day | OneTradeJournal | partial |
| 117 | Gap-and-go | Strong gap + breakout = trend day | Long > opening-range high on gap up | ORB SL; trail | gap%, ORB, rvol | 5m/15m | Momentum | gap lit | partial |
| 118 | Island reversal | Gap-isolated cluster reverses | Trade against island after confirming gap | Prior swing | gaps, pivots | 1d | Reversal | price-action lit | no |
| 119 | Overnight-gap stat edge | Systematic long/short on gap z-score | Trade fut at open by gap zscore sign | EOD close | gap zscore(daily) | 1d | Mean-rev/momo | quant lit | partial |
| 120 | Weekend/event gap straddle bias | Pre-event flat, trade post-gap direction | Enter after gap resolves direction | Trail | gap%, event flag | 1d | Event | event lit | no |

## 14. News / Event-Day Volatility

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 121 | Budget-day volatility breakout | High-vol session ORB both sides | Break of post-announcement range | Opposite side; trail | event range, atr_pct | 5m/15m | Event vol | event lit | no (calendar) |
| 122 | RBI-policy reaction | Trade direction after policy digest | Enter on post-event trend confirm | Trail/EOD | event flag, EMA, VWAP | 15m | Event | event lit | no |
| 123 | Earnings-day stock fut momentum | Post-result drift (PEAD) | Long fut after positive surprise gap | Drift fades (days) | gap%, earnings cal | 1d | Post-earnings drift | PEAD lit | no (earnings cal) |
| 124 | Result-day straddle-fade | IV-crush; fade post-result spike | Fade overextended post-result fut move | Mean | atr_pct spike, VWAP | 15m | Overreaction | event lit | partial |
| 125 | Pre-event vol compression | Stay flat / sell premium into event | Range bias before scheduled event | Event time | atr_pct, event flag | 15m | Pre-event drift | event lit | no |
| 126 | Macro-data spike trade | React to CPI/GDP/Fed spillover | Trade momentum thrust on data spike | ATR trail | rvol, atr_pct, event | 5m/15m | Event vol | event lit | no |

## 15. Positional Swing (NRML)

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 127 | Weekly-trend swing | Ride multi-day trend on daily chart | Long when price>EMA50 & weekly higher-highs | EMA50 break; ATR trail | EMA50, ATR(14) | 1d | Trend | swing lit | yes |
| 128 | Pullback-to-EMA swing | Buy dip in established uptrend | Long on EMA21 pullback + bullish reversal | Prior high; SL swing low | EMA21, RSI(14) | 1d | Trend | freqtrade | yes |
| 129 | Breakout-retest swing | Enter on retest of broken level | Long on successful retest of resistance | ATR trail; SL retest low | rolling max, ATR | 1d | Trend | price-action | yes |
| 130 | Darvas-box swing | Box breakout positional | Long > box top; trail box bottoms | Box-bottom break | rolling max/min boxes | 1d | Trend | Darvas | yes |
| 131 | 3-bar reversal swing | Multi-bar reversal pattern entry | Long on confirmed 3-bar bullish reversal | ATR/swing SL | price pattern, ATR | 1d | Reversal | swing lit | partial |
| 132 | Sector-leader swing | Buy strongest fut in leading sector | Long top RS sector leader on pullback | RS deteriorates | RS rank, EMA20 | 1d | Trend/rotation | RS lit | partial |

## 16. Intraday Scalping (index futures)

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 133 | EMA 5/13 scalp | Fast EMA cross micro-trend | Long on 5>13 cross; quick tgt | 8-10pt tgt; tight SL | EMA5/13 | 1m/3m | Liquid trend | scalping lit | yes |
| 134 | VWAP micro-scalp | Scalp tags of VWAP intraday | Long bounce off VWAP; small tgt | 0.2-0.4% tgt | VWAP | 1m/3m | Range/trend | scribd VWAP | partial |
| 135 | Supertrend 5m scalp | Quick ST flips on fast TF | Trade each ST flip, tight risk | Opposite flip | Supertrend(7,2) | 3m/5m | Trending | TradingView | partial |
| 136 | Range-bar/tick scalp | Fixed-range bars filter noise | Break of range bar with momentum | Next bar / fixed pts | range bars | tick | Liquid | scalping lit | no (range bars) |
| 137 | Momentum-burst scalp | rvol surge + 1m thrust | Long on rvol spike + green thrust bar | Quick scale-out | rvol, mom(5) | 1m | Burst | scalping lit | yes |
| 138 | Bid-ask/order-flow scalp | Tape & DOM imbalance | Long on bid-stack absorption | Few ticks | order book, footprint | tick | Liquid | order-flow lit | no (L2 data) |

## 17. Beta-Rotation / Cross-Sectional

| # | Name | Core logic | Entry | Exit | Indicators+params | TF | Regime | Source | Genome |
|---|------|-----------|-------|------|-------------------|----|--------|--------|--------|
| 139 | High-beta rotation (risk-on) | Hold high-β futs in uptrends | Long high-β basket when NIFTY>EMA50 | Regime risk-off | beta, index EMA50 | 1d | Bull | factor lit | partial |
| 140 | Low-beta defensive (risk-off) | Rotate to low-β/defensives in downtrend | Long low-β when NIFTY<EMA200 | Regime risk-on | beta, index EMA200 | 1d | Bear | factor lit | partial |
| 141 | Cross-sectional momentum rank | Top-N momentum futs, monthly rebalance | Long top decile by mom(126) | Rank exit | mom(126) rank | 1d | Trend | Jegadeesh-Titman | partial |
| 142 | Low-volatility factor | Long lowest realized-vol futs | Long bottom-vol decile | Rank exit | vol(rolling) rank | 1d | Defensive | low-vol anomaly lit | partial (vol) |
| 143 | Beta-timing index overlay | Scale index-fut exposure by trend+vol | Size long by trend score / atr_pct | Score decays | EMA slope, atr_pct | 1d | All | risk-parity lit | yes |

---

**Total templates: 143** across 17 families (trend-following, momentum, breakout, mean-reversion, VWAP, CPR/pivots, volatility-breakout/ATR-channel, basis/cost-of-carry/calendar-spread, rollover/expiry-week, OI+price, index-arbitrage, pair/spread stat-arb, gaps, news/event-day, positional swing, intraday scalping, beta-rotation).

Genome tally: ~yes 45 (pure TA-feature mappable) · partial ~78 (need OI/basis/multi-symbol/rollover series) · no ~20 (discretionary, order-book, options-chain, or event-calendar).

Primary sources: Zerodha Varsity (TA, calendar spreads, ADX/Supertrend), NSE India (OI spurts, F&O strategies, participant data), 5paisa/Angel One (rollover-basis-carry-OI), QuantConnect Research & awesome-quant/pandas-ta/backtrader/freqtrade (indicator + backtest reference implementations), academic stat-arb (Springer "Risk-adjusted Returns from Statistical Arbitrage in Indian Stock Futures Market", QuantInsti EPAT, arXiv 1907.08397).
