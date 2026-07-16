# B1 — THE ENSEMBLE DELUSION: verdict (2026-07-16, evening)

**One-line verdict: the "fourteen-lens network" is not fourteen opinions. Measured on 40,000
per-decision votes from today, it is roughly five to seven real opinions plus five stuck
constants, one duplicate, one structural negation pair, and one self-contradicting
high-volume source. The tight 0.44–0.53 accuracy clustering that motivated this study is
mostly an artifact of those pathologies, not evidence about signal.**

This is a **fourth world** — the B1 prompt offered three (all-correlated / diverse-but-weak /
no-signal-inputs). The measured answer is: *the ensemble is partly fake, and until the fakes are
fixed, the three-world question cannot be answered from the ledger at all.*

---

## 0. Substrate — and a corrected premise

The B1 prompt's central claim ("`direction_truth.json` stores only aggregates; there are **no
per-decision rows**") is **wrong**. `trading/state/direction_truth_train.jsonl` is a rotating
per-decision log (newest 40k resolved rows: ts, symbol, source, direction, horizon, correct,
taken) written by `truth_ledger._append_train()`. It includes `taken:false` probe rows, so it is
**not** selection-biased the way the journal is.

Limitation stated plainly: rotation means the file covers **one era — today, 06:09→20:07**
(14 hours). Everything below is measured on that window. Joins are on (symbol, 5-minute bin);
26 of 40k rows per source pair overlap sparsely — 27 of 66 balanced-lens pairs have n≥30.

## 1. Five "lenses" are (near-)constant emitters, not opinions

LONG-rate per source, today (n in parentheses):

| source | LONG-rate | reading |
|---|---|---|
| hypothesis (903) | **100.00%** | **recording bug** — see below |
| live_loop (256) | **100.00%** | executed NSE trades (long-only segment), not a lens |
| river_online (3,494) | **96.65%** | degenerate model output (bootstrap class-imbalance latch) |
| symbol_move_net (2,509) | **0.72%** | degenerate — near-constant SHORT |
| strategy_library (393) | **0.00%** | per-coin table all-SHORT this window (possibly genuine, but constant) |

A constant emitter's ledger "accuracy" is just the era's base rate of up/down moves. river_online
0.4456 = "the market fell more than it rose on its labels", nothing more. **These five rows of the
14-source table carry no information about model skill.**

**The `hypothesis` bug (real, file:line):** `trading/direction/brain_sources.py:228-236` asks the
hypothesis ledger for support **of the candidate's hinted direction** (`direction: dir_hint`), then
`_emit()` (line 213-225) records `p>=0.5 → "LONG"` as an **absolute** direction. A
direction-relative support score is being written down as an absolute LONG vote — that is why
hypothesis is 100% LONG. One-line semantics fix: convert the relative bias to the hinted side
before recording (if hint is SHORT and bias positive, record SHORT).

## 2. One structural negation pair — the Mirror-era smoking gun

`funnel_mtf_vote × learned_direction`: **phi = −0.950, agreement 2.5% (n=80 matched bins)**.
Joint distribution: LONG/SHORT 45, SHORT/LONG 33, SHORT/SHORT 2, **LONG/LONG 0**. Two balanced,
live lenses that *never* agreed LONG all day.

Timeline evidence: hour-by-hour agreement was **0.00 from 11:00 through 18:00**, then 0.67 (n=3,
tiny) at 19:00. `.env` was modified at **19:44 today** — the `MIRROR_GATE=0` retirement.
`learned_direction.decide()` weights sources by their measured ledger edge and, in the D2 Mirror
era, inverted the side the ledger called anti-signal. Their aggregate accuracies confirm it: in
the 12:20 snapshot **learned_direction 0.5235 + funnel_mtf_vote 0.4765 = 1.0000 exactly**; an
independent re-derivation at 20:30 measured 0.5102 + 0.4814 = 0.9916 — still near-complementary,
with the drift explained by post-retirement (19:44+) rows diluting the mirror era as expected.
One coin, flipped twice.
learned_direction's apparent "edge" (2nd best in the table) is the mirror image of funnel's
anti-edge — both are the same era artifact the direction-premises-falsified memory describes.
**Neither number should be cited again until re-measured post-19:44.**

## 3. One duplicate cluster

`funnel_mtf_vote × indicator_fusion`: **phi = +0.815, agreement 91.4% (n=217)** — the funnel's
"MTF vote" is substantially indicator_fusion re-badged (journal `app_signals` shows `vote` p_up
values matching `chart` p_up distributions too). Also `app_indicators × app_study`: fate
correlation **+1.000** (n=38) — literal duplicates. Counting these separately in the source table
overstates the network's width.

## 4. The highest-volume source contradicts itself

