# MCX Commodities Strategy Templates (bullion / energy / base metals — intraday + positional)
# Curated for the ML-network trading phase. Genome = TA features {ret, sma, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol} + {threshold, crossover} ops. Strategy count: 124

> Symbols referenced: GOLD, GOLDM, GOLDGUINEA, SILVER, SILVERM, SILVERMIC, CRUDEOIL, CRUDEOILM, NATURALGAS, NATGASMINI, COPPER, ZINC, ALUMINIUM, LEAD, NICKEL. MCX session ~09:00–23:30 IST (energy/metals to 23:30 winter, 23:55 summer; bullion to 23:30/23:55). "Genome-mappable" judged against the TA feature genome above.

---

## FAMILY A — Trend-following (EMA / Supertrend / ADX / Donchian)

### A1. EMA 9/21 Crossover Trend (Crude/NatGas intraday)
- **Family:** Trend-following | **Timeframe:** 5m / 15m intraday
- **Core logic:** Ride directional momentum once fast EMA crosses slow EMA in trending energy markets.
- **Entry:** Long when EMA9 crosses above EMA21 (short on reverse), price on same side of both.
- **Exit:** SL = 1.5×ATR(14) from entry; trail with EMA21; exit on opposite cross.
- **Indicators/params:** EMA(9), EMA(21), ATR(14).
- **Regime/seasonality fit:** Trending; avoid lunch-hour chop.
- **Source:** Upstox MCX strategies guide; StockGro intraday.
- **Genome-mappable:** yes (ema crossover + atr SL).

### A2. EMA 20/50/200 Triple-Stack Trend (Gold positional)
- **Family:** Trend-following | **Timeframe:** Daily positional
- **Core logic:** Trade only in direction of long-term trend confirmed by stacked EMAs.
- **Entry:** Long when EMA20>EMA50>EMA200 and price pulls back to EMA20 then closes up.
- **Exit:** SL below EMA50; trail EMA50; exit when EMA20 crosses below EMA50.
- **Indicators/params:** EMA(20/50/200).
- **Regime/seasonality fit:** Strong bullion trends (e.g. gold bull years).
- **Source:** Zerodha Varsity moving-average module.
- **Genome-mappable:** yes.

### A3. Supertrend Flip (10,3) Intraday
- **Family:** Trend-following | **Timeframe:** 5m/15m
- **Core logic:** ATR-band trend filter; trade flips of the Supertrend line.
- **Entry:** Long on green flip (price closes above Supertrend), short on red flip.
- **Exit:** Supertrend line as trailing SL; flat on opposite flip.
- **Indicators/params:** Supertrend(ATR period 10, mult 3) = derived from atr + price.
- **Regime/seasonality fit:** Trending energy/metals; whipsaws in range.
- **Source:** Finversify MCX crude guide; TradingView NATGASMINI ideas.
- **Genome-mappable:** yes (Supertrend = atr-band rule reproducible from atr+close threshold).

### A4. Supertrend + RSI Confirmation
- **Family:** Trend-following | **Timeframe:** 15m
- **Core logic:** Supertrend direction filtered by RSI not at exhaustion.
- **Entry:** Long when Supertrend green AND RSI(14) between 50–70.
- **Exit:** Supertrend trail; exit if RSI>80 or red flip.
- **Indicators/params:** Supertrend(10,3), RSI(14).
- **Regime/seasonality fit:** Trending crude/copper.
- **Source:** Upstox guide (Supertrend+RSI multi-TF).
- **Genome-mappable:** yes.

### A5. ADX Trend-Strength Filter Trend
- **Family:** Trend-following | **Timeframe:** 15m/daily
- **Core logic:** Only take EMA-trend trades when ADX confirms a strong trend.
- **Entry:** Long when ADX(14)>25 and +DI>-DI and price>EMA50.
- **Exit:** Exit when ADX<20 or DI cross; SL 2×ATR.
- **Indicators/params:** ADX/DI(14), EMA(50), ATR.
- **Regime/seasonality fit:** Filters chop; good for copper/crude.
- **Source:** awesome-quant indicator libs; Wilder ADX.
- **Genome-mappable:** partial (ADX/DI not in genome; approximate with mom + atr_pct trend strength proxy).

### A6. Donchian 20-day Breakout (Turtle System 1)
- **Family:** Trend-following / breakout | **Timeframe:** Daily positional
- **Core logic:** Classic turtle — buy 20-day high breakouts, ATR position sizing.
- **Entry:** Buy when price > highest-high(20); sell when < lowest-low(20).
- **Exit:** 2N (2×ATR) stop; exit on 10-day opposite extreme.
- **Indicators/params:** Donchian(20), Donchian(10), ATR(20)=N.
- **Regime/seasonality fit:** Trending commodities (Donchian works on commodities not stocks).
- **Source:** Turtle Trading (Dennis/Eckhardt); QuantifiedStrategies Donchian backtest.
- **Genome-mappable:** yes (Donchian = rolling max/min → range_pct/threshold).

### A7. Donchian 55-day Breakout (Turtle System 2)
- **Family:** Trend-following / breakout | **Timeframe:** Daily positional
- **Core logic:** Slower turtle channel for major moves, fewer whipsaws.
- **Entry:** Buy 55-day high / sell 55-day low.
- **Exit:** 2N stop; exit on 20-day opposite extreme.
- **Indicators/params:** Donchian(55/20), ATR(20).
- **Regime/seasonality fit:** Long sustained metal/bullion trends.
- **Source:** Turtle rules; Alchemy Markets turtle guide.
- **Genome-mappable:** yes.

### A8. Donchian Mid-line Pullback Continuation
- **Family:** Trend-following | **Timeframe:** 1h/daily
- **Core logic:** In uptrend, buy pullbacks to Donchian midline.
- **Entry:** Uptrend (price>upper recently); buy on touch of mid-line with up-close.
- **Exit:** SL below lower band; target upper band.
- **Indicators/params:** Donchian(20).
- **Regime/seasonality fit:** Trending crude/gold.
- **Source:** TrendSpider Donchian strategies.
- **Genome-mappable:** yes.

### A9. EMA Ribbon Expansion (Aluminium/Zinc)
- **Family:** Trend-following | **Timeframe:** 15m/1h
- **Core logic:** Multiple EMAs fanning out signal accelerating trend.
- **Entry:** Long when EMA8>13>21>34 all rising and separating.
- **Exit:** Exit on ribbon compression/cross; ATR trail.
- **Indicators/params:** EMA(8,13,21,34).
- **Regime/seasonality fit:** Strong base-metal trends.
- **Source:** awesome-quant TA; ribbon technique.
- **Genome-mappable:** yes.

### A10. Hull/Smoothed MA Trend (low-lag)
- **Family:** Trend-following | **Timeframe:** 15m
- **Core logic:** Faster-reacting smoothed MA reduces lag vs EMA.
- **Entry:** Long on HMA(21) turning up + price above.
- **Exit:** HMA turn down; 1.5×ATR SL.
- **Indicators/params:** HMA(21) (approx via weighted ema), ATR.
- **Regime/seasonality fit:** Fast intraday crude moves.
- **Source:** backtrader indicator examples.
- **Genome-mappable:** partial (HMA approximated by ema blend).

### A11. MACD Trend Momentum (Daily metals)
- **Family:** Trend-following | **Timeframe:** Daily
- **Core logic:** MACD line/signal cross with histogram momentum.
- **Entry:** Long when MACD(12,26,9) crosses above signal above zero.
- **Exit:** Cross below signal; SL 2×ATR.
- **Indicators/params:** MACD(12,26,9) = ema diff.
- **Regime/seasonality fit:** Trending copper/gold.
- **Source:** backtrader MACD sample.
- **Genome-mappable:** yes (MACD = ema(12)-ema(26) crossover).

### A12. Heikin-Ashi Trend Continuation
- **Family:** Trend-following | **Timeframe:** 15m/1h
- **Core logic:** Smoothed HA candles filter noise; stay in while same color.
- **Entry:** Long on first bullish HA candle after EMA20 cross.
- **Exit:** Exit on opposite HA color with body; ATR trail.
- **Indicators/params:** Heikin-Ashi, EMA(20).
- **Regime/seasonality fit:** Trending; reduces whipsaw.
- **Source:** TradingView HA strategies.
- **Genome-mappable:** partial (HA = derived OHLC averages; needs candle transform).

---

## FAMILY B — Momentum

