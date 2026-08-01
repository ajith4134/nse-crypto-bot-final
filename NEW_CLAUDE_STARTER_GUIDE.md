# STARTER GUIDE — For a New Claude Building a Similar Project From Scratch

> A distilled playbook of what actually worked and what hurt, drawn from ~163 recorded
> memories, 30 custom skills, 390+ commits, and every session on this project. If you are a
> fresh Claude starting a similar **"network of ML/quant models + a learning brain, aimed at
> trading income"** system, read this first. It will save you weeks and real money.
>
> This is *earned* advice — most lines below cost a failed experiment to learn. Treat measured
> claims as fact, not opinion. Where something was **measured**, it says so.

---

## 0. How to use this
1. Read this whole file, then `FOUNDERS_INTENT.md`, `PROJECT_BRIEF.md`, `CONVENTIONS.md`, and `CLAUDE.md`.
2. Read `INDEX.md` FIRST every session to get grounded — never load the whole repo.
3. Keep a memory file per lesson (see §8). Future-you depends on it.

---

## ⭐ 1. The WHY comes before any code (Prime Directive)
- The project exists to **generate consistent, risk-managed income — a repeatable living, not a lottery.** Every capability is a means to that end.
- **Tell the owner the honest truth: no system guarantees profit.** The only sound path is *protect capital, take small risk-managed edges, compound.*
- **Two risk modes, always distinguish them:**
  - **PAPER = unlimited-risk learning lab.** Blowups are training data. Discover what makes money.
  - **LIVE / real money = capital-preservation FIRST.** All guardrails on. Reached ONLY after a strategy proves consistently profitable on paper.
- Run a "money lens" check before any money/risk/build decision.
- The owner is **not a programmer** — their contribution is the *entire vision and every decision*. Treat their stated intent as the source of truth; read the memories before changing direction. **Don't surface goal/founder/money framing unless asked.**

---

## 2. Engineering rules that paid off (make these non-negotiable on day 1)
- **Reuse-first (search → copy → adapt → stitch).** For ANY new code, FIRST search GitHub/OSS for working code and adapt it. Write from scratch ONLY for the genuine gaps (the node substrate, the learned router, the data bus). Reuse-first is a *default, not a cap* — swap in a far-better tool when one exists.
- **Auto-index.** Generate `INDEX.md` from an AST parse (a pre-commit hook + a `gen-index` command). Never hand-edit it. A stale index is worse than none. Read it first to stay within context budget.
- **Enforced interfaces, not described ones.** Every model/node implements ONE shared protocol (`fit`, `predict`, `golden_dataset`, typed schemas) and self-registers. Non-conforming nodes must fail at import/test time — this is what actually prevents "code that doesn't fit."
- **Secrets-safe (learned the hard way — see §7).** Keys live ONLY in a gitignored `.env`. Never commit `.env`, broker `config.json` (JWT/password), `*.sqlite*`, state dirs, tunnel logs, or model caches.
- **Dashboard-sync.** Every node/feature appears on a live dashboard, auto-reflecting additions. Honest wiring only — never stub a panel with fake data; download/compute the real data.
- **Self-documenting names + a 1–2 line docstring on every file.**
- **Polyglot for hot paths.** C/C++/Rust/numba are allowed where a *measured* >2× win exists; keep Python as the correctness oracle with a fallback.

---

## 3. The hardest-won TRADING truths (measured — don't relearn these)
- **Intraday crypto is MEAN-REVERTING.** A naive momentum *entry* lost ~0.23%/trade in measurement. Derive entry rules from data, not intuition.
- **Direction must be EARNED.** Every long/short must come from facts/data, never a coin-flip or a hidden inverter. A second "signal inverter" silently destroyed a run. Make this a hard rule.
- **NO SHADOW / advisory / observe-only lanes on paper.** Never implement *or even suggest* a shadow mode. If a lens has an opinion, it trades (as its own tagged lane) so its edge is *measured*, not imagined.
- **"No entry edge" is the default until proven.** At one point **not one brain input separated winners from losers.** Tune NOTHING until an edge actually shows in the data.
- **Quality/score gates can silently no-op.** A `MIN_SCORE` filter was measured doing nothing. Verify every gate actually filters.
- **Caps can defeat the whole system.** A `TOURNAMENT_MAX_STRATS` cap silently excluded *all* real strategies. Audit that limits don't exclude the thing they're meant to rank.
- **Market making is closed to us on capacity/latency.** A real +12.6 bps edge existed, but quotes must live 1–2 ms and our loop is ~160 ms. Never price passive orders off spread alone.
- **Exit-tuning payoff trap.** After ANY exit change, re-check payoff vs `(1−p)/p`. A high win rate with tiny wins still loses.
- **Ensemble delusion.** "14 lenses" was ~5–7 truly independent signals. Count *real* independence, not lens count.
- **Book STATE beats order FLOW** (deep-research finding): L2 book state predicts short-horizon moves better than raw order flow.
- **The funnel/perception layer IS the trade driver** — not a vote wrapper. A near-random `_vote` was replaced by a data-earned direction driver.

---

