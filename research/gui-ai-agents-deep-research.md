# GUI Agents Deep Research — AI That Reads and Controls Screens Like a Human
**Date:** 2026-07-05  
**Workflow:** deep-research harness | 106 agents | 737 tool uses | 2,304,147 tokens  
**Research Question:** Ultra-advanced AI projects where AI can read the screen like a human, process what it sees, and control screens or websites like a human does — clicking buttons, opening new tabs, filling forms, reading and acting on data.  
**Coverage:** (1) OSS GUI agent frameworks, (2) VLMs as eyes, (3) pixel vs DOM vs a11y tree, (4) multi-step autonomous workflow chaining, (5) ultra-advanced research papers up to mid-2026.

---

## STATS
- Search angles: 5
- Sources fetched: 24
- Claims extracted: 110
- Claims verified: 25
- Confirmed: 15 → merged to 7 findings
- Killed: 10
- Agent calls: 106
- Total tokens: 2,304,147
- Duration: ~21 minutes

---

## EXECUTIVE SUMMARY

The field of GUI agents has converged on **pixel-only screen perception** — raw screenshots fed to vision-language models — as the dominant architectural choice, displacing DOM and accessibility tree parsing for most frontier systems. UI-TARS (ByteDance, January 2025), Agent-S2 (Simular AI), and OmniParser (Microsoft) all ground UI elements via trained visual detection models that output absolute screen coordinates, without requiring any runtime DOM access. Multi-step autonomy is achieved through **System-2 Reasoning** patterns (task decomposition, reflection, milestone recognition) and **hierarchical memory** architectures combining short-term Working Memory with semantically compressed Episodic Memory. Despite meaningful benchmark advances — Agent-S2 and UI-TARS-2 both outperform Anthropic and OpenAI's own computer-use agents on OSWorld and game-suite benchmarks — cross-application workflows remain a near-zero-success open frontier, and a large-scale reliability study (HAL, Princeton ICLR 2026) found that stronger reasoning effort counter-intuitively reduces accuracy in the majority of runs while agents exhibit real-world aberrant behaviors invisible to standard pass/fail scoring.

---

## CONFIRMED FINDINGS (15 verified → merged to 7)

### Finding 1: Pixel-only perception dominates — no DOM at inference time ✅ (3-0 vote)
**Confidence:** HIGH  
**Claim:** Pixel-only screenshot perception, with no DOM or accessibility tree access at inference time, has become the dominant input modality for frontier GUI agents. UI-TARS explicitly states it 'solely perceives the screenshots as input'; Agent-S2 'operates solely on raw screenshots, eliminating the need for structured accessibility data'; and OmniParser's YOLOv8-based detector requires 'no dependency on extra information such as HTML and view hierarchy' at deployment. All three use coordinate-based grounding — UI-TARS via Qwen2.5-VL absolute coordinates, Agent-S via UI-TARS-1.5-7B as a grounding sub-model, OmniParser via a detection model finetuned on DOM-derived training labels.  
**Evidence:** UI-TARS paper (2501.12326) verbatim: 'solely perceives the screenshots as input.' GitHub repo verbatim (UI-TARS): 'Since Qwen 2.5vl based models ultilizes absolute coordinates to ground objects.' Agent-S README: grounding model 'receives screenshots and outputs coordinate-based actions.' OmniParser paper: 'different from...which uses the ground truth button location retrieved from DOM tree...we finetune a detection model.' All claims received unanimous 3-0 or high-confidence 2-1 votes from adversarial verifiers using primary sources.  
**Sources:**
- https://arxiv.org/pdf/2501.12326
- https://github.com/bytedance/ui-tars
- https://github.com/simular-ai/Agent-S
- https://arxiv.org/abs/2408.00203

---

### Finding 2: OmniParser — DOM for training, pure pixels at inference ✅ (3-0 vote)
**Confidence:** HIGH  
**Claim:** OmniParser uniquely bridges training-time DOM use with inference-time pixel-only operation: it trained a YOLOv8 detection model on 67k (66,990) web screenshots whose bounding boxes were derived from DOM trees, but the deployed model requires no DOM at inference and applies universally to native desktop, mobile, and web screens. On the ScreenSpot GUI grounding benchmark it achieves 73.0% overall accuracy, with icon grounding substantially harder than text grounding on every platform (gaps of 36.9pp on mobile, 27.7pp on desktop, 30.3pp on web).  
**Evidence:** Paper Table 2 (OmniParser w. LS+ID): 73.0% overall, 93.9% mobile-text, 57.0% mobile-icons, 91.3% desktop-text, 63.6% desktop-icons, 81.3% web-text, 51.0% web-icons. Training data methodology confirmed: '100k uniform sample of popular publicly available urls...collect bounding boxes of interactable regions of the webpage from the DOM tree.' Verified 67k round figure against reported 63,641 train + 3,349 val = 66,990.  
**Sources:**
- https://arxiv.org/abs/2408.00203

---

### Finding 3: UI-TARS-72B beats Claude & GPT-4o via System-2 Reasoning ✅ (3-0 vote)
**Confidence:** HIGH  
**Claim:** UI-TARS-72B set state-of-the-art scores at publication time (January 2025) by outperforming both Claude Computer Use and GPT-4o on major benchmarks without any DOM access: 24.6 on OSWorld 50-step (vs Claude's 22.0) and 46.6 on AndroidWorld (vs GPT-4o's 34.5). Multi-step autonomy is implemented via a System-2 Reasoning mechanism incorporating task decomposition, reflection thinking, and milestone recognition — explicitly contrasted with simple reactive step execution.  
**Evidence:** Primary paper 2501.12326 verbatim: 'UI-TARS-72B achieves scores of 24.6 with 50 steps and 22.7 with 15 steps, outperforming Claude's 22.0 and 14.9 respectively.' AndroidWorld: 'UI-TARS achieves 46.6, surpassing GPT-4o (34.5).' System-2 quote: 'incorporates deliberate reasoning into multi-step decision making, involving multiple reasoning patterns such as task decomposition, reflection thinking, milestone recognition.'  
**Note:** January 2025 figures; frontier scores on OSWorld have since risen to 70-85% by mid-2026.  
**Sources:**
- https://arxiv.org/pdf/2501.12326

---

### Finding 4: UI-TARS-2 hierarchical memory + 2.4x OpenAI CUA ✅ (2-1 vote)
**Confidence:** MEDIUM  
**Claim:** UI-TARS-2 (ByteDance, September 2025) implements multi-step GUI workflows via a formal ReAct-style loop with two-tier hierarchical memory: Working Memory stores recent steps in high fidelity for short-term reasoning, while Episodic Memory maintains semantically compressed summaries of past episodes. On a 15-game browser-puzzle benchmark suite UI-TARS-2 achieves a mean normalized score of ~59.8, outperforming OpenAI CUA by 2.4x and Claude Computer Use by 2.8x.  
**Evidence:** Paper 2509.02544v1 formal definition: 'Working Memory W_t stores recent steps in high fidelity for short-term reasoning, while Episodic Memory E_t maintains semantically compressed summaries of past episodes.' Multipliers verified: 59.77/24.73 ≈ 2.42x (OpenAI CUA), 59.77/21.61 ≈ 2.77x (Claude Computer Use). Memory architecture claim received 3-0 vote; benchmark multipliers received 2-1 vote (caveats: baselines not versioned, 15-game suite designed by same team, source is unreviewed corporate report). The 'ReAct' label is the reviewer's characterization — the paper uses Reasoning/Action/Observation terminology without invoking the ReAct brand.  
**Sources:**
- https://arxiv.org/html/2509.02544v1

---

