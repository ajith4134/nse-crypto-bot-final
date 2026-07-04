---
name: dashboard-redesign
description: Invent a dramatically better dashboard — research SOTA dashboard/UX patterns, propose a few redesign directions (mockups + rationale), build the best one reuse-first, and prove it beats the old version with the dashboard-visual-qa skill (render/interaction/data-consistency + faster-lighter). Use when the goal is to REDESIGN or level-up the look/feel/UX/information-architecture of a dashboard (not to check the current one works — that's dashboard-visual-qa). PROPOSE→APPROVE: never rewrite UI until the direction is approved.
---

# Dashboard Redesign ("invent the best version")

Sibling to **dashboard-visual-qa** (which *verifies* the current UI). This skill *invents a better
one*. It is **PROPOSE → APPROVE**: research + propose directions, get the owner's pick, then build +
prove. Never silently rewrite the working UI.

## When to use
"Make the dashboard better / more beautiful / clearer / more modern", "redesign this panel", "best
version you can invent", information-architecture rework, theme/density/hierarchy overhaul. NOT
for "does it work" (→ dashboard-visual-qa) or "add one panel" (→ add-panel).

## Procedure

1. **Baseline the current design (evidence, not opinion).** Run `dashboard-visual-qa`
   (`visual_qa.py --label baseline`) to screenshot every view + capture load/FCP/bytes, and note the
   concrete problems: layout/grid, visual hierarchy, density, colour/contrast, typography, spacing,
   consistency, empty/loading states, mobile/responsive, load weight. List them as a design-debt table.

2. **Research SOTA (reuse-first).** Invoke **research-projects** for the best current dashboard/UX
   references + OSS you can actually stitch in — e.g. design systems & component libs (Tremor,
   shadcn/ui, Radix, MUI, Mantine), data-viz (visx, ECharts, uPlot, lightweight-charts, D3), pro
   trading/quant dashboards (TradingView, Grafana, OpenBB), dashboard layout kits. Read only cheap
   signals (README/docs/stars/screenshots) during selection; save findings to `research/`.

3. **Propose 2–3 distinct directions.** For each: a one-line concept, an ASCII/markdown mockup of the
   new layout + component choices, what OSS it reuses, the migration cost, and why it beats the
   baseline on hierarchy / clarity / density / speed / beauty. Use **AskUserQuestion** (previews) so
   the owner can compare side-by-side and pick. **Do not code yet.**

4. **Build the approved direction (reuse-first).** Use **build-from-oss** / **stitch-projects** to
   adapt the chosen design system + viz libs into `dashboard/web/src/*` (keep the Dark-Pro identity
   unless the redesign IS the theme). Preserve every real data binding + control wiring — a redesign
   changes the SKIN, never fabricates data (honest-dashboard-wiring). Keep it CPU-light + fast-loading
   (dashboard-swr-performance); reject a prettier-but-heavier version.

5. **Prove it beats the old one.** `cd dashboard/web && npm run build`, `tools/restart_dash.sh`, then
   run **dashboard-visual-qa** end-to-end on the new build: (a) **landed** + before/after pixel diff,
   (b) **interaction-qa** — every input/button still works, (c) **data-consistency** — still true to
   disk, (d) **faster/lighter** — load/FCP/bytes not regressed. Show the before/after screenshots +
   the metric deltas. If it's not clearly better on look AND not worse on speed/correctness, iterate
   or revert — never ship a regression.

6. Commit via **commit-safe** (rebuild the FreqUI overlay with **rebuild-frequi** if FreqUI was
   touched; **gen-index** if modules changed).

## Guardrails
- **PROPOSE→APPROVE:** steps 1–3 make ZERO code changes; only build after the owner picks a direction.
- **Reuse-first:** adopt a proven design system / viz lib; hand-roll only glue + bespoke panels.
- **Honest + working:** the redesign must pass interaction-qa + data-consistency unchanged — new skin,
  same real data + same wired controls. Never trade correctness or honesty for looks.
- **Faster or equal:** a redesign that renders slower/heavier than baseline is a regression; fix or drop.
