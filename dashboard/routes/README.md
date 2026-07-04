# dashboard/routes — server.py split (Wave0-⑤)

`dashboard/server.py` is a ~3.7k-line `BaseHTTPRequestHandler` with every route inline in
`_do_GET_impl` / `_do_POST_impl`. We shrink it **incrementally + safely**: the dispatch line
(`if path == "…":`) stays in server.py; the route **body** moves here as `handle_*(h)` using
`h._send(...)` / `h.path`. Each move is verified (restart + curl the moved route) before the next.
The SWR cache + auth wrap `do_GET` *above* dispatch, so moving bodies never affects them.

## Done (verified, committed)
- `brain_ext.handle_ops`          ← `GET /api/brain/ops`
- `brain_ext.handle_mind_events`  ← `GET /api/brain/mind/events`
- **Group 1a (`/api/brain/*` GET status cluster)** — verified live, HTTP 200 + identical shape:
  `handle_agent_status`, `handle_memory_status`, `handle_hybrid_status`, `handle_librarian_status`,
  `handle_quiz_status`, `handle_thinking_status`, `handle_stream_status`, `handle_boss`,
  `handle_autonomy_status`, `handle_embodiment_status`, `handle_activity`, `handle_learning`.
- **Group 1b (`/api/brain/*` GET heavy)** — `handle_worldmodel`, `handle_hypotheses`, `handle_evolve`.
- **Group 2 — `trading_ext.py`** (all 47 `/api/trading/*` GET): the crypto cluster, the T3–T8 `/status`
  snapshots, tickers/candles/forecast/orderbook, scorecard/opentrades, brain/{predict,ultra,
  metacognition,debate,decisions}, gui/status, closed/confidence/context/watchlist/online-*, and the
  stateful single-flight routes (crypto/trades, crypto/predictions — shared `_CT_LOCK`/`_PRED_MAP_LOCK`).
- **Group 3 — `network_ext.py`**: state, state/routing, network/{state,trust,system,antioverfit},
  knowledge, llm/telemetry (GET) + network/refresh (POST).
- **Group 4 — `post_ext.py`** (all `do_POST` bodies): practice/start, brain/discovery/run, credentials,
  brain/learn, brain/web, chat, brain/agent, brain/ultra/remember, chat/stream + agui (streaming via
  `h.wfile`/`send_response`), crypto/params, closedtrades/reset, crypto/mode, online/control, gui/action.

**✅ SPLIT COMPLETE (2026-07-04):** `server.py` 3777 → 1524 lines (−60%). Every `/api/*` GET + POST route
body lives in `dashboard/routes/{brain,trading,network,post}_ext.py`; server.py keeps only the router
dispatch, the SWR/auth wrappers, shared helpers/globals, static-HTML routes, and `BoundedHTTPServer`.
Each group was verified live (shape-diffed vs a pre-move baseline; streaming + mutating POSTs tested
non-destructively) and committed separately.

### The `_srv(h)` accessor (important)
server.py runs as `__main__` (`python dashboard/server.py`), so `from dashboard.server import _bg_snapshot`
would import a **second copy** of the module with its own singletons/caches. Handlers that need a
server-level helper/global (`_bg_snapshot`, `_brain_agent`, `_cached_body`, `_EMBODIMENT_CACHE`…) use
`_srv(h)` — `sys.modules[h.__class__.__module__]` — to reach the **live** running module. Transform rule:
`self.X` → `h.X`; bare module-level `NAME(...)` → `_srv(h).NAME(...)`.

## Remaining
Nothing — the split is complete. Only trivial static-HTML routes (`/`, `/architecture`, `/knowledge`,
`/hub`) and the streaming preamble stay inline in server.py by design. New routes should be added as
`handle_*(h)` in the matching `*_ext.py` with a 2-line delegate in server.py.

## Rules
- Move the body **verbatim**; `self.X` → `h.X`, bare server helpers → `_srv(h).X`. Behavior stays
  **shape-identical** — curl the moved route before/after and compare.
- **Never break the running dashboard:** `tools/restart_dash.sh` + curl each moved route after a group.
- Do it on a **cpu-solo'd** box so restarts are fast; commit per group via `/commit-safe`.
