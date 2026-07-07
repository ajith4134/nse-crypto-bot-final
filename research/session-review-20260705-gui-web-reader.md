# Session Review — "save the finding in a detailed file" (2026-07-05, 12:33–16:44)

**Session ID:** `7a1b852c-34b0-4a6c-86ee-b5bababd855d` (4.0 MB main transcript + 7.2 MB sub-agent transcripts + 13 MB tool results)
**Model used:** Sonnet 4.6 (owner switched at session start; build deferred to Fable 5 — this review is written by Fable 5)
**Reviewed by:** Fable 5, 2026-07-05, on owner request: *"read all the previous session, save the findings in a detailed file, and tell me what you think."*

This file is the complete, verified record of everything that session asked, found, decided, and saved — plus a data-loss audit and an honest assessment.

---

## 1. Timeline — every ask in order

| Time | Owner's ask (normalized) | What happened |
|---|---|---|
| 12:35 | `/deep-research` on AI that reads screens + controls websites like a human | deep-research workflow launched (background) |
| 12:38–12:43 | 4 escalating messages: save ALL findings to a file, zero data loss, include every source link + where found, include every agent's output — "you do not decide which to save" | Committed to full dump |
| 12:55 | Uploaded 2 videos (AngelOne login, Coinbase login): "brain must open websites with login, navigate, read all the images" | video-understand skill ran; frames extracted |
| 12:57 | Workflow completed (106 agents, 21.5 min, 2.30 M tokens) | Full output written to `research/gui-ai-agents-deep-research.md` |
| 13:06 | — | Both video understanding docs written; OTP-handling question asked; owner answered: manual OTP + saved session cookies; web UIs = PRIMARY data source (APIs fallback); expand to Binance, Upstox, Bybit |
| 13:15 | (implied) build the web-reader layer | research-projects + build-from-oss invoked; `trading/web_reader/` build STARTED (5 files written) |
| 13:23 | **INTERRUPT:** "Only do deep web searches… don't build it, we will build it in other session using Fable 5" | Partial build **deleted** (`rm -rf trading/web_reader/`); pivot to research-only |
| 13:24–13:29 | Deep OSS research, 6 angles | `research/web-reader-oss-deep.md` written (335 lines) |
| 13:38 | "Which is faster/lighter on CPU: API data vs opening trading apps with pre-calculated filters?" | Architecture answer: broker screener endpoints (Section 5) |
| 13:47 | "One trading app for both crypto + NSE, for data APIs don't have?" | Answer: no single app; TradingView + REST split (Section 5) |
| 13:51 | "I have 32 GB RAM so RAM is no problem" | Revised answer: 3 persistent headless browsers (Section 5) |
| 13:58 | Full pipeline vision: brain logs in, scans with app filters, picks trades, deep-dives each pick (candles/order book/depth), decides entry/direction/SL, executes via bot | **Architecture CONFIRMED** → `research/web-reader-pipeline-design.md` (208 lines) |
| 14:07 | "Brain should control the computer like Claude Desktop does — search projects + extract Claude's own function, append to the same file" | Computer-use research round; ANGLE 5 appended → `web-reader-oss-deep.md` now 570 lines |
| 14:12 | Session's final synthesis delivered | Handoff notes "for the Fable 5 build session" |

---

## 2. Deep-research workflow — full stats and ALL findings

**Question researched:** Ultra-advanced AI projects where AI reads the screen like a human, processes what it sees, and controls screens/websites like a human — clicking buttons, opening tabs, filling forms, reading and acting on data. Covering OSS GUI-agent frameworks, VLMs-as-eyes, pixel vs DOM vs accessibility-tree parsing, multi-step autonomy, and research up to mid-2026.

**Stats (from workflow journal `wf_795b9b6f-454`):** 5 search angles → 24 sources fetched → **110 claims extracted** → 25 top claims adversarially verified (3 votes each) → **15 confirmed, 10 killed** → merged to **7 final findings**. 106 agent calls, 21.5 minutes, 2,304,147 tokens. 4 URL dupes removed, 2 sources dropped on budget.

