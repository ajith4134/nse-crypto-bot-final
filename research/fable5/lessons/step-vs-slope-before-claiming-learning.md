# Fit step-vs-slope before claiming the brain "learned"

A naive trend on this repo's journal shows balanced accuracy rising +1.6pts/day (t=4.3) —
looks like learning. A changepoint model shows it is actually a single STEP at 2026-07-09
(AIC −13.1 vs linear −3.6): pre 0.34-0.35 (anti-accurate, inverter/Mirror era), post 0.53,
and the post-step slope is NEGATIVE (−0.013/day, t=−1.26). The step coincides with
session-shipped repairs (direction-equation deploy + in-RAM data migration), not autonomous
learning.

Rule: any "improvement over time" claim on this journal must (a) use per-day BALANCED accuracy
(drift-proof: coin-flip = 0.5 regardless of market direction), (b) compare step vs slope models,
(c) check whether the changepoint matches a commit date before crediting a learning loop.
Also measured: the learned channel (0.540) does not beat the unlearned explore control
(0.562, difference z=+0.99 n.s.) — always compare against the built-in explore lane.