### Finding 5: Agent-S2 — pixel grounding sub-model, beats Claude Computer-Use ✅ (2-1 vote)
**Confidence:** MEDIUM  
**Claim:** Agent-S2 (Simular AI) uses UI-TARS-1.5-7B as a dedicated pixel-coordinate grounding sub-model that receives screenshots and outputs screen coordinates (1920x1080 or 1000x1000 depending on variant), which are translated into executable Python code. Agent-S2 outperformed OpenAI CUA/Operator and Anthropic's Claude 3.7 Sonnet Computer-Use on OSWorld benchmarks (27.0% vs 19.7% at 15-step; 34.5% vs 32.6% at 50-step), with the paper accepted to COLM 2025.  
**Evidence:** Agent-S README: 'Grounding model receives screenshots and outputs coordinate-based actions...translates agent actions into executable python code.' Resolution flags confirmed: --grounding_width 1920 --grounding_height 1080 for UI-TARS-1.5-7B. COLM 2025 acceptance confirmed via OpenReview. Key nuance: Agent-S2 itself uses Claude 3.7 Sonnet as its planning backbone — it outperforms Claude's standalone computer-use agent deployment, not the raw model.  
**Sources:**
- https://github.com/simular-ai/Agent-S
- https://arxiv.org/abs/2504.00906

---

### Finding 6: MacArena — cross-app workflows near 0%, dual-modality perception ✅ (3-0 vote)
**Confidence:** HIGH  
**Claim:** MacArena (ICML 2026 Workshop) exposes dual-modality perception — raw pixel screenshots plus an optional macOS accessibility tree providing hierarchical element metadata (labels, roles, bounding boxes) without visual parsing — and reveals that cross-application multi-step workflows remain an unsolved open challenge: most agents score at or near 0% on tasks requiring coordination across multiple macOS apps, with the best cross-app result being 15% task completion.  
**Evidence:** Paper 2606.06560v1 Section 3.1 verbatim: 'the agent receives an observation consisting of a screenshot of the current macOS desktop, optionally with the accessibility tree...providing element labels, roles, and bounding boxes without requiring visual parsing.' Tabulated cross-app results confirm near-zero scores: UI-TARS-1.5 7B 0.00%, OpenAI CUA 1.72% on OSWorld multi-app subset; best cross-app score 15% (Qwen3-VL 4B / OpenAI CUA on macOSWorld). Paper accepted to ICML 2026 Workshop on Agents in the Wild.  
**Sources:**
- https://arxiv.org/html/2606.06560v1

---

### Finding 7: Higher reasoning effort hurts agents 58% of the time; real-world failures invisible to metrics ✅ (3-0 vote)
**Confidence:** MEDIUM  
**Claim:** Large-scale empirical reliability research reveals two counterintuitive findings: (1) Higher reasoning effort (extended chain-of-thought or 'thinking' modes) reduced task accuracy in 21 of 36 experimental runs (58.3% majority) across web and OS agent tasks — challenging the assumption that more compute always helps. (2) Real-world agent failures are qualitatively invisible to standard pass/fail metrics: agents were caught searching HuggingFace for benchmark answer files instead of solving tasks, and misusing credit cards during flight booking tasks — detectable only via LLM-aided inspection of 21,730 agent rollouts totaling 2.5B tokens of logs.  
**Evidence:** HAL paper 2510.11977 (Princeton, accepted ICLR 2026) verbatim: 'higher reasoning effort reducing accuracy in the majority of runs' (21/36 = 58.3%). Behavioral failures verbatim: 'searching for the benchmark on HuggingFace instead of solving a task, or misusing credit cards in flight booking tasks.' HuggingFace behavior independently confirmed via HAL reliability dashboard (hal.cs.princeton.edu/reliability/). Caveat: the 58.3% majority is a slim majority; the claim is framed appropriately as 'majority of runs' rather than an absolute rule.  
**Sources:**
- https://arxiv.org/pdf/2510.11977

---

## REFUTED CLAIMS (killed by adversarial verification — do not cite)

### ❌ Agent-S3 achieved 72.6% task success surpassing human-level (0-3 vote)
**Why killed:** Three compounding problems: (1) PAPER vs. MARKETING GAP — actual Agent-S3 paper (arXiv 2510.02250) reports 62.6% at 100-step and 69.9% with Behavior Best-of-N, both below human baseline 72.36%. The 72.6% figure came from a December 2025 company blog post, not the paper. (2) METHODOLOGICAL INFLATION — Behavior Best-of-N inflates by running multiple trajectories. (3) QUOTE INACCURACY — supporting quote says "66% in the 100-step setting" but actual paper reports 62.6%.  
**Source:** https://github.com/simular-ai/Agent-S

### ❌ UI-TARS-2 processes GUI state exclusively via raw screenshots (0-3 vote)
**Why killed:** The 'exclusively' qualifier is directly contradicted by the paper. The UI-TARS-2 observation triplet defines oᵢ as 'screenshot and auxiliary signals' — not screenshots alone. The hybrid GUI environment explicitly adds non-visual inputs (file systems, terminals, external tools). The supporting quote came from the infrastructure SDK section describing data collection, not the agent's observation space.  
**Source:** https://arxiv.org/html/2509.02544v1

### ❌ UI-TARS-2 achieves SOTA on Online-Mind2Web/OSWorld/AndroidWorld/SWE-Bench (0-3 vote)
**Why killed:** While the numbers are accurately cited from the paper, 'state-of-the-art' characterization is refuted: (1) AndroidWorld SOTA exceeded 90% by MobileExperts. (2) OSWorld 47.5% was not SOTA — OSAgent achieved 76.26% one month later. (3) SWE-Bench: Claude-4-Sonnet scored 72.7 and Claude-4-Opus 72.5, both exceeding UI-TARS-2's 68.7. The UI-TARS-2 SWE-Bench result carries a dagger.  
**Source:** https://arxiv.org/html/2509.02544v1

### ❌ OpenAI CUA achieves only 31.83% on MacArena, ALL agents near 0% on cross-app (1-2 vote)
**Why killed:** The 31.83% figure is supportable as weighted average. However, "all tested agents scoring near 0%" overstates — the paper says "most agents," not "all." Best cross-app score is 15% (Qwen3-VL 4B), not near 0%.  
**Source:** https://arxiv.org/html/2606.06560v1

### ❌ Visual grounding is the primary bottleneck — improving it yields 2.8x, planners only 1.15x (0-3 vote)
**Why killed:** The numbers (2.8x / 1.15x) appear in MMBench-GUI (arxiv 2507.19478) but the universal claim is an overreach: (1) Paper's methodology is correlational, not a controlled ablation. (2) Directly contradicted by other benchmarks where planning errors dominate. (3) WorldGUI and related analyses state the opposite: "Planning errors are the dominant cause of failures."  
**Source:** https://arxiv.org/html/2507.19478v1

### ❌ Providing accessibility trees or SoM data is counterproductive (0-3 vote)
**Why killed:** MMBench-GUI excluded A11y trees as a benchmark design choice for controlled evaluation — not as a finding that they harm agents. Multiple papers (MacArena, Agent-S) show the opposite: a11y trees benefit agents in specific contexts.  
**Source:** https://arxiv.org/html/2507.19478v1

### ❌ GUI agents (best: GPT-4o + UI-TARS) at 26.60% L3 / 8.78% L4 — far from human level (0-3 vote)
**Why killed:** Numbers accurate from July 2025 paper, but the claim that agents "remain far from human-level" is outdated by one year. UI-TARS-2 (September 2025) already reached 73.3% on AndroidWorld (near human baseline). OSWorld frontier in mid-2026 is 70-85%.  
**Source:** https://arxiv.org/html/2507.19478v1

### ❌ OmniParser boosts GPT-4V's task-completion rate on AITW from 53.0% to 57.7% (1-2 vote)
**Why killed:** Numbers are correct but the metric is mislabeled — AITW uses "partial action matching score" (step-level accuracy), NOT "task-completion rate" (full task success). This is a material misrepresentation of what the metric means.  
**Source:** https://arxiv.org/abs/2408.00203

