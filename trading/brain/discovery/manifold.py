"""Concept-space manifold: project the invented-feature space to 2-D and cluster it.

The video's closing visual — messy perception space collapsing into tight concept manifolds.
UMAP (densMAP) reduces the encoder latent to 2-D; HDBSCAN finds the concept clusters. Both
degrade to PCA / KMeans if the OSS reducers are absent, so the panel always has coordinates.
"""
from __future__ import annotations

import warnings

import numpy as np


def project(Z: np.ndarray, seed: int = 0) -> dict:
    """Return {points:[{x,y,cluster,idx}], n_clusters, reducer, clusterer}."""
    X = np.nan_to_num(np.asarray(Z, float))
    n = len(X)
    if n < 3:
        pts = [{"x": 0.0, "y": 0.0, "cluster": -1, "idx": i} for i in range(n)]
        return {"points": pts, "n_clusters": 0, "reducer": "none", "clusterer": "none"}

    # ---- reduce to 2-D ----
    coords, reducer = None, None
    try:
        import umap
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            coords = umap.UMAP(n_components=2, n_neighbors=min(15, n - 1), min_dist=0.1,
                               densmap=n >= 20, random_state=seed).fit_transform(X)
        reducer = "umap_densmap" if n >= 20 else "umap"
    except Exception:
        from sklearn.decomposition import PCA
        coords = PCA(n_components=2, random_state=seed).fit_transform(X)
        reducer = "pca"

    # ---- cluster the 2-D map ----
    labels, clusterer = None, None
    try:
        import hdbscan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            labels = hdbscan.HDBSCAN(min_cluster_size=max(3, n // 20)).fit_predict(coords)
        clusterer = "hdbscan"
    except Exception:
        from sklearn.cluster import KMeans
        k = int(min(6, max(2, n // 15)))
        labels = KMeans(n_clusters=k, n_init=5, random_state=seed).fit_predict(coords)
        clusterer = "kmeans"

    c = np.asarray(coords, float)
    lo, hi = c.min(0), c.max(0)
    rng = np.where(hi - lo > 1e-9, hi - lo, 1.0)
    cn = (c - lo) / rng                                  # normalize to [0,1] for the panel
    pts = [{"x": round(float(cn[i, 0]), 4), "y": round(float(cn[i, 1]), 4),
            "cluster": int(labels[i]), "idx": i} for i in range(n)]
    n_clusters = len({int(v) for v in labels if int(v) >= 0})
    return {"points": pts, "n_clusters": n_clusters, "reducer": reducer, "clusterer": clusterer}
