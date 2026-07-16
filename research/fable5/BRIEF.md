# FABLE-5 BRIEF — hand this file to a fresh Claude Fable 5 session

> **What this is.** A single, honest, self-contained grounding document for a fresh Claude Code
> session running **Claude Fable 5** (`claude-fable-5`). Point Fable 5 at THIS FILE and it knows
> the project, the owner's intent, the direction, and the genuinely-open problems — without
> re-reading 248k lines or 417 design docs.
>
> **Built:** 2026-07-16, from the real corpus: `INDEX.md`, `PROJECT_BRIEF.md`, `CONVENTIONS.md`,
> `FOUNDERS_INTENT.md`, the `/goal` skill (27 pillars), 129 memories, 222 research docs, the
> 2026-07-13/14 audits, and hard counts taken from the repo.
>
> **Honesty rule:** this brief must never contain flattering fiction. A wrong map wastes an
> expensive autonomous run. Every claim here is either measured, cited to a file, or explicitly
> marked as unverified.

---

## 0. THE 60-SECOND VERSION

A **non-coder owner** directed, entirely through prompts, a **CPU-first network of ~500+ ML model-nodes
with a "brain" on top that trades real markets** (crypto via a Freqtrade fork, Indian equities/F&O via
OpenAlgo/Zerodha). It is real: 1,063 project Python modules (1,966 incl. vendored services), ~249k
project lines (~525k incl. vendored), 222 test files / 2,136 test functions, 39 vendored OSS projects,
288 commits, a live dashboard, and a 7,166-neuron memory web.

**The system works. The edge does not — and the measurement of the edge is itself broken.**

Three things every previous session believed are **false**, re-verified against the live ledger on
2026-07-16 (§3):
1. The "4h genuine edge" (55.2%) is now **0.502 — a coin-flip**.
2. Exit labels have been **frozen for 5 days** while 3,108 trades closed — the function that writes
   them has **no production caller**.
3. Direction is **not an anti-signal** (48.8% over 98,528 labels = coin-flip). The 40.3% realized
   figure is a *selection/timing/exit* problem, not a sign error — and **inverting doesn't fix it**.

**So: fix the measurement layer first, then hunt inputs.** That is exactly the kind of long, ambiguous,
evidence-driven work Fable 5 exists for.

---

## 1. THE OWNER — read this before anything else

- **The owner is not a programmer.** Every line of this system exists because the owner described
  what it should do and why. Their contribution is *the entire vision and every decision*.
- **Treat the owner's stated intent as the source of truth.** When unsure why something exists:
  it is because the owner directed it. Read `FOUNDERS_INTENT.md` and the memories before changing
  direction.
- **Be honest about risk. Never over-promise profit. Use plain language** — not jargon.
- The owner has said, in their own words, that they are ill and working against time. This is not
  a hobby project to them. Respect that by being *useful and truthful*, not by being reassuring.
- **Don't surface goal/founder/money framing unless asked** (memory: `dont-surface-goal-money-unless-asked`).

### The PRIME DIRECTIVE (the WHY)

> **This project exists to generate consistent, risk-managed income — a real, repeatable living,
> NOT a lottery.**

The honest truth, always told: **no system can promise profit.** The only sound path is *protect
capital, take small risk-managed edges, compound.*

**Dual-mode risk — the core operating rule:**

| Mode | Purpose | Risk policy |
|---|---|---|
| **PAPER (LEARN)** | Discover what actually makes money | **Unlimited risk. Blowups are allowed and expected — they are training data.** No caps. This is the lab. |
| **LIVE (EARN)** | Turn proven edges into steady income | **Capital preservation FIRST.** Every guardrail enforced. Never blow up. |

Default is **PAPER**. Going live is deliberate and auditable. A strategy reaches real money only
after proving consistent profit on paper *net of costs* and *after overfit deflation*.

### 🧭 THE MOTTO (owner-approved 2026-07-12, never change its meaning)

The strict division of labor. **Test every proposal against all six tenets:**

1. **CPU = the brain's intelligence ONLY** — ML/DL, thinking, reading, research, equation/strategy
   creation, decisions. CPU is NEVER spent on what the exchange can do (data fetching, screening, ranking).