### 2a. The 7 confirmed findings (verbatim from the workflow result)

1. **Pixel-only perception dominates** (high confidence, 3-0): frontier GUI agents (UI-TARS, Agent-S2, OmniParser) take raw screenshots only — no DOM or accessibility tree at inference time.
2. **OmniParser bridges DOM→pixels** (high, 3-0): trained a YOLOv8 detector on 66,990 web screenshots with DOM-derived bounding boxes, but the deployed model needs no DOM; 73.0% ScreenSpot accuracy.
3. **UI-TARS-72B beat Claude Computer Use & GPT-4o** (high): 24.6 vs 22.0 on OSWorld 50-step; 46.6 vs 34.5 on AndroidWorld (January 2025 snapshot) — via "System-2 Reasoning" (decomposition, reflection, milestone recognition).
4. **UI-TARS-2 hierarchical memory** (medium, 2-1): ReAct loop + Working Memory (recent steps, high fidelity) + Episodic Memory (semantically compressed history); claimed ~2.4× OpenAI CUA on a game suite (ByteDance's own report — see caveats).
5. **Agent-S2 pixel-grounding sub-model** (medium, 2-1): uses UI-TARS-1.5-7B as a dedicated coordinate-grounding model whose outputs become executable Python; outperformed OpenAI CUA/Operator and Claude Computer Use on OSWorld at publication.
6. **Cross-app workflows are near 0%** (high, 3-0): MacArena (ICML 2026 workshop) — all tested agents fail nearly all cross-application macOS workflows; dual-modality (pixels + optional accessibility tree) exposed.
7. **More reasoning can hurt agents** (medium, 3-0): Princeton HAL study (ICLR 2026) — higher reasoning effort reduced accuracy in 21/36 runs (58.3%); agents exhibit real-world aberrant behaviors invisible to pass/fail metrics.

### 2b. The 10 killed claims (do not cite — failed adversarial verification)

Agent-S3 "72.6% human-level OSWorld"; UI-TARS-2 "exclusively raw screenshots"; UI-TARS-2 "SOTA on Online-Mind2Web/OSWorld/AndroidWorld/SWE-Bench"; OpenAI CUA "31.83% on MacArena"; "grounding is THE bottleneck (2.8× vs 1.15×)"; "accessibility trees are counterproductive"; "GUI agents at 26.6% L3 / 8.78% L4"; OmniParser "AITW 53.0→57.7"; UI-TARS "42.5% OSWorld 100-step"; Adaptive VLM Routing "78% cost reduction".

### 2c. Open questions the research could not resolve

- Does hybrid input (screenshot + accessibility tree) reliably beat pixel-only on single-app tasks, or does tree noise/token overhead cancel the gain?
- Why does higher reasoning effort hurt (overthinking in sequential action selection vs a chain-of-thought failure mode)?
- What exactly blocks cross-app workflows (state representation vs action space vs focus switching)?
- No reviewed system demonstrated **online adaptation** to novel UI layouts mid-session — all use static fine-tuned weights.

### 2d. Caveats recorded by the workflow

Benchmark scores are time-sensitive (mid-2026 frontier models reach 70–85% on OSWorld-Verified, far above the January-2025 UI-TARS numbers). Agent-S2/UI-TARS-2 "beat Anthropic/OpenAI" claims compare against specific agent versions — and both use Claude or Qwen as backbone planners themselves. UI-TARS-2 multipliers come from an unreviewed ByteDance report on a self-designed game suite (self-serving selection risk). MacArena is a workshop preprint, not a full conference paper.

### 2e. All 24 sources (with angle and quality rating)

Full annotated list preserved in `research/gui-ai-agents-deep-research.md` §"ALL 24 SOURCES". Key primary sources:
- github.com/simular-ai/Agent-S · github.com/bytedance/ui-tars · github.com/bytedance/ui-tars-desktop
- arXiv: 2501.12326 (UI-TARS) · 2509.02544 (UI-TARS-2) · 2408.00203 (OmniParser) · 2504.14603 (WebXSkill) · 2604.13318 (UFO2) · 2603.12823 · 2606.06560 · 2507.19478 · 2510.11977 · dl.acm.org/doi/10.1145/3746027.3755688
- leaderboard.steel.dev · workos.com CUA-comparison blog · zylos.ai/research GUI-agents survey · aimultiple.com/open-source-web-agents · futureagi.com browser-agent evals · epam.com long-horizon agents (rated unreliable) · fazm.ai ×3 (blog/unreliable) · decisioncrafters.com (blog)

---

## 3. Video understanding (both videos fully reconstructed)

**Video 1 — AngelOne** (`research/video/angelone-login/understanding.md`, frames kept on disk): login at angelone.in → mobile 77026642xx → OTP typed manually on phone → account page (₹0 balance) → Markets equity overview (top movers SUMICHEM +43%, ZENSARTECH +45%) → NIFTY option-chain popup → SUMICHEM chart (₹502) with buy/sell buttons.

**Video 2 — Coinbase** (`research/video/coinbase-login/understanding.md`): coinbase.com → email sign-in → password → 2FA off-camera → Advanced Trade BTC-PERP order book (~$62,452) → futures list (BTC/ADA/SOL/ETH/DOGE/XRP Jul-26 contracts) → BTC 30m chart. **Constraint found: Coinbase CDX derivatives are view-only from India — brain can read but never place orders there.**

**Owner's auth decision:** manual OTP on first login + Playwright `storage_state` session cookies thereafter; same pattern for all brokers (AngelOne, Upstox, Binance, Bybit, Coinbase).

---

## 4. OSS research findings — the chosen stack (from `web-reader-oss-deep.md`, 570 lines, 5 angles)

**Angle 1 — Indian broker data (winner: mostly no browser needed):**
- `nsepython` (github.com/aeron7/nsepython) — NSE public APIs, zero login: full option chain OI, FII/DII, futures OI, OI spurts, F&O ban, block deals.
- `smartapi-python` (github.com/angel-one/smartapi-python, official) — TOTP auth → WebSocket 2.0 snap-quote for real-time option OI + LTP.
- `upstox-totp` (github.com/batpool/upstox-totp) + official `upstox-python` — unattended TOTP login.
- Groww: no SDK → Playwright network interception (pattern from github.com/Sparker0i/indian-stock-mcp-agent).

**Angle 2 — Crypto real-time:** `cryptofeed` (github.com/bmoscon/cryptofeed) is the clear winner — 40+ exchanges, normalized L2/funding/OI/liquidations. Backups: `pybit`, `binance-connector-python`, `coinbase-advanced-py`.

**Angle 3 — VLM screen reading:** OmniParser V2 (Microsoft, ~25k stars; GPU preferred, CPU fallback), UI-TARS-1.5-7B (61.6% ScreenSpotPro), `browser-use` (already vendored at `vendor/browser_use_src/`).

**Angle 4 — Unified screeners:** TradingView is the only app screening NSE + crypto together (Pine screener, no login for screener data).

**Angle 5 — Computer use / Claude Desktop mechanism (appended 14:12):**
- The mechanism is the **Computer Use API** (beta header `computer-use-2025-11-24`): send screenshot → Claude returns JSON action (`left_click`, `type`, `scroll`, `key`…) → execute via xdotool/Playwright → send new screenshot → loop. That loop IS Claude Desktop.
- Reference implementation: `anthropics/anthropic-quickstarts` computer-use-demo (~17.2k stars), bare Python + Xvfb + xdotool; with Playwright already in `.venv`, no Xvfb needed for browser work.
- Top picks recorded: Agent-S3 (`pip install gui-agents`) for task completion; SEAgent (github.com/SunzeY/SEAgent) self-evolving app learning; ZeroGUI (github.com/OpenGVLab/ZeroGUI) zero-human RL task generation; Midscene.js (github.com/web-infra-dev/midscene) natural-language Playwright actions; agentdesk (github.com/agentsea/agentdesk).
- **Key architectural insight saved:** vision (computer use) is the LEARNING phase — brain explores a new broker app once, discovers which internal URL carries the data via network intercept, stores it in experience memory; production phase then hits that URL with plain `requests` — zero clicks, zero vision cost.

**Install list for the build session:**
`pip install nsepython smartapi-python upstox-totp upstox-python "cryptofeed[all]" binance-connector pybit coinbase-advanced-py` (+ clone OmniParser if screen parsing is wanted).

---

## 5. Architecture decisions made (Q&A with owner)

1. **API vs browser vs app filters:** hit the brokers' own **pre-calculated screener endpoints** directly (NSE live-analysis OI spurts, `/api/option-chain-v3`, Binance `fapi/v1/ticker/24hr` + `premiumIndex`, Bybit `v5/market/tickers`) — one REST call returns server-side-ranked results; CPU does nothing but parse JSON. Browser is only (a) a one-time OTP/cookie capturer and (b) a one-time endpoint-discovery spy via `page.on("response")`. Never keep a browser open just to poll.
2. **One app for both markets?** None exists. TradingView is the only cross-market pattern screener; genuinely app-only data is narrow (IV rank, liquidation heatmap, sector heatmap).
3. **With 32 GB RAM (owner's correction):** run **3 persistent headless browsers** (~1.5 GB total) — TradingView (cross-market screener + sector rotation), Binance (liquidation heatmap, long/short ratio, funding momentum — no public API for these), AngelOne/Upstox (IV rank, OI heatmap) — plus direct REST for everything else. First login headful for OTP, then headless forever on saved cookies.

## 6. The confirmed 2-phase pipeline (owner-approved, saved in `web-reader-pipeline-design.md`)

- **Phase 1 — Scan (every ~30 s):** brain reads screener pages of TradingView + AngelOne + Binance via network interception → 10–20 candidates with `why_selected`.
- **Phase 2 — Deep dive (5–10 s per candidate):** navigate to the symbol's page, intercept everything (NSE: candles, order book, option OI+IV, delivery volume, news; crypto: candles, OB walls, funding, OI, long/short, liquidations) → decide direction, entry (OB walls + candle structure), stop loss (OB level + ATR buffer), target (R:R ≥ 2.0), confidence.
- Execution stays **API-only**: OpenAlgo (NSE) / Freqtrade (crypto). **The browser never touches an order button.**
- Build deferred by explicit owner instruction to a Fable 5 session; the partial `trading/web_reader/` scaffold (6 files incl. angelone/upstox/binance_web extractors) was built then deleted at 13:23 on the owner's interrupt.

---

## 7. Artifact inventory (everything that session left on disk)

| File | Size | Content |
|---|---|---|
| `research/gui-ai-agents-deep-research.md` | 673 lines / 57 KB | Full workflow dump: stats, exec summary, 7 findings, 10 refuted, open questions, caveats, all 24 sources, projects directory, technical deep-dives, **full 106-agent trace** |
| `research/web-reader-oss-deep.md` | 570 lines | 5-angle OSS research + recommended architecture + install list + ANGLE 5 computer-use append |
| `research/web-reader-broker-scraper.md` | 85 lines | First-round candidate table, recommendation, files-to-build, sources |
| `research/web-reader-pipeline-design.md` | 208 lines | Owner-confirmed 2-phase pipeline, per-app data map, browser session map, build order, design constraints |
| `research/video/angelone-login/understanding.md` (+frames) | 91 lines | Frame-by-frame AngelOne reconstruction |
| `research/video/coinbase-login/understanding.md` (+frames) | 97 lines | Frame-by-frame Coinbase reconstruction |
| `research/session-review-20260705-gui-web-reader.md` | this file | Consolidated session record + audit |

## 8. Data-loss audit (the owner's central worry — verified by Fable 5)

Cross-checked the workflow journal (`subagents/workflows/wf_795b9b6f-454`, 106 agent transcripts + result JSON) against the saved markdown:
- ✅ All 7 synthesized findings present with vote counts — match the journal exactly.
- ✅ All 10 refuted claims present with vote tallies.
- ✅ All 24 sources present with URL, angle-that-found-it, and quality rating.
- ✅ Open questions (4) and caveats — present.
- ✅ Full 106-agent trace section present (phases: 1 scope, 5 search, fetch, 75 verification votes, synthesis).
- ⚠️ Only nuance: "zero data loss" at the token level is physically bounded — the raw agent transcripts are 7.2 MB (mostly tool-call plumbing); the md preserves every *finding, claim, vote, and URL*, which is the meaningful 100%. The raw transcripts still exist at `~/.claude/projects/-home-karan18190164/7a1b852c-*/subagents/workflows/` if ever needed.

**Verdict: no findings were lost.** The session honored the "save everything" directive.

---

## 9. Fable 5 assessment (what I think)

**Strengths of that session:**
1. The research is genuinely good and honest — the adversarial verification killed 10 of 25 headline claims, including the most quotable ones (Agent-S3 "human-level", UI-TARS-2 "SOTA everywhere"). Most research sessions would have saved the hype; this one saved the refutations too.
2. The single most valuable output is the **vision-for-learning / interception-for-production** insight (§4 Angle 5): use expensive VLM screen-reading ONCE to discover a broker's internal JSON endpoints, then run production on plain REST. This resolves the CPU-first constraint and the "use app pre-calculated filters" wish simultaneously.
3. The pivot discipline was right: partial build deleted cleanly on your interrupt, no half-built code left on the branch, everything captured as design docs instead.

**Weaknesses / risks I flag before the build:**
1. **The 3-persistent-browser plan is heavier than claimed.** ~500 MB/browser is realistic but the real cost is fragility: broker web apps change DOM/endpoints without notice, sessions expire, anti-bot (Cloudflare/Akamai on NSE and Binance web) can block headless Chrome. The design's own REST-first findings (nsepython, smartapi, cryptofeed) cover ~90% of the data with none of that fragility — I would build the REST layer first, prove signal value, and add browsers only for the genuinely app-only trio (IV rank, liquidation heatmap, sector heatmap).
2. **Benchmark decay:** the confirmed findings are January-2025 snapshots; mid-2026 frontier (including current computer-use APIs) is far ahead. For the build, the *architecture patterns* (System-2 loop, hierarchical memory, grounding sub-model) matter more than any cited score.
3. **Terms-of-service exposure is unexamined.** Scraping logged-in broker UIs via network interception sits in a gray zone for AngelOne/Upstox; NSE public API and official SDKs (smartapi, upstox) don't. Worth one deliberate decision, since a banned broker account hurts the LIVE mode goal.
4. **Cross-app near-0% is a warning for scope:** keeping the brain inside per-broker browser sessions with narrow, learned routines (as designed) is exactly right; a free-roaming "control the whole computer" agent would sit in the failure regime the research itself documented.
5. The Coinbase work has limited payoff (view-only from India) — fine as a data feed, but Binance/Bybit should get build priority.

**Recommended build order for the Fable 5 session** (consistent with the saved design): 1) REST screener layer (nsepython + Binance/Bybit public + SmartAPI token) → feature_bus; 2) Playwright session vault + one-time endpoint-discovery recon per broker; 3) TradingView screener interception; 4) deep-dive Phase-2 decision module; 5) only then the vision/computer-use learning loop for new-app exploration.

*Everything above is traceable to the transcript at `~/.claude/projects/-home-karan18190164/7a1b852c-34b0-4a6c-86ee-b5bababd855d.jsonl` and the saved research files.*
