# Crypto Options Strategy Templates (BTC / ETH options — Deribit / OKX / Binance, dated + perpetual-option)
# Curated for the ML-network trading phase. Genome = TA features {ret, sma, ema, rsi, atr, atr_pct, mom, vol, zscore, range_pct, rvol} + {threshold, crossover, and/or} ops. Strategy count: 88

> Venues referenced: Deribit (BTC/ETH dated + DVOL index + perps), OKX (BTC/ETH options + perps), Binance (BTC/ETH options + perps), Bybit, plus perpetual-option / Everstrike-style venues. Greeks computable in-repo via fast-vollib / py_vollib Black-76 (crypto options are European, cash/coin-settled — Black-76 forward pricing is the standard). Funding/basis via ccxt. IV-rank/IV-percentile and DVOL term-structure are derivable from the option chain + Deribit DVOL feed. "Genome-mappable" judged against the TA feature genome above: **yes** = pure price/TA rule fully drives entry/exit; **partial** = also needs IV-rank/greeks/OI/funding overlays; **no** = edge is structurally vol/greek/OI/orderflow-driven.

---

## FAMILY A — Directional single-leg (TA-triggered options)

### A1. Long Call — Trend Breakout (BTC)
- **Family:** Directional single-leg | **Timeframe:** intraday–weekly expiry
- **Core logic:** Express bullish breakout with capped risk = premium, leveraged convexity.
- **Entry:** Buy ATM/slightly-ITM call when EMA9 crosses above EMA21 and price breaks prior-day high; prefer IV-rank<50 to avoid overpaying vega.
- **Exit:** SL = 35% of premium or close back below EMA21; target 2R or trail underlying with EMA21.
- **Indicators/params:** EMA(9/21), prior-day high (range), IV-rank overlay; greeks: long delta/gamma/vega, short theta.
- **Regime/seasonality fit:** Trending-up, low/mid IV.
- **Source:** Deribit options playbook; tastytrade; vollib for pricing.
- **Genome-mappable:** yes (EMA crossover + range breakout fully drive entry/exit; IV filter is light overlay).

### A2. Long Put — Trend Breakdown (BTC/ETH)
- **Family:** Directional single-leg | **Timeframe:** intraday–weekly
- **Core logic:** Bearish breakdown with defined risk and downside convexity.
- **Entry:** Buy ATM/ITM put when EMA9<EMA21, price breaks prior-day low, RSI(14)<40; IV-rank<50.
- **Exit:** SL 35% premium or close>EMA21; trail to target.
- **Indicators/params:** EMA(9/21), RSI(14), prior-day low; short delta, long gamma/vega.
- **Regime/seasonality fit:** Trending-down, low/mid IV.
- **Source:** Deribit examples; tastytrade.
- **Genome-mappable:** yes.

### A3. Long Call — Pullback to Rising EMA
- **Family:** Directional single-leg | **Timeframe:** intraday–weekly
- **Core logic:** Buy the dip in an uptrend using a delta~0.6 ITM call.
- **Entry:** Price pulls back to rising EMA20 + bullish reversal candle; IV-rank<60.
- **Exit:** SL below swing low; target prior swing high.
- **Indicators/params:** EMA(20), swing pivot, delta+/gamma+.
- **Regime/seasonality fit:** Trending-up, mid IV.
- **Source:** tastytrade; Deribit.
- **Genome-mappable:** yes.

### A4. Long Put — Rally to Falling EMA
- **Family:** Directional single-leg | **Timeframe:** intraday–weekly
- **Core logic:** Sell rallies in a downtrend via ITM put.
- **Entry:** Price rallies into falling EMA20 + bearish rejection candle.
- **Exit:** SL above swing high; target prior low.
- **Indicators/params:** EMA(20), swing pivot.
- **Regime/seasonality fit:** Trending-down.
- **Source:** Deribit playbook.
- **Genome-mappable:** yes.

### A5. Long Call — Donchian-55 Channel Breakout
- **Family:** Directional single-leg | **Timeframe:** daily/swing, weekly+ expiry
- **Core logic:** Crypto trends persist; buy convexity on a 55-bar high break.
- **Entry:** Underlying closes above Donchian(55) high; buy 25–40 delta OTM call (cheaper convexity).
- **Exit:** Close below Donchian(20) mid; or premium SL 50%.
- **Indicators/params:** Donchian(55/20)=rolling max/min → range_pct/threshold.
- **Regime/seasonality fit:** Strong directional BTC/ETH trends.
- **Source:** Turtle channel adapted; hftbacktest for fills.
- **Genome-mappable:** yes (rolling max/min threshold).

### A6. Long Put — Donchian-55 Breakdown
- **Family:** Directional single-leg | **Timeframe:** daily/swing
- **Core logic:** Downside convexity on 55-bar low break.
- **Entry:** Close below Donchian(55) low; buy 25–40 delta OTM put.
- **Exit:** Close above Donchian(20) mid; premium SL 50%.
- **Indicators/params:** Donchian(55/20).
- **Regime/seasonality fit:** Bear/liquidation trends.
- **Source:** Turtle adapted.
- **Genome-mappable:** yes.

### A7. Cash-Secured Put — Bullish Entry-Discount
- **Family:** Directional / income hybrid | **Timeframe:** weekly–monthly expiry
- **Core logic:** Get paid to bid below market; assignment = buying the dip at discount.
- **Entry:** Sell 20–30 delta put when price>EMA50 (uptrend) and RSI(14)>45; IV-rank>40 to harvest premium.
- **Exit:** Buy back at 50% max profit; roll if tested; accept assignment at support.
- **Indicators/params:** EMA(50), RSI(14), 20–30Δ strike, IV-rank.
- **Regime/seasonality fit:** Up/sideways, elevated IV.
- **Source:** tastytrade wheel; Deribit.
- **Genome-mappable:** partial (TA picks bias/timing; strike + IV-rank gating need greeks/IV).

### A8. Covered Call — Trend-Capped Yield (BTC holding)
- **Family:** Directional / income overlay | **Timeframe:** weekly expiry
- **Core logic:** Sell upside calls against spot/coin holdings for yield; caps upside.
- **Entry:** Hold BTC; sell 15–25 delta OTM call when RSI(14)>60 (stretched up) or near resistance; IV-rank>50.
- **Exit:** Buy back at 50–70% decay or roll up-and-out on breach.
- **Indicators/params:** RSI(14), resistance/range_pct, 15–25Δ strike, IV-rank.
- **Regime/seasonality fit:** Sideways-to-mildly-up, high IV.
- **Source:** Deribit covered-call notes; tastytrade.
- **Genome-mappable:** partial (TA times the sale; income edge is vega/theta + strike selection).

### A9. Protective Put — Tail Hedge for Spot
- **Family:** Directional hedge | **Timeframe:** monthly expiry
- **Core logic:** Insure a long spot/coin position against a crash.
- **Entry:** Buy 10–20 delta OTM put when trend weakens (price<EMA50 or ATR_pct spikes); roll monthly.
- **Exit:** Roll/close with position; let expire if untested.
- **Indicators/params:** EMA(50), atr_pct, 10–20Δ put.
- **Regime/seasonality fit:** Late-cycle / event risk.
- **Source:** Deribit hedging guide.
- **Genome-mappable:** partial (TA triggers hedge-on; cost/strike driven by skew/IV).

