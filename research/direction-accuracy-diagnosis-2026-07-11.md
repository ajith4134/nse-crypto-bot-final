# Direction-accuracy diagnosis (2026-07-11) — owner: "direction decider is not reliable"

> ## ⚠️ CORRECTED 2026-07-16 — the key claims below were RE-MEASURED and are FALSE. Do not build on them.
>
> Re-measured against the live ledger (100,774 labels) on 2026-07-16 (Fable-5 measurement rebuild;
> full evidence: `research/audits/measurement-rebuild-20260716.md`):
>
> 1. **The "4h = 55.2% GENUINE EDGE" is gone.** With 6.7× more data, 4h = **0.502** (n=19,591) — a
>    coin-flip. Every recommendation below that says "bias to the 4h horizon" rests on a number that
>    did not survive out-of-sample.
> 2. **The "exit = 36.5% STRONG ANTI-SIGNAL" was measured on FROZEN data.** The exit labels' only
>    writer (`backfill_journal`) had no production caller; the bucket sat at n=3,459 for 5 days while
>    3,244 trades closed. After fixing the wedge and backfilling (2026-07-16): exit-sign accuracy on
>    the missing 5 days = **0.516** — the "exit destroys good calls" era ended around 7/11.
> 3. **Inversion does not work** (the Mirror Gate premise). Controlled paired analysis: on the exact
>    samples the gate inverted, the raw source would have scored 0.638/0.672/0.656 (z=+4.1/+3.6/+3.0
>    vs its trigger bucket) — bucket accuracies are non-stationary (chrono split-half persistence
>    corr = **−0.214** across 39 cells), so "reliably wrong" sources revert before the flip pays.
>    MIRROR_GATE=0 set 2026-07-16.
> 4. Current honest state: predictors are coin-flips at every horizon (0.488/0.494/0.503); crypto
>    realized sign-accuracy since 7/11 = **0.523** (n=3,282, Wilson-low 0.505) with net P&L ≈
>    breakeven-to-positive (+17.8k USDT, but +30k of it in 2 outlier wins). The bottleneck is
>    decision-time INPUTS (see the Input Hunt), not exits, not sign errors.

Measured from the Truth Ledger (Pillar 27), **n = 12,886 resolved directional labels**. The owner is
right: the direction predictor is unreliable — but the data shows it's specific, not uniform.

## The numbers
- **Aggregate direction accuracy: 47.4%** — a coin-flip (worse than random).
- **By horizon** (the key finding):
  - **4h = 55.2%** (n=2858) — GENUINE EDGE
  - 1h = 51.9% (n=3278) — slight edge
  - 15m = 47.7% (n=3291) — coin-flip
  - **exit = 36.5%** (n=3459) — STRONG ANTI-SIGNAL
- **Anti-signal sources** (reliable n): `meanrev_stochrsi` 24–42%, `unknown/exit` 33% (n=1730),
  `momentum/exit` 39%, `funnel_mtf_vote/trend_down` 25%.
- **Reliable source:** `momentum` 75.6% (n=45, pooled 15m+1h+4h).

## Root cause (two compounding)
1. **The raw entry direction is a coin-flip in aggregate** (47%). The Mirror Gate correctly
   INVERTS clear anti-signals (meanrev_stochrsi → recorded as `mirror:*`) and ABSTAINS coin-flips
   (explore_open_all 47.8% → no trade). So it refuses coin-flips — which is *why so few open*.
2. **Trades resolve at the wrong horizon.** The direction has real edge at 4h (55%) but trades
   EXIT on short-horizon noise where the direction is anti-correlated (exit=37%). The good 4h
   thesis is killed before it plays out ("exit-path destroys correct calls").

So opening MORE trades on this direction just loses faster — the owner's exact point. The Mirror
Gate is already doing the right thing (abstaining coin-flips), which is why opens stay low.

## The fix — Direction Accuracy Program (the real work)
Not a blanket invert (aggregate 47%, 4h is 55%). Make the direction reliable BY CONSTRUCTION:
1. **Reliability-weighted direction ensemble:** weight every signal by its measured Truth-Ledger
   hit-rate per (source, regime, horizon); invert measured anti-signals (<0.45 CI-high), trust
   measured-good (>0.55 CI-low), ignore coin-flips. (Mirror Gate does this per-source binary — make
   it a continuous ensemble across ALL sources so the *net* direction is measured-reliable.)
2. **Bias to the 4h/1h horizon** (where edge is real) + feed the NEW Binance order-flow
   (taker buy/sell, long/short ratios, funding, OI) — a real positioning signal, likely better than
   the anti-correlated meanrev TA.
3. **Fix exits:** hold to the horizon where direction is reliable (4h); stop cutting on the 37%
   exit-horizon signal. (Ties to the Directional EXIT oracle / dir_exit — currently 0.19–0.50.)
4. Keep the Mirror Gate's self-inversion (working).

This is substantial + risky (touches entry direction + exits) — deserves its own focused build with
per-change Truth-Ledger measurement, not a tail-of-session hack. See [[direction-accuracy-program]].
