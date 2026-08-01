# Dashboard ↔ disk data-consistency — 2026-07-10 11:14

| source | api | disk | api# | disk# | demo | verdict | detail |
|---|---|---|---|---|---|---|---|
| network graph state | `/api/state` | `state.json` | 22 | 22 | False | **consistent** | api 22 == disk 22 |
| routing / DGMG | `/api/state/routing` | `phase3.json` | 0 | 0 | False | **consistent** | api 0 == disk 0 |
| CORTEX network | `/api/network/state` | `network_state.json` | 13 | 13 | False | **consistent** | api 13 == disk 13 |
| knowledge graph | `/api/knowledge` | `knowledge_state.json` | 58 | 58 | False | **consistent** | api 58 == disk 58 |
| closed trades | `/api/trading/closedtrades` | `trading/state/journal.json` | 3142 | 3130 | False | **consistent** | api 3142 ⊇ disk 3130 (+12 live-merged, honest) |


_mismatch = a real honest-wiring bug to fix._