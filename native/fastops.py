"""ctypes wrapper for native hot kernels, with pure-Python fallback.

If native/libfastops.so exists (built via build.sh with gcc/clang) it is used;
otherwise the pure-Python fallback runs. HAVE_NATIVE reports which path is live,
so nodes can transparently use whichever is available (polyglot rule, §10).
"""
from __future__ import annotations

import ctypes
import math
import os
import random

_D = ctypes.POINTER(ctypes.c_double)
_LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "libfastops.so")
_lib = None
if os.path.exists(_LIB):
    try:
        _lib = ctypes.CDLL(_LIB)
        _lib.sqdists.argtypes = [_D, ctypes.c_int, ctypes.c_int, _D, _D]
        _lib.sqdists.restype = None
        _lib.logreg_train.argtypes = [_D, _D, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                      ctypes.c_double, _D, _D]
        _lib.logreg_train.restype = None
        _lib.mlp_train.argtypes = [_D, _D, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_double, _D, _D, _D, _D]
        _lib.mlp_train.restype = None
    except (OSError, AttributeError):
        _lib = None

HAVE_NATIVE = _lib is not None


def _flat(rows):
    return [v for r in rows for v in r]


def logreg_train(Xs, y, lr, epochs):
    """Train logistic regression; returns (w, b). Native if available."""
    n, d = len(Xs), len(Xs[0])
    if _lib:
        X = (ctypes.c_double * (n * d))(*_flat(Xs))
        cy = (ctypes.c_double * n)(*[float(v) for v in y])
        w = (ctypes.c_double * d)()
        b = ctypes.c_double(0.0)
        _lib.logreg_train(X, cy, n, d, epochs, lr, w, ctypes.byref(b))
        return list(w), b.value
    w, b = [0.0] * d, 0.0                                   # fallback
    for _ in range(epochs):
        gw, gb = [0.0] * d, 0.0
        for xi, yi in zip(Xs, y):
            p = 1.0 / (1.0 + math.exp(-(sum(w[j] * xi[j] for j in range(d)) + b)))
            e = p - yi
            for j in range(d):
                gw[j] += e * xi[j]
            gb += e
        w = [w[j] - lr * gw[j] / n for j in range(d)]
        b -= lr * gb / n
    return w, b


def mlp_train(Xs, y, H, lr, epochs, seed):
    """Train a 1-hidden-layer MLP; returns (W1_flat, b1, W2, b2). Native if available."""
    n, d = len(Xs), len(Xs[0])
    rng = random.Random(seed)
    W1 = [rng.uniform(-0.5, 0.5) for _ in range(H * d)]     # row-major H x d
    b1 = [0.0] * H
    W2 = [rng.uniform(-0.5, 0.5) for _ in range(H)]
    b2 = 0.0
    if _lib:
        X = (ctypes.c_double * (n * d))(*_flat(Xs))
        cy = (ctypes.c_double * n)(*[float(v) for v in y])
        cW1 = (ctypes.c_double * (H * d))(*W1)
        cb1 = (ctypes.c_double * H)(*b1)
        cW2 = (ctypes.c_double * H)(*W2)
        cb2 = ctypes.c_double(b2)
        _lib.mlp_train(X, cy, n, d, H, epochs, lr, cW1, cb1, cW2, ctypes.byref(cb2))
        return list(cW1), list(cb1), list(cW2), cb2.value
    for _ in range(epochs):                                 # fallback
        gW1 = [0.0] * (H * d)
        gb1 = [0.0] * H
        gW2 = [0.0] * H
        gb2 = 0.0
        for xi, yi in zip(Xs, y):
            ha = [math.tanh(sum(W1[j * d + k] * xi[k] for k in range(d)) + b1[j])
                  for j in range(H)]
            o = 1.0 / (1.0 + math.exp(-(sum(W2[j] * ha[j] for j in range(H)) + b2)))
            dd = o - yi
            gb2 += dd
            for j in range(H):
                gW2[j] += dd * ha[j]
                dh = dd * W2[j] * (1 - ha[j] ** 2)
                gb1[j] += dh
                for k in range(d):
                    gW1[j * d + k] += dh * xi[k]
        b2 -= lr * gb2 / n
        for j in range(H):
            W2[j] -= lr * gW2[j] / n
            b1[j] -= lr * gb1[j] / n
            for k in range(d):
                W1[j * d + k] -= lr * gW1[j * d + k] / n
    return W1, b1, W2, b2


def sqdists(X: list[list[float]], q: list[float]) -> list[float]:
    """Squared Euclidean distance from q to every row of X (one-shot, marshals X)."""
    n, d = len(X), len(q)
    if _lib:
        flat = (ctypes.c_double * (n * d))(*[v for row in X for v in row])
        cq = (ctypes.c_double * d)(*q)
        out = (ctypes.c_double * n)()
        _lib.sqdists(flat, n, d, cq, out)
        return list(out)
    return [sum((row[j] - q[j]) ** 2 for j in range(d)) for row in X]  # fallback


def prepare(X: list[list[float]]):
    """Marshal a dataset into reusable C memory ONCE. Returns an opaque handle
    used by sqdists_prepared (avoids re-flattening X on every query)."""
    n = len(X)
    d = len(X[0]) if n else 0
    if _lib:
        flat = (ctypes.c_double * (n * d))(*[v for row in X for v in row])
        out = (ctypes.c_double * n)()
        return ("native", flat, out, n, d)
    return ("py", X, None, n, d)


def sqdists_prepared(prepared, q: list[float]) -> list[float]:
    """Distances from q to a prepared dataset; marshals only q (d floats)."""
    kind, buf, out, n, d = prepared
    if kind == "native":
        cq = (ctypes.c_double * d)(*q)
        _lib.sqdists(buf, n, d, cq, out)
        return list(out)
    return [sum((row[j] - q[j]) ** 2 for j in range(d)) for row in buf]


if __name__ == "__main__":
    import time as _t
    n, d = 4000, 12
    X = [[(i * 7 + j) % 13 * 0.1 for j in range(d)] for i in range(n)]
    q = [0.5] * d
    t0 = _t.time()
    for _ in range(200):
        sqdists(X, q)
    print(f"native={HAVE_NATIVE}  200x sqdists({n}x{d}) in {_t.time()-t0:.3f}s")
