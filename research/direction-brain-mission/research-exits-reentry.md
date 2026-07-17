# Exits, Stops, and Re-Entry: Published Evidence Review

Date: 2026-07-17 · READ-ONLY research task (no code changed)
Scope: evidence for the paper crypto-perp system — 15m–4h holds, 5x leverage, taker ~0.05%/side,
hard stop at −3% of stake (= **−0.6% in price at 5x**), ratchet trailing TP arming at +1% of stake
(= **+0.2% in price**), 30-min same-symbol-same-direction cooldown after stop-out.
Goal: maximize fraction of green closes AND keep expectancy ≥ 0.

Quality flags: [A] peer-reviewed/academic · [B] serious practitioner/quant blog with data ·
[C] practitioner content, methodology unverifiable — treat as hypothesis only.

---

## Q1 — Stop-loss placement: tight vs wide, MAE methodology, leverage/holding-period scaling

**1. [A] Stops only add value when returns have momentum; under a random walk they are pure cost.**
Kaminski & Lo, "When Do Stop-Loss Rules Stop Losses?" (J. Financial Markets 2014; SSRN 968338;
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338). Under the Random Walk Hypothesis simple
0/1 stop rules *always* lower expected return; with momentum or regime-switching they add value
(50–100 bps/mo in their equity/bond application).
→ *Applies:* our stop earns its keep only to the extent entries carry real short-horizon momentum.
With direction accuracy measured near 0.5 on much of our history, the stop's expected contribution
is negative (fee + whipsaw cost) until the entry edge itself is proven. Stop design cannot rescue a
coin-flip entry.