`dir_exit` (26,846 rows today — **67% of the entire train log**) has within-5-minute
self-consistency of **0.694**: in a third of the bins where it voted more than once on the same
symbol, it voted both LONG and SHORT within 300 seconds. (Sample: LDO LONG/SHORT/LONG/SHORT within
~40s.) Every other balanced lens is ≥0.94. Whatever dir_exit is recording, it is not a stable
opinion — and it dominates the ledger's row count and the `exit` horizon everyone worries about.

## 5. What remains after removing the fakes

Balanced, genuinely-voting lenses (12): dir_exit, direction_equation, direction_model,
filter:funding, filter:liquidations, filter:momentum, funnel_mtf_vote, indicator_fusion,
learned_direction, mtf_agree, psych_ofi, venue_leadlag.

- **Mean |phi| = 0.267, median 0.205** over the 27 observed pairs — genuinely *low* correlation
  (the ensemble literature's aggregation sweet spot is ~0.42 mean pairwise).
- **Effective rank (participation ratio): 7.8 of 12** — but read with care: 39 unobserved pairs
  were filled with 0, which inflates rank, and the −0.95 negation deflates it for a fake reason.
- Real diversity does exist in places: `filter:funding × filter:momentum` phi = **−0.402**
  (n=442) — funding is genuinely contrarian to momentum, consistent with the measured
  pct_change-contrarian finding (commit d056141).

**So which world?** After excluding constants/duplicates/negation: the surviving ~5–7 opinions are
**weakly correlated AND individually near-chance** — closest to world #2's structure
(diverse-but-weak) but with the crucial caveat that *individually weak* here means "within noise
of 0.50 on today's window" for everything except direction_equation (0.5267 on the multi-day
aggregate, n=4,557, ≈ +3.6σ — the one source with a defensible pulse, matching the clock-phase
concentration finding). Fusion of genuinely-diverse near-chance lenses is mathematically capable
of adding value only if their tiny edges are real; that question is answerable only after the
pathologies above are fixed and the vote log (below) accrues clean data.

## 6. What was built (write-only, cannot alter a trade)

The per-candidate simultaneous vote vector existed only transiently as `_reads` inside
`brain_executor` and was never persisted — which is why this study had to join sparse timestamps.
Now persisted: **`trading/direction/vote_log.py`** → `trading/state/direction_votes.jsonl`
(one JSONL row per candidate evaluation: ts, symbol, lane, {source: p_up}, decided side;
rotating 60k; `VOTE_LOG=0` kill-switch; every call wrapped so it can never raise into the
decision path). Tapped at both lanes: breadth (`brain_executor.py` after `_ld.decide`, line ~530)
and selective (line ~965). 4 unit tests pass (`tests/test_vote_log.py`). INDEX.md regenerated.
**Requires the funnel process restart to start logging — owner action.**

With a week of this log, the correlation matrix becomes exact (every pair observed on identical
candidates, no time-bin approximation) and the three-world question can be answered properly.

## 7. Recommended actions (owner decides; none applied beyond the vote log)

1. **Fix the `hypothesis` recording bug** (brain_sources.py:236) — one line; until then, delete or
   ignore its ledger bucket: every row it ever wrote is direction-garbage.
2. **Quarantine pre-19:44 buckets for `learned_direction` and `funnel_mtf_vote`** (era-tag, like
   the poisoned-inverter rows were tagged) — both numbers are Mirror-era artifacts.
3. **Root-cause `symbol_move_net`'s constant-SHORT and `river_online`'s constant-LONG.** Both are
   models emitting one side ~97-99% of the time. Until re-trained/re-calibrated, their fusion
   weight is noise (and learned_direction "earns" weight from their fake track records).
4. **Investigate `dir_exit`'s 0.694 self-consistency** — 67% of ledger volume comes from a source
   that flip-flops within minutes; its 0.4427 exit-horizon accuracy may be measuring churn, not skill.
5. **Restart the crypto funnel** so the vote log starts accruing (owner action).
6. Re-run this study on `direction_votes.jsonl` after ~1 week of clean post-Mirror data.

## Method + reproduction

Scripts: `scratchpad/b1_ensemble.py` (vote matrix, phi, self-consistency, 5-min bins) and
`scratchpad/b1_part2.py` (error-correlation, effective rank, era split) — run with
`.venv/bin/python`. Raw outputs: `b1_result_300s.json`, `b1_part2.json` in the session scratchpad.
Pairwise stats used phi (Matthews) on ±1 votes with n≥30; effective rank = participation ratio of
the phi matrix eigenspectrum. All numbers derived from
`trading/state/direction_truth_train.jsonl` as of 20:07 today; the file rotates, so re-runs will
differ — that is expected and is the reason per-decision logging (item 6) matters.
