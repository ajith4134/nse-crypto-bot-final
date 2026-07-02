# Crypto Futures / Perpetual-Swap Strategy Templates — Curated Library

> 120 distinct, proven leveraged strategy templates for BTC/ETH/alt perps & dated futures, grounded in OSS (freqtrade futures, jesse, Hummingbot, OctoBot, QuantConnect, backtrader, awesome-quant) + exchange research (Binance/Bybit/Coinglass) + published crypto-quant literature. Researched via real web searches, current to **June 2026**.
> **Total templates: 120.** Genome flag = mappability onto our TA-feature genome `{ret, sma, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol}` + `{threshold, crossover}` ops. Funding/basis/OI = **partial** (extra data series, but we already have ccxt funding + liquidation calc in repo). Orderflow/CVD = **no** (needs trade-tick aggressor data).

---

## Legend / per-template fields
`name | family | core logic | entry | exit (SL/target/trail/liq-aware) | indicators+params | leverage | timeframe | regime fit | source | genome`

**Genome key:** `yes` = pure TA genome; `partial` = needs funding/basis/OI/liq series (in-repo ccxt) on top of TA; `no` = needs orderflow/CVD/tick data.

---

## FAMILY A — Trend-following with leverage (1–16)

**A1. EMA Cross Trend (Golden/Death)** | trend | ride medium-term trend via fast/slow EMA cross | LONG when EMA12 crosses above EMA26; SHORT on cross-down | exit on opposite cross; SL = 1.5×ATR; trail at 2×ATR; cut leverage so SL < liq distance | EMA(12,26), ATR(14) | 2–3× (SL must clear liq) | 1h–4h | trending, fails in chop | freqtrade futures docs; jesse examples | **yes**

**A2. Triple-EMA Stack (8/21/55)** | trend | only trade with full EMA alignment | LONG when close>EMA8>EMA21>EMA55 (all rising); SHORT mirror | exit when stack breaks (close<EMA21); SL 2×ATR; trail EMA21 | EMA(8,21,55), ATR(14) | 2–3× | 1h–4h | strong trend | freqtrade community strats | **yes**

**A3. Supertrend Follower** | trend | ATR-band flip defines regime | LONG when Supertrend flips green; SHORT on red flip | exit on opposite flip; Supertrend line is the trailing stop; size so flip-band > maint margin | Supertrend(ATR10, mult3) | 2–4× | 15m–4h | trend; whipsaws in range | jesse `super-trend-strategy` | **yes** (ATR-band ≈ atr+threshold)

**A4. Dual-Supertrend Confirm** | trend | two Supertrends (fast+slow) reduce whipsaw | enter only when both agree on direction | exit when fast flips; SL = slow Supertrend | Supertrend(10,3)+(20,5) | 2–3× | 1h | trend | jesse/community | **yes**

**A5. ADX-Gated EMA Trend** | trend | only trade EMA cross when ADX confirms trend strength | LONG: EMA cross-up AND ADX>25 (+DI>−DI) | exit ADX<20 or opposite cross; SL 1.5×ATR; trail | EMA(20,50), ADX(14)>25, ATR(14) | 2–3× | 1h–4h | trend-onset; filters chop | backtrader docs; QuantConnect | **partial** (ADX not in genome; approximate via atr_pct+mom) 

**A6. Donchian Channel Breakout (Turtle-style)** | trend/breakout | classic 20/55-bar channel breakout, leveraged | LONG on close > 20-bar high; SHORT on < 20-bar low | exit on 10-bar opposite channel; SL 2×ATR; pyramid on N-unit moves | Donchian(20/55,10), ATR(20) | 2–3× (Turtle unit sizing) | 4h–1d | trend; macro moves | jesse `simple-donchian-strategy`; Turtle system | **yes** (range_pct/rolling-max via threshold)

**A7. Donchian Mid-Line Trend** | trend | trade in direction of channel midline slope | LONG when price>midline & midline rising | exit price<midline; SL lower channel | Donchian(20) midline | 2× | 1h–4h | trend | backtrader | **yes**

**A8. MACD Trend + Histogram** | trend/momentum | MACD line/signal cross with histogram expansion | LONG MACD>signal & hist rising>0 | exit hist turns down or cross; SL 2×ATR | MACD(12,26,9) | 2–3× | 1h–4h | trend | freqtrade default templates | **partial** (MACD ≈ ema diff; mappable approx → mark yes-ish, conservatively partial)

**A9. Multi-Timeframe Trend Align (MTF)** | trend | enter on LTF only with HTF trend | LONG when 4h EMA50 rising AND 15m EMA cross-up | exit 15m opposite; SL 1.5×ATR; trail | EMA(50) 4h + EMA(9,21) 15m | 2–3× | 15m exec / 4h bias | trend | freqtrade `informative_pairs` | **yes**

**A10. Parabolic SAR Trend Flip** | trend | SAR dots define trailing trend stop | LONG when price crosses above SAR; SHORT below | exit/reverse on SAR flip (SAR = trailing stop) | PSAR(0.02,0.2) | 2–3× | 1h–4h | strong trend | backtrader; TA-Lib | **partial** (SAR recursive, not in genome) 

**A11. Heikin-Ashi Trend Ride** | trend | smoothed candles reduce noise for trend hold | LONG on consecutive green HA candles w/ no lower wick; SHORT mirror | exit on first opposite HA candle; SL 2×ATR | Heikin-Ashi, ATR | 2–3× | 1h–4h | trend | jesse/community | **partial** (HA transform outside genome) 

