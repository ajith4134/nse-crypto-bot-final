# Trainable Network Architecture — turning 320+ model-nodes into a real, learning "neural network"

> **What this is.** A design + phased build plan to convert the current *pile* of ~320
> ML-model nodes (rendered as two dense columns, almost no real wiring) into a network
> that genuinely **trains end-to-end like a neural network** — forward → loss →
> backward → optimize → iterate — with the Phase-3 router as the wiring mechanism,
> **dynamic (non-fixed) inputs/outputs**, and a **grow/prune "active-subnetwork" view**.
> CPU-first, reuse-first, behind `NodeProtocol`. Grounded in 5 deep-research passes
> (papers + live GitHub, 2026-06-27). **No code yet — this is the plan to approve.**

---

## 0. The problem, stated precisely

A real neural network learns by: **forward** (data through weighted connections) → **loss**
(gap vs truth) → **backprop** (error flows back, credit assigned to each weight) →
**optimize** (gradient descent updates weights) → **iterate** (epochs). Today our system
has ~320 full ML models as "nodes" but they are a **catalog**, not a network: per head we
fit every node, average/meta-combine once, done. No depth that learns, no trained wiring,
no error signal shaping the graph.

**The hard obstacle:** most nodes (XGBoost, RandomForest, HMM, kNN, GARCH, …) are
**non-differentiable** — you cannot backprop through them. So "make it a real neural
network" can NOT mean naive backprop through the nodes. The research gives a precise,
buildable answer instead.

---

## 1. The key insight (what makes this possible)

**A node is a neuron; the *connections* are what we train.** Mixture-of-Experts output is a
differentiable weighted sum of expert outputs:

```
            y = Σ_i  g_i(x) · e_i(x)
                 └gate┘  └ frozen node output ┘
```

The gradient to the gate is `∂L/∂θ = Σ_i (∂L/∂y)·e_i·(∂g_i/∂θ)`. The node output `e_i`
enters only as a **multiplicative constant** — **backprop never needs `∂e_i`**. So the
nodes can be non-differentiable black boxes that merely *emit numbers*; the **gate /
connection weights are fully differentiable and trained by real gradient descent.** That is
a literal forward→loss→backprop→optimize→iterate loop — exactly what the user asked for —
run on the *wiring*, not on the nodes.

This splits training into **two clean tiers**:

| Tier | What it trains | How | Differentiable? |
|---|---|---|---|
| **A. Wiring** | gate/router/combiner weights (the "connections") | real backprop + Adam (PyTorch-CPU) | ✅ yes |
| **B. Nodes** | each model-node itself | its own native `fit()` on a (possibly propagated) target | ❌ no — native trainer |
| **C. Structure** | which edges exist, depth, width | grow/prune + gradient-free search | discrete |

Optional advanced bridge between A and B: **target propagation** (give each node-layer a
*target* instead of a gradient) — see §6.4.

---

## 2. Recommended architecture — "Deep Gated Model-Graph" (DGMG)

A deep, **grown**, **gated** cascade of frozen model-nodes, trained by a hybrid loop.
Recommended because it is the only design that (a) gives a true NN training loop on the
wiring, (b) needs nothing differentiable from the nodes, (c) is CPU-first and ~80%
assembled from mature OSS, and (d) yields the grow/prune active-subnetwork view requested.

```
        RAW FEATURES x  ───────────────────────────────┐ (skip connection, re-fed each layer)
            │                                           │
   ┌────────▼─────────┐  activations a¹                 │
   │ LAYER 1: subset of│ ── node outputs ──┐            │
   │ frozen model-nodes│   (OOF at train)  │            │
   └──────────────────┘                    │            │
                          ┌────────────────▼─────────┐  │
                          │ GATE¹  softmax(W¹·x)      │◄─┘   ← BACKPROP trains W¹
                          │ top-k sparse + noisy +    │       (load-balance aux loss
                          │ load-balance aux loss     │        prevents collapse onto
                          └────────────┬──────────────┘        a few of the 320 nodes)
                          combined z¹ = Σ g·a¹
            │  concat(z¹, x)  ─────────────────────────┐ (skip)
   ┌────────▼─────────┐                                │
   │ LAYER 2 nodes    │ ── a² ──┐                       │
   └──────────────────┘         │                       │
                          ┌──────▼───────┐◄─────────────┘   ← BACKPROP trains W²
                          │ GATE²        │
                          └──────┬───────┘
                          ...grow more layers while validation ↑ (Deep-Forest rule)...
                                 │
                       ┌─────────▼──────────┐
                       │ OUTPUT HEADS (many) │  direction/regime/magnitude/...
                       └─────────┬──────────┘
                                 ▼
                               LOSS  ──► ∇ (gates) + native-fit (nodes) + grow/prune (structure)
```

