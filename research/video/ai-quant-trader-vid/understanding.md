# Understanding — "I coded a self-learning AI quant trader" (3PO / Threepio)

**Source:** `cddb76f6-I_CODED_A_SELF_LEARNING_AI_QUANT_TRADER…mp4` (77.7s, EN, 8 keyframes)
**Slug:** `research/video/ai-quant-trader-vid/`
**What it is:** A vertical social-media promo reel (TikTok/Reels/Shorts). A creator (male,
cap, on-camera at the end) demos a self-learning AI quant-trading agent he built, named
**"3PO" / "Threepio"** (banners also read **THREEPIO v1**, **THREEPIO FALCON**). It runs as
a local web app at **`localhost:5173`** (Vite/React SPA, routes `#/brain`, `#/riskgate`).
The reel is a hype/teaser — "comment **QUANT** for more info" — not a technical explainer.
Crucially, the system is a **near-parallel of this project's own vision** (self-learning brain
that reads research → invents strategies → validates → trades under a risk gate), so it's a
direct competitive/idea-mining reference.

---

## The pipeline as narrated (verbatim intent, [mm:ss])

1. **[00:03] Self-learning agent** — "3PO, a self-learning AI agent that trains himself on
   quantitative trading."
2. **[00:08] Brain Vault** — "his brain vault… every single dot is a research paper or a book
   he's actually read, and the lines between are where the ideas connect." Running ~24h.
3. **[00:20] Research ingestion** — "goes online and finds papers and books related to what
   he's trying to learn about trading, downloads them, reads them, and then **cites** them."
   → **[00:27] 393 research items in under 24 hours.**
4. **[00:32] Strategy Factory** — "creates the strategies using the knowledge he just learned."
5. **[00:35] Strategy Star Map** — "maps out all the strategies tested so far, and sees if
   there's any **correlation or linkage** between them."
6. **[00:41] Validation funnel** — "runs through **out-of-sample data**, a **screening**, a
   **Monte Carlo test**, a **walk-forward test**, a **deflated [Sharpe] chart test**, and if
   they pass all that they go on to a **demo account**."
7. **[00:50] Portfolio** — "once he's found enough profitable strategies he brings them to the
   portfolio, manages it, **swaps out under-performers, adds in new more profitable strategies**."
8. **[01:00] Risk gate** — "apply our **risk gate** to make sure everything's running within
   our risk parameters."
9. **[01:03] Voice** — "and he even speaks to me. 3PO, say hi." (voice agent; ElevenLabs tab
   visible in a frame.)
10. **[01:11] CTA** — full explainer video coming; "comment **quant** below."

---

## What the frames actually show (the real design lives here)

### Frame f_0004 (00:04) — Research Brain / Vault "living showpiece"
- Top status bar: **`CORE ONLINE · GATE ARMED · LIVE OFF · INCIDENTS 0 · MODE BACKTEST`**
- Labels: `read-only`; **"research brain — a living showpiece — data on the vault brain page"**
- Big glowing neural cloud: dots = research items, lines = idea connections (bright core).
- Lower band: **"time-lapse — birth days from git history"** (a second mini galaxy).
- Footer: **`PRIMARY DIRECTIVE — PROVE IT WORKS BEFORE IT TRADES`** and **`34 / 38 MILESTONES`**.
- Overlay caption: "WATCH TO THE END TO LEARN HOW TO GET MORE INFO".

### Frames f_0010 / f_0020 (00:10 / 00:20) — Strategy Star Map (semantic topic map)
- Browser tabs: **"Threepio — The Millennium Fal…"**, arXiv **"[2606.27462v1] The Decision G…"**,
  another arXiv `[2…625v1]`. (Real arXiv papers open as sources.)
- Constellation of strategy/topic nodes; hover-to-inspect: **"click to open its source"**.
- Tooltip: **"Topic — VWAP Reversion · Knowledge · 9 links · CLICK → COPY VAULT"**.
- Stat tiles: **282 LINKS**, **43 WISHLIST WAITING**.
- Caption strip: **"…semantic topic map. Topic-level knowledge arrives with Vault Intelligence
  v1 (D2.8)."**
- **STRATEGIES · BY FAMILY**: evo orb breakout 3, momentum ignition 66, orb breakout 1,
  gap fill 188, designated test 1 … (bar chart).
- **RESEARCH · BY CREDIBILITY TIER**: practitioner 6, peer reviewed 7 … (papers ranked by
  credibility tier).

### Frame f_0030 (00:30) — Knowledge Base (`localhost:5173/#/brain`)
- **KNOWLEDGE BASE** panel: **393 RESEARCH ITEMS**, **244 GRAVEYARD**.
- "Grouping is by folder / source".
- **VAULT NOTES · BY FOLDER**: `00 Inbox, 05 Claude, 06 Strategies, 07 Backtests,
  08 Trade Logs, 10 Strategy Gravey[ard], 11 Research Library, 13 Daily Brain…`
  → the brain is a **Markdown vault** (Obsidian-style numbered folders); `05 Claude` folder
  strongly implies it's built with Claude.

### Frame f_0036 (00:36) — Strategy correlation graph
- Pink/red node-link graph on a green 3D grid — strategies clustered by correlation/linkage
  (the "any correlation or linkage between them" the narration mentions). Highlighted clusters.

### Frame f_0050 (00:50) — Strategy Graveyard / survival funnel
- **"ONYX PROTOCOL"**, clock **16:04:49 THU 09 JUL**.
- A strategy card: **"GAP fade 6-40pt stop10 1.6R tf10m — NOW SURVIVING / KILLED BY SCREEN ·
  09/07/2026"** with a survival/equity curve trailing toward a **DEMO** marker.
