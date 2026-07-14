# Brain stagnated/unused-feature audit — 2026-07-14

**Scope (owner-approved):** whole brain + brain→trading funnel, code-verified, **report-only**.
**Method:** runtime *consumption* trace (does the decision path actually READ this feature's output?),
not just the static import graph — because the static graph hides "computed-but-unconsumed" (the exact
thing asked about). Static audit (`independent-audit-20260714-092507`) used as a second opinion.

## The one fact that reframes everything: there are TWO decision paths

| Path | Code | Drives | Consumes |
|------|------|--------|----------|
| **Real crypto trades** | `trading/crypto/freqtrade/brain_executor.py` → `trading/direction/learned_direction.decide()` | actual Freqtrade orders | app_signals (broker filters), direction_model, debate_gate, **symbol_move_net**, strategy_tournament (strategy_table), indicator_fusion + postmortem (sizing), regime, **conformal/UQ abstention** |
| **T8 "AI Brain / End-to-End Decision" panel** (the `BLOCKED` one) | `trading/brain/pipeline.py:BrainTradingPipeline.decide()` via `trading/online/live_loop.py` | a *separate* running loop (paper/advisory; NSE-side) — "paper-first, emits a decision, T3 places orders downstream" | regime, anomaly, news, evolved_strategy, experience, imagination(world-model), hypothesis |

**The features on the Brain dashboard that you photographed mostly belong to the T8 pipeline / learning
side — NOT the real crypto money path.** So "is the brain using this?" splits into: used by the *real
trade driver*, used only by the *T8 advisory loop*, or used by *nobody*.

---

## A. LIVE — output genuinely consumed by a trade decision
- **Metacognition / Conformal UQ (Pillar 17)** — `learned_direction.decide()` abstains when total edge-weight is below θ. This is a real gate on real trades. ✅
- **Symbol-Move Net** — `brain_executor.py:431-446` folds `p_up` into the fusion when `enabled() & trained`. ✅
- **Strategy tournament / table** — `brain_executor.py:464-494`, gated `STRATEGY_DIRECTION=1`. ✅
- **app_signals / direction_model / debate_gate** — the core fusion `_reads`. ✅
- **Experience recall, regime, anomaly** — consumed in the T8 pipeline decision (and regime in the real driver). ✅
- **Decision Memory / reflections, Hypothesis Ledger, Auto-Quiz** — consumed as *advisory nudges* / learning feedback (small ±0.05 confidence tweaks in `pipeline.py:179-182`), not directional drivers. Working, but low-leverage.

## B. STAGNATED — wired, but producing empty / broken / dry output
| Feature | Evidence | Why it's dead-on-arrival |
|---|---|---|
| **News Sentiment** | consumed in `live_loop.py` (T8) but BTC/ETH/SOL all `—` | vader backend returns nothing → `news_support=0.5` neutral → contributes zero. Wired to a path that isn't the money path anyway. |
| **Regime & Patterns `[object Object]`** | `BrainPanel.jsx:304` `d.regime?.current || d.regime` | API returns regime as an **object without `.current`**, so JS stringifies the whole object. Pure render bug; underlying regime value is fine (used in fusion). |
| **Evolution / Strategy Population** | `PROMOTED 0`, `0 candidates`, `GUARDRAIL FAILED` | The evolve→promote→`strategy_table` path exists (`trading/strategy/evolved_link.py`), but **nothing survives the guardrail**, so 0 flow through. Wired-but-dry. |
| **Self-Evolving Loop** | `ValueError: incorrect value for flags variable (overflow)` | Erroring at runtime; `GATED OFF · LIBRARY-FIRST`. Even if fixed, output only reaches the *T8* `evolved_strategy`, not the real driver. |
| **Continual learning** | panel shows `engine module 'numpy…'` | `continual.py` **imports fine**; the crash is at *runtime* when it builds the torch/Avalanche engine (numpy/torch ABI). Honestly surfaced. Not consumed by any trade path regardless. |
| **Concept Discovery** | `validated 1 / 12`, all "down-trend" | Near-homogeneous features, 1 usable. Referenced from `brain_executor.py` but effectively contributes nothing (11/12 unvalidated). |

## C. ORPHAN — computed but read by NObody on any trade path (0 hits in real-driver dirs)
- **World-model / Imagination** — only an advisory nudge inside the T8 pipeline; **0** references in `learned_direction/funnel/brain_executor`.
- **Skill Library self-improve / DSPy** — `SELF-IMPROVE —→—`, `DSPY OFF`; **0** in real driver.
- **metalearn, selfimprove, self_evolve, evolution, news, sentiment, continual** — all **0** in the real-driver dirs (grepped).
- **Computer-Use / Embodiment Agent** — `REACHABLE yes · CONTROLS FOUND 0`: it sees the dashboard but discovers no controls → actuates nothing. No trade path reads it.
- **RL execution env** — `trading/execution/rl_exec_env` + `rl_execution` form a **disconnected island** (only their own test imports them). Built, never wired into the executor.

## D. DEMO subsystems (honestly labelled — not faked)
`dashboard/routes/brain_ext.py` hard-codes `"real": False` for: **Brain agent, Self-coding autonomy,
Human memory, Librarian, Stream of mind** (+ hybrid). These are offline deterministic snapshots — built
P4.x capabilities that were never promoted to live (need network/embedding models). Honest, but "abandoned-in-place."

## E. Broken wiring (from static audit)
- **`/api/trading/brain/decisions`** — a UI panel calls it but **no backing route exists** → broken feature.
- 37 "unused endpoints" — most are `/api/brain/*` fetched on-click (false positives), but the DEMO set in (D) is genuinely idle.
- 126 orphans / 25 cycles — mostly dynamic-loader false positives (Freqtrade strategy autoload, node autoload); not chased here per prior audit lessons.

---

## Ranked "abandoned / not-used-by-the-brain" list (highest → lowest concern)
1. **World-model, self-evolve/evolution, skills-self-improve, continual, concept-discovery, computer-use** — big built subsystems whose output **never reaches the real crypto driver**. They feed only the T8 advisory loop or nothing.
2. **News sentiment** — empty output, and even when full only feeds the non-money T8 loop.
3. **Evolution/Strategy Population** — guardrail lets 0 candidates through; the whole evolve pipeline is dry.
4. **RL execution env** — orphan island, never wired to the executor.
5. **Regime `[object Object]`** — cosmetic render bug (1-line JSX fix), value itself is used.
6. **DEMO P4.x subsystems** — honest but idle (agent/autonomy/memory/librarian/stream).
7. **`/api/trading/brain/decisions`** — broken UI→route.

**Bottom line:** the real crypto money path is a fairly *narrow* fusion (broker filters + direction_model +
symbol_move_net + strategy_table + UQ gate). A large fraction of the impressive "brain" panels
(world-model, evolution, self-improve, concept-discovery, continual-learning, computer-use, news) are
**either advisory-only on a separate paper loop or fully orphaned** — they are not what picks or sizes
your live trades.

*Report only — no code was changed.*