### A10. Collar — Zero-Cost Range Lock
- **Family:** Directional hedge | **Timeframe:** monthly
- **Core logic:** Finance a protective put by selling an OTM call → defined band around spot.
- **Entry:** When holding spot in mid-trend, buy 20Δ put + sell 20Δ call (≈zero cost); set when RSI(14) neutral 40–60.
- **Exit:** At expiry / unwind on thesis change.
- **Indicators/params:** RSI(14), 20Δ put + call, skew-aware strike pick.
- **Regime/seasonality fit:** Uncertain/range, want downside protection.
- **Source:** Deribit collar examples.
- **Genome-mappable:** partial (TA times entry; skew determines zero-cost strikes).

### A11. Long Call — Momentum + Volume Surge
- **Family:** Directional single-leg | **Timeframe:** intraday, 0DTE/weekly
- **Core logic:** Buy convexity on momentum confirmed by relative volume.
- **Entry:** mom(10)>0 and rvol>1.8 and price>VWAP-proxy(sma); buy ATM call.
- **Exit:** rvol fade or mom flip; premium SL 40%.
- **Indicators/params:** mom(10), rvol(20), sma.
- **Regime/seasonality fit:** News/liquidation-driven impulse.
- **Source:** hftbacktest; intraday momentum.
- **Genome-mappable:** yes (mom + rvol + threshold).

### A12. Long Put — RSI-Exhaustion Reversal
- **Family:** Directional single-leg | **Timeframe:** swing
- **Core logic:** Fade overbought blow-off via long put.
- **Entry:** RSI(14)>78 + bearish reversal candle at range high; buy ATM put, IV-rank<60.
- **Exit:** RSI back to 50; target prior mid.
- **Indicators/params:** RSI(14), range_pct.
- **Regime/seasonality fit:** Euphoric tops.
- **Source:** Connors-style reversion adapted to options.
- **Genome-mappable:** yes.

### A13. Long Call — Z-Score Oversold Bounce
- **Family:** Directional single-leg | **Timeframe:** swing
- **Core logic:** Deep deviation below mean snaps back; buy call convexity.
- **Entry:** zscore(close,20)<-2.5 and price>EMA200 (regime up); buy ITM call.
- **Exit:** zscore→0; SL zscore<-3.5.
- **Indicators/params:** zscore(20), EMA(200).
- **Regime/seasonality fit:** Dip-buy in uptrend.
- **Source:** stat-reversion adapted.
- **Genome-mappable:** yes (native zscore).

### A14. Synthetic Long (long call + short put) — Leveraged Trend
- **Family:** Directional synthetic | **Timeframe:** weekly–monthly
- **Core logic:** Replicate long forward cheaply at same strike (≈long delta 1, near-zero vega).
- **Entry:** Strong uptrend (EMA20>EMA50>EMA200) + IV-rank low; buy ATM call, sell ATM put.
- **Exit:** Trend break (EMA20<EMA50) or delta-stop.
- **Indicators/params:** EMA stack; synthetic forward.
- **Regime/seasonality fit:** Confident directional, low IV.
- **Source:** put-call parity; Deribit.
- **Genome-mappable:** partial (TA drives; structure needs parity/greeks, margin on short put).

### A15. Risk Reversal — Skew-Cheap Directional
- **Family:** Directional synthetic | **Timeframe:** weekly–monthly
- **Core logic:** Sell expensive-skew put, buy cheaper-skew call (or reverse) for directional + skew edge.
- **Entry:** Bullish + put skew rich (25Δ put IV ≫ 25Δ call IV); sell 25Δ put, buy 25Δ call.
- **Exit:** Skew normalizes or delta target.
- **Indicators/params:** 25Δ risk-reversal skew, EMA trend.
- **Regime/seasonality fit:** Directional with skew dislocation.
- **Source:** Deribit skew analytics; leanderdulac/crypto_vol_arb.
- **Genome-mappable:** no (edge is structurally skew-driven).

---

## FAMILY B — Vertical & ratio spreads

### B1. Bull Call Spread — Defined-Risk Breakout
- **Family:** Vertical debit | **Timeframe:** weekly–monthly
- **Core logic:** Buy ATM call, sell higher OTM call; cheaper bullish play, capped reward.
- **Entry:** EMA20>EMA50 + breakout; long ATM/short 30Δ; prefer mid IV.
- **Exit:** 50–75% max profit; SL on trend break.
- **Indicators/params:** EMA(20/50), strike width; net long delta, reduced vega.
- **Regime/seasonality fit:** Moderately bullish.
- **Source:** Deribit spreads; optopsy backtests.
- **Genome-mappable:** partial (TA picks bias; strike selection needs greeks/IV).

### B2. Bear Put Spread — Defined-Risk Breakdown
- **Family:** Vertical debit | **Timeframe:** weekly–monthly
- **Core logic:** Buy ATM put, sell lower OTM put; capped bearish.
- **Entry:** EMA20<EMA50 + breakdown.
- **Exit:** 50–75% max profit; SL trend reclaim.
- **Indicators/params:** EMA(20/50), strikes.
- **Regime/seasonality fit:** Moderately bearish.
- **Source:** Deribit; optopsy.
- **Genome-mappable:** partial.

### B3. Bull Put Spread — Credit Support Hold
- **Family:** Vertical credit | **Timeframe:** weekly
- **Core logic:** Sell put above support, buy lower put; collect credit if price holds.
- **Entry:** Price>EMA50 + RSI>45; sell 30Δ put / buy 15Δ; IV-rank>40.
- **Exit:** 50% credit decay; roll/close on support break.
- **Indicators/params:** EMA(50), RSI, IV-rank, strikes.
- **Regime/seasonality fit:** Up/sideways, elevated IV.
- **Source:** tastytrade; Deribit.
- **Genome-mappable:** partial (TA picks the support; credit/theta edge + IV-rank gating).

### B4. Bear Call Spread — Credit Resistance Cap
- **Family:** Vertical credit | **Timeframe:** weekly
- **Core logic:** Sell call below resistance, buy higher call; profit if price stays capped.
- **Entry:** Price<EMA50 or at resistance, RSI<55; sell 30Δ call/buy 15Δ; IV-rank>40.
- **Exit:** 50% credit; roll on breach.
- **Indicators/params:** EMA(50), RSI, resistance/range_pct, IV-rank.
- **Regime/seasonality fit:** Down/sideways, high IV.
- **Source:** tastytrade; Deribit.
- **Genome-mappable:** partial.

### B5. Call Ratio Spread (1×2) — Cheap Upside, Skew Sell
- **Family:** Ratio | **Timeframe:** monthly
- **Core logic:** Buy 1 ATM call, sell 2 OTM calls; finance upside by selling pricier upside vol.
- **Entry:** Mildly bullish + upside vol/skew elevated; net credit/zero cost.
- **Exit:** Manage if price approaches short strikes (gamma risk above).
- **Indicators/params:** strikes, call skew, greeks (gamma/vega).
- **Regime/seasonality fit:** Slow grind up, rich upside vol.
- **Source:** Deribit ratio examples.
- **Genome-mappable:** no (edge is skew/vega; unbounded gamma risk above).

