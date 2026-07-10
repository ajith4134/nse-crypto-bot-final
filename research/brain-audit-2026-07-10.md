# Brain audit — 2026-07-10 (why everything looked stagnant)

## Root causes found (all verified, not guessed)

1. **All 3 trading-loop processes were DEAD** since ~08:33–08:35 UTC (crypto funnel, NSE funnel,
   live_loop). They were pkilled during an earlier dev session (the one that produced
   `run_upstox_focus.py` / screen-mirror work, quiet since 10:27) and never restarted.
   The dashboard (restarted 09:17) kept serving *stale state*, so every brain panel looked frozen.
   **The system has boot self-heal (systemd unit) but NO runtime self-heal** — a mid-day loop
   death goes unnoticed until a human looks. → proposal #1.
   FIXED today: `bash start_all.sh` revived all three (pgrep-guarded, safe).
   ⚠️ gotcha: `pkill -f 'run_funnel_loop'` in a compound command kills your own shell (pattern
   matches the shell's own cmdline) — exit 144.

2. **LLM provider pool ~95% dead** (llm_telemetry.json): groq 3799/4490 rate-limited,
   sambanova 3613/3795, gemini 3614/3614 quota, openrouter 3609/3611, mistral rate-limited,
   **cerebras 3796/3796 NotFoundError — model `llama-3.3-70b` was RETIRED by Cerebras Feb-2026**
   (FIXED today → `cerebras/gpt-oss-120b`, verified live), **deepseek: "Insufficient Balance"**
   (paid account empty — owner action, not code). Every LLM-dependent feature (RD-Agent, LLM
   mutation, reflections, micro-LLM notes) starved silently. → proposal #2.

3. **Learn-loop is NOT dead** — it runs inside the dashboard process (BRAIN_LOOP=1):
   203 cycles, 200 topics, last cycle 10:25 UTC today, FSRS retention 0.905 but `rising: false`
   (plateaued). Knowledge IS accruing; it isn't *visibly* improving → proposals #4, and the
   stagnant look came from #1.

4. **Tailgate/brain columns missing on NSE**: commit d88743b put the Tailgate column ONLY on
   FreqUI's TradeList (crypto). Journal rows for NSE carry `tailgate_*` on 100% of rows.
   FIXED today: "Tailgate Lock"+"Tailgate Trail" columns on the unified Open Trades table for
   all venues (commit a87279f), verified rendering with live ratchet values.

5. **Demo-data panels** (all honestly labelled `demo:true`, never wired to the live brain):
   `/api/brain/memory/status`, hybrid memory, librarian, quiz, thinking (P4.5), stream-of-mind,
   self-coding (P4.7) — from root `run_*.py` demo builders — plus the synthetic options chain
   in `dashboard/server.py` (`build_demo_chain`). The REAL counterparts now exist
   (get_brain() HippoRAG/A-MEM, knowledge_main, FSRS log, mind_events.json, self_evolve state,
   OpenAlgo NFO chain). → proposal #5.

6. **Calibration blind spots**: per-symbol Brier mostly `null`, ETH/USDT brier exactly 0.0
   (degenerate — suspicious), UQ ECE 0.1577. Confidence numbers exist but aren't being
   *scored* per symbol honestly. → proposal #3.

7. **Test-runner traps** (recorded to skill learnings): brain tests are pytest-style —
   `unittest` collects 0 and prints NO TESTS RAN; `.env` arms STRATEGY_EVOLUTION_ENABLED=1 so
   the gate-off test needs the env cleared (fixed in test today).

## State verified healthy
- TradeOutcomeNet: trained, n=3338, OOF acc 0.852 (base rate 0.256), gated_moe engine.
- Hypothesis ledger: 99 entries, updating today. Decision episodes ~6 MB, fresh.
- Data-consistency QA: 5/5 sources consistent after fixing the checker's own
  apples-vs-oranges closed-trades comparison (false "210 dropped rows").
- Funnel entered 8 futures + 6 spot within minutes of revival; predictions map + tailgate
  overlay serving.
