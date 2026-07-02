# NSE Options Strategy Templates — Curated Library
Index (NIFTY/BANKNIFTY/FINNIFTY) + stock options. Single-leg directional AND multi-leg structures. Each row: name | family/legs | logic | entry (incl IV/regime) | exit/adjust | greeks focus | timeframe/expiry | regime fit | source | genome-mappable.
**Total strategies: 126.** Genome key — a strategy is *genome-mappable: yes* if a pure TA-feature genome (price/indicator triggers) fully drives entry/exit; *partial* if it also needs IV-rank/greeks/OI overlays; *no* if its edge is structurally vol/greek/OI-driven and TA is at most secondary. Greeks computable in-repo via fast-vollib / Black-76.

---

## A. Directional Single-Leg (TA-triggered)

1. **Long Call – Trend Breakout** | single long ATM/ITM call | buy directional upside with defined risk = premium | EMA(20)>EMA(50) crossover + price breaks prior-day high, IV-rank < 50 (avoid overpaying vega) | SL = 30–40% premium or close < EMA20; target 2R or trail | long delta, long gamma, short theta, long vega | intraday–weekly expiry | trending up, low/mid IV | Zerodha Varsity Option Strategies module | **yes** (TA fully drives; IV filter is light overlay)
2. **Long Put – Trend Breakdown** | single long ATM/ITM put | downside with capped risk | EMA20<EMA50 + break of prior-day low + RSI<40, IV-rank<50 | SL 30–40% prem or close>EMA20; trail to target | short delta, long gamma, long vega | intraday–weekly | trending down, low/mid IV | Varsity | **yes**
3. **Long Call – Pullback to Moving Average** | single long ITM call (delta ~0.6) | buy dip in uptrend | price pulls to rising 20-EMA + bullish reversal candle, IV-rank<60 | SL below swing low; target prior high | delta+, gamma+ | intraday–weekly | trending up, mid IV | tastytrade / Varsity | **yes**
4. **Long Put – Pullback to Resistance** | single long ITM put | sell rally in downtrend | price rallies to falling 20-EMA + bearish rejection | SL above swing high | delta−, gamma+ | intraday–weekly | trending down | Varsity | **yes**
5. **Long Call – Opening Range Breakout (ORB)** | single ATM call (weekly) | capture intraday momentum | price closes above 15-min opening range high + volume surge | SL = ORB low; square-off by EOD | gamma+, theta− (intraday minimizes theta) | intraday weekly expiry | trending intraday | icfmindia / AlgoTest expiry guide | **yes**
6. **Long Put – Opening Range Breakdown** | single ATM put | intraday momentum short | break below ORB low + volume | SL = ORB high; EOD square-off | gamma+ | intraday weekly | trending intraday | AlgoTest | **yes**
7. **Long Call – VWAP Reclaim** | single ATM/OTM call | momentum continuation | price reclaims VWAP after dip + higher-low | SL below VWAP; target session high | delta+, gamma+ | intraday | trending/mean-revert intraday | stockgro intraday guide | **yes**
8. **Long Put – VWAP Rejection** | single ATM/OTM put | short failed VWAP test | price fails at VWAP from below | SL above VWAP | delta− | intraday | intraday down | stockgro | **yes**
9. **Long Call – Supertrend Flip** | single ITM call | ride confirmed trend flip | Supertrend(10,3) flips green | SL = flip price; exit on opposite flip | delta+, gamma+ | weekly–monthly | trending | Varsity / community | **yes**
10. **Long Put – Supertrend Flip Down** | single ITM put | ride down-flip | Supertrend flips red | exit on green flip | delta− | weekly–monthly | trending down | Varsity | **yes**
11. **Long Call – Bollinger Squeeze Expansion** | single ATM call | trade volatility expansion upside | BB width at 6-month low then upside breakout, IV-rank low (cheap premium) | SL on re-entry into band; trail | gamma+, vega+ | weekly | low→high vol transition, breakout | optionstradingiq | **partial** (needs BB-width feature + IV-rank for cheap-vega timing)
12. **Long Put – Bollinger Squeeze Down** | single ATM put | vol-expansion downside | squeeze + downside breakout | as above | gamma+, vega+ | weekly | breakout down | optionstradingiq | **partial**
13. **Long Call – Gap-and-Go** | single ATM call | trade gap-up continuation | gap-up > prior high holds first 15-min | SL = gap fill; EOD exit | gamma+ | intraday weekly | momentum | community/Angel One | **yes**
14. **Long Put – Gap-Down Continuation** | single ATM put | gap-down follow-through | gap below prior low holds | SL = gap fill | gamma+ | intraday weekly | momentum | Angel One | **yes**
15. **Long Call – Stock Options Momentum (high-beta stock)** | single ITM stock call | leverage stock breakout | stock breaks 52-wk high consolidation + sector strength, IV-rank<50 | SL below base; trail | delta+ | weekly–monthly | trending stock | Varsity | **yes**

