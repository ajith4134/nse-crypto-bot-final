# CPU-First Systems for Wiring Hundreds of ML/DL Models as Graph Nodes: A Survey of Adjacent Fields and Open-Source Projects

## Executive Summary

This report surveys the adjacent research fields and open-source projects relevant to building a CPU-first system that wires hundreds of ML/DL prediction models as graph "nodes," coordinated by an external "brain-agent" responsible for memory and learning. The strongest, best-evidenced foundations come from two areas: (1) **deep stacked/multi-layer ensembles with dynamic routing** (AutoGluon, H2O, Hellsemble, Ensemble²), where treating whole models — and even whole AutoML pipelines — as ensemble members is empirically validated, but selecting the right meta-learners at higher stacking layers remains an open problem; and (2) **reservoir computing / Echo State Networks** (ReservoirPy), which are notably CPU-friendly and outperform gated RNNs (LSTM/GRU) for chaotic time-series prediction by one-to-three orders of magnitude in speed. Supporting fields — nonlinear dynamics and signal-in-noise discovery (nolds, pyunicorn), financial regime/change-point detection (ruptures, hmmlearn, Merlion, Kats), continual learning (Avalanche), symbolic regression and self-improving agents (PySR, AlphaEvolve), and mixture-of-experts/model merging (MergeKit, FusionBench) — each map cleanly onto a component of the proposed architecture. The most confident, multi-primary-source findings concern ensemble stacking and reservoir computing; claims about continual learning, MoE, and symbolic-regression projects rest on fewer verified primary sources and should be treated as medium confidence.

---

## 1. Prediction Graph Networks: Deep Stacked & Multi-Layer Ensembles with Dynamic Routing

This is the field most directly analogous to "models as graph nodes." The architectural primitive — many full models whose outputs feed higher-level combiner models — is mature, well-benchmarked, and open-source.

