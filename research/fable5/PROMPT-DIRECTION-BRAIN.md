# The Direction Brain Mission — Fable-5 prompt (drafted 2026-07-17, owner approval pending)

**How to run:** `/model` → Claude Fable 5 → paste everything below the line as ONE message.
Owner note: the prompt asks the session to use parallel subagents and workflow orchestration —
by pasting it you are explicitly opting in to multi-agent runs (this line is that consent).

---

## MISSION: make the post-selection direction call the most accurate it can honestly be

You own ONE subsystem of a live paper-trading brain: the **direction decision** — given a symbol
the scanner already picked, decide **LONG / SHORT / NO-TRADE**, with calibrated confidence.
Everything else (scanning, execution, risk, dashboards) exists and works; touch it only where it
provably limits direction accuracy. This is YOUR research mission, not a task list: iterate until
you can no longer justify a meaningful improvement, however many hours that takes. I am explicitly
authorizing long autonomous runs, parallel subagents, and workflow orchestration for experiment
fan-out — subject to the standing owner rules below.

**Why this matters:** the system opens dozens of paper trades a day. Its entry-sign is measurably
a little better than chance, and its wins are tail-heavy — so every percentage point of honest
directional accuracy (or every bad trade correctly refused via NO-TRADE) compounds into the one
number the owner cares about: consistent risk-managed income. Fewer, better decisions beat more
decisions.

## Ground truth — measured 2026-07-17 09:36 UTC, not folklore (re-derive before you build)

- Truth ledger: **160,655 labels / 607 buckets, overall 0.5274**. By horizon:
  **15m 0.5073 (n=57.8k) · 1h 0.5239 (n=54.8k) · 4h 0.5750 (n=42.0k) · exit 0.4236 (n=6.1k)**.
  The 4h edge and the exit destruction are the two loudest facts in the system. CAVEAT: these
  pool eras and label methods — your step zero is re-deriving them on (a) the clean window only
  (≥ 2026-07-16 21:23 UTC, epoch 1784236980; everything earlier carries measured contaminations)
  and (b) split by label method (`method_acc`: feather vs mirror-mark vs probe — a 2pp
  measurement artifact was already caught here once).
- Per-source (all-era, verify on clean window): indicator_fusion 0.5335 (n=8.8k),
  strategy_library 0.5292, direction_equation 0.5128, **direction_model 0.4910 (n=4.3k — the
  trained model is BELOW chance)**, filter:funding 0.4901, dir_exit claims 0.5466 (n=89k).
- The decision function is `trading/direction/learned_direction.py::decide()` — Hedge-style
  weights from truth-ledger reliability with hierarchical shrinkage (global→regime→conditioner),
  fed by `brain_executor._lens_reads()` (the ONE lens family for both decision lanes: filters,
  direction_model, symbol_move_net, strategy_tournament, debate, hypothesis/experience/news/
  river, worldmodel/concept deep lane, VP trap/accept, cross-symbol market state, lessons,
  onchain). NO-TRADE already exists as abstention (`min_total_w`, `band`).
