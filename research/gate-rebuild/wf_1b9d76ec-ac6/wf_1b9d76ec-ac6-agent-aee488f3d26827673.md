# Agent agent-aee488f3d26827673 — wf_1b9d76ec-ac6

I verified the claim independently rather than relying on the Crossref reference list.

**Findings:**

1. **Heston + Merton attribution — CONFIRMED, but not by the quoted evidence.** A reference list does not establish methodology (Heston/Merton could be cited in an intro). However, the authors' own reproduction repo confirms it directly: `RiskLabAI/Notebooks.py` → `backtest/5_backtest_overfitting_simulation/` builds a `regimes` dict with Heston parameters (`kappa`, `theta`, `xi`, `rho`, `mu`) plus Merton jump params (`lam`, `m`, `v`) for calm/volatile/speculative_bubble, and calls `drift_volatility_burst(...)` (Christensen et al. drift-burst, ref b16). Paper title itself: "...in a synthetic controlled environment" (Knowledge-Based Systems Vol 305, 112477, Dec 2024; Arian, Norouzi M., Seco).

2. **Reference implementation — CONFIRMED.** `RiskLabAI/RiskLabAI.py` (pushed 2026-07-12) contains `backtest/validation/combinatorial_purged.py`, `bagged_combinatorial_purged.py`, `adaptive_combinatorial_purged.py`, `purged_kfold.py`, `walk_forward.py`, plus `probability_of_backtest_overfitting.py`, `probabilistic_sharpe_ratio.py`, `sharpe_inference.py`, `backtest_synthetic_data.py` — with a parallel unit-test tree. So "directly reusable for a CPCV/PBO/DSR gate" holds. Note: `pip install RiskLabAI`; org repos have ~0-1 stars, so it is low-adoption code, not battle-tested.

3. **Material qualification the claim omits.** The paper is NOT synthetic-only. The authors' readme states: *"Real-World Validation: Empirical validation using historical S&P 500 data confirms the practical applicability and resilience of CPCV and its variants"*, and the repo ships `figs/sp500_pbo_dsr_comparison.png`. The claim's framing ("results are from SYNTHETIC simulated price processes") understates this. Strictly parsed, though, each assertion still survives: the primary comparison IS synthetic, and the finding is indeed not validated on crypto perp order-flow (S&P 500 daily bars ≠ 500ms L2 microstructure).

The claim's stated evidence (Crossref reference list) was too weak for the strength of the methodological assertion, but the assertion checks out against primary sources, so I do not refute it.

Sources: [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110), [SSRN 4686376](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4686376), [RiskLabAI.py](https://github.com/RiskLabAI/RiskLabAI.py), [Notebooks.py reproduction](https://github.com/RiskLabAI/Notebooks.py/tree/main/backtest/5_backtest_overfitting_simulation)
