# Column-MoE / DGMG connection architecture — OSS selection

Goal: connect the 320+ NodeProtocol nodes as **columns** (same function, N implementations),
with **learned/trainable** gates, CPU-first, quality-maximizing, clear+visual, and open to
adding new nodes with no reshaping. Build order: A (intra-column gate) → B (cross-column
router) → C (growing DGMG) → D (brain-as-gate).

## Phase-1 selection (README/signal level, no premature source reading)

| Building block | Project / source | Already here? | Verdict |
|---|---|---|---|
| Gate tensors, autograd, CPU | **PyTorch** | ✅ `.venv` | Use — core substrate for all gates |
| Per-input competence routing (classical) | **DESlib** (KNORA/META-DES) | ✅ `.venv` | Use for optional DES gate + baseline |
| Conformal confidence on outputs | **MAPIE** | ✅ `.venv` | Use for calibrated gate inputs |
| Base experts | sklearn / xgboost / lightgbm | ✅ `.venv` | Already the node backends |
| Sparse-MoE gate + load-balance aux-loss | lucidrains **st-moe-pytorch** / **soft-moe-pytorch** | ❌ | **Do NOT vendor** — built for transformer token routing (seq/embed dims); wrong shape for "frozen scalar-emitting experts". Reuse the *pattern* (Switch-Transformer load-balance loss) in ~30 lines of torch. |
| Plateau-based depth growth | **deep-forest (DF21)** | ❌ | **Do NOT install** — trains its own forests; we only need its plateau *rule*. Reuse rule (~10 lines): add a layer while held-out score improves > eps. |
| Lottery-ticket / L1 pruning | pattern (Frankle & Carbin) | n/a | Implement as L1 on gate weights → prune ~0 gates. |

## Recommendation
Single "winner" is **PyTorch + DESlib + MAPIE (all installed)**; the MoE-gate and growth/prune
logic are small algorithmic patterns with no drop-in lib matching our frozen-expert shape, so we
implement them directly (this is real torch, not a stdlib workaround). If the user prefers a
packaged MoE later, `st-moe-pytorch` can be pip-installed and swapped behind the same gate API.

## Why not end-to-end differentiable through the nodes
Nodes (XGBoost/HMM/reservoir/symbolic) are non-differentiable black boxes. Only the **gates/edges**
are differentiable — DGMG Tier A: nodes trained by native `fit()`, gate weights trained by Adam.
This is what keeps it CPU-cheap and lets any new node join without gradient plumbing.
