# CLAUDE.md — Project Instructions for Claude Code

> Loaded into context every session. Keep it tight. The detailed, authoritative
> docs live in the files linked below — read those when you need depth.

## What this project is
A **CPU-first "network of prediction models with a brain"**: hundreds of ML/DL/quant
models wired as graph "nodes", plus an outside **brain agent** that reads books/PDFs/news
into memory, learns, and learns *how to wire and route the nodes*. Primary domain is
**trading/quant** (crypto via Freqtrade, NSE/options via OpenAlgo), with a live
React + D3/Three.js dashboard. GPU is off for now, flag-switchable later.

## ⭐ PRIME DIRECTIVE (the WHY)
Generate **consistent, risk-managed income** — a repeatable living, not a lottery.
- **PAPER mode** = unlimited-risk learning lab; blowups are training data.
- **LIVE / real money** = capital-preservation FIRST, all guardrails enforced, reached
  only after a strategy proves consistently profitable on paper.
- Run `/money-lens` before any money/risk/build decision. See `/goal` for the full statement.

## Non-negotiable rules (full list in `CONVENTIONS.md`)
`prompt-rating | reuse-first | ask-to-install | polyglot | auto-index | enforced-interfaces | secrets-safe | dashboard-sync | never-skip`

- **Reuse-first (search-copy-adapt-stitch):** for ANY new code, FIRST search GitHub/OSS for
  working code and adapt/stitch it. Write from scratch ONLY when nothing exists.
- **Auto-index:** `INDEX.md` is machine-generated (AST parse) — never hand-edit. Read it
  FIRST to get grounded, then open only the files you need. Regenerate via
  `python3 tools/gen_index.py` (a pre-commit hook also does this).
- **Enforced interfaces:** every node implements the shared `NodeProtocol` (`fit`, `predict`,
  `golden_dataset`, typed schemas) and self-registers. Non-conforming nodes fail at import/test.
- **Secrets-safe:** API keys live ONLY in gitignored `.env`. NEVER commit or echo real keys.
  Never commit `.env`, `trading/crypto/freqtrade/config.json`, `*.sqlite*`, `trading/state/`,
  `tunnel.log`, or `.paddlex/`.
- **Dashboard-sync:** every node/feature appears on the animated dashboard, auto-reflecting additions.
- **Self-documenting names + 1–2 line module docstrings** on every file.

## Where things live
- `trading/` — brain, broker_sense funnel, execution, crypto (Freqtrade), NSE/options, direction.
- `dashboard/` — FastAPI server (`server.py`) + React app (`web/src/trading/`) + built assets (`static/`).
- `vendor/` — vendored OSS (frequi, browser_use, etc.); update via `/vendor-update`, preserve local edits.
- `research/` — persisted findings, audits, datasets (most gitignored).
- `tests/` — `python3 -m unittest discover -s tests` (`ML_NETWORK_SKIP_HEAVY=1` for quick runs).

## Read these for depth
- `CONVENTIONS.md` — the standing coding rules (read before writing code).
- `PROJECT_BRIEF.md` — vision, goal, captured owner plans.
- `FOUNDERS_INTENT.md` — the owner's vision and journey.
- `INDEX.md` — auto-generated module/function map (read FIRST to get grounded).
- `ml-network-master-plan.md` and the other `ml-network-*.md` — architecture blueprints.
- `trading-execution-blueprint.md`, `t8-stitch-blueprint.md` — trading execution plan.

## Workflow
- Skills carry repo-specific commands/traps — invoke the matching one (see `.claude/skills/`).
  New feature → `research-projects` + `build-from-oss`; bug → `debug-error`; after code
  changes → `run-tests` + `verify-live`; committing → `commit-safe`; FreqUI touched →
  `rebuild-frequi`; Python modules changed → `gen-index`.
- Prefer targeted module tests over full-suite discovery (full suite times out with live loops running).