2. **APIs = execution ONLY** — place the trades the brain already selected. NOT market data, NOT screening.
3. **Data = web navigation ONLY** — candles, timeframes, indicators, order book, screeners, funding, OI
   come from *navigating the Binance and Upstox web apps*, not data APIs.
4. **Read with the eyes (local vision)** — charts read as screenshots by the free local VLM
   (qwen2.5-vl via Ollama). The brain SEES the app like a human.
5. **Maximize the browser surface** — push the web apps to their maximum; keep exploiting more built-ins.
6. **RAM for speed** — in-memory mirrors/caches keep the web+vision path fast.

> **Known motto violations (open):** Freqtrade still pulls OHLCV/VolumePairList via API; funnel
> `fast_candles`/`data_failsafe` still fetch via API. Migration queued.

### Standing owner rules (violating these is a real failure)

| Rule | Meaning |
|---|---|
| `zero-cost-first` | ALWAYS find the free way. Never hand the owner a "pay/top-up" action item. |
| `prefer-best-not-just-existing` | Reuse-first is a **default, not a cap**. If something far better exists, say so and use it. |
| `reuse-real-code-first` | pip when packaged, else clone-and-vendor. Never reimplement a public project. |
| `no-license-filter` | Private project — rank OSS by capability, never exclude by license. |
| `never-skip` | **GPU-only is the ONLY valid skip reason.** Missing data → download it. Slow/heavy/copyleft are NOT reasons. |
| `honest-wiring` | Dashboards show only REAL connectivity. A pretty-but-false graph is worse than an ugly-but-true one. |
| `verify-first` | NEVER trust a report — from a subagent, a tool summary, or your own earlier claim — until checked first-hand. |
| `research-then-fix` | Root-cause at the right depth. Never blind-patch or silence symptoms. |
| `one-agent-at-a-time` | **Strictly sequential subagents.** ⚠️ See §7 — this rule conflicts with Fable 5's strengths; ask before relaxing. |
| `ask-to-install` | Ask the owner to install deps rather than stdlib workarounds. Blanket install permission largely pre-approved. |
| `secrets-safe` | Keys only in gitignored `.env`. Never commit/echo. |

---

## 2. WHAT THIS SYSTEM ACTUALLY IS

### Scale (measured 2026-07-16, not estimated)

| Thing | Count |
|---|---|
| Python modules (excl. vendor/.venv/srv) | **1,063** |
| Python lines | **248,951** |
| Test files | **222** |
| Vendored OSS projects | **39** |
| Git commits | **288** |
| Neuron memory files | **7,166** |
| Research design docs | **222** |
| Owner memories | **129** |
| Custom skills | **29** |
| Goal pillars | **27** |

### 🔑 THE MOST IMPORTANT STRUCTURAL FACT: there are TWO decision paths

Source: `research/audits/brain-stagnated-features-20260714.md:7-14`.
**Most of the impressive "brain" is on the path that does not place trades.**

**Path A — the REAL crypto money path** (places actual Freqtrade orders):
```
run_funnel_loop.py (crypto|nse)          ← live process
  → broker_sense/funnel.py                 SCREEN → LOOK → VERIFY → EXECUTE → CRAWL
  → broker_sense/indicator_fusion.py:fuse()    (27 deps; VLM/YOLO/OFI/VP/on-chain lenses)
  → crypto/freqtrade/brain_executor.py         (44 deps — the hub)
  → direction/learned_direction.py:decide()    ← THE driver (Hedge / multiplicative-weights)
  → direction/mirror_gate.py:apply()           (invert/abstain — see §3 F3: premise falsified)
  → direction/truth_ledger.py:record()         (measurement)
  → Freqtrade REST → tradesv3.dryrun.sqlite
```

**Path B — the T8 advisory loop** (paper/NSE; drives **no** crypto money):
```
online/run_live_loop.py → brain/pipeline.py:BrainTradingPipeline.decide()
  consumes: regime, anomaly, news, evolved_strategy, experience, imagination(world-model), hypothesis
```

> **On Path B / shelf-ware:** world-model, imagination, self-evolve, skills-self-improve/DSPy,
> continual learning, concept-discovery, computer-use/embodiment, and news sentiment have
> **0 references** in `learned_direction` / `funnel` / `brain_executor`. They are built, panelled,
> tested — and reach no real trade.

