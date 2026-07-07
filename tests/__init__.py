"""Test package init.

Cap BLAS/OpenMP thread pools for the whole suite BEFORE any test module imports
numpy/scipy/sklearn/hmmlearn. Unbounded, hmmlearn's GaussianHMM.fit (and other BLAS
kernels) oversubscribe every core with 100+ threads that thrash rather than progress —
this turned `MLNB_SKIP_HEAVY=1 python -m unittest discover tests/` into an 80-minute
hang (see nodes/oss_nodes.py HMMRegimeNode; grow-cascade in tests/test_columns.py).
Single-threaded the same work finishes in seconds. Env vars only take effect if set
before the native libs load, hence here in the package __init__. A user-provided value
is respected (never overridden).
"""
import os as _os

for _var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
             "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    _os.environ.setdefault(_var, "1")