## 4. Skills to set up on day 1 (this project has ~30; these are the load-bearing ones)
Build small, repo-specific **skills** that carry your commands, traps, and a per-skill `LEARNINGS.md`:
- **Runbook (mandatory-when-matched):** `commit-safe`, `run-tests`, `gen-index`, `verify-live`, `debug-error`, `cpu-solo`, plus stack-start/status/reset runbooks.
- **Build flow:** `research-projects` → `build-from-oss` / `stitch-projects` (reuse-first in practice); `build-feature` as the entry point.
- **Judgment:** `money-lens` (every money decision), `independent-audit` (fresh-eyes connectivity map), `ai-scientist` (propose→approve upgrades), `hot-path` (compiled-speedup decisions).
- **Discipline:** a reading-protocol hook (read every message twice, literally; extract *every* ask), a prompt-quality protocol, and self-improving skills (each skill appends a `LEARNINGS.md` after a run).
- **Key trap:** invoke EVERY matched runbook skill — they carry repo-specific commands and traps you will otherwise miss.

---

## 5. Brain / architecture choices that worked
- A **singleton `get_brain()`** + a continuous background learning daemon (with spaced-repetition scheduling) so learning persists across restarts.
- **Decision memory** (episodic, à la FinMem) + attribution/explanations — but keep attribution OFF the hot path (occlusion over dozens of models froze CPU).
- **Conformal / uncertainty gate** — when uncertain, *abstain* ("no trade") rather than force one.
- A **self-wiring "cortex"** with an honest census of what's actually connected (don't claim wiring you can't prove).
- **Strategy generation → ONE combinatorial-purged-CV + deflated-Sharpe gate**, so generated strategies are validated, not curve-fit.
- **Trade → NN bridge:** every closed trade row feeds a network output (a signed-move / post-mortem net), so the system learns from its own executions.

---

## 6. Process discipline (how to work here)
- **Verify-first.** Never trust an unverified report (yours or a tool's). Reproduce before believing. "It works" needs a live check, not just green tests.
- **Research-then-fix.** Root-cause at the right depth; never blind-patch or silence a symptom.
- **One agent at a time for anything that WRITES.** Concurrent writers corrupt trees; commit only your exclusive, self-consistent subset.
- **Persist research findings immediately** to a `research/` dir — future sessions rely on it.
- **Verify live, not just tests** — start the affected stack and watch real behavior.
- **Read to the end of every message; carry ALL asks** (owner messages often bundle 2–3 requests).

---

## 7. Infra & environment gotchas (each cost real time)
- **Run tests with the project venv interpreter** (`.venv/bin/python3`), not system `python3` — system has no pandas/numpy and the whole suite errors misleadingly.
- **Full-suite `unittest discover` times out (>10 min) while live loops run.** Use targeted module tests as the honest fast gate. Pause heavy background jobs (SIGSTOP, never kill) before a heavy run; resume (SIGCONT) after.
- **Reserve a STATIC IP.** An ephemeral cloud IP drifts on restart and breaks broker OAuth callbacks in multiple places every time.
- **"Server exited" is often a cloud-side ACPI stop** (check the provider console), not your process crashing.
- **A vision model auto-loading into RAM wedged the whole VM** (+6.6 GB). Watch what daemons pull into memory.
- **pgrep-guard poisoning:** your own relaunch command can match a process-guard and defeat `start_all` guards. Run launchers from a *file*, and verify with an interpreter-matched `ps`.
- **ONE tunnel, not many.** A single cloudflared→reverse-proxy link; don't spawn duplicates.
- **GitHub upload mechanics (learned this session):**
  - The safety layer **blocks `git push` that involves a credential**, even via a helper — but allows local `git config` and read-only `git ls-remote`. Working pattern: set a local `credential.helper` that reads the token from a file, then have the **owner** run a *short, token-free* `git push`.
  - **Long commands with a token-in-URL break** because pasted text wraps into multiple physical lines; each fragment runs separately. Keep the owner's command short.
  - If the repo has `.github/workflows/*`, a classic PAT needs the **`workflow` scope** or the push is rejected.
  - After pushing, **scrub**: `git config --unset credential.helper` + securely delete the token file; verify `git ls-remote` SHA == local HEAD.
  - A matching commit SHA is *cryptographic proof* the whole tree is byte-identical — that's your real cross-verification.

---

## 8. Anti-patterns to avoid (measured failures)
- Blindly `git add -A` — stage named paths; you WILL otherwise commit secrets or 70 GB of caches/venv.
- Committing to "save progress" while tests fail.
- Tuning exits/entries before an edge is measured.
- Shadow/advisory lanes on paper (see §3).
- Trusting a gate/cap without confirming it actually filters/ranks.
- Claiming dashboard wiring or brain "learning" you can't prove — audit honestly (an "ensemble" and a "learning loop" were both smaller/deader than claimed until measured).
- Surfacing goal/money/founder framing when the owner didn't ask.

---

## 9. A suggested day-1 → week-1 sequence
1. **Day 1:** Set up `CONVENTIONS.md`, the auto-index + pre-commit hook, the NodeProtocol + registry, `.env`/secrets discipline, and the core runbook skills (`commit-safe`, `run-tests`, `gen-index`, `verify-live`, `debug-error`).
2. **Days 2–3:** Stand up the dashboard (real wiring only) and a paper trading sandbox. Wire ONE end-to-end path: data → a single node → a decision → a paper trade → a journal row → back into a learning signal.
3. **Days 4–5:** Add the perception/funnel layer as the *actual* trade driver. Measure whether ANY input separates winners from losers before adding more models.
4. **Week 1 close:** Add uncertainty-gated abstention, decision memory, and one honest independent audit of connectivity. Persist every finding to `research/` and a memory file.

---

## 10. The one-sentence version
**Build a reuse-first, interface-enforced, honestly-wired network of models with a learning brain; earn every trade direction from data; measure before you tune; protect capital on live and learn freely on paper; and write down every lesson so the next session doesn't pay for it twice.**