### B1. ROC Momentum (Crude positional)
- **Family:** Momentum | **Timeframe:** Daily
- **Core logic:** Buy when N-day rate-of-change is strongly positive.
- **Entry:** Long when ROC(20)>threshold (e.g. +5%).
- **Exit:** Exit when ROC<0; SL 2×ATR.
- **Indicators/params:** ROC/mom(20).
- **Regime/seasonality fit:** Trending energy.
- **Source:** awesome-quant momentum literature.
- **Genome-mappable:** yes (mom + threshold).

### B2. 12-1 Time-Series Momentum
- **Family:** Momentum | **Timeframe:** Monthly/weekly positional
- **Core logic:** Classic TSMOM — go long if past 12m return (skip last) positive.
- **Entry:** Long if trailing return positive; short if negative.
- **Exit:** Rebalance monthly on sign flip.
- **Indicators/params:** ret(252) lagged 21.
- **Regime/seasonality fit:** Works across commodity futures (Moskowitz TSMOM).
- **Source:** Moskowitz-Ooi-Pedersen "Time Series Momentum"; QuantPedia.
- **Genome-mappable:** yes (ret + sign threshold).

### B3. RSI Momentum Continuation (50-line)
- **Family:** Momentum | **Timeframe:** 15m/1h
- **Core logic:** RSI staying above 50 = bullish momentum regime.
- **Entry:** Long when RSI(14) crosses above 50 with rising price.
- **Exit:** RSI<45; SL 1.5×ATR.
- **Indicators/params:** RSI(14).
- **Regime/seasonality fit:** Trending intraday.
- **Source:** Zerodha Varsity RSI.
- **Genome-mappable:** yes.

### B4. Relative-Momentum Rotation (metals basket)
- **Family:** Momentum | **Timeframe:** Weekly
- **Core logic:** Rotate into strongest base metal by trailing return.
- **Entry:** Long top-ranked of {copper, zinc, aluminium, lead} by ret(63).
- **Exit:** Rotate weekly; drop if falls out of top rank.
- **Indicators/params:** ret(63) cross-sectional rank.
- **Regime/seasonality fit:** Dispersed base-metal trends.
- **Source:** cross-sectional momentum (Asness); awesome-quant.
- **Genome-mappable:** partial (needs cross-asset ranking layer).

### B5. Momentum + Volume Surge (rvol)
- **Family:** Momentum | **Timeframe:** 5m/15m
- **Core logic:** Momentum confirmed by relative-volume spike.
- **Entry:** Long when mom(10)>0 and rvol>1.5.
- **Exit:** rvol fade or mom flip; ATR SL.
- **Indicators/params:** mom(10), rvol(20).
- **Regime/seasonality fit:** News-driven crude moves.
- **Source:** StockGro intraday; volume confirmation.
- **Genome-mappable:** yes (mom + rvol + threshold).

### B6. Acceleration (2nd-derivative) Momentum
- **Family:** Momentum | **Timeframe:** 1h
- **Core logic:** Buy when momentum itself is accelerating.
- **Entry:** Long when mom(10) today > mom(10) prior and >0.
- **Exit:** Deceleration; ATR SL.
- **Indicators/params:** mom(10) delta.
- **Regime/seasonality fit:** Early-trend energy.
- **Source:** quant momentum-of-momentum.
- **Genome-mappable:** yes.

### B7. 52-week High Proximity (positional)
- **Family:** Momentum | **Timeframe:** Daily
- **Core logic:** Commodities near 52-wk high keep rising.
- **Entry:** Long when price within 2% of 252-day high.
- **Exit:** SL 5%; trail 20-day low.
- **Indicators/params:** range_pct vs rolling max(252).
- **Regime/seasonality fit:** Bull commodity regimes.
- **Source:** George-Hwang 52-week-high momentum.
- **Genome-mappable:** yes (range_pct + threshold).

---

## FAMILY C — Breakout (volatility / range)

### C1. Opening Range Breakout (ORB) 15-min (Crude)
- **Family:** Breakout intraday | **Timeframe:** 5m, ORB=first 15m
- **Core logic:** Trade break of first-15-min high/low after MCX open.
- **Entry:** Long > OR-high, short < OR-low (with rvol confirm).
- **Exit:** SL at opposite OR boundary; target 1×–2× OR range; trail.
- **Indicators/params:** OR(15m) high/low, rvol.
- **Regime/seasonality fit:** Crude high-volatility open / 18:00 IST US-data window.
- **Source:** Upstox MCX strategies; classic ORB.
- **Genome-mappable:** yes (range high/low threshold + rvol).

### C2. ORB 30-min (NatGas)
- **Family:** Breakout intraday | **Timeframe:** 5m, OR=30m
- **Core logic:** Wider OR for ultra-volatile natural gas.
- **Entry:** Break of 30-min range with momentum.
- **Exit:** ATR-based SL (wider, given natgas vol); 2R target.
- **Indicators/params:** OR(30m), ATR(14).
- **Regime/seasonality fit:** NatGas; use smaller size (60–100% vol).
- **Source:** Sarwa natgas strategies (wider stops/smaller size).
- **Genome-mappable:** yes.

### C3. Bollinger Band Squeeze Breakout
- **Family:** Volatility breakout | **Timeframe:** 15m/1h
- **Core logic:** Low-volatility squeeze precedes expansion.
- **Entry:** When BB width at N-period low, enter on close outside band.
- **Exit:** Opposite band / middle band; ATR SL.
- **Indicators/params:** BB(20,2) width (=sma±k·std → zscore), ATR.
- **Regime/seasonality fit:** Pre-breakout consolidation any commodity.
- **Source:** awesome-quant; Bollinger.
- **Genome-mappable:** yes (BB = sma + std → zscore/threshold).

### C4. Keltner Channel Breakout
- **Family:** Volatility breakout | **Timeframe:** 15m
- **Core logic:** Break of ATR-based channel around EMA.
- **Entry:** Close above EMA20 + 2×ATR.
- **Exit:** Back inside channel; trail EMA.
- **Indicators/params:** EMA(20), ATR(14) mult 2.
- **Regime/seasonality fit:** Trending breakouts copper/crude.
- **Source:** backtrader Keltner; Chester Keltner.
- **Genome-mappable:** yes (ema + atr band threshold).

### C5. TTM Squeeze (BB inside Keltner)
- **Family:** Volatility breakout | **Timeframe:** 15m/1h
- **Core logic:** Fire long when BB exits Keltner (squeeze release) with momentum.
- **Entry:** Squeeze-off + positive momentum histogram.
- **Exit:** Momentum flip; ATR SL.
- **Indicators/params:** BB(20,2), Keltner(20,1.5), mom.
- **Regime/seasonality fit:** Coiled metals before data.
- **Source:** John Carter TTM Squeeze.
- **Genome-mappable:** yes (combine zscore band vs atr band + mom).

### C6. NR7 / Inside-Bar Breakout
- **Family:** Range breakout | **Timeframe:** Daily/1h
- **Core logic:** Narrowest-range-7 bar signals impending expansion.
- **Entry:** Buy break of NR7 bar high, sell break of low.
- **Exit:** Opposite side of NR7 bar SL; 2R target.
- **Indicators/params:** range_pct (7-bar min).
- **Regime/seasonality fit:** Low-vol coil any commodity.
- **Source:** Crabel "Day Trading with Short Term Price Patterns".
- **Genome-mappable:** yes (range_pct min + threshold).

### C7. Volatility-Contraction Pattern (VCP)
- **Family:** Range breakout | **Timeframe:** Daily
- **Core logic:** Successively tighter pullbacks then breakout.
- **Entry:** Breakout from contracting ATR_pct base.
- **Exit:** SL below base; trail.
- **Indicators/params:** atr_pct contraction, range_pct.
- **Regime/seasonality fit:** Bullion accumulation.
- **Source:** Minervini VCP (adapted to commodities).
- **Genome-mappable:** yes (atr_pct decline + breakout threshold).

### C8. Previous-Day High/Low Breakout
- **Family:** Range breakout intraday | **Timeframe:** 5m/15m
- **Core logic:** PDH/PDL act as intraday breakout triggers.
- **Entry:** Long > prior-day high, short < prior-day low.
- **Exit:** SL midpoint of prior range; trail.
- **Indicators/params:** prior-day H/L (range).
- **Regime/seasonality fit:** Trend-day crude/copper.
- **Source:** StockGro intraday; common MCX desk rule.
- **Genome-mappable:** yes (rolling daily H/L threshold).

### C9. Weekly High/Low Breakout (positional)
- **Family:** Range breakout | **Timeframe:** Daily/weekly
- **Core logic:** Break of prior week's range for swing entries.
- **Entry:** Close above prior-week high.
- **Exit:** SL prior-week low; trail weekly.
- **Indicators/params:** rolling 5-day H/L.
- **Regime/seasonality fit:** Swing bullion/metals.
- **Source:** classic swing breakout.
- **Genome-mappable:** yes.

