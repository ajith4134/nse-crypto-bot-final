# Dashboard ↔ disk data-consistency — 2026-07-10 11:11

| source | api | disk | api# | disk# | demo | verdict | detail |
|---|---|---|---|---|---|---|---|
| network graph state | `/api/state` | `state.json` | 22 | 22 | False | **consistent** | api 22 == disk 22 |
| routing / DGMG | `/api/state/routing` | `phase3.json` | 0 | 0 | False | **consistent** | api 0 == disk 0 |
| CORTEX network | `/api/network/state` | `network_state.json` | 13 | 13 | False | **consistent** | api 13 == disk 13 |
| knowledge graph | `/api/knowledge` | `knowledge_state.json` | 58 | 58 | False | **consistent** | api 58 == disk 58 |
| closed trades | `/api/trading/closedtrades` | `trading/state/journal.json` | 3139 | 3349 | False | **mismatch** | api 3139 != disk 3349 — dashboard NOT true to disk |

**1 mismatch(es)** — dashboard not true to disk.
_mismatch = a real honest-wiring bug to fix._