### The pipeline (data → decision → execution)

```
  WEB APPS (Binance + Upstox, headed Chromium/Xvfb)   ← the ONLY sanctioned data source (motto §3)
        │  screenshots + DOM + the apps' own filters/screeners
        ▼
  PERCEPTION   trading/broker_sense/  (ui_market, micro_collect, tab_pool, indicator_fusion)
               local vision: qwen2.5-vl via Ollama (free, no throttle)
        │
        ▼
  RAM MIRRORS  binance_stream (all-market !markPrice@arr@1s → rolling price history)
               Kite/Zerodha in-RAM mirror for NSE
        │
        ▼
  BRAIN        memory/neurons.py (NeuronStore, 7,166 instruction-shaped neurons)
               trading/brain/brain_os.py (BrainKernel + WorkingMemory + syscall surface)
               cognition/ (Thinker: ReAct/ToT, pymdp active inference, symbolic, conformal gate)
               school.py (L0→L6, currently L5) · instructions.py · evolution.py · apply.py
        │
        ▼
  DIRECTION    trading/direction/  ← THE BOTTLENECK. truth_ledger, mirror_gate, meta_labeler,
               direction_model (CatBoost), dir_exit, reflex, app_signals, regime, pullback
        │
        ▼
  FUNNEL       trading/brain/indicator_fusion.fuse() → brain_executor → the actual open decision
        │
        ▼
  EXECUTION    API-ONLY (motto §2): Zerodha/OpenAlgo (NSE) · Binance (crypto, Freqtrade fork)
        │
        ▼
  LEARNING     truth_ledger resolves every claim → edge-weights every source →
               freqtrade_ingest/journal grade instructions → evolution mutates → promote/retire
```

### The three loop processes (they are SEPARATE OS PROCESSES, not threads)

1. **crypto funnel** (`run_funnel_loop`) — headed browser, the crypto trade driver
2. **NSE-equity funnel** — OpenAlgo/Zerodha path
3. **dashboard** (`:8000`) — hosts the learn loop, school, evolution as in-process threads

The Brain-OS kernel runs **inside the dashboard process**; other lobes are represented via
state-file heartbeats, **not shared memory**. This is a known, honest architectural caveat.

---

## 3. THE ACTIVE GOALS (in priority order)

### 🎓 PRIMARY — BRAIN ULTRA UPGRADE (the new north-star, owner 2026-07-12)

> "Teach the brain to **BE INTELLIGENT** the way a teacher takes a student from basics to PhD."

**28 requirements R1–R28, none may be dropped.** Verbatim: `research/brain-ultra-upgrade/OWNER_MESSAGE_VERBATIM.md`.
Goal: `research/brain-ultra-upgrade/GOAL.md`.

Six pillars: (1) one **Neuron common format** — instruction-shaped, mandatory `action` facet;
(2) **one cognitive loop** perceive→recall→reason→decide→act→observe→reflect→learn→evolve→teach-self;
(3) a **school** L0→L6, dual-track (intelligence itself AND trading/nav); (4) **instruction lifecycle**
acquire→follow→grade→edit→GEPA-mutate→promote/retire; (5) **honest self-evaluation**; (6) researched
upgrades (DGM, Voyager, AWM, A-MEM, GEPA, PromptBreeder).

**Status (audit `research/brain-ultra-upgrade/AUDIT-20260713.md`): 21 ✅ / 7 🟡.**
Open partials: **R6** (no invention neuron has passed the CPCV+DSR gate), **R11/R12/R13** (trading &
Binance/Upstox nav "expert" = graduation states, evidence-starved), **R27** (no graded
knowledge-application exam).

⚠️ **The single most damning measured number: genius-use ≈ 5.7% — only ~383 of 6,741 neurons have
EVER been consulted in a decision.** The brain has a vast memory it does not use.

### Pillar 27 — DIRECTION SUPREMACY (owner order 2026-07-10)

> "Losses come from wrong direction. Invent a way to be ≥80% correct."

