# vendor/ — in-tree vendored OSS source (vendor-first rule)

Per the project's **vendor-first** rule: reuse real project code by copying its source
into this directory and making only minor edits to fit our flow — heavy logic comes from
the original project, our code is the glue. License is no obstacle (private, non-published).

**The practical boundary (honest):**
- **Vendored here** = pure-Python projects we can run + edit in-tree.
- **pip-installed instead** = compiled / JIT / framework libs that cannot be vendored sanely:
  TA-Lib (C), STUMPY & vectorbt (Numba), hmmlearn/scikit-learn (Cython), River, DEAP,
  LanceDB, mem0, (PyTorch/FinRL, Qlib — Qlib also has no py3.13 wheel). These are documented
  in `trading-execution-blueprint.md` as "pip — compiled, not vendorable".

## Contents
- **gplearn/** — genetic-programming symbolic regression (pure-Python, MIT), vendored from
  the upstream package. Used by `trading/brain/picking.py` (GPLearnFactorMiner) to *learn* a
  symbolic asset-ranking factor from features→forward-returns. Minor edits: removed the
  upstream `tests/` and `__pycache__`; imports are relative so it runs unchanged from here.
  Import as `from vendor.gplearn.genetic import SymbolicRegressor`.