### B6. Put Ratio Spread (1×2) — Downside Skew Sell
- **Family:** Ratio | **Timeframe:** monthly
- **Core logic:** Buy 1 ATM put, sell 2 OTM puts; finance hedge with rich put skew.
- **Entry:** Mildly bearish + put skew very rich.
- **Exit:** Manage near short strikes (tail risk below).
- **Indicators/params:** strikes, put skew.
- **Regime/seasonality fit:** Controlled decline, expensive put skew.
- **Source:** crypto_vol_arb skew notes.
- **Genome-mappable:** no.

### B7. Call Backspread (1×2 long) — Long Tail Convexity
- **Family:** Ratio backspread | **Timeframe:** monthly
- **Core logic:** Sell 1 near call, buy 2 farther calls; long convexity for explosive upside, often near-zero/credit.
- **Entry:** Coiled/low IV + expecting upside breakout (atr_pct compressed).
- **Exit:** On big move (profit) or time decay (small loss zone).
- **Indicators/params:** atr_pct compression, strikes, long gamma/vega.
- **Regime/seasonality fit:** Pre-expansion, cheap vol.
- **Source:** Deribit; optopsy.
- **Genome-mappable:** partial (atr_pct compression can trigger; payoff driven by gamma/vega).

### B8. Put Backspread — Crash Convexity
- **Family:** Ratio backspread | **Timeframe:** monthly
- **Core logic:** Sell 1 near put, buy 2 farther puts; cheap long crash exposure.
- **Entry:** Low IV + bearish-risk regime (price<EMA200, weakening).
- **Exit:** On crash (profit) or decay.
- **Indicators/params:** EMA(200), IV level, strikes.
- **Regime/seasonality fit:** Complacent high before stress.
- **Source:** tail-hedge literature.
- **Genome-mappable:** partial.

### B9. Christmas-Tree / Broken-Wing Butterfly (Bullish)
- **Family:** Multi-leg directional | **Timeframe:** monthly
- **Core logic:** Skewed butterfly with no/low-cost downside, directional tilt up.
- **Entry:** Bullish bias + want defined risk; place body at target zone.
- **Exit:** Near max-profit pin or thesis change.
- **Indicators/params:** target strike (range projection), greeks.
- **Regime/seasonality fit:** Drift toward a target level.
- **Source:** Deribit structures.
- **Genome-mappable:** no (pin/greek-driven payoff).

### B10. Diagonal Bull Call (poor-man's covered call)
- **Family:** Diagonal directional | **Timeframe:** long LEAP-style + weekly shorts
- **Core logic:** Long deep-ITM far-dated call as stock substitute; sell weekly OTM calls for yield.
- **Entry:** Uptrend (EMA stack up); buy 70–80Δ far call, sell 20–25Δ weekly.
- **Exit:** Roll shorts weekly; close on trend break.
- **Indicators/params:** EMA stack, deltas, theta harvest.
- **Regime/seasonality fit:** Slow uptrend.
- **Source:** PMCC adapted; tastytrade.
- **Genome-mappable:** partial (trend TA + theta/greek structure).

---

## FAMILY C — Neutral income (short premium)

### C1. Short Straddle — At-the-Money Premium Harvest
- **Family:** Neutral income | **Timeframe:** weekly–monthly
- **Core logic:** Sell ATM call+put; profit from time decay + IV contraction in a range.
- **Entry:** IV-rank>70, range-bound (price≈EMA50, atr_pct low/falling, ADX-proxy low).
- **Exit:** 25–35% credit; delta-hedge or close if break > 1×expected move.
- **Indicators/params:** IV-rank, atr_pct, EMA(50); short gamma/vega, long theta.
- **Regime/seasonality fit:** Low realized vol, high IV (positive VRP).
- **Source:** tastytrade; Deribit; optopsy.
- **Genome-mappable:** no (edge = IV-RV vol-risk-premium; TA only flags range).

### C2. Short Strangle — Wide OTM Premium
- **Family:** Neutral income | **Timeframe:** weekly–monthly
- **Core logic:** Sell 16Δ call + 16Δ put; wider breakevens than straddle.
- **Entry:** IV-rank>60, range_pct compressed; price mid-range.
- **Exit:** 50% credit; defend tested side, roll untested.
- **Indicators/params:** IV-rank, 16Δ strikes, range_pct.
- **Regime/seasonality fit:** Range, elevated IV.
- **Source:** tastytrade; Deribit.
- **Genome-mappable:** no.

### C3. Iron Condor — Defined-Risk Range Income
- **Family:** Neutral income | **Timeframe:** weekly–monthly
- **Core logic:** Short strangle + protective wings; capped risk range play.
- **Entry:** IV-rank>50, low atr_pct, price mid-range; sell 16Δ, buy 8Δ wings.
- **Exit:** 50% max profit; manage tested spread.
- **Indicators/params:** IV-rank, atr_pct, deltas.
- **Regime/seasonality fit:** Range-bound, high IV.
- **Source:** Deribit; optopsy backtests.
- **Genome-mappable:** no (vol-premium edge; TA flags range only).

### C4. Iron Butterfly — Pin Income
- **Family:** Neutral income | **Timeframe:** weekly
- **Core logic:** ATM short straddle + wings; max profit if price pins strike.
- **Entry:** Very low expected move, IV-rank high, price magnet at round level/max-pain.
- **Exit:** Decay capture; close before gamma risk into expiry.
- **Indicators/params:** IV-rank, max-pain/OI level.
- **Regime/seasonality fit:** Pin/expiry days, high IV.
- **Source:** Deribit; max-pain studies.
- **Genome-mappable:** no.

### C5. Jade Lizard — No-Upside-Risk Premium
- **Family:** Neutral/bullish income | **Timeframe:** monthly
- **Core logic:** Short put + short call spread; total credit ≥ call-spread width → no upside risk.
- **Entry:** Neutral-to-bullish, IV-rank>50, put skew rich.
- **Exit:** 50% credit; defend put side on decline.
- **Indicators/params:** IV-rank, put skew, strikes.
- **Regime/seasonality fit:** Sideways-up, rich put skew.
- **Source:** tastytrade jade lizard; Deribit.
- **Genome-mappable:** no.

### C6. Big-Lizard — ATM Straddle + Call Spread
- **Family:** Neutral income | **Timeframe:** monthly
- **Core logic:** Short ATM straddle with call-spread overlay removing upside risk.
- **Entry:** High IV-rank, neutral.
- **Exit:** 25% credit.
- **Indicators/params:** IV-rank, strikes.
- **Regime/seasonality fit:** High IV range.
- **Source:** tastytrade.
- **Genome-mappable:** no.

