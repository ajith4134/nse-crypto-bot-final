# Direction-accuracy diagnosis (2026-07-11) — owner: "direction decider is not reliable"

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