**A12. Ichimoku Cloud Trend** | trend | Kumo cloud + Tenkan/Kijun cross | LONG price>cloud & Tenkan>Kijun & Chikou clear | exit price re-enters cloud; SL Kijun | Ichimoku(9,26,52) | 2× | 4h–1d | trend | backtrader; jesse | **partial** (multi-line; approximate w/ smas) 

**A13. Hull MA Trend** | trend | low-lag HMA for early trend entries | LONG when HMA slope turns up; SHORT down | exit slope flip; SL 2×ATR; trail HMA | HMA(55) | 2–3× | 1h–4h | trend | community | **partial** (weighted MA not exact; approx ema) 

**A14. KAMA Adaptive Trend** | trend | Kaufman adaptive MA adjusts to volatility | LONG price>KAMA & KAMA rising | exit price<KAMA; SL ATR | KAMA(10,2,30) | 2× | 1h–4h | trend/variable vol | TA-Lib; QuantConnect | **partial** 

**A15. Leverage-Scaled Trend (vol-target)** | trend/leverage | scale leverage inverse to realized vol to hold constant risk | LONG on EMA trend; set lev = target_vol / realized_vol (cap 5×) | exit trend break; SL 2×ATR; auto-deleverage as vol rises | EMA(50), realized vol(20), ATR | dynamic 1–5× | 4h–1d | trend; vol regimes | AQR/Moskowitz TSMOM; awesome-quant | **yes** (vol+ema+threshold) 

**A16. Chandelier-Exit Trend** | trend | trail stop off highest-high − ATR multiple | LONG on trend filter (EMA50); ride until Chandelier hit | exit at Chandelier stop (HH − 3×ATR); liq-aware sizing | EMA(50), Chandelier(22,3×ATR) | 2–3× | 1h–4h | trend | backtrader | **yes** (rolling max + atr) 

---

## FAMILY B — Momentum & leverage-scaled momentum (17–28)

**B17. Time-Series Momentum (TSMOM)** | momentum | sign of trailing return predicts next-period return | LONG if 20-bar return>0; SHORT if<0; rebalance | flip on sign change; vol-target sizing; SL 2.5×ATR | ret(20), realized vol | dynamic 1–4× | 1d (weekly rebal) | trend; strong empirical edge in crypto | Han/Kang/Ryu SSRN 4675565; Moskowitz TSMOM | **yes** (ret+threshold) 

**B18. Cross-Sectional Momentum (alt basket)** | momentum | rank alts by trailing return, long top / short bottom | LONG top-decile 3-week return perps; SHORT bottom; market-neutral | weekly rebalance; per-leg SL; cap gross lev | ret(15d) cross-sectional rank | 2–3× gross | 1d/weekly | dispersion regimes (weaker than TSMOM) | Cryptocurrency Factor Momentum (ICM); SSRN | **yes** (ret rank + zscore) 

**B19. RSI Momentum Continuation** | momentum | strong RSI in trend signals continuation not reversal | LONG when RSI crosses up through 60 in uptrend (EMA200 up) | exit RSI<50; SL 2×ATR | RSI(14), EMA(200) | 2–3× | 1h–4h | trend/momentum | freqtrade; QuantConnect | **yes** 

**B20. ROC Thrust** | momentum | rate-of-change spike = momentum ignition | LONG when ROC(10)>threshold & price>EMA50 | exit ROC<0; SL 2×ATR; trail | ROC(10), EMA(50) | 2–3× | 15m–1h | momentum bursts | backtrader | **yes** (≈ mom + threshold) 

**B21. Momentum + Volume Confirm** | momentum | momentum only valid on rising relative volume | LONG ROC>0 AND rvol>1.5 AND price>EMA20 | exit rvol fades & ROC<0; SL ATR | ROC, rvol(20), EMA20 | 2–3× | 15m–1h | breakouts | freqtrade volume filters | **yes** (mom+rvol+threshold) 

**B22. Dual-Momentum (abs+rel)** | momentum | combine absolute (vs cash) and relative (vs peers) momentum | LONG asset if 90d ret>0 AND ret>peer median | monthly rebalance; SL trend break | ret(90d) abs+rel | 2× | 1d | trend | Antonacci Dual Momentum; awesome-quant | **yes** 

**B23. Leverage-Scaled Momentum Pyramid** | momentum/leverage | add to winners, scaling lev with conviction | initial LONG on momentum; add 0.5 unit each +1×ATR; reduce on stall | exit on momentum reversal; trail breakeven after 1st add | ret, ATR, EMA | escalating 1→4× | 1h–4h | sustained trend | Turtle pyramiding; backtrader | **yes** 

**B24. Momentum Z-Score Entry** | momentum | enter when normalized momentum exceeds z-band | LONG zscore(ret,50)>1.5 & price>EMA50 | exit zscore<0; SL 2×ATR | zscore(ret,50), EMA50 | 2–3× | 1h–4h | momentum | quant lit | **yes** (zscore native) 

**B25. Awesome Oscillator Momentum** | momentum | AO (5/34 median-price SMA diff) zero-cross + saucer | LONG AO crosses>0 or bullish saucer | exit AO<0; SL ATR | AO(5,34) | 2–3× | 1h | momentum | jesse/backtrader | **yes** (≈ sma diff) 

**B26. TSI (True Strength Index) Trend-Mom** | momentum | double-smoothed momentum oscillator | LONG TSI>signal & >0; SHORT mirror | exit cross-down; SL ATR | TSI(25,13,7) | 2× | 1h–4h | momentum | TA libs | **partial** (double-smooth approx) 

