# CONVENTIONS — Standing Rules for This Project

> These rules exist to stop the #1 failure mode of agent-built codebases:
> the agent assumes wrong things about existing code, writes new code that
> doesn't fit, and you end up with large files that don't talk to each other
> plus orphaned/dead code. Every coding step MUST follow these.

A one-line banner of the active rules is shown at the top of every reply:
`Rules: prompt-rating | reuse-first | ask-to-install | polyglot | auto-index | enforced-interfaces | secrets-safe | dashboard-sync | never-skip`

---

## 1. Self-documenting names
- File, class, and function names must describe **what the code does**, so the
  name alone conveys purpose (e.g. `reservoir_node.py`, `class RegimeChangeNode`,
  `def predict_next_close(...)`).
- Each file starts with a 1–2 line module docstring: what it does, its inputs,
  its outputs.

## 2. Auto-generated index (`INDEX.md`) — never hand-edited
- A machine-generated manifest maps **every file → its functions/classes,
  imports, exports, input types, output types, and a 1-line summary**.
- It is regenerated from the code (AST parse) via `make index` and a pre-commit
  hook. **A stale index is worse than none**, so humans/agents never edit it by
  hand — they change the code and regenerate.
- The coding agent reads `INDEX.md` FIRST to get grounded, then opens only the
  specific files it needs. This is also the **context-budget** mechanism — never
  load the whole repo.

## 3. Enforced interfaces, not described ones
- The index *describes* contracts; the type system *enforces* them.
- Every node implements a shared **`NodeProtocol`** (`fit`, `predict`,
  `golden_dataset`, typed `InputSchema`/`OutputSchema` via Pydantic or
  `typing.Protocol`). A node that doesn't conform **fails at import/test time**,
  not after merge. This is what actually prevents "code that doesn't fit."
- Nodes self-register in a **registry**, so wiring cannot be silently wrong.

## 4. Reuse-first / search-copy-adapt-stitch (build-from-scratch is LAST resort)
- For ANY new code or feature: **FIRST search online — GitHub and other open-source —
  for working code that already does it.**
- If you find similar/working code, **copy it and edit/adapt it to fit our needs**
  (match our `NodeProtocol`/interfaces). Don't reinvent what already exists.
- **Prefer stitching multiple OSS pieces together** — connect different/many GitHub or
  open-source projects/snippets into the solution — over writing original code.
- Reuse mature OSS libraries too (AutoGluon, ReservoirPy, nolds, ruptures, Mem0,
  Graphiti, sigma.js…); if a library needs installing, request it (→ ask-to-install).
- **Write code from scratch ONLY when no similar code exists anywhere** to find/adapt
  (the genuine gaps: the node-graph substrate, the learned router at depth, the node
  interface/data bus). See `ml-network-master-plan.md`.

## 5. No orphans / no dead code (automated)
- CI runs dead-code detection (`vulture`) + an import-graph check. Orphaned files
  or uncalled functions **block the merge**. Don't rely on discipline.

## 6. Dashboard-sync (every node & feature is visible)
- **Every new node, feature, or intelligence/learning capability MUST register a
  dashboard view** when added — nothing ships invisible.
- Dashboard stack: **Web — React + D3/Three.js** (3D node graph, real-time data
  flows, animated learning/accuracy metrics). New additions auto-reflect via a
  registry the dashboard reads.
- **HONEST WIRING (no fake) — load-bearing.** Every node, edge, input, output and
  data-flow shown on the dashboard MUST reflect the REAL architecture, derived
  only from the live registry/`state.json` (real `feature_names`, real per-node
  `input_dim`/`upstream`, real terminal predictors). NEVER fabricate nodes, edges,
  inputs, outputs or flows just to look like a diagram. If a connection is drawn,
  it must be a true data dependency in the project (e.g. feature→node only when
  the node consumes that feature; node→meta only from the real `upstream`;
  node→output only for real terminal predictors). A pretty-but-false graph is
  worse than an ugly-but-true one. Visual layout (layering/animation) is free to
  arrange; the *connectivity it depicts* is not.

