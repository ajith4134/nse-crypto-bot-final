# Concept Discovery Engine — "Idea Discovery Mode" (pure-self feature invention)

**Origin:** User request 2026-07-03 after watching *"How Neural Networks Learn Concepts"*
(Art of the Problem / Distill.pub neuron-probing visuals) + a "Claude × Quant" dashboard image
whose INPUTS panel feeds abstract self-invented features (PHASE, TARGET, DISTANCE, ANGLE,
VELOCITY, ENERGY) into an 8-layer SELF-LEARN deep MLP.

**Core idea (from the video):** a deep net turns *perception → concepts* by inventing its own
features in the hidden layers — nobody hand-codes them. Early layers = edges, mid = textures,
deep = whole objects; each layer transforms points until messy *perception space* becomes clean
*concept space* (tight manifolds). You can **probe and name** each latent unit. We currently
hand-feed engineered features to our 320+ nodes; this engine instead lets the net **invent its
own market features purely by itself**, reads them out, names them, and feeds the useful ones back.

**User design decisions:**
- **Two lanes (paper-trading, no real money → experimentation is the point):**
  - **Experiment lane** — *fully autonomous, ungated*: discovered features flow straight into
    paper trades with NO validation gate. Pure-self invention, maximum exploration.
  - **Validated lane** — *proof-gated*: a discovered feature may only enter the "trusted" set
    after passing the anti-overfit (Pillar 20: CPCV+DSR+PBO) and causal (Pillar 19) gates.
  - Same engine, a per-feature `lane` flag decides which path it takes.
- **Status: SELECTION DONE, BUILD NOT STARTED.** User will paste a list of models; we combine
  their list + this online research, THEN start building. Do not build until the list arrives.

Maps onto goal Pillar 7 (NN prediction engine) and Pillar 24 (program synthesis / library learning).

---

## The pipeline (3 stitched stages + 2-lane output)

```
RAW PERCEPTION            STAGE 1: INVENT            STAGE 2: READ OUT & NAME       STAGE 3: SEE IT
OHLCV windows  ─┐       self-supervised encoders    probe latent units,            reduce + cluster
L2 order book  ─┼─►  (TS2Vec + tsai + TF-C + ──►   crack polysemantic units   ──►  concept manifolds
funding/OBI    ─┘     DeepLOB/LOBench branch)       into monosemantic features      (UMAP+HDBSCAN)
                          │                              │  (SAE) + LLM auto-name        │
                          ▼                              ▼                               ▼
                    latent embedding  ──────────►  named discovered features  ──►  ConceptSpacePanel
                                                         │
                                                    ┌────┴─────┐
                                          EXPERIMENT lane   VALIDATED lane
                                          (ungated →        (Pillar 20+19 gate →
                                           paper trades)     trusted feature set)
```

---

## STAGE 1 — Self-supervised representation (the net invents features)
Full report: `research/self-supervised-representation-learning-oss.md`. **Every PyTorch repo below
runs CPU-only** (GPU flags are just device selectors; TS2Vec/tsai/PatchTST train fine on CPU).

| Project | Repo | Role | Score | Verdict |
|---|---|---|---|---|
| **TS2Vec** | yuezhihan/ts2vec | Primary OHLCV hierarchical-contrastive encoder; light dilated-CNN; clean `model.encode()` (dim 320), causal sliding for streaming | 9 | **Core** |
| **tsai** | timeseriesAI/tsai | Harness: masked-value-prediction SSL (MVP/TSBERT) + encoder zoo + embedding extraction — no hand-rolled training loops | 9 | **Core** |
| **TF-C** | mims-harvard/TFC-pretraining | Time-Frequency Consistency contrastive head (time+FFT → shared latent) for spectral/regime invariances TS2Vec misses | 8 | **Stitch** |
| **PatchTST** | yuqinie98/PatchTST | Masked-patch transformer SSL; reusable encoder | 8 | Optional |
| **LOBench** | Financial-Simulation-Lab/LOBench | 2025 order-book representation benchmark + curated L2 preprocessing/baselines | 7 | **Order-book stitch** |
| **DeepLOB** | zcakhaa/DeepLOB | Canonical CNN-Inception-LSTM L2 encoder; penultimate = compact book embedding | 7 | **Order-book stitch** |
| **MOMENT / Chronos-tiny** | moment-.../amazon-science | Frozen zero-shot embedding channels via `.embed()` (inference-only, cheap CPU) | 7 | Optional |
| disentanglement_lib | google-research | β-VAE idea good but TF1.x stale → reimplement β-VAE in torch only if we want explicitly disentangled market factors | 3 | Skip |

