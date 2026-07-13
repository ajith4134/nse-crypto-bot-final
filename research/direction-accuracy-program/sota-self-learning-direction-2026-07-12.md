# SOTA: Self-Learning Market-Direction Predictor (learns from its own wrong calls)
**Date:** 2026-07-12 · **Scope:** CPU-only crypto/NSE trading brain · **For:** Direction Accuracy Program (Pillar 27)
**Constraint recap:** CPU-only, ONLINE/incremental from streaming closed-trade outcomes, calibrated, regime-shift robust, ~seconds/symbol.

## TL;DR
Our existing stack (`truth_ledger.py` + `meta_labeler.py`) already implements the *right idea* — López de Prado meta-labeling with isotonic calibration and an honesty gate — but the meta-learner is **batch-retrained every 6h (LightGBM)**, so it is not truly online and reacts slowly to regime flips. The highest-capability, lowest-friction upgrade is to add a **River online meta-learner (ARF/SRP + ADWIN)** that runs `learn_one` on every resolved truth-ledger label, keep the LightGBM as a slower "batch oracle," fuse them with **Hedge/multiplicative-weights**, and gate coverage with **crepes/MAPIE conformal abstention**. Everything except Hedge is *already installed in `.venv`*.

**Installed already (verified in `.venv`):** `river 0.25.0`, `lightgbm 4.6.0`, `crepes 0.9.1`, `mapie 1.4.1`, `scikit-learn 1.7.2`. `vendor/bocd` already present. Only genuinely new dep proposed: none required (Hedge is ~30 lines) — optional `vowpalwabbit`.

---

## Ranked shortlist (by CAPABILITY, license ignored per project policy)

### 1. River — online streaming classifiers + drift detectors (PRIMARY)
- **Link:** https://github.com/online-ml/river · ~5.9k★ · v0.25.0 (May 2026, actively maintained) · **already installed**.
- **What:** The merged successor to `creme` + `scikit-multiflow`. Native `learn_one`/`predict_proba_one` on dict rows (matches our per-symbol decision dicts). Ships exactly the models we need for "learn from being wrong fast":
  - `forest.ARFClassifier` (Adaptive Random Forest) and `ensemble.SRPClassifier` (Streaming Random Patches) — **each base tree carries its own ADWIN**; when a tree's error distribution shifts, ADWIN triggers and that tree is reset. This is drift-reactive *by construction*, which is precisely our regime-flip requirement.
  - `linear_model.LogisticRegression` (SGD) for a cheap always-on baseline; `drift.ADWIN`/`DDM`/`EDDM` as standalone detectors.
  - `ensemble.ADWINBaggingClassifier`, plus online `BaggingClassifier`/boosting/stacking.
- **Why #1:** true incremental `partial_fit`-style learning, CPU-native (pure-Python dict pipeline, no GPU, sub-ms per row), drift handling is first-class not bolted-on, and it consumes the *same feature dicts* our `meta_labeler._featurize` already builds. Docs: https://riverml.xyz/dev/ (ARF: https://riverml.xyz/dev/api/forest/ARFClassifier/, SRP: https://riverml.xyz/dev/api/ensemble/SRPClassifier/, ADWIN: https://riverml.xyz/dev/api/drift/ADWIN/).

