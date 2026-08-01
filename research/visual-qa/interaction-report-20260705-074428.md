# Dashboard interaction QA — 2026-07-05 07:44

## crypto_window  (9 controls · ok 6 · dead 0 · error 0 · skipped 3)

| label | type | action | effect | verdict |
|---|---|---|---|---|
| 🛑 PANIC (halt all) | button | - | destructive — not clicked | skipped |
| ▶ Start trading | button | - | heavy job — not clicked | skipped |
| ⏹ Stop trading | button | - | destructive — not clicked | skipped |
| Switch to LIVE 💵 | button | click | confirm dialog (wired, dismissed) | ok |
| → Futures (short) | button | click | confirm dialog (wired, dismissed) | ok |
| filter all cells… | input | type | 4 request(s) | ok |
| on | input/checkbox | click | DOM +110 | ok |
| Columns ▾ | button | click | DOM +274 | ok |
| Export CSV | button | click | download (closed_trades_2026-07-05-07-44-27.csv) | ok |
