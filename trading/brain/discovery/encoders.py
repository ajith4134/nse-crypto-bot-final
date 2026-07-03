"""Self-supervised market-window encoder — the net that INVENTS its own features.

The video's lesson: a deep net turns perception → concepts by inventing features in its
hidden layers, no hand-engineering. Here a small self-supervised autoencoder is trained to
reconstruct standardized windows of market perception (OHLCV / close). Its bottleneck latent
IS the set of self-invented features that later stages probe, name, and visualize.

CPU-first, torch-guarded (numpy PCA fallback if torch is absent) so the package always imports.
"""
from __future__ import annotations

import warnings

import numpy as np


def make_windows(series: np.ndarray, w: int = 24, stride: int = 1) -> np.ndarray:
    """Overlapping causal windows of a 1-D (or multi-col) series → [n, w*channels]."""
    s = np.asarray(series, float)
    if s.ndim == 1:
        s = s.reshape(-1, 1)
    s = np.nan_to_num(s)
    n, c = s.shape
    idx = list(range(w, n + 1, stride))
    if not idx:
        idx = [n]
    out = np.zeros((len(idx), w * c), float)
    for k, end in enumerate(idx):
        win = s[max(0, end - w):end]
        if len(win) < w:
            win = np.vstack([np.repeat(win[:1], w - len(win), axis=0), win])
        out[k] = win.reshape(-1)
    return out


class WindowEncoder:
    """Self-supervised autoencoder over market windows. `latent_dim` invented features."""

    def __init__(self, latent_dim: int = 16, hidden: int = 64, epochs: int = 50, seed: int = 0):
        self.latent_dim = latent_dim
        self.hidden = hidden
        self.epochs = epochs
        self.seed = seed
        self._model = None
        self._pca = None
        self._mu = None
        self._sd = None
        self.backend = None

    def fit(self, W: np.ndarray) -> "WindowEncoder":
        X = np.asarray(W, float)
        X = np.nan_to_num(X)
        self._mu, self._sd = X.mean(0), X.std(0) + 1e-9
        Xn = (X - self._mu) / self._sd
        try:
            import torch
            import torch.nn as nn
            torch.manual_seed(self.seed)
            din = Xn.shape[1]
            ld, hd = self.latent_dim, self.hidden

            class _AE(nn.Module):
                def __init__(s):
                    super().__init__()
                    s.enc = nn.Sequential(nn.Linear(din, hd), nn.GELU(), nn.Linear(hd, ld))
                    s.dec = nn.Sequential(nn.Linear(ld, hd), nn.GELU(), nn.Linear(hd, din))

                def forward(s, x):
                    z = s.enc(x)
                    return s.dec(z), z

            self._model = _AE()
            xt = torch.tensor(Xn, dtype=torch.float32)
            opt = torch.optim.Adam(self._model.parameters(), lr=0.01)
            lossf = nn.MSELoss()
            self._model.train()
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                for _ in range(self.epochs):
                    opt.zero_grad()
                    recon, _ = self._model(xt)
                    loss = lossf(recon, xt)
                    loss.backward(); opt.step()
            self._model.eval()
            self.backend = "torch_ae"
        except Exception:
            # numpy PCA fallback — still "invents" latent factors, just linearly
            from sklearn.decomposition import PCA
            self._pca = PCA(n_components=min(self.latent_dim, Xn.shape[1]),
                            random_state=self.seed).fit(Xn)
            self.backend = "pca"
        return self

    def encode(self, W: np.ndarray) -> np.ndarray:
        Xn = (np.nan_to_num(np.asarray(W, float)) - self._mu) / self._sd
        if self._model is not None:
            import torch
            with torch.no_grad():
                _, z = self._model(torch.tensor(Xn, dtype=torch.float32))
            return z.numpy()
        return self._pca.transform(Xn)
