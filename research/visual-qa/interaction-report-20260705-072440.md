# Dashboard interaction QA — 2026-07-05 07:24

## crypto_window  (9 controls · ok 5 · dead 2 · error 0 · skipped 2)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| 🛑 PANIC (halt all) | button | - | destructive — not clicked | skipped |
| ▶ Start trading | button | - | heavy job — not clicked | skipped |
| ⏹ Stop trading | button | click | 6 request(s) | ok |
| Switch to LIVE 💵 | button | click | no request / no DOM change | dead |
| → Futures (short) | button | click | no request / no DOM change | dead |
| filter all cells… | input | type | value set (controlled input) | ok |
| on | input/checkbox | click | 7 request(s) | ok |
| Columns ▾ | button | click | DOM +274 | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-24-39.csv) | ok |
