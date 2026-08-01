# Dashboard ↔ disk data-consistency — 2026-07-12 07:28

| source | api | disk | api# | disk# | demo | verdict | detail |
|---|---|---|---|---|---|---|---|
| network graph state | `/api/state` | `state.json` | - | - | - | **error** | api: JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| routing / DGMG | `/api/state/routing` | `phase3.json` | - | - | - | **error** | api: JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| CORTEX network | `/api/network/state` | `network_state.json` | - | - | - | **error** | api: JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| knowledge graph | `/api/knowledge` | `knowledge_state.json` | - | - | - | **error** | api: JSONDecodeError: Expecting value: line 1 column 1 (char 0) |
| closed trades | `/api/trading/closedtrades` | `trading/state/journal.json` | - | - | - | **error** | api: JSONDecodeError: Expecting value: line 1 column 1 (char 0) |


_mismatch = a real honest-wiring bug to fix._