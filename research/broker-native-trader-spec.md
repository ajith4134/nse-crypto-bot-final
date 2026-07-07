# Broker-Native Trader — Build Spec (2026-07-05)

**Author:** Fable 5 · **Status:** framing → awaiting design confirm
**Grounded in:** research/web-reader-oss-deep.md, research/gui-ai-agents-deep-research.md, research/web-reader-pipeline-design.md, research/session-review-20260705-gui-web-reader.md
**Money-lens:** PROCEED (PAPER / learn-lab). Guardrails: app is eyes-only (never presses buy/sell), creds via Fernet vault, live behind guard flag, every outcome journaled.

---

## 1. The honest starting point — ~70% already exists

The `trading/broker_sense/` funnel + `trading/brain/gui/` already implement most of the owner's vision:

| Owner's requirement | Already built | File |
|---|---|---|
| Log into real broker accounts via dashboard creds + OTP | ✅ SessionManager, vault-backed, OTP-via-chat, storage_state persistence | `broker_sense/sessions.py:42` |
| Navigate app like a human — open segment, read ranked list, use built-in filters | ✅ app_screen opens broker movers/screener pages + TV pushdown lane | `broker_sense/screeners.py:113`, `:86` |
| Open symbol page, read multi-TF candles + indicators | ✅ ChartVision multi-TF screenshots → CNN + LLM vote | `broker_sense/chart_vision.py:61` |
| Read order book | ✅ BookMonitor OCR + API fail-safe | `broker_sense/book_monitor.py:109` |
| Decide direction; execute API-only; never press app buy/sell | ✅ funnel DECIDE+EXECUTE, read-only guard | `broker_sense/funnel.py:162`, `sessions.py:33` |
| Every observed datapoint → column on the trade, carried to close | ✅ ColumnRegistry.discover_from_text → decision_snapshot → journal | `broker_sense/learning_columns.py:83` |
| Paper now, live behind guard | ✅ ExecAdapter paper/real doors + guard | `broker_sense/exec_adapter.py:21` |
| Explore + catalog app features | ✅ FeatureCatalog, explore(), mind-stream announce | `broker_sense/app_explorer.py:73` |
| Dashboard shows what the brain sees | ✅ BrokerSensePanel.jsx (uncommitted) | `dashboard/web/src/trading/BrokerSensePanel.jsx` |

**Implication:** this is a reuse-first **upgrade**, not a greenfield build. We extend the funnel, we do not replace it.

## 2. The genuine gaps to build (the novel, high-value part)

The owner's strongest ask — "ultra-advanced human eyes and brain, how eyes store data in brain; upgrade BOTH Claude Computer Use AND DOM/interception" — is exactly what's missing:

- **G1 — No Claude Computer Use API integration.** Today the "eyes" are a 20×20 tiny CNN + PaddleOCR + Playwright DOM. No frontier visual understanding for reading an unfamiliar broker screen or acting on it.
- **G2 — No unified multi-modal perception frame.** Pixels, OCR text, DOM controls, intercepted network JSON, and API reference are read separately and never fused into one coherent "what is on this screen right now" object.
- **G3 — No visual/episodic memory of app layouts ("how eyes store data in brain").** FeatureCatalog stores button *labels* only — not coordinates, not layout, not "where the OI table lives," not which internal URL carries which data. The brain re-discovers every crawl instead of building a habit.
- **G4 — No golden-path recall.** No "on Binance, order book = this element / this intercepted endpoint" memory to go straight there like a human who's used the app 100 times.
- **G5 — No visual-outcome linkage.** decision_memory stores entry context as text; the actual chart/book image that drove the trade is deleted. Reflection can't "re-see" what it looked at.
- **G6 — No novelty detection.** When a broker redesigns a page, nothing notices; strategies silently read the wrong region.

## 3. What we build — the "Ocular Cortex" (new) + Computer-Use eyes, stitched into the funnel

### 3a. `trading/brain/gui/computer_use.py` — Claude Computer Use loop (upgrades "option 1")
Real Anthropic Computer Use API loop (beta `computer-use-2025-11-24`), **Playwright as executor** (no Xvfb/GPU): screenshot → Claude action JSON → execute on the existing SessionManager page → loop. Hard read-only guard (reuses `sessions.py` forbidden-control regex; the model is *never* allowed `left_click` on buy/sell/order/confirm/leverage). Cloud-cost-aware: only invoked for exploration + novel situations, not every cycle. Reuses `core.llm` provider stack.

