# CONVENTIONS — Standing Rules for This Project

> These rules exist to stop the #1 failure mode of agent-built codebases:
> the agent assumes wrong things about existing code, writes new code that
> doesn't fit, and you end up with large files that don't talk to each other
> plus orphaned/dead code. Every coding step MUST follow these.

A one-line banner of the active rules is shown at the top of every reply:
`Rules: prompt-rating | reuse-first | auto-index | enforced-interfaces | secrets-safe | dashboard-sync`

---

## 1. Self-documenting names
- File, class, and function names must describe **what the code does**, so the
  name alone conveys purpose (e.g. `reservoir_node.py`, `class RegimeChangeNode`,
  `def predict_next_close(...)`).
- Each file starts with a 1–2 line module docstring: what it does, its inputs,
  its outputs.

## 2. Auto-generated index (`INDEX.md`) — never hand-edited
- A machine-generated manifest maps **every file → its functions/classes,
  imports, exports, input types, output types, and a 1-line summary**.
- It is regenerated from the code (AST parse) via `make index` and a pre-commit
  hook. **A stale index is worse than none**, so humans/agents never edit it by
  hand — they change the code and regenerate.
- The coding agent reads `INDEX.md` FIRST to get grounded, then opens only the
  specific files it needs. This is also the **context-budget** mechanism — never
  load the whole repo.

## 3. Enforced interfaces, not described ones
- The index *describes* contracts; the type system *enforces* them.
- Every node implements a shared **`NodeProtocol`** (`fit`, `predict`,
  `golden_dataset`, typed `InputSchema`/`OutputSchema` via Pydantic or
  `typing.Protocol`). A node that doesn't conform **fails at import/test time**,
  not after merge. This is what actually prevents "code that doesn't fit."
- Nodes self-register in a **registry**, so wiring cannot be silently wrong.

## 4. Reuse-first / build-only-the-gaps
- Prefer mature OSS (AutoGluon, ReservoirPy, nolds, ruptures, Mem0, Graphiti…).
- Build from scratch ONLY where nothing fits (the node-graph substrate, the
  learned router at depth, the node interface/data bus). See `ml-network-master-plan.md`.
- When editing existing/online code, adapt it to our interface — don't fork blindly.

## 5. No orphans / no dead code (automated)
- CI runs dead-code detection (`vulture`) + an import-graph check. Orphaned files
  or uncalled functions **block the merge**. Don't rely on discipline.

## 6. Dashboard-sync (every node & feature is visible)
- **Every new node, feature, or intelligence/learning capability MUST register a
  dashboard view** when added — nothing ships invisible.
- Dashboard stack: **Web — React + D3/Three.js** (3D node graph, real-time data
  flows, animated learning/accuracy metrics). New additions auto-reflect via a
  registry the dashboard reads.
- **HONEST WIRING (no fake) — load-bearing.** Every node, edge, input, output and
  data-flow shown on the dashboard MUST reflect the REAL architecture, derived
  only from the live registry/`state.json` (real `feature_names`, real per-node
  `input_dim`/`upstream`, real terminal predictors). NEVER fabricate nodes, edges,
  inputs, outputs or flows just to look like a diagram. If a connection is drawn,
  it must be a true data dependency in the project (e.g. feature→node only when
  the node consumes that feature; node→meta only from the real `upstream`;
  node→output only for real terminal predictors). A pretty-but-false graph is
  worse than an ugly-but-true one. Visual layout (layering/animation) is free to
  arrange; the *connectivity it depicts* is not.

## 7. Secrets-safe
- Real API keys live ONLY in a gitignored `.env` (template: `.env.example`),
  loaded via `config.py`. Never commit, print, or store real keys (not in code,
  logs, memory, or commits). Pasted keys are treated as compromised.

## 10. Polyglot for performance (not Python-only)
- The project is **not limited to Python**. Use C, C++, Rust, etc. for any hot
  path where it meaningfully improves speed, latency, memory, or throughput —
  expose it to Python via a clean boundary (CFFI/ctypes, PyO3, subprocess, or a
  small service) so it still slots behind `NodeProtocol`.
- Pure Python stays the default for correctness/iteration; drop to a compiled
  language when profiling shows a real bottleneck (e.g. node training loops,
  distance computations, reservoir state updates).
- Needing a toolchain (gcc/clang/cargo) triggers §9 **ask-to-install** — request it.
- Keep the interface identical so swapping a Python node for a compiled one is invisible to the graph.

## 9. Ask-to-install (dependencies & data)
- When the project would genuinely benefit from a new package, dataset, model, or
  any download, **ask the user to install/provide it** rather than reimplementing
  it in pure stdlib or settling for a weaker existing option.
- Surface: what's needed, why, the exact install command (e.g. `pip install scikit-learn`),
  and the size/cost if notable. The user runs the install (or approves it).
- This refines §4: reuse-first means *use the best mature OSS* — and if it needs
  installing, request the install instead of building a workaround.

## 8. Prompt-quality protocol (workflow rule)
- Every user prompt is rated 1–10; missing info is gathered to reach a 10/10
  before execution. (Enforced by a UserPromptSubmit hook.)

---

### Definition of Done for any coding task
1. Names follow §1; module docstring present.
2. `INDEX.md` regenerated (§2).
3. New node/component conforms to `NodeProtocol` + registered (§3).
4. Reused OSS where possible; new-from-scratch justified (§4).
5. No dead code / orphans (§5 passes CI).
6. Dashboard view registered for any new node/feature (§6).
7. No secrets touched tracked files (§7).