**B27. Stochastic-Momentum Pop** | momentum | fast stochastic exiting oversold in uptrend | LONG %K crosses %D up from <20 with EMA200 up | exit %K>80; SL 1.5×ATR | Stoch(14,3,3), EMA200 | 2–3× | 15m–1h | pullback-in-trend | backtrader | **partial** (stoch ≈ range_pct of close) 

**B28. Vol-Adjusted Momentum (Sharpe-mom)** | momentum | rank by return/vol not raw return | LONG top risk-adjusted momentum names | weekly rebal; vol-target lev | ret/vol ratio | dynamic 1–3× | 1d | trend | SSRN crypto momentum | **yes** 

---

## FAMILY C — Breakout & volatility breakout (29–42)

**C29. Bollinger Band Breakout** | breakout | close outside band = volatility expansion | LONG close>upper BB(20,2); SHORT<lower | exit return to mid-band; SL opposite band; trail mid | BB(20,2), ATR | 2–3× | 15m–1h | expansion | freqtrade; backtrader | **yes** (bands ≈ sma±vol*z) 

**C30. Bollinger Squeeze → Breakout** | vol breakout | trade expansion after band-width contraction | enter on close breaking band after band-width<20th pct | exit mid-band; SL inside opposite band | BB(20,2) width percentile | 2–4× | 15m–1h | post-consolidation | TTM Squeeze; QuantConnect | **yes** (vol/atr_pct percentile) 

**C31. Keltner Channel Breakout** | vol breakout | EMA±ATR band break (cleaner than BB) | LONG close>EMA20+2×ATR; SHORT mirror | exit back to EMA; SL ATR; trail | Keltner(EMA20, 2×ATR) | 2–3× | 15m–1h | expansion | luxalgo/quantvps Keltner guides | **yes** (ema+atr) 

**C32. TTM Squeeze (BB-in-Keltner)** | vol breakout | BB inside Keltner = squeeze; fire on release | enter direction of momentum when BB exits Keltner | exit momentum fade; SL ATR | BB(20,2), Keltner(20,1.5), momentum | 2–4× | 15m–1h | compression→expansion | QuantConnect TTM | **yes** (atr_pct+mom) 

**C33. ATR Channel Breakout** | vol breakout | break of close±N×ATR envelope | LONG close>prevClose+N×ATR | exit opposite ATR band; SL 1×ATR | ATR(14), mult 1.5–3 | 2–3× | 15m–1h | expansion | backtrader | **yes** 

**C34. Opening-Range / Session Breakout** | breakout | break of first-N-hour range (00:00 UTC) | LONG break above session high; SHORT below low | exit session close or opposite; SL mid-range | session high/low, ATR | 2–3× | 5m–15m | intraday vol | community; QuantConnect | **yes** (range_pct intraday) 

**C35. NR7 / Inside-Bar Breakout** | vol breakout | narrowest-range bar precedes expansion | enter on break of NR7/inside bar; direction of break | exit 2×ATR target; SL other side of bar | range_pct rank(7), ATR | 2–4× | 1h–4h | compression | Crabel volatility; backtrader | **yes** (range_pct native) 

**C36. Volatility Contraction Pattern (VCP)** | vol breakout | tightening ranges → explosive break | LONG break of pivot after 2–3 contractions on falling vol | exit 3×ATR; SL pivot low | range_pct sequence, vol, ATR | 2–3× | 4h–1d | post-base | Minervini VCP | **yes** (range_pct+vol) 

**C37. Donchian 4h Breakout + Vol Filter** | breakout | channel break only on volume surge | LONG 20-bar high break AND rvol>2 | exit 10-bar low; SL ATR | Donchian(20), rvol | 2–3× | 4h | trend onset | freqtrade | **yes** 

**C38. Range Expansion (ATR-pct trigger)** | vol breakout | trade when atr_pct jumps above baseline | enter direction of close move when atr_pct>2× its 50-bar mean | exit atr_pct normalizes; SL 1×ATR | atr_pct(14), ret sign | 2–3× | 15m–1h | vol regime shift | quant lit | **yes** (atr_pct native) 

**C39. Failed-Breakout Reversal (fakeout fade)** | breakout/reversal | fade breakouts that fail back into range | SHORT when close pops above range high then closes back inside | exit mid-range; SL above the wick | range high/low, rvol | 2–3× | 15m–1h | range; liquidity grabs | community; OI-divergence research | **partial** (better w/ OI-falling confirm) 

**C40. Pivot-Point Breakout** | breakout | classic floor-trader pivots R1/S1 break | LONG break R1 with trend; SHORT break S1 | exit R2/S2 target; SL pivot | daily pivots, ATR | 2–3× | 15m–1h | intraday | backtrader | **yes** (levels from OHLC) 

**C41. Volatility Breakout (Larry Williams)** | vol breakout | buy at open + k×(prev range) | LONG when price ≥ open + 0.5×prevRange; SHORT mirror | exit at close; SL k×range other side | prev range, k=0.5 | 2–4× | 1d | daily momentum | Larry Williams; backtrader | **yes** (range_pct) 

**C42. Choppiness-Filtered Breakout** | breakout | only breakout when Choppiness Index says trending | enter channel break when CHOP<38.2 | exit CHOP>61.8; SL ATR | Choppiness(14), Donchian | 2–3× | 1h–4h | filter chop | community | **partial** (CHOP ≈ atr/range; approximate) 

---

## FAMILY D — Mean-reversion & funding-flip reversals (43–56)

