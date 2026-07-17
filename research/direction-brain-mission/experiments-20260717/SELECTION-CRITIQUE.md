# Selection & entry-timing critique — 2026-07-17 (owner's momentum question)

Owner's question: how do we pick symbols from the futures universe? If via a momentum
filter, aren't we entering AFTER the move completed — buying as momentum dies? Can we
enter at the START instead? Plus: find every wrong architecture decision, skip nothing.

Measured with m_entry_timing.py + follow-up band/2×2 probes over 5,495 covered closed
trades (candle-covered subset of 6,500).

## 1. How symbols are ACTUALLY picked (code-verified)

Attention flows through THREE layers that all rank by the COMPLETED 24h move:
1. `binance_filter_lane` preset "momentum" = `abs(24h pct_change)·1.0 + log(volume)·0.6`;
   the `filter:momentum` side is `sigmoid(24h pct / 5)` — sign of the finished move.
2. Funnel HEAT: `watch.touch(score=24h change)` — the watchlist's heat ranking is the
   same completed move again.
3. Even in unlimited "brain-decides" mode (whole 626-futures whitelist injected),
   `LOOK_TOPK=60` reads per-TF direction only for the top-60 *by that same heat score* —
   so ~90% of the universe is structurally unexamined each cycle, and the examined 10%
   is exactly the already-moved cohort.
Parallel lanes: broker pickers (top-gainers/losers/trending pages — completed-move lists
by construction), reflex ticks (armed BY those pickers), strategy-table engine workers,
lens-lane rotation (12/cycle), breadth driver.

## 2. The measurements — owner's hypothesis is HALF right, and the half matters

Signed 1h pre-entry run-up (move in the trade's direction before entry), all eras:

| band | win | avgP | n |
|---|---|---|---|
| chase +10..100% | **0.570** | **+2.97%** | 107 |
| chase +5..10% | 0.536 | −0.42% | 293 |
| +0..2% | 0.421 | −0.64% | 1,882 |
| fade −5..−2% | 0.469 | −1.27% | 548 |
| fade < −5% | 0.440 | −2.94% | 273 |

- **Blanket "momentum entries are late" — REFUTED**: the hardest 1h chases are the BEST
  band and the only positive one. Fresh moves continue at our horizons.
- **But the owner is RIGHT about the lanes built on stale rankings**: `filter:*` enters
  at +4.6% 4h run-up with a nearly FLAT last hour (+0.84%) → win 0.425, −1.43%/trade.
  `mom_trix` enters at +17.4% 4h → win 0.273, −5.40%. `force_entry` (old router) +5.4%
  4h → −1.92%. Ranking by 24h change selects moves that already stalled.
- **Freshness 2×2** (big 4h move >5%): last-hour still moving (≥2%) → 0.529/−0.92;
  last-hour stalled (<1%) → 0.488/−1.21. **Counter-trend** (entering against a >5% 4h
  move): 0.444/−1.80 — the worst cohort, and the whole meanrev_* family lives there
  (meanrev_stochrsi win 0.261, n=283).
- `learned_direction` entries are timing-neutral (run-up ≈ 0) — the decider isn't the
  chaser; the FILTER/STRATEGY lanes are.

**The correct reframe: the defect isn't "momentum" — it's ranking by STALE momentum
(24h) instead of by what is moving NOW (1h) or about to move (inception).**

## 3. Professor's full defect list (nothing skipped)

A. **Attention = completed 24h move, three layers deep** (preset score, watch heat,
   LOOK_TOPK order). The pre-momentum universe is structurally invisible; by the time a
   symbol earns attention its move is hours old.
B. **Selection and direction were historically the SAME signal** (sign of 24h change) —
   no independent evidence; partially fixed by the direction driver, but filter-family
   claims still carry that side.
C. **No lifecycle/freshness feature exists anywhere** — the strongest discriminant found
   today (fresh-vs-stale, run60-vs-run240 shape) is computed nowhere in the pipeline.
D. **No inception detection, despite owning perfect infrastructure**: 1m WS mirror on
   877 symbols, true OFI, order-book state (which the deep-research says predicts
   15m–4h!), liquidation feed. Selection consumes none of it — it reads yesterday's
   scoreboard instead of the tape.
E. **Strategy-table lanes bleed with no kill criteria**: most tag families run win
   0.23–0.44 with negative avgP (trend_parabolic_sar 0.231, pattern_hammer 0.286,
   breakout_lw 0.245…). The lens lane has a pre-registered verdict bar; the strategy
   lanes have nothing — proven losers keep trading.
F. **Reflex arm-time staleness** (session-5 JCT) patched with a pos-gate built on a
   finding E1 later inverted — the patch may block the best entries; its counterfactual
   will adjudicate.
G. **Counter-trend family fights 4h trends and loses** (696 trades, worst bucket) —
   mean-reversion needs a range/exhaustion qualifier it doesn't have.
H. **Exit geometry** (E5/E6): win% fine, payoff 0.54 — being fixed (early_abort arm +
   tighter tailgate).
I. **Measurement debt**: OHLCV feathers stale since 07-16 18:55 → only 78 clean-window
   trades were retro-measurable. Science is data-gated by a missing daily refresh.

## 4. Improvement directions (discussion — nothing implemented)

1. **Inception ranker (replaces 24h heat as the attention key)**: score the WHOLE
   universe every cycle in RAM — 1m/5m acceleration, volume-surge ratio (last-5m vs
   trailing avg), squeeze percentile (rolling range-width), breakout freshness (bars
   since new 30m high/low), OFI impulse, liquidation-cascade onset. All vectorizable
   from mirror candles; rank attention by P(move starting), not P(move happened).
2. **Lifecycle "phase" conditioner** on every claim (fresh/mid/stale/exhausted from the
   run60-vs-run240 shape + move age): the E8 conditioner chain then LEARNS per-source
   phase reliability — momentum sources should auto-discover they only work fresh.
3. **Freshness gate on the momentum-family lanes**: a filter/reflex momentum entry must
   see the last hour still moving in its direction (r60 threshold or accel>0).
4. **Kill-criteria parity**: every entry lane (strategy tags included) gets the lens
   bar — n≥100 closed, measured negative → retired. Same rule everywhere.
5. **Unlimited-mode look order by inception score** instead of 24h heat, so the top-60
   examined symbols are the ones most likely to move next.
6. **Daily feather refresh** so every future question has retro-measurable data.

Academic anchor: intraday/short-horizon continuation is real while EXTREME multi-day
winners revert (short-term reversal); "fresh move continues, stale move doesn't" is the
standard momentum-lifecycle result — our tape agrees with the literature.
