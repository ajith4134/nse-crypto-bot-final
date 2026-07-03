# Manifold / Concept-Space Visualization + Clustering — OSS SELECT (Phase-1)

Goal: show market "perception space" collapsing into concept clusters/manifolds — CPU-first Python
embeddings -> 2D/3D coordinates -> web-dashboard render. Pipeline = **reducer + clusterer + JS renderer**.

## Ranked shortlist

| Project | Repo | Key features | Activity | CPU-fit | Score | Verdict |
|---|---|---|---|---|---|---|
| **UMAP (umap-learn)** | github.com/lmcinnes/umap | Nonlinear manifold reducer; densMAP (density-preserving) shows manifolds collapsing; supervised/semi-supervised; sklearn API; `transform()` for new points; inverse_transform | 8.2k★, rel 0.5.12 Apr-2026 | Numba/CPU, MNIST(70k)<1min; 100k fine | 9 | **WINNER reducer** — densMAP is the exact "concept manifold" visual |
| **openTSNE** | github.com/pavlin-policar/openTSNE | FIt-SNE, multiscale global structure, `transform()` to embed new pts into ref space, OpenMP parallel | 1.6k★, v1.0.2 Aug-2024 | C++/Cython, scales to millions | 8 | Strong alt/complement; best for streaming new pts into fixed space |
| **PaCMAP / LocalMAP** | github.com/YingfanWang/PaCMAP | Preserves local+global; LocalMAP (AAAI-25) = cleanest cluster separation; FAISS backend; sklearn API | 993★, v0.9.1 Mar-2026 | CPU, auto-neighbors >10k; fast | 8 | Best cluster *separability* — swap in when clusters must look crisp |
| **HDBSCAN** | github.com/scikit-learn-contrib/hdbscan | Density clustering, varying densities, noise label, soft/probabilistic membership, condensed tree; also in sklearn 1.9 | 531★ + in sklearn core; wheels Jun-2026 | CPU, fast on 2D projected coords | 9 | **WINNER clusterer** — run on reduced coords -> concept clusters + noise |
| **datamapplot** | github.com/TutteInstitute/datamapplot | Auto cluster labeling; interactive HTML (WebGL via deck.gl/datashader); pan/zoom/search; static + web export | 1.0k★, 0.7.3 May-2026 | Python, uses datashader for big N | 8 | **Fastest path to dashboard** — Python->interactive HTML in one call |
| **regl-scatterplot** | github.com/flekschas/regl-scatterplot | WebGL scatter up to 20M pts, lasso select, color/size encode, transitions, React/Vue examples | 235★, v1.16.0 May-2026 | Pure JS front-end (renders coords) | 8 | **WINNER JS renderer** for custom React dashboard; feed x,y,cluster |
| deck.gl ScatterplotLayer | deck.gl | WebGL 2D/3D, millions of pts, layered, React bindings | very active | JS front-end | 7 | Heavier; use if you want 3D manifold or map-style layers |
| PHATE | github.com/KrishnaswamyLab/PHATE | Diffusion-based manifold embedding, great for continuous trajectories/branches | 541★, Mar-2026 | CPU, heavier than UMAP | 6 | Nice for "flow" manifolds; slower, niche vs UMAP |
| TriMap | github.com/eamid/trimap | Triplet global-structure reducer | low-moderate | CPU | 5 | Superseded by PaCMAP for our need |
| ivis | github.com/beringresearch/ivis | Siamese-net parametric embedding, out-of-sample | moderate | needs TF/Keras (heavier) | 5 | Parametric alt; env weight not worth it here |
| scikit-dimension | github.com/j-bac/scikit-dimension | Intrinsic dimension estimators (manifold ID) | moderate | CPU, light | 6 | Optional metric: quantify "collapse" (ID drop) as a number |
| giotto-tda / ripser | github.com/giotto-ai/giotto-tda | Persistent homology, topology of manifolds (loops/voids), sklearn API + C++ | moderate | CPU | 6 | Optional: topological summary of concept space, not the visual |
| FINCH | github.com/ssarfraz/FINCH-Clustering | Parameter-free hierarchical clustering, very fast | moderate | CPU | 6 | Good param-free alt to HDBSCAN if k unknown & speed matters |
| TF Embedding Projector | github.com/tensorflow/embedding-projector | Standalone 3D PCA/t-SNE/UMAP web viewer | legacy | browser | 5 | Great inspiration, but standalone app not embeddable cleanly |

## Recommendation — STITCH 3 (reducer + clusterer + renderer)

Build the "perception space collapsing into concepts" visual as a **three-part pipeline**:

1. **Reducer = UMAP with densMAP** (`densmap=True`) as the default — it is the highest-star, actively
   maintained, CPU-fast manifold reducer, and densMAP literally preserves local density so the video's
   "collapse into dense concept blobs" reads correctly. Keep **PaCMAP/LocalMAP** as a drop-in alternate
   for maximally *separated* clusters, and use UMAP/openTSNE `transform()` to stream new market states
   into a fixed embedding without recomputing (essential for a live dashboard).
2. **Clusterer = HDBSCAN** run on the 2D/3D coordinates — density-based, auto-detects the number of
   concept clusters, labels outliers as noise, and gives soft membership for glow/opacity effects.
3. **Renderer =** for the fastest ship, **datamapplot** emits an interactive, labeled WebGL HTML map
   directly from Python (auto cluster labels). For the tighter custom React dashboard, feed the
   `{x, y, clusterId, prob}` arrays to **regl-scatterplot** (20M-pt WebGL, lasso, smooth transitions —
   ideal for animating the "collapse"). Optionally add **scikit-dimension** to display the intrinsic
   dimension dropping as an honest scalar of the collapse.

Winner-if-forced-to-one: **datamapplot** (it internally already stitches UMAP-style coords + labeling +
WebGL export), but the strongest result is UMAP-densMAP + HDBSCAN + regl-scatterplot.