**D43. Bollinger Mean-Reversion** | mean-rev | fade extension back to mean | LONG close<lower BB(20,2) & RSI<30; SHORT mirror | exit mid-band; SL 1.5×ATR beyond band; low lev (rev risk) | BB(20,2), RSI(14) | 1–2× | 5m–1h | range | freqtrade; backtrader | **yes** 

**D44. RSI(2) Reversion** | mean-rev | Connors short-term oversold/overbought | LONG RSI(2)<5 & price>EMA200; exit RSI>70 | exit on RSI rise or EMA5 cross; SL 2×ATR | RSI(2), EMA200/EMA5 | 1–2× | 1h–4h | range/pullback | Connors RSI2; backtrader | **yes** 

**D45. Z-Score Reversion** | mean-rev | fade statistical extremes of price vs MA | LONG zscore(close,20)<−2; SHORT>+2 | exit zscore→0; SL zscore beyond ±3 | zscore(close,20) | 1–2× | 15m–1h | range | quant lit | **yes** (native) 

**D46. VWAP Reversion (intraday)** | mean-rev | fade deviation from session VWAP | LONG price<VWAP−2σ band; exit at VWAP | exit VWAP touch; SL −3σ | VWAP, σ bands | 1–2× | 5m–15m | range/intraday | community; QuantConnect | **partial** (VWAP needs volume-weighted; approx) 

**D47. Funding-Flip Reversal** | funding/mean-rev | extreme funding marks crowded side → fade | SHORT when funding > +0.1%/8h (overheated longs) & price stalls; LONG when funding deeply negative | exit on funding normalization; SL beyond recent swing; liq-aware | funding rate (ccxt), price stall | 2–3× | 4h–1d | euphoria/capitulation | Coinglass funding; tradelink.pro | **partial** (funding series in repo) 

**D48. Funding + Price Divergence Reversal** | funding/mean-rev | price up but funding falling = weak longs → reversal | SHORT when price makes HH but funding declines (long exhaustion) | exit on funding/price re-sync; SL above HH | funding rate, price | 2–3× | 4h | top/bottom detection | Gate derivatives-signals wiki | **partial** 

**D49. Bollinger %B Reversion** | mean-rev | %B extremes for normalized reversion | LONG %B<0.05; SHORT>0.95; trend filter | exit %B 0.5; SL ATR | BB %B(20,2) | 1–2× | 15m–1h | range | backtrader | **yes** 

**D50. Mean-Reversion Pairs (BTC/ETH ratio)** | mean-rev/stat-arb | trade ratio spread back to mean, delta-neutral | LONG ETH/SHORT BTC when ratio zscore<−2; reverse>+2 | exit zscore→0; SL zscore±3 | zscore of log price ratio | 2–3× per leg | 1h–4h | cointegrated regime | awesome-quant pairs; backtrader | **yes** (zscore of ratio) 

**D51. Kalman-Filter Pairs** | stat-arb | dynamic hedge ratio via Kalman for pair spread | enter spread zscore extreme using Kalman beta | exit spread mean; SL zscore band | Kalman beta, zscore | 2–3× | 1h–4h | cointegrated | QuantConnect Kalman pairs | **partial** (Kalman recursive) 

**D52. OU Mean-Reversion (Ornstein-Uhlenbeck)** | stat-arb | model spread as OU, trade half-life bands | enter at ±1.5σ_OU; exit at OU mean | exit mean; SL ±3σ | OU params (θ,μ,σ) | 2× | 1h–4h | stationary spread | quant lit; awesome-quant | **partial** 

**D53. RSI Divergence Reversal** | mean-rev | price new extreme but RSI doesn't = reversal | LONG bullish RSI divergence at support; SHORT bearish at resistance | exit prior swing; SL beyond extreme | RSI(14), swing pivots | 1–2× | 1h–4h | exhaustion | backtrader; community | **partial** (divergence detection nontrivial) 

**D54. CCI Extreme Reversion** | mean-rev | Commodity Channel Index ±200 fades | LONG CCI<−200 reverting up; SHORT>+200 | exit CCI→0; SL ATR | CCI(20) | 1–2× | 15m–1h | range | backtrader | **partial** (CCI ≈ zscore of typical price) 

**D55. Overnight/Funding-Window Reversion** | funding/mean-rev | price drifts into funding settlement then reverts | enter against pre-funding drift just before settlement | exit shortly after funding tick; tight SL | funding schedule (ccxt), price drift | 2–3× | 1h/8h windows | microstructure | metamask perp funding; exchange research | **partial** 

**D56. Bollinger Band Walk Exhaustion** | mean-rev | repeated band-rides end in snap-back | SHORT after N closes outside upper band then first close back inside | exit mid-band; SL recent high | BB(20,2), count | 1–2× | 15m–1h | range/top | community | **yes** 

---

## FAMILY E — Funding-rate arbitrage / delta-neutral farm (57–66)

**E57. Spot-Perp Funding Farm (delta-neutral)** | funding-arb | long spot + short perp, collect positive funding, zero delta | enter when funding>fees threshold (e.g. >0.01%/8h); long spot, short equal perp | exit when funding flips negative or below cost; rebalance hedge on drift | funding rate (ccxt), spot+perp price | low (hedged; perp leg 1–2×) | hold days–weeks | positive-funding/contango | arbitragescanner; aoki-h-jp/funding-rate-arbitrage (GitHub) | **partial** (funding+spot in repo) 

**E58. Reverse Funding Farm (negative funding)** | funding-arb | short spot/borrow + long perp when funding deeply negative | enter funding<−threshold; long perp, short spot (or borrow) | exit on funding normalization; manage borrow cost | funding rate, borrow rate | low/hedged | days | backwardation/bearish | arbitragescanner; Messari | **partial** 

