# Boss-Command Brain — stitch map (2026-07-04)

Feature × donor matrix (all donors already in-repo/vendored; no new clones needed):

| Feature | Best donor | Module taken | Lands in | Glue |
|---|---|---|---|---|
| NL command → tool calls | core/llm.py (LiteLLM failover) | chat() prompted-JSON tool loop (no native fn-calling in our layer) | trading/brain/boss.py | JSON extraction + retry + deterministic regex fallback parser (offline-safe) |
| Action registry | vendor/browser_use_src .../tools/registry/service.py | decorator → RegisteredAction pattern | trading/brain/boss.py (BossRegistry, sync + stdlib-typed) | adapted: pydantic-free param spec, per-tool JSON schema for the LLM prompt |
| Cross-process event bus | trading/brain/activity_feed.py | atomic ring-buffer state-file pattern | trading/brain/mind_events.py | new kinds: problem/discovery/trade_credit/research/directive/learning/invention/boss |
| Directive persistence | trading/state.py | load_json/save_json atomic | trading/state/boss_directives.json | schema: mode, intensity, focus, per-market segments/target_open_trades, standing_goals, history |
| Crypto obedience | trading/crypto/freqtrade/{run_brain_loop,control,config_template}.py | enabled_segments(), set_params, executor loop | edits in run_brain_loop.py | per-cycle directive read: segment overrides, target-open push, mode→threshold nudges |
| NSE obedience | trading/online controls (/api/trading/online/control backing fns) | toggle_segment/start/stop/mode | boss tools call same fns; live loop reads directives | segment + target parity |
| Online research on demand/need | trading/brain/researcher.py | AutonomousResearcher.search/research | boss tool trigger_research + R&D drive | background thread + research events |
| Discovery events | trading/brain/hypothesis.py | ExperimentRunner credence updates | emit on confirmed/refuted | discovery/problem events |
| Trade credit assignment | trading/brain/decision_memory.py resolve() | FinMem reflection | emit trade_credit event with lesson + strategy | on profitable/losing close |
| Learning-cycle events | trading/crypto/freqtrade/brain_learning.py | maybe_run() results | emit learning/discovery events | in run_brain_loop |
| Autonomous R&D / invention | gap — from scratch (glue only) | — | trading/brain/rnd.py | curiosity topics from problems/goals → research → propose hypothesis/feature → foundry/ledger seed → invention events |
| Chat/panel UI | dashboard/server.py /api/chat[,stream] + web src trading panels | existing routes/panels | boss routing inside chat handlers + new GET /api/brain/mind/events + panel upgrades | command chips, categorized stream, directive progress |

Overlaps: activity_feed vs new mind_events — keep both; activity_feed stays web-brain-specific, mind_events is the brain-wide stream (pattern reused, one config style via trading.state).
Gaps (from scratch, glue-only allowed): boss.py orchestration, rnd.py invention loop, directive schema, UI rendering.
