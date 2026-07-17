# Video A — "First Candle Value" (opening-range volume profile strategy)

Uploaded 2026-07-17 (Instagram reel, 65s, podcast-style trader clip). Speech transcript in `transcript.md`, keyframes in `frames/`.

## The strategy, exactly as taught

1. **Opening range**: mark the HIGH and LOW of the first 15 minutes of the session (one M15 candle).
2. **Instead of trading the raw ORB breakout**, draw a **volume profile over just those first 15 minutes** (he renders it from the M5 sub-candles).
3. The profile's **value area** = price band holding **70% of traded volume** → **VAH** (top) / **VAL** (bottom).
4. Two playable events at VAH (mirror logic applies at VAL):
   - **Trap / failed breakout (reversal)**: price pushes above VAH then **closes back inside** → buyers trapped. **Entry = that closing candle**, **stop = the breakout high**, **target = VAL**. **Trail the stop after each candle that moves beyond the value area** ("that's when the explosive moves happen" — i.e. once price leaves the 70% zone it's in low-volume territory and travels fast).
   - **Acceptance (continuation)**: price pushes above VAH and **holds** → market accepting higher prices. **Wait for the pullback to VAH**, trade the continuation. **Move stop to each new candle's low** and let it run until stopped out ("how you get the most out of your winners").
5. Framing: "After 10 years, complexity never made me money. Simplicity did." (frames show Wyckoff, FVG crossed out on a 2017-2026 timeline). Ends with course/community CTA ("comment Join") — it's lead-gen content.

## Fact-check (2026-07-17)

- Value area = 70% (≈±1σ of a bell-shaped volume distribution), VAH/VAL/POC: standard Market Profile / auction market theory (Steidlmayer, CBOT 1980s; Dalton). CONFIRMED standard.
- Failed-breakout-above-VA → rejection → high probability of rotation back to POC/VAL: standard auction-theory playbook (ATAS, FTMO, auction-theory guides teach the same trap/acceptance pair). CONFIRMED as established practice; **no rigorous public backtest of the exact 15-min variant** — the edge claim is anecdotal.
- The mechanism is real, not mystical: trapped breakout longs must sell to exit → fuel for the reversal; acceptance outside value = one-time-framing/initiative activity → continuation. Same family as our failed-auction signal.
- Caveats: works best on session-open instruments (index futures / NSE open). Crypto is 24/7 — "first 15 minutes" must be re-anchored (UTC day open, funding timestamps, or high-volume session opens like US equity open which drives BTC intraday volume).

## Relation to our repo

We ALREADY have a Volume-Profile auction engine (POC/VAH/VAL, failed-auction detection) — see memory `volume-profile-auction-feature`. This video adds:
- **Opening-range anchored profile** (first N minutes) as a distinct profile window vs rolling/day profile.
- The **two-sided event grammar** at VAH/VAL: trap→fade vs acceptance+pullback→continue. This is a DIRECTION source with a defined trigger (close back inside vs hold), stop, target, and trail rule — i.e. it fixes *selection/timing/exit*, which is exactly the measured gap (direction program: sign accuracy wasn't the whole problem; selection/timing/exit was).

## Verdict

Real, established mechanics; modest but genuine expected edge if (a) anchored correctly per venue, (b) gated by liquidity_regime/clock_phase conditioners we already record, (c) run on the paper path with full outcome logging (no shadow mode). Not a money-printer; a clean, testable direction+exit policy.