**E59. Cross-Exchange Funding Spread** | funding-arb | long perp on low/neg-funding venue, short perp on high-funding venue | enter when funding spread (ExA−ExB) > fees; both legs perp, net delta 0 | exit on spread convergence; monitor basis risk | funding rates 2 venues (ccxt) | per-leg 2–3×, net~0 | hours–days | funding dispersion | Pendle Boros (Medium); Fenni Kang Coinmonks | **partial** (multi-venue funding) 

**E60. Funding-Rate Carry Basket** | funding-arb | farm top-N positive-funding alts delta-neutral, diversified | enter basket of highest-funding perps each hedged spot; size by funding/vol | rebalance daily; drop names whose funding<cost | funding screen (ccxt), vol | hedged | daily | persistent positive funding | aoki-h-jp repo; Coinglass funding | **partial** 

**E61. Funding Predictive Entry (premium-index)** | funding-arb | enter farm pre-emptively when premium index predicts next funding | open hedge when premium index trending up before funding fixes | exit after capturing funding; close hedge | premium index, funding (ccxt) | hedged | 8h cycle | predictable funding | Binance premium-index docs; whaleportal | **partial** 

**E62. Dynamic-Hedge Funding Farm** | funding-arb | keep delta ≈0 by re-hedging as perp price drifts | maintain short-perp/long-spot; adjust perp size when |delta|>band | exit funding<cost; SL = funding-regime flip | funding, position delta | hedged | continuous | any positive-funding | Hummingbot perpetual MM concepts; altrady delta-neutral | **partial** 

**E63. Funding Threshold Switch (long/short bias)** | funding | use funding sign as cheap directional filter on a trend system | only take LONG trades when funding ≤0 (you get paid/cheap); SHORT when funding≥0 | normal trend exits; SL ATR | funding rate + EMA trend | 2–3× | 4h | trend w/ funding tailwind | Gate wiki; zipmex | **partial** 

**E64. Funding Extremes Contrarian Bias** | funding | very high funding = crowded → bias against new longs | block/short bias when funding>99th pct; long bias when<1st pct | combine w/ price trigger; SL swing | funding percentile | 2–3× | 4h–1d | crowded markets | Coinglass; XT microstructure (Medium) | **partial** 

**E65. Perp Triangular / Synthetic Carry** | funding-arb | synthetic spot via two perps vs cash to lock funding | construct delta-neutral synthetic capturing net funding across legs | exit on net-carry decay | funding multiple legs | hedged | days | multi-venue | quant lit; awesome-quant | **partial** 

**E66. Stablecoin-Pair Funding Farm** | funding-arb | farm funding on USDC vs USDT margined perps spread | exploit funding/basis differences between quote-collateral perps | exit convergence | funding by collateral | hedged | days | stable dispersion | exchange research | **partial** 

---

## FAMILY F — Basis trading (dated futures vs spot) (67–74)

**F67. Cash-and-Carry (quarterly contango)** | basis | long spot + short dated future at premium, capture basis to expiry | enter when annualized basis>hurdle (e.g.>10%); hold to settlement | exit at expiry (basis→0) or early if basis collapses | dated future price, spot, days-to-expiry | hedged (low) | weeks–quarter | contango | cmegroup basis; CoinGlass Basis | **partial** (dated-future series needed) 

**F68. Reverse Cash-and-Carry (backwardation)** | basis | short spot + long future when future<spot | enter when basis negative beyond cost | exit at expiry/convergence | future, spot | hedged | weeks | backwardation | cmegroup; quant lit | **partial** 

**F69. Calendar Spread (near vs far)** | basis | trade term-structure between two dated contracts | LONG far/SHORT near (or reverse) when spread off fair curve | exit spread mean-revert/roll | two dated futures prices | 2–3× spread | weeks | term-structure dislocation | backtrader; awesome-quant | **partial** 

**F70. Basis Momentum** | basis | basis itself trends with sentiment → trade its direction | LONG basis-widening (buy future) when basis momentum + sentiment up | exit basis momentum stall | basis time-series, momentum | 2–3× | days | trending basis | CFBenchmarks basis blog | **partial** 

**F71. Basis Mean-Reversion** | basis | extreme annualized basis reverts to norm | SHORT basis when annualized basis>z-band (e.g.>30%); long spot hedge | exit basis→mean; SL basis>extreme | basis zscore | hedged | days–weeks | overheated premium | CoinGlass; cmegroup | **partial** 

**F72. Perp-vs-Quarterly Basis Spread** | basis | trade dislocation between perp and dated future | LONG cheaper leg / SHORT richer when perp-future spread off funding-implied fair | exit convergence | perp + quarterly prices, funding | hedged | days | dislocation | OctoBot-Script basis.md; aeaweb basis paper | **partial** 

**F73. Roll-Yield Harvest** | basis | systematically roll short-future carry capturing roll yield | maintain short dated future, roll before expiry while contango | exit when curve flattens/backwardates | term structure | hedged | continuous roll | contango | quant lit | **partial** 

**F74. ETF-Driven Basis Trade** | basis | spot-ETF flows widen basis; trade the structural premium | long spot(ETF)/short CME future when basis elevated by inflows | exit basis normalization/expiry | basis, ETF flow proxy | hedged | weeks | ETF inflow regime | cmegroup OpenMarkets | **partial** 

---

## FAMILY G — Open-Interest (OI) + price strategies (75–84)