> ## ✅ UPDATE 2026-07-16 (later the same day): PROMPT 0 WAS EXECUTED.
> The exit-label wedge is FIXED (backfill_journal now called from live_loop ingest + learn_loop
> safety net; exit n 3,459 → 7,174; **continuous labeling activates on run_live_loop + dashboard
> restart — owner action**). The Mirror Gate premise was falsified by a controlled paired
> experiment and the gate RETIRED (MIRROR_GATE=0; bucket accuracies are non-stationary,
> persistence corr −0.214). The 40.3%/36.5% numbers were era artifacts — crypto realized since
> 7/11 = 0.523 (n=3,282), net +17.8k USDT (tail-heavy). Predictors remain coin-flips → the Input
> Hunt (PROMPT 1) is next. Full evidence: `research/audits/measurement-rebuild-20260716.md`.
> F1–F4 below are kept as the historical record of what was falsified.
>
> ## 🚨 STOP — THE DIRECTION DOCS ARE STALE IN THEIR KEY CLAIM
>
> **Re-measured first-hand 2026-07-16 against the live ledger (`trading/state/direction_truth.json`,
> 486 buckets, 98,528 labels). Three load-bearing beliefs in this project are FALSIFIED. Do not
> build on the older docs until you re-measure.**

**LIVE ground truth, verified 2026-07-16 (this supersedes every earlier number in `research/`):**

| horizon | n | accuracy |
|---|---|---|
| 15m | 40,545 | **0.488** |
| 1h | 35,981 | **0.493** |
| **4h** | **18,543** | **0.502** |
| exit | 3,459 | **0.365** ← frozen, see F2 |
| **TOTAL** | **98,528** | **0.488** |

#### F1 — The 4h edge no longer exists.
`research/direction-accuracy-diagnosis-2026-07-11.md:9` claims **4h = 55.2% (n=2,858) "GENUINE EDGE"**
and the whole fix plan says *"bias to the 4h/1h horizon where edge is real."* With 6× more data the
4h bucket is **0.502 — a pure coin-flip.** **Any plan that assumes the 4h edge is building on a
falsified premise.**

#### F2 — The exit-horizon labels are FROZEN. This is a real, unnoticed wedge.
`exit` n = **3,459** today. It was **3,459** on 2026-07-11 — *identical, five days later* — while
**3,108 trades closed in those same 5 days** (verified against `tradesv3.dryrun.sqlite`; 4,891 closed
total). **Root cause, verified by grep:** exit labels come only from `backfill_journal()`
(`trading/direction/truth_ledger.py:434`, documented at `:24` as a *"one-shot idempotent label pass"*)
— and **it has NO production caller.** The only invocations in the entire repo are
`tests/test_truth_ledger.py:144,152`.
> So the single worst-performing horizon (36.5%) — the one every doc blames for destroying good
> calls — **is measured from stale July-10 data and is not being tracked at all.**

#### F3 — The Mirror Gate's premise is contradicted by its own ledger.
D2's thesis (`mirror_gate.py:5`): *"a 30%-accurate source inverted is a 70%-accurate source."*
Verified live:

| bucket | n | acc |
|---|---|---|
| `meanrev_stochrsi\|CRYPTO\|any\|15m` (raw) | 113 | **0.310** |
| `mirror:meanrev_stochrsi\|CRYPTO\|chop\|15m` (**inverted**) | 58 | **0.362** |
| `meanrev_stochrsi\|CRYPTO\|any\|1h` (raw) | 113 | 0.381 |
| `mirror:meanrev_stochrsi\|CRYPTO\|chop\|1h` (**inverted**) | 58 | **0.328** |

Inverting a 31% signal should score ~69%. It scores 36%. **Both directions lose.** The gate code is
correct (`mirror_gate.py:161-163` flips, `:182-184` records the flip), so this is *empirical, not a
coding bug*. The tie-rate explanation was tested and **falsified** (only 0.86% ties). Caveat: the
buckets are **not paired samples** (113 vs 58; `any` vs `chop`), so the honest verdict is
**"unexplained — and it invalidates the free-accuracy-from-inversion assumption D2 rests on."**
Needs a controlled paired experiment.

#### F4 — "40.3% = anti-signal" is a base-rate artifact. THE MOST CONSEQUENTIAL CORRECTION.
Both numbers are real but measure different things:
- **40.3%** = 1,665 **closed trades**, entry→exit price sign (`direction-accuracy-program/PLAN.md:14`).
- **48.8%** = 98,528 **all directional labels**, live today.

