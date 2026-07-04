"""AI-scientist idea #9 — VAE synthetic factors + scenario generator (CPU torch).

Two capabilities from one small β-VAE over the feature bus:

  1. ``VAEFactorNode`` (NodeProtocol) — encodes raw features into K *decorrelated latent factors*
     (β-VAE KL pressure pushes the latents toward an independent unit-Gaussian, i.e. ANTI-CROWDING:
     the model trades on compressed orthogonal factors instead of the raw, mutually-correlated
     features every other model already uses), then a logistic head on the latents predicts the
     target. Falls back to a plain logistic-on-raw-features if torch is unavailable — same
     NodeProtocol either way (graceful degradation, the pool convention).

  2. ``SyntheticScenarioGenerator`` — wraps the trained decoder; ``generate(n)`` samples the latent
     prior and decodes to synthetic feature rows for STRESS-TESTING strategies and sleep-replay
     (novel-but-plausible regimes the historical tape never showed).

Reuse note: a β-VAE is a standard architecture with no single NodeProtocol-shaped OSS to vendor;
this is a compact, correct torch implementation (glue-level), CPU-sized by default.
"""
from __future__ import annotations

import numpy as np

from core.node_protocol import BaseNode, IOSchema, Labels, Matrix, Vector

try:
    import torch
    import torch.nn as nn
    _HAS_TORCH = True
except Exception:                                   # torch absent → logistic fallback
    _HAS_TORCH = False


if _HAS_TORCH:
    class _VAE(nn.Module):
        def __init__(self, in_dim: int, latent: int, hidden: int):
            super().__init__()
            self.enc = nn.Sequential(nn.Linear(in_dim, hidden), nn.ReLU(),
                                     nn.Linear(hidden, hidden), nn.ReLU())
            self.mu = nn.Linear(hidden, latent)
            self.logvar = nn.Linear(hidden, latent)
            self.dec = nn.Sequential(nn.Linear(latent, hidden), nn.ReLU(),
                                     nn.Linear(hidden, hidden), nn.ReLU(),
                                     nn.Linear(hidden, in_dim))

        def encode(self, x):
            h = self.enc(x)
            return self.mu(h), self.logvar(h)

        def reparam(self, mu, logvar):
            std = torch.exp(0.5 * logvar)
            return mu + std * torch.randn_like(std)

        def forward(self, x):
            mu, logvar = self.encode(x)
            z = self.reparam(mu, logvar)
            return self.dec(z), mu, logvar


class VAEFactorNode(BaseNode):
    """β-VAE latent-factor node: raw features → K decorrelated latents → logistic head → p(class=1)."""

    kind = "vae_factor"

    def __init__(self, name: str = "vae_factor", latent: int = 6, hidden: int = 24,
                 beta: float = 1.0, epochs: int = 60, col: int = 0):
        self.name = name
        self.summary = (f"β-VAE latent factors (K={latent}, β={beta}): trades on decorrelated "
                        "compressed factors (anti-crowding) instead of raw correlated features.")
        self.latent = int(latent)
        self.hidden = int(hidden)
        self.beta = float(beta)
        self.epochs = int(epochs)
        self.col = int(col)
        self.task = "binary"
        self.head = "y"
        self.schema = IOSchema(0, "numeric feature rows", "p(class=1)")
        self._vae = None
        self._clf = None
        self._mu_mean = None
        self._mu_std = None
        self.fell_back = False

    # ---- helpers -------------------------------------------------------------------------
    def _latents(self, X: np.ndarray) -> np.ndarray:
        """Encode rows → latent means (deterministic, the factor representation)."""
        with torch.no_grad():
            mu, _ = self._vae.encode(torch.as_tensor(X, dtype=torch.float32))
        return mu.cpu().numpy()

    # ---- NodeProtocol --------------------------------------------------------------------
    def fit(self, X: Matrix, y: Labels) -> "VAEFactorNode":
        A = np.asarray(X, dtype=np.float32)
        ya = np.asarray(y).astype(int)
        self.schema = IOSchema(A.shape[1], f"{A.shape[1]} numeric features", "p(class=1)")
        # standardize inputs (VAE + logistic both like it)
        self._mu_mean = A.mean(0)
        self._mu_std = A.std(0) + 1e-8
        As = (A - self._mu_mean) / self._mu_std

        if not _HAS_TORCH or len(set(ya.tolist())) < 2:
            from sklearn.linear_model import LogisticRegression
            self.fell_back = True
            self._clf = LogisticRegression(max_iter=500).fit(As, ya) if len(set(ya.tolist())) >= 2 else None
            return self

        torch.manual_seed(0)
        self._vae = _VAE(As.shape[1], self.latent, self.hidden)
        opt = torch.optim.Adam(self._vae.parameters(), lr=1e-3)
        xb = torch.as_tensor(As, dtype=torch.float32)
        self._vae.train()
        for _ in range(self.epochs):
            opt.zero_grad()
            recon, mu, logvar = self._vae(xb)
            recon_loss = nn.functional.mse_loss(recon, xb, reduction="mean")
            kl = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())
            (recon_loss + self.beta * kl).backward()
            opt.step()
        self._vae.eval()
        # logistic head on the (decorrelated) latent factors
        from sklearn.linear_model import LogisticRegression
        Z = self._latents(As)
        self._clf = LogisticRegression(max_iter=500).fit(Z, ya)
        return self

    def predict_proba(self, X: Matrix) -> Vector:
        A = np.asarray(X, dtype=np.float32)
        As = (A - self._mu_mean) / self._mu_std
        if self._clf is None:                          # degenerate single-class fit
            return [0.5] * len(A)
        Z = As if self.fell_back else self._latents(As)
        return self._clf.predict_proba(Z)[:, 1].tolist()

    def predict(self, X: Matrix) -> Labels:
        return [1 if p >= 0.5 else 0 for p in self.predict_proba(X)]

    # ---- scenario generation -------------------------------------------------------------
    def generator(self) -> "SyntheticScenarioGenerator":
        return SyntheticScenarioGenerator(self)


class SyntheticScenarioGenerator:
    """Samples the VAE latent prior → decodes → synthetic feature rows (stress-test / sleep-replay)."""

    def __init__(self, node: VAEFactorNode):
        self._node = node

    @property
    def available(self) -> bool:
        return _HAS_TORCH and self._node._vae is not None

    def generate(self, n: int = 64, scale: float = 1.0, seed: int = 0) -> Matrix:
        """n synthetic rows in the ORIGINAL feature space. ``scale``>1 pushes into rarer
        (more-extreme) regimes for stress-testing. Returns [] if the VAE is unavailable."""
        if not self.available:
            return []
        node = self._node
        with torch.no_grad():
            torch.manual_seed(int(seed))
            z = torch.randn(int(n), node.latent) * float(scale)
            syn = node._vae.dec(z).cpu().numpy()
        return (syn * node._mu_std + node._mu_mean).tolist()   # de-standardize to raw feature space


def vae_factor_node(name: str = "vae_factor") -> VAEFactorNode:
    """Zero-arg factory (pool + autoload convention)."""
    return VAEFactorNode(name=name)
