# Agent agent-abc45bfb8685e59bb — wf_57b21e69-3a8

I have the primary PDF text with the actual tables. The claim collapses under direct inspection of the paper's own numbers.

**Decisive findings from arXiv:2112.13213v1 (extracted full text):**

1. **The paper's own body text contradicts the in-sample half of the claim.** Section on "Performance of Integrated OFIs": *"even though the in-sample R² of PII is lower than PI[m] (when m ≥ 5), its performance in out-of-sample tests is better than PI[m] (∀1≤m≤10)."* Table 3 gives PII in-sample R² = **87.14%**; Table 1 gives PI[5]=87.66%, PI[8]=89.04%, PI[10]=**89.38%** — all higher. The abstract's "superior in both in-sample and out-of-sample" is an overstatement contradicted by the authors' own tables.

2. **"Out-of-sample" here is contemporaneous fitting, not prediction.** The paper defines: *"contemporaneous returns denote the returns that materialize over the same bucket of time as the OFI."* The 83.83% OOS R² regresses same-bucket OFI on same-bucket return, fitted on a prior 30-min window. That is untradeable at entry — it cannot be snapshotted to forecast.

3. **In the genuine forecasting test (Table 6), integrated OFI OOS R² is negative: −17.62%** (vs −19.07% for best-level ofi1). Both are worse than predicting the mean. The PCA integration is only marginally less-bad, and the paper concedes *"negative R² values do not imply that the forecasts are economically meaningless"* — an admission that predictive R² failed.

4. **Version drift:** the quote is from the v1 preprint abstract. The published v4, retitled *"Cross-Impact of Order Flow Imbalance in Equity Markets"*, dropped the "superior results in both in-sample and out-of-sample" and PCA framing, softening to *"better explains price impact, compared to the best-level OFI."*

5. **Asset-class mismatch:** Nasdaq equities, 2017–2019. Nothing on crypto perps.

The steelman — PII beats best-level PI[1] both IS (87.14 vs 71.16) and OOS (83.83 vs 64.64), and beats multi-level OOS — is real and is a genuine anti-overfitting result. But that is contemporaneous explanatory power against a *single-level* baseline only, not the claim as worded, and not entry-time predictive edge.