### C10. ATR Expansion Trigger
- **Family:** Volatility breakout | **Timeframe:** 15m
- **Core logic:** Sudden ATR jump signals regime shift; trade with direction.
- **Entry:** When atr_pct spikes >X and close breaks recent range.
- **Exit:** ATR normalizes; trail.
- **Indicators/params:** atr_pct, range_pct.
- **Regime/seasonality fit:** Event/data spikes.
- **Source:** volatility-breakout literature.
- **Genome-mappable:** yes.

### C11. Range-Compression Pivot Breakout
- **Family:** Range breakout | **Timeframe:** 5m intraday
- **Core logic:** After tight midday range, trade breakout into close.
- **Entry:** Break of 11:30–14:00 IST consolidation box.
- **Exit:** Box-height target; box-mid SL.
- **Indicators/params:** intraday range_pct.
- **Regime/seasonality fit:** Afternoon metals.
- **Source:** intraday box theory.
- **Genome-mappable:** yes.

---

## FAMILY D — Mean-reversion

### D1. RSI(2) Oversold Reversion
- **Family:** Mean-reversion | **Timeframe:** Daily/1h
- **Core logic:** Short-period RSI extreme snaps back in range markets.
- **Entry:** Long when RSI(2)<5 and price>SMA200 (uptrend filter).
- **Exit:** Exit when RSI(2)>70 or price>SMA5.
- **Indicators/params:** RSI(2), SMA(200/5).
- **Regime/seasonality fit:** Range/uptrend pullbacks (gold).
- **Source:** Larry Connors RSI(2); QuantifiedStrategies.
- **Genome-mappable:** yes.

### D2. Bollinger Band Fade
- **Family:** Mean-reversion | **Timeframe:** 15m/daily
- **Core logic:** Price tags outer band then reverts to mean in range.
- **Entry:** Long on close below lower BB(20,2); short above upper.
- **Exit:** Target middle band; SL 1×ATR beyond band.
- **Indicators/params:** BB(20,2) = zscore.
- **Regime/seasonality fit:** Range-bound metals/bullion.
- **Source:** awesome-quant; Bollinger reversion.
- **Genome-mappable:** yes (zscore threshold).

### D3. Z-Score Reversion
- **Family:** Mean-reversion | **Timeframe:** 1h/daily
- **Core logic:** Trade extreme deviations from rolling mean.
- **Entry:** Long when zscore(close,20)<-2; short >+2.
- **Exit:** zscore back to 0; SL at -3.
- **Indicators/params:** zscore(20).
- **Regime/seasonality fit:** Mean-reverting/range regimes.
- **Source:** stat-arb reversion literature.
- **Genome-mappable:** yes (native zscore).

### D4. VWAP Reversion (intraday)
- **Family:** Mean-reversion | **Timeframe:** 5m intraday
- **Core logic:** Price stretched from VWAP reverts intraday.
- **Entry:** Long when price < VWAP − 2σ band; short above +2σ.
- **Exit:** Target VWAP; SL further band.
- **Indicators/params:** VWAP, VWAP std bands.
- **Regime/seasonality fit:** Range days in liquid crude/copper.
- **Source:** Upstox VWAP usage; intraday desk standard.
- **Genome-mappable:** partial (VWAP needs volume-weighted price, not in genome; approximate with sma/zscore).

### D5. RSI Divergence Reversal
- **Family:** Mean-reversion | **Timeframe:** 1h
- **Core logic:** Price new low but RSI higher low = reversal.
- **Entry:** Bullish divergence at support.
- **Exit:** Prior swing high target; SL below low.
- **Indicators/params:** RSI(14), swing pivots.
- **Regime/seasonality fit:** Exhausted moves.
- **Source:** classic divergence.
- **Genome-mappable:** partial (divergence = pattern over rsi + price, needs pivot detection).

### D6. Mean Reversion to Moving Average (gap-to-MA)
- **Family:** Mean-reversion | **Timeframe:** Daily
- **Core logic:** Price far above/below SMA reverts.
- **Entry:** Long when (close−SMA50)/SMA50 < −X% in uptrend.
- **Exit:** Touch of SMA20; SL 2×ATR.
- **Indicators/params:** SMA(50/20), ret distance.
- **Regime/seasonality fit:** Overstretched bullion pullbacks.
- **Source:** Connors/QuantifiedStrategies.
- **Genome-mappable:** yes.

### D7. Overnight Gap Fade (bullion)
- **Family:** Mean-reversion | **Timeframe:** Daily open
- **Core logic:** Outsized opening gap (vs intl close) often fades.
- **Entry:** Fade gap > 1×ATR at open back toward prev close.
- **Exit:** Prev close target; SL beyond gap extreme.
- **Indicators/params:** gap size vs ATR.
- **Regime/seasonality fit:** Gold/silver gap from COMEX overnight.
- **Source:** gap-fade futures literature.
- **Genome-mappable:** yes (open-vs-prevclose ret + atr threshold).

### D8. Bollinger %B Reversion Bands
- **Family:** Mean-reversion | **Timeframe:** 15m
- **Core logic:** %B>1 overbought, <0 oversold in range.
- **Entry:** Long %B<0; short %B>1.
- **Exit:** %B=0.5; SL band.
- **Indicators/params:** %B from BB(20,2).
- **Regime/seasonality fit:** Range metals.
- **Source:** Bollinger %B.
- **Genome-mappable:** yes (zscore variant).

### D9. CCI Extreme Reversion
- **Family:** Mean-reversion | **Timeframe:** 1h
- **Core logic:** CCI ±200 marks overextension.
- **Entry:** Long CCI<−200; short >+200.
- **Exit:** CCI back to 0.
- **Indicators/params:** CCI(20).
- **Regime/seasonality fit:** Range commodities.
- **Source:** Lambert CCI.
- **Genome-mappable:** partial (CCI ≈ zscore of typical price; close proxy).

---

## FAMILY E — ATR channels / volatility bands

### E1. ATR Trailing-Stop Trend (Chandelier Exit)
- **Family:** ATR channel trend | **Timeframe:** Daily/1h
- **Core logic:** Trail long below highest-high − 3×ATR.
- **Entry:** With trend (price>EMA50).
- **Exit:** Chandelier stop hit.
- **Indicators/params:** ATR(22)×3, rolling high.
- **Regime/seasonality fit:** Trending metals.
- **Source:** Chuck LeBeau Chandelier; backtrader.
- **Genome-mappable:** yes (atr + rolling high threshold).

### E2. ATR Channel Breakout (Crude)
- **Family:** ATR channel | **Timeframe:** 15m
- **Core logic:** Bands = close ± k×ATR; break = signal.
- **Entry:** Close above upper band.
- **Exit:** Mid/opposite band.
- **Indicators/params:** ATR(14) mult 2.5.
- **Regime/seasonality fit:** Volatile energy.
- **Source:** ATR channel technique.
- **Genome-mappable:** yes.

### E3. Volatility-Adjusted Position Sizing Overlay
- **Family:** ATR risk overlay | **Timeframe:** any
- **Core logic:** Size inversely to atr_pct so risk per trade is constant.
- **Entry:** Any base signal; size = risk$/(ATR×lot).
- **Exit:** Base exit.
- **Indicators/params:** ATR, atr_pct.
- **Regime/seasonality fit:** Essential for natgas/crude vol differences.
- **Source:** Turtle N-sizing; QuantPedia vol-targeting.
- **Genome-mappable:** yes (atr_pct as sizing input).

### E4. ATR Percent-Rank Regime Switch
- **Family:** Volatility regime | **Timeframe:** Daily
- **Core logic:** Use trend rules in high-vol, reversion in low-vol.
- **Entry:** If atr_pct percentile>70 → breakout module; <30 → reversion module.
- **Exit:** Per active module.
- **Indicators/params:** atr_pct percentile.
- **Regime/seasonality fit:** Adaptive across metals.
- **Source:** regime-switching vol literature.
- **Genome-mappable:** yes (atr_pct threshold gates).

### E5. Standard-Deviation Channel Trend
- **Family:** Volatility band | **Timeframe:** 1h
- **Core logic:** Linear-regression channel ± k·std for trend ride.
- **Entry:** Bounce off lower band in uptrend.
- **Exit:** Upper band; band break SL.
- **Indicators/params:** regression(50), std (zscore).
- **Regime/seasonality fit:** Steady trends.
- **Source:** stat band technique.
- **Genome-mappable:** partial (regression slope not native; zscore approximates).

