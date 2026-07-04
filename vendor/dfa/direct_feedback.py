"""Direct Feedback Alignment broadcaster — fixed random error projection.

One error vector -> a pseudo-gradient for every registered layer, all in parallel,
via per-layer fixed random feedback matrices B_l (never updated, the defining property
of DFA). Layers may be added dynamically (new gates/glue appearing as CORTEX grows).
"""
from __future__ import annotations

import numpy as np

__all__ = ["DFABroadcaster"]


class DFABroadcaster:
    """Broadcast a scalar/vector error to fixed random pseudo-gradients per layer.

    Parameters
    ----------
    error_dim : width of the error signal (1 for a scalar trade-outcome error).
    seed      : RNG seed; the feedback matrices are drawn ONCE and frozen.
    scale     : std of the Gaussian feedback entries. The classic DFA choice is a
                fixed random matrix; scale only rescales the learning-rate baseline.
    sign_only : DRTP-style — use sign(B) instead of B (bounded, hardware-cheap).
    """

    def __init__(self, error_dim: int = 1, *, seed: int = 0, scale: float = 1.0,
                 sign_only: bool = False):
        if error_dim < 1:
            raise ValueError("error_dim must be >= 1")
        self.error_dim = int(error_dim)
        self.scale = float(scale)
        self.sign_only = bool(sign_only)
        self._rng = np.random.default_rng(seed)
        self._B: dict[str, np.ndarray] = {}   # layer name -> (dim, error_dim) frozen

    # -- registration --------------------------------------------------------
    def register(self, name: str, dim: int) -> np.ndarray:
        """Register a layer of width `dim`; returns its frozen feedback matrix."""
        if dim < 1:
            raise ValueError(f"layer '{name}' dim must be >= 1")
        if name not in self._B:
            B = self._rng.standard_normal((dim, self.error_dim)) * self.scale
            if self.sign_only:
                B = np.sign(B)
            self._B[name] = B
        return self._B[name]

    def register_all(self, dims: dict[str, int]) -> None:
        for name, dim in dims.items():
            self.register(name, dim)

    @property
    def layers(self) -> list[str]:
        return list(self._B)

    # -- broadcast -----------------------------------------------------------
    def broadcast(self, error) -> dict[str, np.ndarray]:
        """Project `error` to a pseudo-gradient vector for every registered layer.

        error : scalar or shape (error_dim,). Returns {layer: (dim,) pseudo-grad}.
        DFA pseudo-grad for layer l is B_l @ error (times the layer activation
        derivative, which the caller applies — here we return the raw projection).
        """
        e = np.atleast_1d(np.asarray(error, dtype=float)).ravel()
        if e.shape[0] != self.error_dim:
            raise ValueError(f"error width {e.shape[0]} != error_dim {self.error_dim}")
        return {name: (B @ e) for name, B in self._B.items()}

    def broadcast_to(self, name: str, dim: int, error) -> np.ndarray:
        """Convenience: register-if-needed then broadcast to a single layer."""
        self.register(name, dim)
        e = np.atleast_1d(np.asarray(error, dtype=float)).ravel()
        return self._B[name] @ e