- Table **`DIED AT | BRED`**: many rows **"deflated sharpe"** with breed dates 08/07/2026 &
  06/07/2026 → strategies are killed and logged with the **stage they died at** (mostly the
  deflated-Sharpe test) plus a "bred" date. This is the graveyard = 244 count from the KB.

### Frame f_0100 (01:00) — Risk Gate (`localhost:5173/#/riskgate`, "THREEPIO v1")
- **RISKGATE — "fails closed · every order path passes through"**.
- **GATE RADAR** ("eight rules · live verdicts"): a radar sweep; **`GATE ARMED · 1 CONTRACT ·
  1/DAY · -1R STOP · 09:30–15:30 NY · RISK NEWS · KILL SWITCH`**; last-10-verdicts, blocked count.
- **VERDICT** panel: timestamped checks, **"LAST 10 CHECKS"**.
- **ACTIVE LIMITS `config/risk.yaml` — "ENFORCED ON EVERY PATH"**:
  `max_contracts`, `max_trades_per_day 1`, `daily_loss_limit_r 1`,
  `trading_window.start 09:30`, `trading_window.end 15:30`,
  `news_blackout_minutes_before 15`, `news_blackout_minutes_after 15`,
  `portfolio.max_pairwise_correlation 0.7`, `portfolio.max_simultaneous_positions 1`,
  `portfolio.max_combined_drawdown_usd 2500`, `portfolio.min_common_days 20`.
- **BLACKOUT CALENDAR (next 30 days)**: 2026-07-14 08:30, 07-15 08:30, 07-29 14:00, 07-30,
  08-07 08:30 (news/econ-event blackouts).
- ElevenLabs "Voices" tab visible → the talking-agent voice.

### Frame f_0109 (01:09) — Creator sign-off
- Creator on camera, caption **"COMMENT "QUANT" FOR MORE INFO"**.

---

## Distilled feature set (what the video demonstrates)

| # | Feature | Evidence |
|---|---|---|
| A | Autonomous research ingestion: web-search → download papers/books → read → **cite** | narration [00:20-27]; 393 items; arXiv tabs |
| B | **Research Brain graph** (papers=nodes, idea-links=edges), git-history birth time-lapse | f_0004 |
| C | Markdown **vault** knowledge base, numbered folders, credibility tiers | f_0030, f_0020 |
| D | **Strategy Factory** — generate strategies from learned knowledge, by family | narration; f_0020 families |
| E | **Strategy Star Map** — semantic topic map + strategy correlation graph | f_0010/20/36 |
| F | **Validation funnel**: OOS screening → Monte Carlo → walk-forward → **deflated Sharpe** → demo | narration [00:41-50]; f_0050 |
| G | **Strategy Graveyard** — killed strategies logged with *died-at stage* + bred date (244) | f_0050, f_0030 |
| H | **Portfolio manager** — swap underperformers, add better, pairwise-corr cap | narration; risk.yaml |
| I | **Risk Gate** — fails-closed, 8 rules, `config/risk.yaml`, blackout calendar, kill switch | f_0100 |
| J | **Voice agent** (ElevenLabs) — the agent talks to the operator | narration [01:03]; tabs |
| K | Ops framing: `PROVE IT WORKS BEFORE IT TRADES`, MODE BACKTEST, LIVE OFF, milestones 34/38 | f_0004 |

---

## Relation to *this* project (why it matters)

This is essentially a rival/parallel build of our own north star (eyes→brain→hand→memory
self-learning trading brain). Overlap vs. gaps we could mine:

- **We already have:** a brain/knowledge layer (HippoRAG+A-MEM, `brain_memory/` notes),
  strategy library (239 institutional strategies + Foundry), CPCV/DSR anti-overfit gate,
  conformal UQ gate, risk sizing, dashboard panels, LLM providers, decision memory.
- **They show sharper/cleaner versions of things we have partial:**
  - a **research→citation ingestion loop** that visibly grows a paper graph (our brain reads
    notes but doesn't autonomously harvest+cite arXiv/books into a visual graph);
  - an explicit **strategy graveyard** with *died-at-stage* accounting (we track perf but not
    a first-class "cause of death" ledger);
  - a **single "fails-closed" Risk Gate** page where every order path provably passes 8 rules
    incl. a **news blackout calendar** (we have risk levers but not one unified gate view);
  - a **deflated-Sharpe** stage as a named funnel step (we have DSR in the Foundry gate —
    could be surfaced as a visible funnel);
  - the **"prove it works before it trades" milestone tracker** (34/38) as a gating ritual.

## Open questions (do not guess — for you to steer)

1. **Intent of sharing this video** — do you want me to (a) just archive the understanding,
   (b) **research the specific techniques** shown (deflated Sharpe, walk-forward, Monte Carlo,
   Vault-Intelligence-style topic maps, autonomous arXiv ingestion) and write a plan to
   *adopt the best missing ones* into our brain, or (c) both? Default assumption = (c).
2. **Scope** — is the target the **crypto/NSE trading brain** we already run, or a new
   research-ingestion sub-system? (The video's strongest novel bits are the **research→citation
   graph** and the **strategy graveyard / risk-gate pages** — those are the likely adopt list.)
3. **The arXiv paper `2606.27462v1` "The Decision G…"** — want me to pull it and the other
   visible source and add to `research/`? (Note: 2606 = a 2026 arXiv id, i.e. very recent.)
4. Any interest in the **voice-agent** angle (ElevenLabs "3PO says hi"), or ignore as cosmetic?