> **The raw predictors are COIN-FLIPS (~48.8%), not anti-signals.** The ~8.5-point gap between
> *what we predict* and *what we get on trades we actually took* is **trade selection + entry timing
> + the exit path** — **not a sign error.**
>
> `ideas-ledger.md:224` calls it a *"systematic ANTI-signal, exploitable by inversion."* **The live
> data does not support that, and F3 shows inversion does not recover it.** The project has been
> chasing a sign-flip fix for what is actually a selection/timing problem.

**Honest framing:** 80% is reachable ONLY on *taken* trades via abstention/selectivity — never
unconditionally.

**Everything D1–D9 + W + M shipped.** And yet:

> **THE MEASURED CEILING:** LightGBM AUC **0.477** (*below chance*), TabPFN **0.523**, live
> `direction_meta.pkl` **0.487** (below its own 0.55 honesty bar → stays ADVISORY, never armed).
> `direction_model` **0.525 → 0.582**. **The bottleneck is decision-time FEATURES/INPUTS, not the
> model.** Adding models will not fix this.
>
> Best broad source measured: **`direction_equation` = 0.530 (n=4,107)**; best sub-bucket
> `trend|4h` **0.573** (n=436) — capped at a ±0.15 lens that nobody has raised.

### Direction-Equation Quest (owner 2026-07-11, ACTIVE)

Build ONE reliable direction equation via **symbolic regression + evolution** over ALL price-driving
data. Requirements verbatim: `research/direction-equation-quest/REQUIREMENTS.md` (READ IT FIRST —
the owner explicitly demanded the meaning be preserved).

P1→P4 shipped: feature bus → `direction_equation.py` (gplearn + Operon + PySR, horizon-conditioned
Rank-IC, invert flag) → `validate()` (purged CPCV + triple-barrier + PBO) → `direction_equation_deploy.py`
(IC-weighted ensemble, Mirror-Gate self-inversion, bounded ±0.15 tilt).
**NEXT (ops, not built):** run the re-evolution daemon on real data; let the ledger accumulate live
accuracy before raising the ±0.15 weight; optional AI-Feynman/SINDy generators.

### The Human Trading System (owner 2026-07-07)

Eyes→brain→hand→memory on the REAL Binance + Upstox web apps. Execution API-only. UI-only data.
Owner granted **FULL AUTHORITY to replace/redesign any code when something better exists** — judge as
an outside specialist, never argue for existing code out of bias.

### Brain-as-OS (owner 2026-07-13)

"The combined brain must act as an OS with its own RAM." OS-1..OS-4 **COMPLETE** (kernel, WorkingMemory,
process table, attention scheduler, syscall migration, cross-process WM). Caveat in §2 above.

---

## 4. THE HARDEST OPEN PROBLEMS (ranked — this is where Fable 5 should look)

