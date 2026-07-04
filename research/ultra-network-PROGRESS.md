# Ultra-Network Redesign — Pipeline State (resume file)

> Purpose: if the session/context is lost, a fresh session resumes from HERE.
> Updated: 2026-07-03 ~20:50 — PAUSED by user near token limit.
>
> PAUSE STATE: the 3 research agents (frontier / SOTA / data-plan) were still running
> at pause time and write their docs to research/ on completion. On resume: check
> whether research/ultra-network-frontier.md, research/video-requirements-sota.md,
> research/ultra-network-data-plan.md exist. Any missing → relaunch that agent with the
> brief in "In flight" below (full briefs are reproducible from it + MASTER-REQUIREMENTS).
> Then continue at "Next steps" step 2 (write the invention design).

## The mission (user mandate, saved in memory/ultra-network-mandate.md)
Invent a NEW ultra-advanced neural network where each node is a full ML model.
Stitch: 9 user videos (EVERYTHING in them = requirements) + saved plan + frontier research
+ own inventions. Full permission to redesign/replace the existing 320-node column network.
Download whatever's missing. Implement end-to-end. Think big, aim high.
Order fixed by user: read videos → THEN research (requirement-driven) → design → implement.

## Done
1. **video-understand skill** built (.claude/skills/video-understand/): ingest.py (ffmpeg
   keyframes + faster-whisper CPU + yt-dlp) + SKILL.md. Deps installed: ffmpeg 7.1,
   faster-whisper 1.2.1, yt-dlp. Notes: research/video-understand-skill.md
2. **8 of 9 videos ingested + fully read** → research/video/<slug>/{frames/,transcript.md,
   manifest.json,understanding.md}. Slugs: nn-in-minutes(32 REQs), python-nn-price(30),
   lstm-codetrading(22), transformer-codetrading(45), krafer-patterns(27),
   greencode-scratch(29), joshua-trades(14), robot-learning(12). Total 211 REQs.
   Reader agents self-healed 3 frame gaps by re-extracting from the mp4s.
3. **Master requirements**: research/video/MASTER-REQUIREMENTS.md — 211 REQs → 63 CANONs,
   17 themes, coverage-matrix skeleton (empty "Implemented by" column), 20 research questions.
   Key CANONs: 36 naive-baseline gate, 30 chrono-splits, 41 mark-to-market fitness,
   49 risk overlay, 18 encoder-only TS transformer, 10 window tensor builder,
   46+25 feature admission gate, 47/48 autoregressive+multi-horizon, 59/61 NEAT bounded.

## Blocked / pending user
- **9th video** (youtube w8yWXqWQYmU): yt-dlp bot-check from GCP IP. User must either
  re-upload the file or drop cookies at ~/yt_cookies.txt (then retry ingest.py with
  --cookies; add flag or run yt-dlp manually then ingest the local file).

## Research fleet — COMPLETE (2026-07-03 ~20:51, all landed on disk, verified untruncated)
- research/ultra-network-frontier.md (40KB) — mechanisms to steal; composite: cheap CPU
  nodes (TTM/CfC/minGRU/streaming-TCN) + MoD top-k routers + PHATGOOSE/Arrow gates +
  GPTSwarm-REINFORCE + NEAT speciation on PnL fitness + jump-model regime → AdaHedge trust
  + BOCD resets + dual direct/rollout heads + conformal exits. Gap: CANON-21 diffusion lane
  needs its own scan later. Pip wins listed at end.
- research/video-requirements-sota.md (15KB) — per-question verdicts; zero new deps for
  transformer/LSTM/rollout/risk/GARCH/indicators/fitness; optional xlstm, efficient-kan,
  TSDiff, ABIDES vendors.
- research/ultra-network-data-plan.md (12KB) — download plan: Binance Vision 1m dumps,
  stooq/dukascopy for daily+EURUSD, tardis free-first-of-month L2, NSE bhavcopy; yfinance
  429s from cloud IPs (avoid).

## DESIGN COMPLETE (2026-07-04): research/ultra-network-design.md — "CORTEX, the Self-Wiring
## Market Cortex". 7 tissues (sensory/bus/reflex-arc/gates/heads/plasticity/brain-hub) +
## 14 video lanes + cortex dashboard + build order B1–B8 + deps list + honesty register.
## AWAITING: user dep approval (5 core + 7 frontier + 3 optional pips) → then build B1.

## Next steps (superseded by design doc §6 build order B1–B8)
1. ~~Collect the 3 research docs~~ DONE all three on disk.
2. ~~Write the INVENTION DESIGN~~ DONE → research/ultra-network-design.md: new architecture stitching
   all 63 CANONs + frontier mechanisms + the saved plan's Steps (segments taxonomy,
   HierarchicalGateNode w/ Leiden, TrustLedger, run_network.py, SigmaNetwork dashboard,
   /api/network/*) + new video-mandated lanes (TCN lane, encoder-transformer lane, LSTM lane,
   numpy-core educational lane, NEAT label-free structure search, autoregressive rollout,
   risk overlay, honesty-gate harness). MUST fill the coverage matrix (every CANON → impl).
3. Show design to user, then implement per the saved plan file discipline:
   /run-tests + /gen-index + /commit-safe per shippable step, /verify-live at the end.
4. Data downloads per ultra-network-data-plan.md (never data-gate).

## Key reference files
- ~/.claude/plans/cryptic-painting-lamport.md — approved plan: video-skill (done) + ON-HOLD
  NN-redesign steps 1-8 (segments/active_subnet/trust/run_network/dashboard/server/tests/P3.9).
- ml-network-trainable-architecture.md — DGMG design (P3.5-P3.7 BUILT: gated_node.py,
  cascade_node.py, dynamic_bus.py; structure_search.py half-built; run_active.py feeds
  SigmaNetwork.jsx already).
- ml-network-master-plan.md — original north-star architecture.
- Existing code anchors: nodes/gated_node.py:47-205, nodes/column_network.py:38-243,
  core/columns.py:56-179, run_columns.py, run_active.py, dashboard/web/src/SigmaNetwork.jsx,
  dashboard/server.py:892-909 (+subprocess pattern :1360-1397).