## B. Credit / Debit Vertical Spreads

16. **Bull Call Spread (debit)** | long lower-strike call + short higher-strike call | cheap defined-risk bullish | mild-bullish bias, IV-rank low-mid (debit benefits from rising IV) | exit at 50–70% max profit; SL 1.5× debit | net delta+, reduced vega/theta vs naked | weekly–monthly | mild uptrend, low IV | Varsity / OptionStrat | **partial** (TA gives bias; strike width needs IV)
17. **Bear Put Spread (debit)** | long higher-strike put + short lower-strike put | cheap defined-risk bearish | mild-bearish, low-mid IV | 50–70% profit; SL 1.5× debit | net delta−, lower vega | weekly–monthly | mild downtrend, low IV | Varsity / OptionStrat | **partial**
18. **Bull Put Spread (credit)** | short higher-strike put + long lower-strike put | collect premium, bullish/neutral | IV-rank > 40, price above support, sell put below support | exit 50% max profit; roll/close if short strike breached (delta ~30 → 50) | net delta+, theta+, vega− | weekly–monthly | range/up, high IV | tastytrade | **partial** (needs IV-rank + delta strike pick)
19. **Bear Call Spread (credit)** | short lower-strike call + long higher-strike call | collect premium, bearish/neutral | IV-rank>40, price below resistance, sell call above resistance | 50% profit; roll if breached | delta−, theta+, vega− | weekly–monthly | range/down, high IV | tastytrade | **partial**
20. **Bull Call Spread – Wide (directional swing)** | debit vertical, wide strikes | higher payoff trend trade | strong uptrend + retest, IV low | trail to short strike | delta+ | monthly | trending up | OptionStrat | **partial**
21. **Bear Put Spread – Wide** | wide debit put vertical | trend short | strong downtrend retest | trail | delta− | monthly | trending down | OptionStrat | **partial**
22. **Short Put Vertical at Support (OI)** | bull put credit spread anchored to high put-OI strike | sell below OI-support wall | high Put-OI strike acts as support, IV-rank>40 | close 50%; defend if OI wall breaks | theta+, vega−, delta+ | weekly | range/support hold | niftytrader OI / tastytrade | **no** (OI-anchored strike selection)
23. **Short Call Vertical at Resistance (OI)** | bear call credit spread at high call-OI strike | sell below resistance wall | high Call-OI strike = resistance | close 50%; defend on breach | theta+, delta− | weekly | range/resistance | marketseasy OI guide | **no** (OI-driven)
24. **Poor Man's Covered Call (diagonal debit)** | long deep-ITM LEAPS-style call + short near OTM call | capital-efficient covered call | bullish, low IV to buy long leg | roll short call monthly; exit if long delta collapses | delta+, theta+ (from short), vega mixed | monthly+/weekly short | mild up | OptionStrat / tastytrade | **partial**
25. **Poor Man's Covered Put** | long deep-ITM put + short near OTM put | capital-efficient bearish income | bearish | roll short put | delta−, theta+ | monthly | mild down | OptionStrat | **partial**

## C. Straddles & Strangles

