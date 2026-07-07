"""trading/strategy/generators/stats_gate.py — generator ⑥ (part A): family-wise error control.

Research shortlist #6: now that the portfolio produces MANY candidates per cycle from several
generators, the chance that the best one looks good by luck rises. Our Deflated-Sharpe already
deflates by the trial count; this ADDS Hansen's StepM (a stepwise White's-Reality-Check / SPA)
to control the family-wise error rate — it tells us which candidates beat a do-nothing benchmark
*after* correcting for how many were tried, holding the FWER at `alpha`.

Reuse: arch.bootstrap.StepM (Hansen 2005) via a stationary bootstrap. Fail-open by design — if
the sample is too small to test or the bootstrap errors, it returns "all pass" so it can only
ever ADD strictness when statistically meaningful, never silently block the whole portfolio.
"""
from __future__ import annotations

import numpy as np


def family_wise_superior(fold_returns_by_id: dict, *, alpha: float = 0.05,
                         reps: int = 200) -> set:
    """Return the ids whose OOS per-path returns beat a zero benchmark, FWER-controlled.

    `fold_returns_by_id`: {candidate_id: list of per-CPCV-path OOS returns} — aligned across
    candidates (same paths). Uses StepM on losses = -returns (a superior model has lower loss).
    Fail-open: returns ALL ids if the sample is too small (<8 paths / <2 models) or on error."""
    ids = [k for k, v in fold_returns_by_id.items() if v is not None and len(v) >= 8]
    all_ids = set(fold_returns_by_id.keys())
    if len(ids) < 2:
        return all_ids
    T = min(len(fold_returns_by_id[i]) for i in ids)
    if T < 8:
        return all_ids
    try:
        import pandas as pd
        from arch.bootstrap import StepM
        losses = pd.DataFrame({i: -np.asarray(fold_returns_by_id[i][:T], dtype=float)
                               for i in ids})
        benchmark = pd.Series(np.zeros(T), name="benchmark")
        stepm = StepM(benchmark, losses, size=float(alpha), reps=int(reps),
                      block_size=max(2, T // 4))
        stepm.compute()
        superior = set(stepm.superior_models)
        # keep untested ids (too few paths) so they still flow to the individual guardrail
        return superior | (all_ids - set(ids))
    except Exception:
        return all_ids