### C7. Calendarized Short Strangle (defined duration)
- **Family:** Neutral income | **Timeframe:** weekly cycle
- **Core logic:** Roll a short strangle weekly to maximize theta with managed gamma.
- **Entry:** Each cycle when IV-rank>55 and range stable.
- **Exit:** 50% per cycle; skip cycles when atr_pct rising.
- **Indicators/params:** IV-rank, atr_pct gate.
- **Regime/seasonality fit:** Persistent positive VRP regimes.
- **Source:** systematic VRP harvesting.
- **Genome-mappable:** no.

### C8. Short Iron Condor — DVOL-Mean-Reversion Timed
- **Family:** Neutral income | **Timeframe:** weekly
- **Core logic:** Sell condor when Deribit DVOL is stretched high and mean-reverting.
- **Entry:** DVOL zscore>+1.5 (overpriced vol) + range_pct low.
- **Exit:** DVOL reverts / 50% profit.
- **Indicators/params:** DVOL index zscore, range_pct.
- **Regime/seasonality fit:** Post-spike vol normalization.
- **Source:** Deribit DVOL; vol mean-reversion.
- **Genome-mappable:** no (DVOL/IV-level driven; zscore is on a vol series, not price).

### C9. Ratio Iron Condor (unbalanced wings)
- **Family:** Neutral income | **Timeframe:** monthly
- **Core logic:** Skew the condor toward the side with richer IV for extra credit.
- **Entry:** Skew asymmetry + range; weight the rich side.
- **Exit:** 50% credit.
- **Indicators/params:** skew, IV-rank, strikes.
- **Regime/seasonality fit:** Skewed-IV range.
- **Source:** Deribit skew.
- **Genome-mappable:** no.

### C10. Short Strangle + ATR-Band Range Filter
- **Family:** Neutral income | **Timeframe:** weekly
- **Core logic:** Only sell strangles when price has stayed inside an ATR band (true range regime).
- **Entry:** Price within EMA50 ± 1.5×ATR for N bars + IV-rank>55.
- **Exit:** 50% credit or band break.
- **Indicators/params:** EMA(50), ATR(14), IV-rank.
- **Regime/seasonality fit:** Confirmed low-realized-vol range.
- **Source:** systematic income + ATR regime gate.
- **Genome-mappable:** partial (ATR-band range gate is TA; premium edge still vega/theta).

---

## FAMILY D — Long volatility (debit structures)

### D1. Long Straddle — Pre-Event Vol Expansion
- **Family:** Long vol | **Timeframe:** days into event
- **Core logic:** Buy ATM call+put before catalyst (CPI/FOMC/halving/ETF decision) for a big move either way.
- **Entry:** atr_pct compressed + IV not yet bid (IV-rank<40) ahead of known event.
- **Exit:** Post-event on realized move; cut on IV crush if no move.
- **Indicators/params:** atr_pct, IV-rank, event calendar; long gamma/vega.
- **Regime/seasonality fit:** Vol-compression before catalysts.
- **Source:** Deribit event playbook.
- **Genome-mappable:** partial (atr_pct compression triggers; IV-rank + event needed; payoff gamma-driven).

### D2. Long Strangle — Cheap Breakout Convexity
- **Family:** Long vol | **Timeframe:** weekly
- **Core logic:** Buy OTM call+put; cheaper than straddle, needs larger move.
- **Entry:** Bollinger/Keltner squeeze (atr_pct N-period low) + IV-rank<35.
- **Exit:** On expansion / range break; theta-stop if quiet.
- **Indicators/params:** atr_pct min, BB-width (sma±std→zscore), IV-rank.
- **Regime/seasonality fit:** Coiled low-vol before expansion.
- **Source:** TTM squeeze adapted; Deribit.
- **Genome-mappable:** partial (squeeze detection TA; IV-cheapness + greek payoff).

### D3. Calendar Spread (long vol via term structure)
- **Family:** Long vol / term | **Timeframe:** sell front, hold back
- **Core logic:** Sell near-dated, buy far-dated same strike; profit from front theta + back vega.
- **Entry:** Term structure flat/backwardated (front IV ≥ back IV) at ATM; expect calm then move.
- **Exit:** Front expires / vol term re-steepens.
- **Indicators/params:** IV term-structure slope, ATM strike, vega.
- **Regime/seasonality fit:** Backwardated/flat term, range near-term.
- **Source:** Deribit term-structure; crypto_vol_arb.
- **Genome-mappable:** no (term-structure/vega edge).

### D4. Double Calendar — Range + Term Edge
- **Family:** Long vol / term | **Timeframe:** monthly
- **Core logic:** Calendars at two strikes bracketing price; profit if pinned in range while term-vega gains.
- **Entry:** Range + steep-able term structure.
- **Exit:** Front cycle decay captured.
- **Indicators/params:** term slope, range_pct, strikes.
- **Regime/seasonality fit:** Range with term edge.
- **Source:** Deribit calendars.
- **Genome-mappable:** no.

### D5. Diagonal Spread — Directional + Term Vol
- **Family:** Long vol / directional | **Timeframe:** monthly
- **Core logic:** Calendar with offset strikes; directional drift + term/vega edge.
- **Entry:** Mild trend (EMA20 slope) + favorable term structure.
- **Exit:** Roll front; close on trend break.
- **Indicators/params:** EMA(20) slope, term slope.
- **Regime/seasonality fit:** Slow trend, term edge.
- **Source:** Deribit; tastytrade.
- **Genome-mappable:** partial (trend TA + term/greek structure).

### D6. Long Strangle — Vol-Cone Cheap-IV Entry
- **Family:** Long vol | **Timeframe:** weekly–monthly
- **Core logic:** Buy vol when current IV sits at the low band of the historical volatility cone for that tenor.
- **Entry:** IV below cone 25th percentile for the chosen DTE.
- **Exit:** IV reverts toward cone median or realized move.
- **Indicators/params:** volatility cone (HV percentiles by tenor), IV.
- **Regime/seasonality fit:** Cheap-vol troughs.
- **Source:** volatility-cone methodology; crypto_vol_arb.
- **Genome-mappable:** no (cone is a vol-statistics construct, not price-TA).

### D7. Long Call Calendar — Upside Vol Ramp
- **Family:** Long vol / directional | **Timeframe:** monthly
- **Core logic:** Call calendar above price to benefit from drift up + vega.
- **Entry:** Bullish bias + cheap back-month vol.
- **Exit:** Front expiry.
- **Indicators/params:** EMA trend, term slope.
- **Regime/seasonality fit:** Slow grind up.
- **Source:** Deribit.
- **Genome-mappable:** partial.

### D8. Long Put Calendar — Downside Vol Ramp
- **Family:** Long vol / directional | **Timeframe:** monthly
- **Core logic:** Put calendar below price for drift down + vega.
- **Entry:** Bearish bias + cheap back vol.
- **Exit:** Front expiry.
- **Indicators/params:** EMA trend, term slope.
- **Regime/seasonality fit:** Slow decline.
- **Source:** Deribit.
- **Genome-mappable:** partial.

