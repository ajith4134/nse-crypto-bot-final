---
name: dashboard-visual-qa
description: After any edit to dashboard / FreqUI / OpenAlgo view code, screenshot every user-visible view before + after, pixel-diff them, measure load/reload performance, confirm each view actually rendered ("landed" — no blank/error), and drive toward the fastest-loading, lightest, top-design version. A PostToolUse hook fires it automatically on dashboard edits. Use when dashboard/FreqUI/OpenAlgo UI changes, to verify a panel renders, to compare before/after look, to check load speed, or when the hook reminder appears.
---

# Dashboard Visual QA (screenshot · diff · perf · "landed")

Auto-triggered by a PostToolUse hook whenever dashboard/FreqUI/OpenAlgo view source changes (the reminder names the file + queues it in `research/visual-qa/pending.txt`). Goal: every view **renders correctly, loads fast, and looks top-tier** — verified with real screenshots + metrics, never assumed.

Reuses the repo's `dashboard/verify_render.py` pattern (headless chromium, basic-auth, console/pageerror capture) — Playwright browsers are already cached under `~/.cache/ms-playwright`.

## Procedure (when the hook fires, or on demand)

1. **Ensure the change is live.** The dashboard serves a built bundle — after editing `dashboard/web/src/*`, rebuild:
   `cd /home/karan18190164/dashboard/web && npm run build` (skip for pure `server.py`/backend edits; FreqUI edits → use `/rebuild-frequi`).
   Make sure the affected server is up (dashboard `:8000` — restart only via `tools/restart_dash.sh`; FreqUI/Freqtrade `:8080`).

2. **Capture `current`** (secrets come from env — never printed):
   ```bash
   DASH_PASS="$DASH_PASS" /home/karan18190164/.venv/bin/python \
     /home/karan18190164/.claude/skills/dashboard-visual-qa/visual_qa.py --label current
   ```
   (First-ever run on a known-good build: also `--label baseline` to set the reference.)
   Add `--views main frequi` to limit; `--lighthouse http://localhost:8000/` for a deep perf audit.

3. **Compare vs baseline:**
   `visual_qa.py --compare` → writes `research/visual-qa/report-<ts>.md` with, per view: **landed** status + console/page errors, **load-event / FCP / transfer-bytes / resource-count deltas** (🟢faster-lighter vs 🔺slower-heavier), and **pixel-change %** + changed-region bbox.

4. **Judge with your own eyes.** Open the before/after PNGs (`research/visual-qa/<view>/{baseline,current}.png`) by reading them, and decide:
   - **Landed?** Renders fully, no blank panel, no console/page errors, expected content present.
   - **Design?** Consistent with the Dark-Pro theme, aligned, no overflow/clipping, top-tier.
   - **Faster/lighter?** Load-event & FCP not regressed, transfer-bytes/resource-count not ballooning (honor dashboard-swr-performance). If current is slower/heavier or broke rendering, recommend the leaner version or a fix — this is the "best ultra + less-load fast-reloading" decision.

5. **Report to the user** the verdict per view (landed ✓/✗, faster/slower, design notes) with the screenshot paths. If good, `visual_qa.py --promote` to accept `current` as the new baseline. If regressed, propose the fix (do not silently keep a worse version).

6. Clear handled entries from `research/visual-qa/pending.txt`.

## Notes / guardrails
- **Secrets-safe:** basic-auth password read from `DASH_PASS` env (or `.env`); never echo it.
- **Honest wiring:** a screenshot proving render ≠ proving data is real — cross-check with honest-dashboard-wiring when a panel shows numbers.
- Perf uses the browser Performance API by default (fast, no extra deps); Lighthouse (`--lighthouse`) is the deep, optional audit (npx downloads on first run — ask-to-install).
- If `visual_qa.py` reports Playwright missing for this python: ask to run `pip install playwright` (browsers are already cached, so no big download).
- Views are configurable via the `VISUAL_QA_VIEWS` env (JSON) — add OpenAlgo's URL there when its port is known.
- Dashboards in this project: main **:8000** (Brain + Trading in-app views; Trading needs a chip click, `?win=crypto` = crypto window, `/hub` `/architecture` `/knowledge` = pages), **FreqUI :8080**, **OpenAlgo :5000**, Caddy aggregator :8100.

## End-to-end INPUT + BUTTON interaction testing (added 2026-07-04, owner directive)

A screenshot proves a view *renders*; it does NOT prove the controls *work*. For EVERY dashboard,
also drive every user control end-to-end and verify the effect — never assume a button is wired.

1. **Enumerate every interactive control per view.** Query the DOM for `input, select, textarea,
   button, [role=button], .chip[onclick], [contenteditable]`. Record each with a stable label
   (text / aria-label / placeholder / name / nearest heading) so the report is readable. Do this in
   BOTH in-app views (Brain + Trading — click the 📈 Trading chip first) and in FreqUI + OpenAlgo.

2. **Classify by safety BEFORE acting.** SKIP (report as `skipped-destructive`, do not click) any
   control whose label matches: reset / wipe / delete / close all / square-off / panic / arm live /
   confirm / go live / real-money. Everything else is safe to exercise in paper/dry-run.

3. **Drive each control + capture its real effect:**
   - **input / textarea / contenteditable:** focus → type a benign valid test value → assert the
     control reflects it (controlled component) → blur/submit; capture any triggered network call.
   - **select:** pick a non-default option → assert `value` changed.
   - **button / chip / toggle:** click → capture (a) any `fetch`/XHR it fires (method+path+status),
     (b) DOM mutation (node count / text delta), (c) any NEW console/page error. "Works end-to-end"
     = it triggered a request OR mutated the DOM AND returned no error AND (for POSTs) the response
     was 2xx. A control that fires nothing and mutates nothing is flagged `dead/unwired`.
   - Intercept `page.on("request"/"response")` around each interaction so the POST→server→response
     round-trip is captured (this is the "input → change → output works accordingly" proof).

4. **Verify the OUTPUT changed accordingly** where observable: after a control that mutates state
   (e.g. set a param, toggle a segment), re-read the matching GET endpoint / re-check the panel value
   and confirm it reflects the input (honest wiring: the number the panel shows must match what the
   API returns — cross-check with honest-dashboard-wiring).

5. **Report per control:** `label · type · action · effect(request/DOM/none) · http · errors ·
   verdict(ok/dead/error/skipped)`, grouped by view. Call out every `dead/unwired` and `error`
   control explicitly with the fix. Use `interaction_qa.py` (headless playwright, mirrors visual_qa.py)
   — same guardrails: paper/dry-run only, secrets from env, never click a destructive/arm-live control.