---

## FAMILY F — Seasonality

### F1. Gold Q4 Festive/Wedding Seasonal (India)
- **Family:** Seasonality positional | **Timeframe:** Daily, Sep–Nov hold
- **Core logic:** Indian festive+wedding physical demand lifts gold into Diwali.
- **Entry:** Long GOLD late Aug/Sep.
- **Exit:** Exit Nov; SL 3×ATR.
- **Indicators/params:** calendar window + trend filter (ema).
- **Regime/seasonality fit:** Strong India bullion seasonality.
- **Source:** MCX/Zerodha Varsity commodities; Bookmap seasonal futures.
- **Genome-mappable:** partial (needs calendar/date input + ema confirm).

### F2. Gold January Effect
- **Family:** Seasonality | **Timeframe:** Daily, Dec–Feb
- **Core logic:** Gold tends to rally early year (jewelry restock).
- **Entry:** Long late Dec.
- **Exit:** Exit Feb.
- **Indicators/params:** calendar.
- **Regime/seasonality fit:** Bullion turn-of-year.
- **Source:** Forecaster.biz commodity seasonality; Bookmap.
- **Genome-mappable:** partial (date-driven).

### F3. Silver January & July Long
- **Family:** Seasonality | **Timeframe:** Daily monthly
- **Core logic:** Jan positive ~69.5%, Jul ~63.6%; avoid Jun/Sep.
- **Entry:** Long start of Jan and Jul.
- **Exit:** End of month; SL ATR-based.
- **Indicators/params:** calendar + monthly seasonality table.
- **Regime/seasonality fit:** Silver-specific.
- **Source:** QuantifiedStrategies "Silver Seasonal Strategy".
- **Genome-mappable:** partial (calendar input required).

### F4. NatGas Winter Heating Long
- **Family:** Seasonality | **Timeframe:** Daily, Oct–Jan
- **Core logic:** Cold-season heating demand lifts gas; strongest seasonal of any commodity.
- **Entry:** Long NATURALGAS Oct/Nov.
- **Exit:** Exit Jan/Feb; wide ATR stop (high vol).
- **Indicators/params:** calendar + ATR (wide stop).
- **Regime/seasonality fit:** Winter; polar vortex can override.
- **Source:** Bookmap; Sharpnel commodity seasonality; EIA storage.
- **Genome-mappable:** partial (calendar + vol sizing).

### F5. NatGas Shoulder-Season Short (spring)
- **Family:** Seasonality | **Timeframe:** Daily, Feb–Apr
- **Core logic:** Post-winter demand collapse pressures gas.
- **Entry:** Short late Feb after winter peak.
- **Exit:** Apr; ATR SL.
- **Indicators/params:** calendar + trend filter.
- **Regime/seasonality fit:** Spring shoulder season.
- **Source:** commodity seasonality guides.
- **Genome-mappable:** partial.

### F6. Crude Summer Driving-Season Long
- **Family:** Seasonality | **Timeframe:** Daily, Apr–Jul
- **Core logic:** US driving season raises gasoline/crude demand.
- **Entry:** Long crude spring into summer.
- **Exit:** Exit mid-summer; ATR SL.
- **Indicators/params:** calendar.
- **Regime/seasonality fit:** Crude summer; highest prices traded in summer.
- **Source:** ScienceDirect time-seasonality; Bookmap.
- **Genome-mappable:** partial.

### F7. Crude Autumn/Winter Softness Short
- **Family:** Seasonality | **Timeframe:** Daily, Sep–Dec
- **Core logic:** Lower seasonal demand post-summer.
- **Entry:** Short crude autumn.
- **Exit:** Year-end; ATR SL.
- **Indicators/params:** calendar.
- **Regime/seasonality fit:** Crude seasonal low in winter trading.
- **Source:** ScienceDirect seasonality study.
- **Genome-mappable:** partial.

### F8. Copper Spring Construction Demand
- **Family:** Seasonality | **Timeframe:** Daily, Feb–Apr
- **Core logic:** China/global construction restart lifts copper.
- **Entry:** Long copper late winter.
- **Exit:** Spring; ATR SL.
- **Indicators/params:** calendar + trend.
- **Regime/seasonality fit:** Base-metal industrial seasonality.
- **Source:** InsiderWeek seasonal charts.
- **Genome-mappable:** partial.

### F9. Front-Running Seasonality (early entry)
- **Family:** Seasonality | **Timeframe:** Daily
- **Core logic:** Enter ~1–2 weeks before the known seasonal window to beat crowd.
- **Entry:** Early relative to seasonal table.
- **Exit:** At/just before traditional seasonal exit.
- **Indicators/params:** seasonal calendar shifted.
- **Regime/seasonality fit:** All seasonal commodities.
- **Source:** QuantPedia "Front-Running Commodity Seasonality".
- **Genome-mappable:** partial (calendar).

### F10. Seasonal + Trend Confluence Filter
- **Family:** Seasonality | **Timeframe:** Daily
- **Core logic:** Only take seasonal trade if price trend agrees.
- **Entry:** Seasonal window AND price>EMA50.
- **Exit:** Window end or trend break.
- **Indicators/params:** calendar + EMA(50).
- **Regime/seasonality fit:** Reduces seasonal false signals.
- **Source:** Sharpnel; quant seasonal best-practice.
- **Genome-mappable:** partial (ema part yes, calendar extra).

### F11. Day-of-Week / Turn-of-Month Effect
- **Family:** Seasonality | **Timeframe:** Daily
- **Core logic:** Commodity returns cluster around month turn.
- **Entry:** Long last day + first 3 days of month.
- **Exit:** After window.
- **Indicators/params:** calendar.
- **Regime/seasonality fit:** Mild edge bullion.
- **Source:** turn-of-month effect literature.
- **Genome-mappable:** partial (date input).

---

## FAMILY G — Inventory / EIA-event volatility

### G1. EIA Crude Inventory Surprise Breakout
- **Family:** Event volatility | **Timeframe:** 1m/5m, Wed ~20:00 IST
- **Core logic:** Trade direction of the post-EIA inventory move.
- **Entry:** After release, enter on break of the first post-news 1-min candle range.
- **Exit:** ATR-based; quick scalp 1–2R; flat before close.
- **Indicators/params:** ATR, post-event range; EIA calendar.
- **Regime/seasonality fit:** Crude EIA Wednesday; high vol.
- **Source:** Bitget "EIA/OPEC/geopolitical"; event-driven desk practice.
- **Genome-mappable:** partial (needs EIA event timestamp input; price part yes).

### G2. EIA NatGas Storage Surprise
- **Family:** Event volatility | **Timeframe:** 1m/5m, Thu ~20:00 IST
- **Core logic:** Storage draw/build surprise drives gas.
- **Entry:** Break of first post-release candle range.
- **Exit:** Wide ATR stop (natgas 60–100% vol); scalp.
- **Indicators/params:** ATR, EIA storage calendar.
- **Regime/seasonality fit:** NatGas Thursday.
- **Source:** Sarwa natgas strategies; EIA reports.
- **Genome-mappable:** partial (event input).

### G3. Pre-EIA Volatility Squeeze Position
- **Family:** Event volatility | **Timeframe:** 5m
- **Core logic:** Volatility contracts before release; straddle the break.
- **Entry:** Set buy-stop above / sell-stop below pre-release range.
- **Exit:** Opposite stop / ATR trail.
- **Indicators/params:** range_pct pre-event, ATR.
- **Regime/seasonality fit:** Crude/natgas inventory days.
- **Source:** event-vol breakout practice.
- **Genome-mappable:** partial (event timing).

### G4. OPEC Meeting Volatility Play
- **Family:** Event volatility | **Timeframe:** Intraday
- **Core logic:** OPEC+ decisions trigger crude gaps; trade follow-through.
- **Entry:** Break of pre-announcement range post-decision.
- **Exit:** ATR trail.
- **Indicators/params:** ATR, OPEC calendar.
- **Regime/seasonality fit:** Crude event days.
- **Source:** Bitget oil-price drivers.
- **Genome-mappable:** partial (event input).

### G5. Inventory-Mean-Reversion Fade
- **Family:** Event volatility | **Timeframe:** 5m
- **Core logic:** Initial EIA spike often over-reacts then partially reverts.
- **Entry:** Fade the first spike after it stalls (rvol fade).
- **Exit:** Partial retrace target; tight SL beyond extreme.
- **Indicators/params:** rvol, ATR.
- **Regime/seasonality fit:** Crude/natgas post-spike.
- **Source:** event over-reaction literature.
- **Genome-mappable:** partial (event input; rvol/atr yes).

