# Brain vs SOTA + advance-everything proposal (2026-07-13)

Grounded: 831 modules, 135 deps, 37 vendored OSS. Audit 20260713-054103.

## 1. Brain vs SOTA online projects (benchmark)
| Capability | SOTA online | Ours | Verdict |
|---|---|---|---|
| Multi-agent firm (bull/bear/risk debate) | TradingAgents v0.2.4 (LangGraph, 12 agents), TradingGroup, ContestTrade (internal contest) | DebatePanel + tradingagents vendored + finmem | ~parity; MISSING the *internal-contest* selection + structured debate driving the actual trade |
| Memory + reflection | FinMem, FinAgent (dual-level reflection + diversified retrieval) | HippoRAG+A-MEM, FinMem episodes, Reflexion, neuron web | AHEAD (we have the web-of-neurons + evolution) |
| Instruction evolution | GEPA/PromptBreeder | evolution.py + induction + apply | AHEAD |
| Self-eval / curriculum | Voyager | school L0-L6 + self_eval | ~parity |
| **Direction prediction** | orderbook microstructure + CatBoost direction-aware GMADL objective, DeepLOB, Hawkes return-sign; "better INPUTS > deeper models" | learned_direction (Hedge) + direction_equation + cnn_direction, ~40% accuracy | **BEHIND — the frontier is microstructure inputs + direction-aware objective; we have the inputs (OFI/microprice/walls) but don't feed a direction-aware model, and don't record what drove each trade** |

## 2. Direction diagnosis (owner's #5) — CONCRETE
- Only **79/300 (26%)** recent trades record their direction rationale in decision_snapshot; **74% have NO "why this direction" data**.
- signal_source split: brain 210, momentum 89 — the learned-direction driver is NOT consistently used; ~74% bypass fusion entirely.
- indicator_fusion block empty on the last trade → no p_up / direction_equation / consulted lenses recorded.
- Root: direction is decided in multiple places (learned_direction, direction_equation, cnn_direction, momentum lane, filter lane) and the snapshot isn't populated uniformly → can't audit or improve accuracy.

## 3. Ranked proposal (impact × confidence ÷ effort)
| # | Idea | Type | Why it beats what we have | Reuse | Effort/Risk | Pillar |
|---|---|---|---|---|---|---|
| A | **Direction Decision Ledger + one unified direction driver** — every trade records the FULL direction rationale (each lens's vote+weight, p_up, the microstructure inputs, which driver won) into decision_snapshot; a single `decide_direction()` seam all lanes call; a dashboard "Direction X-Ray" panel per trade | new+replace | fixes 74% blind trades; makes accuracy improvable; SOTA = better inputs, measured | indicator_fusion, learned_direction, trader-psychology (OFI/microprice/walls) | M / low (attribution, paper) | direction program |
| B | **Direction-aware microstructure model** — CatBoost/gradient-boost on OFI+microprice+walls+funding+OI+CVD with a direction-aware objective (GMADL-style) + meta-label gate; replaces the near-random vote | replace | SOTA consensus: microstructure inputs + direction-aware objective; we already capture the inputs | catboost, our psych/order_flow signals, meta_labeler | M-L / med | direction program |
| C | **Screener/Filter exploitation engine** — enumerate EVERY Binance + Upstox built-in filter/screener (movers, gainers/losers, funding, OI, long/short, taker, volume-shock, 52w, option-chain OI, PCR…), rank the universe by learned filter presets, feed top-N + the filter evidence into direction | new | uses the brokers' compute for free (motto); breadth + edge from filters we already capture | ui_market, binance_filter_lane, screeners.py | M / low | motto/breadth |
| D | **Dashboard v2 (simple→advanced)** — brain-OS "mission control": per-trade Direction X-Ray, live decision replay, per-market scorecards, filter/screener heatmap, one dense cockpit; SOTA dashboard IA | redesign | current is many flat panels; make it a focused command surface | dashboard-redesign skill, Recharts | L / med | dashboard |
| E | **Internal-contest debate driving trades** — bull/bear/risk agents actually contest each candidate; winner's thesis (with direction) drives the trade + is recorded | new | ContestTrade/TradingGroup SOTA; our debate is a panel, not a driver | DebatePanel, tradingagents, boss | M / med | cognition |
| F | **Brain-driven UI trading everywhere** — nav_brain follows induced route instructions to read every data kind on both apps; funnel consults the full neuron web (not k=3) for each decision | extend | pushes brain into every UI trade decision; raises genius-use | nav_brain, consult, apply | M / med | R12/R13 |

## Recommendation
Do **A → B → C** in sequence (direction is the owner's repeated pain + highest ROI): A makes it *transparent & measurable*, B makes it *accurate*, C feeds it *better breadth*. D/E/F follow.
