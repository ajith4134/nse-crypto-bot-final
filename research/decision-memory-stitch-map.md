# Decision-Memory Upgrade — Stitch Map (2026-07-03)

Goal: every trade is a fully-provenanced EPISODE the brain can recall and learn from —
what it considered at entry (symbol choice, direction, entry price, features, signals,
psychology), which data drove the decision and how much (attribution), and what happened
(outcome + reflection + brain-correct).

Donor surveys: `trade-journal-decision-provenance-oss.md`,
`episodic-memory-trading-agents.md`, `decision-lineage-feature-attribution-logging.md`.

## Feature × project matrix

| Feature | Best donor | What we take | Lands in | Glue |
|---|---|---|---|---|
| Layered episodic store (shallow/mid/deep) with importance + recency decay, P&L re-weighting | **FinMem** (`vendor/finmem/puppy/memorydb.py`, `memory_functions/`) | layer semantics, decay/importance formulas, feedback promotion/demotion | `trading/brain/decision_memory.py` | adapt to state.save_json persistence; episodes keyed by trade_id |
| Outcome closure: stored decision later *resolved* with realized P&L + one-paragraph reflection injected into future decisions | **TradingAgents** (`vendor/tradingagents/.../reflection.py`, memory) | resolution flow + reflection prompt structure | `decision_memory.resolve()` called from journal close paths | LLM via `core/llm.py` failover, template fallback when no LLM |
| Verbal self-reflection buffer (gradient-free learning) | **Reflexion** (already vendored, `trading/brain/gui`) | reflection framing (actor/evaluator/self-reflection) | reflection text stored on episode + journal column | reuse prompt shape only |
| Retrieval score recency × importance × relevance | **Generative Agents** recipe (via FinMem's implementation) | scoring combination | `decision_memory.recall()` | relevance via `memory/associative.py` embeddings |
| Associative multi-hop recall backend | **our own** `memory/associative.py` (HippoRAG/A-MEM stitch) | search API | recall() relevance term | none — reuse |
| Per-decision feature attribution ("which data led to this and how much") | **SHAP** (pip, TreeExplainer/Explainer) | attribution engine | `trading/brain/attribution.py` over TradeOutcomeNet features | budget-capped, CPU; JSON column `feature_attribution` |
| Record-template schema: prediction record → attribution record → outcome record linked by id | **qlib** recorder pattern (docs only) | 3-record shape | episode dict layout in decision_memory | none |
| Trade-record analytics table | our 85-col journal (already exists) | — | journal schema gains `episode_id`, `feature_attribution`, `exit_reflection` | schema + fixed view columns |
| Human review taxonomy (tags/mistakes/playbook) | TradeNote/TradeTally (concept only, JS) | column ideas only | future | — |

Overlaps resolved: FinMem vs mem0/Letta → FinMem (outcome-aware, tiny, we own the loop).
Generative-Agents scoring comes via FinMem's implementation (same recipe) — no separate vendor.
FinAgent dual-level reflection (market-level vs decision-level) has no repo → its *concept*
ships as two reflection scopes in resolve() (per-trade + periodic per-symbol lesson).

Gaps (from-scratch, glue only): wiring into live_loop/brain_executor/journal, the
/api/trading/brain/decisions endpoint + DecisionMemoryPanel, tests.

## Vendored donors
- vendor/finmem — https://github.com/pipiku915/FinMem-LLM-StockTrading @ be814aa
- vendor/tradingagents — https://github.com/TauricResearch/TradingAgents @ 85946c2
- shap 0.48.0 via pip (.venv)

## Wiring plan
1. Entry (paper loop `_open_trade`; Freqtrade `brain_executor._record_entry_meta`):
   `decision_memory.open_episode(trade_id?, symbol, market, segment, direction, entry_price,
   decision_snapshot, brain, psych, features, attribution)` → episode_id returned, stored in ot /
   sidecar meta so the close path can link it.
2. Attribution at entry: `attribution.explain(feature_vector)` (SHAP over TradeOutcomeNet,
   fallback: gradient×input) → top-k feature contributions JSON.
3. Close (live_loop journal block; freqtrade_ingest map_trade when sidecar hits;
   journal.record hook): `decision_memory.resolve(episode_id, net_pnl, r_multiple,
   exit_price, exit_reason, brain_correct)` → importance re-weight + reflection text →
   journal columns `exit_reflection`, episode promoted/demoted across layers.
4. Recall before new decisions: pipeline decide() + brain_executor consult
   `decision_memory.recall(symbol, context_text, k)` → lessons list injected
   (recall_bias / prompt context).
5. Dashboard: GET /api/trading/brain/decisions (episodes + stats), DecisionMemoryPanel.