**AutoGluon-Tabular** is an open-source AutoML framework (Apache-2.0) that trains highly accurate models on raw tabular/CSV data with a single line of Python. Crucially, its core technique is *not* tuning a single model but **ensembling multiple full models and stacking them in multiple layers** ([source](https://arxiv.org/pdf/2003.06505)) — confidence: **high** (primary, 3-0). Across 50 classification and regression benchmark tasks, AutoGluon-Tabular outperformed competing AutoML systems including TPOT, H2O, AutoWEKA, auto-sklearn, and Google AutoML Tables ([source](https://arxiv.org/pdf/2003.06505)) — confidence **high**, with the mild caveat that this is the authors' own benchmark (though independently corroborated by the OpenML AutoML benchmark).

**H2O Stacked Ensembles** implement the Super Learner / stacked regression method, training a second-level "metalearner" to find the optimal combination of multiple base learners ([source](https://docs.h2o.ai/h2o/latest-stable/h2o-docs/data-science/stacked-ensembles.html)) — confidence **high**. The procedure is the canonical recipe for "models as nodes": it builds **level-one data from k-fold cross-validated predictions of the L base learners, forming an N×L matrix** that, with the original response vector, trains the metalearner ([source](https://docs.h2o.ai/h2o/latest-stable/h2o-docs/data-science/stacked-ensembles.html)) — confidence **high**. This rests on textbook methodology (Wolpert 1992 stacked generalization; Breiman 1996 stacked regressions; van der Laan et al. 2007 Super Learner).

**Scaling to deeper stacks and to time series.** Multi-layer stack ensembles built on AutoGluon-TimeSeries base models consistently outperform individual combination methods across 50 real-world datasets, achieving up to ~5% error reduction over simple median aggregation; learned aggregation (ensemble selection, linear models) beats simple or performance-based averaging ([source](https://arxiv.org/html/2511.15350)) — confidence **high** (the word "consistently" is mildly softened, since average rank 2.81 means stacking is not literally best on every dataset).

**The open gap — dynamic routing/meta-learner selection at higher layers.** The same work explicitly states that **selecting which aggregation/meta-learner models to use at higher stacking layers (L2/L3) remains an open and important challenge** ([source](https://arxiv.org/html/2511.15350)) — confidence **medium** (this is a single recent preprint's self-stated future work, not field-wide consensus). This is precisely the "dynamic routing between full-model nodes" gap a brain-agent architecture would target.

**Explicit routing architectures already exist on tabular data.** **Hellsemble** is an interpretable ensemble framework that demonstrates the "models-as-nodes with dynamic routing" pattern: **a separate router model learns to assign each new instance to the most suitable base model based on inferred difficulty** ([source](https://arxiv.org/pdf/2506.20814)) — confidence **high**. It builds its committee by **incrementally partitioning data into "circles of difficulty," passing misclassified instances to subsequent models so each base learner specializes on increasingly hard subsets** ([source](https://arxiv.org/pdf/2506.20814)) — confidence **high** (caveat: specifically binary classification, evaluated on OpenML-CC18/Tabzilla with KNN, Naive Bayes, Logistic Regression, Decision Trees, Random Forest, and XGBoost as base learners).

**Treating whole pipelines as nodes.** **Ensemble Squared (Ensemble²)** is a meta-AutoML system that ensembles the *outputs of multiple state-of-the-art open-source AutoML systems* rather than individual models ([source](https://arxiv.org/pdf/2012.05390)) — confidence **high**. Its empirical finding is directly relevant to a graph-of-models design: the **diversity of search spaces and heuristics across different AutoML systems is sufficient to justify ensembling at the AutoML-system level**, i.e., treating whole pipelines as ensemble members ([source](https://arxiv.org/pdf/2012.05390)) — confidence **high**.

**What scales vs. what is still open (benchmark evidence).** On larger datasets (≥1,900 samples), **Ensemble Selection and Stacking outperform other ensemble techniques** such as majority voting and dynamic selection ([source](https://arxiv.org/html/2307.00285v1)) — confidence **high** (the paper notes weaker dynamic-selection results may partly reflect limited base-model diversity in the benchmark). That same benchmark evaluates the dynamic routing/selection family — **Dynamic Classifier Selection (DCS) and Dynamic Ensemble Selection (DES)** — alongside stacking and ensemble selection across 31 datasets ([source](https://arxiv.org/html/2307.00285v1)) — confidence **high**.

**Summary for Section 1:** Multi-layer stacking of full models scales well and is the safest architectural backbone. Dynamic routing between model-nodes (DCS/DES, Hellsemble routers) exists but currently underperforms static stacking on standard benchmarks, and meta-learner selection at deeper layers is an acknowledged open problem — the natural niche for an external brain-agent.

*GNN-based meta-learners* were named in the research question, but no claim on them survived adversarial verification; they should be treated as an unverified avenue here.

---

## 2. Chaos, Noise, and Signal-in-Noise Discovery (incl. Reservoir Computing)

This section covers the CPU-friendly toolkit for distinguishing structure from noise in nonlinear/chaotic time series — a strong fit for CPU-first deployment.

### Reservoir Computing / Echo State Networks — the headline CPU-friendly approach

**ReservoirPy** is a simple, flexible Python library for Reservoir Computing architectures, particularly **Echo State Networks (ESNs)**, for temporal/sequence processing, developed and maintained by **Inria's Mnemosyne group in Bordeaux, France** ([source](https://github.com/reservoirpy/reservoirpy), [source](https://link.springer.com/chapter/10.1007/978-3-030-61616-8_40)) — confidence **high**. It demonstrates chaotic time-series prediction on the **Mackey-Glass** dataset, achieving **RMSE 0.0020282 and R² 0.99992** ([source](https://github.com/reservoirpy/reservoirpy)) — confidence **high** (this is an illustrative README run, not an averaged benchmark).

ReservoirPy is explicitly **CPU-friendly**: its advanced features (sparse matrix computation, parallelism, fast spectral initialization, efficient ridge/FORCE training — all NumPy/SciPy-based and GPU-free) **improve computation-time efficiency on an ordinary laptop relative to a basic Python implementation** (up to 87.9% in the original paper) ([source](https://link.springer.com/chapter/10.1007/978-3-030-61616-8_40)) — confidence **high**.

**Why reservoir computing matters for a CPU-first chaotic-prediction system.** A peer-reviewed comparative study finds that **next-generation reservoir computing (NVAR) is faster than ESNs by more than one order of magnitude, and faster than gated RNNs (LSTM/GRU) by more than two orders of magnitude** for chaotic time-series prediction ([source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) — confidence **high**. Conversely, **gated RNNs (LSTM, GRU), while successful for general time series, perform poorly at predicting chaotic series** compared with reservoir approaches ([source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) — confidence **high**. On the Lorenz dataset specifically, **LSTM and GRU are more than 3 orders of magnitude slower to train/run than NVAR and ESN** ([source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) — confidence **high**. (Caveat: figures derive from Mackey-Glass/Lorenz/Morris-Lecar benchmarks, not a universal proof, but they match established next-generation RC literature, e.g., Gauthier et al. 2021.)

**Implication:** Because ESNs/NVAR avoid backpropagation-through-time, they are dramatically cheaper on CPU than gated RNNs *and* more accurate on chaotic signals — making ReservoirPy a prime candidate for CPU-first model-nodes handling noisy/chaotic time series.

### Nonlinear dynamics, RQA, and Lyapunov/entropy measures

**nolds** is a small NumPy-based Python library implementing nonlinear measures for dynamical systems from one-dimensional time series; **NumPy is its sole hard requirement**, making it CPU-friendly ([source](https://pypi.org/project/nolds/)) — confidence **high**. It computes **Lyapunov exponents (via the Rosenstein and Eckmann algorithms), sample entropy, and correlation dimension** as chaos/complexity indicators relevant to signal-in-noise discovery — positive Lyapunov exponents indicating chaos and unpredictability ([source](https://pypi.org/project/nolds/)) — confidence **high**.

**pyunicorn** is an open-source (BSD 3-Clause) Python package that implements methods from both **complex network theory and nonlinear time series analysis** in a performant, modular, and flexible way ([source](https://arxiv.org/pdf/1507.01571)) — confidence **high**. It performs nonlinear time series analysis using **recurrence plots, recurrence networks, and visibility graphs** — i.e., recurrence quantification analysis (RQA) grounded in the recurrence properties of phase-space trajectories ([source](https://arxiv.org/pdf/1507.01571)) — confidence **high**.

**Summary for Section 2:** ReservoirPy (ESN/NVAR), nolds (Lyapunov/entropy/correlation dimension), and pyunicorn (RQA/recurrence networks) form a coherent, NumPy/SciPy-based, GPU-free stack for separating signal from noise — among the most CPU-friendly options in this entire report.

---

## 3. Quantitative Finance & Trading ML: Regime, Change-Point, and Anomaly Detection

This section addresses market regime detection, change-point/anomaly detection, and pattern discovery in noisy financial time series.

**ruptures** is a Python library for **offline change-point detection and segmentation of non-stationary signals**, directly applicable to detecting regime shifts/change-points in noisy financial time series ([source](https://github.com/deepcharles/ruptures)) — confidence **high**. Note: a related claim that ruptures is "pure-Python, CPU-only, with no GPU requirement" was **refuted (1-2 vote)** during verification and should not be relied upon; its CPU-only/offline character is therefore **unconfirmed** here.

Additional reputable OSS libraries were identified as source material for this domain but did not have specific claims survive 3-vote verification, so they are listed at **lower confidence** as starting points rather than verified facts:
- **hmmlearn** — Hidden Markov Models, commonly used for market regime detection ([source](https://github.com/hmmlearn/hmmlearn)) — confidence **low** (source listed, claim unverified).
- **Merlion** (Salesforce) — a library for time-series anomaly detection and forecasting ([source](https://github.com/salesforce/Merlion)) — confidence **low**.
- **Kats** (Facebook/Meta) — a toolkit for time-series analysis including change-point and anomaly detection ([source](https://github.com/facebookresearch/Kats)) — confidence **low**.

**Summary for Section 3:** ruptures is the verified anchor for change-point/regime detection; hmmlearn, Merlion, and Kats are credible complementary starting points but were not independently verified in this pass.

---

## 4. Brain-Like Memory, Continual/Lifelong Learning, and Growing Networks

This maps to the "outside brain-agent for memory and learning" and to catastrophic-forgetting mitigation. No claims in this area survived 3-vote adversarial verification, so the following are presented at **low confidence** as starting points based on the source list rather than verified facts:

- **Avalanche** (ContinualAI) — an end-to-end library for continual/lifelong learning, including catastrophic-forgetting benchmarks and strategies ([source](https://github.com/ContinualAI/avalanche)) — confidence **low**.
- Continual-learning surveys and growing/expandable network literature (progressive networks, dynamically expandable networks) are represented by ([source](https://www.sciencedirect.com/science/article/pii/S1566253523001458)) and a related Nature Communications article ([source](https://www.nature.com/articles/s41467-020-17866-2)) — confidence **low** (sources listed; specific claims not independently verified here).

**Summary for Section 4:** Avalanche is the natural OSS starting point for the brain-agent's continual-learning/memory layer, but the evidence here is unverified and should be confirmed before relying on specifics.

---

## 5. Symbolic Regression, Equation/Algorithm Discovery, and Self-Improving Agents

This maps to a brain-agent that *discovers structure and improves itself*. No claims survived 3-vote verification, so these are **low-confidence** starting points from the source list:

- **PySR** (Miles Cranmer) — high-performance symbolic regression for discovering interpretable equations from data; Python with a Julia backend, runs well on CPU ([source](https://github.com/MilesCranmer/PySR)) — confidence **low** (well-known project; specific claim unverified in this pass).
- **AlphaEvolve** (DeepMind) — a Gemini-powered evolutionary coding agent for designing/improving algorithms ([source](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)) — confidence **low** (vendor blog, primary but promotional).
- The research question also named **LLM-SR, OpenEvolve, AI-Scientist, and FunSearch** as relevant projects; these had no verified claims and are noted as avenues only.

**Summary for Section 5:** PySR is the strongest CPU-feasible OSS anchor for equation discovery; the self-improving-agent projects (AlphaEvolve/FunSearch family) are LLM-driven and generally *not* CPU-first.

---

## 6. Mixture-of-Experts and Model Merging (the Architectural Analog of "Models as Nodes")

MoE — a router selecting among expert sub-models — is the closest large-model analog to "models as graph nodes with dynamic routing." Model merging is the complementary "fuse many models into one" operation. No claims survived 3-vote verification, so these are **low-confidence** starting points from the source list:

- **MergeKit** (Arcee AI) — a toolkit for merging pretrained language models ([source](https://github.com/arcee-ai/mergekit)) — confidence **low**.
- **FusionBench** — a benchmark for deep model fusion / model merging ([source](https://github.com/tanganke/fusion_bench), [source](https://arxiv.org/abs/2409.02060)) — confidence **low**.
- The question also named **Mixtral and OLMoE** as the canonical sparse-MoE reference models; these had no verified claims here.
- A model-merging/MoE survey is represented by ([source](https://arxiv.org/pdf/2307.09218)) — confidence **low**.

**Caveat on CPU-fitness:** Large sparse-MoE LLMs (Mixtral, OLMoE) are **not** CPU-first; only a subset of their experts activates per token, which helps inference cost but they still typically require accelerators at scale. MergeKit's merging operations, by contrast, are often feasible on CPU/RAM-bound machines.

---

## 7. CPU-Only / Lightweight ML: Practical CPU-First Guidance

The research question asks which of the above run well without a GPU and requests practical CPU-first guidance (gradient boosting, ONNX Runtime CPU inference, quantization). Several CPU-friendliness findings are **verified at high confidence**:

- **Reservoir computing (ReservoirPy / ESN / NVAR)** is strongly CPU-friendly and *faster on CPU than gated RNNs by 1–3 orders of magnitude* for chaotic series, because it avoids backpropagation-through-time ([source](https://link.springer.com/chapter/10.1007/978-3-030-61616-8_40), [source](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) — confidence **high**.
- **nolds** (nonlinear measures) is CPU-friendly with NumPy as its only hard requirement ([source](https://pypi.org/project/nolds/)) — confidence **high**.
- **pyunicorn** (RQA/recurrence networks) is a performant, modular CPU-based package ([source](https://arxiv.org/pdf/1507.01571)) — confidence **high**.
- **Stacked ensembles** (AutoGluon, H2O) run primarily on CPU and are built around gradient-boosted base learners; AutoGluon's single-line tabular workflow is a practical CPU-first default ([source](https://arxiv.org/pdf/2003.06505), [source](https://docs.h2o.ai/h2o/latest-stable/h2o-docs/data-science/stacked-ensembles.html)) — confidence **high**.

The question's specific items — **XGBoost / LightGBM / CatBoost gradient boosting, ONNX Runtime CPU inference, and quantization** — are well-established CPU-first techniques but had **no claims survive verification** in this pass; they are noted as standard practice (gradient-boosted trees are the de facto CPU-first tabular baseline and underpin AutoGluon/H2O stacks) at **low confidence** for any specific assertion.

---

## Concluding Table: Topic → Best OSS Starting Point → CPU Feasibility

| Related topic | Best OSS starting point | CPU feasibility | Confidence |
|---|---|---|---|
| Deep stacked / multi-layer ensembles (models as nodes) | AutoGluon-Tabular ([src](https://arxiv.org/pdf/2003.06505)); H2O Stacked Ensembles ([src](https://docs.h2o.ai/h2o/latest-stable/h2o-docs/data-science/stacked-ensembles.html)) | CPU-friendly (GBM base learners) | High |
| Dynamic routing between full-model nodes | Hellsemble ([src](https://arxiv.org/pdf/2506.20814)); DCS/DES benchmark ([src](https://arxiv.org/html/2307.00285v1)) | CPU-friendly | High (method) / open gap at L2–L3 ([src](https://arxiv.org/html/2511.15350)), Medium |
| Pipelines-as-nodes (meta-AutoML) | Ensemble² ([src](https://arxiv.org/pdf/2012.05390)) | CPU-friendly | High |
| Chaotic time-series prediction (reservoir computing) | ReservoirPy / ESN / NVAR ([src](https://github.com/reservoirpy/reservoirpy)) | Strongly CPU-friendly; faster than RNNs ([src](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) | High |
| Chaos / entropy / Lyapunov measures | nolds ([src](https://pypi.org/project/nolds/)) | CPU-friendly (NumPy-only) | High |
| Recurrence quantification / recurrence networks | pyunicorn ([src](https://arxiv.org/pdf/1507.01571)) | CPU-friendly (BSD, performant) | High |
| Financial regime / change-point detection | ruptures ([src](https://github.com/deepcharles/ruptures)); hmmlearn, Merlion, Kats | Likely CPU-friendly (CPU-only claim refuted/unverified) | High (ruptures purpose) / Low (CPU claim) |
| Continual / lifelong learning & growing nets | Avalanche ([src](https://github.com/ContinualAI/avalanche)) | Varies (often CPU-feasible for small models) | Low (unverified) |
| Symbolic regression / equation discovery | PySR ([src](https://github.com/MilesCranmer/PySR)) | CPU-feasible | Low (unverified) |
| Self-improving / algorithm-discovery agents | AlphaEvolve ([src](https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/)); FunSearch family | LLM-driven — not CPU-first | Low (unverified) |
| Mixture-of-Experts (routing analog) | Mixtral / OLMoE | Not CPU-first (needs accelerators) | Low (unverified) |
| Model merging | MergeKit ([src](https://github.com/arcee-ai/mergekit)); FusionBench ([src](https://github.com/tanganke/fusion_bench)) | Merging often CPU/RAM-feasible | Low (unverified) |

---

## Caveats

- **Uneven evidence depth.** Sections 1–3 rest on multiple primary sources with unanimous (3-0) adversarial verification and are **high confidence**. Sections 4–6 (continual learning, symbolic regression/self-improving agents, MoE/model merging) had **no claims survive 3-vote verification**; their projects are named from the curated source list and should be treated as **low-confidence starting points**, not verified facts. Confirm specifics directly from the linked repositories before relying on them.
- **Refuted claim.** The assertion that **ruptures is "pure-Python, CPU-only, with no GPU requirement"** was refuted (1-2 vote). ruptures' purpose (offline change-point detection) is verified; its precise CPU/GPU profile is not.
- **Self-interested benchmarks.** The AutoGluon 50-task comparison ([src](https://arxiv.org/pdf/2003.06505)) and the multi-layer time-series stacking results ([src](https://arxiv.org/html/2511.15350)) are authored by the methods' proponents; the latter's L2/L3 open-problem statement is one preprint's self-stated future work, not field consensus (**medium** confidence).
- **Benchmark-specific generalization.** The reservoir-computing speed/accuracy advantages over LSTM/GRU ([src](https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/)) are measured on Mackey-Glass, Lorenz, and Morris-Lecar systems; they are consistent with broader RC literature but are not universal proofs. The ReservoirPy Mackey-Glass metrics are a single README example, not an averaged benchmark.
- **Time-sensitivity.** AutoML, MoE, model merging, and self-improving-agent fields move quickly (2024–2026). The reservoir-computing and nonlinear-dynamics findings are in slower-moving niches and are less likely to be outdated.

## Open Questions

1. **Meta-learner / router selection at depth.** What principled method should a brain-agent use to choose which aggregation models to deploy at L2/L3 stacking layers — the explicitly open problem in current multi-layer stacking research ([src](https://arxiv.org/html/2511.15350))?
2. **Dynamic routing vs. static stacking at scale.** Dynamic selection (DCS/DES) currently underperforms static stacking on standard benchmarks ([src](https://arxiv.org/html/2307.00285v1)); does this reverse with hundreds of diverse model-nodes and a learning brain-agent supplying the missing base-model diversity?
3. **Continual learning for the brain-agent.** Which catastrophic-forgetting mitigation and growing-network strategies (Avalanche and the progressive/dynamically-expandable-network literature) remain CPU-feasible at the scale of hundreds of coordinated model-nodes? (Currently unverified.)
4. **MoE/model-merging transfer to CPU-first tabular/time-series graphs.** Can sparse-routing and model-merging techniques developed for large LLMs (MergeKit, FusionBench) be adapted into CPU-first "models-as-nodes" routing without accelerator dependence?

## References

- https://arxiv.org/pdf/2003.06505
- https://docs.h2o.ai/h2o/latest-stable/h2o-docs/data-science/stacked-ensembles.html
- https://arxiv.org/html/2511.15350
- https://arxiv.org/pdf/2506.20814
- https://arxiv.org/pdf/2012.05390
- https://arxiv.org/html/2307.00285v1
- https://github.com/reservoirpy/reservoirpy
- https://link.springer.com/chapter/10.1007/978-3-030-61616-8_40
- https://github.com/reservoirpy/awesome-reservoir-computing
- https://pypi.org/project/nolds/
- https://arxiv.org/pdf/1507.01571
- https://pmc.ncbi.nlm.nih.gov/articles/PMC9230140/
- https://github.com/deepcharles/ruptures
- https://github.com/hmmlearn/hmmlearn
- https://github.com/salesforce/Merlion
- https://github.com/facebookresearch/Kats
- https://github.com/ContinualAI/avalanche
- https://www.nature.com/articles/s41467-020-17866-2
- https://www.sciencedirect.com/science/article/pii/S1566253523001458
- https://arxiv.org/pdf/2307.09218
- https://github.com/MilesCranmer/PySR
- https://deepmind.google/blog/alphaevolve-a-gemini-powered-coding-agent-for-designing-advanced-algorithms/
- https://github.com/arcee-ai/mergekit
- https://arxiv.org/abs/2409.02060
- https://github.com/tanganke/fusion_bench

---

## Refuted claims (excluded for transparency)
- "ruptures is a pure-Python, CPU-only, offline (non-real-time) library with no GPU requirement, making it suitable for CPU-first systems." — https://github.com/deepcharles/ruptures (vote 1-2)

---

## Run statistics
- Search angles: 5
- Sources fetched: 25
- Claims extracted: 116
- Claims verified: 25
- Confirmed (survived voting): 24
- Refuted (killed): 1
