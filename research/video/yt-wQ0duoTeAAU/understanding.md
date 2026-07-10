# Video: "Build Self-Improving Claude Code Skills. The Results Are Crazy."

- **URL:** https://youtu.be/wQ0duoTeAAU
- **Author:** Simon Scrapes
- **Title (verified via YouTube oEmbed):** "Build Self-Improving Claude Code Skills. The Results Are Crazy."

## ⚠️ Provenance — HONEST
I could **NOT read the actual video**. Every yt-dlp path (full video, all player clients
tv_embedded/web_safari/ios/mweb, and subtitle-only) was blocked from this VM's datacenter IP with
"Sign in to confirm you're not a bot." So there are **no frames and no transcript** on disk. Only
the title/author are verified (oEmbed). The summary below is **reconstructed from web write-ups of
this same topic/creator**, not from the video's audio/frames — treat it as topic-level, not a
faithful frame-by-frame reading.

## What the video is about (web-reconstructed)
A tutorial on making a Claude Code **Skill improve itself over repeated runs** instead of starting
fresh each time. Core mechanism:

- **A memory file beside the skill** (e.g. `learnings.md` / `MEMORY.md`) is **read at the top of
  every run**. It holds observations from past executions: which patterns worked, which edge cases
  broke the skill, what the model tends to get wrong.
- **A learning loop:** after each run, the agent (or the user) **appends structured notes** about
  what worked / failed / new edge cases. The file becomes a growing knowledge base the skill
  consults before executing next time — knowledge **compounds across runs**.
- **An eval loop:** the skill is paired with evaluations that score its output, so "better" is
  measured, not assumed; failures feed back into the memory file.
- **Build-from-scratch in ~5 steps** (skill definition → eval → memory → run → append learnings).
- **Scales up** to an "agentic OS": many self-improving skills that run business tasks, improve
  from feedback, and maintain themselves.

## Relevance to THIS project
Directly on-point — this project already has the building blocks the video advocates:
- 26 custom skills in `.claude/skills/` + the **prompt-quality / understand-prompt** hook chain.
- A **file-based memory** system (`memory/MEMORY.md` + per-fact files) read each session — exactly
  the "memory file read at the top of every run" pattern.
- A **continuous-learning loop** and eval-ish harnesses (dashboard-visual-qa, interaction_qa,
  data_consistency_qa, independent-audit).
What's thinner here vs the video's recipe: a **per-skill `learnings.md` + explicit eval loop** that
each skill appends to automatically after every run (our memory is project-level, not per-skill).

## Open question for the user
Do you want me to actually build this — a **per-skill self-improvement loop** (each skill gets a
`learnings.md` + a PostToolUse/Stop hook that appends what worked/failed + an eval score)? Or did
you just want the summary?