### 3b. `trading/brain/vision/ocular_cortex.py` — the eyes→brain memory (invented; upgrades "option 2" + fuses with 3a)
Modeled on human visual memory (iconic → working → long-term consolidation):
- **PerceptualFrame** — one capture fuses ALL modalities of a broker screen: screenshot + DOM controls w/ bboxes + OCR numbers + intercepted network JSON (`page.on("response")`) + API reference quote. (G2)
- **Sensory/working memory** — ring buffer of last N frames per (broker, page); enables cross-cycle grounding ("depth ladder shifted +0.2% since last bar"). (G6)
- **Episodic visual memory (LayoutMemory)** — persisted per (broker, segment, page): element coordinates, the intercept-URL→data-kind registry, reliability/`n_seen`, last-verified ts. This is the "golden path" the brain reuses. Backed by the vendored A-MEM/HippoRAG associative store for semantic recall ("how do I read depth on this exchange"). (G3, G4)
- **Consolidation + novelty** — frame-diff vs last stored layout; stable layouts consolidate (habit), changed layouts flag novelty → trigger a Computer-Use re-exploration. (G6)
- **Visual-outcome link** — the PerceptualFrame that drove a decision is hashed + retained and linked to the `decision_memory` episode, so reflection can re-see it. (G5)

### 3c. Wiring into the existing funnel (reuse, minimal edits)
- `sessions.py`: attach a network-interception recorder to each page (feeds PerceptualFrame + endpoint registry).
- `funnel.py` LOOK/VERIFY: OcularCortex recall runs *first* (fast habit path); Computer-Use vision only on novelty/low-confidence. app_signals gains fused-perception fields.
- `app_explorer.py`: FeatureCatalog gains coordinates + endpoint registry from LayoutMemory.
- `learning_columns.py`: unchanged contract — fused numbers flow through the existing column path (so learning-columns requirement stays satisfied, now richer).
- `decision_memory.py`: `open_episode` stores the visual-frame handle (G5).

### 3d. Dashboard (extend `BrokerSensePanel.jsx`, honest wiring)
New sub-view: per-broker **Ocular Cortex** tiles — live PerceptualFrame thumbnail, known golden paths + reliability, novelty alerts, endpoint registry, visual-memory size. Real data from a new `/api/trading/ocular` route.

## 4. Acceptance criteria (done when…)
1. Brain logs into AngelOne + Binance real accounts (paper exec) and completes a full funnel cycle using OcularCortex recall for known layouts and Computer-Use vision for novel screens — verified live.
2. A PerceptualFrame fuses ≥4 modalities (screenshot+DOM+OCR+network/API) into one object; unit-tested.
3. LayoutMemory persists and recalls a golden path across process restarts; second visit to a page uses recall (no full re-crawl) — tested + shown in logs.
4. Novelty detection flags a changed layout and triggers Computer-Use re-exploration — tested with a synthetic layout change.
5. Every observed datapoint still becomes a learning column on the open trade, carried to close (existing contract preserved) — tested.
6. The brain **never** issues an in-app order action; execution is API-only, paper, live behind guard — enforced + tested (RoleViolation / forbidden-action).
7. Dashboard Ocular Cortex view renders real data, passes dashboard-visual-qa, no fake tiles.
8. Full test suite green; INDEX.md regenerated; secrets-safe.

## 5. Reuse ledger
- Vendored `browser_use_src` (browser control patterns), `a_mem`/HippoRAG (associative visual-memory index), `finmem` (episodic decay pattern already in decision_memory), PaddleOCR (perception), Playwright (executor + interception).
- New deps to request if needed: `anthropic` SDK for Computer Use (likely already present via core.llm — verify before asking).
- Existing project code reused verbatim where possible: SessionManager, ExecAdapter, ColumnRegistry, ChartVision, BookMonitor, DecisionMemory, ComputerUseAgent/perception/actions.

## 6. Build order (vertical slice first)
1. Network-interception recorder on SessionManager + endpoint registry (foundation for frames + fast reads).
2. OcularCortex: PerceptualFrame + working memory + LayoutMemory (persist/recall) + consolidation/novelty — with tests against an oracle.
3. Claude Computer Use loop (read-only guarded) + novelty-triggered exploration.
4. Funnel wiring (LOOK/VERIFY recall-first) + decision_memory visual link + learning-column passthrough.
5. Dashboard Ocular Cortex view + /api/trading/ocular route.
6. Live verify on AngelOne + Binance (paper) + dashboard-visual-qa + code-review + gen-index.
