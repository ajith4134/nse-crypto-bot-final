---
name: dashboard-redesign
description: Invent a dramatically better dashboard — research SOTA patterns, propose 2-3 redesign directions (mockups + rationale), build the approved one reuse-first, and prove it beats the old version with dashboard-visual-qa. Use when the goal is to REDESIGN the look/feel/UX/information-architecture (not to check the current one works — that's dashboard-visual-qa). PROPOSE→APPROVE: never rewrite UI until the direction is approved.
---

# Dashboard Redesign ("invent the best version")

*(Thinned 2026-07-16, owner-approved: gates kept, step narration + library shopping list cut —
research the current SOTA fresh each time.)*

Sibling to **dashboard-visual-qa** (which *verifies*); this skill *invents*. NOT for "does it
work" (→ dashboard-visual-qa) or "add one panel" (→ add-panel).

## The gates (non-negotiable)
- **PROPOSE→APPROVE:** baseline with `dashboard-visual-qa` evidence, research reuse candidates
  (`research-projects`), then present 2–3 distinct directions with mockups via AskUserQuestion —
  ZERO code changes until the owner picks one.
- **Honest + working:** a redesign changes the SKIN — every real data binding and wired control
  must survive, proven by interaction-qa + data-consistency. Never trade correctness for looks.
- **Faster or equal:** load/FCP/bytes must not regress vs baseline (dashboard-swr-performance);
  a prettier-but-heavier version is a regression — fix or drop.
- **Prove it beats the old one** end-to-end with dashboard-visual-qa (landed + pixel diff +
  interaction + data-consistency + perf deltas) before calling it done; commit via `commit-safe`
  (`rebuild-frequi` if FreqUI touched).
