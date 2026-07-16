# B3 — THE TWO-PATH RECKONING: every orphan lens now trades (2026-07-16, night)

**What shipped: a lens paper lane (`trading/brain/lens_lane.py` + `BrainExecutor.open_lens_lane`
+ funnel stage 1c). Each funnel cycle, every orphaned directional lens inspects a rotating slice
of the universe and may open its single strongest conviction as a REAL paper trade under its own
identity — `enter_tag="lens:<name>"` — with full feedback. No shadow votes anywhere.**

## Why realized P&L, not graded predictions

The exit horizon measures 0.4427–0.4463 against ~0.49–0.53 on clock horizons (B1/B2): this
system loses money at entry timing, exits, and fees even when its sign is right. A shadow vote
grades the part that already looks fine and skips the part that's broken. So each lens now has
to survive the whole trade.

## The census — wired vs already-trading vs retired

**WIRED into the lens lane (9) — orphans that now trade under their own identity:**

| lens | what it is | was |
|---|---|---|
| cortex | B8 self-wiring expert network (144 tests) | shadow-only since it shipped (CORTEX_SIGNAL=1) |
| world_model | imagination/MCTS rollouts | flag-default-off deep lane, no consumer |
| concept_discovery | SSL encoders → SAE probe | flag-default-off, needs warm engine (abstains until one exists) |
| experience_recall | CBR bank over analogous trades | fused-only, never accountable alone |
| hypothesis | confirmed-hypothesis ledger (side-differential, post-B1-fix) | fused-only |
| river_online | online learner (now actually learning, post-B2-fix) | fused-only |
| debate | LLM bull/bear/risk room (deep lane, capped 2 symbols/cycle) | deep-lane advisory |
| dir_exit_read | the exit oracle's read as an ENTRY opinion | 25k+ ledger claims, zero positions ever |
| news_sentiment | vader news lens | measured dry in B2 census — the lane is its prove-it-or-retire trial: a persistent zero-nomination count is the retire evidence |

**NOT wired — already trade on the money path (not orphans):** broker filters,
direction_model, symbol_move_net, strategy_library / strategy_tournament, direction_equation,
learned_direction, explore_open_all.

**RETIRED from lens candidacy, with reasons (recommendation — no code deleted):**

- **self_evolve (DEAP)** — it is a strategy *generator*, not a direction lens; it has promoted
  0 candidates ever (B4's calibration question), and the 311 library strategies that do trade
  came from the other generators. Nothing to wire.
- **skills self-improve / school / FSRS learn-loop study output** — knowledge maintenance, no
  directional opinion API; wiring would fabricate a lens (honest-wiring violation).
- **computer-use embodiment (GUI agent)** — perception/actuation, not a direction source.
- **app_study** — B1 measured it a literal duplicate of app_indicators (fate correlation
  +1.000); wiring both would double-count one opinion.
- **decision_episodes/FinMem recall** — memory retrieval layer; its content already reaches
  decisions via exit-reflection lesson recall (B2 fix) and the NSE loop's episode recall.

## Identity & feedback (the one hard requirement)

- `enter_tag lens:<name>` → freqtrade → `journal.strategy_name` (freqtrade_ingest.map_trade:288)
  → per-lens realized P&L is a journal group-by.
- Every entry writes a `taken=True` truth-ledger claim under `source="lens:<name>"` → per-lens
  direction accuracy accrues from day one, separate from its fused record.
- Every close already flows through `_learn_from_close` → champion bandit, neuron grading,
  river online update, exit labels, decision-memory resolution. Nothing new needed — the B2
  fixes completed this loop hours before this lane shipped.

## Honesty mechanics

- **Abstain-by-default**: a lens with no opinion or |p_up−0.5| < LENS_LANE_MIN_EDGE (0.08)
  nominates nothing (CONVENTIONS §16 — unproven ⇒ abstain, never a forced coin-flip).
- **Bounded cost**: rotation slice LENS_LANE_SCAN_N=12/cycle; LLM/MCTS lenses see only
  LENS_LANE_DEEP_N=2. A broken lens is skipped silently and simply accrues no record.
- **Paper by construction**: same engine_client, dry-run Freqtrade, `allow_live` stays False
  from the funnel; crypto executor only, NSE isolation untouched.
- Flags: `LENS_LANE=1` default ON (§15 no-shadow-on-paper), `LENS_LANE_DISABLE=<names>` for
  per-lens off, caps via `LENS_LANE_MAX_PER_LENS`.

## How many trades before each lens's P&L means anything (the number, not "a while")

- **Direction skill** (is it >50%?): to detect a true 55% winner at α=0.05 one-sided with 80%
  power needs **~620 closed trades**; a true 60% winner needs **~155**.
- **Mean P&L edge**: with this journal's per-trade σ ≈ 2.5% and a +0.3%/trade true edge,
  **~430 closed trades**; a +0.5% edge needs **~155**.
- Accrual rate is nomination-gated (abstention is allowed and expected). At 1 nomination per
  lens per funnel cycle (~5-15 min) a maximally-active lens caps at ~100-250 entries/day; the
  honest expectation is **1–3 weeks per active lens** before a promote/retire verdict, and the
  first few days' nomination counts themselves are the verdict for the silent ones
  (news_sentiment, concept_discovery without a warm engine).
- **Read no verdicts before n≥100 closed per lens.** Interim P&L on dozens of trades is noise;
  that is how the 55.2%-4h-edge belief was born and falsified.

## Verification

8/8 unit tests (`tests/test_lens_lane.py`): strongest-edge selection, direction mapping,
min-edge abstention, None/raising lens silence, kill-switch, per-lens disable, rotation
coverage, and executor mechanics (identity tag + taken=True claim on entry; refused order =
skip, never a fake entry — the phantom-entered scar). Live: funnel restarted 2026-07-16 ~22:0x
with the lane in stage 1c; first `[lens-lane:futures]` cycle lines and `lens:*` journal rows
are the activation evidence (see session log).
