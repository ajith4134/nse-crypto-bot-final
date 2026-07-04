# dashboard/routes — server.py split (Wave0-⑤)

`dashboard/server.py` is a ~3.7k-line `BaseHTTPRequestHandler` with every route inline in
`_do_GET_impl` / `_do_POST_impl`. We shrink it **incrementally + safely**: the dispatch line
(`if path == "…":`) stays in server.py; the route **body** moves here as `handle_*(h)` using
`h._send(...)` / `h.path`. Each move is verified (restart + curl the moved route) before the next.
The SWR cache + auth wrap `do_GET` *above* dispatch, so moving bodies never affects them.

## Done (verified, committed)
- `brain_ext.handle_ops`          ← `GET /api/brain/ops`
- `brain_ext.handle_mind_events`  ← `GET /api/brain/mind/events`

## Remaining groups (same pattern, do one group at a time + verify)
1. **brain_ext** — the rest of `/api/brain/*`: `boss/status`, `autonomy/status`, `agent/status`,
   `memory/status`, `hybrid/status`, `librarian/status`, `stream/status`, `embodiment/*`,
   `quiz/*`, `thinking/*`, `activity`, `web`.
2. **trading_ext** — `/api/trading/*`: crypto, screener, sizing, exits, advintel, alerts, `brain/*`, status.
3. **network_ext** — `/api/network/*`, `/api/state/*`, `/api/knowledge`.
4. **POST routes** — split `_do_POST_impl` the same way: `handle_*_post(h, body)`.

## Rules
- Move the body **verbatim**; change `self` → `h`. Behavior must stay **byte-identical** — curl the
  moved route before/after and compare.
- **Never break the running dashboard:** `tools/restart_dash.sh` + curl each moved route after a group.
- Do it on a **cpu-solo'd** box so restarts are fast; commit per group via `/commit-safe`.
