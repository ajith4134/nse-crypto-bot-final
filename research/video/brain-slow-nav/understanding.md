# brain-slow-nav — video understanding (2026-07-11)

Silent 134s screen recording of the dashboard's **Brain Screen Mirror** (Trading view).

## What it shows
- The mirror embeds the brain's headed Binance browser.
- **Frame 0 (0s):** status **LIVE**, page = BTCUSDT **Options** (Binance Futures).
- **Frame 4 (40s):** status flips to **IDLE**, page = **ALGO_USDT spot**, a Chromium
  `www.binance.com wants to [Show notifications] Block/Allow` permission prompt is up, plus a
  "Restore pages? Chromium didn't shut down correctly" banner. Many (~15) tabs open.
- **Frame 8 (120s):** **identical** to frame 4 — same ALGO page, same prompt, still IDLE.
  → the browser does **not navigate for ~80s**. This is the "not moving / very slow" symptom.

## Symptom (literal)
The brain browser is effectively frozen on one page; the mirror shows IDLE (no new actions
logged). Navigation between pages is not happening (or extremely slow).

## Leading hypotheses (to verify with live logs — see debug)
1. **NEW human_handoff hook regression** — I just shipped `human_handoff.guard()` inside
   `screen_mirror.record()` (the per-action chokepoint). If it mis-parks or adds per-action
   latency, every driving loop slows/stalls. TOP suspect given the timing.
2. Browser wedged behind the **"Show notifications" permission modal** / "Restore pages?"
   banner — Playwright clicks land behind a native prompt.
3. Driving loop process not running / crashed / paused (CPU starvation).
4. Too many open tabs → browser resource exhaustion → slow.

Open question: which loop drives this browser (app-school vs funnel vs watchlist) — resolve
from the running processes.