### D9. Straddle Swap — Roll Long Vol on Vol-Compression Cycles
- **Family:** Long vol systematic | **Timeframe:** weekly cycles
- **Core logic:** Systematically hold long straddles only during low-IV / low-RV windows, flat otherwise.
- **Entry:** IV-rank<25 AND atr_pct at N-low.
- **Exit:** IV-rank>60 or realized expansion.
- **Indicators/params:** IV-rank, atr_pct.
- **Regime/seasonality fit:** Mean-reverting vol regimes.
- **Source:** systematic long-vol timing.
- **Genome-mappable:** partial (atr_pct gate TA; IV-rank gate + gamma payoff).

---

## FAMILY E — Advanced quant volatility & arbitrage

### E1. Gamma Scalping (delta-hedged long straddle)
- **Family:** Vol arb / gamma | **Timeframe:** intraday continuous
- **Core logic:** Hold long gamma (straddle), delta-hedge with perp/spot; profit when realized vol > paid IV.
- **Entry:** Buy ATM straddle when IV<expected RV; hedge delta on bands.
- **Exit:** Unwind when RV<IV or theta bleed dominates.
- **Indicators/params:** delta (Black-76), gamma, RV vs IV; hedge band = k×ATR.
- **Regime/seasonality fit:** High realized vol, underpriced IV.
- **Source:** hftbacktest delta-hedge; Sinclair "Volatility Trading"; crypto_vol_arb.
- **Genome-mappable:** no (edge = RV>IV; hedging needs continuous greeks).

### E2. Reverse Gamma Scalp (delta-hedged short straddle)
- **Family:** Vol arb / gamma | **Timeframe:** intraday
- **Core logic:** Short gamma, hedge against; profit when realized vol < IV (collect theta).
- **Entry:** Short ATM straddle when IV≫RV (high VRP); hedge to flat.
- **Exit:** RV approaches IV or stop on vol spike.
- **Indicators/params:** greeks, RV vs IV, hedge band.
- **Regime/seasonality fit:** Calm, overpriced IV.
- **Source:** Sinclair; tastytrade; hftbacktest.
- **Genome-mappable:** no.

### E3. Delta-Neutral Dynamic Hedging (DDH overlay)
- **Family:** Vol arb | **Timeframe:** continuous
- **Core logic:** Keep any option book delta-flat with perps; isolate vega/gamma/theta P&L.
- **Entry:** Re-hedge when net delta breaches threshold band.
- **Exit:** Managed continuously.
- **Indicators/params:** portfolio delta, ATR-scaled rehedge band.
- **Regime/seasonality fit:** Any; isolates vol P&L.
- **Source:** Deribit hedging; hftbacktest.
- **Genome-mappable:** no (greek-driven).

### E4. IV–RV Spread Arbitrage (variance risk premium)
- **Family:** Vol arb | **Timeframe:** weekly
- **Core logic:** Sell options when implied vol systematically exceeds subsequently-realized vol (positive VRP), buy when negative.
- **Entry:** (IV − trailing RV) zscore > +1; short vol delta-hedged. Reverse when < −1.
- **Exit:** Spread mean-reverts.
- **Indicators/params:** IV, RV (close-to-close vol of underlying = vol feature), zscore of spread.
- **Regime/seasonality fit:** Stable VRP regimes.
- **Source:** Carr-Wu variance risk premium; crypto_vol_arb.
- **Genome-mappable:** no (RV is computable but edge is the IV-vs-RV vol spread, not price TA).

### E5. Volatility-Surface Arbitrage (calendar mispricing)
- **Family:** Vol arb / surface | **Timeframe:** intraday–days
- **Core logic:** Fit the IV surface; trade strikes/tenors that deviate from the smooth no-arbitrage surface (e.g. SVI fit).
- **Entry:** Buy cheap nodes / sell rich nodes vs fitted surface; delta+vega neutralize.
- **Exit:** Node reprices to surface.
- **Indicators/params:** SVI/SABR surface fit residuals, greeks.
- **Regime/seasonality fit:** Liquid surface with transient dislocations.
- **Source:** leanderdulac/crypto_vol_arb; gatheral SVI; Deribit chain.
- **Genome-mappable:** no.

### E6. Calendar-Arbitrage (term-structure no-arb)
- **Family:** Vol arb / surface | **Timeframe:** days
- **Core logic:** Total variance must be non-decreasing in maturity; trade violations.
- **Entry:** When near-tenor total variance > far-tenor (arb), sell near vol / buy far.
- **Exit:** Term re-orders.
- **Indicators/params:** total variance by tenor.
- **Regime/seasonality fit:** Stressed front-month spikes.
- **Source:** Gatheral no-arb conditions; crypto_vol_arb.
- **Genome-mappable:** no.

### E7. Butterfly-Arb (vertical convexity no-arb)
- **Family:** Vol arb / surface | **Timeframe:** intraday
- **Core logic:** Call price must be convex in strike; trade negative butterflies (static arb).
- **Entry:** When a strike's price violates convexity, buy the cheap fly.
- **Exit:** Convexity restored.
- **Indicators/params:** strike convexity, fly pricing.
- **Regime/seasonality fit:** Thin-strike dislocations.
- **Source:** static no-arb; Deribit.
- **Genome-mappable:** no.

### E8. Skew Trading — 25Δ Risk-Reversal Mean Reversion
- **Family:** Vol arb / skew | **Timeframe:** days–weeks
- **Core logic:** BTC/ETH 25Δ RR (call IV − put IV) mean-reverts; fade extremes.
- **Entry:** RR zscore>+1.5 (calls too rich) → sell call skew/buy put skew, vega-hedged. Reverse < −1.5.
- **Exit:** RR reverts to mean.
- **Indicators/params:** 25Δ RR series zscore, vega-neutral structure.
- **Regime/seasonality fit:** Range-bound sentiment swings.
- **Source:** Deribit skew analytics; crypto_vol_arb.
- **Genome-mappable:** no.

### E9. Skew Trading — Directional Skew Momentum
- **Family:** Vol arb / skew | **Timeframe:** days
- **Core logic:** Sharp put-skew steepening confirms downside trend; trade with skew.
- **Entry:** Put skew rising fast + price<EMA50 → bearish structure.
- **Exit:** Skew flattens.
- **Indicators/params:** 25Δ RR slope, EMA(50).
- **Regime/seasonality fit:** Stress/de-risking phases.
- **Source:** skew-as-sentiment studies.
- **Genome-mappable:** no (skew-driven; EMA only secondary).

### E10. Dispersion Trade (index vs single-name) — BTC/ETH proxy
- **Family:** Vol arb / dispersion | **Timeframe:** weeks
- **Core logic:** Sell "index" vol (e.g. a correlated majors basket) and buy component vol when implied correlation is rich.
- **Entry:** Implied correlation (index IV vs weighted component IV) high.
- **Exit:** Correlation normalizes.
- **Indicators/params:** implied correlation, basket weights, vega.
- **Regime/seasonality fit:** High implied-correlation regimes (macro-driven crypto).
- **Source:** dispersion literature adapted to crypto majors.
- **Genome-mappable:** no.

### E11. ETH–BTC Vol Spread (cross-asset vega)
- **Family:** Vol arb | **Timeframe:** days–weeks
- **Core logic:** ETH/BTC IV ratio mean-reverts; long cheaper vol / short richer.
- **Entry:** (ETH IV / BTC IV) zscore extreme.
- **Exit:** Ratio reverts.
- **Indicators/params:** ETH IV, BTC IV ratio zscore.
- **Regime/seasonality fit:** Stable vol relationship.
- **Source:** cross-asset vol-spread; crypto_vol_arb.
- **Genome-mappable:** no.

