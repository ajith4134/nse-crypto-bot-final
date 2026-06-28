"""trading/strategy/guardrails.py — overfitting guardrails (T8.2).

The gate every evolved strategy must pass before it is trusted / promoted. Because the
evolution tests thousands of candidates, a good in-sample backtest means almost nothing
on its own — so we apply the standard multiple-testing defenses (López de Prado):

  • Probabilistic Sharpe Ratio (PSR) — confidence the true Sharpe exceeds a benchmark,
    adjusted for sample length, skew and kurtosis.
  • Deflated Sharpe Ratio (DSR) — PSR against a benchmark inflated by the NUMBER OF
    TRIALS, i.e. "is this Sharpe still significant given we tried N strategies?".
  • Probability of Backtest Overfitting (PBO) via CSCV — population-level: does the
    best in-sample config tend to land in the bottom half out-of-sample?
  • Walk-forward OOS positivity, min-trades, and max-drawdown sanity gates.

Reuse-first: the statistics come from scipy.stats (norm/skew/kurtosis/spearmanr); the
formulas + gating are the glue. Pure, deterministic, no new deps.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import combinations

import numpy as np
from scipy import stats

from trading.strategy.fitness import evaluate_oos

_EULER = 0.5772156649015329


# ── Probabilistic / Deflated Sharpe ─────────────────────────────────────────────
def probabilistic_sharpe_ratio(sr: float, n: int, *, skew: float = 0.0, kurt: float = 3.0,
                               sr_benchmark: float = 0.0) -> float:
    """PSR: P(true per-period Sharpe > sr_benchmark). `kurt` is NON-excess (normal=3)."""
    if n < 2:
        return 0.0
    denom = 1.0 - skew * sr + (kurt - 1.0) / 4.0 * sr * sr
    if denom <= 0:
        return 0.0
    z = (sr - sr_benchmark) * math.sqrt(n - 1) / math.sqrt(denom)
    return float(stats.norm.cdf(z))


def expected_max_sharpe(var_sr: float, n_trials: int) -> float:
    """Expected maximum of N independent Sharpe trials (the DSR deflation benchmark)."""
    if n_trials < 2 or var_sr <= 0:
        return 0.0
    sigma = math.sqrt(var_sr)
    a = stats.norm.ppf(1.0 - 1.0 / n_trials)
    b = stats.norm.ppf(1.0 - 1.0 / (n_trials * math.e))
    return float(sigma * ((1.0 - _EULER) * a + _EULER * b))


def deflated_sharpe_ratio(returns, *, n_trials: int, var_sr: float | None = None) -> dict:
    """DSR from a returns sample. var_sr = variance of Sharpe across the trial population
    (pass it from the generation; if omitted, a conservative proxy is used)."""
    r = np.asarray(returns, dtype=float)
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return {"sr": 0.0, "psr": 0.0, "dsr": 0.0, "sr_benchmark": 0.0, "n": n}
    sr = float(r.mean() / r.std(ddof=1))
    skew = float(stats.skew(r))
    kurt = float(stats.kurtosis(r, fisher=False))   # non-excess
    if var_sr is None:
        # conservative proxy: sampling variance of an estimated Sharpe ≈ (1+sr^2/2)/n
        var_sr = (1.0 + 0.5 * sr * sr) / n
    sr_star = expected_max_sharpe(var_sr, n_trials)
    psr0 = probabilistic_sharpe_ratio(sr, n, skew=skew, kurt=kurt, sr_benchmark=0.0)
    dsr = probabilistic_sharpe_ratio(sr, n, skew=skew, kurt=kurt, sr_benchmark=sr_star)
    return {"sr": sr, "psr": psr0, "dsr": dsr, "sr_benchmark": sr_star, "n": n,
            "skew": skew, "kurt": kurt}


# ── PBO via CSCV (population-level) ──────────────────────────────────────────────
def pbo_cscv(perf_blocks: np.ndarray, *, max_combos: int = 1000) -> dict:
    """Probability of Backtest Overfitting via Combinatorially-Symmetric Cross-Validation.

    `perf_blocks`: array shape (n_configs, n_blocks) — a performance scalar per strategy
    per time block (e.g. mean return). Returns {pbo, n_combos, median_logit}.
    """
    M = np.asarray(perf_blocks, dtype=float)
    if M.ndim != 2 or M.shape[0] < 2 or M.shape[1] < 4 or M.shape[1] % 2 != 0:
        raise ValueError("perf_blocks must be (n_configs>=2, n_blocks>=4 and even)")
    n_cfg, S = M.shape
    block_idx = list(range(S))
    logits = []
    combos = list(combinations(block_idx, S // 2))
    if len(combos) > max_combos:                 # subsample symmetric combos deterministically
        step = len(combos) // max_combos
        combos = combos[::step][:max_combos]
    for is_blocks in combos:
        is_set = set(is_blocks)
        oos_blocks = [b for b in block_idx if b not in is_set]
        is_perf = M[:, list(is_blocks)].mean(axis=1)
        oos_perf = M[:, oos_blocks].mean(axis=1)
        best = int(np.argmax(is_perf))
        # OOS rank of the IS-best config (1=worst .. n_cfg=best)
        rank = float(stats.rankdata(oos_perf)[best])
        omega = rank / (n_cfg + 1)
        omega = min(max(omega, 1e-6), 1 - 1e-6)
        logits.append(math.log(omega / (1.0 - omega)))
    logits = np.array(logits)
    pbo = float(np.mean(logits <= 0.0)) if len(logits) else 1.0
    return {"pbo": pbo, "n_combos": len(logits), "median_logit": float(np.median(logits))
            if len(logits) else 0.0}


# ── Information Coefficient gate (for factor/alpha genomes, T8.3) ─────────────────
def information_coefficient(values, forward_returns) -> float:
    """Rank IC (Spearman) between a factor/signal and forward returns."""
    a = np.asarray(values, dtype=float)
    b = np.asarray(forward_returns, dtype=float)
    mask = np.isfinite(a) & np.isfinite(b)
    if mask.sum() < 3:
        return 0.0
    ic, _ = stats.spearmanr(a[mask], b[mask])
    return float(ic) if np.isfinite(ic) else 0.0


# ── the gate ─────────────────────────────────────────────────────────────────────
@dataclass
class GuardrailReport:
    passed: bool
    reasons: list
    dsr: dict
    oos: dict

    def as_dict(self) -> dict:
        return {"passed": self.passed, "reasons": self.reasons, "dsr": self.dsr,
                "oos": {k: v for k, v in self.oos.items() if k != "trade_returns"}}


def passes_guardrails(strategy, ohlcv, *, n_trials: int = 1, features=None, n_folds: int = 4,
                      scheme: str = "rolling", min_trades: int = 10, dsr_min: float = 0.6,
                      max_dd_limit: float = -0.5, var_sr: float | None = None) -> GuardrailReport:
    """Run the full OOS + DSR gate for one strategy. `n_trials` = candidates tested this run."""
    oos = evaluate_oos(strategy, ohlcv, features=features, n_folds=n_folds, scheme=scheme)
    reasons = []
    n = oos["n_trades"]
    if n < min_trades:
        reasons.append(f"too few OOS trades ({n} < {min_trades})")
    if oos["oos_total_return"] <= 0:
        reasons.append(f"non-positive OOS return ({oos['oos_total_return']:.4f})")
    if oos["max_drawdown"] < max_dd_limit:
        reasons.append(f"drawdown too deep ({oos['max_drawdown']:.2f} < {max_dd_limit})")

    dsr = deflated_sharpe_ratio(oos["trade_returns"], n_trials=n_trials, var_sr=var_sr) \
        if n >= 3 else {"sr": 0.0, "psr": 0.0, "dsr": 0.0, "n": n}
    if dsr["dsr"] < dsr_min:
        reasons.append(f"deflated Sharpe too low ({dsr['dsr']:.3f} < {dsr_min}; "
                       f"{n_trials} trials)")

    return GuardrailReport(passed=(len(reasons) == 0), reasons=reasons, dsr=dsr, oos=oos)
