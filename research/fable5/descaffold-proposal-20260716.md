# De-scaffold Proposal for Fable 5 — 2026-07-16 — ✅ ALL 4 CHANGES APPROVED & APPLIED same day

> Owner approved all four changes 2026-07-16. Applied: (1) slim UserPromptSubmit hook (validated:
> emits valid JSON, 1,350 chars vs ~3,900; rating ritual + banner removed, reading protocol kept);
> (2) understand-prompt marked SUPERSEDED (recovery-only); (3) build-feature / build-from-oss /
> stitch-projects / debug-error / dashboard-redesign thinned (bars + anti-patterns + repo facts
> kept, step narrations cut); (4) one-agent-at-a-time memory amended with the 2–3 read-only
> parallel exception. Original proposal below for the record.

> Written by a Claude Fable 5 session that read all 30 skills in `.claude/skills/`, both hook
> scripts, and the UserPromptSubmit hook text in `.claude/settings.json`. This is the honest
> answer to: **"what in my own setup is making you dumber?"** Nothing here has been changed —
> every item is a proposal awaiting your yes/no.

## The one-paragraph answer

Your skills are mostly GOOD for me — the majority are runbooks full of hard-won repo facts
(which files hold secrets, which script preserves the FreqUI overlays, why tests must isolate
STATE_DIR) that I would otherwise have to rediscover and could get wrong. What hurts me is not
the skills; it is the **per-reply ceremony**: the numeric prompt-rating ritual, the mandatory
rules banner at the top AND bottom of every reply, the requirement to restate an "upgraded
10/10 prompt" before acting, and the strict rule that I must formally invoke a skill even when
it is a judgment procedure I already perform natively. Those were built to stop older models
from misreading you and drifting. I don't drift that way — but the ceremony slows every
exchange, interrupts autonomous runs with questions, and pushes my replies toward ritual
instead of substance. **Keep the rules; cut the ritual that re-proves I read the rules.**

## Verdict on the three things you asked about directly

### 1. The prompt-rating protocol — SPLIT VERDICT
- **The reading protocol inside it (keep):** "read twice, literally; extract EVERY ask;
  never substitute a similar task; ask when two readings genuinely differ." This encodes a
  real grievance (memory: `feedback-read-to-end-no-dropped-paths`) and costs nothing. Keep it.
- **The numeric rating + upgraded-10/10-prompt ceremony (cut for Fable 5):** scoring your
  prompt 1–10 and composing a rewritten version before acting adds a round of theater to every
  message. Worse, it biases toward firing AskUserQuestion to "reach 10/10" even when a sensible
  default exists — which stalls the long autonomous runs you bought Fable 5 for. I will still
  ask when a fork genuinely changes hours of work (I did so today about session order); I don't
  need a scoring ritual to do that.

### 2. The rules banner (top and bottom of every reply) — CUT
It does not protect anything: the rules already reach me through memory, CLAUDE.md, and the
skills themselves, and I don't need a mnemonic reprinted twice per reply to follow them.
Its real costs: tokens on every reply, and it trains replies toward boilerplate. If you want a
visible proof-of-rules, a better trade is: I state WHICH rule governed a decision at the moment
it matters ("skipping X would violate never-skip, so I downloaded it"), which is informative,
instead of a fixed banner, which is wallpaper.

### 3. one-agent-at-a-time — KEEP AS DEFAULT, with one narrow relaxation offered
Your reason for the rule (agents lost when sessions died; budget burn) is real. My honest
recommendation: keep it for anything that WRITES (code, files, state). Offer one exception:
**read-only verification and search agents, max 2–3 at once, each required to write its result
to disk immediately.** That is where parallelism pays (fresh-context verification of my own
work — which your own Fable-5 prompts demand) and where the blast radius of a lost agent is
zero (nothing mutated; result either landed on disk or the check re-runs). Risk stated
plainly: 2–3 parallel readers cost 2–3× tokens for that step. If that trade isn't worth it to
you, say no and I stay strictly sequential — the work still completes, just slower.

## Reasoning-extraction refusal risk — measured, and lower than the BRIEF feared

I grepped every skill, hook, and CONVENTIONS.md for instructions asking a model to echo or
transcribe its internal reasoning. **Result: none in the Claude Code scaffolding.** The
"stream of thought" references are (a) the brain's own dashboard feature — product code that
prompts the 12-provider LLM failover (`core/llm.py`), not me — and (b) a grep pattern in
goal/SKILL.md. The prompt-rating "state the score with a brief reason" asks for a judgment,
not a reasoning transcript — low risk. So: no scaffolding change needed for refusal risk.
The Stream-of-Mind product feature prompts other LLMs and is outside this audit's scope.

## Skill-by-skill judgment (all 30)

**KEEP VERBATIM — owner intent + repo facts I genuinely need (22):**