**G75. OI-Confirmed Breakout** | OI | breakout valid only if OI rising (new money) | LONG channel/range break AND OI rising | exit OI rolls over or price re-enters range; SL ATR | price break + OI delta (ccxt) | 2–3× | 1h–4h | trend onset | Gate OI wiki; XT microstructure | **partial** (OI series in repo) 

**G76. OI-Divergence Fade** | OI | breakout on falling OI = liquidity grab → fade | SHORT breakout up when OI falling (no new longs); mirror | exit mean-revert into range; SL above wick | price + OI delta | 2–3× | 15m–1h | range/false-breaks | OI-divergence research; Gate wiki | **partial** 

**G77. Price↑ + OI↑ Trend Add** | OI | rising price + rising OI = healthy uptrend, add | add LONG units while price & OI both rising | exit when OI flattens/price stalls; trail ATR | price, OI | escalating 2–4× | 4h | strong trend | Gate derivatives signals | **partial** 

**G78. Price↑ + OI↓ Short-Covering Fade** | OI | rally on falling OI = short covering, fades | fade the rally (SHORT) once OI decline + price up exhausts | exit reversion; SL swing high | price, OI | 2–3× | 1h–4h | corrective bounce | KuCoin/Gate research | **partial** 

**G79. Price↓ + OI↑ New-Shorts Trend** | OI | falling price + rising OI = aggressive new shorts, trend down | SHORT continuation while both persist | exit OI flattens; trail | price, OI | 2–3× | 4h | downtrend | Gate wiki | **partial** 

**G80. OI Spike Reversal (leverage flush)** | OI | parabolic OI spike + price spike = unsustainable | fade after OI hits extreme z-band with extreme funding | exit post-flush; SL beyond spike | OI zscore, funding | 2–3× | 1h–4h | euphoria | XT Bitcoin microstructure | **partial** 

**G81. OI Buildup at Range Edge** | OI/liq | OI clustering near level = liquidation fuel | position for break toward the OI/liquidation cluster | exit at opposite cluster; SL beyond level | OI distribution, levels | 2–3× | 1h | pre-cascade | XT liquidation-cascade (Medium) | **partial** 

**G82. OI Momentum Filter on Trend** | OI | use OI rate-of-change as conviction gate on EMA trend | take EMA-trend trades only when OI ROC>0 | normal trend exit; SL ATR | EMA trend + OI ROC | 2–3× | 4h | trend | Gate wiki | **partial** 

**G83. OI/Volume Ratio Regime** | OI | high OI growth vs volume = leverage building (fragile) | reduce size / tighten stops when OI/vol ratio high; trade reversals | exit ratio normalizes | OI, volume | 1–2× | 4h–1d | fragile leverage | XT microstructure | **partial** 

**G84. Aggregated OI Cross-Exchange Trend** | OI | total-market OI trend (all venues) as macro filter | bias long when aggregate OI + price rising; short mirror | macro exit; SL ATR | aggregated OI (Coinglass) | 2–3× | 1d | macro regime | Coinglass; Gate | **partial** 

---

## FAMILY H — Liquidation cascade / liquidation-hunt (85–92)

**H85. Liquidation-Cascade Momentum** | liquidation | ride the forced-selling/buying cascade | enter direction of cascade when liq-volume spikes + price accelerates through level | exit when liq volume fades / price stabilizes; tight trail | liquidation feed/calc (repo), ATR | 2–4× | 1m–15m | cascade event | XT liquidation-cascade; WazirX | **partial** (liq calc in repo) 

**H86. Liquidation-Cluster Magnet** | liquidation | price gravitates to dense liq clusters | position toward nearest large liq cluster (stop-hunt target) | exit at cluster (liquidity pool); SL beyond | liq heatmap/calc, levels | 2–3× | 15m–1h | pre-hunt | Coinglass liq map; XT | **partial** 

**H87. Post-Liquidation Reversion (V-bounce)** | liquidation/mean-rev | over-extended cascade snaps back after flush | LONG after long-liquidation flush exhausts (wick + liq spike fades) | exit prior level; SL below wick | liq spike, RSI(2), wick | 2–3× | 5m–1h | capitulation | WazirX; XT microstructure | **partial** 

**H88. Stop-Hunt Fade (liquidity grab)** | liquidation | exchanges sweep obvious stops then reverse | fade the sweep: LONG after price spikes below equal-lows + reclaims | exit range mid; SL below sweep low | swing lows, liq, wick reclaim | 2–3× | 5m–15m | range/grab | community; OI-divergence | **partial** 

**H89. Funding+Liq Combo Top/Bottom** | liquidation/funding | extreme funding + cascade = local reversal | reverse after long-liq cascade with very positive funding (long top) | exit reversion; SL beyond extreme | funding + liq calc | 2–3× | 1h | euphoria/capitulation | tradelink.pro; XT | **partial** 

**H90. Cascade-Continuation Breakout** | liquidation | first cascade triggers chain through next clusters | add in cascade direction as each cluster breaks | exit when cluster density thins; trail | liq clusters sequence | 2–4× | 1m–15m | high-leverage flush | XT; KuCoin | **partial** 

**H91. Liquidation-Imbalance Bias** | liquidation | long-liq >> short-liq skew = downside pressure (and vice versa) | bias short when long-liquidations dominate; long mirror | combine price trigger; SL ATR | liq long/short ratio | 2–3× | 15m–1h | trend | Gate liquidation data | **partial** 

**H92. Pre-Cascade Risk-Off (defensive)** | liquidation/risk | detect fragility (high OI+extreme funding) and de-risk/flip | cut leverage or open small contrarian hedge when fragility score high | exit after flush; SL tight | OI + funding + liq composite | 1–2× | 4h | pre-event | XT; finance.yahoo cascade reports | **partial** 