- Infrastructure that exists FOR you (use it, don't rebuild it):
  `trading/state/direction_votes.jsonl` — every lane's full simultaneous vote vector;
  `trading/direction/ope.py` — labels those rows at 15m/1h and replays candidate decide()
  configs offline (subprocess-isolated env grid) → this is your experiment engine;
  `trading/state/direction_truth*.json` — per-source reliability with conditioner sub-buckets
  (liquidity calm/mixed/stressed, clock at/off-quarter-hour); `market_graph.json` lead-lag +
  coint-lite pairs; the in-RAM mirror (`binance_stream.get_mirror()`) — 1m/5m/15m bars, 20-level
  book, funding, liquidations for every USDⓈ-M perp, zero API; a local vision model
  (qwen2.5-vl via Ollama) for chart reading; `tests/` with the STATE_DIR isolation pattern.
- Recent history you must not re-litigate: the regime classifier was dead 07-12→07-17 (fixed,
  mirror-first, ~2.5h warm-up after any restart); two inverters that flipped "anti-signals"
  lost money and were killed; the quality gate (CRYPTO_MIN_SCORE) was measured a no-op with
  score↔profit correlation −0.031; the "4h edge = 55.2%" and "40.3% anti-signal" doc numbers
  were both era artifacts. Full context: memory index + research/direction-accuracy-program/ +
  research/direction/cross-symbol-direction-catalog.md + research/fable5/BRIEF.md.

## The laws (violating any of these voids the work)

1. **Direction must be earned (CONVENTIONS §16).** Every side comes from measured evidence.
   NEVER invert an unproven or noisy source — 0.49 is noise, not 0.51 in a mask. Unproven ⇒
   NO-TRADE. Underpowered ≠ wrong.
2. **No shadow mode on the paper path (§15).** Paper IS the experiment: candidate deciders trade
   for real on paper under their own enter_tags, full risk allowed, every outcome logged. Never
   ship an observe-only/flag-gated-off variant on the paper path.
3. **Multiple-testing discipline.** You will try many combinations — so every "winner" must
   survive: (a) out-of-sample evaluation on data the search never saw, (b) a deflated/adjusted
   significance standard that accounts for how many things you tried (deflated Sharpe or
   Bonferroni-style Wilson bounds — state which and why), (c) the martingale baseline
   ("tomorrow = today"), (d) for anything periodicity-flavored, the random-walk null in
   `trading/strategy/cycle_gate.py`, and (e) **era robustness** — the edge must hold on at
   least two disjoint time slices of the clean window, or it is a regime artifact, not an
   edge. In-sample fit quality is inadmissible evidence.
4. **Clean-window + method-quality discipline.** Fits and verdicts use post-1784236980 rows;
   any claim you make is split by label method before you report it.
5. **Measurement before mechanism.** When a source looks bad (e.g. direction_model at 0.4910),
   first prove the measurement is honest, then decide retire/refit — never "fix" by inversion.
6. **RAM first, zero cost.** No new REST polling loops (the last one earned an IP ban), no paid
   services, no ccxt in the decision path. The mirror + existing state files are your data.
   Fable 5 may be the teacher; it must never become a runtime dependency.
7. **Standing owner rules.** One WRITING session at a time (read-only subagents may fan out;
   parallel WRITE agents require asking the owner first — ask, don't assume). Never commit
   secrets. Commit via the commit-safe flow with tests green. NSE and crypto stay isolated.
8. **A side without a horizon is half a decision.** The measured truth is horizon-asymmetric
   (4h 0.575 vs 15m 0.507) and exit labels sit at 0.4236 — the system's correct entries are
   being destroyed AFTER entry, outside your subsystem. You do not redesign exits, but your
   decision contract MUST emit the horizon the side is valid for, your validation MUST score
   at that horizon, and you SHOULD hand the horizon to the exit machinery that already
   consumes per-trade context (the exit-policy bandit reads assignment records) so your
   correct calls stop dying to a mismatched holding period.
9. **Edges must clear costs.** A 0.52 side at 15m can be a money-losing trade after the
   ~round-trip fee + measured slippage (exec_choice_stats.json now grades real fills). The
   NO-TRADE band is cost-aware by definition: expected |move| at the emitted horizon × edge
   must exceed round-trip cost, or the honest output is NO-TRADE. Raw sign accuracy that
   loses money is not a win on this scoreboard.
10. **Hot-path budget.** decide() runs inside a funnel cycle that has died to per-candidate
    heavy calls before (the TabPFN freeze, the per-pick LLM debate). Whatever wins must
    answer in milliseconds on the hot path; anything heavier trains/refreshes on the learning
    cadence and serves from state files.

## What "done better" means (your scoreboard, all measurable in-repo)

Report improvements as, at minimum:
- **OOS sign accuracy at 15m/1h/4h** with Wilson CIs, clean window, per method, vs today's
  decide() replayed on the SAME rows (the OPE harness gives you exact apples-to-apples).
- **Calibration** (Brier / reliability curve) of the emitted probability, because sizing and
  NO-TRADE both consume it.
- **NO-TRADE quality**: the abstention rate AND the counterfactual accuracy of what was refused
  (a good NO-TRADE band refuses worse-than-average trades; prove it, don't assert it).
- **False-LONG and false-SHORT rates separately** (the owner asked for both; short-side history
  here is scarred — B4 found short returns inverted in a gate).
- **Risk-adjusted capture**: signed move captured per decision (the OPE capture metric), and for
  live-paper candidates, realized P&L vs the concurrent control lane — never trade-count.
- **Forward validation**: an offline winner earns a paper lane (its own enter_tag / ledger
  source) and a pre-registered sample size (~100+ closed labels) before any verdict. State the
  verdict rule BEFORE the lane opens, then honor it — including retiring your own idea.
- **Control-lane governance**: today's decide() config becomes a PERMANENT control lane the
  moment you first change anything. A challenger replaces the control only after beating it
  live-on-paper at the pre-registered n — and even then the control keeps trading a small
  allocation forever as the benchmark. Never delete the control; without it, every future
  "improvement" claim is unfalsifiable.

- **The decision contract**: whatever architecture wins, each decision must still emit — machine-
  readably, as decide() does today via its weights dict + the direction ledger — the side,
  calibrated probability, confidence, the contributing sources with their weights, the regime/
  conditioner context it was made under, and, on NO-TRADE, WHICH uncertainty refused the trade
  (thin evidence vs conflicting evidence vs hostile regime). The owner must be able to ask "why
  this side?" about any trade and get a real answer from recorded state.

Every progress claim you make must be auditable against a tool result from the session that made
it. If you can't point to the artifact, you don't report the claim.

## Freedom (this is the part that is genuinely yours)

Within the laws, EVERYTHING is on the table: new decider architectures beside Hedge (Bayesian
model averaging, regime-switching HMM/Kalman gates, GNN over the lead-lag graph, transformer/
temporal models over the vote-vector history, meta-labeling stacks, conformal or e-value gates
for NO-TRADE, causal screens for the feature set, information-theoretic lens pruning — the B1
study showed the 14-lens table is ~5-7 real opinions, so redundancy reduction is live prey),
new features from the mirror's book/flow/liquidation streams, chart-vision reads as a lens,
disagreement-as-signal, per-symbol vs pooled deciders, horizon-specialized deciders (the 4h/15m
asymmetry is begging for one), sequential-testing NO-TRADE bands, and anything else you can
justify from first principles. Two candidates this repo's own audits point at, which nobody has
tried: **selection-conditioning** — the scanner hands you a symbol BECAUSE it moved, and
research/audits/pct-change-is-contrarian-20260716.md measured that selection pressure; the
pick's lane/preset/rank is a free, information-bearing conditioner the decider currently never
sees. And **evidence half-life** — reliability buckets weight a week-old outcome equal to an
hour-old one; a recency-decayed (or drift-tested) reliability estimate is a one-parameter
change with a clean OPE test. Kill your own darlings: an idea that fails its pre-registered
test dies in the ledger with a written negative result — **a rigorous "this doesn't work and
here's why" is a valued deliverable, not a failure.** Log each such verdict as one file in
`research/fable5/lessons/`.

Prefer improving/refitting what exists over adding modules; prefer removing a noise source over
adding a clever one; add a new component only with a measured benefit its absence can't explain.

## Boundaries and pauses

- Don't redesign the trading system, the scanner, execution, or risk. Don't touch NSE.
- Don't modify truth-ledger HISTORY (quarantine patterns exist; follow them) — append, never
  rewrite.
- Pause and ask the owner only for: real-money anything, deleting/renaming shared state files,
  spending money, parallel WRITE agents, or a change whose blast radius exceeds the direction
  subsystem. Everything else: decide and proceed; you are running unattended.
- If a run is interrupted, your first act on resume is re-reading `research/fable5/lessons/`
  and the ledger — never re-run an experiment whose verdict is already written.

## Deliverable shape (for a reader who did not watch you work)

A running mission log in `research/direction-brain-mission/` — grounded findings first (what you
re-measured and what contradicted the docs), then each experiment: hypothesis → pre-registered
test → artifact paths → verdict. Final summary in plain language: what the Direction Brain now
does differently, the measured before/after on the scoreboard above, what you tried that failed
and why, and what you'd try next with more data. Write it so the owner (not a coder) can read it
top to bottom.

Begin by fact-checking the pipeline end to end yourself — symbol arrives → lenses read → weights
applied → side/abstain emitted — and verifying every number in this prompt against the live
ledger. Where this prompt is wrong, the ledger wins, and saying so loudly is your first win.