### G6. Storage-vs-5yr-Average Bias
- **Family:** Inventory positional | **Timeframe:** Daily/weekly
- **Core logic:** Inventories below 5-yr avg = bullish bias; above = bearish.
- **Entry:** Bias long natgas/crude when stocks <5yr avg.
- **Exit:** Bias flips; trend SL.
- **Indicators/params:** EIA storage series (external).
- **Regime/seasonality fit:** Fundamental overlay.
- **Source:** EIA Today-in-Energy; Discovery Alert inventory analysis.
- **Genome-mappable:** no (external fundamental series).

---

## FAMILY H — Gold-silver ratio & inter-commodity spreads

### H1. Gold-Silver Ratio Mean Reversion
- **Family:** Inter-commodity spread | **Timeframe:** Daily
- **Core logic:** GSR mean-reverts; long laggard / short leader at extremes.
- **Entry:** When zscore(GSR,252)>+2 short gold/long silver; <−2 reverse.
- **Exit:** GSR back to mean; SL at ±3.
- **Indicators/params:** GSR = GOLD/SILVER, zscore(252).
- **Regime/seasonality fit:** Range-bound ratio regimes.
- **Source:** CME "Gold & Silver Ratio Spread"; QuantStrategy.io spreads.
- **Genome-mappable:** partial (needs 2-symbol ratio series; then native zscore).

### H2. Gold-Silver Ratio Trend (industrial cycle)
- **Family:** Inter-commodity | **Timeframe:** Weekly
- **Core logic:** GSR trends with risk-on/off (silver industrial beta).
- **Entry:** Follow GSR breakout direction.
- **Exit:** Trend break.
- **Indicators/params:** GSR + Donchian/ema.
- **Regime/seasonality fit:** Macro risk regimes.
- **Source:** CME precious-metals spreads.
- **Genome-mappable:** partial.

### H3. GOLD-GOLDM / SILVER-SILVERM Calendar/Contract Arb
- **Family:** Intra-commodity spread | **Timeframe:** Intraday
- **Core logic:** Mispricing between standard and mini bullion contracts.
- **Entry:** Spread deviates beyond fair band.
- **Exit:** Convergence.
- **Indicators/params:** spread zscore.
- **Regime/seasonality fit:** Microstructure; always-on.
- **Source:** QuantStrategy.io intra-commodity spreads.
- **Genome-mappable:** partial (2-leg spread).

### H4. Copper-Gold Ratio Macro Signal
- **Family:** Inter-commodity | **Timeframe:** Daily/weekly
- **Core logic:** Copper/Gold ratio = growth vs fear gauge; trade ratio extremes.
- **Entry:** Ratio zscore extreme reversion or breakout.
- **Exit:** Mean / trend break.
- **Indicators/params:** COPPER/GOLD, zscore.
- **Regime/seasonality fit:** Macro cyclical.
- **Source:** macro copper/gold ratio analysis.
- **Genome-mappable:** partial.

### H5. Crude-NatGas Energy Spread
- **Family:** Inter-commodity | **Timeframe:** Daily
- **Core logic:** Oil/gas ratio mean-reverts around energy-equivalence.
- **Entry:** Ratio zscore>+2 long gas/short crude; reverse <−2.
- **Exit:** Mean revert.
- **Indicators/params:** CRUDE/NATGAS ratio, zscore.
- **Regime/seasonality fit:** Range; breaks on supply shocks.
- **Source:** energy spread literature; QuantStrategy.io.
- **Genome-mappable:** partial.

### H6. Zinc-Lead Sister-Metal Spread
- **Family:** Inter-commodity | **Timeframe:** Daily
- **Core logic:** Co-mined metals revert in relative price.
- **Entry:** Spread zscore extreme.
- **Exit:** Convergence.
- **Indicators/params:** ZINC−LEAD spread zscore.
- **Regime/seasonality fit:** Range.
- **Source:** CME metals spread whitepaper.
- **Genome-mappable:** partial.

### H7. Aluminium-Copper Base-Metal Spread
- **Family:** Inter-commodity | **Timeframe:** Daily
- **Core logic:** Substitution/relative-value reversion between metals.
- **Entry:** Spread zscore extreme.
- **Exit:** Mean.
- **Indicators/params:** ratio zscore.
- **Regime/seasonality fit:** Range; diverges on supply news.
- **Source:** CME spread-trading metals.
- **Genome-mappable:** partial.

### H8. Pairs Stat-Arb (cointegrated metals)
- **Family:** Spread/stat-arb | **Timeframe:** 1h/daily
- **Core logic:** Trade residual of cointegrated metal pair to mean.
- **Entry:** Hedge-ratio residual zscore>±2.
- **Exit:** Residual to 0; SL ±3.
- **Indicators/params:** OLS hedge ratio, residual zscore.
- **Regime/seasonality fit:** Stable cointegration.
- **Source:** awesome-quant pairs; Chan stat-arb.
- **Genome-mappable:** partial (needs regression hedge ratio; residual zscore native).

---

## FAMILY I — USDINR-linked bullion

### I1. USDINR-Adjusted Gold Arbitrage
- **Family:** FX-linked | **Timeframe:** Intraday
- **Core logic:** MCX gold = COMEX gold × USDINR × factor; trade MCX dislocation from synthetic fair value.
- **Entry:** When MCX price diverges from (intl gold × USDINR) beyond band.
- **Exit:** Convergence.
- **Indicators/params:** intl gold, USDINR, conversion; zscore of basis.
- **Regime/seasonality fit:** Always-on microstructure.
- **Source:** Zerodha Varsity commodities (import-parity pricing).
- **Genome-mappable:** no (needs USDINR + intl price inputs).

### I2. USDINR Momentum → Bullion Bias
- **Family:** FX-linked | **Timeframe:** Daily
- **Core logic:** Weak INR raises rupee gold price; bias long MCX bullion when USDINR rising.
- **Entry:** Long GOLD when USDINR mom>0 and gold trend up.
- **Exit:** USDINR mom flips; ATR SL.
- **Indicators/params:** USDINR mom, EMA, ATR.
- **Regime/seasonality fit:** INR-depreciation regimes.
- **Source:** import-parity logic; Varsity.
- **Genome-mappable:** partial (USDINR series external; ema/mom native).

### I3. Dollar-Index (DXY) Inverse Gold
- **Family:** FX-linked | **Timeframe:** Daily
- **Core logic:** DXY strength typically pressures USD gold.
- **Entry:** Short bias gold when DXY breaks out up; long when DXY down.
- **Exit:** DXY trend break.
- **Indicators/params:** DXY trend (ema), gold trend.
- **Regime/seasonality fit:** Macro USD cycles.
- **Source:** gold-DXY inverse correlation studies.
- **Genome-mappable:** partial (DXY external input).

### I4. INR Event (RBI/Budget) Bullion Volatility
- **Family:** FX-linked event | **Timeframe:** Intraday
- **Core logic:** INR/import-duty events move rupee bullion sharply.
- **Entry:** Break of pre-event range on RBI policy / Budget customs-duty news.
- **Exit:** ATR trail.
- **Indicators/params:** event calendar, ATR.
- **Regime/seasonality fit:** India policy days.
- **Source:** Varsity; MCX bullion event behavior.
- **Genome-mappable:** no (event + FX inputs).

---

## FAMILY J — Crack / spark spread & refined-product concepts

### J1. Crack-Spread Proxy Bias (crude vs products)
- **Family:** Crack spread | **Timeframe:** Daily
- **Core logic:** Refining margin (gasoline/heating oil − crude) signals crude demand; bias MCX crude with crack direction.
- **Entry:** Long crude when crack widening; short when collapsing.
- **Exit:** Crack trend break.
- **Indicators/params:** external crack series + crude trend.
- **Regime/seasonality fit:** Refinery-cycle driven.
- **Source:** CME crack spread; QuantStrategy.io inter-commodity.
- **Genome-mappable:** no (needs product prices not on MCX).

### J2. Spark-Spread Concept Gas Bias
- **Family:** Spark spread | **Timeframe:** Daily
- **Core logic:** Power-generation margin (power − gas) proxies gas demand.
- **Entry:** Bias gas with spark-spread strength.
- **Exit:** Spread reversal.
- **Indicators/params:** external power/gas spread.
- **Regime/seasonality fit:** Summer cooling demand.
- **Source:** spark-spread energy literature.
- **Genome-mappable:** no (external power prices).