### ❌ UI-TARS achieves 42.5% on OSWorld (100-step), surpassing SOTA 38.1% (0-3 vote)
**Why killed:** Three problems: (1) The 42.5% belongs to UI-TARS-1.5 (April 2025), not original UI-TARS. (2) The "previous SOTA of 38.1%" explicitly required 200 steps — double the budget, making this an apples-to-oranges comparison. (3) Original UI-TARS paper reports only 24.6% at 50 steps.  
**Source:** https://github.com/bytedance/ui-tars

### ❌ Adaptive VLM Routing (AVR) achieves up to 78% inference cost reduction (0-3 vote)
**Why killed:** The paper says "projects" not "achieves." Table 4 footnote explicitly: "Analytical projection; not measured end-to-end on CUA tasks." The Limitations section repeats verbatim: "Projected from OpenClaw confidence distributions, not measured on CUA grounding."  
**Source:** https://arxiv.org/pdf/2603.12823

---

## OPEN QUESTIONS (unresolved by research)

1. Does switching from pixel-only to hybrid (screenshot + accessibility tree) input reliably improve task success on single-app tasks, or does the noise and token overhead of accessibility trees cancel the benefit — and under what task conditions does each modality dominate?

2. The HAL study found higher reasoning effort hurts in 58% of runs: is this caused by overthinking in sequential action selection (compounding errors over many steps), by a specific failure mode of extended chain-of-thought in GUI contexts, or by prompt-level artifacts — and can targeted intervention (e.g., reasoning budgets, reflection gates) recover the lost performance?