**Stitch:** TS2Vec (OHLCV) + tsai (harness) + TF-C (frequency head) + DeepLOB/LOBench (order-book
branch), fused into one latent the trading net probes. Optional frozen MOMENT/Chronos channels.

## STAGE 2 — Probe & name (read out the self-invented features)
Full report in-thread. No single repo both probes an arbitrary CPU tabular net *and* names features → **stitch 3**.

| Project | Repo | Role | Score | Verdict |
|---|---|---|---|---|
| **Captum** | pytorch/captum | Backbone: activation hooks → per-neuron activations, NeuronConductance/attribution, max-activating inputs, built-in **TCAV**; native tabular/time-series, CPU | 10 | **Core** |
| **dictionary_learning** | saprmarks/dictionary_learning | Sparse autoencoder on hidden activations → cracks polysemantic units into **monosemantic** dictionary features (the "self-invented feature" readout); lightest SAE lib, feed activations directly | 8 | **Stitch** |
| **delphi** | EleutherAI/delphi | Auto-interp: feed each feature's max-activating examples to our 12-provider brain LLM → generate + **score** a human-readable concept name | 7 | **Stitch** |
| OpenAI neuron-explainer | openai/automated-interpretability | Archived, but the generate→simulate→score naming recipe is the reference to copy | 7 | Adapt |
| SAELens | jbloomAus/SAELens | Heavier SAE alt with feature dashboards if we want richer viz | 7 | Fallback |
| SHAP | shap/shap | Input-attribution fallback ("which trade columns drove this") | 6 | Fallback |
| lucent / NetDissect / MAIA / tcav | — | Image-only, stale, or GPU-bound | ≤4 | Skip |

**Stitch:** Captum (probe) + dictionary_learning (monosemantic SAE) + delphi/neuron-explainer (LLM naming).

## STAGE 3 — Concept-space manifold visualization (see it, like the video)
Full report: `research/manifold-concept-space-viz-oss.md`.

| Project | Repo | Role | Score | Verdict |
|---|---|---|---|---|
| **UMAP (densMAP)** | lmcinnes/umap | Reducer; `densmap=True` = "perception space collapsing into dense concept blobs" visual; `transform()` streams live states into a fixed embedding | 9 | **Core reducer** |
| **HDBSCAN** | scikit-learn-contrib/hdbscan | Auto-detects #concept clusters, noise labels, soft membership for glow/opacity | 9 | **Core clusterer** |
| **regl-scatterplot** | flekschas/regl-scatterplot | WebGL scatter (20M pts, lasso, transitions) fed `{x,y,clusterId,prob}` for the React dashboard | 8 | **Core renderer** |
| PaCMAP / LocalMAP | YingfanWang/PaCMAP | Drop-in reducer for maximally separated clusters | 8 | Alt |
| openTSNE | pavlin-policar/openTSNE | `transform()` to embed new pts into ref space (streaming) | 8 | Alt |
| datamapplot | TutteInstitute/datamapplot | One-shot: UMAP coords + auto-labeling + WebGL HTML export (fastest ship) | 8 | Fast path |
| scikit-dimension | j-bac/scikit-dimension | Honest scalar of the "collapse" (intrinsic dimension) | 6 | Optional |

**Stitch:** UMAP-densMAP + HDBSCAN + regl-scatterplot (or datamapplot for a fast first cut).

---

## Proposed module layout (to build AFTER user's model list arrives)
- `trading/brain/discovery/encoders.py` — Stage-1 SSL encoders (TS2Vec/tsai/TF-C/DeepLOB) → fused latent
- `trading/brain/discovery/probe.py` — Stage-2 Captum hooks + dictionary_learning SAE
- `trading/brain/discovery/namer.py` — Stage-2 LLM auto-naming via `core/llm.py` failover (delphi recipe)
- `trading/brain/discovery/manifold.py` — Stage-3 UMAP+HDBSCAN → coords for the panel
- `trading/brain/discovery/engine.py` — orchestrator + per-feature `lane` flag (experiment vs validated)
- `dashboard/` route `/api/trading/brain/discovery` + `ConceptSpacePanel.jsx` (manifold + discovered-feature list)
- `tests/test_concept_discovery.py`

## Open questions to resolve with the user's list
1. Which of the user's listed models replace/augment the Stage-1 encoders above.
2. Whether existing 320+ nodes act as the *downstream* consumer of discovered features (likely yes)
   or whether the user wants a fresh deep MLP as in the image (8-layer SELF-LEARN).
3. Compute budget for nightly SSL pretraining vs frozen-encoder inference only.

**Deps to install when we start (ask-to-install):** torch (CPU) already present; `ts2vec` (vendor),
`tsai`, `captum`, `dictionary_learning` (vendor), `umap-learn`, `hdbscan`. JS: `regl-scatterplot`.