### J3. Seasonal Crack Margin Long (spring refinery turnaround)
- **Family:** Crack spread seasonal | **Timeframe:** Daily, Feb–May
- **Core logic:** Refinery maintenance tightens products, widens crack; crude bias.
- **Entry:** Spring window with crack confirmation.
- **Exit:** Summer.
- **Indicators/params:** calendar + crack proxy.
- **Regime/seasonality fit:** Refinery turnaround season.
- **Source:** crack-spread seasonality.
- **Genome-mappable:** no.

---

## FAMILY K — COT-style positioning

### K1. COT Commercial-Extreme Contrarian
- **Family:** Positioning | **Timeframe:** Weekly
- **Core logic:** Commercials (smart money) net-position extremes precede reversals.
- **Entry:** Long when commercials at multi-yr net-long extreme.
- **Exit:** Position normalizes; trend SL.
- **Indicators/params:** CFTC COT index (external), zscore.
- **Regime/seasonality fit:** Reversal timing crude/gold/copper.
- **Source:** CFTC COT; COTInsight; Briese "The Commitments of Traders Bible".
- **Genome-mappable:** no (external COT data).

### K2. COT Managed-Money Trend Confirmation
- **Family:** Positioning | **Timeframe:** Weekly
- **Core logic:** Rising managed-money longs confirm trend continuation.
- **Entry:** Trend long when MM longs increasing.
- **Exit:** MM longs roll over.
- **Indicators/params:** COT MM series + price trend.
- **Regime/seasonality fit:** Trend confirmation.
- **Source:** CFTC COT; COTInsight.
- **Genome-mappable:** no (external).

### K3. COT + Term-Structure Combo (basis)
- **Family:** Positioning/curve | **Timeframe:** Weekly
- **Core logic:** Combine COT extreme, inventory direction, and backwardation narrowing/deepening.
- **Entry:** Aligned bullish (deep backwardation + commercial long + draws).
- **Exit:** Signal divergence.
- **Indicators/params:** COT, curve slope, inventory (all external).
- **Regime/seasonality fit:** Confluence positional.
- **Source:** QuantifiedStrategies contango/backwardation + COT.
- **Genome-mappable:** no.

### K4. Open-Interest + Price Confirmation (proxy)
- **Family:** Positioning | **Timeframe:** Daily
- **Core logic:** Rising price + rising OI = strong trend; rising price + falling OI = weak.
- **Entry:** Long when price up and OI up.
- **Exit:** OI diverges from price.
- **Indicators/params:** OI (MCX provides), price trend.
- **Regime/seasonality fit:** Trend strength confirmation.
- **Source:** Zerodha Varsity OI; futures OI analysis.
- **Genome-mappable:** partial (OI available on MCX but not in genome; add as feature → then threshold).

---

## FAMILY L — VWAP / pivot intraday

### L1. VWAP Trend-Follow (above/below)
- **Family:** VWAP intraday | **Timeframe:** 5m
- **Core logic:** Trade long only above VWAP, short below.
- **Entry:** Pullback to VWAP with-trend bounce.
- **Exit:** VWAP cross; ATR SL.
- **Indicators/params:** VWAP, ATR.
- **Regime/seasonality fit:** Trend day crude/copper.
- **Source:** Upstox VWAP; StockGro.
- **Genome-mappable:** partial (VWAP needs volume×price; sma proxy).

### L2. VWAP Anchored Breakout (from session open)
- **Family:** VWAP intraday | **Timeframe:** 5m
- **Core logic:** Anchored VWAP from open acts as decision line.
- **Entry:** Break and hold above AVWAP.
- **Exit:** Loss of AVWAP.
- **Indicators/params:** anchored VWAP.
- **Regime/seasonality fit:** Trend day.
- **Source:** anchored VWAP technique.
- **Genome-mappable:** partial.

### L3. Floor-Pivot (R1/S1) Reversal
- **Family:** Pivot intraday | **Timeframe:** 5m/15m
- **Core logic:** Classic pivots define intraday S/R; fade into pivot, target next.
- **Entry:** Long at S1 with reversal candle; short at R1.
- **Exit:** Target pivot/PP; SL beyond S2/R2.
- **Indicators/params:** Pivot = (H+L+C)/3 prior day.
- **Regime/seasonality fit:** Range days metals.
- **Source:** classic floor pivots; MCX desk standard.
- **Genome-mappable:** partial (pivots from prior-day OHLC; computable but not native).

### L4. Pivot Breakout Trend
- **Family:** Pivot intraday | **Timeframe:** 5m
- **Core logic:** Break above R1 → momentum to R2/R3.
- **Entry:** Close above R1.
- **Exit:** R2/R3 targets; SL pivot.
- **Indicators/params:** pivot levels.
- **Regime/seasonality fit:** Trend day crude.
- **Source:** pivot breakout method.
- **Genome-mappable:** partial.

### L5. Camarilla Pivot Mean-Reversion
- **Family:** Pivot intraday | **Timeframe:** 5m
- **Core logic:** Camarilla H3/L3 reversal zones for range scalps.
- **Entry:** Long at L3, short at H3.
- **Exit:** PP target; SL H4/L4.
- **Indicators/params:** Camarilla levels.
- **Regime/seasonality fit:** Range intraday.
- **Source:** Camarilla equation.
- **Genome-mappable:** partial.

### L6. VWAP-Pivot Confluence Scalp
- **Family:** VWAP+pivot | **Timeframe:** 1m/5m
- **Core logic:** Trade where VWAP and a pivot coincide (stronger level).
- **Entry:** Reversal at VWAP≈pivot confluence.
- **Exit:** Quick R-multiple; tight SL.
- **Indicators/params:** VWAP, pivots.
- **Regime/seasonality fit:** Liquid crude/gold.
- **Source:** confluence scalping.
- **Genome-mappable:** partial.

---

## FAMILY M — Gap strategies

### M1. Gap-and-Go Continuation (bullion open)
- **Family:** Gap | **Timeframe:** 5m at open
- **Core logic:** Large open gap (vs intl overnight) with momentum continues.
- **Entry:** Long if gap up holds first-5m high.
- **Exit:** ATR trail; SL gap fill.
- **Indicators/params:** gap size, ATR, rvol.
- **Regime/seasonality fit:** Strong overnight COMEX move into MCX open.
- **Source:** gap-and-go futures; gap literature.
- **Genome-mappable:** yes (open-vs-prevclose ret + rvol + threshold).

### M2. Gap Fill Fade
- **Family:** Gap | **Timeframe:** 5m
- **Core logic:** Moderate gaps fill back to prior close.
- **Entry:** Fade gap toward prev close when it stalls.
- **Exit:** Prev close target; SL beyond gap extreme.
- **Indicators/params:** gap size vs ATR.
- **Regime/seasonality fit:** Quiet overnight, range day.
- **Source:** gap-fill statistics.
- **Genome-mappable:** yes.

### M3. Gap-Zone Breakout (post-weekend crude)
- **Family:** Gap | **Timeframe:** 5m Monday
- **Core logic:** Weekend news creates Monday gaps; trade the resolution.
- **Entry:** Break of first-hour range in gap direction.
- **Exit:** ATR trail.
- **Indicators/params:** gap, range, ATR.
- **Regime/seasonality fit:** Crude weekend geopolitical.
- **Source:** weekend-gap practice.
- **Genome-mappable:** yes.

### M4. Island Reversal Gap
- **Family:** Gap reversal | **Timeframe:** Daily
- **Core logic:** Gap up then gap down isolating an island = reversal.
- **Entry:** Short on confirming gap down after exhaustion gap up.
- **Exit:** Prior base; SL above island.
- **Indicators/params:** gap pattern.
- **Regime/seasonality fit:** Exhausted trends.
- **Source:** island-reversal pattern.
- **Genome-mappable:** partial (multi-bar gap pattern).

---

## FAMILY N — Time-of-day / session-overlap

### N1. London-Open Metals Momentum (12:30–13:30 IST)
- **Family:** Time-of-day | **Timeframe:** 5m
- **Core logic:** LME/London open injects volume into base metals/bullion.
- **Entry:** Trade breakout at ~12:30–13:30 IST in trend direction.
- **Exit:** Session-end / ATR trail.
- **Indicators/params:** time window, range, rvol.
- **Regime/seasonality fit:** Copper/zinc/gold London hours.
- **Source:** session-overlap intraday practice.
- **Genome-mappable:** partial (time-of-day filter + price native).

