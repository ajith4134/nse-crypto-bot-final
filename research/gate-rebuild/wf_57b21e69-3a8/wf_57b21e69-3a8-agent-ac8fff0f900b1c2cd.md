# Agent agent-ac8fff0f900b1c2cd — wf_57b21e69-3a8

I attempted to refute this claim on all five checklist axes and could not.

**Checklist results:**

1. **Quote vs. claim** — No overreach. The claim asserts "explanatory power," which is precisely the contemporaneous framing the quote uses. Had the claim asserted *predictive* power from that quote alone, it would be a misread — but it doesn't. Separately, the paper's own abstract goes further ("significantly increase both in-sample and out-of-sample R²"), so even the stronger reading survives.

2. **Contradicting evidence** — Two targeted searches for disputes/qualifications returned nothing. My "no additional predictive power / best-level sufficient" search surfaced only irrelevant hits (video prediction hierarchies, leadership research) — the absence of any credible dissent on a well-trodden microstructure question is itself informative.

3. **Source quality** — Exceeds the bar. Cont/Cucuringu/Zhang, arXiv 2112.13213, peer-reviewed in *Quantitative Finance* Vol 23 No 10 (2023). Independently corroborated by the separate MLOFI paper (Xu/Gould/Cont, Oxford ORA) on LOBSTER Nasdaq data: **out-of-sample** RMSE reductions of 65–75% (large-tick) and 15–30% (small-tick) vs. best-level-only. Two independent primary sources, not one. This is a modest incremental claim, not an extraordinary one.

4. **Currency** — v1 Dec 2021, v4 June 2023. Market microstructure of LOB mechanics is not a fast-moving field the way model architectures are; the mechanism (depth beyond best carries queue information) is structural.

5. **Marketing/cherry-pick** — No. Academic, peer-reviewed, single-level OFI used as explicit baseline.

**Qualifications worth carrying forward (they qualify, they do not refute):**

- **Asset class transfer**: the primary source is *equities* (Nasdaq), not crypto perps. This is the claim's weakest joint. However, independent crypto work corroborates directionally — Binance Futures perp LOB studies (arXiv 2607.09230) use multi-level depth/imbalance, and crypto order imbalance is documented as out-of-sample predictive.
- **The paper's actual prescription is *integrated* OFI via PCA across levels**, not 20 raw per-level OFIs dumped into a model. The claim's implication still holds — you must snapshot per-level to *compute* the PCA-integrated variable — but the modeling step matters. Given your gate problem (in-sample Sharpe, −0.031 correlation to profit, n=260), naively adding 20 correlated per-level OFI columns is exactly the multiple-testing/overfit failure mode you're already suffering from. PCA-integration is the variance-controlled form.
- **Diminishing returns with depth**: gains concentrate in the first several levels beyond best. 20 levels is not specifically validated as optimal, but recording is cheap and the PCA handles collapse.

**Entry snapshot implication (supported):** record per-level OFI for all 20 levels plus the PCA-integrated OFI scalar. Cont et al.'s cross-impact finding is a bonus for your 200-coin setup: once multi-level OFI is integrated, *contemporaneous* cross-asset terms add nothing — but *lagged* cross-asset OFIs do improve forecasting at short horizons, decaying rapidly. That argues for snapshotting BTC/ETH lagged integrated-OFI at entry too.
