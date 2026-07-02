# NSE Intraday Cash/Equity — Proven Strategy Templates

**Segment:** Indian equities, intraday/MIS, square-off same day (NSE CASH).
**What this is:** A curated, deduped library of distinct, publicly-documented intraday strategy templates — each with entry/exit/indicator params, regime fit, source citation, and a flag for whether it is expressible in the T8 strategy genome (TA-Lib features: `ret, sma_fast/slow, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol` + threshold/crossover entry-exit operators). **Genome-mappable:** `yes` = expressible with current genome features; `partial` = needs one extra TA-Lib indicator we can add (VWAP, BB, MACD, Supertrend, Donchian, pivots/CPR, ADX, Stoch, CCI, %R, OBV, SAR, Hull); `no` = needs a second instrument / cross-section / news / order-flow (discretionary).

> Conventions: SL = stop-loss, T = target, TSL = trailing stop. "1R" = initial risk (entry→SL distance). TF = entry timeframe. All positions force-squared-off by ~15:15 IST regardless of rule. Default RVOL = current vol / 20-day avg-at-time-of-day; ATR default 14 unless noted.

---

## 1. Opening-Range Breakout (ORB) family

| # | Name | Core logic | Entry | Exit (SL/T/TSL) | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|-----------------|---------------------|----|--------|--------|--------|
|1|ORB-5|Break of first 5-min candle range|Long > 5m-high / Short < 5m-low after 09:20|SL = other side of OR; T = 1.5–2R; TSL prior bar|5m OR high/low|1m/5m|Trending/volatile|partial|[StockEzee ORB](https://www.stockezee.com/stock-screener/technical/price-action/opening-range-breakout), [BuildAlpha](https://www.buildalpha.com/opening-range-breakout/)|
|2|ORB-15|Break of 09:15–09:30 range|Same as ORB but 15m range|SL=opp side; T=1.5R; TSL|15m OR|5m|Trending/volatile|partial|[IntradayScreener ORB](https://intradayscreener.com/opening-range-breakout)|
|3|ORB-30|Break of first 30-min range (cleaner, fewer fakes)|Break of 30m hi/lo|SL=mid-OR; T=R2 pivot|30m OR|5m/15m|Trending|partial|[StockEzee ORB](https://www.stockezee.com/stock-screener/technical/price-action/opening-range-breakout)|
|4|ORB-60|First-hour range break (high conviction)|Break after 10:15|SL=opp side; T=2R; TSL EMA20|60m OR|15m|Trending|partial|[StockEzee ORB](https://www.stockezee.com/stock-screener/technical/price-action/opening-range-breakout)|
|5|ORB+RVOL|ORB confirmed by volume surge|ORB break AND RVOL≥1.5×|SL=opp side; T=2R|OR + RVOL 1.2–1.5|5m|Volatile|partial|[StockEzee ORB](https://www.stockezee.com/stock-screener/technical/price-action/opening-range-breakout)|
|6|ORB+VWAP|Break must hold same side of VWAP|Long > ORhi AND price>VWAP|SL=VWAP; T=2R; TSL VWAP|OR + VWAP|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/), [Tradewink](https://tradewink.com/learn/vwap-trading-strategy)|
|7|ORB-fade|Failed breakout reversal back into range|Fade when break fails & re-enters OR|SL=breakout extreme; T=opp OR side|OR high/low|5m|Ranging|partial|[ForexTester ORB](https://forextester.com/blog/opening-range-breakout-trading-strategies/)|
|8|ORB-ATR|Only trade if OR width > k·ATR (volatility-validated)|ORB break with OR>0.5·ATR(daily)|SL=opp; T=1.5R|OR + ATR14|5m|Volatile|partial|[SSRN block-eval](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5198458)|
|9|ORB-retest|Enter on retest of broken OR level|Break, then pullback to OR line holds|SL=below retest; T=2R|OR high/low|5m|Trending|partial|[ForexTester ORB](https://forextester.com/blog/opening-range-breakout-trading-strategies/)|
|10|ORB+ADX|Break only when ADX>20 (trend present)|ORB break AND ADX>20|SL=opp; T=2R; TSL|OR + ADX14|5m|Trending|partial|[SSRN block-eval](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5198458)|
|11|ORB-1m scalp|1-min opening candle break, quick scalp|Break 1m candle hi/lo|SL=opp; T=0.5–1R fast|1m OR|1m|Volatile|partial|[ForexTester ORB](https://forextester.com/blog/opening-range-breakout-trading-strategies/)|
|12|ORB-NR7 precond|Break of OR only after a narrow-range-7 prior day (coiled)|ORB break after NR7 day|SL=opp; T=2R|OR + range_pct rank|5m|Volatile (post-squeeze)|yes|[Crabel NR7] via [BuildAlpha](https://www.buildalpha.com/opening-range-breakout/)|
|13|ORB-PRB|Break of prior-day range + opening range together|Break OR & previous-day high/low|SL=opp; T=2R|OR + PDH/PDL|5m|Trending|yes|[StockEzee ORB](https://www.stockezee.com/stock-screener/technical/price-action/opening-range-breakout)|
|14|ORB body-strength|Break candle must close with strong body (≥70% range)|ORB break + strong body candle|SL=opp; T=2R|OR + candle range_pct|5m|Volatile|yes|[IntradayScreener ORB](https://intradayscreener.com/opening-range-breakout)|
|15|ORB-multi N-day hold proxy|ORB with N=2/3/5 bar momentum confirm before commit|Break sustained N bars|SL=opp; T=2R; TSL|OR + mom(N)|5m|Trending|yes|[SSRN block-eval](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5198458)|

## 2. Gap-up / Gap-down — Fade & Go family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|16|Gap-up-go|Continuation after bullish gap|Long on break of opening 5m high after gap-up|SL=opening low; T=PDC+gap, TSL|gap=open/PDC−1, OR|5m|Trending|partial|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|17|Gap-down-go|Continuation after bearish gap|Short on break of opening 5m low|SL=opening high; T=1.5R|gap, OR|5m|Trending|partial|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|18|Gap-up-fade|Small gap-up reverses to fill|Short when price fails opening high & turns|SL=HOD; T=PDC (gap fill)|gap<0.5·ATR|5m|Ranging|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|19|Gap-down-fade|Small gap-down bounces to fill|Long when opening low holds & turns up|SL=LOD; T=PDC|gap<0.5·ATR|5m|Ranging|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|20|Gap-fill|Trade toward prior close (gap closes ~70% of time)|Enter toward PDC after first 15m|SL=gap extreme; T=PDC|gap, PDC|5m|Ranging (high VIX)|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|21|Gap-and-go OC break|Break of opening candle high in gap direction|Long>opening-candle-high|SL=OC low; T=2R; TSL|opening candle|1m/5m|Volatile|partial|[Humbled Trader VWAP/gap](https://www.humbledtrader.com/blog/vwap-strategy-secrets-boosting-your-trading-skills-to-the-next-level/)|
|22|Breakaway gap|Large gap (>ATR) = breakaway, trade with it|Continuation, gap>1·ATR(daily)|SL=opening range; T=trail|gap, ATR14|5m|Trending|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|23|Common gap fade|Tiny gap (<0.3·ATR), no catalyst → fade to fill|Fade toward PDC|SL=gap extreme; T=PDC|gap, ATR|5m|Ranging|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|
|24|Gap+RVOL go|Gap continuation only if RVOL high (catalyst)|Gap-go AND RVOL≥2|SL=OR; T=2R|gap + RVOL|5m|Volatile|partial|[GWC RVOL](https://www.gwcindia.in/blog/how-to-use-relative-volume-rvol-for-better-entry-timing-in-indian-stocks/)|
|25|Gap+VWAP reclaim|Gap-up dips below VWAP then reclaims = go|Long on VWAP reclaim post-gap|SL=reclaim low; T=2R; TSL VWAP|gap + VWAP|5m|Trending|partial|[Snappchart VWAP momentum](https://www.snappchart.app/blog/strategy-playbooks/vwap-momentum-trading-strategy)|
|26|Island reversal|Gap in then opposite gap out = reversal|Reverse against prior gap|SL=island extreme; T=2R|gap pattern|5m/15m|Volatile|no|[Dow Theory pt2](https://zerodha.com/varsity/chapter/dow-theory-part-2/)|
|27|Gap to PDH/PDL|Gap toward prior-day extreme → fade at level|Fade at PDH/PDL touch|SL=beyond level; T=PDC|gap + PDH/PDL|5m|Ranging|yes|[JournalPlus Gap](https://journalplus.co/strategies/opening-gap-strategy/)|

## 3. VWAP family (trend + reversion)

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|28|VWAP-trend|Trade only with VWAP slope/side|Long while price>VWAP & rising|SL=VWAP; T=trail; TSL VWAP|VWAP|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|29|VWAP-reversion|Fade extreme distance from VWAP back to it|Short when far above VWAP & stalling|SL=extreme; T=VWAP|VWAP + dist|5m|Ranging|partial|[Tradewink VWAP](https://tradewink.com/learn/vwap-trading-strategy)|
|30|VWAP-bounce|Pullback to VWAP in uptrend|Long at VWAP touch in uptrend|SL=below VWAP; T=HOD; TSL|VWAP|5m|Trending|partial|[Humbled VWAP](https://www.humbledtrader.com/blog/vwap-strategy-secrets-boosting-your-trading-skills-to-the-next-level/)|
|31|VWAP momentum reclaim|Fade below VWAP, consolidate, reclaim on vol spike|Long on reclaim + RVOL|SL=reclaim low; T=2R|VWAP + RVOL|5m|Trending|partial|[Snappchart VWAP](https://www.snappchart.app/blog/strategy-playbooks/vwap-momentum-trading-strategy)|
|32|VWAP-breakout|First decisive cross of VWAP with volume|Long on VWAP cross + vol|SL=VWAP; T=2R|VWAP + vol|5m|Trending|partial|[Tradewink VWAP](https://tradewink.com/learn/vwap-trading-strategy)|
|33|VWAP-band reversion|Fade ±1–2σ VWAP bands|Short at +2σ band, long at −2σ|SL=outside band; T=VWAP|VWAP ±2σ|5m|Ranging|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|34|VWAP-band breakout|Break of +2σ VWAP band = strong trend|Long on +2σ break + vol|SL=VWAP; T=trail|VWAP ±2σ|5m|Volatile|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|35|Anchored VWAP (open)|Use AVWAP anchored at day open as dynamic S/R|Trade bounces/rejections off AVWAP|SL=opp; T=2R|AVWAP@open|5m|Trending/ranging|partial|[Snappchart VWAP](https://www.snappchart.app/blog/strategy-playbooks/vwap-trading-strategy)|
|36|VWAP+RSI confluence|VWAP side + RSI confirm|Long: price>VWAP & RSI>55|SL=VWAP; T=2R|VWAP + RSI14|5m|Trending|partial|[FxPro RSI](https://www.fxpro.com/help-section/education/beginners/articles/utilizing-the-relative-strength-index-indicator)|
|37|VWAP-rejection short|Price tags VWAP from below, rejects|Short on VWAP rejection in downtrend|SL=above VWAP; T=LOD|VWAP|5m|Trending (down)|partial|[Tradewink VWAP](https://tradewink.com/learn/vwap-trading-strategy)|
|38|VWAP-first-cross|First VWAP cross of day sets bias|Trade direction of first cross|SL=opp; T=2R|VWAP|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|39|VWAP z-score|Z-score of (price−VWAP) reversion|Short z>+2, long z<−2|SL=z±3; T=z→0|VWAP + zscore|5m|Ranging|partial|[Forextester VWAP](https://forextester.com/blog/vwap/)|

## 4. Momentum / Relative-Strength family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|40|Intraday momentum|N-bar return positive & accelerating|Long if ret(N)>thr|SL=1R ATR; T=2R; TSL|ret, mom(10)|5m|Trending|yes|[Medium momentum 2026](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|41|ROC breakout|Rate-of-change crosses threshold|Long ROC(12)>0 & rising|SL=ATR; T=trail|ROC/mom|5m|Trending|yes|[Medium momentum](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|42|RS vs NIFTY|Stock outperforming index intraday|Long when stock ret > NIFTY ret|SL=ATR; T=2R|ret(stock) vs ret(NIFTY)|5m|Trending|no|[Medium momentum](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|43|RS vs sector|Stock outperforms its sector index|Long strongest-RS stock in leading sector|SL=ATR; T=2R|sector index ret|5m|Trending|no|[Medium momentum](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|44|Momentum+volume|Price momentum with volume confirm|Long ret>thr & RVOL>1.5|SL=ATR; T=2R; TSL|mom + RVOL|5m|Volatile|yes|[GWC RVOL](https://www.gwcindia.in/blog/how-to-use-relative-volume-rvol-for-better-entry-timing-in-indian-stocks/)|
|45|MACD momentum|MACD line>signal & >0|Long on MACD bull cross above 0|SL=ATR; T=trail|MACD 12/26/9|5m/15m|Trending|partial|[freqtrade sample](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/templates/sample_strategy.py)|
|46|RSI momentum|RSI>60 = momentum long (not reversion)|Long RSI crosses up 60|SL=ATR; T=trail; exit RSI<50|RSI 9/14|5m|Trending|yes|[TradingSim RSI](https://www.tradingsim.com/blog/relative-strength-index-rsi)|
|47|Stochastic momentum|%K>%D in upper zone|Long on stoch cross in trend|SL=ATR; T=2R|Stoch 14/3/3|5m|Trending|partial|[TradingView RSI/Stoch](https://www.tradingview.com/scripts/relativestrengthindex/)|
|48|Williams %R momentum|%R rising out of −50|Long %R crosses −50 up|SL=ATR; T=2R|Williams %R 14|5m|Trending|partial|[TradingSim RSI](https://www.tradingsim.com/blog/relative-strength-index-rsi)|
|49|CCI breakout|CCI crosses +100 = momentum|Long CCI>+100|SL=ATR; T=trail; exit CCI<0|CCI 20|5m|Trending|partial|[pandas-ta CCI](https://github.com/twopirllc/pandas-ta)|
|50|TSI momentum|True Strength Index zero/signal cross|Long TSI>signal & >0|SL=ATR; T=trail|TSI 25/13|15m|Trending|partial|[pandas-ta TSI](https://github.com/twopirllc/pandas-ta)|
|51|Awesome Osc|AO zero-line / saucer cross|Long AO crosses>0|SL=ATR; T=2R|AO 5/34|5m|Trending|partial|[pandas-ta AO](https://github.com/twopirllc/pandas-ta)|

## 5. Breakout (Donchian / range / volatility) family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|52|Donchian-20|Break of N-bar highest/lowest|Long > Donchian upper(20)|SL=mid/lower; T=trail lower band|Donchian 20|5m/15m|Trending|partial|[TradingView Donchian](https://www.tradingview.com/scripts/donchianchannels/), [millerrh](https://www.tradingview.com/script/hyYvFjux-Donchian-Breakout-Strategy/)|
|53|Donchian squeeze|Narrow channel precedes breakout|Long on break after channel contraction|SL=opp band; T=trail|Donchian 10–20 width|5m|Volatile (post-squeeze)|partial|[LuxAlgo Donchian](https://www.luxalgo.com/blog/donchian-channels-breakout-and-trend-following-strategy/)|
|54|PDH/PDL break|Break of previous-day high/low|Long>PDH|SL=PDC; T=2R; TSL|PDH/PDL|5m|Trending|yes|[Dow Theory pt2](https://zerodha.com/varsity/chapter/dow-theory-part-2/)|
|55|Range expansion|Today's range exceeds avg range → trend day|Trade direction when range_pct > avg|SL=ATR; T=trail|range_pct, ATR|5m|Volatile|yes|[Crabel] via [BuildAlpha](https://www.buildalpha.com/opening-range-breakout/)|
|56|NR7 breakout|Break after narrowest-range-7 bar|Long>NR7 high|SL=NR7 low; T=2R|range_pct rank(7)|5m/15m|Volatile|yes|[BuildAlpha](https://www.buildalpha.com/opening-range-breakout/)|
|57|Inside-bar break|Break of inside-bar consolidation|Long>inside-bar high|SL=mother-bar low; T=2R|bar range compare|5m/15m|Volatile|yes|[Dow Theory pt2](https://zerodha.com/varsity/chapter/dow-theory-part-2/)|
|58|Keltner breakout|Break of ATR channel around EMA|Long>EMA20+2·ATR|SL=EMA; T=trail|Keltner EMA20/ATR×2|5m|Trending|partial|[LuxAlgo Donchian](https://www.luxalgo.com/blog/donchian-channels-breakout-and-trend-following-strategy/)|
|59|BB squeeze breakout|Bollinger bandwidth contracts then expands|Long on band expansion break|SL=mid-band; T=trail|BB 20/2 bandwidth|5m|Volatile|partial|[Kite Metric MR](https://kitemetric.com/blogs/freqtrade-mean-reversion-strategy-a-comprehensive-guide)|
|60|VCP intraday|Volatility-contraction pattern then break|Long on break of tightest contraction|SL=last low; T=2R|ATR_pct contraction|5m/15m|Volatile|yes|[Minervini VCP] via [BuildAlpha](https://www.buildalpha.com/opening-range-breakout/)|
|61|HOD/LOD break|Break of intraday high/low of day|Long on new HOD with vol|SL=last swing; T=trail|HOD/LOD, RVOL|5m|Trending|yes|[TradingSim RVOL](https://www.tradingsim.com/blog/relative-volume-rvol)|
|62|Pivot R1/S1 break|Break of classic pivot R1 (or S1)|Long>R1|SL=PP; T=R2/R3|Pivot PP/R1/R2|5m|Trending|partial|[Varsity CPR](https://zerodha.com/varsity/chapter/the-central-pivot-range/)|
|63|New-HOD momentum|Stock making fresh highs all day (trend day)|Add/hold on each new HOD|SL=VWAP; T=trail close|HOD, VWAP|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|

## 6. Mean-reversion (RSI / Bollinger / z-score) family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|64|RSI oversold bounce|Buy oversold turn-up|Long RSI<30 & turns up|SL=below swing; T=RSI 50|RSI 14|5m|Ranging|yes|[StockGro RSI](https://www.stockgro.club/blogs/intraday-trading/rsi-strategy-for-intraday-trading/)|
|65|RSI overbought short|Short overbought turn-down|Short RSI>70 & turns|SL=above swing; T=RSI 50|RSI 14|5m|Ranging|yes|[StockGro RSI](https://www.stockgro.club/blogs/intraday-trading/rsi-strategy-for-intraday-trading/)|
|66|RSI(2) extreme|Connors RSI(2) ultra-short reversion|Long RSI(2)<10|SL=ATR; T=RSI(2)>70|RSI 2|5m|Ranging|yes|[Connors RSI2] via [pandas-ta](https://github.com/twopirllc/pandas-ta)|
|67|BB lower bounce|Buy at lower Bollinger band|Long at/under lower band + RSI<35|SL=below band; T=mid-band|BB 20/2 + RSI|5m|Ranging|partial|[HorizonAI MR](https://www.horizontrading.ai/learn/mean-reversion-trading-strategies)|
|68|BB upper fade|Short at upper band|Short at upper band + RSI>65|SL=above band; T=mid|BB 20/2 + RSI|5m|Ranging|partial|[Proptradingvibes MR](https://proptradingvibes.com/blog/mean-reversion-trading-strategy)|
|69|Z-score reversion|Fade (price−SMA)/std extremes|Long z<−2, short z>+2|SL=z±3; T=z→0|zscore(20)|5m|Ranging|yes|[Kite Metric MR](https://kitemetric.com/blogs/freqtrade-mean-reversion-strategy-a-comprehensive-guide)|
|70|Connors RSI|Composite reversion (RSI+streak+rank)|Long CRSI<15|SL=ATR; T=CRSI>70|Connors RSI|5m|Ranging|partial|[pandas-ta CRSI](https://github.com/twopirllc/pandas-ta)|
|71|Mean-revert to SMA|Distance from SMA mean reverts|Long when price≪SMA20 & turns|SL=ATR; T=SMA20|sma_slow 20|5m|Ranging|yes|[HorizonAI MR](https://www.horizontrading.ai/learn/mean-reversion-trading-strategies)|
|72|EMA-deviation fade|Fade large % deviation from EMA|Long when (price−EMA)/EMA<−x%|SL=ATR; T=EMA|ema 20 + dev|5m|Ranging|yes|[HorizonAI MR](https://www.horizontrading.ai/learn/mean-reversion-trading-strategies)|
|73|Stoch reversion|%K oversold/overbought reversion|Long %K<20 cross up|SL=swing; T=%K>80|Stoch 14/3/3|5m|Ranging|partial|[TradingView Stoch](https://www.tradingview.com/scripts/relativestrengthindex/)|
|74|Williams %R reversion|%R<−80 long, >−20 short|Long %R<−80 turns up|SL=swing; T=mid|Williams %R 14|5m|Ranging|partial|[TradingSim RSI](https://www.tradingsim.com/blog/relative-strength-index-rsi)|
|75|CCI reversion|Fade CCI ±100/±200|Long CCI<−100 turn|SL=ATR; T=CCI 0|CCI 20|5m|Ranging|partial|[pandas-ta CCI](https://github.com/twopirllc/pandas-ta)|

## 7. Moving-average crossover / Supertrend family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|76|EMA 9/21 cross|Fast/slow EMA crossover|Long EMA9>EMA21|SL=ATR; T=trail; exit on opp cross|ema 9/21|5m|Trending|yes|[freqtrade sample](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/templates/sample_strategy.py)|
|77|EMA 5/20 cross|Faster crossover for scalps|Long EMA5>EMA20|SL=ATR; exit opp cross|ema 5/20|3m/5m|Trending|yes|[freqtrade sample](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/templates/sample_strategy.py)|
|78|SMA 20/50 cross|Slower trend crossover|Long SMA20>SMA50|SL=ATR; exit opp cross|sma_fast 20/sma_slow 50|15m|Trending|yes|[backtrader](https://www.backtrader.com/)|
|79|EMA 8/13/21 ribbon|Triple-EMA stacked alignment|Long when 8>13>21 stacked|SL=EMA21; T=trail|ema 8/13/21|5m|Trending|yes|[Guppy/GMMA] via [TradingView](https://www.tradingview.com/scripts/)|
|80|Supertrend 10/3|ATR trend flip|Long when ST turns green|SL=ST line; T=trail ST|Supertrend 10,3|5m/15m|Trending|partial|[TradingView Supertrend](https://in.tradingview.com/scripts/supertrend/)|
|81|Supertrend 7/2|Faster Supertrend|Long on flip|SL=ST; T=trail|Supertrend 7,2|5m|Trending/volatile|partial|[TradingView Supertrend](https://in.tradingview.com/scripts/supertrend/)|
|82|Supertrend+EMA|ST flip with EMA200 filter|Long ST green & price>EMA200|SL=ST; T=trail|ST + ema 200|5m|Trending|partial|[TradingView Supertrend](https://in.tradingview.com/scripts/supertrend/)|
|83|MACD signal cross|MACD/signal crossover|Long MACD crosses signal up|SL=ATR; exit opp cross|MACD 12/26/9|5m/15m|Trending|partial|[freqtrade sample](https://github.com/freqtrade/freqtrade/blob/develop/freqtrade/templates/sample_strategy.py)|
|84|Price/EMA cross|Single MA crossover of price|Long price crosses EMA21 up|SL=ATR; exit cross down|ema 21|5m|Trending|yes|[backtrader](https://www.backtrader.com/)|
|85|Hull MA cross|HMA reduces lag in crossover|Long when HMA turns up|SL=ATR; exit turn down|HMA 21|5m|Trending|partial|[pandas-ta HMA](https://github.com/twopirllc/pandas-ta)|
|86|DEMA/TEMA cross|Double/triple EMA crossover|Long DEMA>TEMA|SL=ATR; exit opp|DEMA/TEMA 20|5m|Trending|partial|[pandas-ta DEMA/TEMA](https://github.com/twopirllc/pandas-ta)|
|87|Guppy MMA|Short vs long EMA group separation|Long when short group>long group expanding|SL=ATR; T=trail|6 short + 6 long EMA|15m|Trending|yes|[GMMA] via [TradingView](https://www.tradingview.com/scripts/)|

## 8. Pivot-point / CPR family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|88|Pivot reversal|Reverse at S1/R1|Long at S1 bounce, short at R1|SL=beyond level; T=PP|Pivot PP/S1/R1|5m|Ranging|partial|[Varsity CPR](https://zerodha.com/varsity/chapter/the-central-pivot-range/)|
|89|Pivot breakout|Break R1 → run to R2/R3|Long>R1 with vol|SL=PP; T=R2|Pivot levels|5m|Trending|partial|[Varsity CPR](https://zerodha.com/varsity/chapter/the-central-pivot-range/)|
|90|CPR break-above|Price above Top Central = bullish control|Long>TC|SL=BC; T=R1/R2|CPR (P/TC/BC)|5m|Trending|partial|[Varsity CPR](https://zerodha.com/varsity/chapter/the-central-pivot-range/), [5paisa CPR](https://www.5paisa.com/blog/cpr-central-pivot-range-trading-strategy-understanding-market-structure)|
|91|CPR break-below|Price below Bottom Central = bearish|Short<BC|SL=TC; T=S1/S2|CPR|5m|Trending (down)|partial|[Groww CPR](https://groww.in/blog/central-pivot-range)|
|92|Narrow-CPR trend|Narrow CPR predicts trend day → directional|Trade breakout w/ Supertrend/MA on narrow-CPR day|SL=opp side; T=trail|CPR width + ST/MA|5m|Trending|partial|[Groww CPR](https://groww.in/blog/central-pivot-range)|
|93|Wide-CPR reversal|Wide CPR → range day → fade S/R|Short at resistance, long at support|SL=beyond; T=opp CPR|CPR width|5m|Ranging|partial|[Groww CPR](https://groww.in/blog/central-pivot-range)|
|94|Virgin-CPR fade|Untouched prior-CPR acts as magnet/reversal|Fade at virgin CPR touch|SL=beyond; T=PP|CPR (virgin)|5m|Ranging|no|[Jainam CPR](https://www.jainam.in/blog/cpr-in-trading/)|
|95|Camarilla pivots|H3/L3 reversal, H4/L4 breakout|Short at H3, long at L3; break H4=go|SL=next level; T=next|Camarilla H1-4/L1-4|5m|Ranging→Trending|partial|[TradingView CPR](https://in.tradingview.com/scripts/cpr/)|
|96|Fibonacci pivots|Fib-weighted pivot S/R|Bounce/break of fib pivots|SL=beyond; T=next fib|Fib pivots|5m|Ranging|partial|[TradingView CPR](https://in.tradingview.com/scripts/cpr/)|
|97|CPR + 1st-candle bias|First 5m candle close vs R1/S1 sets bias|Long if 1st candle closes>R1|SL=PP; T=R2/R3|CPR + opening candle|5m|Trending|partial|[Stockfyre CPR](https://stockfyre.com/what-is-cpr-in-trading-the-central-pivot-range-strategy-explained-for-intraday-traders/)|

## 9. Volume / RVOL family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|98|RVOL>2 mover|Trade stocks with abnormal volume in first hour|Long on momentum if RVOL>2 before 10:00|SL=ATR; T=2R; TSL|RVOL>2|5m|Volatile|yes|[TradingSim RVOL](https://www.tradingsim.com/blog/relative-volume-rvol), [GWC RVOL](https://www.gwcindia.in/blog/how-to-use-relative-volume-rvol-for-better-entry-timing-in-indian-stocks/)|
|99|Volume-spike breakout|Breakout confirmed by RVOL spike|Long on level break + RVOL spike|SL=opp; T=2R|RVOL + level|5m|Volatile|yes|[TrendSpider RVOL](https://trendspider.com/learning-center/relative-volume-rvol-trading-strategies/)|
|100|Volume dry-up reversal|Low volume at extreme = exhaustion|Fade move when vol dries up at extreme|SL=extreme; T=mean|vol, RVOL<0.7|5m|Ranging|yes|[ChartSchool RVOL](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol)|
|101|OBV trend|On-balance-volume confirms price trend|Long when OBV rising & price up|SL=ATR; T=trail|OBV|5m|Trending|partial|[TA-Lib OBV](https://ta-lib.org/)|
|102|Volume-price confirm|Up bars on rising vol, down on falling|Long when price up & vol expanding|SL=ATR; T=trail|vol slope + ret|5m|Trending|yes|[ChartSchool RVOL](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/relative-volume-rvol)|
|103|Climax-volume reversal|Extreme RVOL spike = climax → reversal|Fade after blow-off RVOL>4|SL=extreme; T=mean|RVOL>4|5m|Volatile|yes|[StockTitan RVOL](https://www.stocktitan.net/articles/relative-volume-rvol-trading-indicator)|

## 10. Time-of-day family

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|104|First-hour breakout|Trade break of 09:15–10:15 range|Break of first-hour hi/lo|SL=opp; T=2R; TSL|first-hour range|5m|Trending|partial|[Snappchart VWAP](https://www.snappchart.app/blog/strategy-playbooks/vwap-trading-strategy)|
|105|Last-hour momentum|14:30–15:15 trend continuation|Enter with prevailing trend at 14:30|SL=VWAP; T=close; TSL|time + VWAP/ema|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|106|Lunch-hour fade|11:30–13:00 low-vol range fade|Fade extremes during midday lull|SL=beyond; T=mean|time + VWAP bands|5m|Ranging|partial|[Tradewink VWAP](https://tradewink.com/learn/vwap-trading-strategy)|
|107|09:15–09:20 drive|5-min opening-drive continuation|Trade direction of first 5m bar|SL=opp; T=1.5R|opening candle|1m/5m|Volatile|partial|[ForexTester ORB](https://forextester.com/blog/opening-range-breakout-trading-strategies/)|
|108|Closing trend|3pm directional close-out trend|Enter with day trend ~15:00|SL=tight; T=15:15 close|time + ema/VWAP|5m|Trending|partial|[Warrior VWAP](https://www.warriortrading.com/vwap/)|
|109|Mid-day range break|Break of established 11:00–13:00 box|Break box hi/lo afternoon|SL=opp; T=2R|midday range|5m|Trending|yes|[Snappchart VWAP](https://www.snappchart.app/blog/strategy-playbooks/vwap-trading-strategy)|
|110|Power-hour|14:30–15:15 expansion play|Momentum + RVOL in power hour|SL=ATR; T=close|time + RVOL|5m|Volatile|partial|[TradingSim RVOL](https://www.tradingsim.com/blog/relative-volume-rvol)|
|111|Reversal-window|Mid-morning (~10:30) reversal of opening move|Fade opening move at 10:30 stall|SL=HOD/LOD; T=VWAP|time + VWAP|5m|Ranging|partial|[Humbled VWAP](https://www.humbledtrader.com/blog/vwap-strategy-secrets-boosting-your-trading-skills-to-the-next-level/)|

## 11. Combos, cross-instrument & advanced

| # | Name | Core logic | Entry | Exit | Indicators + params | TF | Regime | Genome | Source |
|---|------|-----------|-------|------|---------------------|----|--------|--------|--------|
|112|ORB+VWAP+RVOL triple|Highest-conviction confluence stack|ORB break + same side VWAP + RVOL≥1.5|SL=VWAP; T=2R; TSL VWAP|OR+VWAP+RVOL|5m|Trending/volatile|partial|[Tradewink VWAP](https://tradewink.com/learn/vwap-trading-strategy)|
|113|Supertrend+VWAP|Trend filter + dynamic mean|Long ST green & price>VWAP|SL=ST; T=trail|ST 10,3 + VWAP|5m|Trending|partial|[TradingView Supertrend](https://in.tradingview.com/scripts/supertrend/)|
|114|RSI+BB combo|Reversion at band with RSI confirm|Long lower-BB touch & RSI<30|SL=below band; T=mid|BB 20/2 + RSI 14|5m|Ranging|partial|[Kite Metric MR](https://kitemetric.com/blogs/freqtrade-mean-reversion-strategy-a-comprehensive-guide)|
|115|EMA+RSI pullback|Trend pullback entry|Long: price>EMA21, RSI dips to 40 & turns|SL=EMA; T=trail|ema 21 + RSI 14|5m|Trending|yes|[FxPro RSI](https://www.fxpro.com/help-section/education/beginners/articles/utilizing-the-relative-strength-index-indicator)|
|116|Index-stock divergence|High-beta stock lags index move → catch-up|Long laggard when index breaks up|SL=ATR; T=catch-up|stock vs NIFTY ret/beta|5m|Trending|no|[Medium momentum](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|117|Sector rotation|Trade strongest stock in strongest sector intraday|Long top-RS stock in leading sector|SL=ATR; T=trail|sector index ret rank|5m|Trending|no|[Medium momentum](https://medium.com/@TradingInvestingStrategies/the-simplest-intraday-momentum-strategy-in-2026-and-how-to-find-the-setups-d2dbefdadac3)|
|118|Intraday pairs|Stat-arb two correlated NSE stocks|Long/short spread when z-score>2|SL=z±3; T=z→0|spread zscore|5m|Ranging|no|[awesome-quant](https://github.com/wilsonfreitas/awesome-quant)|
|119|Heikin-Ashi trend|HA candles smooth trend signal|Long on consecutive HA green, no lower wick|SL=ATR; exit first red HA|Heikin-Ashi|5m/15m|Trending|partial|[TradingView HA](https://www.tradingview.com/scripts/)|
|120|Parabolic SAR|SAR dot flip trend follow|Long when SAR flips below price|SL=SAR; T=trail SAR|PSAR 0.02/0.2|5m/15m|Trending|partial|[TA-Lib SAR](https://ta-lib.org/)|
|121|ADX trend filter|Only take MA/breakout trades when ADX>25|Directional entry gated by ADX>25|SL=ATR; T=trail|ADX 14 + ema cross|5m/15m|Trending|partial|[pandas-ta ADX](https://github.com/twopirllc/pandas-ta)|
|122|TTM squeeze|BB inside Keltner → squeeze fires|Trade momentum direction when squeeze releases|SL=opp; T=trail|BB 20/2 + Keltner 20/1.5|5m/15m|Volatile (post-squeeze)|partial|[pandas-ta squeeze](https://github.com/twopirllc/pandas-ta)|

---

## Genome-mappability summary

- **yes** (expressible with current genome features today): ~38 templates (most ORB-derivatives using range/mom/RVOL, gap-fade/fill, pure momentum/ROC, z-score & SMA/EMA-deviation reversion, RSI threshold reversion & momentum, all SMA/EMA crossovers, range-expansion/NR7/inside-bar/VCP breakouts, volume-price confirm).
- **partial** (need one extra TA-Lib indicator we can add — VWAP, Bollinger, MACD, Supertrend, Donchian/Keltner, pivots/CPR/Camarilla/Fib, ADX, Stoch, CCI, Williams %R, OBV, PSAR, Hull/DEMA/TEMA, Heikin-Ashi, TTM squeeze): ~78 templates.
- **no** (need a second instrument, cross-section, or discretionary read): 6 templates — RS-vs-index/sector (#42, #43, #116, #117), intraday pairs/stat-arb (#118), virgin-CPR (#94), island reversal (#26 — pattern/discretionary).

## Top OSS / reference sources used

1. **freqtrade** strategy templates & indicator patterns — `github.com/freqtrade/freqtrade`
2. **pandas-ta** (TA-Lib-compatible indicators: CCI, TSI, AO, Connors RSI, ADX, Hull, squeeze) — `github.com/twopirllc/pandas-ta`
3. **TradingView** community Pine scripts (Supertrend, Donchian, CPR/Camarilla, RVOL, Heikin-Ashi)
4. **Zerodha Varsity** (CPR, pivots, Dow-theory ranges/breakouts/flags)
5. **backtrader** + **QuantConnect/Lean** backtesting frameworks; **awesome-quant** (pairs/stat-arb) and **TA-Lib** (OBV, SAR) for indicator implementations.

**Total distinct strategy templates: 122**
