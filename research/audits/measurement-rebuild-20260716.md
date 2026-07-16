# Measurement-Layer Rebuild — 2026-07-16 (Fable-5 session, Prompt 0)

Every number below was measured first-hand in this session against the live state files —
`trading/state/direction_truth.json` (100,774 labels), `trading/state/direction_truth_train.jsonl`
(40,000 newest per-decision rows), `trading/state/journal.json` (7,190 trades), and
`~/tradesv3.dryrun.sqlite` (4,937 closed) — not read from any doc.

## 1. The exit-label wedge — FIXED

**Bug (verified):** the truth ledger's `exit` horizon is written only by
`backfill_journal()` (`trading/direction/truth_ledger.py`), documented as a "one-shot idempotent
label pass" — and its only callers in the whole repo were `tests/test_truth_ledger.py:144,152`.
The seen-ids file (`direction_truth_seen.json`) was last modified **Jul 11 00:02** — the last manual
run. The exit bucket sat at n=3,459 while 3,244 trades closed (sqlite-verified).

**Fix (shipped this session, tests green):**
- `truth_ledger.backfill_journal()` — now flock-guarded (concurrent callers return `locked=True`,
  can never double-fold) and accepts a pre-loaded `TradeJournal` (skips re-reading the 59MB file).
- **Primary caller:** `trading/online/live_loop.py::_ingest_freqtrade` — labels exits right where
  closed trades enter the journal; throttled by `EXIT_BACKFILL_MIN_S` (900s) after any ingest, and
  at worst every 2h. This is the same process that owns journal ingest, so labels land immediately.
- **Safety net:** `trading/brain/learn_loop.py` — time-gated redundant pass
  (`TRUTH_EXIT_BACKFILL_INTERVAL_H`, default 6h) so exit labels survive a live-loop death.
- Regression tests added: `tests/test_truth_ledger.py` (preloaded-journal + lock-contention);
  full file 11/11 green; `tests/test_online` 34/34 green; `tests/test_learn_loop` green (pytest).

**Catch-up executed:** `backfill_journal()` run once against live state — scanned 7,186, labeled
4,702 (3,715 exits + 987 fixed-horizon), 19.2s. Exit bucket: **n=3,459 → 7,174**.

**⚠️ Activation pending:** the running `run_live_loop` (PID 334248) and the dashboard (learn loop)
still execute the old code; the permission sandbox blocked restarting a production process from
this session. Until restarted, continuous labeling is NOT active (the one-time catch-up is done).
**Owner action: restart `run_live_loop` (and the dashboard at next convenient window).**

## 2. Controlled paired Mirror-Gate experiment — premise FALSIFIED, gate retired

Every `mirror:X` decision is by construction the inverted raw claim on the SAME sample (same
symbol, ts, horizon), so paired raw accuracy = 1 − mirror accuracy (ties measured 0.86%).

| horizon | raw bucket (trigger) | mirror bucket | implied raw ON THE GATE'S OWN SAMPLES | z (vs trigger) |
|---|---|---|---|---|
| 15m | 35/113 = 0.310 | 21/58 = 0.362 | **0.638** | +4.12 |
| 1h  | 43/113 = 0.381 | 19/58 = 0.328 | **0.672** | +3.62 |
| 4h  | 46/110 = 0.418 | 21/61 = 0.344 | **0.656** | +2.98 |

On the exact samples where the gate flipped, the raw source was scoring 64–67% — it had already
reverted above chance. The mechanism is **non-stationarity, not estimation error**: across 39
source×horizon cells with n≥40 in both chronological halves of the train log, the correlation
between first-half and second-half accuracy is **−0.214**. The 11 "invertible" cells (first-half
acc < 0.45) averaged **0.487** in the second half — a coin-flip, not a 55%+ inverted edge. The
gate's conservative Wilson-CI bar could not save it because the quantity it estimates does not
persist.

**Action taken:** `MIRROR_GATE=0` appended to `.env` with a dated evidence comment (the gate's own
documented kill-switch; reversible; takes effect on the same pending restarts). **Everything that
assumes "free accuracy from inversion" — D2 and the `invert` flags in the equation ensemble —
should stop citing that premise.** Broader implication: ANY mechanism that hard-selects on trailing
bucket accuracy (invert/abstain/trust thresholds) is fitting noise unless it first demonstrates
out-of-sample persistence, which this data says does not exist at current n.