26. **Long Straddle (ATM)** | long ATM call + long ATM put | profit from big move either way | IV-rank LOW (cheap), pre-event/squeeze expecting expansion | exit on vol pop or 50% gain; theta-stop if flat | long gamma, long vega, short theta, delta~0 | weekly–event | low IV → expansion expected | Varsity / OptionStrat | **partial** (IV-rank entry; TA for timing)
27. **Long Strangle (OTM)** | long OTM call + long OTM put | cheaper big-move bet | low IV, expected breakout, BB squeeze | 50% gain or vol-pop exit | gamma+, vega+, theta− | weekly–event | low IV, breakout pending | Varsity | **partial**
28. **Short Straddle (ATM)** | short ATM call + short ATM put | sell premium, expect pin | IV-rank HIGH (>50), range-bound, no event | close 25–50% profit; SL at 1.5–2× credit or delta breach; convert to IC if tested | theta+, vega−, delta~0, short gamma | weekly | high IV, range | tastytrade | **no** (vega/theta-driven, needs IV-rank) 
29. **Short Strangle (OTM)** | short ~16-delta call + short ~16-delta put | wide range premium sell | IV-rank>50, range, ~45 DTE classic | 50% profit; manage tested side at 2× / 21 DTE | theta+, vega−, short gamma | weekly–monthly | high IV, range | tastytrade research | **no**
30. **Short Strangle – Delta-Balanced (intraday)** | short OTM call+put weekly | expiry-week theta harvest | high IV-rank, low ADX (range), no event-day | square-off EOD or 30% profit; SL per leg | theta+, gamma− | intraday weekly | range, high IV | Traders Gurukul / AlgoTest | **partial** (ADX range filter + IV)
31. **Strap (2 calls + 1 put straddle)** | long 2 ATM calls + 1 ATM put | bullish volatility | expect big move, upside-biased, low IV | scale out on move | gamma+, vega+, delta+ | event/weekly | low IV, vol+up bias | OptionStrat (strips/straps) | **partial**
32. **Strip (1 call + 2 puts)** | long 1 ATM call + 2 ATM puts | bearish volatility | big move expected, downside bias, low IV | scale out | gamma+, vega+, delta− | event/weekly | low IV, vol+down bias | OptionStrat | **partial**
33. **Long Guts** | long ITM call + long ITM put | strangle with ITM strikes, deep vol bet | very low IV, large move expected | exit on expansion | gamma+, vega+ | event | low IV | OptionStrat (guts) | **partial**
34. **Short Guts** | short ITM call + short ITM put | premium-rich neutral sell | high IV, strong range conviction | close on decay | theta+, vega− | weekly | high IV range | OptionStrat | **no**
35. **Reverse (Long) Iron Butterfly** | long ATM straddle + short OTM strangle wings (debit) | defined-risk long-vol | low IV, expecting breakout | 50% gain | gamma+, vega+ | weekly–event | low IV | Option Alpha | **partial**

## D. Iron Condor / Iron Butterfly

