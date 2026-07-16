---
name: debug-error
description: Research-then-fix protocol for bugs and errors — reproduce first, root-cause via in-project + online research, fix at the right depth. Use whenever an error, traceback, or wrong behavior is reported. Never blind-patch or silence symptoms.
---

# Debug Error (research-then-fix)

*(Thinned 2026-07-16, owner-approved: rules + repo facts kept, step narration cut.)*

Never trust an unverified report and never patch a symptom. The deliverable is a root-cause fix —
or a verified explanation when no fix was requested (don't upgrade a question into a task).

## Rule 0 — THE MESSAGE IS NOT THE CAUSE. Trace the CONTROL FLOW, and obey the COUNTERS.

*(Added 2026-07-16 after a real miss: a session read `entered=[] skipped=0 err=forceenter failed:
Symbol does not exist`, concluded "the lane proposes invalid symbols", and patched a guard that was
already there. The true cause: `place_order → _check` RAISES, the loop caught only the RETURNED
`{"ok": False}`, so one refusal aborted the whole cycle. Another session found it. The falsifying
evidence — `skipped=0` — was on screen the whole time and went unread.)*

1. **An error string tells you what the callee SAID. It never tells you what your code DID with it.**
   Before proposing any cause, trace the path: *who raises → who catches → what happens next.*
   `grep -n "def _check\|raise \|except " <the call chain>`. A handler that catches a RETURNED error
   (`if res.get("ok") is False`) does NOT catch a RAISED one — that asymmetry is a top recurrent
   root cause in this repo.
2. **Read the counters BEFORE you believe your story, then try to KILL the story with them.**
   `entered=[] skipped=0` is not decoration: if candidates were being *refused*, `skipped` would be
   ≥1. Zero skips is logically incompatible with "they're being skipped" → it aborted on #1.
   **Write the number your story predicts, compare it to the log, and if they disagree your story is
   dead** — no matter how well it matches the error text. One line of telemetry outranks a plausible
   narrative.
3. **If a guard you're about to add already exists, STOP — that's a clue, not a chore.**
   Ask: "the guard already runs, so why does the error persist?" (Answers here are usually: it FAILS
   OPEN by design, its data source is WIDER/narrower than the consumer's, or the failure is
   downstream of it.) Adding a second copy of an existing guard is proof you skipped root-causing.
4. **A test of yours that fails "for the wrong reason" may BE the bug reproducing.**
   Before dismissing it as a bad fixture, ask whether its failure mode *is* the reported symptom.
5. **Symptom vs blast radius.** Ask separately: what failed, and *why did the failure spread?*
   A per-item fault that ends a whole loop/cycle is TWO bugs — the refusal and the missing isolation.
   Per-item work needs per-item try/except; the loop-level `except` is the last resort, not the plan.
6. **Pre-existing or mine?** `git stash` your change and re-run. ⚠ `.env`/state files are NOT
   stashed — for env- or state-driven behavior, prove it with an explicit override instead.

## The rules
- **Reproduce/verify first.** If you can't reproduce, say so — don't fix what you can't observe.
  Trading code: reproduce with `trading.state.STATE_DIR` monkeypatched to a temp dir — never
  against the live journal/wallets.
- **Fix at the diagnosed level** (data / our glue / vendored code / upstream / config). Vendored
  bug → patch in `vendor/<project>` with a divergence comment. Upstream-known → apply the tracker's
  fix, cite it. NEVER try/except-pass, timeout-widening, or feature-disabling unless that IS the
  researched root cause.
- **Prove it:** the original repro must pass, related tests run, and a regression test lands when
  the bug was ours. Save non-trivial online findings to `research/`.
- Check `git log -S "<symbol>"` when a regression is suspected; read the skill's LEARNINGS
  (injected on invocation) — this repo's past root causes are highly recurrent.

## Known behaviors that LOOK like bugs here (check before "fixing")
- FreqUI cannot save strategy params (param "reverts" are that limitation; truth =
  `trading/crypto/freqtrade/config.json`).
- Live-chart "No data" off the 5m timeframe = pair_candles(5m) vs pair_history(disk) split.
- Root `config.settings` is cached at process start — a changed `.env` does NOT reach a long-lived
  process until restart.
- Freqtrade alone opens no trades — entries come from the brain loop / funnel.
- Zero "Bot heartbeat" lines in the Freqtrade log = the worker loop never started, however alive
  the API looks.