## 7. Secrets-safe
- Real API keys live ONLY in a gitignored `.env` (template: `.env.example`),
  loaded via `config.py`. Never commit, print, or store real keys (not in code,
  logs, memory, or commits). Pasted keys are treated as compromised.

## 10. Polyglot for performance (not Python-only)
- The project is **not limited to Python**. Use C, C++, Rust, etc. for any hot
  path where it meaningfully improves speed, latency, memory, or throughput —
  expose it to Python via a clean boundary (CFFI/ctypes, PyO3, subprocess, or a
  small service) so it still slots behind `NodeProtocol`.
- Pure Python stays the default for correctness/iteration; drop to a compiled
  language when profiling shows a real bottleneck (e.g. node training loops,
  distance computations, reservoir state updates).
- Needing a toolchain (gcc/clang/cargo) triggers §9 **ask-to-install** — request it.
- Keep the interface identical so swapping a Python node for a compiled one is invisible to the graph.

## 9. Ask-to-install (dependencies & data)
- When the project would genuinely benefit from a new package, dataset, model, or
  any download, **ask the user to install/provide it** rather than reimplementing
  it in pure stdlib or settling for a weaker existing option.
- Surface: what's needed, why, the exact install command (e.g. `pip install scikit-learn`),
  and the size/cost if notable. The user runs the install (or approves it).
- This refines §4: reuse-first means *use the best mature OSS* — and if it needs
  installing, request the install instead of building a workaround.
- **NEVER-SKIP rule (load-bearing).** The ONLY acceptable reason to skip a model,
  feature, node, or library is that it **requires a GPU** (no CPU path). Nothing
  else justifies skipping: if a node needs **extra data, DOWNLOAD it** (free/no-key
  sources first; ask for a key only if unavoidable); slowness, heaviness, copyleft
  license, or a different paradigm (e.g. RL) are NOT reasons to skip — build it
  (slow/standalone is fine, just keep it off the fast hot-path). When something is
  GPU-only, say so explicitly and note any CPU alternative.

## 8. Prompt-quality protocol (workflow rule)
- Every user prompt is rated 1–10; missing info is gathered to reach a 10/10
  before execution. (Enforced by a UserPromptSubmit hook.)

## 11. Verify-first (never trust unverified reports)
- **NEVER trust a report — from a subagent, a tool summary, or my own earlier
  claim — until I have checked it MYSELF against the real code / real error /
  real command output.** A subagent saying "tests pass" or "no secrets tracked"
  is a hypothesis, not a fact, until I re-run the check and see it.
- Concretely: re-run the test, read the actual file, `grep` the real tracked
  list, hit the live endpoint, look at the real screenshot. Relay results only
  after first-hand confirmation; if I relayed something unverified, say so.
- Applies doubly to claims of success ("it works", "all green", "fixed") and to
  anything safety-relevant (secrets, deletions, accuracy gates).

## 12. Error-research (online + in-project) before fixing
- On ANY error or inconsistency: don't guess a fix. First (a) **scan THIS project
  and its git history** for where a similar problem was already solved (reuse the
  proven pattern), and (b) **search online** for the error / library behaviour to
  find the established solution. Then apply the evidence-based fix.
- Prefer a fix already used elsewhere in the repo (consistency) over a novel one.
  Record the root cause, not just the patch.

## 14. Multi-dataset evaluation (never crypto-only)
- A node/feature/network is NOT validated on one dataset. Every capability must be
  testable on **multiple, diverse data types**: crypto, **Indian equities (NSE/BSE)**,
  and at least one **non-financial dynamical series** (e.g. sunspots/solar, weather/
  climate, energy demand, ECG/physiological). Prefer free/no-key sources; download
  per §9 never-skip.
