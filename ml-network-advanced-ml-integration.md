# Including ALL Ultra-Advanced ML Algorithms — design + catalog (2026)

> Goal: a scalable WAY to fold any ultra-advanced (CPU-friendly) ML algorithm
> into the node-graph, plus the catalog of algorithms to load. From 3 parallel
> GitHub/PyPI research passes + a study of how sklearn/sktime/PyCaret/AutoGluon/
> River/OpenML expose many algorithms behind one interface.

## THE WAY — declarative registry + one universal adapter
Don't hand-code each algorithm. Define **one `AlgoSpec` per algorithm (a single
decorated dataclass line)** and a single **`UniversalNode`** that turns any spec
into a `NodeProtocol` node. Adding an ultra-advanced algorithm = one registry line.

Design = AutoGluon registry-keys + PyCaret container-fields + sklearn duck-typing/Tags
+ sktime input-coercion + OpenML version/license pinning:

```python
@register
@dataclass(frozen=True)
class AlgoSpec:
    id: str                         # "tabpfn"
    import_path: str                # "tabpfn.TabPFNClassifier"
    tasks: frozenset[str]           # {"binary","multiclass","regression"}
    fixed_args: dict = {}           # always-passed kwargs
    search_space: dict = {}         # typed Real/Int/Categorical -> Optuna can tune ANY node
    probabilistic: bool | None = None   # None = auto-introspect hasattr(predict_proba)
    needs_gpu: bool = False; license: str = ""; priority: int = 0
    fit_method="fit"; proba_method="predict_proba"; point_method="predict"  # non-sklearn overrides

class UniversalNode(BaseNode):      # built from ANY spec, task-gated, task-aware predict_output
    # fit/predict/predict_proba/predict_output dispatch via the spec's method names;
    # coerce(X) adapts input; probabilistic auto-detected or forced by spec.

def build_nodes(task):              # the brain queries the registry declaratively
    return [UniversalNode(s, task) for s in REGISTRY.values()
            if task in s.tasks and not s.needs_gpu]   # never-skip: only GPU excluded
```
Benefits: (1) **task-gated** (`tasks` asserted, brain filters by task); (2) **probabilistic vs point** auto-routed in `predict_output`; (3) **typed search_space** → Optuna/AutoSampler tunes any node generically; (4) **method-name overrides** absorb non-sklearn estimators (LightAutoML `fit_predict`, River `learn_one`, pyoperon) with zero special-casing; (5) **license/version pinned** so the brain avoids LGPL/proprietary/GPU nodes at build time. Existing `SklearnNode`/`SklearnRegressorNode` become the default UniversalNode path.

## CATALOG — ultra-advanced CPU algorithms to load into the registry
### Tier A — build first (mature, CPU, permissive, distinct)
| Algorithm | pip | What's advanced | License |
|---|---|---|---|
| **imodels** | `imodels` | RuleFit/FIGS/GOSDT/TreeGAM/Bayesian-rules — many advanced interpretable models in one | MIT |
| **quantile-forest** | `quantile-forest` | quantile regression forests — full conditional distribution/intervals | Apache-2.0 |
| **deep-forest** | `deep-forest` | gcForest — deep cascade of forests, no backprop | open |
| **XGBoostLSS / LightGBMLSS** | `xgboostlss`/`lightgbmlss` | distributional boosting (predict full distribution) | Apache-2.0 |
| **Tsetlin Machine** | `tmu` | propositional-logic clause learning, integer-only, novel paradigm | MIT |
| **wittgenstein** | `wittgenstein` | RIPPER/IREP rule induction → human-readable rules | MIT |
| **metric-learn** | `metric-learn` | LMNN/NCA/ITML metric learning (boosts kNN/few-shot) | MIT |
| **hyppo** | `hyppo` | MMD / kernel two-sample & independence tests (drift/structure) | MIT-0 |
| **LCE** | `lcensemble` | local cascade ensemble (RF+XGBoost hybrid) | Apache-2.0 |
| **RotationForest** | `aeon` (have) | PCA-rotated subspace forest | BSD-3 |
| **mljar-supervised** | `mljar-supervised` | full AutoML stacking node | MIT |
| **pyoperon** | `pyoperon` | C++ GP symbolic regression (SRBench accuracy leader) | MIT |
| sklearn built-ins (no dep) | — | NearestCentroid, BayesianGaussianMixture (DP/variational), KernelDensity, Label{Propagation,Spreading}, SelfTraining, QuantileRegressor | BSD-3 |

### Tier B — high value, thin adapter / heavier / license-flag
| Algorithm | pip | Note |
|---|---|---|
| **TabPFN** | `tabpfn` | tabular FOUNDATION model; CPU-OK small data; ⚠ weights NON-COMMERCIAL |
| **stochtree** / **pymc-bart** | `stochtree`/`pymc-bart` | Bayesian additive regression trees (non-sklearn → adapter) |
| **scikit-survival** | `scikit-survival` | RSF / gradient-boosted survival; ⚠ GPL-3.0 |
| **scikit-activeml** / **modAL** | `scikit-activeml` | active-learning query strategies |
| **Optuna** | `optuna` | HPO backbone for the search_space tuning (not a node) |
| **TPOT** | `tpot` | GP pipeline AutoML; ⚠ LGPL (depend, don't vendor) |
| **LightAutoML** | `lightautoml` | AutoML presets (fit_predict → adapter) |
| **pymfe** | `pymfe` | dataset meta-features → feed the algorithm-selecting brain (selection input, not predictor) |

### Excluded (not CPU / not OSS / dead) — per never-skip these are GPU/legal/dead blocks, not choices
- **GPU-favored** (defer to a future GPU tier): TabNet, GRANDE, NODE, FT-Transformer, falkon, GPflow/GPyTorch, learn2learn.
- **Proprietary / non-OSI**: feyn/QLattice (EULA), alibi-detect (BSL-1.1).
- **LLM-API / no code**: AlphaEvolve (no code), OpenEvolve & AI-Scientist (LLM+GPU).
- **Dead**: auto-sklearn (no py3.13), EvalML (stale), mlens/bartpy/skope-rules/nflows. H2O needs JVM.

## PHASED BUILD PLAN
1. **Build the substrate**: `core/algo_registry.py` (`AlgoSpec` + `@register` + `REGISTRY`) and a generic `UniversalNode` in `nodes/` (extends current SklearnNode). Wire `build_nodes(task)` into the pool. (Refactor existing sklearn nodes onto it incrementally — non-breaking.)
2. **Populate Tier A** (one spec line each) → instantly ~12 advanced node families.
3. **Tier B** with thin adapters (TabPFN, BART, survival, AutoML, LightAutoML) + Optuna tuning hook + pymfe meta-features feeding the brain's algorithm selection.
4. Dashboard auto-syncs (registry-driven). Per never-skip, only GPU/proprietary/dead are deferred — all noted.

> Net: the registry+adapter is the durable "way" — the project can absorb ANY
> future ultra-advanced ML algorithm by adding one declarative line.
