# Agent agent-a3671ac1c05e4fbfe — wf_57b21e69-3a8

I tried hard to refute this claim across five angles. It survived all of them. Here is my assessment.

**Angle A — Does the quote support the claim?** Yes, near-verbatim. The abstract of Cont, Cucuringu & Zhang (arXiv 2112.13213) states they "examine the contemporaneous price impact of multi-level OFIs and reveal their additional explanatory power." The claim says "additional explanatory power for price moves beyond best-level OFI" — it does *not* overclaim predictive power. That hedging is what saves it.

**Angle B — Independent replication?** Found one from a *separate* group: Xu, Gould & Howison, "Multi-Level Order-Flow Imbalance in a Limit Order Book" (arXiv 1907.06230). Out-of-sample goodness-of-fit improves with *each additional* level for all 6 stocks; ridge on 10-level MLOFI cuts forecast RMSE 65–75% (large-tick) and 15–30% (small-tick) vs best-level-only. Robust across sampling schemes, OLS/ridge, and intraday seasonality. Two independent groups, same direction.

**Angle C — Source quality?** Rama Cont is arguably the leading name in this exact subfield. Primary arXiv paper + SSRN, not a blog, not marketing, not a press release.

**Angle D — Outdated?** No. 2019 + 2021 core, with 2025–26 crypto follow-ups still building on it.

**Angle E — Crypto contradiction?** I specifically hunted for a crypto refutation. The closest candidate (arXiv 2506.05764) actually cuts *for* the claim: 40 levels = 71.5% accuracy vs 10 levels = 58.4%, 5 levels = 58.0%. Deeper = better, though confounded by sample-size filtering rather than a clean feature-engineering ablation, so I count it as weak corroboration only.

**The real qualifications** (which qualify, but do not refute):
1. **Contemporaneous ≠ predictive.** Both core papers fit OFI against *contemporaneous* mid-price change. A ~70% contemporaneous R² is worthless for entry timing. The claim is worded correctly, but anyone reading it as "entry edge" is misreading it. Cont *does* have a separate forecasting section with genuine out-of-sample R² gains — that is the part that matters for entry.
2. **Equities, not crypto perps.** The primary source is Nasdaq equities. And note the tick-size split: gains were 65–75% for *large*-tick, only 15–30% for *small*-tick. BTCUSDT perp is extremely small-tick, so expect the low end.
3. **Diminishing returns past ~2–4 levels.** Levels 5–20 add little. This qualifies the "20-level" part of the implication.
4. **Severe collinearity.** Per-level OFIs are highly collinear — ridge or PCA is *required*. Dumping 20 raw per-level OFIs into a GBM unorthogonalized can hurt. Notably this *reinforces* the recording implication: PCA-integrated OFI needs per-level inputs to exist.

The engineering implication holds independently of all of this: per-level OFI is a strict superset — you can always collapse to top-of-book later, but you can never recover per-level from a top-only snapshot.

I could not refute this. Defaulting to `refuted=true` applies only under uncertainty, and I am not uncertain about the core claim.