**2. [A] A stop sized at the scale of the strategy's own return distribution tames crashes and ~doubles Sharpe.**
Han, Zhou & Zhu, "Taming Momentum Crashes: A Simple Stop-Loss Strategy" (SSRN 2407199, 2016;
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2407199). A 10% *monthly* stop on US momentum
deciles (1926–2011) cut worst monthly loss from −49.8% to −11.4% and raised Sharpe 0.165→0.399.
Key detail: 10%/month is roughly one monthly sigma — the stop sits at the *edge* of normal
excursion, not inside it.
→ *Applies:* the published wins for stops come from stops placed at ~1σ of the holding-period move.
Our −0.6% price stop over a 15m–4h crypto hold is far *inside* 1σ for the longer holds (see #5) —
the regime where the same literature predicts stops destroy value.

**3. [B] MAE methodology: derive the stop from the adverse-excursion boundary separating winners from losers.**
John Sweeney, *Campaign Trading* (1996), summarized with modern examples by QuantifiedStrategies
(https://www.quantifiedstrategies.com/maximum-adverse-excursion-mae-maximum-favorable-excursion-mfe-explained-quantifiedstrategies-com/)
and TradingMetrics docs (https://docs.tradingmetrics.com/en/technical-analysis/trading-metrics/trade-specific-metrics/max-adverse-excursion).
Plot MAE vs final P&L over ≥50–100 trades *per setup*: winners cluster below an adverse-excursion
threshold; place the stop just beyond that threshold (example in sources: 88% of winning breakout
trades never exceeded a given MAE; beyond it, 79% were losers).
→ *Applies:* this is directly computable from our own journal + excursion data (post-mortem engine
already records excursions). The stop should come from *our measured* winners' MAE quantile per
symbol/timeframe, not from a fixed stake fraction.

**4. [B/C] Volatility-scaled (ATR) stops beat fixed-distance stops across regimes.**
Quant-Signals multi-asset test (~9,433 trades; https://quant-signals.com/atr-stop-loss-take-profit/):
~2.0x ATR best average profit factor; BTCUSD 2x ATR gave PF 1.72. LuxAlgo / VolatilityBox guides
(https://www.luxalgo.com/blog/how-to-use-atr-for-volatility-based-stop-losses/,
https://volatilitybox.com/research/volatility-adjusted-stop-losses/) report fixed stops triggering
within the first 2 bars 47% of the time in high-vol regimes vs 19% in calm ones. Methodologies are
not fully auditable — treat magnitudes as indicative, direction as consistent across many sources.
→ *Applies:* our stop is fixed in price % and regime-blind. A 1.5–2.5x ATR stop (day-trading range
in these sources) on the entry timeframe would widen in exactly the regimes where the current
−0.6% stop is being harvested by noise.

**5. [A/B] Stop distance must scale with intended holding period (~√t); leverage should size the position, not compress the stop.**
Square-root-of-time scaling of volatility: Danielsson & Zigrand (LSE, http://eprints.lse.ac.uk/24827/1/dp439.pdf —
including caveats that √t *understates* risk with jumps, i.e., crypto is worse) and
https://www.sixfigureinvesting.com/2014/06/volatility-and-the-square-root-of-time/. First-passage
probability of touching a barrier rises steeply as the barrier sits inside cumulative noise
(https://cfrm17.github.io/barrierProb.html). Published position-sizing practice (e.g.
https://www.markethitchhiker.com/p/the-hitchhikers-guide-to-sizing) is: derive the stop from
volatility and horizon first, then choose size/leverage so the stake loss at that stop equals the
risk budget.
→ *Applies:* our system does it backwards — leverage (5x) plus a stake-risk cap (−3%) *forces* a
0.6% price stop regardless of vol or hold length. For a 4h hold, BTC-scale vol (~0.5–1%+ per 4h in
normal regimes, larger for alts) puts 0.6% at or inside 1σ → frequent stop-outs are guaranteed by
geometry, independent of entry quality. The published fix: keep stake-risk at −3% but achieve it by
reducing size (or leverage) while widening the price stop to the vol/MAE-derived distance.

**6. [B] The tightest stop tested is often the only one that loses.**
Snorrason & Yusupov, "Performance of Stop-Loss Rules vs. Buy-and-Hold" (Lund Univ. thesis, 2009;
https://lup.lub.lu.se/luur/download?func=downloadFile&recordOId=1474565&fileOId=2435595). OMXS30
1998–2009: trailing stops of 15–20% performed best; the *only* level that underperformed
buy-and-hold was the tightest tested (5% trailing). Student thesis on daily equities — limited
external validity, but the monotone "too tight = uniquely bad" pattern recurs across sources.
→ *Applies:* consistent with #4/#5 — the failure mode to fear is stop-too-tight, not stop-too-wide;
our hard cap already bounds the too-wide direction.

---

## Q2 — Re-entry cooldowns, churn control, revenge loops

**1. [A] Loss-triggered re-risking is real and value-destroying even for professionals.**
Coval & Shumway, "Do Behavioral Biases Affect Prices?" (J. Finance 2005;
https://papers.ssrn.com/sol3/papers.cfm?abstract_id=269113). CBOT proprietary traders with morning
losses were ~16% more likely to take above-average afternoon risk, and prices moved *against* those
trades (reversion within ~10 minutes).
→ *Applies:* an automated funnel replicates the revenge loop mechanically: if the entry signal is
still lit after a stop-out, it re-fires immediately. A cooldown is the mechanical analog of the
discipline pros lack; the evidence says the post-loss re-entry population is *worse* than baseline,
so gating it is justified.

**2. [C→B] Broker-data estimates of the cost of revenge loops.**
hoc-trade analysis of retail broker accounts
(https://hoc-trade.com/blogs/behavioral-risks/revenge-trading-emotional-recovery): ~37% of traders
show revenge patterns; cost ≈ 10% of total account losses; revenge-tagged trades ~28% win rate vs
~58% for planned trades (similar numbers echoed by TradesViz/Tradezella journaling posts). Vendor
content, self-selected samples — order-of-magnitude only.
→ *Applies:* supports logging "re-entry after stop-out" as a tagged sub-population in our journal
and measuring its win rate against baseline before loosening the cooldown.

**3. [B] Practitioner consensus favors PRICE-based re-entry conditions over pure time cooldowns.**
Original Turtle rules (https://www.tradingblox.com/Manuals/UsersGuideHTML/turtlesystem.htm): re-entry
governed by price structure (skip-after-winner rule + 55-day fail-safe breakout), not clocks. Modern
Turtle variants (e.g. "AdTurtle" writeups, https://www.gate.com/learn/articles/gate-research-turtle-trading-rules-classic-system-with-annual-returns-up-to-62-71/10867)
add an explicit *exclusion zone*: after a stop-out, re-enter only once price breaks back out of a
buffer beyond the old stop/entry, which directly attacks repeated whipsaw losses in chop. Trading
platforms now ship both forms (time and candle-close cooldowns, e.g. Altrady
https://support.altrady.com/en/article/smart-orders-stop-loss-including-optional-cooldowns-time-and-candle-close-new-1hqv471/).
→ *Applies:* our 30-min timer alone lets the system re-enter the same chop at the same price. A
price condition ("long re-entry only if price > prior stop-out's entry, or has reclaimed the stop
level") is the published upgrade; the two compose cleanly.

**4. [C] The one head-to-head cooldown-length backtest found: short cooldowns cheap/beneficial, long cooldowns catastrophic.**
Medium, "The Rule-Based Trading Trap" (Henry / Nextinvest,
https://medium.com/@henry.nextinvest/the-rule-based-trading-trap-why-your-smart-stop-loss-strategy-is-quietly-destroying-your-returns-a7de177dac4b):
in its (single-asset, methodology-opaque, LOW quality) test, 0-day re-entry ≈ buy-and-hold, 1-day
cooldown +27% vs that, 7-day −79%, 30-day −91%. The mechanism (long cooldowns miss the recovery leg
that follows vol spikes) matches the Kaminski-Lo regime logic and is plausible; the numbers are not
transferable.
→ *Applies:* our 30-minute window on 15m–4h holds ≈ 1–2 bars — squarely in the "cheap insurance"
zone. The evidence gives no support for lengthening it dramatically; it supports adding the price
condition (#3) instead.

**5. [A/B] Time is a legitimate *exit* barrier, and which barrier should dominate depends on strategy class.**
López de Prado's triple-barrier framework (*Advances in Financial ML*, 2018; practitioner summary
https://medium.com/@jpolec_72972/stop-loss-take-profit-triple-barrier-time-exit-advanced-strategies-for-backtesting-8b51836ec5a2):
for mean-reversion the time barrier tends to dominate (payoff concentrates in early bars); for
trend-following, trailing price barriers dominate. No rigorous published comparison of time-based vs
price-based *re-entry* windows was found — this is a genuine evidence gap; our own A/B would be a
contribution.
→ *Applies:* re-entry policy should be conditioned on which lens/strategy class fired (mean-rev
lenses: timer-style, don't chase; trend lenses: price-reclaim re-entry).

---

## Q3 — Win-rate maximization vs expectancy: ratchets, scale-outs, breakeven stops

**1. [B] Win rate is trivially manufacturable and jointly meaningless without payoff asymmetry.**
CrossTrade (https://crosstrade.io/learn/performance-metrics/win-rate-vs-expectancy), Tradezella
(https://www.tradezella.com/blog/win-rate). Standard result: pulling targets closer raises win rate
while making the system negatively skewed; worked example — 65% win rate with 0.8R avg win / 1R avg
loss = −0.07R expectancy. 80–90% win-rate systems can run green for months before one tail day
erases everything (the short-volatility profile).
→ *Applies:* "fraction of trades closing green" is gameable by our own ratchet: arming at +0.2%
price converts many would-be winners into tiny wins. The green fraction KPI must be *pre-registered
jointly* with expectancy and avg-win/avg-loss, or the ratchet will optimize the wrong thing. Our
hard −3% stake stop caps the classic tail-blowup failure mode — so for us the residual failure
modes are fee drag and avg-win compression, not tail risk.

**2. [B] Moving stops to breakeven early measurably destroys trend-system expectancy.**
Trading Heroes (https://www.tradingheroes.com/move-stoploss-breakeven/, citing QuantifiedStrategies
backtests) and ATAS (https://atas.net/blog/break-even-in-trading/): early breakeven ratchets
"reliably turn an inherently profitable trend system into a net loser"; traders planning 1:3 R:R
realize ~1:1.4 because winners are exited early. No source found showing early-BE *improving* net
expectancy on trend entries.
→ *Applies:* our ratchet arms at +1% of stake = +0.2% price — roughly 2x the round-trip fee and far
inside normal 15m noise. This is the "early breakeven" pattern the evidence warns about: expect
inflated green fraction, collapsed avg win, and expectancy dominated by the occasional −3% stake
stop plus fees.

**3. [B] Scale-out/partial-TP raises win rate and smooths equity but usually lowers net profit and raises costs; no universal winner.**
QuantStrategy.io head-to-head (https://quantstrategy.io/blog/scaling-out-vs-all-in-all-out-a-data-driven-backtesting/):
BTC trend case — scaling out gave lower avg win, better equity stability; S&P mean-rev case —
all-in/all-out often beat scaling on net profit. Their summary table: scaling = higher win rate,
lower avg profit, lower drawdown, *higher transaction costs*. QuantifiedStrategies scaling-out
backtest reaches the same "no free lunch" conclusion
(https://www.quantifiedstrategies.com/scaling-out-strategy/).
→ *Applies:* partial-TP would push our green fraction up honestly only if the retained runner keeps
expectancy ≥0 after doubled exit fees; on taker fees it's an extra 0.05% per partial fill — must be
A/B'd, not assumed.

**4. [B] Fee drag is the binding constraint on high-churn, small-target perp systems.**
BloFin/BTCC/BingX fee academies
(https://blofin.com/en/academy/education/crypto-trading-fees,
https://www.btcc.com/en-US/academy/crypto-trading/trading-guide/maker-vs-taker-fees-in-crypto-trading-how-exchange-fee-structures-impact-your-net-profits):
taker 0.05%/side ⇒ 0.10% round trip; at 5x that is **0.5% of stake per trade before price moves**.
Our ratchet arms at +1% of stake — only 2x costs — so armed-and-ratcheted-out trades bank ~0.5% of
stake net at best; one −3% stop erases ~6 such wins ⇒ break-even needs ≳86% green just to fight the
stop/fee asymmetry at current settings. AutoQuant (arXiv 2512.22476,
https://arxiv.org/pdf/2512.22476) treats execution-cost-aware parameter tuning for crypto perps as
its core problem — academic confirmation that costs, not signals, dominate this design region.
→ *Applies:* the current (arm +1% stake, stop −3% stake) geometry is a ~6:1 loss-to-win ratio
machine; win-rate targets ≥80% are *forced* by the exit geometry, not chosen. Widening the arm
threshold or cutting the stop's price-space tightness (Q1) changes this arithmetic more than any
entry improvement can.

**5. [A/B] The honest route to high win rates is trading less (selection), not shrinking targets: meta-labeling.**
Singh & Joubert, "Does Meta-Labeling Add to Signal Efficacy?" (Hudson & Thames,
https://hudsonthames.org/wp-content/uploads/2022/04/Does-Meta-Labeling-Add-to-Signal-Efficacy.pdf);
López de Prado 2018. A secondary model that predicts "will the primary signal win?" and sizes/vetoes
accordingly raised precision 0.48→0.54 and accuracy 48%→55% in published tests — win rate rises by
*abstaining* from low-quality signals while payoff asymmetry is preserved.
→ *Applies:* directly matches our abstain-by-default direction rule and conformal/UQ gating. Green
fraction ≥80% with expectancy ≥0 is far more plausible via harder selection (fewer, better trades)
than via exit compression, per the only academically-studied mechanism found.

**6. [A] Caveat on trusting our own sweep results: exit-parameter optimization overfits easily.**
Kaminski & Lo (above) and the triple-barrier literature both stress that SL/TP grids fitted on one
regime invert in the next (cf. the 2020-24 fixed-stop VIX-regime numbers in Q1#4). Bayesian
drawdown-based threshold selection exists as a principled alternative (arXiv 1609.00869,
https://arxiv.org/pdf/1609.00869).
→ *Applies:* any ratchet/stop sweep we run must be pre-registered with out-of-sample verdicts
(mission verdict-check style), or the sweep will "discover" the last regime's noise.

---

## Where the evidence genuinely conflicts

- **Stops help vs hurt:** Han/Zhou/Zhu and Kaminski-Lo (momentum case) show stops adding large value;
  Kaminski-Lo (random-walk case) and Snorrason-Yusupov's 5% level show stops as pure cost. The
  reconciliation both literatures support: it is not *whether* to stop but *where* — stops placed at
  ~1σ of the holding-period move protect tails cheaply; stops inside the noise band transfer money to
  the market via whipsaw + fees. Our current stop is in the second category for multi-hour holds.
- **Ratchets/trailing:** trailing stops outperform in multi-month equity data (Snorrason-Yusupov,
  Han-style crash protection) but early/tight ratchets destroy expectancy at intraday scale
  (breakeven-stop evidence). Scale matters; the same mechanism flips sign with distance.
- **Cooldowns:** psychology literature (Coval-Shumway, broker data) justifies gating post-loss
  re-entries; the only direct cooldown-length backtest ([C] quality) says long cooldowns are very
  costly. No high-quality head-to-head of time vs price re-entry exists — gap worth filling ourselves.

---

## Recommended next experiments (max 5)

1. **MAE audit of our own journal (no trading change).** Compute per-trade MAE/MFE in price % from
   stored excursions, split winners vs losers, per symbol-class and hold-length bucket.
   *Validates:* if >~30–40% of eventual winners exceed 0.6% adverse excursion before closing green,
   the current stop is proven inside the winners' noise band (Sweeney boundary), quantifying exactly
   how much P&L the stop clips.
2. **Vol-scaled stop lane vs fixed lane.** New paper lane: stop = k·ATR(entry TF)·√(expected-hold
   bars) with size shrunk so stake-risk stays −3%; k∈{1.5, 2.5}. Control = current fixed stop.
   *Validates:* pre-registered at n≥200 closed/lane — stop-out rate, green fraction, expectancy;
   verdict rule "vol lane wins iff expectancy higher AND green fraction not >5pts lower".
3. **Price-conditioned re-entry gate on top of the 30-min timer.** After a stop-out, same-direction
   re-entry additionally requires price to have reclaimed the stop level (longs: trade above prior
   stop price). Log blocked re-entries with counterfactual P&L from the candle stream.
   *Validates:* measured win rate/expectancy of (a) taken re-entries vs (b) blocked-counterfactuals;
   gate is correct iff blocked population underperforms.
4. **Ratchet arm-threshold randomized sweep.** Arm at +1% / +2.5% / +5% of stake (0.2/0.5/1.0% price),
   randomized per trade, everything else fixed.
   *Validates:* joint (green fraction, expectancy, avg-win/avg-loss) per arm; tests the fee-drag
   prediction that the +1% arm caps net wins near 2x round-trip cost and that a wider arm raises
   expectancy at a small green-fraction cost.
5. **Fee-drag ledger column.** Record round-trip cost as % of gross P&L per closed trade; weekly
   metric = share of green trades whose net P&L < 2x round-trip fees ("hollow wins").
   *Validates:* directly measures whether green-fraction gains from ratchet/scale-out are real or
   fee-hollow; success = hollow-win share falling while expectancy holds.

*(Constraint honored: all lanes trade for real on paper — no shadow/observe-only modes, per
CONVENTIONS §15; experiments are pre-registered mission-verdict style.)*
