# Hermes Agent (Nous Research) — research + integration assessment

Researched 2026-07-06. Primary sources: official site, GitHub repo, Nous announcement.
Question: what is it, and would integrating it help our CPU-first trading-brain project?

## What it is (A–Z, verified)
**Hermes Agent** — an open-source, **self-hosted, self-improving autonomous AI agent** by Nous
Research (first release Feb 2026; **v0.18.0**, July 2026). "The AI agent that grows with you." It's
a *general-purpose personal agent runtime* (its own CLI + loop), not trading-specific.

- **Self-improving loop (its headline feature):** after solving a hard task it **writes a reusable
  skill document** (procedural memory), and skills **self-improve during use** — the exact
  "compounding skills" idea from the Simon Scrapes video. Uses the **agentskills.io** open standard
  so skills are searchable/shareable.
- **Memory model:** agent-curated memory with "periodic nudges", **full-text search across session
  history** (LLM-summarised cross-session recall), and **Honcho dialectic user modeling** (a
  deepening model of the user). Data stored locally in **`~/.hermes/`**.
- **LLM backends:** Nous Portal (OAuth), **OpenRouter** (200+ models), **OpenAI-compatible custom
  endpoints**, **local vLLM**. Swap with `hermes model` — no code change.
- **Integrations:** 40+ built-in skills (MLOps, GitHub, diagramming, notes); messaging via
  **Telegram, Discord, Slack, WhatsApp, Signal, CLI**; parallel sub-agents; cron automations;
  browser/web control.
- **Licence:** **MIT**. **Language:** Python (82%).
- **Hardware:** **No GPU required** — "runs on a $5 VPS", Linux/macOS/WSL2/Termux/Windows, one-line
  install. ← fits our **CPU-first** rule.

## Hype check (verify-first)
Reported **~210k stars / 38.5k forks / "most-used agent on OpenRouter"** in ~5 months. Those
numbers are **implausibly large for the timeframe** and come partly from SEO blogs — treat as
marketing, not fact. What's *verifiable and relevant* is the technical design (MIT, Python, CPU-ok,
skill-writing loop, agentskills.io), which is solid regardless of the star count.

## Candidate table
| Project | Repo | Key features | Activity | Fit score | Verdict |
|---|---|---|---|---|---|
| Hermes Agent (whole runtime) | github.com/NousResearch/hermes-agent | self-improving skills, memory, messaging, sub-agents, cron, browser | active (v0.18.0 Jul 2026) | 4/10 as-a-whole | **Don't adopt wholesale** — a competing general agent, redundant with our brain + Claude Code |
| Hermes *skill-writing loop* (idea/mechanism) | ^ (extract) | procedural memory: agent writes/improves a `learnings.md`-style skill after each task | — | 8/10 | **Adopt the pattern** reuse-first (matches the video ask) |
| Hermes *messaging bridge* (Telegram) | ^ (extract) | control/alert the brain from a phone | — | 7/10 | **Optional, high owner value** (non-coder owner) |
| agentskills.io format | agentskills.io | portable skill schema | — | 6/10 | Align our `.claude/skills/` to it if we want shareable skills |

## Assessment for OUR project
We **already have** the bulk of what Hermes is: 26 Claude skills, file-based memory
(`memory/MEMORY.md` read each session), a continuous-learning daemon, and a 12-provider LiteLLM
failover (`core/llm.py`). Adopting the *whole* Hermes runtime would stand up a **second, competing
brain** with its own loop/CLI — redundant, and it does **no trading** (our core). Net: low value as
a wholesale integration, real value as **cherry-picked patterns**.

**What Hermes has that we genuinely lack (worth taking):**
1. **Agent-authored procedural memory** — skills that the brain *writes and refines from its own
   task outcomes*, not just human-authored. This is the self-improving-skills idea; highest value.
2. **Messaging bridge (Telegram)** — remote alert + command of the brain from a phone; high value
   for a non-coder owner (ties to the existing Brain-Chat/boss-command system).
3. **Cross-session full-text memory search** — our memory is index-file based; full-text recall over
   all past sessions/decisions would strengthen the decision-memory feature.

## Recommendation
**Do NOT wholesale-integrate the Hermes runtime.** **DO** implement two Hermes-inspired capabilities
reuse-first: (1) a **self-improving per-skill learning loop** (procedural `learnings.md` per skill +
a Stop/PostToolUse hook that appends what worked/failed + an eval score) — same deliverable as the
video; (2) optionally a **Telegram control/alert bridge** wired to the existing boss-command brain.
Both are small, CPU-only, and additive — no competing agent. PROPOSE→APPROVE before building.