**Mapping onto the neural-network training loop (the user's diagram):**

| NN concept | DGMG realization |
|---|---|
| neuron | a frozen model-node (XGBoost, ESN, HMM, …) emitting a score/proba vector |
| activation | a node's output on the current input |
| weight / connection | a **differentiable gate weight** `g_i(x)` (per layer, per head) |
| bias / skip | original features re-fed to every layer (AutoGluon-style skip connection) |
| forward propagation | raw → layer nodes → gate-combine → next layer → heads |
| loss | per-head task loss (we already have `score_head` / golden eval) |
| backpropagation | gradient through the **gates** (Tier A); **target-propagation** to nodes (Tier B, optional) |
| optimization | Adam on gate weights; native `fit()` + Caruana/L1 selection for nodes |
| epochs / iteration | epochs over gate training; **outer loop grows depth + prunes** to the active subnetwork |

---

## 3. The three legs — and why no one has combined them (our novelty)

The prior-art scan is decisive: **every existing system has one or two legs; none has all
three CPU-first over heterogeneous model-nodes.** That intersection is the project's genuine
contribution.

| Leg | Best reuse (mature OSS) | Maps to |
|---|---|---|
| **1. Multi-layer stacking** (depth, skip connections, leakage-free) | **AutoGluon** internals (`num_stack_levels`, bagged OOF), `sklearn StackingClassifier(cv='prefit')`, **Deep-Forest/DF21** | the cascade layers |
| **2. Learned gate/router** (trained wiring) | **MoE** sparse top-k + Switch load-balance aux-loss + noisy gating (`lucidrains/soft-moe`, `st-moe-pytorch`); **DESlib** META-DES (classical learned competence gate); *our Phase-3 routers already start this* | GATEᵏ |
| **3. Grow / prune → active subnetwork** | **Deep-Forest** validation-plateau layer growth; **Caruana** greedy selection (already in our `routing_advanced.py`); DARTS α-on-edges → prune; **NEAT-Python** topology evolution | depth growth + the prune view |

**Confirmed whitespace (research, verbatim conclusion):** *"No system unifies heterogeneous
ML nodes + multi-layer graph + a learned controller + grow/prune, CPU-first."* Closest
cousins to study: **GPTSwarm** (RL optimizes graph edge-probabilities — nearest "learn the
wiring"), **Routing Networks** (ICLR'18 — per-input composed sub-network; *read its
failure-modes paper*), **MoErging survey** (routing among many heterogeneous post-hoc
experts), **AdaNet** (adaptively grows an ensemble with guarantees).

---

## 4. Dynamic (non-fixed) inputs & outputs

Today node I/O widths are effectively fixed per head. To make them dynamic:

- **Per-node projection bus** — each node gets a tiny trainable `Linear(out_dim_i → D)` that
  maps its (any-width) output into a shared latent width `D`, plus a **presence mask** so a
  node can be absent/added without reshaping. (The single most reused trick across NAS,
  MoE, multimodal.)
- **Count-agnostic aggregation** — treat the (variable number of) firing nodes as a *set*:
  **Set-Transformer / Perceiver-IO** pooling → fixed latent, so adding/removing nodes needs
  no rewrite. Order-independent, linear cost.
- **Name-keyed feature bus** — producers emit named outputs; consumers subscribe by name
  (Hamilton/Feast pattern). Decouples producer/consumer widths entirely.
- **NaN-superset fallback (pragmatic)** — union all features into a wide vector, leave
  absent ones NaN; gradient-boosting nodes route NaNs natively. Zero infra.

Result: a node may take raw features, *other nodes' outputs*, or both; new nodes plug in
without fixed shapes — the structure learner (§6.5) decides who connects to whom.

---

## 5. Reuse-first dependency shortlist (all CPU, permissive licenses)

| Need | Library | Note |
|---|---|---|
| Differentiable gate / backprop | **PyTorch (CPU)** — already a project dep | tiny gate tensors; ms/epoch |
| Gate patterns | `lucidrains/soft-moe-pytorch`, `st-moe-pytorch` | borrow combine + load-balance/z-loss |
| Deep cascade reference | **`deep-forest` (DF21)** | CPU, sklearn, plateau growth |
| Classical learned routing | **DESlib** (already installed) | META-DES competence gate |
| Static combiner / prune | **Caruana** (already in `routing_advanced.py`) | grow/prune the combiner |
| Dynamic I/O pooling | **Set-Transformer** (~50 lines) / `perceiver-pytorch` | count-agnostic fusion |
| Gradient-free topology (optional) | **NEAT-Python**, **Nevergrad** | evolve wiring/depth when grad-free needed |
| Per-input dynamic active set | Expert-Choice MoE (2202.09368); DESlib DFP (installed); RigL/SET dynamic-sparse | active subnetwork per query, not static prune |
| Dashboard graph viz | **sigma.js + graphology** (Leiden + ForceAtlas2, WebGL) | community layout + semantic zoom + firing-path animation |
| Execution at scale (later) | **Ray** actors | runtime rewiring of stateful nodes |

Items needing install when we build: `torch` (confirm CPU build), `deep-forest`,
`set_transformer`/`perceiver-pytorch`, optionally `neat-python`/`nevergrad`. **Ask before
installing**, per project rule.

---

## 6. Training algorithm (the loop, in detail)

**6.1 Forward.** `x → Layer1 nodes (OOF preds at train time) → project to width D → GATE¹
(softmax/top-k) → z¹ = Σ g·a¹ → concat(z¹, x) → Layer2 nodes → … → heads → ŷ`.

**6.2 Loss.** Per-head task loss (cross-entropy / MSE) via existing `score_head`; sum across
heads. Add the **MoE load-balance aux loss** so the gate spreads usage across the 320 (not
collapse onto `rf100`).

**6.3 Backward — Tier A (gates).** Real backprop in PyTorch through the differentiable gates
only (node outputs are detached constants). Adam updates the connection weights. This is the
genuine NN loop.

**6.4 Backward — Tier B (nodes), two options.**
- *Pragmatic (start here):* nodes are trained by their **own `fit()`** on leakage-free **OOF**
  targets (stacking) or **residual** targets (forward-stagewise/boosting). No gradients
  needed; this is the proven, CPU-cheap path.
- *Advanced (upgrade):* **mGBDT target propagation** — pair each node-layer with a learned
  inverse map; push *targets* down the stack (only the top loss step uses a derivative),
  stabilized with **Difference-Target-Propagation**'s correction term. Gives the nodes a true
  backward learning signal across layers.

**6.5 Optimize structure (Tier C).** Outer loop:
- **Grow depth** — add a layer while held-out score improves (Deep-Forest plateau rule).
- **Prune** — drop nodes whose learned gate weight ≈ 0 (lottery-ticket / Caruana / L1) →
  the **active subnetwork**.
- **Search wiring** (optional) — DARTS α-on-edges (differentiable) for the gate, or
  NEAT/Nevergrad/RL-bandit (gradient-free) for discrete node→node edges.

**6.6 Iterate.** Epochs over gates; periodic node refit; outer grow/prune until the active
subnetwork stabilizes.

---

## 7. The active subnetwork — better than static pruning (dynamic, per-input)

Static one-shot pruning (delete low-weight nodes, keep a fixed set) is the **weakest**
option — it (1) permanently deletes capacity, (2) fixes the active set regardless of input
even though different nodes are competent on different queries, and (3) commits irreversibly
from one noisy importance estimate. The research says replace it with a **dynamic per-input
active subnetwork**:

**Learning mechanism (recommended): sparse top-k MoE with per-input routing.**
- All 320 nodes stay permanently available; the gate fires only the **top-k per input** —
  the active subnetwork is chosen **per query**, not frozen. A node useless on average but
  expert on 2% of inputs is preserved and fired exactly when needed.
- **Expert-Choice routing** (arXiv:2202.09368) — each node picks which inputs it handles
  (capacity factor C) → perfect load balance by construction, variable compute per input.
  CPU-ideal: only k of 320 nodes execute per query (true conditional compute).
- Make it **hierarchical** over **Leiden clusters** (§A5/B1) — top gate picks a competence
  cluster, sub-gate picks within it: cuts 320-way routing to ~(#clusters + cluster-size).
- **Quick no-retrain win:** DESlib DES + DFP (already installed) gives per-query competence
  selection over the existing nodes with zero architecture change.
- Complementary refinements: **dynamic sparse training** (RigL/SET — grow *and* prune edges
  continuously, so wrong early deletions are reversible), and **soft gates** (L0 / movement
  pruning / entmax — importance learned end-to-end against the loss, no hand-set threshold).

**Visualization (recommended): sigma.js + graphology.** One WebGL library covers both
rendering (scales past 1000 nodes) and the graph algorithms:
- **Leiden communities + ForceAtlas2 + edge bundling** — turns the two-column mess into
  spatially-separated competence clusters (the *same* clusters the hierarchical router uses).
- **Semantic zoom** — clusters render as super-nodes, expand on click (focus+context).
- **Animated per-input firing path** — on each sample, highlight only the nodes that fired
  and flow the active edges. This is the honest, dynamic counterpart to per-input routing —
  it shows the *real active subnetwork changing per query*, which static highlighting cannot.

**One-line pairing:** route per input with Expert-Choice MoE over Leiden-clustered nodes, and
render it in sigma.js as grouped communities with a live firing-path animation — replacing
both the static prune *and* the two-column dashboard at once. Honors the **honest-wiring**
rule (every edge shown is a real trained connection).

---

## 8. Risks & mitigations (from the research)

| Risk | Mitigation |
|---|---|
| **Routing collapse / router-node co-adaptation** (documented failure of learned routers over module pools) | Switch **load-balance aux loss** + **noisy gating**; or EM-style trainer (Modular Networks) instead of naive RL |
| **Overfitting with 320 nodes** | **Out-of-fold predictions mandatory** at every layer; L1/Caruana sparsity |
| **Diminishing returns past ~dozens of experts** (TabM) | prune to a diverse active subset; diversity-aware selection |
| **Gated net may not beat tuned GBDT** (Grinsztajn bar; frozen-heterogeneous gating is an *unproven* hypothesis) | benchmark honestly vs tuned XGBoost/CatBoost, not a strawman; keep Caruana static combiner as the safe fallback |
| Deep stacks may not help past 1–2 layers on our data | grow only while validation improves; report depth honestly |

---

## 9. Phased build plan (proposed; CPU-first, reuse-first, behind `NodeProtocol`)

- **P3.5 — Differentiable gate (1 layer).** A `GatedLayerNode`: PyTorch-CPU softmax/top-k gate
  over frozen node outputs, trained by backprop with load-balance aux loss. Proves the real
  NN loop on the wiring. Benchmark vs stacking/Caruana + tuned XGBoost.
- **P3.6 — Deep cascade + skip.** Stack gated layers (Deep-Forest growth, OOF, skip
  connections); grow depth by validation. This is the "deep network."
- **P3.7 — Dynamic I/O bus.** Per-node projection + presence mask + Set-Transformer pooling;
  name-keyed bus so I/O is non-fixed and nodes plug in freely.
- **P3.8 — Dynamic active-subnetwork + dashboard.** Per-input top-k / Expert-Choice routing
  (active set chosen per query, not statically pruned), optionally hierarchical over Leiden
  clusters; render in **sigma.js + graphology** (Leiden communities + ForceAtlas2 + semantic
  zoom + animated per-input firing path) — fixes the two-column mess with a live network.
- **P3.9 — Structure search (optional).** DARTS α-edges and/or NEAT/RL controller for learned
  wiring/depth; budget for routing-collapse mitigations.
- **P4 bridge — Target propagation (advanced).** mGBDT + Difference-TP to give nodes a true
  backward signal; ties into the Phase-4 brain as the meta-controller running this loop.

Each phase ships something working, reuses mature OSS, and defers the hardest research
(target-prop, learned topology) until the trainable substrate exists.

---

## 10. Recommendation

Build **DGMG** starting at **P3.5 (the differentiable gate)** — it is the smallest step that
delivers a genuine neural-network training loop over the existing nodes, is CPU-cheap, reuses
PyTorch + MoE patterns, and slots directly onto the Phase-3 routers already built. Treat
"gated stacking over frozen heterogeneous experts beats tuned GBDT" as a **hypothesis to
benchmark honestly**, with the Caruana static combiner as the always-available safe fallback.
This is, per the prior-art scan, **genuinely novel** — no public system unifies these legs.

*Sources: 5 deep-research passes (deep-forest/target-prop; MoE-over-frozen-experts;
learned/dynamic structure; gradient-free training; prior-art projects), papers + live GitHub
verified 2026-06-27. Key reads: MoE (arXiv:1701.06538), Switch (2101.03961), mGBDT
(1806.00007), Difference-TP (1412.7525), Deep Forest (IJCAI'17), Routing Networks
(1711.01239 + failure modes 1904.12774), MoErging survey (2408.07057), TabM (2410.24210),
GG-MoE-tabular (2502.03608), Grinsztajn (2207.08815).*
