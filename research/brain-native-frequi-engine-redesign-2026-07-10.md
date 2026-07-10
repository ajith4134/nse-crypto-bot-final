# Brain-Native FreqUI + Freqtrade Engine Redesign — PROPOSAL (2026-07-10)

Owner ask: "customise it by editing its source code and redesigning it to fit our brain" —
scope confirmed: **both** FreqUI (vendor/frequi) and the Freqtrade engine (vendor/freqtrade),
full redesign, PROPOSE→APPROVE.

## Why we can: we own all the source
- `vendor/frequi` — Vue 3 UI, already forked (unified trades table, Strategy/Brain/NN + Tailgate
  columns, MlnbControls, PairListLive, segment column, ?segment= routing).
- `vendor/freqtrade` — deep fork already running MultiWorker (4 segment bots, one URL,
  X-Freqtrade-Segment header), MlBridgeStrategy shell (brain drives via forceenter/forceexit).
- The brain exposes ~40 APIs on :8000 (xray, ocular, mind-events, decision memory, psychology,
  tailgate, funnel, sandbox, cortex, segment focus…). Today FreqUI reaches them via a fragile
  cross-origin overlay — the root of the 2026-07-10 fabricated-lock incident.

## Design-debt table (evidence from today's sessions)
| # | Debt | Evidence |
|---|------|----------|
| 1 | Brain data reaches FreqUI via cross-origin overlay polling | fabricated 🔒 incident; Strategy/Brain/NN "–" when overlay fails |
| 2 | Exit enforcement at funnel cadence (2–4 min), not engine tick | trades gapped through locks between passes |
| 3 | /status ignores segment header (union of all workers) | "only futures opens" misdiagnosis |
| 4 | Journal context reconstructed AFTER the fact by ingest | entry-time context risk (2026-07-07 label-honesty bug class) |
| 5 | Engine carries dead weight we bypass (FreqAI blocked, hyperopt UI, strategy plugins) | freqtrade-deep-fork memory |
| 6 | Brain telemetry (funnel stages, skip reasons, mind events) invisible in the trading UI | options "dead" for 4.5h while merely selective |

## ENGINE workstreams (E1–E5)
- **E1 In-engine tailgate enforcement (top impact).** Move the ratchet exit check into the
  engine's own exit-evaluation tick (~5–15s, `freqtradebot.py` exit path), reading
  `profit_tailgate_locks.json` (funnel still owns learning the distance). Sub-second-class
  enforcement; no more gap-through-lock windows. Effort M.
- **E2 Native brain fields in /api/v1 (kills the overlay).** Trades/status responses carry
  tailgate lock/peak/dist + strategy_label + brain/NN predictions read from sidecar state
  (entry_meta, locks). FreqUI reads same-origin → the fabricated-fallback bug class is gone
  permanently. Also fix segment-header routing on /status. Effort M.
- **E3 Decision inbox (push, not poll).** Funnel writes `decisions.jsonl` (idempotent ids);
  the engine consumes each iteration and executes natively — replaces REST forceenter storms,
  entries survive API hiccups. Effort M-L.
- **E4 Fill-time journal.** Engine stamps decision_snapshot/entry context at order fill, not
  via later ingest reconstruction. Effort M.
- **E5 Fork hygiene.** Disable FreqAI/hyperopt surfaces we bypass; one FORK.md documenting
  every divergence for future updates. Effort S.

## FreqUI directions (pick one)
- **A. Brain Cockpit (recommended)** — keep FreqUI shell + theme; redesign the Trading view:
  left rail = live segment tiles (count/P&L/funnel-stage heat/skip reasons), center = unified
  trades (native brain columns via E2), right rail = mind-events + decision feed, row-click →
  X-Ray drawer. Migration cost lowest; depends on E2.
- **B. Mission Control merge** — Brain/Funnel/School/Sandbox dashboard panels become native
  FreqUI tabs; one URL for everything; :8000 stays as API + fallback. Highest scope.
- **C. Pro Terminal** — TradingView-style: full-height chart with brain entry/exit markers,
  ratchet locks drawn as lines, reason tooltips, dockable panels. Most visual wow; chart work
  heaviest (lightweight-charts already in FreqUI).

## Reuse
FreqUI's own component kit + lightweight-charts (in-tree), existing :8000 APIs, sidecar state
files. No new heavy deps required for A; C would lean harder on lightweight-charts markers API.

## Rollback
Fork edits are commits in the main repo; upstream FreqUI build remains reproducible via
vendor-update. E2/E3 land behind config flags (`mlnb_native_fields`, `mlnb_decision_inbox`).

Status: PROPOSED — awaiting owner picks (UI direction + engine workstream set).