- Datasets with genuine, measurable signal are preferred (the project proves accuracy
  rises as the network learns) — synthetic dynamical benchmarks stay the default dev
  data, real datasets are swapped in via a data-source switch.
- The dashboard/runners expose a data-source selector so any node can be evaluated
  across sources; report honest per-dataset metrics (no cherry-picking one dataset).

## 13. Never-skip (GPU-only is the ONLY skip reason)
- The ONLY acceptable reason to skip a model, feature, node, or library is that it
  **requires a GPU** with no CPU path. Build everything else.
- If a node needs **extra data, DOWNLOAD it** (free/no-key sources first — e.g.
  Deribit public options API, Binance L2 via the collector; request a key only if
  unavoidable, per §7). Slowness, heaviness, copyleft license, redundancy, or a
  different paradigm (RL → a separate policy/execution layer) are NOT skip reasons
  — build it (slow/standalone is fine, kept off the fast hot-path).
- When something is genuinely GPU-only, say so explicitly and note any CPU
  alternative used instead.

---

## 15. NO SHADOW ON PAPER (load-bearing, owner rule 2026-07-16)
- **Never implement — and never even SUGGEST — a "shadow", advisory-only, observe-only,
  dry-run-within-dry-run, or flag-gated-OFF variant of anything on the PAPER path.**
  Do not offer it as an option, a "safe first step", a phase 1, or a compromise.
  The owner has ruled it out; re-proposing it is itself the violation.
- **Why:** paper (Freqtrade `dry_run`) IS the experiment and the sandbox. There is no
  capital to protect, so shadowing it is shadow-on-shadow — zero safety bought, pure
  redundancy. It is also **dishonest measurement**: a shadow vote is graded on prediction
  alone, so it never faces entry timing, exit timing, fees, or slippage — exactly where this
  brain loses (measured 2026-07-16: exit horizon **0.4427** vs 0.4887–0.5092 on clock
  horizons). Shadow grades the half that already looks fine and skips the broken half.
- **Instead:** on paper, wire it to ACTUALLY TRADE and judge it on realized P&L.
  **Full access for experimenting** — any size, any risk, any lens; a blown-up paper
  account is training data, not a failure. Never ask permission to take paper risk.
- **The one hard requirement in the lab:** every outcome (win or wipeout) MUST be logged and
  fed back — journal, truth ledger, hypothesis ledger. An unlogged blowup teaches nothing.
- **Real limits still apply:** no real money, no real keys, no `.env`/`config.json` secrets
  (§7), keep the crypto↔NSE market-isolation boundary, and never restart production loops
  (owner action).
- **Shadow/flag-gating stays CORRECT for real-money paths only.** The mistake this rule
  bans is importing LIVE-mode caution into the lab (see `/money-lens` PAPER vs LIVE).

---

## 16. EVERY DIRECTION IS EARNED — never a coin flip, never an inversion (owner rule 2026-07-16)

**The owner's words:** *"I need the brain to open trades' direction based on its FACTS, DATA and
KNOWLEDGE, and every decision calculated and backed with EXPERIENCE and LEARNING — instead of a coin
flip or inverting."*

- **A trade's side must be the OUTPUT OF EVIDENCE.** It comes from measured, learned structure — the
  fused inputs, the model, the truth ledger's *proven* sources — and every entry must be able to
  answer *"what did I know that made this a LONG?"* with a real reading, not a leftover default.
- **NEVER invert a signal you have not PROVEN is reliably wrong.** *Absence of evidence that a source
  is right is NOT evidence that its opposite is right.* A source at 0.49 is not a 0.51 source wearing
  a mask — it is **noise**, and flipping noise produces confident nonsense. Inversion is legitimate
  ONLY when the whole confidence interval sits below 0.5 **and** the effect clears `min_edge`.
  Statistically indistinguishable from a coin flip → **IGNORE the source entirely**.