### N2. US-Open / Data-Window Crude Burst (18:00–20:00 IST)
- **Family:** Time-of-day | **Timeframe:** 5m
- **Core logic:** US session + macro data window is crude's most active period.
- **Entry:** Momentum/breakout entries only in this window.
- **Exit:** Before MCX close; ATR trail.
- **Indicators/params:** time window, ATR, rvol.
- **Regime/seasonality fit:** Crude/natgas US hours.
- **Source:** Upstox/StockGro intraday timing.
- **Genome-mappable:** partial (time filter).

### N3. Lunch-Lull Range Fade (14:00–16:00 IST)
- **Family:** Time-of-day | **Timeframe:** 5m
- **Core logic:** Low-volume midday → mean-revert within range.
- **Entry:** Fade range extremes during lull.
- **Exit:** Range mid; tight SL.
- **Indicators/params:** time window, range_pct.
- **Regime/seasonality fit:** Quiet midday metals.
- **Source:** intraday volume-profile practice.
- **Genome-mappable:** partial.

### N4. Pre-Close Momentum (22:30–23:25 IST)
- **Family:** Time-of-day | **Timeframe:** 5m
- **Core logic:** End-of-session positioning creates late directional push.
- **Entry:** With-trend entry in last hour on rvol.
- **Exit:** Flat at close.
- **Indicators/params:** time, mom, rvol.
- **Regime/seasonality fit:** Crude/metals close.
- **Source:** end-of-day momentum.
- **Genome-mappable:** partial.

### N5. First-Hour Trend-Day Identification
- **Family:** Time-of-day | **Timeframe:** 5m
- **Core logic:** Strong directional first hour predicts trend day; stay with it.
- **Entry:** If first-hour range one-directional + rvol high, add on pullbacks.
- **Exit:** Trend break / close.
- **Indicators/params:** first-hour range, rvol.
- **Regime/seasonality fit:** Crude trend days.
- **Source:** market-profile trend-day theory.
- **Genome-mappable:** partial.

---

## FAMILY O — Volatility breakout around data releases

### O1. NFP/CPI Gold Volatility Breakout
- **Family:** Data-event vol | **Timeframe:** 1m/5m
- **Core logic:** US NFP/CPI move gold sharply; trade the break.
- **Entry:** Break of pre-release range after US data drop.
- **Exit:** ATR trail; scalp.
- **Indicators/params:** event calendar, range, ATR.
- **Regime/seasonality fit:** Gold/silver US macro days.
- **Source:** macro-event vol trading.
- **Genome-mappable:** partial (event input + price native).

### O2. FOMC Gold/Crude Straddle Breakout
- **Family:** Data-event vol | **Timeframe:** 5m
- **Core logic:** Fed decisions whip metals/energy; capture directional resolution.
- **Entry:** Buy-stop/sell-stop bracketing pre-FOMC range.
- **Exit:** Opposite stop / ATR trail.
- **Indicators/params:** FOMC calendar, range, ATR.
- **Regime/seasonality fit:** Fed days.
- **Source:** FOMC volatility studies.
- **Genome-mappable:** partial (event).

### O3. China PMI Base-Metal Reaction
- **Family:** Data-event vol | **Timeframe:** 5m
- **Core logic:** China data drives copper/zinc/aluminium.
- **Entry:** Break of pre-data range in reaction direction.
- **Exit:** ATR trail.
- **Indicators/params:** China data calendar, ATR.
- **Regime/seasonality fit:** Base-metal macro days.
- **Source:** base-metal China-data sensitivity.
- **Genome-mappable:** partial (event).

### O4. Generic ATR-Spike Post-Data Breakout
- **Family:** Data-event vol | **Timeframe:** 5m
- **Core logic:** Detect any data-driven atr_pct spike and ride direction (no need to know event).
- **Entry:** When atr_pct jumps > percentile + close breaks range.
- **Exit:** ATR normalizes.
- **Indicators/params:** atr_pct, range_pct, rvol.
- **Regime/seasonality fit:** Any high-vol catalyst.
- **Source:** volatility-breakout literature; arxiv GARCH energy vol.
- **Genome-mappable:** yes (atr_pct + range_pct + rvol, no event input needed).

---

## FAMILY P — Carry / contango-backwardation (term structure)

### P1. Backwardation Long / Contango Short Carry
- **Family:** Carry/term-structure | **Timeframe:** Monthly roll
- **Core logic:** Long backwardated (positive roll yield), short contangoed commodities.
- **Entry:** Long when near>far (backwardation); short when far>near.
- **Exit:** Curve slope flips.
- **Indicators/params:** near−far futures basis.
- **Regime/seasonality fit:** Tight-supply (crude/copper) vs glut.
- **Source:** QuantifiedStrategies contango/backwardation; QuantPedia carry.
- **Genome-mappable:** no (needs two-contract curve data).

### P2. Roll-Yield Harvest (calendar spread)
- **Family:** Carry/calendar | **Timeframe:** Monthly
- **Core logic:** Capture positive roll in backwardation via near/far calendar spread.
- **Entry:** Long near / short far when backwardated.
- **Exit:** Before expiry / slope flip.
- **Indicators/params:** calendar spread.
- **Regime/seasonality fit:** Backwardated energy.
- **Source:** roll-yield literature; CME calendar spreads.
- **Genome-mappable:** no (two-contract).

### P3. Term-Structure Slope Momentum
- **Family:** Carry | **Timeframe:** Weekly
- **Core logic:** Steepening backwardation = accelerating tightness, bullish.
- **Entry:** Long when backwardation deepening; exit when narrowing.
- **Exit:** Slope reversal.
- **Indicators/params:** basis slope change.
- **Regime/seasonality fit:** Supply-tightness regimes.
- **Source:** QuantifiedStrategies; Wiley comovement study.
- **Genome-mappable:** no (curve data).

### P4. Seasonal Calendar-Spread (natgas winter/summer)
- **Family:** Carry/calendar seasonal | **Timeframe:** Positional
- **Core logic:** Winter-vs-summer gas spread (e.g. long Jan / short Apr) on storage seasonality.
- **Entry:** Establish seasonal calendar spread in shoulder season.
- **Exit:** Into winter.
- **Indicators/params:** calendar spread + seasonal table.
- **Regime/seasonality fit:** NatGas storage cycle.
- **Source:** natgas seasonal spread practice; CME.
- **Genome-mappable:** no (two-contract + calendar).

### P5. Carry + Momentum Combo (commodity factor)
- **Family:** Carry+momentum | **Timeframe:** Monthly
- **Core logic:** Combine roll-carry rank with TSMOM for robust commodity factor.
- **Entry:** Long high-carry + positive-momentum; short opposite.
- **Exit:** Monthly rebalance.
- **Indicators/params:** basis + ret(252).
- **Regime/seasonality fit:** Cross-commodity factor.
- **Source:** Koijen et al "Carry"; QuantPedia.
- **Genome-mappable:** no (carry leg external; momentum leg native).

---

## FAMILY Q — Multi-factor / regime / composite

### Q1. Trend + Momentum + Vol Filter Composite
- **Family:** Composite | **Timeframe:** Daily
- **Core logic:** Require EMA-trend, positive mom, and atr_pct in tradable band.
- **Entry:** ema-stack up AND mom>0 AND atr_pct in mid-range.
- **Exit:** Any condition fails; ATR trail.
- **Indicators/params:** ema, mom, atr_pct.
- **Regime/seasonality fit:** Robust trend across commodities.
- **Source:** multi-factor TA practice.
- **Genome-mappable:** yes (all native).

### Q2. Regime-Switch Trend/Reversion (vol-gated)
- **Family:** Regime | **Timeframe:** Daily
- **Core logic:** High atr_pct → breakout; low → mean-reversion (zscore).
- **Entry:** Per regime module.
- **Exit:** Per module.
- **Indicators/params:** atr_pct gate, zscore, range_pct.
- **Regime/seasonality fit:** Adaptive all commodities.
- **Source:** regime-switching literature.
- **Genome-mappable:** yes.

### Q3. RVOL-Confirmed Breakout Composite
- **Family:** Composite | **Timeframe:** 15m
- **Core logic:** Breakout only valid with relative-volume expansion.
- **Entry:** range_pct breakout AND rvol>1.5.
- **Exit:** rvol fade / ATR trail.
- **Indicators/params:** range_pct, rvol, atr.
- **Regime/seasonality fit:** Genuine breakouts.
- **Source:** volume-confirmed breakout.
- **Genome-mappable:** yes.

### Q4. Dual-Timeframe Trend Alignment
- **Family:** Composite | **Timeframe:** 15m entry / 1h trend
- **Core logic:** Trade 15m signals only with 1h trend.
- **Entry:** 1h ema up AND 15m pullback-buy.
- **Exit:** 15m signal / 1h trend break.
- **Indicators/params:** ema both TFs.
- **Regime/seasonality fit:** Reduces counter-trend trades.
- **Source:** multi-timeframe practice.
- **Genome-mappable:** yes (ema on two TFs).

