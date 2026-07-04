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

### The `_srv(h)` accessor (important)
server.py runs as `__main__` (`python dashboard/server.py`), so `from dashboard.server import _bg_snapshot`
would import a **second copy** of the module with its own singletons/caches. Handlers that need a
server-level helper/global (`_bg_snapshot`, `_brain_agent`, `_cached_body`, `_EMBODIMENT_CACHE`…) use
`_srv(h)` — `sys.modules[h.__class__.__module__]` — to reach the **live** running module. Transform rule:
`self.X` → `h.X`; bare module-level `NAME(...)` → `_srv(h).NAME(...)`.

## Remaining groups (same pattern, do one group at a time + verify)
1. **brain_ext (part b)** — remaining `/api/brain/*` GET: `worldmodel`, `hypotheses`, `evolve`.
   (`learn`, `web`, `agent` live in `_do_POST_impl` → Group 4.)
2. **trading_ext** — `/api/trading/*`: crypto, screener, sizing, exits, advintel, alerts, `brain/*`, status.
3. **network_ext** — `/api/network/*`, `/api/state/*`, `/api/knowledge`.
4. **POST routes** — split `_do_POST_impl` the same way: `handle_*_post(h, body)`.

## Rules
- Move the body **verbatim**; `self.X` → `h.X`, bare server helpers → `_srv(h).X`. Behavior stays
  **shape-identical** — curl the moved route before/after and compare.
- **Never break the running dashboard:** `tools/restart_dash.sh` + curl each moved route after a group.
- Do it on a **cpu-solo'd** box so restarts are fast; commit per group via `/commit-safe`.
