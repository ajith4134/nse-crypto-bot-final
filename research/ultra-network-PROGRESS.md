# Ultra-Network Redesign — Pipeline State (resume file)

> Purpose: if the session/context is lost, a fresh session resumes from HERE.
> Updated: 2026-07-04 (B9) — ALL 13 PARTIAL canons CLOSED → 61 FULL / 2 PARKED.
> B9 gap-closers: CANON-01 gap_map (psychology.py) · 02 pattern_levels (features_ta.py) ·
> 05 dukascopy+NSE-bhavcopy downloaders (data/downloads.py) · 06 arbitrate_timeframe
> (fitness.py) · 09 one_hot_features · 34 trading/sweep.py · 37+58 trading/classification_eval.py ·
> 43 trading/antioverfit.py + /api/network/antioverfit + NetworkPanel · 45 CoinDetailPanel
> research-preview disclaimer · 54 /api/trading/forecast + PriceChart/CoinDetailPanel overlay ·
> 55 PriceChart.OVERLAY_STYLE · 56 PnlStrip.jsx + train band. 144 CORTEX tests green
> (+9 tests/test_cortex_b9_gaps.py). Web rebuilt. Services RESTARTED with CORTEX_SIGNAL=1
> shadow (durable in start_all.sh) — brain loop logs cortex-vs-decider live. Only 2 PARKED
> remain (CANON-04 determinism study, CANON-21 diffusion lane — deliberate future lanes).
> Prior: 2026-07-04 ~09:05 — B3-B6 committed. Next: B7 Cortex dashboard.
> B6 (01cd693): trading/heads.py (RolloutHead direct+AR on TTM/Chronos/TabPFN, DM-gated) +
> data/downloads.py (Binance archive OK, 416 on-disk 1m feathers, stooq GCP-IP-blocked).
> Deps granite-tsfm+tabpfn-ts; fixed torch/torchvision ABI (torch 2.10.0+cpu + torchvision
> 0.25.0+cpu — see research/torch-torchvision-abi-mismatch.md). 110/110 CORTEX green.
> B7 = run_network.py + /api/network/* + SigmaNetwork upgrade + NetworkPanel + web rebuild
> (no new deps; touches React -> needs npm build + verify-live; services still PAUSED).
> Prior: 2026-07-04 ~08:35 — B3/B4/B5 committed. Next: B6 Heads + data.
> Build state: B1+B2 (68e984e) · B3 reflex (7f7445a) · B4 brain hub (4dab1d4) ·
> B5 evolution lane nodes/neat_lane.py + trading/simlab.py (c1093bf). 97/97 CORTEX
> B1-B5 tests green. Installed neat-python 2.0, order-matching, hftbacktest, evotorch
> (numpy -> 2.2.6, no regression). B6 next needs deps granite-tsfm, tabpfn-time-series +
> data downloads (Binance Vision 1m, stooq daily, dukascopy EURUSD, NSE bhavcopy per
> research/ultra-network-data-plan.md). Prior: 2026-07-04 ~08:10.
>
> ⚠ SERVICES PAUSED (2026-07-04, user request "free all 12 cores until build done"):
> STOPPED — dashboard/server.py, freqtrade trade, freqtrade.run_brain_loop,
> freqtrade.candle_updater, OpenAlgo gunicorn + websocket_proxy. KEPT UP (≈0% CPU) —
> cloudflared/ngrok/caddy tunnels. RESTART EVERYTHING after the CORTEX build with:
>   bash ~/start_all.sh   (idempotent; re-relaunches OpenAlgo separately if needed)
> NOTE: pkill -f "<pattern>" self-kills the calling shell here (its cmdline contains the
> pattern) → exit 144. Stop services by numeric PID, not pkill -f.
> Prior update: 2026-07-03 ~20:50 — PAUSED by user near token limit.
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

## BUILD COMPLETE (2026-07-04): all 8 steps B1–B8 SHIPPED, tested, committed, live-verified.
Commits: 68e984e B1+B2 · 7f7445a B3 · 4dab1d4 B4 · c1093bf B5 · 01cd693 B6 ·
9dec6ea catch-up · ad5ca17 B7 · 194e952 B8. (B3–B6 built in an Opus 4.8 session,
quality-verified here: 110 tests re-run green + donor-usage spot checks.)
Tests: 135 CORTEX tests green (b1..b8) + full-suite regression green.
Coverage matrix filled for all 63 CANONs: 48 FULL / 13 PARTIAL (gaps named in
research/video/MASTER-REQUIREMENTS.md §3) / 2 PARKED (CANON-04 determinism study,
CANON-21 diffusion lane).
Live-verified (2026-07-04): /api/network/state serves real 9-node/8-edge/48-firing state
with reflex compute stats (70/160 stay-flat exits — dead-band routing live);
/api/network/trust honest-empty; POST refresh spawns subprocess (regeneration confirmed);
/api/state latency 0.9ms after restart (no 524 wedge); NetworkPanel bundle served.
Shadow mode: CORTEX_SIGNAL=1 logs cortex decisions beside the live decider;
CORTEX_TRADE=1 promotes cortex (paper-first). Trust accrues from closed trades.
Remaining known gaps (honest): 13 PARTIAL canon items, 9th video (YouTube bot-check —
needs re-upload or cookies), dukascopy/bhavcopy downloaders, per-segment scorecard
arbitration automation, diffusion + determinism-study lanes.

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