36. **Iron Condor (standard)** | short OTM put spread + short OTM call spread | defined-risk range income | IV-rank>50, range-bound, ~16-delta shorts, 45 DTE | close 50% profit; manage tested side at 2×/21DTE; roll untested in | theta+, vega−, delta~0 | weekly–monthly | high IV, range | Zerodha Varsity Iron Condor / tastytrade | **no** (IV+delta strike driven)
37. **Iron Condor – Weekly Expiry Income** | tight short wings weekly | fast theta on weekly | high IV-rank, range, no event mid-week | close 50% or EOD-expiry pin | theta+ | weekly | range | AlgoTest expiry | **partial** (range/ADX TA + IV)
38. **Iron Butterfly (ATM)** | short ATM straddle + long OTM wings | max theta at pin point | IV-rank high, strong pin expectation | close 25% profit (high credit); SL on break | theta+ (high), vega−, short gamma | weekly | high IV, tight range | OptionStrat / Varsity | **no**
39. **Reverse Iron Condor (debit)** | long inner spreads, short outer = net long vol | defined-risk breakout | low IV, breakout expected, squeeze | exit on move or 50% | gamma+, vega+ | weekly–event | low IV, breakout | Option Alpha Reverse IC | **partial**
40. **Broken-Wing Iron Condor** | IC with one side's wing wider (no-risk side) | shift risk to one direction | mild directional bias + range, high IV | close 50% | theta+, slight delta tilt | weekly–monthly | high IV, biased range | optionstrat | **no**
41. **Unbalanced Iron Condor (ratio'd)** | extra contracts on lower-prob side | skew payoff to expected zone | directional lean + range, high IV | manage at 50% | theta+, delta tilt | monthly | high IV biased | tastytrade | **no**
42. **Double Calendar (condor cousin)** | long far + short near calls AND puts OTM | range income with vega+ | low-mid IV, range, want vega long | close on IV pop / 25% | theta+ (near), vega+, delta~0 | weekly/monthly legs | range, rising-IV expected | OptionStrat double diagonal/calendar | **partial**
43. **Iron Condor – IV-Rank Gated** | standard IC only when IV-rank>50 | systematic premium harvest | IV-rank/IV-percentile > 50 + range | mechanical 50% / 21DTE | theta+, vega− | monthly | high IV | tastytrade IV-rank research | **no**

## E. Ratio Spreads & Backspreads

44. **Call Ratio Spread (1×2)** | long 1 ATM call + short 2 OTM calls | finance upside, profit zone at short strike | mild-bull but capped, high IV (short extra vega) | close before short strikes breach; SL above upper breakeven | theta+, vega−, short gamma above | monthly | mild up, high IV | tastytrade ratio | **no** (greek/IV structural)
45. **Put Ratio Spread (1×2)** | long 1 ATM put + short 2 OTM puts | mild-bear with cushion | mild-bear, high IV | manage if breaks lower BE | theta+, vega− | monthly | mild down, high IV | tastytrade | **no**
46. **Call Ratio Backspread (2×1)** | short 1 ITM/ATM call + long 2 OTM calls | net long gamma upside, often credit | expect explosive upside, IV low-mid | profit on big move; lose in stall zone | gamma+, vega+, delta+ | monthly/event | breakout up, low IV | OptionStrat backspread | **partial** (TA breakout + IV)
47. **Put Ratio Backspread (2×1)** | short 1 ATM put + long 2 OTM puts | long-gamma downside crash bet | expect sharp drop, low-mid IV | profit on crash | gamma+, vega+, delta− | monthly/event | crash/breakout down | OptionStrat | **partial**
48. **Front-Ratio Call (credit ratio)** | short more calls than long, net credit | neutral-bear premium | high IV, range/down | close 50%; defend upper | theta+, vega− | monthly | high IV, neutral-bear | tastytrade | **no**
49. **Ratio'd Bull Call (1×3 lottery)** | long 1 + short 3 far OTM | very cheap/credit upside to target | strong target zone, high IV | exit at target zone | theta+ | monthly | defined up move | community | **no**
50. **Christmas Tree Butterfly (call)** | 1×3×2 asymmetric butterfly | skewed range profit | directional-range bias, mid-high IV | close 50% | theta+ | monthly | biased range | optionstradingiq | **no**
51. **Lizard / Ratio Hybrid (intraday weekly)** | short straddle + extra OTM short on trend side | tilt theta toward expected drift | high IV weekly, mild drift | EOD/50% | theta+ | weekly | high IV biased | community / AlgoTest | **partial**

## F. Calendar & Diagonal Spreads

52. **Call Calendar (horizontal)** | short near-expiry call + long far call, same strike | sell fast theta, own slow theta | low-mid IV-rank (term structure normal), price near strike, range | close on IV pop / 20–30%; roll short | theta+ (net), vega+ (long-dated) | dual expiry | range, rising-IV expected | OptionStrat / Varsity | **partial**
53. **Put Calendar** | short near put + long far put same strike | downside-leaning theta+vega | range near strike, low IV | roll short, exit on pop | theta+, vega+ | dual expiry | range/mild-down | OptionStrat | **partial**
54. **Call Diagonal (bullish)** | short near OTM call + long far higher-delta call | directional + theta | mild-bull, low-mid IV | roll short up/out; exit if trend breaks | delta+, theta+, vega+ | dual expiry | mild uptrend | OptionStrat | **partial**
55. **Put Diagonal (bearish)** | short near OTM put + long far ITM put | bearish + theta | mild-bear | roll short down/out | delta−, theta+ | dual expiry | mild down | OptionStrat | **partial**
56. **Double Diagonal** | diagonal calls + diagonal puts | range income, long vega | range, low-mid IV, want vega long into event | close 25% / IV pop | theta+, vega+, delta~0 | dual expiry | range, rising IV | OptionStrat double diagonal | **no**
57. **Calendar at OI Max-Pain Strike** | calendar centered on max-pain/high-OI strike | pin-toward-maxpain theta | near expiry, max-pain cluster, range | close at expiry pin | theta+ | weekly+monthly | range pin | niftytrader OI | **no** (OI/max-pain anchored)
58. **Reverse Calendar (short cal)** | long near + short far, same strike | profit from IV crush / term flattening | high IV-rank, expecting near-term vol collapse | exit post-crush | vega−, theta− | dual expiry | high IV, vol-collapse expected | tastytrade | **no**
59. **Diagonal Roll-Down Repair** | adjustment template: roll tested diagonal | salvage losing directional | short leg ITM → roll out/down | continue or close | delta-managed | dual expiry | any | tastytrade management | **no**

## G. Covered Call / Protective / Collar (stock + option)

60. **Covered Call (OTM)** | long stock/futures + short OTM call | income on holdings | own underlying, neutral-bull, IV-rank>40 | buy back at 50%; roll up/out near expiry | delta+ (reduced), theta+, vega− | monthly | sideways-up, high IV | QuantConnect Covered Call / Varsity | **partial** (TA picks strike; needs holding + IV)
61. **Covered Call (ATM, max income)** | long stock + short ATM call | max premium, cap upside | very neutral, high IV | roll if breached | theta+ | monthly | flat, high IV | QuantConnect | **partial**
62. **Covered Put** | short stock/futures + short OTM put | income on short position | bearish-neutral, high IV | roll down/out | delta−, theta+ | monthly | flat-down | QuantConnect Covered Put | **partial**
63. **Protective Put (married put)** | long stock + long OTM put | insure downside | hold stock, hedge tail/event, low IV to buy cheap | exit put on stop or roll | delta+ (hedged), long vega | event/monthly | hedging | QuantConnect Protective Put | **partial**
64. **Protective Call** | short stock + long OTM call | cap short-side risk | hedge short | roll | delta−, long vega | monthly | hedging short | QuantConnect Protective Call | **partial**
65. **Collar (zero-cost)** | long stock + long put + short call (put funded by call) | bracketed protection | hold stock into uncertainty, want cheap hedge | adjust strikes / roll | delta+ (capped), low net vega | monthly–quarterly | hedging, range-up | QuantConnect Protective Collar | **partial**
66. **Collar – Skew-Funded** | collar exploiting put-call skew to get net credit | finance protection via rich put skew | high put-skew regime | roll on skew change | vega/skew aware | monthly | hedging, high skew | tastytrade skew | **no** (skew-driven)
67. **Covered Strangle** | long stock + short OTM call + short OTM put | aggressive income, add on dip | bullish-neutral, high IV, willing to add | manage put side | theta+, delta+ | monthly | up-range, high IV | OptionStrat covered short straddle | **partial**
68. **Cash-Secured Put (wheel entry)** | short OTM put, cash-backed | get paid to buy at discount | want to own underlying lower, IV-rank>40 | take 50% or accept assignment → covered call | theta+, vega−, delta+ | monthly | neutral-bull, high IV | tastytrade wheel | **partial**
69. **The Wheel (CSP → CC cycle)** | CSP, if assigned sell covered call, repeat | continuous premium income | range/mild-up name, persistent high IV | mechanical 50% rolls | theta+ | monthly cycle | high IV, range-up | tastytrade | **partial**

## H. Butterflies

70. **Long Call Butterfly (ATM)** | +1/−2/+1 calls | cheap pin bet at center | strong pin/target expectation, high IV (cheap to buy) | exit near expiry at center / 50% | theta+ near center, short gamma | weekly–monthly | range/pin, high IV | OptionStrat | **partial** (target zone TA + IV)
71. **Long Put Butterfly** | +1/−2/+1 puts | pin bet, put strikes | pin target below | as above | theta+ | weekly | pin | OptionStrat | **partial**
72. **Broken-Wing Call Butterfly** | asymmetric wings, often credit, no downside risk | directional-pin with no-risk side | mild-bull-to-target, high IV | close 50%; let no-risk side ride | theta+, slight delta+ | weekly–monthly | biased range | OptionStrat broken wing | **no**
73. **Broken-Wing Put Butterfly (21-DTE income)** | put BWB, net credit, ~21 DTE | mechanical income with skew | enter ~21 DTE, IV mid-high, place below price | mechanical close at profit/loss thresholds | theta+, vega−, skew | ~3 wk | range/down-drift | Data Driven Options BWB | **no**
74. **Iron Butterfly vs Butterfly (defined)** | see #38 / debit variant | center-pin | high IV (iron) / low IV (long debit) | 25–50% | theta+ | weekly | pin | OptionStrat | **no**
75. **Skip-Strike Butterfly** | wings skipped one strike out | wider profit tent | range, target zone | 50% | theta+ | monthly | range | optionstradingiq | **no**
76. **Double Butterfly (two flies)** | flies at two target zones | bimodal pin | expect settle at one of two zones | manage zones | theta+ | monthly | range, two magnets | OptionStrat | **no**
77. **Calendarized Butterfly** | butterfly with different expiries | add vega to fly | range + want vega | manage | theta+, vega+ | dual expiry | range | OptionStrat | **no**

## I. Jade Lizard & Exotic Credit

78. **Jade Lizard** | short put + short call spread, credit > call-spread width | neutral-bull, NO upside risk | IV-rank HIGH, neutral-bullish, below resistance | close 50% (tastytrade); defend put side | theta+, vega−, delta+ | monthly | high IV, neutral-up | tastytrade Jade Lizard | **no** (credit-width rule, IV-rank)
79. **Reverse Jade Lizard** | short call + short put spread, no downside risk | neutral-bear | IV-rank high, neutral-bearish | close 50% | theta+, vega−, delta− | monthly | high IV, neutral-down | tastytrade | **no**
80. **Big Lizard** | short ATM straddle + long OTM call (no upside risk) | max premium neutral, hedge upside | very high IV, range | 25% profit | theta+ (high), vega− | weekly–monthly | high IV range | tastytrade | **no**
81. **Twisted Sister** | short ATM straddle + long OTM put (no downside risk) | mirror big lizard | high IV, range, downside-hedge | 25% | theta+, vega− | monthly | high IV | tastytrade | **no**
82. **Zebra (Zero Extrinsic Back Ratio)** | 2 ITM long − 1 ATM short (call or put), ~zero extrinsic | stock replacement, full delta, defined risk | directional, want delta~100 cheaply | trail as stock proxy | delta~1, low theta bleed | monthly | trending | tastytrade Zebra | **partial**

## J. Delta-Neutral / Gamma Scalping

83. **Long Gamma Scalp** | long ATM straddle + dynamic delta hedge in futures | profit when realized vol > implied | IV cheap vs expected realized, event/expansion | hedge deltas at bands; exit on IV pop | gamma+, vega+, theta− (paid) | intraday–weekly | realized>implied, choppy-trend | Schwab / SteadyOptions gamma scalp | **no** (continuous greek hedging)
84. **Short Gamma Theta Harvest** | short straddle/strangle + delta hedge | collect theta when realized < implied | high IV, expect calm | hedge tail; stop on vol spike | theta+, short gamma, vega− | intraday–weekly | realized<implied, range | tastytrade / MenthorQ | **no**
85. **Delta-Neutral Calendar Scalp** | calendar + hedge underlying delta | vega+theta neutralized of direction | range, rising-IV view | rebalance delta | vega+, theta+, delta~0 | dual expiry | range | MenthorQ gamma/delta guide | **no**
86. **Dynamic Delta Hedge (DDH) overlay** | any options book + futures hedge to flatten delta | risk-management template | net delta exceeds band | rehedge at thresholds | delta~0 | continuous | any | Lean/QuantConnect | **no**
87. **Pin-Risk Expiry Gamma Trade** | short ATM near expiry, scalp gamma intraday | exploit decay vs pin | expiry day, range, high IV | EOD square-off | theta+ huge, short gamma risk | expiry intraday | range pin | AlgoTest expiry | **partial** (range TA + expiry timing)

## K. Theta-Decay / Expiry-Day Income

88. **Expiry-Day Short Straddle** | short ATM straddle on expiry morning | harvest terminal theta | expiry day, low ADX/range open, high IV | trail SL; EOD square-off | theta+ (max), short gamma | expiry intraday | range expiry | AlgoTest / Angel One | **partial** (range filter)
89. **Expiry-Day Short Strangle** | short OTM call+put expiry | safer terminal theta | expiry, range, OI walls bracketing | 30% / EOD; defend breached | theta+ | expiry intraday | range | Traders Gurukul | **partial**
90. **Expiry Iron Fly (defined)** | iron butterfly on expiry day | defined-risk terminal theta | expiry, range | EOD pin | theta+ | expiry | range | AlgoTest | **partial**
91. **Sell-the-Wing OTM (far)** | short far-OTM call+put weekly | low-prob premium harvest | high IV, strikes beyond expected move (1SD) | 50% / 21–0 DTE | theta+, vega− | weekly | range, high IV | tastytrade 1SD | **no**
92. **Theta Ladder (staggered shorts)** | sell premium across multiple expiries | smooth theta income | persistent high IV-rank | mechanical rolls | theta+ | multi-expiry | high IV | tastytrade | **no**
93. **0DTE Short Premium (index)** | 0DTE short spread/strangle | intraday theta | expiry day, defined range, OI bracket | hard SL, EOD | theta+, gamma risk | 0DTE | range | AlgoTest / community | **partial**
94. **9:20 Straddle (popular Indian template)** | short ATM straddle entered 9:20 AM | systematic intraday theta | weekly/expiry, range bias, mechanical | SL per leg / 30%, EOD | theta+ | intraday | range | AlgoTest blog | **partial**
95. **Range-Bound IC Income (mechanical)** | weekly IC every cycle | systematic theta | low ADX + IV-rank>50 | 50% / 21DTE | theta+ | weekly | range | tastytrade | **no**
96. **Premium Decay into Event-Pass** | short premium AFTER event (post-crush calm) | sell once vol-event resolved | post-event, IV still elevated, range | close 50% | theta+, vega− | weekly | post-event range | tastytrade | **no**
97. **Last-Hour Theta Sell** | short ATM options final trading hour | capture end-of-day decay | low-vol afternoon, range | EOD square-off | theta+, gamma risk | intraday | afternoon range | AlgoTest | **partial**

## L. Volatility (IV-Rank / IV-Percentile gated)

98. **High IV-Rank Premium Sell (engine)** | sell strangle/IC when IV-rank>50 | systematic mean-reversion of vol | IV-rank or IV-percentile > 50 | close 50% / 21DTE | vega−, theta+ | monthly | high IV | tastytrade IV-rank research | **no** (vol-feature gated)
99. **Low IV-Rank Premium Buy** | buy straddle/strangle when IV-rank<25 | long vol when cheap | IV-rank<25 + catalyst | exit on IV pop | vega+, gamma+ | event/weekly | low IV | tastytrade | **partial**
100. **IV Term-Structure Calendar** | calendar when front IV > back IV (backwardation) | sell rich front vol | term-structure inverted | exit on normalization | vega+ (net), theta+ | dual expiry | event-driven term skew | tastytrade | **no**
101. **VIX/India-VIX Regime Switch** | long premium when VIX rising, short when VIX high+falling | macro vol timing | India VIX percentile thresholds | switch on regime | vega-directional | weekly–monthly | regime transition | tastytrade / community | **partial** (VIX feature, not pure TA)
102. **Vol-Risk-Premium Harvest** | persistent short premium capturing IV>RV | structural edge | IV consistently > realized | mechanical | vega−, theta+ | monthly | high IV markets | tastytrade VRP | **no**
103. **IV Crush Calendar (pre-results)** | put calendar/diagonal before results to own back-vol | profit when front crushes | pre-earnings, normal term structure | exit post-result | vega+, theta+ | event | pre-event | tastytrade | **no**

## M. Skew Strategies

104. **Put-Skew Sell (rich downside vol)** | sell OTM put spread when put-skew steep | harvest fear premium | steep put skew, IV-rank high | close 50% | vega−, theta+, delta+ | monthly | high skew | tastytrade skew | **no**
105. **Risk Reversal (skew directional)** | short OTM put + long OTM call (or reverse) | directional via skew, ~zero cost | bullish + rich put skew | manage delta | delta+, vega/skew | monthly | trend + skew | tastytrade risk reversal | **partial**
106. **Skew Arbitrage Fly** | broken-wing fly exploiting strike skew | monetize skew shape | skew dislocation | close on normalization | skew/vega | monthly | skew dislocation | optionstradingiq | **no**
107. **Call-Skew Sell (post-rally)** | sell rich OTM call vol after spike | fade upside vol pop | call skew elevated | 50% | vega− | monthly | call-skew rich | tastytrade | **no**

## N. OI-Based Strategies

108. **OI Support/Resistance Range Fade** | sell strangle inside highest Put-OI (support) and Call-OI (resistance) | trade the OI bracket | clear OI walls, range, high IV | exit if wall OI shifts/breaks | theta+ | weekly | range, OI-bracketed | niftytrader OI / marketseasy | **no** (OI-driven)
109. **OI Buildup Breakout (long-buildup)** | buy option on price↑ + OI↑ (long buildup) | ride confirmed accumulation | price up + OI up + volume | SL on OI unwind | delta+, gamma+ | intraday–weekly | trending w/ OI | marketseasy OI | **partial** (price TA + OI feature)
110. **Short-Covering Squeeze** | buy call on price↑ + OI↓ | ride short covering | price up + OI falling | exit on OI flat | delta+ | intraday | squeeze up | marketseasy | **partial**
111. **Long-Unwinding Short** | buy put on price↓ + OI↓ | ride profit-booking exit | price down + OI down | exit on OI flat | delta− | intraday | unwind down | marketseasy | **partial**
112. **Max-Pain Pin Trade** | sell ATM straddle/IC centered on max-pain near expiry | price gravitates to max-pain | near expiry + max-pain cluster + range | close at expiry pin | theta+ | weekly expiry | range/pin | niftytrader max-pain | **no**
113. **OI Change Breakout Confirmation** | directional option + require OI delta confirm | filter false breakouts | breakout + fresh OI same direction | SL on OI fade | delta+ | intraday–weekly | trending | marketseasy | **partial**

## O. PCR-Based Strategies

114. **PCR Extreme Reversal (contrarian)** | buy puts when PCR>1.3 (over-bullish), buy calls when PCR<0.7 | fade sentiment extreme | PCR beyond threshold + price reversal candle | SL on continuation | delta directional | intraday–weekly | sentiment extreme | niftytrader / AlgoTest PCR | **partial** (PCR feature + TA confirm)
115. **PCR Trend Confirmation** | trade with PCR rising (bullish) + price up | momentum w/ sentiment | PCR trend aligns with price | exit on PCR divergence | delta+ | weekly | trending | niftytrader | **partial**
116. **PCR Bull-Put-Spread (high PCR support)** | sell put spread when PCR>1.3 (heavy put writing = support) | align with writers | PCR>1.3 + support hold | 50% | theta+, delta+ | weekly | bullish sentiment | niftytrader PCR | **partial**
117. **PCR Bear-Call-Spread (low PCR)** | sell call spread when PCR<0.7 | align with call writers | PCR<0.7 + resistance | 50% | theta+, delta− | weekly | bearish sentiment | niftytrader | **partial**

## P. Event / Earnings Vol-Crush

118. **Earnings IV-Crush Short Strangle** | short strangle just before results | profit from post-event IV collapse | IV-rank elevated pre-results, expected move priced rich | close morning after on crush | vega−, theta+ | event (1–2 days) | high pre-event IV | tastytrade earnings | **no**
119. **Earnings Iron Condor (defined crush)** | IC sized to expected move, pre-results | defined-risk vol-crush | pre-event IV high | close post-crush | vega−, theta+ | event | high IV | tastytrade | **no**
120. **Earnings Calendar (long back-vol)** | sell front (crushes) + own back month | monetize term-structure crush | pre-results, steep front IV | exit post-event | vega+, theta+ | event | pre-event | tastytrade | **no**
121. **Event Long Straddle (expansion play)** | long straddle before binary event if IV underpriced | profit if move > implied | low IV-rank vs expected move (rare), binary catalyst | exit on move/IV pop | gamma+, vega+ | event | underpriced IV | OptionStrat | **partial**
122. **Budget/Policy-Day Index Strangle Sell** | short index strangle around scheduled macro event | harvest elevated event IV | India-VIX spiked pre-event, range expected | close post-event crush | vega−, theta+ | event | high event IV | community / tastytrade | **no**

## Q. Synthetics & Misc Structures

123. **Synthetic Long (call − put same strike)** | long call + short put ATM | stock/futures replacement | bullish, want leverage/low capital | manage as future | delta~1, low theta | monthly | trending up | OptionStrat synthetics | **partial**
124. **Synthetic Short (put − call)** | long put + short call ATM | short replacement | bearish | manage | delta~−1 | monthly | trending down | OptionStrat | **partial**
125. **Conversion / Reversal (arb)** | synthetic + offsetting underlying to lock arb | capture put-call parity mispricing | parity violation (rare) | hold to expiry | delta~0 | to expiry | any (arb) | OptionStrat arbitrage | **no** (pricing arb)
126. **Box Spread (financing/arb)** | bull call + bear put spreads = locked payoff | rate/financing or parity arb | box value ≠ PV of width | hold to expiry | delta~0, no greeks net | to expiry | any | OptionStrat box | **no**

---

### Genome-mappability summary
- **yes (≈15):** pure single-leg directional templates (#1–10,13–15) — TA-feature genome drives entry/exit directly; greeks only for sizing.
- **partial (≈55):** verticals, calendars/diagonals, covered/collar, OI-confirmed directional, PCR-confirmed, IV-gated long-vol — TA picks bias/timing but strike selection and gating need IV-rank / India-VIX / greeks / OI features (all computable via fast-vollib + Black-76 + option-chain OI feed in repo).
- **no (≈56):** short-premium income (short straddle/strangle/IC/iron-fly), ratio/backspreads, jade-lizard family, gamma scalping & DDH, vol-risk-premium / skew / earnings vol-crush, max-pain/OI-bracket fades, arbitrage (box/conversion) — edge is structurally vega/theta/gamma/skew/OI/parity-driven; TA is secondary. These need IV-rank/IV-percentile, full greeks, term-structure, OI/max-pain, and skew as first-class genome inputs, not just TA features.