### E12. Variance-Swap Replication (static option strip)
- **Family:** Vol arb | **Timeframe:** monthly
- **Core logic:** Replicate a variance swap via a 1/K²-weighted strip of OTM options; trade synthetic variance vs realized.
- **Entry:** When synthetic implied variance > expected realized.
- **Exit:** At maturity / realized variance accrues.
- **Indicators/params:** OTM strip weights (1/K²), realized variance.
- **Regime/seasonality fit:** Positive VRP harvesting, hedged.
- **Source:** Demeterfi-Derman-Kamal-Zou variance replication; Deribit.
- **Genome-mappable:** no.

### E13. Vol-of-Vol / DVOL Trading
- **Family:** Vol arb | **Timeframe:** days
- **Core logic:** Trade the Deribit DVOL index (mean-reverting vol-of-vol) via options on vol or DVOL futures.
- **Entry:** DVOL zscore extreme → fade.
- **Exit:** Mean revert.
- **Indicators/params:** DVOL zscore.
- **Regime/seasonality fit:** Vol-spike normalization.
- **Source:** Deribit DVOL product.
- **Genome-mappable:** no.

### E14. Volatility-Cone Percentile Switch
- **Family:** Vol arb regime | **Timeframe:** weekly
- **Core logic:** Use the HV cone to decide long-vol (IV at low percentile) vs short-vol (IV at high percentile) for the tenor.
- **Entry:** IV < cone 20th pct → buy vol; > 80th pct → sell vol.
- **Exit:** IV reverts to cone median.
- **Indicators/params:** vol cone (HV by tenor), IV.
- **Regime/seasonality fit:** Adaptive vol regime.
- **Source:** vol-cone method; Sinclair.
- **Genome-mappable:** no.

### E15. Gamma-Weighted Pin / Dealer-Gamma Fade
- **Family:** Orderflow / gamma | **Timeframe:** intraday into expiry
- **Core logic:** Where dealer gamma is large (high OI strikes), price gets pinned; fade moves toward the gamma wall.
- **Entry:** Near expiry, fade away-from-wall extensions toward max-OI strike.
- **Exit:** Pin to wall / expiry.
- **Indicators/params:** OI by strike, gamma exposure, max-pain.
- **Regime/seasonality fit:** Expiry days, concentrated OI.
- **Source:** dealer-gamma / max-pain studies; Deribit OI.
- **Genome-mappable:** no (OI/gamma-driven).

### E16. Vega-Neutral Theta Harvest (calendar + ratio combo)
- **Family:** Vol arb | **Timeframe:** monthly
- **Core logic:** Construct a vega-neutral, positive-theta book that profits from decay regardless of small vol moves.
- **Entry:** Build when term structure allows vega-flat positive-theta.
- **Exit:** Rebalance to stay vega-flat.
- **Indicators/params:** vega, theta across tenors.
- **Regime/seasonality fit:** Stable vol surface.
- **Source:** market-maker theta harvesting.
- **Genome-mappable:** no.

### E17. Smile Curvature Trade (butterfly vol)
- **Family:** Vol arb / skew | **Timeframe:** days
- **Core logic:** Trade the convexity of the smile (ATM-fly vol) when wings rich/cheap vs ATM.
- **Entry:** Fly vol zscore extreme → sell wings/buy ATM or reverse.
- **Exit:** Smile normalizes.
- **Indicators/params:** 25Δ butterfly vol zscore.
- **Regime/seasonality fit:** Smile dislocations.
- **Source:** smile-dynamics literature; crypto_vol_arb.
- **Genome-mappable:** no.

### E18. Forward-Vol / Calendar-Vol Carry
- **Family:** Vol arb / term | **Timeframe:** weeks
- **Core logic:** Trade the implied forward volatility between two tenors when it's mispriced vs expected spot-vol path.
- **Entry:** Forward vol cheap/rich vs HV expectation.
- **Exit:** Roll-down realizes.
- **Indicators/params:** forward vol from term structure.
- **Regime/seasonality fit:** Steep/flat term regimes.
- **Source:** forward-variance literature.
- **Genome-mappable:** no.

### E19. Conversion / Reversal Arbitrage (put-call parity)
- **Family:** Arbitrage | **Timeframe:** intraday
- **Core logic:** Lock risk-free edge when synthetic (call−put) deviates from forward (carry/funding).
- **Entry:** When call−put ≠ forward−strike beyond costs; box the legs with perp/spot.
- **Exit:** Convergence at expiry.
- **Indicators/params:** put-call parity, forward (funding/basis).
- **Regime/seasonality fit:** Microstructure dislocations.
- **Source:** put-call parity; ccxt for funding/basis.
- **Genome-mappable:** no (parity/funding-driven).

### E20. Box Spread — Funding-Rate Synthetic Lending
- **Family:** Arbitrage / financing | **Timeframe:** to expiry
- **Core logic:** A box (bull call + bear put spread) locks a fixed payoff = synthetic interest rate; arb vs prevailing crypto yields.
- **Entry:** When box price implies a rate cheaper/richer than borrow/lend or funding.
- **Exit:** Hold to expiry.
- **Indicators/params:** box pricing, funding/yield comparison.
- **Regime/seasonality fit:** Rate dislocations.
- **Source:** box-spread financing; Deribit.
- **Genome-mappable:** no.

---

## FAMILY F — Crypto-native (funding / basis / perp-vol)

### F1. Funding-vs-IV Carry (short vol when funding pays vol seller)
- **Family:** Crypto-native vol | **Timeframe:** funding cycles (8h) / weekly
- **Core logic:** When perp funding is extreme and IV is high, sell options + take the funded perp hedge for double carry.
- **Entry:** Funding zscore>+1.5 (longs overpay) + IV-rank>60 → short call (covered by short perp) harvesting funding + theta.
- **Exit:** Funding normalizes or 50% premium.
- **Indicators/params:** funding rate zscore (ccxt), IV-rank, greeks.
- **Regime/seasonality fit:** Overheated longs, rich IV.
- **Source:** funding-carry + vol-carry combos; ccxt funding.
- **Genome-mappable:** no (funding + IV driven).

### F2. Perp-Vol Carry (sell options, finance with funding)
- **Family:** Crypto-native vol | **Timeframe:** weekly
- **Core logic:** Delta-hedge short options with perps; net carry = theta − hedge cost ± funding.
- **Entry:** Positive expected (theta + funding − slippage); IV>RV.
- **Exit:** Carry turns negative or vol spike.
- **Indicators/params:** funding, theta, RV vs IV.
- **Regime/seasonality fit:** Calm, positive-carry.
- **Source:** crypto vol-carry desks; hftbacktest.
- **Genome-mappable:** no.

