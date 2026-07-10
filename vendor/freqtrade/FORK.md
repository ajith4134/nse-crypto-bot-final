# mlnb Freqtrade Fork — Divergence Map

This vendored Freqtrade (editable-installed into `.venv`, so edits go live on process
restart) is the ML-Network-Brain's execution engine. Every divergence from upstream is
marked with an `# mlnb` comment in-source; this file is the index. Update it whenever a
new divergence lands (E5 rule, 2026-07-10). For upstream updates use `/vendor-update` and
re-check each area below.

## Architecture divergences

| Area | Files | What changed |
|------|-------|--------------|
| Multi-segment engine | `worker_multi.py`, `commands/trade_commands.py` | ONE process runs a bot per segment (futures/spot/options/prediction) from `mlnb_segments` in config.json; per-segment boot isolation (one segment's boot error can't kill the others); first segment owns the shared ApiServer. |
| Segment isolation | `persistence/segment_context.py`, `persistence/trade_model.py`, `persistence/models.py`, `persistence/migrations.py` | `bot_segment` column on Trade (stamped from a ContextVar); query helpers scope reads to the current segment; unscoped = aggregate view. |
| Segment-aware API | `rpc/api_server/deps.py`, `api_trading.py`, `api_v1.py`, `webserver.py`, `rpc/rpc.py`, `rpc/rpc_manager.py` | One URL serves all segments: `?segment=` or `X-Freqtrade-Segment` header routes to that segment's RPC; `/status` without a segment aggregates ALL bots (each pair priced by its own bot's exchange). 2026-07-10: header now scopes `/status` too (was query-param-only → silent union). |
| Options venue | `exchange/deribit.py`, `exchange/__init__.py`, `enums/tradingmode.py`, `constants.py` | Deribit exchange class + OPTION trading mode for the options segment (USDC-quoted option contracts). |
| Prediction venue | `exchange/predictionpaper.py` | Paper prediction-market exchange (Polymarket-style outcome prices via CLOB history). |
| Pairlists | `plugins/pairlist/AllMarketsPairList.py` | Whitelist = every active market of the venue (options/prediction dynamic universes). |

## Brain-native layer (E-workstreams, 2026-07-10)

| Piece | Files | What it does |
|-------|-------|--------------|
| E2 native brain fields | `rpc/api_server/mlnb_sidecar.py`, `api_schemas.py`, `api_trading.py` | `/status`, `/trades`, `/trade/{id}` carry `tg_locked_pct` / `tg_peak_pct` / `tg_trail_dist` (live ratchet from `profit_tailgate_locks.json`) + `strategy_label` / `brain_pred` (entry-time facts from `crypto_entry_meta.json`) — same-origin, no dashboard overlay needed. Kill-switch `"mlnb_native_fields": false`. |
| E2 brain-state API | `rpc/api_server/api_mlnb.py`, `webserver.py` | Read-only `/api/v1/mlnb/{feed,funnel,tailgate,xray}` serving the brain's state files for the FreqUI Brain Cockpit. Same auth as the rest of the API. |
| E1 in-engine tailgate | `trading/crypto/freqtrade/user_data/strategies/MlBridgeStrategy.py` (userdir, not fork) | `custom_exit` enforces the brain's locked-profit ratchet on EVERY bot iteration (exit_reason `tailgate_lock`); the funnel only ratchets/learns. Kill-switch `"mlnb_tailgate_enforce": false`. |
| E3 decision inbox | `mlnb_inbox.py`, `freqtradebot.py` (process() hook) | Push model: funnel appends decisions to `<state>/decisions_inbox.jsonl`; each segment bot consumes via per-segment byte-offset cursor and executes through the same RPC force-entry/exit guards. Stale (>15 min) decisions are skipped. OFF by default: `"mlnb_decision_inbox": true` + funnel env `CRYPTO_DECISION_INBOX=1`. |
| E4 fill-time journal | `mlnb_fills.py`, `freqtradebot.py` (`_notify_enter`/`_notify_exit` fill branches) | Appends every REAL fill to `<state>/mlnb_fills.jsonl` at confirmation time — engine-authored ground truth for the brain's journal. Kill-switch `"mlnb_fill_journal": false`. |

Sidecar state directory resolution (all brain-native pieces): config `"mlnb_state_dir"` →
env `MLNB_STATE_DIR` → `~/trading/state`.

## Deliberately unused upstream surfaces (E5)

- **FreqAI** — blocked in this deployment (see brain-controls-freqtrade memory); ML lives
  in the brain processes, never in-engine. Keep `freqai.enabled` absent/false.
- **Hyperopt / Edge** — unused; strategy selection is the brain's champion/foundry logic.
- **Strategy plugins as signal sources** — the `MlBridgeStrategy` shell never emits
  entries; entries come from the brain (REST forceenter or the E3 inbox). The `lib_*`
  strategies in userdir are backtest adapters for the strategy library, not live drivers.
- **FreqUI is served from the fork's `rpc/api_server/ui/installed/`** — deployed by
  `tools/deploy_frequi.sh` (preserves the `mlnb_*.json` overlay files).
