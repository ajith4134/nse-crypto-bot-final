"""trading/direction — the Direction Accuracy Program (goal Pillar 27).

Measured 2026-07-10: the brain chose the correct side on only 40.3% of 1,665 closed
crypto trades (its most-confident bucket: 29%) — a systematic anti-signal. This package
makes direction a MEASURED, calibrated, self-correcting decision instead of a hope:

  truth_ledger  — D1: fixed-horizon direction outcomes for every decision (taken AND
                  skipped), per source×regime×horizon hit-rates with Wilson CIs.

Plan: research/direction-accuracy-program/PLAN.md (D1-D9 + watchlist study + live mirror).
"""