### F3. Cash-and-Carry + Covered Call (triple yield)
- **Family:** Crypto-native income | **Timeframe:** quarterly
- **Core logic:** Long spot, short dated future (basis yield), sell covered calls → stack basis + premium.
- **Entry:** Futures in contango (basis>0) + IV-rank>50.
- **Exit:** At future expiry / roll.
- **Indicators/params:** basis (future−spot), IV-rank.
- **Regime/seasonality fit:** Contango bull markets.
- **Source:** cash-and-carry + covered call; ccxt basis.
- **Genome-mappable:** no.

### F4. Funding-Skew Divergence Signal → Options Directional
- **Family:** Crypto-native directional | **Timeframe:** days
- **Core logic:** When funding is very positive but options put-skew steepening (hedging), expect long squeeze; buy puts.
- **Entry:** Funding>+ extreme AND put skew rising AND price<EMA20.
- **Exit:** Squeeze plays out / skew flattens.
- **Indicators/params:** funding, 25Δ RR, EMA(20).
- **Regime/seasonality fit:** Over-leveraged longs.
- **Source:** funding-skew divergence; Deribit + ccxt.
- **Genome-mappable:** no.

### F5. Perpetual-Option Funding Harvest (Everstrike-style)
- **Family:** Perpetual option | **Timeframe:** continuous
- **Core logic:** Perpetual options charge a continuous funding/streaming premium; sell perp-options to collect it when vol overpriced.
- **Entry:** Perp-option funding implies IV>RV; sell + delta-hedge.
- **Exit:** Funding/IV normalizes.
- **Indicators/params:** perp-option funding, IV vs RV.
- **Regime/seasonality fit:** Overpriced perpetual vol.
- **Source:** Everstrike / Panoptic-style perpetual options docs.
- **Genome-mappable:** no.

### F6. Perpetual-Option Long Convexity (no-expiry gamma)
- **Family:** Perpetual option | **Timeframe:** continuous
- **Core logic:** Hold perpetual long gamma without roll/expiry; pay streaming funding, scalp realized moves.
- **Entry:** Perp-option funding cheap (implied < expected RV) + atr_pct compressed.
- **Exit:** Funding richens or RV<implied.
- **Indicators/params:** perp-option funding, atr_pct.
- **Regime/seasonality fit:** Cheap perpetual vol before expansion.
- **Source:** Panoptic / Everstrike perpetual options.
- **Genome-mappable:** partial (atr_pct gate TA; funding/gamma drives payoff).

### F7. Basis-Spike Volatility Hedge
- **Family:** Crypto-native | **Timeframe:** event
- **Core logic:** Extreme basis blow-outs precede vol; buy straddles when basis dislocates.
- **Entry:** Basis zscore extreme + IV not yet elevated.
- **Exit:** Vol realizes / basis normalizes.
- **Indicators/params:** basis zscore (ccxt), IV-rank.
- **Regime/seasonality fit:** Leverage flushes.
- **Source:** basis-stress signals.
- **Genome-mappable:** no.

### F8. Funding-Reset Theta Scalp (8h cycle)
- **Family:** Crypto-native income | **Timeframe:** intraday 8h
- **Core logic:** Sell short-dated options to capture decay across funding resets while perp-hedged for funding.
- **Entry:** Stable range + IV-rank mid/high before funding stamp.
- **Exit:** After funding capture / decay.
- **Indicators/params:** funding schedule, IV-rank, theta.
- **Regime/seasonality fit:** Range, positive funding.
- **Source:** funding-cycle harvesting.
- **Genome-mappable:** no.

---

## FAMILY G — Event / expiry / OI-structured

### G1. Pre-FOMC / Pre-CPI Long Straddle
- **Family:** Event vol | **Timeframe:** days into macro print
- **Core logic:** Crypto reacts to US macro; own gamma into the print before IV fully bids.
- **Entry:** 1–2 days pre-event, IV-rank<45, atr_pct compressed; buy ATM straddle.
- **Exit:** Immediately post-print on realized move (beat IV crush).
- **Indicators/params:** event calendar, IV-rank, atr_pct.
- **Regime/seasonality fit:** Macro-event clusters.
- **Source:** event-vol desk practice.
- **Genome-mappable:** partial (atr_pct/event timing TA; IV + gamma payoff).

### G2. Post-Event IV-Crush Short (vol mean-revert)
- **Family:** Event vol | **Timeframe:** hours–day after event
- **Core logic:** IV collapses after the catalyst; sell elevated premium once event passes.
- **Entry:** Immediately after event, IV-rank>80 and price stabilizing (atr_pct falling).
- **Exit:** IV normalizes / 35% credit.
- **Indicators/params:** IV-rank, atr_pct, event flag.
- **Regime/seasonality fit:** Post-catalyst vol drop.
- **Source:** earnings-style vol crush adapted.
- **Genome-mappable:** no.

### G3. Bitcoin-Halving Long-Vol Lead
- **Family:** Event/seasonal vol | **Timeframe:** weeks around halving
- **Core logic:** Halving windows historically precede vol expansion; own long-dated gamma.
- **Entry:** Buy long-dated strangle weeks ahead while IV subdued.
- **Exit:** On expansion / vol spike.
- **Indicators/params:** halving calendar, IV term.
- **Regime/seasonality fit:** Halving cycle.
- **Source:** crypto seasonality; Deribit.
- **Genome-mappable:** partial (calendar trigger; vol payoff).

### G4. Monthly/Quarterly Expiry Max-Pain Fade
- **Family:** OI structured | **Timeframe:** into Deribit expiry (Fri 08:00 UTC)
- **Core logic:** Spot gravitates toward max-pain (max-OI) strike near large expiries; fade deviations.
- **Entry:** Within 1–2 days of expiry, fade price away from max-pain toward it.
- **Exit:** Pin / expiry.
- **Indicators/params:** OI by strike, max-pain calc.
- **Regime/seasonality fit:** Large-OI expiries.
- **Source:** max-pain studies; Deribit OI.
- **Genome-mappable:** no.

### G5. OI-Bracket Range (high-OI strikes as S/R)
- **Family:** OI structured | **Timeframe:** weekly
- **Core logic:** Largest call-OI strike = resistance, largest put-OI = support; range-trade between.
- **Entry:** Sell condor inside the OI bracket; or fade toward edges.
- **Exit:** Bracket break / expiry.
- **Indicators/params:** OI distribution, strikes.
- **Regime/seasonality fit:** Concentrated-OI weeks.
- **Source:** options OI mapping.
- **Genome-mappable:** no.

### G6. Put/Call-Ratio (PCR) Contrarian → Options Directional
- **Family:** Sentiment | **Timeframe:** days
- **Core logic:** Extreme PCR signals capitulation/euphoria; fade with directional options.
- **Entry:** PCR>extreme high (fear) + price>EMA200 → buy calls; PCR extreme low + weakness → buy puts.
- **Exit:** PCR normalizes / target.
- **Indicators/params:** options PCR, EMA(200).
- **Regime/seasonality fit:** Sentiment extremes.
- **Source:** PCR contrarian studies.
- **Genome-mappable:** no (PCR/OI-driven; EMA secondary).