---

## FAMILY I — Long/short ratio & sentiment-positioning (93–99)

**I93. Top-Trader Long/Short Contrarian** | LS-ratio | fade crowd when top-trader LS ratio extreme | SHORT when global LS ratio extremely long; LONG when extremely short | exit ratio normalizes; SL swing | long/short account ratio (Binance data) | 2–3× | 4h–1d | crowded | Binance futures/data; Coinglass | **partial** (LS series) 

**I94. Smart-Money vs Retail Divergence** | LS-ratio | top-trader positioning vs all-account divergence | follow top-trader side when it diverges from retail crowd | exit convergence; SL ATR | top vs global LS ratio | 2–3× | 4h | divergence | Binance data; Gate wiki | **partial** 

**I95. LS-Ratio Momentum** | LS-ratio | trend in positioning confirms price trend | LONG when LS ratio rising with price; short mirror | exit ratio rolls over | LS ratio trend | 2–3× | 4h | trend | Gate wiki | **partial** 

**I96. Fear & Greed Contrarian Overlay** | sentiment | extreme sentiment marks turns | LONG at extreme Fear; reduce/short at extreme Greed (w/ price trigger) | exit toward neutral; SL swing | Fear&Greed index (in repo) | 2× | 1d | extremes | alternative.me; repo F&G panel | **partial** 

**I97. Long/Short + Funding Confluence** | sentiment | both LS ratio and funding extreme = high-confidence fade | fade when LS-long extreme AND funding very positive | exit normalization; SL beyond extreme | LS ratio + funding | 2–3× | 4h | crowded | Coinglass; Gate | **partial** 

**I98. Sentiment-Filtered Trend** | sentiment | only take trend trades aligned with positioning shift | trend entry gated by LS-ratio confirmation | trend exit; SL ATR | EMA trend + LS ratio | 2–3× | 4h | trend | Gate wiki | **partial** 

**I99. Social/On-chain Sentiment Spike** | sentiment | social volume spike precedes vol | enter direction of price on sentiment-volume spike | exit spike fades; SL ATR | social index (ext), price | 2× | 1h–4h | event-driven | OctoBot social indicators | **partial** 

---

## FAMILY J — Premium-index & mark-price strategies (100–104)

**J100. Premium-Index Threshold Entry** | premium | sustained premium index = directional pressure | LONG when premium index>+band persistently (perp rich, bullish); short mirror | exit premium normalizes; SL ATR | premium index (ccxt/Binance) | 2–3× | 1h–4h | trending premium | Binance premium-index; whaleportal | **partial** 

**J101. Premium-Index Reversion** | premium | spiky premium snaps back (overpaid perp) | SHORT perp when premium spikes far above MA; mirror | exit premium→MA; SL beyond spike | premium index zscore | 2–3× | 15m–1h | spike | whaleportal; Binance docs | **partial** 

**J102. Mark-vs-Last Dislocation Scalp** | premium | mark price vs last-trade gap = mean-revert | fade gap between mark and last when beyond band | exit gap closes; tight SL | mark price, last price | 2–3× | 1m–5m | microstructure | CoinAPI perp explainer | **partial** 

**J103. Premium-Predicted Funding Pre-Position** | premium/funding | premium index forecasts next funding; pre-position farm/bias | open bias before funding fixes per premium trend | exit after funding capture | premium index → funding | 2–3× | 8h cycle | predictable | Binance; metamask | **partial** 

**J104. Basis-of-Perp (mark−index) Momentum** | premium | perp basis (mark−index) trend as signal | follow direction of widening perp basis | exit basis stalls; SL ATR | mark−index series | 2–3× | 1h | trend | CoinGlass; CoinAPI | **partial** 

---

## FAMILY K — Cross-exchange & latency arbitrage (105–108)

**K105. Cross-Exchange Price Arb (perp)** | x-exchange | same perp priced differently across venues | LONG cheap venue / SHORT rich venue when spread>fees+slippage | exit spread converges | perp price 2 venues | per-leg 2–3×, net 0 | seconds–min | dislocation | Bybit arb help; hftarbitrage | **partial** (multi-venue feeds) 

**K106. Triangular Arb (perp legs)** | x-exchange | mispricing across 3 related contracts | execute the 3-leg loop when implied edge>costs | exit on fill (instantaneous) | 3 contract prices | hedged | seconds | dislocation | quant lit; ccxt | **partial** 

**K107. Spot-Perp Same-Venue Basis Scalp** | x-exchange/basis | intraday perp-spot gap scalp delta-neutral | enter when perp-spot spread>band; long cheap/short rich | exit spread mean; tight SL | perp+spot, funding | hedged | min–hours | dislocation | arbitragescanner; ccxt | **partial** 

**K108. Latency / Lead-Lag (BTC leads alts)** | x-exchange | BTC move leads alt perps by seconds | LONG alt perp when BTC breaks first (lead signal) | exit alt catches up; tight SL | BTC ret lead, alt price | 2–3× | 1m–5m | high correlation | quant lit; awesome-quant | **partial** (cross-asset lead; ret usable) 

---

## FAMILY L — Market-making & grid on perps (109–116)

**L109. Pure Grid (perp)** | grid/MM | ladder buy/sell orders harvest oscillation | place N grid orders ±step around mid; each fill opens/closes perp position | exit on grid bounds / trend filter stop; liq-aware spacing | grid step, range bounds | 1–2× (grid risk) | continuous | ranging | OctoBot grid; Hummingbot | **partial** (range/atr_pct to size grid) 