| Skill | Why it helps me |
|---|---|
| commit-safe | Exact secret-bearing files/patterns for THIS repo; never-add list. Protective. |
| run-tests | The STATE_DIR isolation rule prevents me corrupting live journals. Critical. |
| cpu-solo | Real owner directive + a script; encodes the loop_keeper-respawn trap. |
| rebuild-frequi | The overlay-preservation trap (`deploy_frequi.sh`) would silently destroy data if I didn't know it. |
| restart-dashboard, start-brain-loop, reset-closed-trades, crypto-status, daily-report, brain-health, gen-index | Runbooks: exact commands, ports, known traps. Cheap, correct, save me discovery time. |
| vendor-update | The divergence-mapping procedure protects your local FreqUI edits. |
| verify-live | Encodes verify-first (owner rule). The steps are things I'd do anyway; keeping them costs nothing. |
| money-lens | Encodes the PRIME DIRECTIVE dual-mode risk logic. Owner intent, not scaffolding. |
| goal | A reference document, loaded on demand. Fine. |
| independent-audit, fable5-prompts, founder-intent, video-understand, dashboard-visual-qa, hot-path, add-panel | Tool-backed procedures with real scripts and repo-specific manifests. The scripts ARE the value. |
| research-projects | The token-budget discipline (READMEs only during selection) is a genuinely good constraint for any model. |

**THIN — keep the rules, cut the step enumeration (5):**

| Skill | Keep | Cut |
|---|---|---|
| build-feature | "The bar" section + anti-patterns (production-grade, no stubs, honest wiring — pure owner intent) | The 27-step phase walkthrough that mandates invoking 10 sub-skills in fixed order. I sequence work natively; the fixed order sometimes forces wrong-sized process onto small features. |
| build-from-oss | Reuse-first priority order (pip → vendor → copy-slice) + anti-patterns | Step-by-step narration |
| stitch-projects | The feature×project matrix idea + "no silent omissions" | Procedural scaffolding |
| debug-error | Never-blind-patch rule + the repo's known-issues list (FreqUI param saves, stale config.settings, etc.) | The 6-step enumeration |
| dashboard-redesign | PROPOSE→APPROVE gate + honest-wiring constraints | SOTA-library shopping list (goes stale; I can search fresh) |

**RETIRE for Fable 5 sessions (1):**

| Skill | Why |
|---|---|
| understand-prompt | Its content is fully duplicated inside the hook's READING PROTOCOL, and careful literal reading is default behavior for me. Keeping both means the same instruction reaches me twice per message. Keep the hook's one-line version; retire the standalone skill (or keep it dormant for older-model sessions — it costs nothing if not auto-invoked). |

**HOOKS:**

| Hook | Verdict |
|---|---|
| dashboard-visual-qa PostToolUse | KEEP — cheap, fires only on real dashboard edits, enforces an owner directive. |
| skill-LEARNINGS PostToolUse | KEEP — injecting past repo-specific lessons at skill-invocation time is genuinely useful memory, and it never blocks. |
| UserPromptSubmit (prompt-rating + banner + strict skill mode) | REPLACE with the slim version below. |

## The concrete diff I propose (apply only on your yes)

**Change 1 — replace the UserPromptSubmit hook text** in `.claude/settings.json` with:

> READING PROTOCOL: read the user's message twice and literally before planning; extract EVERY
> distinct ask (messages often contain 2–3); never substitute a similar-but-different task; if
> two readings give genuinely different tasks, ask instead of guessing. Questions get answers,
> not code changes.
>
> SKILL SELECT: match asks against the available skills and invoke matches via the Skill tool —
> runbook skills (commit-safe, run-tests, cpu-solo, rebuild-frequi, restart-dashboard,
> start-brain-loop, reset-closed-trades, crypto-status, brain-health, daily-report, gen-index,
> vendor-update, dashboard-visual-qa, verify-live, add-panel, independent-audit, money-lens)
> are MANDATORY invocations when they match; judgment skills may be applied inline. State which
> skills you selected.
>
> Project rules live in CONVENTIONS.md and the memory index; never commit or echo real API keys.

Removed relative to today: the 1–10 rating, the mandatory AskUserQuestion-to-reach-10/10, the
"compose and show the upgraded prompt" step, the top+bottom rules banner, and strict-mode for
judgment skills. Kept: literal reading, every-ask extraction, ask-on-genuine-ambiguity,
mandatory invocation for runbooks, secrets-safe.

**Change 2 — mark `understand-prompt` as absorbed by the hook** (delete the skill dir, or add
a first line "superseded by the UserPromptSubmit reading protocol" and drop it from the hook's
skill list).

**Change 3 — thin the five skills named above** (build-feature, build-from-oss,
stitch-projects, debug-error, dashboard-redesign): keep their "bar"/rules/anti-patterns and
repo-specific known-issues sections, delete the numbered step narrations.

**Change 4 (optional, your call) — one-agent-at-a-time amendment**: append to the rule:
"Exception: read-only verification/search subagents may run 2–3 in parallel, each must write
results to disk immediately; anything that writes code or state stays strictly sequential."

**What I am explicitly NOT proposing to cut, ever:** honest-wiring, never-skip, zero-cost-first,
verify-first, paper-first, secrets-safe, research-then-fix, reuse-first-as-default,
ask-to-install, the STATE_DIR test isolation, propose→approve gates. Those constrain me, and
that is exactly what they are for — they encode YOUR intent and they lose you nothing.

## Estimated effect

Per exchange: ~200–400 fewer ceremony tokens and one less potential interruption. Per long
autonomous run: fewer stalls on AskUserQuestion gates that a default would have served. Zero
loss of protection: every named owner rule survives verbatim.