### 2. crepes / MAPIE — conformal abstention (calibrated "don't trade when unsure")
- **Links:** crepes https://github.com/henrikbostrom/crepes (v0.9.1 installed; PMLR paper https://proceedings.mlr.press/v179/bostrom22a/bostrom22a.pdf) · MAPIE https://github.com/scikit-learn-contrib/MAPIE (v1.4.1 installed).
- **What:** Distribution-free coverage guarantees. crepes wraps any classifier into calibrated p-values / prediction sets ("Mondrian"/class-conditional supported). Both now support **binary classification with reject/abstention** (MAPIE risk-control for binary + reject option; crepes reject-option per arXiv 2506.21802 "Classification with Reject Option").
- **Key upgrade for non-stationarity:** **Adaptive Conformal Inference (ACI)** — online conformal that *drops the exchangeability assumption* and re-tunes the significance level from realized coverage error, designed for time series (Zaffran 2022 https://proceedings.mlr.press/v162/zaffran22a/zaffran22a.pdf; multi-step online ACI arXiv 2409.14792). This is the correct calibration layer for a regime-switching market where a static calibration set goes stale.
- **Why #2:** turns the meta-learner's probability into an *honest coverage dial* — "abstain unless P(correct) clears a conformal threshold at target risk α." We already use crepes elsewhere (Pillar 17), so this is a known quantity. Directly replaces the fixed `META_MIN_P` threshold with a self-calibrating one.

### 3. Hedge / Multiplicative-Weights over the lens ensemble (fast "punish the wrong lens")
- **Refs:** Freund–Schapire Hedge / MWU (survey arXiv 1802.02871; notes https://www.cs.cornell.edu/courses/cs6820/2016fa/handouts/mw.pdf). No heavyweight lib needed — ~30 lines; River's `ensemble` weighting can also host it.
- **What:** Maintain a weight per direction *lens* (our `f_orderflow`, `f_vp`, `f_yolo`, `f_direq`, `f_vision`, CORTEX, strategy-library vote, each timeframe). On every resolved outcome, multiplicatively down-weight lenses that were wrong and up-weight those that were right: `w_i *= exp(-η · loss_i)`. Regret-bounded, no distributional assumptions, reacts in *one* observation.
- **Why #3:** This is the literal "learn from being wrong fast" primitive and the principled replacement for the naive `funnel._vote` ("≥2 TFs agree") — instead of counting votes it *weights* them by realized, decaying reliability. Cheap, interpretable, complements the meta-learner (Hedge is reactive/short-memory; the meta-learner is structured/long-memory).

### 4. López de Prado meta-labeling — keep our design, it's SOTA (STAY)
- **Ref impl:** mlfinlab / Hudson & Thames (https://hudsonthames.org/tag/meta-labeling/), `mlfinpy` (https://mlfinpy.readthedocs.io); Meta-Labeling overview https://en.wikipedia.org/wiki/Meta-Labeling.
- **What:** Primary model picks the SIDE; a secondary model predicts P(side correct) and sizes/abstains. Our `meta_labeler.py` already *is* this (LightGBM + isotonic + AUC honesty guard + stacking over all lenses). mlfinlab adds triple-barrier labeling + purged/embargoed CV — worth borrowing the **triple-barrier** idea to enrich truth-ledger labels (path-dependent hit vs. our fixed 15m/1h/4h endpoint check) and **CPCV** to make holdout AUC less optimistic.
- **Why #4:** validates our architecture and offers concrete, drop-in label/CV improvements without a rewrite. Don't replace — enrich.

### 5. Bayesian Online Changepoint Detection (bocd) — regime segmentation trigger (HAVE IT)
- **Have:** `vendor/bocd` already in tree. **What:** Adams–MacKay online changepoint posterior over a chosen signal (e.g., realized-vol or the meta-learner's rolling error). **Why #5:** a complementary, *probabilistic* drift trigger to ADWIN — when bocd's changepoint probability spikes, decay Hedge weights and/or shrink the River learners' effective memory. Use as the "regime clock" that coordinates resets across #1 and #3.

**Considered, ranked lower:** Vowpal Wabbit (https://github.com/VowpalWabbit/vowpal_wabbit) — excellent online SGD + contextual bandits, but a separate C++ runtime/dep and less friction-free than River when our data is already Python dicts; hold as a future *bandit* upgrade for exploration (which lens/strategy to allocate to), not the direction core. scikit-multiflow — superseded by River, don't use.

---

## Least-friction fit onto our existing `truth_ledger` + `meta_labeler`

Our plumbing already does the hard part; the online learners slot into two existing seams:

1. **Feed:** `truth_ledger.tick()` already resolves pending decisions into labeled examples and appends them to `direction_truth_train.jsonl` via `_append_train`. Add a single call there: for each newly-resolved fold, call `online.learn_one(features, correct)`. The feature dict is *identical* to what `meta_labeler._featurize` produces — reuse it verbatim (no train/serve skew, matching the file's existing design rule).
2. **Gate:** `meta_labeler.gate()` returns `{p, allow, advisory, auc}`. Introduce a sibling `online_p_correct()` (River `predict_proba_one`) and fuse batch-LGBM `p` with online-`p` via Hedge weights, then wrap the fused probability in a conformal abstention check (crepes/ACI) to set `allow`. Keep the existing `META_MIN_AUC` honesty guard: the online learner stays *advisory* until its own rolling holdout accuracy clears the bar. Persist River model with `river` + `pickle`/`joblib` exactly like the LightGBM bundle in `load_model()`.
3. **Drift:** run `drift.ADWIN` (or `vendor/bocd`) on the stream of `correct` bits per source/regime; on trigger, log a regime-flip event and let ARF/SRP self-reset (automatic) while Hedge weights decay. This directly attacks the measured pathology (40.3% direction accuracy = invertible anti-signal that nobody could see shift).

No schema changes, no new storage — it rides the existing JSONL + `state.update_json` cross-process-safe path.

## Recommended next-gen design (one paragraph)
Build a **dual-speed, drift-reactive meta-labeler**: keep the current LightGBM+isotonic model as the *slow oracle* (structured, 6h batch, good priors), add a **River `SRPClassifier` (Hoeffding trees + per-tree ADWIN)** as the *fast learner* that does `learn_one` on every truth-ledger-resolved outcome so it tracks regime shift in real time, and combine the two probabilities with a **Hedge/multiplicative-weights** layer that also weights each raw direction lens (order-flow / VP / YOLO / direction-equation / vision / CORTEX / strategy-library / per-timeframe) by its *own* decaying realized hit-rate — this is the principled replacement for `funnel._vote`'s naive "≥2 TFs agree." Wrap the fused P(correct) in an **online conformal (ACI, via crepes)** abstention gate so the engine *skips* rather than takes a low-confidence trade at a chosen risk α, and drive regime resets from **ADWIN + vendored bocd** changepoints. Net effect: the system learns from each wrong call within one-to-a-few observations (Hedge/River), stays well-calibrated and honest about coverage (conformal + existing AUC guard), and never silently rides an inverted anti-signal through a regime flip.

## Exact pip install names
```
# Already in .venv — nothing to install for the core build:
#   river (0.25.0), lightgbm (4.6.0), crepes (0.9.1), mapie (1.4.1), scikit-learn (1.7.2)
# Already vendored: vendor/bocd
pip install river          # online learners + ADWIN/SRP/ARF (present; pin >=0.22)
pip install crepes         # conformal abstention (present)
pip install mapie          # conformal risk-control/reject alt (present)
# Optional / future:
pip install vowpalwabbit   # only if adding a contextual-bandit allocation lane later
# Hedge/MWU: no dependency — ~30 lines, or use river.ensemble weighting.
# Meta-labeling reference (triple-barrier + CPCV ideas to borrow, not required to run):
pip install mlfinpy        # maintained mlfinlab-lineage impl; read for labeling/CV only
```

## Sources
- River: https://github.com/online-ml/river · https://riverml.xyz/dev/ · ARF https://riverml.xyz/dev/api/forest/ARFClassifier/ · SRP https://riverml.xyz/dev/api/ensemble/SRPClassifier/ · ADWIN https://riverml.xyz/dev/api/drift/ADWIN/
- crepes: https://github.com/henrikbostrom/crepes · https://proceedings.mlr.press/v179/bostrom22a/bostrom22a.pdf
- MAPIE: https://github.com/scikit-learn-contrib/MAPIE
- Adaptive Conformal Inference: https://proceedings.mlr.press/v162/zaffran22a/zaffran22a.pdf · https://arxiv.org/abs/2409.14792 · reject-option https://arxiv.org/pdf/2506.21802
- Meta-labeling: https://en.wikipedia.org/wiki/Meta-Labeling · https://hudsonthames.org/tag/meta-labeling/ · https://mlfinpy.readthedocs.io/en/latest/Labelling.html
- Hedge / Multiplicative Weights: https://www.cs.cornell.edu/courses/cs6820/2016fa/handouts/mw.pdf · online-learning survey https://arxiv.org/pdf/1802.02871
- Vowpal Wabbit: https://github.com/VowpalWabbit/vowpal_wabbit