### G7. Expiry-Pin Iron Butterfly at Max-Pain
- **Family:** OI structured income | **Timeframe:** into expiry
- **Core logic:** Center an iron fly on the max-pain strike to harvest pin decay.
- **Entry:** 1–2 days pre-expiry, IV-rank>50, max-pain near spot.
- **Exit:** Close before gamma whips into settlement.
- **Indicators/params:** max-pain, IV-rank.
- **Regime/seasonality fit:** Pinning expiries.
- **Source:** max-pain + iron fly.
- **Genome-mappable:** no.

### G8. Block-Flow Follow (whale options print)
- **Family:** Orderflow | **Timeframe:** days
- **Core logic:** Large Deribit/Paradigm block trades signal informed positioning; align directional options.
- **Entry:** Large bullish call block + price>EMA50 → join with calls.
- **Exit:** Thesis/level.
- **Indicators/params:** block-flow feed, EMA(50).
- **Regime/seasonality fit:** Informed-flow regimes.
- **Source:** Paradigm/Deribit block-trade feeds.
- **Genome-mappable:** no.

---

## FAMILY H — Tail / structured / portfolio overlays

### H1. Tail-Risk Hedge (cheap deep-OTM puts, rolled)
- **Family:** Tail hedge | **Timeframe:** monthly roll
- **Core logic:** Persistent small allocation to far-OTM puts for crash convexity (Taleb-style).
- **Entry:** Buy 5–10Δ puts each month; size as % of book.
- **Exit:** Monetize spikes; roll otherwise.
- **Indicators/params:** 5–10Δ strikes, skew, vega.
- **Regime/seasonality fit:** Always-on insurance.
- **Source:** Universa-style tail hedging.
- **Genome-mappable:** no (skew/cost-driven).

### H2. Crash-Convexity Put Spread (financed tail)
- **Family:** Tail hedge | **Timeframe:** monthly
- **Core logic:** Buy near-OTM put, sell far-OTM put to cheapen crash protection.
- **Entry:** When put skew rich (sell the rich tail) and regime weakening.
- **Exit:** Monetize on selloff.
- **Indicators/params:** put skew, EMA(200).
- **Regime/seasonality fit:** Pre-stress.
- **Source:** financed-tail structures.
- **Genome-mappable:** no.

### H3. VRP Overlay on Spot Book (systematic short strangle sleeve)
- **Family:** Portfolio overlay | **Timeframe:** weekly
- **Core logic:** Run a sized short-strangle sleeve to harvest VRP on top of a long spot core, scaling by IV-rank.
- **Entry:** Each week scale short-vol exposure by IV-rank (more when rich).
- **Exit:** 50% credit / vol-spike stop.
- **Indicators/params:** IV-rank scaler, position sizing.
- **Regime/seasonality fit:** Persistent positive VRP.
- **Source:** systematic VRP overlay.
- **Genome-mappable:** no.

### H4. Vol-Targeted Option Sizing Overlay
- **Family:** Risk overlay | **Timeframe:** any
- **Core logic:** Scale option notional inversely to realized vol so vega/gamma risk per trade is constant.
- **Entry:** Any base options signal; size = risk$ / (vega×IV or gamma×ATR²).
- **Exit:** Base exit.
- **Indicators/params:** atr_pct, vol, greeks.
- **Regime/seasonality fit:** All; risk normalization.
- **Source:** vol-targeting; Turtle N-sizing adapted.
- **Genome-mappable:** partial (atr_pct/vol sizing TA; greek inputs needed).

### H5. Synthetic Covered Call via Short Put (wheel)
- **Family:** Income overlay | **Timeframe:** weekly cycle
- **Core logic:** The wheel — sell cash-secured puts, take assignment, then sell covered calls; loop.
- **Entry:** Sell 30Δ put in uptrend (price>EMA50); on assignment sell 30Δ call.
- **Exit:** 50% credit per leg; loop.
- **Indicators/params:** EMA(50), 30Δ strikes, IV-rank.
- **Regime/seasonality fit:** Sideways-up, elevated IV.
- **Source:** tastytrade wheel; Deribit.
- **Genome-mappable:** partial (EMA trend gate; income edge vega/theta).

### H6. Ladder / Strip / Strap (volatility with directional tilt)
- **Family:** Long vol directional | **Timeframe:** weekly
- **Core logic:** Strap = 2 calls + 1 put (bullish vol); strip = 2 puts + 1 call (bearish vol).
- **Entry:** Expect big move with bias (EMA slope) + cheap IV.
- **Exit:** On expansion.
- **Indicators/params:** EMA slope, IV-rank.
- **Regime/seasonality fit:** Biased breakout expected.
- **Source:** classic strip/strap; Deribit.
- **Genome-mappable:** partial (TA bias; gamma/vega payoff).

### H7. Ratio-Diagonal Income (term + skew harvest)
- **Family:** Vol arb income | **Timeframe:** monthly
- **Core logic:** Combine diagonal with a ratio to harvest both term decay and skew.
- **Entry:** Favorable term + rich skew side; build defined-risk variant.
- **Exit:** Front roll / skew normalize.
- **Indicators/params:** term slope, skew, greeks.
- **Regime/seasonality fit:** Term + skew edge.
- **Source:** market-maker structures.
- **Genome-mappable:** no.

### H8. Regime-Switched Vol Engine (TA-gated long/short vol)
- **Family:** Composite overlay | **Timeframe:** daily
- **Core logic:** Use atr_pct percentile to switch between long-vol (low-vol regime, expect expansion) and short-vol (high-vol regime, expect contraction) option modules.
- **Entry:** atr_pct percentile<25 → long straddle module; >75 → short strangle module (with IV-rank confirm).
- **Exit:** Per active module.
- **Indicators/params:** atr_pct percentile, IV-rank gate.
- **Regime/seasonality fit:** Adaptive across vol regimes.
- **Source:** regime-switching vol; volatility-cone.
- **Genome-mappable:** partial (atr_pct percentile gate is TA; module payoffs are vol/greek-driven, IV-rank confirm needed).

---

**Total templates: 88**
Family breakdown — A directional single-leg (15), B verticals/ratios (10), C neutral income (10), D long vol (9), E advanced vol arb/arb (20), F crypto-native funding/perp-vol (8), G event/expiry/OI (8), H tail/structured/overlays (8). Mappability split — **yes: 9** (pure TA-triggered single-leg & breakout/momentum/reversion option buys A1–A6, A11–A13 where an EMA/Donchian/momentum/zscore rule fully drives entry/exit), **partial: 26** (TA picks bias/timing but strike/sizing/regime gating needs IV-rank, greeks, atr-band, or term structure — A7–A10, A14, B1–B4, B7–B8, B10, D1–D2, D5, D7–D9, F6, G1, G3, H4–H6, H8), **no: 53** (edge is structurally vega/theta/gamma/skew/term-structure/OI/funding/parity-driven — all of C, the vol-arb/skew/dispersion/variance/surface set in E, crypto-native funding/perp-vol carry in F, OI/max-pain/sentiment/block-flow in G, and tail/structured income in H). Greeks via fast-vollib/Black-76, funding/basis via ccxt, DVOL/skew/term-structure from the Deribit chain are the first-class inputs needed to lift the "partial" and "no" rows.