## 3. The direction story, re-derived (era-controlled)

Per-horizon, all 100,774 labels: 15m 0.488 (n=41,762) · 1h 0.494 (n=36,949) · 4h 0.503 (n=19,591)
· exit 0.443 (n=7,174). **Predictors are coin-flips at every horizon — confirmed.**

The famous numbers were ERA artifacts, not stable properties:

| measure | pre-7/11 era | since 7/11 |
|---|---|---|
| crypto realized sign-accuracy (journal) | 0.361 (n=2,942) | **0.523** (n=3,282, Wilson-low 0.505) |
| exit-horizon accuracy | 0.365 (frozen bucket) | 0.516 (backfilled 5 days) |
| crypto net P&L | −22,134 USDT | **+17,819 USDT** (but +30k of it in 2 outlier wins) |

- The "8.5-point gap" (predicted 48.8% vs realized 40.3%) **no longer exists** — realized now runs
  ~3 points ABOVE the fixed-horizon predictor baseline. The gap was a property of the pre-7/11
  system (pre profit-tailgate / direction-driver / market-isolation changes), not of this one.
- Taken vs skipped at identical horizons (train log, post-7/11): taken 0.471/0.500/0.495 vs skipped
  0.498/0.487/0.521 — **selection is currently neutral within CI**, neither adverse nor helpful.
  (The aggregate's flattering `taken|4h=0.586` mixes eras and label methods — feather-labeled
  majors 0.544 vs probe 0.328 — do not quote it unqualified.)
- Confidence calibration is still broken but NOT catastrophically inverted: conf 0.0–0.2 → 0.568,
  conf 0.6–0.8 → 0.425, conf 0.8–1.0 → 0.498 (34,175 rows). The old "conf≈1.0 = 29%" is stale.
- Win/loss shape (recent crypto): pnl-win-rate 0.464, payoff 1.357 (breakeven needs 1.153), median
  hold 13–14m. Expectancy ≈ +5.4 USDT/trade but tail-dominated (top-2 wins = 30k of the +17.8k).
- SHORT beats LONG at every fixed horizon (e.g. 4h: 0.543 vs 0.454) — worth a dedicated look, but
  test for era/downtrend confounding before acting.

**Bottom line:** the system stopped being "worse on trades it takes" around 7/11. What remains is
that NO input shows a real directional edge (everything 0.47–0.53), which points the next session
at the Input Hunt (Prompt 1: true L2 OFI/GOFI are still uncollected), not at exits or sign flips.

## 4. NEW finding: poisoned journal rows (measurement pollution)

456 journal rows have |net_pnl| > 10k, dominated by **374 rows: symbol "USDT", exchange NSE,
strategy "momentum", qty ≈ 66,000,000, entry 0.0076 → exit 0.70** — each fabricating ~₹45M profit
(sum ≈ ₹3.86B, which is why any naive journal P&L readout is garbage). They peak on 7/13 (372 rows)
and nearly stop after 7/14 — consistent with the market-isolation `market_guard` fix landing then.
These rows also injected ~400 fake-correct labels into `momentum|NSE|*|exit` buckets during the
backfill (they are cleanly separable — NSE market key — and do NOT pollute any crypto bucket).
**Open follow-ups:** (a) purge/quarantine the 456 rows (they feed TradeOutcomeNet training),
(b) add a sanity gate at journal-write (reject NSE rows with crypto-shaped symbols/absurd qty).

## 5. What changed on disk (this session)

- `trading/direction/truth_ledger.py` — flock + `journal=` param on backfill_journal
- `trading/online/live_loop.py` — exit-label backfill at the ingest seam (primary caller)
- `trading/brain/learn_loop.py` — 6h-gated safety-net backfill
- `tests/test_truth_ledger.py` — 2 new regression tests (11/11 green)
- `.env` — `MIRROR_GATE=0` (dated comment)
- Corrected in place, dated: `research/direction-accuracy-diagnosis-2026-07-11.md`,
  `research/direction-equation-quest/SYNTHESIS-AND-PLAN.md`, `research/ai-scientist/ideas-ledger.md`
- Live state: exit labels backfilled (n 3,459 → 7,174)

NOT committed to git (owner did not ask). Restarts pending (owner action, §1).
