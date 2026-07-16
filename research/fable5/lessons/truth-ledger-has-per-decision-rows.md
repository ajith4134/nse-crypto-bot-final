# The truth ledger DOES have per-decision rows — use them

`trading/state/direction_truth_train.jsonl` is a rotating per-decision log (newest 40k resolved
rows: ts, symbol, source, direction, horizon, correct, taken — including taken:false probes,
so NOT trade-selection-biased). Written by `truth_ledger._append_train()`. The widely-repeated
claim "direction_truth.json is aggregate-only, per-decision analysis is impossible" (B1 prompt,
PROMPTS-BRAIN.md §B) is FALSE — it was written by sessions that only looked at the aggregate file.

Why it mattered: the entire B1 lens-correlation study ran on this file. Caveat: rotation keeps
~14h of data, so it is single-era; for exact simultaneous vote vectors use
`trading/state/direction_votes.jsonl` (vote_log.py, built 2026-07-16).