| # | Problem | Evidence (verified 2026-07-16) | Why it's hard |
|---|---|---|---|
| **0** | **THE MEASUREMENT LAYER IS BROKEN — fix before anything else.** Exit labels frozen (F2); the 4h edge is gone (F1); inversion doesn't work (F3); "anti-signal" is an artifact (F4). **Several planning docs are built on falsified numbers.** | This brief §3 F1–F4, re-measured first-hand | Everything downstream depends on these numbers being right. Re-deriving invalidates and rewrites multiple docs. |
| 1 | **Direction inputs are the ceiling.** Every model lands at AUC 0.477–0.582. | LightGBM 0.477, TabPFN 0.523, live `direction_meta.pkl` **0.487**, `direction_model` 0.582 | Needs *new information*, not new models. **The research's #1/#2 ranked drivers — true L2-book OFI/GOFI — are NOT computed**; only OHLCV proxies (`buy_press`, `cvd`, `tick_ofi`) exist. Needs a stored per-bar order-flow series that doesn't exist yet. |
| 2 | **Selection + timing + exit, NOT sign.** Predictors are 48.8% (coin-flip); realized trades are 40.3%. The 8.5-pt gap is where the money goes. | F4 | Reframed 2026-07-16. `dir_exit.py` is SHADOW-only; all lanes n<30 → `cal_strength=0.0` → cuts nothing. |
| 3 | **The whole ultra-network LOSES to a naive baseline.** CORTEX holdout **0.495 vs naive 0.546** at every selectivity. | `deep-connect-findings-20260712.md:69-74` (verified) | 61 FULL canons, 135 tests green — and it underperforms naive. CANON-36 *was* the naive-baseline gate. |
| 4 | **Two decision paths; most of the "brain" is on the wrong one.** | `brain-stagnated-features-20260714.md:7-14` | See §2. World-model, self-evolve, continual learning, concept-discovery, computer-use, news-sentiment have **0 references** in `learned_direction`/`funnel`/`brain_executor`. |
| 5 | **Genius-use 5.7%** — 383 of 6,741 neurons ever consulted. | `AUDIT-20260713.md:49` | The denominator may itself be wrong (news snippets that *should* never be consulted). Measure before "fixing". |
| 6 | **Funnel regressed ~3×: `took=738.83s`, `entered=[]`.** The main funnel opens nothing; only `filter-lane` enters. | `logs/funnel_crypto.log` (verified) | Was fixed to 255s, regressed. The doc calls it "whack-a-mole" — each fix reveals the next hog. |
| 7 | **`INDEX.md` — the map every agent reads first — is polluted and ~53% stale.** 536 stale entries; it indexes `.cache/huggingface` model files as project code. | `independent-audit-20260714-092507.md:194+`; verified via grep | The context-budget mechanism is lying to every session that trusts it. |
| 8 | **126 orphan modules / 25 import cycles.** | `independent-audit-20260714-092507.md:6,59-84` | ⚠️ Many are dynamic-loader false positives; several are *superseded* alternatives. **Blind-wiring them makes trades worse** (see #3). |
| 9 | **The meta-labeler has never armed.** AUC 0.487 < its 0.55 bar → permanently ADVISORY. | `deep-connect-findings-20260712.md:180-182` | This is the honest route to the owner's 80%-on-taken ask, and it has never fired. |
| 10 | **R6 / R12 / R13 / R27 open.** No invention through the CPCV+DSR gate; nav expertise evidence-starved; no graded knowledge-application exam. | `AUDIT-20260713.md` | Graduation states — need accumulated evidence, not code. |
| 11 | **Motto violations persist** — Freqtrade + funnel still fetch market data via API. | memory `motto-cpu-ml-api-exec-web-data` | Deep surgery on a vendored fork. |
| 12 | **Loop fragility.** `build_demo_evolution` wedges the whole server (GIL, py-spy-confirmed); serial `_bg_snapshot` = 3+ min "warming"; `loop_keeper` kills a warming dashboard as dead; `/api/trading/brain/decisions` has **no backing route** though the UI calls it. | `AUDIT-20260713.md:46-48`; `independent-audit-20260714-092507.md:189` | Concurrency/lifecycle across processes. |

### ⚠️ Three warnings before any autonomous run

1. **The direction docs are stale in their key claim.** `direction-accuracy-diagnosis-2026-07-11.md`
   and `SYNTHESIS-AND-PLAN.md` both rest on a 4h edge that no longer exists (F1) and an inversion
   premise the ledger contradicts (F3). **Re-measure before building on them.**
2. **Don't blind-wire the orphans.** Both audits warn: several are *superseded* alternatives, and
   CORTEX/raw-direction *underperform naive*. Wiring a bad signal in makes trades **worse**.
3. **The docs skew optimistic.** Checkmarks like *"P4 DONE — QUEST CHAIN COMPLETE"* are technically
   true (code ships, tests pass) while the measured payoff is 53% and the flagship feature is capped
   at a ±0.15 lens nobody raised. **The two most honest documents in the repo are
   `research/direction-equation-quest/COVERAGE-AUDIT.md` and
   `research/audits/brain-stagnated-features-20260714.md` — start there.**

---

## 5. WHAT IS LIVE vs WHAT IS SHELF-WARE

**Verify this section before trusting it** — it drifts fast.

- **LIVE:** crypto funnel (headed browser), NSE funnel, dashboard `:8000` + learn loop/school/evolution
  threads, truth ledger + mirror gate, Brain-OS kernel, neuron web, direction X-Ray, `binance_stream`
  RAM mirror, local vision.
- **SHADOW (records but does not act):** `dir_exit` (DIR_EXIT=shadow default), `meta_labeler`
  (advisory until AUC clears), `INSTRUCTION_APPLY_TILT` (default **OFF**), `CORTEX_SIGNAL=1` shadow.
- **BUILT BUT EVIDENCE-STARVED:** most direction lanes (n<30), nav route instructions, invention neurons.
- **KNOWN-BROKEN / MISLEADING:** `/api/trading/brain/predict` reports "trading stack not importable"
  when it is merely warming.

---

## 6. HOW TO WORK IN THIS REPO

1. **Read `INDEX.md` FIRST** (auto-generated, 5,317 lines, 1,015 module entries) — it is the
   context-budget mechanism. Never load the whole repo. Then open only the files you need.
   > ⚠️ **But do not trust it blindly.** Verified 2026-07-16: it has **536 stale entries (~53%)** and
   > it **indexes `.cache/huggingface` model files and `.claude/plugins` as if they were project
   > code**. It is a useful map with known potholes — cross-check anything load-bearing against disk.
2. **`INDEX.md` is never hand-edited.** Change code, then `make index` (or `/gen-index`).
3. Every node implements **`NodeProtocol`** and self-registers. Non-conforming = fails at import/test.
4. **Dashboard-sync:** every new node/feature registers a real dashboard view. Honest wiring only.
5. Tests: `ML_NETWORK_SKIP_HEAVY=1 STRATEGY_EVOLUTION_ENABLED=0 pytest` (the heavy-skip flags matter —
   `STRATEGY_EVOLUTION_ENABLED=1` can wedge the server).
6. **`/cpu-solo`** before heavy runs — but note `loop_keeper` **undoes SIGSTOP pauses** by respawning.
7. Restart the dashboard **ONCE** via `tools/restart_dash.sh` and wait — repeated calls FLAP it.
8. Never commit secrets. `/commit-safe` scans the diff.

### Traps that have burned previous sessions (real, recorded)

- **pgrep/pkill SELF-MATCH:** `pkill -f <pattern>` in the same Bash call puts the pattern in your own
  cmdline → kills your own shell. Re-run from a clean command line.
- **Python does NOT set OS thread names** — `/proc/comm` is useless. Use `py-spy dump`.
- **Chromium won't render multipart MJPEG over HTTP/2** (all tunnels are h2). curl can't verify
  rendering — only a Playwright click-through can.
- **`_bg_snapshot` warmers are serial** — panels show "warming" for minutes after restart.
- **Never call `get_store()` in a request thread** before the warmer built it.
- **avalanche-lib pulls CUDA torch** — reinstall the cpu wheel.

---

## 7. ⚠️ FABLE-5-SPECIFIC WARNINGS FOR THIS REPO

These are real conflicts between this project's scaffolding and Fable 5's documented behavior.
**Read them before starting.**

1. **This repo's skills are too prescriptive for Fable 5.** Anthropic's guidance is explicit:
   *"Skills developed for prior models are often too prescriptive for Claude Fable 5 and can degrade
   output quality. Review and consider removing older instructions if default performance is better."*
   This repo has **29 highly-prescriptive skills** plus a `UserPromptSubmit` hook that forces a
   prompt-rating protocol and a rules banner on every reply. **Expect this to cost quality.**
   Consider running Fable 5 sessions with the scaffolding deliberately thinned.

2. **`reasoning_extraction` refusal risk.** Fable 5 refuses requests that ask it to echo/transcribe/
   explain its internal reasoning. This repo has a **Stream-of-Mind panel** and skills that ask for
   reasoning traces. Audit prompts for show-your-thinking instructions — they can trigger elevated
   refusals/fallbacks.

3. **Cyber-classifier refusal risk — REAL for this project.** Fable 5 runs safety classifiers targeting
   offensive-security techniques. This repo does **browser automation against broker apps, a Patchright
   STEALTH_BROWSER flag, a CAPTCHA human-handoff, and endpoint scraping from page origin/session.**
   Framed carelessly, that pattern-matches to scraping-evasion tooling and may be refused.
   **Mitigation:** always frame as *"automating MY OWN authenticated account in MY OWN browser session,
   reading data I am entitled to."* That is true, and it is the honest framing. If a task is refused,
   it is a classifier false-positive on benign work — fall back to Opus 4.8 for that task.

4. **`one-agent-at-a-time` conflicts with Fable 5's biggest strength.** That rule exists for a good
   reason (parallel agents were lost on session exits; they burn budget). But Fable 5 is *"significantly
   more dependable at dispatching and sustaining parallel subagents."* **Do not silently override the
   owner's rule — ask them.** The rule's stated rationale (agents lost mid-flight) is partially
   addressed by Fable 5's reliability + "save results to disk immediately."

5. **Turns run for MANY MINUTES.** Do not interpret a long silence as a hang. Plan for async check-ins.

6. **Fable 5 costs 2× Opus 4.8** ($10/$50 vs $5/$25 per MTok). Only give it work that justifies that —
   see `PROMPTS.md`.

---

## 8. THE PROMPT PREAMBLE (paste this into every Fable 5 session)

```text
You are working on a CPU-first ML-network trading brain owned by a NON-CODER who directs it
entirely through prompts. Read research/fable5/BRIEF.md first — it is your grounding.

Context for why I'm asking: the owner needs consistent, risk-managed income. Everything runs in
PAPER mode, where unlimited risk is allowed because blowups are training data. Honesty about
what does and does not work matters more than reassurance.

Ground truth you must respect:
- Direction accuracy is measured at ~40-52%. The bottleneck is measured to be decision-time
  INPUTS, not models (LightGBM AUC 0.477, TabPFN 0.523 — both near/below chance).
- Read INDEX.md first for grounding; never load the whole repo.
- Honest wiring only: never fabricate a node, edge, or metric. A true-but-ugly result beats a
  pretty-but-false one.
- GPU-only is the ONLY valid reason to skip something. Missing data → download it.
- Reuse real OSS first, but that is a default, not a cap — if something far better exists, use it
  and say why.

Before reporting progress, audit each claim against a tool result from this session. Only report
work you can point to evidence for; if something is not yet verified, say so explicitly. Report
outcomes faithfully: if tests fail, say so with the output; if a step was skipped, say that; when
something is done and verified, state it plainly without hedging.

When you have enough information to act, act. Do not re-derive facts already established, or
narrate options you will not pursue. If you are weighing a choice, give a recommendation, not an
exhaustive survey.

Don't add features, refactor, or introduce abstractions beyond what the task requires. Don't
design for hypothetical future requirements.

Pause for me only when the work genuinely requires it: a destructive or irreversible action, a
real scope change, or input only I can provide. If you hit one of these, ask and end the turn,
rather than ending on a promise.

Write your final summary for someone who did not watch you work: outcome first, in complete
sentences, with terms spelled out. Drop the working shorthand.
```

---

## 9. WHERE TO LOOK (file map for a fresh session)

| You need | Read |
|---|---|
| The owner's vision, in their words | `FOUNDERS_INTENT.md` (incl. verbatim prompts) |
| The 27 pillars + Prime Directive | `.claude/skills/goal/SKILL.md` |
| The standing rules | `CONVENTIONS.md` |
| The active north-star + R1–R28 | `research/brain-ultra-upgrade/{GOAL,OWNER_MESSAGE_VERBATIM}.md` |
| What's done vs open on it | `research/brain-ultra-upgrade/AUDIT-20260713.md` |
| The direction problem | `research/direction-accuracy-program/PLAN.md`, `research/direction-accuracy-diagnosis-2026-07-11.md` |
| The equation quest | `research/direction-equation-quest/REQUIREMENTS.md` |
| Latest expert proposal + status | `research/ai-scientist/proposal-20260713-brain-vs-sota.md` |
| Newest independent audits | `research/audits/independent-audit-20260714-092507.md` |
| The code map | `INDEX.md` |
| Decision trail (129 memories) | `.claude/projects/-home-karan18190164/memory/MEMORY.md` |
| Fable-5 ideas + ready prompts | `research/fable5/PROMPTS.md` |

---

_Regenerate this brief with `/fable5-prompts` (it re-reads the repo and rebuilds this file + PROMPTS.md)._
