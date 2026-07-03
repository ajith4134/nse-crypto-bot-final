"""Read out the self-invented features: sparse-autoencoder probe over the encoder latent.

Distill.pub's neuron-probing, for markets: train a sparse dictionary autoencoder on the
encoder's latent activations to crack polysemantic latent units into MONOSEMANTIC dictionary
features, then find the windows that maximally activate each feature (so the next stage can
name the concept). Reuse: dictionary_learning.AutoEncoder (saprmarks); torch training loop.
"""
from __future__ import annotations

import warnings

import numpy as np


class SAEProbe:
    """Sparse dictionary features over latent Z. `dict_size` monosemantic candidates."""

    def __init__(self, dict_size: int = 32, l1: float = 3e-2, epochs: int = 90, seed: int = 0):
        self.dict_size = dict_size
        self.l1 = l1
        self.epochs = epochs
        self.seed = seed
        self._sae = None
        self._mu = None
        self._sd = None

    def fit(self, Z: np.ndarray) -> "SAEProbe":
        X = np.nan_to_num(np.asarray(Z, float))
        self._mu, self._sd = X.mean(0), X.std(0) + 1e-9
        Xn = (X - self._mu) / self._sd
        try:
            import torch
            from dictionary_learning import AutoEncoder
            torch.manual_seed(self.seed)
            self._sae = AutoEncoder(activation_dim=Xn.shape[1], dict_size=self.dict_size)
            xt = torch.tensor(Xn, dtype=torch.float32)
            opt = torch.optim.Adam(self._sae.parameters(), lr=1e-2)
            self._sae.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.epochs):
                    opt.zero_grad()
                    f = self._sae.encode(xt)
                    recon = self._sae.decode(f)
                    loss = ((recon - xt) ** 2).mean() + self.l1 * f.abs().mean()
                    loss.backward(); opt.step()
            self._sae.eval()
        except Exception:
            self._sae = None                    # fall back: use latent dims as "features"
        return self

    def features(self, Z: np.ndarray) -> np.ndarray:
        """Per-window sparse feature activations [n, dict_size] (or the latent if no SAE)."""
        Xn = (np.nan_to_num(np.asarray(Z, float)) - self._mu) / self._sd
        if self._sae is None:
            return Xn
        import torch
        with torch.no_grad():
            f = self._sae.encode(torch.tensor(Xn, dtype=torch.float32)).numpy()
        return np.maximum(f, 0.0)               # ReLU-style activations

    def max_activating(self, F: np.ndarray, k: int = 5) -> dict:
        """For each feature column, the indices of its top-k most-activating windows."""
        out = {}
        for j in range(F.shape[1]):
            col = F[:, j]
            order = np.argsort(col)[::-1][:k]
            out[j] = [int(i) for i in order if col[i] > 0]
        return out