- **NEVER trade a coin flip.** No side by default, by fallback, by `rate < 0.5`, or "the model was
  quiet so we went long". **If nothing is proven, ABSTAIN** — no trade is a valid, honest decision;
  a guessed one is not. (This is why `learned_direction.decide()` abstains rather than forcing a side.)
- **Underpowered ≠ wrong.** ~260 observations give ~12% power at realistic effect sizes (~540 needed
  for 80%). A sub-0.5 reading on a few hundred trades is *unresolved*, not *anti-signal*. Treating it
  as anti-signal is what produced 31 SHORT vs 1 LONG and −112 P&L, shorting coins that rose +13%.
- **Every decision must be auditable after the fact.** Log what was read, its weight, and why —
  `decision_snapshot` + `entry_vector` exist for exactly this. A direction you cannot reconstruct
  from recorded evidence is not knowledge; it is a guess with good PR.

### 16b. A COIN FLIP IS A TRIGGER, NOT AN ANSWER (owner, same day)

*"If anything looks 50/50 or coin-flip, I need you to SUGGEST until we find evidence or fix it and
find the data-driven answer — so we won't just leave it at that and say 'it is what it is' until we
solve it. Give me ALL the suggestions and ask me questions."*

**Abstaining is the correct TRADE. It is never the end of the WORK.** Whenever a reading lands at
~50/50 — a source, a gate, a model, a metric — that is a **red flag to investigate**, not a fact to
accept:
- **Say it out loud.** Name the thing that is 50/50 and that it is unresolved. Never bury it.
- **Never close with "it is what it is."** "The signal is a coin flip" is a *finding*, not a
  *conclusion*. The conclusion is *why*, and what would change it.
- **Always produce SUGGESTIONS** — the concrete candidates that could turn noise into evidence:
  better inputs, a conditioner we never recorded, the wrong horizon, a labeling error, a leak, a
  power problem (n too small), a regime we pooled across.
- **Always ask the owner questions** when the next step needs a decision only they can make
  (what to spend, what to risk, which direction to pursue).
- **Prefer "we cannot resolve this yet, here is what would" over silence.** An honest unknown with a
  plan beats a confident guess AND beats a shrug.

**The distinction that matters:** *underpowered* ("we can't tell yet — here's the n we'd need"),
*unproven* ("measured, no edge found — here's what to try next"), and *proven-wrong* ("CI entirely
below 0.5 — invert it"). Collapsing the first two into the third is exactly the bug §16 exists to
prevent, and collapsing them into "shrug" is what this clause exists to prevent.

**WHY (the scar):** an inverter inside `learned_direction._signed_weight` returned `weight 0.0` while
STILL returning `invert=True` for sources whose CI straddled 0.5 — so the brain flipped pure noise
into confident shorts. It hid for months behind spot mode (which refuses shorts) and only surfaced
when the futures segment was repaired. Killed 2026-07-16; pinned by
`tests/test_learned_direction.py::TestNoiseIsNeverInverted`. The "invertible anti-signal" premise was
ALREADY falsified as an era artifact ([[direction-premises-falsified-20260716]]) — inversion has now
failed twice (Mirror Gate, then this). **A third attempt needs proof, not a hunch.**

---

### Definition of Done for any coding task
1. Names follow §1; module docstring present.
2. `INDEX.md` regenerated (§2).
3. New node/component conforms to `NodeProtocol` + registered (§3).
4. Reused OSS where possible; new-from-scratch justified (§4).
5. No dead code / orphans (§5 passes CI).
6. Dashboard view registered for any new node/feature (§6); wiring is real (honest, §6).
7. No secrets touched tracked files (§7).
8. Every "it works / passes / fixed" claim was VERIFIED first-hand (§11), not taken on trust.
9. Nothing skipped except GPU-only (§13); extra data downloaded when a node needs it.
10. Nothing on the paper path is shadow/advisory/flag-gated-off (§15) — it trades for real on
    paper and every outcome is logged back to the learning stores.