### Q5. Mean-Reversion-in-Uptrend (buy-the-dip)
- **Family:** Composite | **Timeframe:** Daily
- **Core logic:** Long-term up + short-term oversold = high-odds dip buy.
- **Entry:** close>SMA200 AND rsi(2)<10.
- **Exit:** close>SMA5; SL 2×ATR.
- **Indicators/params:** SMA200, RSI(2), SMA5, ATR.
- **Regime/seasonality fit:** Bullion bull markets.
- **Source:** Connors buy-the-dip.
- **Genome-mappable:** yes.

### Q6. Volatility-Targeted Trend Portfolio
- **Family:** Composite/risk | **Timeframe:** Daily
- **Core logic:** TSMOM across MCX commodities, each scaled to target vol.
- **Entry:** Long/short by ret(126) sign, weight = target_vol/atr_pct.
- **Exit:** Sign flip; rebalance.
- **Indicators/params:** ret, atr_pct.
- **Regime/seasonality fit:** Diversified trend.
- **Source:** AQR vol-targeting; QuantPedia.
- **Genome-mappable:** yes (ret + atr_pct).

### Q7. Breakout-Failure Reversal (false-break fade)
- **Family:** Composite reversal | **Timeframe:** 15m
- **Core logic:** Failed breakout (quick reclaim) signals reversal.
- **Entry:** Short when price breaks high then closes back inside range.
- **Exit:** Range opposite side; SL above failed high.
- **Indicators/params:** range_pct, rvol.
- **Regime/seasonality fit:** Range/trap conditions.
- **Source:** false-breakout / stop-run theory.
- **Genome-mappable:** yes.

### Q8. Stochastic Oversold/Overbought in Range
- **Family:** Mean-reversion | **Timeframe:** 15m/1h
- **Core logic:** Stochastic %K/%D extremes in non-trending market.
- **Entry:** Long when %K crosses up from <20; short from >80.
- **Exit:** Mid (50); SL ATR.
- **Indicators/params:** Stochastic(14,3,3).
- **Regime/seasonality fit:** Range metals.
- **Source:** Lane stochastics; Varsity.
- **Genome-mappable:** partial (stoch = position-in-range; range_pct proxy).

### Q9. Williams %R Reversion
- **Family:** Mean-reversion | **Timeframe:** 15m
- **Core logic:** %R<−80 oversold, >−20 overbought.
- **Entry:** Long %R exits <−80.
- **Exit:** %R>−50.
- **Indicators/params:** Williams %R(14).
- **Regime/seasonality fit:** Range.
- **Source:** Williams %R.
- **Genome-mappable:** partial (range-position proxy via range_pct).

### Q10. Parabolic SAR Trend Trail
- **Family:** Trend-following | **Timeframe:** 15m/daily
- **Core logic:** SAR dots flip to define trailing stop and direction.
- **Entry:** Long when SAR flips below price.
- **Exit:** SAR flip above; SAR as trail.
- **Indicators/params:** PSAR(0.02,0.2).
- **Regime/seasonality fit:** Trending; whipsaws in range.
- **Source:** Wilder Parabolic SAR; backtrader.
- **Genome-mappable:** partial (SAR recursive; atr-trail approximation).

### Q11. ATR-Normalized Momentum Rank
- **Family:** Composite | **Timeframe:** Daily
- **Core logic:** Rank commodities by ret/atr (risk-adjusted momentum).
- **Entry:** Long top risk-adjusted momentum names.
- **Exit:** Rotate; SL atr.
- **Indicators/params:** ret, atr_pct.
- **Regime/seasonality fit:** Cross-sectional.
- **Source:** risk-adjusted momentum literature.
- **Genome-mappable:** partial (cross-asset ranking; per-asset features native).

### Q12. Bollinger-Walk Trend Ride
- **Family:** Trend-following | **Timeframe:** 15m/daily
- **Core logic:** In strong trend price "walks the band"; stay long while riding upper band.
- **Entry:** Long when close repeatedly tags upper BB with rising sma.
- **Exit:** Close back below mid-band.
- **Indicators/params:** BB(20,2), sma.
- **Regime/seasonality fit:** Strong trends.
- **Source:** Bollinger band-walk.
- **Genome-mappable:** yes (zscore high persistence).

### Q13. Dual-MA + RSI Filter Swing
- **Family:** Composite | **Timeframe:** Daily
- **Core logic:** MA cross entry filtered by RSI not overbought.
- **Entry:** EMA20>EMA50 cross AND RSI<65.
- **Exit:** Opposite cross or RSI>75; ATR SL.
- **Indicators/params:** EMA(20/50), RSI(14), ATR.
- **Regime/seasonality fit:** Swing metals/bullion.
- **Source:** combined MA-RSI swing.
- **Genome-mappable:** yes.

### Q14. Range-Expansion Trend-Day Add
- **Family:** Composite | **Timeframe:** 5m
- **Core logic:** On wide-range expansion bar, pyramid with trend.
- **Entry:** range_pct expansion bar + rvol, add on pullbacks.
- **Exit:** Range contraction / close.
- **Indicators/params:** range_pct, rvol.
- **Regime/seasonality fit:** Crude trend days.
- **Source:** range-expansion (Crabel).
- **Genome-mappable:** yes.

### Q15. Mean-Reversion Pairs of Bullion (GOLD vs SILVER beta)
- **Family:** Composite spread | **Timeframe:** Daily
- **Core logic:** Beta-hedged gold/silver residual reversion (refinement of GSR).
- **Entry:** Residual zscore>±2.
- **Exit:** Residual to 0.
- **Indicators/params:** beta hedge, residual zscore.
- **Regime/seasonality fit:** Stable bullion correlation.
- **Source:** CME precious-metals spreads; stat-arb.
- **Genome-mappable:** partial (two-leg).

### Q16. Inside-Day NR4 Volatility Squeeze (Crabel)
- **Family:** Range breakout | **Timeframe:** Daily
- **Core logic:** Inside day + narrowest range 4 = strong expansion setup.
- **Entry:** Break of inside-NR4 bar.
- **Exit:** ATR target; opposite SL.
- **Indicators/params:** range_pct (4-bar min), inside-bar.
- **Regime/seasonality fit:** Pre-expansion any commodity.
- **Source:** Crabel "Short Term Price Patterns".
- **Genome-mappable:** yes.

### Q17. Trend-Filtered ORB (only with daily trend)
- **Family:** Composite intraday | **Timeframe:** 5m + daily filter
- **Core logic:** Take ORB only in direction of daily ema trend.
- **Entry:** ORB break aligned with daily EMA50 slope.
- **Exit:** ATR trail / close.
- **Indicators/params:** OR range, daily EMA(50).
- **Regime/seasonality fit:** Higher-odds ORB.
- **Source:** filtered-ORB practice.
- **Genome-mappable:** yes.

### Q18. Volatility-Compression-to-Expansion (squeeze + direction)
- **Family:** Composite | **Timeframe:** 1h
- **Core logic:** Detect atr_pct low (compression) then trade first expansion candle.
- **Entry:** atr_pct at N-period low → enter on range break.
- **Exit:** ATR normalizes; trail.
- **Indicators/params:** atr_pct, range_pct.
- **Regime/seasonality fit:** All commodities pre-move.
- **Source:** vol compression/expansion cycle.
- **Genome-mappable:** yes.

### Q19. Momentum Ignition + VWAP Reclaim Scalp
- **Family:** Composite intraday | **Timeframe:** 1m/5m
- **Core logic:** After sharp move, trade reclaim of VWAP in move direction.
- **Entry:** Reclaim VWAP after impulse + rvol.
- **Exit:** Quick R; tight SL.
- **Indicators/params:** VWAP, rvol, mom.
- **Regime/seasonality fit:** Liquid crude/gold scalps.
- **Source:** momentum-ignition scalping.
- **Genome-mappable:** partial (VWAP).

### Q20. Cross-Sectional Reversal (short-term loser bounce)
- **Family:** Mean-reversion cross-sectional | **Timeframe:** Weekly
- **Core logic:** Worst 1-week MCX commodity bounces next week.
- **Entry:** Long worst ret(5) of the commodity set.
- **Exit:** 1-week hold.
- **Indicators/params:** ret(5) rank.
- **Regime/seasonality fit:** Range/choppy markets.
- **Source:** short-term reversal literature.
- **Genome-mappable:** partial (cross-asset ranking; ret native).