**L110. Geometric Grid** | grid/MM | percentage-spaced grid for wide ranges | geometric step grid around mid | exit bounds; trend cutoff | % step, bounds | 1–2× | continuous | range/vol | OctoBot; Pionex-style | **partial** 

**L111. Trend-Adaptive Grid (directional)** | grid/MM | bias grid up/down with EMA trend | skew grid long in uptrend; flip in downtrend | exit trend reversal; SL bound | grid + EMA(50) | 1–2× | continuous | mild trend | OctoBot strategy designer | **partial** 

**L112. ATR-Spaced Grid** | grid/MM | space grid by volatility not fixed % | grid step = k×ATR; re-grid as ATR changes | exit bound/trend; liq-aware | ATR(14), grid | 1–2× | continuous | vol regimes | community; backtrader | **yes** (atr defines spacing) 

**L113. Pure Market-Making (perp)** | MM | symmetric bid/ask quotes around mid, manage inventory | place limit bid/ask at ±spread; skew on inventory | exit/flatten on inventory or vol spike; liq-aware | spread, inventory target | 1–2× | continuous | calm/liquid | Hummingbot perpetual MM | **no** (needs L2 book/inventory engine) 

**L114. Avellaneda-Stoikov MM** | MM | optimal reservation price + spread from inventory & vol | quote around reservation price r = s − q·γ·σ²·(T−t); spread from γ,κ | flatten near close / vol spike; inventory risk control | γ (risk), σ, κ (book liquidity) | 1–2× | continuous | liquid | Hummingbot avellaneda; Avellaneda-Stoikov paper | **no** (order-book intensity) 

**L115. Funding-Aware MM Skew** | MM/funding | skew quotes to earn funding while making | bias inventory to funding-favored side; quote both sides | flatten on funding flip / vol; liq-aware | spread + funding | 1–2× | continuous | positive funding | Hummingbot perpetual MM | **partial**→**no** (book + funding) 

**L116. Spread/Liquidity-Provision Rebate** | MM | passive maker capturing spread + rebates | post inside spread; cancel/replace on book shifts | flatten on adverse move; SL | spread, book | 1–2× | continuous | liquid | Hummingbot; dYdX bounty | **no** (book required) 

---

## FAMILY M — Orderflow / CVD (partial-to-no, flagged) (117–120)

**M117. CVD Divergence Reversal** | orderflow | price HH but CVD lower (selling into strength) → reversal | SHORT on bearish CVD/price divergence at resistance; mirror | exit reversion; SL beyond extreme | CVD (aggressor trades), price | 2–3× | 5m–1h | exhaustion | Bookmap/Phemex CVD; MarketTrace | **no** (tick aggressor data) 

**M118. CVD Trend Confirmation** | orderflow | rising price + rising CVD = real buying, follow | LONG when price & CVD both rising (per-exchange) | exit CVD rolls over; trail | CVD, price | 2–3× | 5m–15m | trend | MarketTrace CVD guide | **no** 

**M119. CVD + Funding + Book Confluence** | orderflow | combine aggressor flow, funding, book imbalance | enter when CVD, funding bias, and book imbalance align | exit any leg flips; SL ATR | CVD + funding + L2 imbalance | 2–3× | 1m–15m | high-conviction | MarketTrace; INCRYPTED CVD Pro | **no** 

**M120. Absorption / Delta-Exhaustion Scalp** | orderflow | large delta with no price progress = absorption → reversal | fade when heavy one-sided delta fails to move price | exit on snap-back; tight SL | footprint/delta, price | 2–3× | 1m–5m | absorption | ATAS; Bookmap | **no** 

---

## Genome-mappability summary
- **`yes` (drop-in, pure TA genome): 36** — A1,A2,A3,A4,A6,A7,A9,A15,A16, B17,B18,B19,B20,B21,B22,B23,B24,B25,B28, C29,C30,C31,C32,C33,C34,C35,C36,C37,C38,C40,C41, D43,D44,D45,D49,D50,D56, L112. (TA features + threshold/crossover/zscore/range_pct cover these.)
- **`partial` (TA + a funding/basis/OI/liq/LS series — all available via in-repo ccxt + liquidation calc): ~70** — all of Family E,F,G,H,I,J,K plus A5,A8,A10–A14, B26,B27, C39,C42, D46–D48,D51–D55, L109–L111,L115.
- **`no` (needs orderflow/CVD/L2-book ticks we don't ingest): 9** — L113,L114,L116, M117,M118,M119,M120 (+L115 book-side, A11/A13 only loosely).

## Implementation notes for our engine
- Funding/basis/OI/LS/premium-index/liquidation are **all reachable today**: ccxt `fetchFundingRate(History)`, Binance `/futures/data` (OI, long/short ratio, premium index), and our existing liquidation-distance calc. These power Families E–K as "partial" with only a new data column per genome.
- **Liq-aware sizing is universal:** for every leveraged template, enforce `stop_distance < liquidation_distance` (maint-margin aware) — freqtrade explicitly warns a 50% SL at 2× liquidates first. Encode as a hard constraint on (leverage, SL) pairs.
- Delta-neutral families (E,F,K107) carry near-zero directional genome signal — they are **yield/carry overlays**, scored on funding/basis capture minus fees + basis risk, not on TA fitness.
- Orderflow family (M) is parked until/if we ingest trade-tick aggressor data (cryptofeed FUNDING/LIQUIDATIONS channels noted in our screener research could be extended to TRADES for CVD).
