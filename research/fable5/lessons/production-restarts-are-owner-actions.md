# Plan production-process restarts as OWNER actions, not session actions

2026-07-16: the permission classifier (correctly) blocked `kill <pid>` on the running
run_live_loop — a production trading process this session didn't start. Consequence: code fixes to
long-running loops (live_loop, learn_loop/dashboard, funnels) do NOT activate until the owner
restarts them. Rule: when a fix lands in loop code, (a) do any one-shot catch-up work directly
(that's allowed — e.g. running backfill_journal once), (b) state the exact restart command as an
owner action item, (c) design fixes to be safe under stale-process overlap (flock + idempotency),
which this session's backfill fix is.