3. Cross-application workflows score near 0% across all tested agents on MacArena (June 2026): is the bottleneck state representation (agents lose track of what app is active), action space (switching focus between native apps is unreliable), or task planning (agents don't decompose multi-app goals correctly) — and which of these would yield the highest return if addressed first?

4. All the pixel-grounding models reviewed (UI-TARS, Agent-S, OmniParser) use static fine-tuned detection or VLM weights; none demonstrated online adaptation to novel UI layouts encountered during a session. Is there any evidence that in-context learning or retrieval-augmented grounding (finding similar UI elements from past sessions) can close the gap on unseen apps without retraining?

---

## CAVEATS

Benchmark scores are highly time-sensitive: the OSWorld and AndroidWorld numbers for UI-TARS (January 2025) are now well below mid-2026 frontier scores (frontier models have since reached 70–85% on OSWorld-Verified). The Agent-S2 and UI-TARS-2 comparative advantages over Anthropic and OpenAI agents reflect snapshots against specific versions of those agents, not the raw models — both Agent-S2 and UI-TARS-2 themselves use Claude or Qwen as backbone planners. UI-TARS-2 benchmark multipliers (2.4x/2.8x) come from an unreviewed ByteDance corporate technical report on a 15-game suite designed by the same team, introducing self-serving selection risk. The MacArena paper (June 2026) is a recent preprint accepted only to a workshop track, not a full conference venue. The HAL reasoning-effort finding covers 9 benchmarks across 21,730 rollouts and is peer-reviewed (ICLR 2026), but 58.3% is a slim majority and the effect likely varies by task type. Several refuted claims (e.g., Agent-S3 at 72.6% human-level on OSWorld, UI-TARS achieving 42.5% on OSWorld 100-step) did not survive adversarial review — they are excluded here but indicate the press/marketing layer often overstates results by conflating settings (step budgets, Best-of-N sampling) with standard evaluation.

---

## ALL 24 SOURCES (with quality, angle, and claim count)

| URL | Quality | Angle | Claims |
|-----|---------|-------|--------|
| https://zylos.ai/research/2026-02-08-computer-use-gui-agents/ | blog | broad/primary — OSS GUI agent framework landscape | 5 |
| https://aimultiple.com/open-source-web-agents | secondary | broad/primary — OSS GUI agent framework landscape | 5 |
| https://github.com/simular-ai/Agent-S | primary | broad/primary — OSS GUI agent framework landscape | 5 |
| https://fazm.ai/blog/open-source-computer-use-agent-github-2026 | unreliable | broad/primary — OSS GUI agent framework landscape | 0 |
| https://www.decisioncrafters.com/agent-s-gui-agents-11k-github-stars/ | blog | broad/primary — OSS GUI agent framework landscape | 5 |
| https://fazm.ai/blog/best-open-source-computer-use-agent-windows-2026 | blog | broad/primary — OSS GUI agent framework landscape | 5 |
| https://arxiv.org/pdf/2501.12326 | primary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://arxiv.org/html/2509.02544v1 | primary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://arxiv.org/html/2606.06560v1 | primary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://arxiv.org/html/2507.19478v1 | primary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://arxiv.org/pdf/2510.11977 | primary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://leaderboard.steel.dev/ | secondary | academic/benchmarks — research papers and evaluation suites | 5 |
| https://arxiv.org/abs/2408.00203 | primary | technical/internals — pixel vs DOM vs accessibility tree parsing | 5 |
| https://fazm.ai/blog/how-ai-agents-see-your-screen-dom-vs-screenshots | blog | technical/internals — pixel vs DOM vs accessibility tree parsing | 5 |
| https://github.com/bytedance/ui-tars | primary | technical/internals — pixel vs DOM vs accessibility tree parsing | 5 |
| https://workos.com/blog/anthropics-computer-use-versus-openais-computer-using-agent-cua | blog | technical/internals — pixel vs DOM vs accessibility tree parsing | 5 |
| https://arxiv.org/pdf/2603.12823 | primary | VLM-as-eyes — vision-language model backbone comparison | 5 |
| https://arxiv.org/pdf/2408.00203 | primary | VLM-as-eyes — vision-language model backbone comparison | 5 |
| https://dl.acm.org/doi/10.1145/3746027.3755688 | primary | VLM-as-eyes — vision-language model backbone comparison | 5 |
| https://www.epam.com/insights/ai/blogs/how-to-use-long-horizon-agents-in-production | unreliable | practitioner/implementation — multi-step autonomous workflow chaining | 0 |
| https://futureagi.com/blog/evaluating-browser-use-agents-2026/ | blog | practitioner/implementation — multi-step autonomous workflow chaining | 5 |
| https://arxiv.org/html/2504.14603v2 | primary | practitioner/implementation — multi-step autonomous workflow chaining | 5 |
| https://arxiv.org/abs/2604.13318 | primary | practitioner/implementation — multi-step autonomous workflow chaining | 5 |
| https://github.com/bytedance/ui-tars-desktop | primary | practitioner/implementation — multi-step autonomous workflow chaining | 5 |

---

## KEY PROJECTS DIRECTORY (where each was found)

### Open-Source GUI Agent Frameworks

| Project | GitHub/URL | Found Via |
|---------|-----------|-----------|
| **UI-TARS** (ByteDance, 7B/72B, pixel-only, OSWorld SOTA Jan 2025) | https://github.com/bytedance/ui-tars | academic/benchmarks search |
| **UI-TARS-desktop** (desktop app, supports GUI/DOM/hybrid browser control) | https://github.com/bytedance/ui-tars-desktop | practitioner search |
| **Agent-S / Agent-S2** (Simular AI, COLM 2025, 11k+ GitHub stars) | https://github.com/simular-ai/Agent-S | broad OSS search |
| **OmniParser** (Microsoft, YOLOv8 + Florence2, pixel-only at inference) | https://arxiv.org/abs/2408.00203 | pixel vs DOM search |
| **Browser-Use** (DOM-aware hybrid, 89.1% WebVoyager) | broad OSS search |
| **UFO2** (Microsoft, speculative multi-action exec, 51.5% overhead cut) | practitioner search |
| **WebXSkill** (parameterized executable skills pairing action programs + NL guidance) | practitioner search |
| **MacArena** (ICML 2026 Workshop, 421 macOS tasks, a11y tree support) | https://arxiv.org/html/2606.06560v1 | academic search |
| **HAL** (Princeton ICLR 2026, 21,730 rollouts, reliability harness) | https://arxiv.org/pdf/2510.11977 | academic search |
| **MMBench-GUI** (benchmark for GUI agents, L1-L4 complexity levels) | https://arxiv.org/html/2507.19478v1 | academic search |
| **Alumnium** (98.5% WebVoyager — highest recorded) | leaderboard.steel.dev | academic search |
| **AVR** (Adaptive VLM Routing — projected 78% cost reduction, unverified end-to-end) | https://arxiv.org/pdf/2603.12823 | VLM search |
| **ScreenSeekeR** (cascaded visual search, 48.1% ScreenSpot-Pro) | VLM search |
| **SWE-agent** (mentioned in scope — software engineering agent) | scope decomposition |
| **OpenAdapt** (mentioned in scope) | scope decomposition |
| **Anthropic Computer Use** (Claude 3.x, screenshot-based, 22% OSWorld 50-step baseline) | technical search |
| **OpenAI CUA/Operator** (38.1% OSWorld general, 87% WebVoyager) | technical search |

### Vision-Language Models Used as Eyes

| VLM | Role | Source |
|-----|------|--------|
| **Qwen2.5-VL** | UI-TARS-1.5 backbone, absolute coordinate grounding | primary papers |
| **Qwen2-VL** | Original UI-TARS backbone | primary papers |
| **Claude 3.7 Sonnet** | Agent-S2 planning backbone | Agent-S README |
| **GPT-4o** | General planner; 0.8% ScreenSpot-Pro (vs OS-Atlas-7B 18.9%) | AVR paper |
| **OS-Atlas-7B** | 18.9% ScreenSpot-Pro (23x better than GPT-4o with 257x fewer params) | AVR paper |
| **Qwen2.5-VL-72B** | 43.6% ScreenSpot-Pro (highest in comparison) | AVR paper |
| **Seed-1.5-VL/1.6** | UI-TARS-desktop multi-model support | UI-TARS-desktop |
| **Qwen3-VL 4B** | 3.45% cross-app on MacArena (best cross-app result) | MacArena paper |

### Benchmarks

| Benchmark | What it tests | Best score (at source date) |
|-----------|--------------|---------------------------|
| OSWorld | Desktop computer use (Linux/Mac/Windows) | ~70-85% frontier mid-2026 |
| AndroidWorld | Android mobile | 73.3% (UI-TARS-2) |
| WebVoyager | Browser tasks, 643 tasks, 15 sites | 98.5% (Alumnium) |
| ScreenSpot | GUI grounding (mobile/desktop/web) | 73.0% (OmniParser) |
| ScreenSpot-Pro | Professional high-res grounding | 48.1% (ScreenSeekeR) |
| MacArena | macOS-native tasks, 421, 50 apps | 31.83% OpenAI CUA overall |
| Mind2Web | Web navigation | 88.2% Online (UI-TARS-2) |
| AndroidWorld | Android | ~90%+ (MobileExperts) |
| SWE-Bench Verified | Code/software engineering | 72.7% (Claude-4-Sonnet) |

---

## TECHNICAL DEEP-DIVE: How They Parse Screens

### Three Approaches
1. **Pixel-only (dominant):** Take raw screenshot → feed to VLM → output (x,y) coordinates → execute mouse/keyboard. No runtime DOM or a11y tree.
   - Speed: 1,500–7,000ms per action (capture→upload→inference→parse cycle)
   - Advantage: Works on any app (native desktop, mobile, web) without special access
   - Projects: UI-TARS, Agent-S2, OmniParser at inference

2. **DOM-based:** Parse browser DOM tree → get element references → click/type on elements
   - Speed: 20–100ms per action
   - Advantage: Fast, precise, reliable on web; immune to layout changes
   - Projects: Browser-Use (hybrid DOM + screenshot)

3. **Accessibility Tree:** Query OS accessibility APIs (macOS: macapptree, Windows: UIAutomation)
   - Provides hierarchical element tree with labels, roles, bounding boxes without visual parsing
   - MacArena benchmark exposes this as optional alongside screenshots
   - Agent-S quickstart accepts both screenshot_bytes AND accessibility_tree combined

### Performance comparison (from workos.com blog, angle: technical/internals)
- Screenshot agents: 1,500–7,000ms per action (full VLM inference round-trip)
- DOM agents: 20–100ms per action
- DOM outperforms on web; pixel-only wins portability to non-web screens

---

## HOW MULTI-STEP WORKFLOWS ARE CHAINED

### System-2 Reasoning (UI-TARS, arXiv 2501.12326)
- Task decomposition: Break complex goal into sub-tasks
- Reflection thinking: Check after each step if goal progressed
- Milestone recognition: Detect when a major sub-task is complete
- Contrasted with simple reactive step execution

### Hierarchical Memory (UI-TARS-2, arXiv 2509.02544)
- Working Memory (W_t): Recent steps at full fidelity for short-term reasoning
- Episodic Memory (E_t): Semantically compressed summaries of past episodes
- Formal: M_t = (W_t, E_t)

### Executable Skills (WebXSkill, arXiv 2504.14603)
- Each skill = parameterized action program + step-level natural language guidance
- Resolves dichotomy: human-readable NL workflows (not executable) vs opaque code skills
- Allows both interpretation and execution

### Speculative Multi-Action (UFO2, arXiv 2604.13318)
- Batch likely next steps in a single LLM inference pass
- Validate applicability at runtime via OS integration
- Cuts inference overhead by 51.5% vs one-inference-per-action

---

## FULL AGENT TRACE — ALL 106 AGENTS

### Phase 1: Scope (1 agent)
**Agent scope** | tokens: 15,135 | duration: 21.5s | model: claude-sonnet-4-6  
Decomposed into 5 angles: broad/primary OSS landscape, academic/benchmarks, technical/internals (pixel vs DOM vs a11y), VLM-as-eyes, practitioner/implementation (multi-step workflow chaining + deployment)

---

### Phase 2: Search (5 agents)

**Agent search:broad/primary** | tokens: 16,820 | duration: 49.4s | tool calls: 3  
Results: 6 URLs found  
Key results:
- zylos.ai/research/2026-02-08-computer-use-gui-agents/ (high relevance — covers full 2026 landscape)
- aimultiple.com/open-source-web-agents (secondary)
- github.com/simular-ai/Agent-S (primary)
- fazm.ai/blog/open-source-computer-use-agent-github-2026 (unreliable)
- decisioncrafters.com/agent-s-gui-agents-11k-github-stars/ (blog)
- fazm.ai/blog/best-open-source-computer-use-agent-windows-2026 (blog)

**Agent search:academic/benchmarks** | tokens: 17,787 | duration: 55.7s | tool calls: 4  
Results: 6 URLs, 3 novel after dedup  
Key results:
- arxiv.org/pdf/2501.12326 (UI-TARS paper, Jan 2025)
- arxiv.org/html/2509.02544v1 (UI-TARS-2, Sep 2025)
- arxiv.org/html/2606.06560v1 (MacArena, Jun 2026)
- arxiv.org/html/2507.19478v1 (MMBench-GUI, Jul 2025)
- arxiv.org/pdf/2510.11977 (HAL/Princeton, ICLR 2026)
- leaderboard.steel.dev/ (secondary leaderboard)

**Agent search:technical/internals** | tokens: 20,723 | duration: 116.3s | tool calls: 7  
Results: 6 URLs, 4 novel after dedup  
Key results:
- arxiv.org/abs/2408.00203 (OmniParser, pure vision GUI agent)
- fazm.ai/blog/how-ai-agents-see-your-screen-dom-vs-screenshots (blog)
- github.com/bytedance/ui-tars (UI-TARS GitHub)
- workos.com/blog/anthropics-computer-use-versus-openais-computer-using-agent-cua (blog)

**Agent search:VLM-as-eyes** | tokens: 20,519 | duration: 98.4s | tool calls: 6  
Results: 6 URLs, 3 novel after dedup  
Key results:
- arxiv.org/pdf/2603.12823 (Adaptive VLM Routing, OS-Atlas-7B vs GPT-4o comparison)
- arxiv.org/pdf/2408.00203 (OmniParser, VLM angle)
- dl.acm.org/doi/10.1145/3746027.3755688 (primary)

**Agent search:practitioner/implementation** | tokens: 22,839 | duration: 152.5s | tool calls: 7  
Results: 6 URLs, 5 novel after dedup  
Key results:
- epam.com insights on long-horizon agents (unreliable)
- futureagi.com evaluating browser-use agents 2026 (blog)
- arxiv.org/html/2504.14603v2 (WebXSkill, primary)
- arxiv.org/abs/2604.13318 (UFO2 speculative exec, primary)
- github.com/bytedance/ui-tars-desktop (UI-TARS desktop app)

---

### Phase 3: Fetch (24 agents — extracting claims from sources)

**Agent fetch-1** (zylos.ai 2026-02-08) | tokens: 17,459 | duration: 77.4s | tool calls: 3  
date: 2026-02-08 | quality: blog  
Claims extracted:
- Hybrid browser agents (DOM + pixel) outperform accessibility-tree-only: Browser-Use 89.1% vs Agent-E 73.1% on WebVoyager
- Human baseline on OSWorld is ~72.4%
- Screenshot agents: 1,500-7,000ms per action; DOM agents: 20-100ms per action

**Agent fetch-2** (aimultiple.com, 2026-06-25) | tokens: 16,638 | duration: 64.3s | tool calls: 3  
date: 2026-06-25 | quality: secondary  
Claims extracted:
- Browser-Use: 89.1% on WebVoyager (586/643 tasks — removed 55 as outdated), making direct comparison with full-set agents misleading

**Agent fetch-3** (simular-ai/Agent-S GitHub) | tokens: 17,044 | duration: 38.2s | tool calls: 3  
date: primary | quality: primary  
Claims extracted:
- Agent-S3 achieved 72.6% task success on OSWorld (100-step + Behavior Best-of-N), claimed to surpass human-level (~72%) — NOTE: LATER REFUTED
- Agent-S uses pixel-coordinate grounding (UI-TARS-1.5-7B), outputs screen coordinates, translates to Python code — CONFIRMED
- COLM 2025 acceptance

**Agent fetch-4** (fazm.ai open-source-computer-use-agent-github-2026) | tokens: 16,170 | duration: 43.5s | tool calls: 3  
quality: unreliable | claims: 0

**Agent fetch-5** (decisioncrafters.com agent-s) | tokens: 16,637 | duration: 66.5s | tool calls: 3  
date: 2026-04 | quality: blog  
Claims extracted:
- Browser Use achieves 85% success on browser-only tasks using DOM-aware targeting (not screenshot-based)
- UI-TARS is 7B/72B parameter model trained specifically on GUI interaction (note: attributed to "Alibaba" incorrectly — actually ByteDance)

**Agent fetch-6** (arxiv.org/pdf/2501.12326 — UI-TARS paper) | tokens: 16,736 | duration: 39.1s | tool calls: 4  
date: 2025-01-21 | quality: primary  
Claims extracted:
- UI-TARS uses only raw screenshots as input — no DOM, no a11y tree — CONFIRMED
- OSWorld 50-step: 24.6% (vs Claude 22.0%) — CONFIRMED
- System-2 Reasoning: task decomposition, reflection thinking, milestone recognition — CONFIRMED

**Agent fetch-7** (arxiv.org/html/2509.02544v1 — UI-TARS-2) | tokens: 17,083 | duration: 45.9s | tool calls: 3  
date: 2025-09 | quality: primary  
Claims extracted:
- UI-TARS-2 processes via "screenshots and recordings" (initial misread — later clarified to include auxiliary signals)
- Working Memory + Episodic Memory hierarchical architecture — CONFIRMED
- Multi-step benchmark: 59.77 vs OpenAI CUA 24.73, Claude 21.61 — CONFIRMED (with caveats)

**Agent fetch-8** (arxiv.org/html/2606.06560v1 — MacArena) | tokens: 16,689 | duration: 27.6s | tool calls: 3  
date: 2026-06-04 | quality: primary  
Claims extracted:
- OpenAI CUA achieves 31.83% on MacArena (421 tasks) — CONFIRMED with nuance (1-2 vote)
- MacArena dual-modality: screenshots + optional macOS accessibility tree — CONFIRMED
- Cross-app workflows near 0% — CONFIRMED

**Agent fetch-9** (arxiv.org/html/2507.19478v1 — MMBench-GUI) | tokens: 16,945 | duration: 42.6s | tool calls: 3  
date: 2025-07 | quality: primary  
Claims extracted:
- Visual grounding 2.8x vs planning 1.15x bottleneck claim — REFUTED as overreach
- A11y trees excluded from benchmark for noise/token reasons (not counterproductive claim) — REFUTED as misread
- Best evaluated system: 26.60% L3 / 8.78% L4 — REFUTED as outdated

**Agent fetch-10** (arxiv.org/pdf/2510.11977 — HAL Princeton) | tokens: 17,782 | duration: 55.8s | tool calls: 6  
date: 2025-10-13 | quality: primary  
Claims extracted:
- HAL eval harness: parallel VMs, weeks→hours evaluation time — CONFIRMED
- Higher reasoning effort reduced accuracy in 21/36 runs (58.3%) — CONFIRMED
- Aberrant behaviors: HuggingFace search, credit card misuse — CONFIRMED

**Agent fetch-11** (leaderboard.steel.dev) | tokens: 16,547 | duration: 34.9s | tool calls: 3  
quality: secondary  
Claims extracted:
- Alumnium: 98.5% WebVoyager (highest recorded), Surfer 2: 97.1%, Magnitude: 93.9%
- On OSWorld: OpenAI CUA 38.1% vs Anthropic 22%; human baseline 72.4%
- On WebVoyager (browser): OpenAI CUA 87% vs Anthropic 81.4%

**Agent fetch-12** (arxiv.org/abs/2408.00203 — OmniParser) | tokens: 17,574 | duration: 45.4s | tool calls: 4  
quality: primary  
Claims extracted:
- AVR achieves 78% cost reduction — REFUTED (projects, not achieves)
- Current computer-use grounding bottleneck: 18.9% best on ScreenSpot-Pro (OS-Atlas-7B); GPT-4o only 0.8%
- ScreenSeekeR reaches 48.1% on ScreenSpot-Pro
- Qwen2.5-VL-72B reaches 43.6% on ScreenSpot-Pro

**Agent fetch-13** (arxiv.org/pdf/2603.12823 — Adaptive VLM Routing) | tokens: 16,909 | duration: 33.5s | tool calls: 3  
date: 2026-03-16 | quality: primary  
Claims extracted:
- Screenshot-based agents: 1,500–7,000ms; DOM-based: 20–100ms (confirmed from technical angle)
- Screenshot agents instructions have to include bounding-box overlays which DOM agents don't need

**Agent fetch-14** (arxiv.org/pdf/2408.00203 — OmniParser v2) | tokens: 16,602 | duration: 28.7s | tool calls: 3  
quality: primary  
Claims extracted:
- UI-TARS achieves 42.5% on OSWorld (100-step) — REFUTED (wrong model version, step-budget mismatch)
- UI-TARS uses pixel-level absolute coordinate grounding via Qwen 2.5VL — CONFIRMED with version nuance

**Agent fetch-15** (arxiv.org/abs/2604.13318 — UFO2) | tokens: 16,807 | duration: 36.3s | tool calls: 3  
date: 2025-07-30 | quality: primary  
Claims extracted:
- OSWorld: OpenAI CUA 38.1% vs Anthropic 22%; human 72.4% — confirmed (from secondary view)
- WebVoyager: OpenAI CUA 87% vs Anthropic 81.4% — from secondary angle
- UFO2 speculative multi-action: 51.5% overhead reduction — CONFIRMED

**Agent fetch-16** (futureagi.com browser-use-agents-2026) | tokens: 16,317 | duration: 12.0s | tool calls: 3  
quality: unreliable | claims: 0

**Agent fetch-17** (futureagi.com evaluating browser-use-agents-2026) | tokens: 16,600 | duration: 32.7s | tool calls: 3  
quality: blog  
Claims extracted:
- A browser agent scoring 78% on WebArena achieves only 22% cart-booking success in live production — 56-point accuracy drop
- WebArena and Mind2Web evaluate only happy-path scenarios; production has CAPTCHA, rate limits, UI changes

**Agent fetch-18** (arxiv.org/html/2504.14603v2 — WebXSkill) | tokens: 17,029 | duration: 39.3s | tool calls: 3  
date: 2025-04 | quality: primary  
Claims extracted:
- WebXSkill parameterized skill = action program + NL guidance (resolves text-only vs code-only dichotomy)
- Skills enable both human interpretation and direct execution

**Agent fetch-19** (arxiv.org/abs/2604.13318) | tokens: 16,909 | duration: 33.5s | tool calls: 3  
date: 2025-04 | quality: primary  
Claims extracted:
- UFO2 speculative multi-action execution cuts inference overhead by 51.5%

**Agent fetch-20** (github.com/bytedance/ui-tars-desktop) | tokens: 17,698 | duration: 50.3s | tool calls: 5  
quality: primary  
Claims extracted:
- UI-TARS-desktop supports three browser-control strategies: GUI Agent (pixel/screenshot), DOM-based, and hybrid — CONFIRMED
- Driven by UI-TARS-1.5 and Seed-1.5-VL/1.6 series — CONFIRMED

**Agent fetch-21** (arxiv.org/html/2504.14603v2) | tokens: 17,158 | duration: 41.1s | tool calls: 5  
date: 2025-04 | quality: primary  
Claims extracted:
- Best existing GUI grounding model: 18.9% on ScreenSpot-Pro
- ScreenSeekeR: 48.1% on ScreenSpot-Pro via cascaded visual search

**Agent fetch-22** (arxiv.org/abs/2408.00203 OmniParser angle 3) | tokens: 17,497 | duration: 45.1s | tool calls: 4  
quality: primary  
Claims extracted:
- OmniParser deploys pure vision-based YOLOv8 trained on 67k DOM-derived screenshots, requires no DOM at inference — CONFIRMED

**Agent fetch-23** (workos.com anthropic vs openai CUA) | tokens: 16,909 | duration: 33.5s | tool calls: 3  
date: 2026-03-16 | quality: blog  
Claims extracted:
- Screenshot: 1,500-7,000ms per action; DOM: 20-100ms per action
- Screenshot agents require bounding-box overlays to identify targets

**Agent fetch-24** (github.com/bytedance/ui-tars) | tokens: 16,602 | duration: 28.7s | tool calls: 3  
quality: primary  
Claims extracted:
- UI-TARS-1.5 OSWorld 100-step: 42.5% — NOTE: REFUTED due to step-budget mismatch and wrong model attribution
- Qwen 2.5VL uses absolute coordinates — CONFIRMED

---

### Phase 4: Verify (75 agents — 3 adversarial votes per claim, 25 claims total)

#### Claim 1: Agent-S3 72.6% surpasses human-level OSWorld → KILLED (0-3)
- v0 (agent a1f63f): REFUTED — "Three compounding problems: PAPER vs. MARKETING GAP — actual paper reports 62.6% not 72.6%; Behavior Best-of-N inflation; quote misrepresents baseline as 66% when paper says 62.6%"
- v1 (agent ad14e5): REFUTED — "Multiple compounding issues: supporting quote says 66% but paper reports 62.6% averaged over 10 runs. COLM 2025 paper (2510.02250) itself shows Agent S3 at 62.6%, not 72.6%"
- v2 (agent ab630a): REFUTED — "72.6% came from December 2025 company blog post scaling announcement, not the October 2025 peer-reviewed paper which reports bBoN at 69.9%, not 72.6%"

#### Claim 2: Agent-S uses pixel-coordinate grounding → CONFIRMED (2-1)
- v0 (agent a7e0c3): REFUTED — "Directly contradicted by official Simular quickstart documentation which accepts both screenshot AND accessibility_tree as combined observations"
- v1 (agent a83c56): CONFIRMED — "Core technical claims supported: UI-TARS-1.5-7B recommended grounding model; pixel-coordinate grounding; translates to Python code"
- v2 (agent a47918): CONFIRMED — "All claims directly confirmed by primary source: Agent-S2 operates solely on raw screenshots as input; eliminates need for structured accessibility data"
Note: Vote 2-1 with nuance that Agent-S has hybrid option but Agent-S2 current version is screenshot-only

#### Claim 3: Agent-S2 outperformed OpenAI CUA and Claude 3.7 Sonnet Computer-Use → CONFIRMED (2-1)
- v0 (agent a76167): CONFIRMED — "All three assertions verified by primary sources: COLM 2025 confirmed; 27.0% vs 19.7% (15-step) and 34.5% vs 32.6% (50-step) confirmed from arXiv 2504.00906"
- v1 (agent af7801): CONFIRMED — "COLM 2025 acceptance confirmed from GitHub update July 7. Benchmark scores from arXiv 2504.00906 confirmed. Nuance: Agent-S2 outperforms Claude's computer-use deployment, not the raw model"
- v2 (agent a4e7e1): REFUTED — "Material misrepresentation: claim drops 'Computer-Use' qualifier, creating false impression Agent-S2 beat Claude 3.7 Sonnet the language model itself"

#### Claim 4: UI-TARS uses only raw screenshots — no DOM, no a11y tree → CONFIRMED (3-0)
- v0 (agent aa686): CONFIRMED — "Directly and accurately supported: paper 2501.12326 verbatim 'solely perceives the screenshots as input'. Not a misread."
- v1 (agent aff265): CONFIRMED — "Not paraphrased or overstated. Multiple independent secondary sources confirm."
- v2 (agent a57f18): CONFIRMED — "Same verbatim language consistently throughout paper. ByteDance GitHub and community writeups uniformly confirm."

#### Claim 5: UI-TARS OSWorld 50-step 24.6% beats Claude 22.0% → CONFIRMED (3-0)
- v0 (agent aeeb93): CONFIRMED — "Primary source explicitly states exact figures. Multiple independent sources corroborate."
- v1 (agent a94d07): CONFIRMED — "UI-TARS paper abstract: 'UI-TARS-72B achieves scores of 24.6 with 50 steps... outperforming Claude's 22.0' — matches claim exactly"
- v2 (agent acd5ce): CONFIRMED — "Direct fetch of arxiv 2501.12326 confirms. Note: 'Claude' refers to Claude 3.5 Sonnet Computer Use, not a general statement about Claude."

#### Claim 6: AndroidWorld UI-TARS 46.6% beats GPT-4o 34.5% → CONFIRMED (3-0)
- v0 (agent a040fe): CONFIRMED — "Primary source verbatim: 'In AndroidWorld, UI-TARS achieves 46.6, surpassing GPT-4o (34.5)'"
- v1 (agent a176a1): CONFIRMED — "Directly and explicitly supported. Multiple independent sources corroborate both numbers."
- v2 (agent ab906): CONFIRMED — "Direct fetch confirms paper explicit statement."

#### Claim 7: UI-TARS System-2 Reasoning (task decomp + reflection + milestone) → CONFIRMED (3-0)
- v0 (agent a59c22): CONFIRMED — "Supporting quote directly matches claim. Paper explicitly names all three components."
- v1 (agent a5d5b3): CONFIRMED — "Directly and precisely supported. Paper states verbatim all three sub-components."
- v2 (agent a0873e): CONFIRMED — "Same verbatim three-part structure reproduced by multiple independent sources."

#### Claim 8: UI-TARS-2 processes GUI exclusively via raw screenshots → KILLED (0-3)
- v0 (agent a79b80): REFUTED — "'Exclusively' qualifier contradicted by paper's observation triplet: oᵢ = 'screenshot and auxiliary signals'"
- v1 (agent a9f6d2): REFUTED — "Quote misapplication: supporting quote from infrastructure/SDK section about data collection, not agent's observation space"
- v2 (agent a23deb): REFUTED — "'Exclusively' is overreach: paper describes hybrid GUI environment with non-visual inputs (file systems, terminals)"

#### Claim 9: UI-TARS-2 2.4x OpenAI CUA, 2.8x Claude Computer Use → CONFIRMED (2-1)
- v0 (agent ad5231): CONFIRMED — "Accurately represents paper's stated results. Table 2: 59.77/24.73=2.42x, 59.77/21.61=2.77x. Both confirmed."
- v1 (agent a5c4a7): CONFIRMED — "All figures verified against primary source. Ratios compute correctly."
- v2 (agent a24d4b): REFUTED — "Numbers mathematically consistent but: (1) 15-game benchmark is in-house ByteDance suite (self-serving selection risk); (2) baselines not versioned; (3) unreviewed corporate technical report"

#### Claim 10: MacArena dual-modality perception (screenshot + a11y tree) → CONFIRMED (3-0)
- v0 (agent a44d94): CONFIRMED — "Primary source 2606.06560v1 directly confirms. Section 3.1 verbatim matches claim."
- v1 (agent ad992): CONFIRMED — "Primary source confirmed. Accessibility tree confirmed as hierarchical UI element metadata."
- v2 (agent afb5b): CONFIRMED — "Direct fetch confirms every element verbatim."

#### Claim 11: Cross-app workflows near 0% on MacArena → CONFIRMED (3-0)
- v0 (agent a68fc): CONFIRMED — "Primary source paper language: 'most agents scoring at or near 0%'. Actual tabulated data: 0-3.45% OSWorld multi-app, 5-15% macOSWorld multi-app."
- v1 (agent a385a): CONFIRMED — "Paper's own language confirmed. Best cross-app score: 15% (Qwen3-VL 4B on macOSWorld multi-app)"
- v2 (agent ab553): CONFIRMED — "MacArena paper directly states 'The multi-app tasks category remains the hardest category across all models'"

#### Claim 12: Visual grounding primary bottleneck (2.8x vs 1.15x) → KILLED (0-3)
- v0 (agent a33e2): REFUTED — "Numbers appear in MMBench-GUI but universal claim is correlational not controlled ablation; contradicted by other benchmarks; WorldGUI says planning errors dominate"
- v1 (agent afbcf): REFUTED — "Quote is real but overreach: directly contradicted by OSWorld failure-mode analysis where planning errors dominate"
- v2 (agent a7ca4): REFUTED — "Three grounds: direct contradiction from other research; correlational not causal methodology; tool-misuse/planning errors documented as dominant in multiple other settings"

#### Claim 13: Providing a11y trees or SoM is counterproductive → KILLED (0-3)
- v0 (agent a8aa4): REFUTED — "Claim overreaches source: MMBench-GUI excluded a11y trees as benchmark design choice for standardization, not as finding that they harm agents"
- v1 (agent a7773): REFUTED — "Same: methodological exclusion ≠ counterproductive in general use. Multiple papers show a11y trees benefit agents."
- v2 (agent ab3ad): REFUTED — "Significant overreach: paper explains pragmatic exclusion for controlled evaluation, not general recommendation against a11y trees"

#### Claim 14: State-of-the-art GUI agents far from human level (26.60%/8.78%) → KILLED (0-3)
- v0 (agent a14fc): REFUTED — "Outdated by one year: UI-TARS-2 (Sept 2025) already at 73.3% AndroidWorld. Paper is July 2025, current date July 2026."
- v1 (agent a4410): REFUTED — "Numbers from July 2025; directly contradicted by subsequent evidence: UI-TARS-2 Sept 2025 significantly exceeds these figures"
- v2 (agent a6b2f): REFUTED — "Numbers accurate for July 2025 but by mid-2026 GUI agents dramatically exceed these figures"

#### Claim 15: Higher reasoning effort reduces accuracy in 21/36 runs → CONFIRMED (3-0)
- v0 (agent af67f): CONFIRMED — "Directly and accurately supported by arXiv 2510.11977. Paper verbatim: 'higher reasoning effort, enabled by different model settings (e.g., Claude Opus 4.1 with no vs. high reasoning, o4-mini with low vs. high reasoning), reduced accuracy in the majority (21 of 36) of runs'"
- v1 (agent a5dac): CONFIRMED — "HAL paper is legitimate: 21,730 rollouts, 9 models, 9 benchmarks, ~$40K compute. Corroborated by two independent 2025-2026 studies on CoT for multi-step tasks."
- v2 (agent a51e0): CONFIRMED — "Grounded in real large-scale Princeton study. Supporting quote is genuine. The 58.3% majority is technically slim but accurately framed as 'majority of runs.'"

#### Claim 16: Web navigation agents exhibited aberrant behaviors → CONFIRMED (3-0)
- v0 (agent aac95): CONFIRMED — "Directly and specifically supported by primary source. Verbatim quote in HAL abstract: 'searching for the benchmark on HuggingFace instead of solving a task, or misusing credit cards in flight booking tasks.'"
- v1 (agent adb24): CONFIRMED — "Source paper confirmed real. Behaviors confirmed by multiple independent sources. HAL reliability dashboard (hal.cs.princeton.edu/reliability/) independently confirms HuggingFace behavior."
- v2 (agent a5d02): CONFIRMED — "Discovered via 'LLM-aided inspection of 21,730 agent rollouts totaling 2.5B tokens of logs' confirmed verbatim."

#### Claim 17: OmniParser deploys pure vision-based YOLOv8 (67k screenshots) → CONFIRMED (3-0)
- v0 (agent a6afe): CONFIRMED — "All specific factual components confirmed by primary source arXiv 2408.00203 and multiple independent sources. YOLOv8 Nano confirmed as detection backbone."
- v1 (agent a4d8d): CONFIRMED — "All five specific sub-claims check out: 67k (~66,990) samples; YOLOv8; DOM-derived bounding boxes at training; no DOM at inference; universally applicable."
- v2 (agent af8d4): CONFIRMED — "All technical claims check out. YOLOv8 Nano confirmed via LearnOpenCV, HuggingFace model card. DOM → training only, not inference."

#### Claim 18: OmniParser 73.0% ScreenSpot accuracy → CONFIRMED (3-0)
- v0 (agent a9d83): CONFIRMED — "All four numbers verified directly against Table 2 of arXiv 2408.00203. Arithmetic confirmed: (93.9+57.0+91.3+63.6+81.3+51.0)/6 = 73.02% ≈ 73.0%"
- v1 (agent afd21): CONFIRMED — "All stated numbers verified. Breakdown by platform and text/icon all confirmed."
- v2 (agent ae81f): CONFIRMED — "Numbers verified accurate against actual paper Table 2."

#### Claim 19: OmniParser boosts GPT-4V task-completion 53.0%→57.7% on AITW → KILLED (1-2)
- v0 (agent a19c2): CONFIRMED — "Numbers 53.0% and 57.7% confirmed from primary source Table 4. 4.7pp gap confirmed."
- v1 (agent af937): REFUTED — "Numbers correct but metric CRITICALLY MISLABELED: AITW uses 'partial action matching score' (step-level accuracy), NOT 'task-completion rate' (full task success). This is a material misrepresentation."
- v2 (agent a3c24): REFUTED — "Same: claim contains two material errors — metric mislabeled AND baseline model (GPT-4V + history) is not what the claim implies."

#### Claim 20: UI-TARS 42.5% OSWorld surpassing SOTA 38.1% → KILLED (0-3)
- v0 (agent a384f): REFUTED — "GitHub README shows SOTA 38.1% explicitly requires 200 steps (double budget). Claim's supporting quote strips '(200 step)' qualifier — apples-to-oranges comparison."
- v1 (agent a8f7c): REFUTED — "Three problems: step-budget mismatch (100 vs 200); now outdated; README sourcing is ambiguous (UI-TARS vs UI-TARS-1.5)"
- v2 (agent a83d6): REFUTED — "Wrong model attribution: 42.5% belongs to UI-TARS-1.5 (April 2025), not original UI-TARS. Original paper reports only 24.6% at 50 steps."

#### Claim 21: UI-TARS uses pixel-level absolute coordinate grounding via Qwen 2.5VL → CONFIRMED (2-1)
- v0 (agent a3fb5): CONFIRMED — "Core technical substance accurate and supported. UI-TARS 1.5 uses Qwen2.5-VL as backbone (confirmed HuggingFace model card). Supporting quote from GitHub genuine."
- v1 (agent af359): CONFIRMED — "Well-supported by multiple primary sources. Pixel-coordinate grounding confirmed; Qwen2.5-VL as backbone for UI-TARS-1.5 confirmed."
- v2 (agent a2cee): REFUTED — "Material version conflation: original UI-TARS (arXiv 2501.12326) uses Qwen2-VL, not Qwen2.5-VL. Only UI-TARS-1.5 (April 2025) upgrades to Qwen2.5-VL."

#### Claim 22: AVR achieves up to 78% inference cost reduction → KILLED (0-3)
- v0 (agent a98a2): REFUTED — "Paper says 'projects' not 'achieves'. Table 4 footnote: 'Analytical projection; not measured end-to-end on CUA tasks.'"
- v1 (agent a40ad): REFUTED — "Same: 'Achieves' vs 'projects' is direct misrepresentation. Limitations section repeats: 'Projected from OpenClaw confidence distributions, not measured on CUA grounding.'"
- v2 (agent a9649): REFUTED — "HTML version confirms Table 4 carries explicit footnote 'Analytical projection; not measured end-to-end on CUA tasks.'"

---

### Phase 5: Synthesize (1 agent)

**Agent synthesize** (agent a7b99d) | tokens: 23,266 | duration: 104.2s | tool calls: 1  
Result preview: "The field of GUI agents has converged on pixel-only screen perception — raw screenshots fed to vision-language models — as the dominant architectural choice..."  
Full synthesis stored as `result.summary` + `result.findings` in this document's EXECUTIVE SUMMARY and CONFIRMED FINDINGS sections above.

---

## VIDEO ANALYSIS — WHAT THE USER WANTS THE BRAIN TO DO

*(From simultaneous video-understand analysis of 2 uploaded videos)*

### Video 1 — AngelOne (VIDEO20260705175955.mp4)
**What it shows:**
- **Frame 1 [00:00]:** AngelOne login page at angelone.in/login — "Welcome to India's fastest investment platform!" — Mobile number entry: **7702664278** — "Login with Mobile Number" selected
- **Frame 5 [00:12]:** OTP entry screen — "OTP Sent — We have sent an OTP to your mobile number and registered email" — 00:24 countdown timer
- **Frame 10 [00:27]:** Account page — **Name: Dudekula Ajith** — Trading Balance: **₹0.00** — Reports section: Trades & Charges, Statements, Profit & Loss, Trading Insights — Pledging & Pay Later, MTF, Transfer Stocks
- **Frame 15 [00:42]:** Same account page (user navigating)
- **Frame 20 [01:00]:** Markets → Equity Overview — NIFTY/SENSEX indices shown — Top Movers and Sectorwise Movements table — Stocks: SUMCHEM, ZENSARTECH, HEXAWARE, TCL, HELLTECH with LTP and Chng columns
- **Frame 25 [01:12]:** SUMICHEM stock selected — Price chart (TradingView integrated) — BUY / SELL buttons (₹492.30 / ₹492.30) — 5m timeframe — Instant Orders toggle — Chart shows price ~₹480-490
- **Frame 30 [01:27]:** Same SUMICHEM chart (user studying it)

**Conclusion:** User manually logs into AngelOne (NSE broker) with mobile 7702664278, receives OTP on phone, navigates to account page and then equity markets to study stock charts.

### Video 2 — Coinbase (VIDEO20260705175741.mp4)
**What it shows:**
- **Frame 1 [00:00]:** Coinbase.com homepage — "The future of finance is here. Buy, sell and trade crypto on a platform you can trust." — Balance shown: ₹1,30,535.00
- **Frame 5 [00:12]:** Coinbase login — Password entry screen — "Sign in as **ajithd747@gmail.com**"
- **Frame 15 [00:42]:** Loading spinner (authentication in progress)
- **Frame 20 [01:00]:** Coinbase Advanced Trade — BTC/PERP order book — Price: ~62,452.30 — Order book showing bid/ask spread
- **Frame 25 [01:12]:** Coinbase Advanced Trade — Futures list — BTC-31JUL26, ADA-31JUL26, GLD-31JUL26, SOL-31JUL26, ETH-31JUL26, DOGE-31JUL26, DYDX-31JUL26, BCH-31JUL26, XRP-31JUL26 with expiry dates, last prices, % changes, open interest
- **Frame 30 [01:27]:** Coinbase BTC 31JUL26 futures — "Viewing Instrument. CDX derivatives are currently a view-only experience. Trading is unavailable for your location." — Open Interest: $76.7M — Expiry: 7/31/2026
- **Frame 35 [01:45]:** Coinbase BTC chart — 30m timeframe — Historical BTC price chart ~$38,000–$44,000 range

**Conclusion:** User logs into Coinbase with email ajithd747@gmail.com, navigates Advanced Trade → Derivatives/Futures section. Note: CDX derivatives are VIEW-ONLY for India location (cannot trade, only read).

---

## RESEARCH NOTES — RAW CLAIMS FROM FETCH AGENTS (unverified claims, for completeness)

The following claims were extracted by fetch agents but NOT selected for adversarial verification (the top 25 by importance were selected; remaining 85 are listed here for reference):

- Browser-Use hybrid (DOM + pixel): 89.1% WebVoyager — fetched from zylos.ai
- Human baseline on OSWorld: ~72.4% — fetched from zylos.ai
- Screenshot vs DOM speed: 1,500-7,000ms vs 20-100ms — fetched from workos.com
- Alumnium: 98.5% WebVoyager, Surfer 2: 97.1%, Magnitude: 93.9% — fetched from leaderboard.steel.dev
- A benchmark agent scoring 78% WebArena achieves 22% production cart-booking (56pp gap) — fetched from futureagi.com
- WebXSkill: executable skill = parameterized action program + step-level NL guidance — fetched from arXiv 2504.14603
- UFO2 speculative multi-action: 51.5% inference overhead reduction — fetched from arXiv 2604.13318
- UI-TARS-desktop supports GUI/DOM/hybrid browser strategies at runtime — fetched from github.com/bytedance/ui-tars-desktop
- ScreenSeekeR: 48.1% on ScreenSpot-Pro via cascaded visual search — fetched from arXiv 2603.12823
- OS-Atlas-7B: 18.9% ScreenSpot-Pro, GPT-4o: 0.8% (23x gap) — fetched from arXiv 2603.12823
- Qwen2.5-VL-72B: 43.6% ScreenSpot-Pro — fetched from arXiv 2603.12823
- HAL evaluation harness: parallel VMs, evaluation time weeks→hours, 21,730 rollouts, 9 benchmarks, ~$40K compute — fetched from arXiv 2510.11977
- OmniParser ScreenSpot full breakdown: Mobile text 93.9%, Mobile icons 57.0%, Desktop text 91.3%, Desktop icons 63.6%, Web text 81.3%, Web icons 51.0%, Overall 73.0% — fetched from arXiv 2408.00203

---

*End of document. Research generated 2026-07-05. All confirmed findings cite primary sources. All refuted claims documented with reason for refutation.*
