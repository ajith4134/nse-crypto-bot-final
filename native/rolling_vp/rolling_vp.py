"""native/rolling_vp — numba-JIT rolling Volume Profile kernel (Pillar 9 hot path).

`trading.strategy.library.features_ext._rolling_vp` calls `volume_profile()` once per bar over a
trailing window, in the per-symbol trade decision (144 symbols/cycle). cProfile pinned it at ~1.25s
per symbol — the funnel EXECUTE bottleneck. This JITs the whole rolling loop (per-bar TPO histogram
→ POC → 70% value area → failed-auction) to near-C. Pure-numpy Python stays the correctness oracle
(`features_ext._rolling_vp` fallback); this must produce identical columns.

Research (2026-07-12): numba @njit on a sliding-window histogram is 1-2 orders of magnitude over the
Python loop; the value-area growth has data-dependent branching that doesn't vectorize cleanly, so a
JIT'd scalar loop is the right tool (not np.vectorize). Reuse-first: numba, not hand-written C.
"""
from __future__ import annotations

import numpy as np

_MIN_BARS = 20                     # mirrors volume_profile._MIN_BARS

try:
    from numba import njit
    HAVE_NUMBA = True
except Exception:                  # numba missing → wrapper falls back to the Python oracle
    HAVE_NUMBA = False

    def njit(*args, **kwargs):      # no-op decorator so the module still imports
        def _wrap(fn):
            return fn
        return _wrap(args[0]) if args and callable(args[0]) else _wrap


@njit(cache=True)
def _kernel(H, L, C, V, window, nb):
    n = H.shape[0]
    poc = np.full(n, np.nan)
    vah = np.full(n, np.nan)
    val = np.full(n, np.nan)
    pos = np.full(n, np.nan)
    fl = np.zeros(n)
    fs = np.zeros(n)
    hist = np.zeros(nb)
    for i in range(window, n):
        s = i - window + 1
        lo = L[s]
        hi = H[s]
        vsum = 0.0
        for j in range(s, i + 1):
            if L[j] < lo:
                lo = L[j]
            if H[j] > hi:
                hi = H[j]
            vsum += V[j]
        if hi <= lo or vsum <= 0.0:
            continue
        bin_size = (hi - lo) / nb
        for b in range(nb):
            hist[b] = 0.0
        for j in range(s, i + 1):
            v = V[j]
            if v <= 0.0:
                continue
            li = int((L[j] - lo) / bin_size)      # int() truncates; L-lo>=0 so matches np.clip cast
            hj = int((H[j] - lo) / bin_size)
            if li < 0:
                li = 0
            elif li > nb - 1:
                li = nb - 1
            if hj < 0:
                hj = 0
            elif hj > nb - 1:
                hj = nb - 1
            span = hj - li + 1
            share = v / span
            for b in range(li, hj + 1):
                hist[b] += share
        total = 0.0
        for b in range(nb):
            total += hist[b]
        if total <= 0.0:
            continue
        poc_i = 0
        mx = hist[0]
        for b in range(1, nb):
            if hist[b] > mx:
                mx = hist[b]
                poc_i = b
        lo_i = poc_i
        hi_i = poc_i
        acc = hist[poc_i]
        target = 0.70 * total                     # VA_PCT
        while acc < target and (lo_i > 0 or hi_i < nb - 1):
            up = hist[hi_i + 1] if hi_i < nb - 1 else -1.0
            dn = hist[lo_i - 1] if lo_i > 0 else -1.0
            if up >= dn:
                hi_i += 1
                acc += hist[hi_i]
            else:
                lo_i -= 1
                acc += hist[lo_i]
        poc_v = lo + (poc_i + 0.5) * bin_size      # mids[poc_i]
        vah_v = lo + (hi_i + 1) * bin_size         # edges[hi_i+1]
        val_v = lo + lo_i * bin_size               # edges[lo_i]
        poc[i] = poc_v
        vah[i] = vah_v
        val[i] = val_v
        span_va = vah_v - val_v
        if span_va == 0.0:
            span_va = bin_size
        if span_va == 0.0:
            span_va = 1.0
        pos[i] = (C[i] - poc_v) / span_va
        inside = (val_v <= C[i]) and (C[i] <= vah_v)
        if (C[i - 1] < val_v) and inside:
            fl[i] = 1.0
        elif (C[i - 1] > vah_v) and inside:
            fs[i] = 1.0
    return poc, vah, val, pos, fl, fs


def rolling_vp(H, L, C, V, window: int = 96):
    """Rolling Volume-Profile columns (poc, vah, val, pos, failed_long, failed_short) as 6 float64
    arrays. Returns None when unusable (caller then keeps the Python oracle). H/L/C/V: 1-D float64."""
    H = np.ascontiguousarray(H, dtype="float64")
    L = np.ascontiguousarray(L, dtype="float64")
    C = np.ascontiguousarray(C, dtype="float64")
    V = np.ascontiguousarray(V, dtype="float64")
    n = H.shape[0]
    if window < _MIN_BARS or n <= window:
        return None                                # matches the oracle's all-NaN / unavailable case
    nb = window // 2
    if nb < 10:
        nb = 10
    elif nb > 60:
        nb = 60
    return _kernel(H, L, C, V, int(window), int(nb))
