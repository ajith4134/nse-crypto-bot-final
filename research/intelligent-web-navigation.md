# Intelligent web-navigation for the brain's Binance browsing (research, 2026-07-11)

Owner problem (watching the Screen Mirror): the brain's Binance web navigation is DUMB — it loops on
the same page and opens the OPTIONS segment even though options is toggled OFF. Make it intelligent;
research SOTA web-nav agents; propose→approve before building.

## Map-first (what we ALREADY have — the gap is a LOOP + a GATE, not a missing agent)
- **`trading/brain/gui/ComputerUseAgent`** already runs observe(target) → decide(goal)=recall lessons
  + retrieve skill + safety + PLAN → act(plan) → learn() → practice(n). BUT: (a) it's aimed at our
  OWN DASHBOARD, not driving Binance nav; (b) it has **NO VALIDATOR** — nothing re-reads the page after
  an action to check "did we get where we planned? are we stuck?" → so it can loop.
- **vendor/browser_use_src** (browser-use, DOM autonomous), **vendor/voyager** (skill learning),
  **vendor/reflexion** (self-reflect), `live_browser.py` / `human_ui.py` (Playwright eyes+hand),
  `core/llm.vision_chat` (local qwen2.5-vl:7b) — all present.
- **The bug:** `run_funnel_loop.py:181` drives options via `enabled_segments()` (+ optional `active`),
  which DISAGREES with the dashboard's `boss.active_segments` → options opens when "off". Navigation is
  funnel-driven and dumb, NOT routed through the perceive-plan-act agent.

## Phase-1 shortlist (SOTA web-nav agents)
| Project | Approach | Planner / Validator | Stuck-recovery | Local-LLM / CPU | Fit | Verdict |
|---|---|---|---|---|---|---|
| **Skyvern 2.0** | vision-first | **Planner-Actor-Validator** loop; 45→**85.85%** WebVoyager | **Validator re-reads post-action screenshot, replans on mismatch** | framework (AGPL); cloud-oriented | **10 (pattern)** | **ADOPT THE PATTERN** — Planner-Actor-Validator + replan-on-stuck is exactly the missing piece; too heavy/AGPL to vendor whole |
| **browser-use** (VENDORED) | DOM autonomous | goal→steps planner | retries | local-LLM OK | 9 | **REUSE** for robust low-level DOM actions |
| Agent-E | DOM-only | hierarchical | — | efficient, no vision | 7 | reference — DOM parsing beat vision baselines on 643 tasks (cheap) |
| Stagehand | DOM + self-heal | act()/observe() | **self-heals cached action via LLM re-map** | local-LLM OK | 7 | self-heal pattern for cached selectors |
| LaVague | command exec | none (step cmds) | manual | ok | 5 | too low-level |
| our gui/ComputerUseAgent | perceive-plan-act-learn | plan yes / **validator NO** | none | uses core/llm | base | **THE BASE to extend** |

## Recommendation — STITCH (reuse-first), don't adopt a new heavy framework
Add the ONE missing thing (Skyvern's **Validator + replan loop**) to our existing agent, and ROUTE
Binance navigation through it, gated by the real segment toggle:

1. **Planner** (core/llm text) — decompose the goal ("screen the enabled crypto segments for entries")
   into sub-goals; **hard-gate by `boss.active_segments`** so it can NEVER plan to open an OFF segment.
2. **Actor** — reuse `gui/actions` + `human_ui` + **browser-use** (vendored) for robust DOM clicks/nav.
3. **Validator (NEW)** — after each action, re-read the page (local **qwen2.5-vl:7b** vision + DOM):
   did we reach the sub-goal? **Stuck-detector**: same page-signature (URL+DOM/screenshot hash) N times
   → declare stuck → hand error context back to the Planner to REPLAN / escape (Skyvern pattern).
4. **Memory** — voyager skills + reflexion notes: learned nav macros that succeed get promoted; the
   Truth-Ledger-style success stats already on ComputerUseNode track credence.
5. **Fix the gate bug** — the funnel options-driver must consult `boss.is_segment_active`, the SAME
   source as the dashboard toggle (kill the enabled_segments vs active_segments disagreement).

Result: a Planner-Actor-Validator navigation brain that explores the Binance UI purposefully, never
opens an OFF segment, and escapes loops by replanning when the Validator sees it's stuck.

Sources: skyvern.com/blog/skyvern-2-0 · github.com/skyvern-ai/skyvern · steel-dev/awesome-web-agents ·
dev.to framework-wars (browser-use/Stagehand/Skyvern) · aimultiple open-source-web-agents.
